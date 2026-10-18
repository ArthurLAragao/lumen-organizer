"""Only fictional vaults. No export/import of personal data."""
import unittest
from pathlib import Path
from unittest.mock import patch
import tkinter as tk
import time
import gc

from lumen_organizer.export_workflow import ExportWorkflow
from lumen_organizer.destinations import FIXED
from lumen_organizer.atlas_transfer import decode_package
from lumen_organizer.models import LumenError
from lumen_organizer.ui import App
from .support import FictionalWorkspace, bounded_writes, ROOT


class ExportWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.workspace = FictionalWorkspace()
        self.w = self.workspace.__enter__()
        self.bound = bounded_writes(self.w.root)
        self.bound.__enter__()
        self.source = self.w.vault / FIXED["ferramentas"] / "fictional.md"
        self.source.write_bytes((ROOT / "tests/fixtures/atlas-export/reviewed.md").read_bytes())
        self.output = self.w.root / "out"
        self.output.mkdir()
        self.flow = ExportWorkflow(self.w.state)

    def tearDown(self):
        self.bound.__exit__(None, None, None)
        self.workspace.__exit__()

    def finish(self, job):
        value = job.work()
        self.flow.complete(job, value)
        return value

    def ready(self):
        self.finish(self.flow.configure(self.w.vault))
        self.flow.select(source=self.source, category="ferramentas")
        self.finish(self.flow.validate())
        self.finish(self.flow.create_registry(confirmed=True))
        self.finish(self.flow.register(confirmed=True))
        self.finish(self.flow.prepare())
        self.flow.set_destination(self.output / "fixture.lumen-atlas.json")
        self.finish(self.flow.review())
        return self.flow.confirmation

    def test_complete_manual_package_retains_exact_source_and_unknown_delivery(self):
        original = self.source.read_bytes()
        review = self.ready()
        self.finish(self.flow.commit(review, confirmed=True))
        self.assertEqual(self.source.read_bytes(), original)
        package = decode_package(self.flow.output.read_bytes())
        self.assertEqual(package.source_bytes, original)
        self.assertEqual(self.flow.registry.record(self.flow.archive_id).delivery, "unknown")
        self.assertIn("ainda não foi confirmada", self.flow.status)

    def test_cancel_never_generates_package(self):
        review = self.ready()
        self.assertIsNone(self.flow.commit(review, confirmed=False))
        self.assertEqual(self.flow.registry.records(), ())
        self.assertEqual(list(self.output.iterdir()), [])
        self.assertEqual(list(self.flow.registry.archives.iterdir()), [])

    def test_source_change_after_review_is_blocked(self):
        review = self.ready()
        self.source.write_bytes(self.source.read_bytes() + b"\nChanged fictional content")
        self.finish(self.flow.commit(review, confirmed=True))
        self.assertEqual(self.flow.error, "export_source_changed")
        self.assertEqual(list(self.output.iterdir()), [])

    def test_destination_change_invalidates_review(self):
        review = self.ready()
        self.flow.set_destination(self.output / "other.lumen-atlas.json")
        with self.assertRaisesRegex(LumenError, "export_confirmation_stale"):
            self.flow.commit(review, confirmed=True)
        self.assertEqual(self.flow.registry.records(), ())

    def test_collision_blocks_before_archive_and_never_overwrites(self):
        review = self.ready()
        review.destination.write_bytes(b"existing fictional file")
        with self.assertRaisesRegex(LumenError, "export_package_collision"):
            self.flow.commit(review, confirmed=True).work()
        self.assertEqual(review.destination.read_bytes(), b"existing fictional file")
        self.assertEqual(self.flow.registry.records(), ())

    def test_blocked_lifecycle_does_not_get_edited_or_registered(self):
        self.finish(self.flow.configure(self.w.vault))
        data = self.source.read_bytes().replace(b"status: reviewed", b"status: inbox").replace(b"lumen_export: true", b"lumen_export: false")
        self.source.write_bytes(data)
        self.flow.select(source=self.source, category="ferramentas")
        self.finish(self.flow.validate())
        self.assertFalse(self.flow.validation.valid)
        self.assertEqual(self.source.read_bytes(), data)
        self.assertIsNone(self.flow.registry)

    def test_outside_area_is_not_read(self):
        self.finish(self.flow.configure(self.w.vault))
        self.flow.select(source=self.w.source, category="ferramentas")
        with patch.object(Path, "open", side_effect=AssertionError("Source must not be opened")):
            self.finish(self.flow.validate())
        self.assertFalse(self.flow.validation.valid)

    def test_copy_failure_retains_original_archive_for_explicit_resend(self):
        review = self.ready()
        with patch("lumen_organizer.export_workflow.save_prepared", side_effect=OSError("private fixture")):
            self.finish(self.flow.commit(review, confirmed=True))
        self.assertIsNone(self.flow.output)
        self.assertEqual(self.flow.error, "export_copy_failed")
        self.finish(self.flow.resend(confirmed=True))
        self.assertEqual(len(self.flow.registry.records()), 1)
        self.assertTrue(self.flow.output.exists())

    def test_unverified_output_halts_instead_of_blind_resend(self):
        review = self.ready()
        with patch("lumen_organizer.export_workflow.save_prepared", side_effect=LumenError("export_copy_unverified")):
            self.finish(self.flow.commit(review, confirmed=True))
        self.assertTrue(self.flow.halted)
        self.assertIsNotNone(self.flow.archive_id)
        with self.assertRaisesRegex(LumenError, "export_review_required"):
            self.flow.resend(confirmed=True)

    def test_history_failure_requires_reconciliation_not_blind_retry(self):
        review = self.ready()
        with patch.object(self.flow.registry, "_complete", side_effect=LumenError("export_registry_unavailable")):
            self.finish(self.flow.commit(review, confirmed=True))
        self.assertTrue(self.flow.halted)
        with self.assertRaisesRegex(LumenError, "export_reconciliation_required"):
            self.flow.prepare()
        self.finish(self.flow.reconcile())
        self.finish(self.flow.resend(confirmed=True))
        self.assertTrue(self.flow.output.exists())

    def test_repeated_export_requires_explicit_baseline_and_preserves_identity(self):
        review = self.ready()
        self.finish(self.flow.commit(review, confirmed=True))
        first = self.flow.registry.record(self.flow.archive_id)
        self.flow.select(source=self.source, category="ferramentas")
        self.finish(self.flow.validate())
        self.assertEqual(self.flow.identity.integration_id, first.integration_id)
        self.assertIsNone(self.flow.baseline)
        self.flow.baseline = first.id
        self.finish(self.flow.prepare())
        self.assertEqual(decode_package(self.flow.plan.package_bytes).baseline_sha256, first.comparison_sha256)
        self.assertEqual(first.delivery, "unknown")


class ExportWidgetTests(unittest.TestCase):
    """Real Tk widgets, automated assertions; not a manual visual acceptance."""
    finish = ExportWorkflowTests.finish
    ready = ExportWorkflowTests.ready

    def setUp(self):
        gc.collect()  # Collect old Tk cycles on the owner thread before starting a worker.
        ExportWorkflowTests.setUp(self)
        try:
            self.root = tk.Tk()
        except tk.TclError:
            ExportWorkflowTests.tearDown(self)
            self.skipTest("Tk display unavailable")
        self.root.withdraw()
        self.app = App(self.root, self.w.state, load_settings=False)
        self.app.export_button.invoke()
        self.window = self.app.export_window
        self.flow = self.window.workflow

    def tearDown(self):
        if hasattr(self, "app"):
            try:
                self.pump()
            finally:
                self.app.destroy()
                self.window = self.app = self.root = None
                gc.collect()
                ExportWorkflowTests.tearDown(self)

    def pump(self):
        deadline = time.monotonic() + 10
        while self.flow.active and time.monotonic() < deadline:
            self.root.update()
            time.sleep(.005)
        self.root.update()
        self.assertIsNone(self.flow.active)

    def test_widget_flow_and_explicit_confirmation(self):
        with patch("lumen_organizer.export_ui.filedialog.askdirectory", return_value=str(self.w.vault)):
            self.window.vault_button.invoke()
        self.pump()
        with patch("lumen_organizer.export_ui.filedialog.askopenfilename", return_value=str(self.source)):
            self.window.file_button.invoke()
        # Choose the actual approved label through the presentation mapping.
        from lumen_organizer.presentation import CATEGORY_LABELS
        self.window.category_box.set(CATEGORY_LABELS["ferramentas"])
        self.window.category_box.event_generate("<<ComboboxSelected>>")
        self.window.validate_button.invoke()
        self.pump()
        with patch("lumen_organizer.export_ui.messagebox.askyesno", return_value=True):
            self.window.registry_button.invoke()
            self.pump()
            self.window.identity_button.invoke()
            self.pump()
        self.window.prepare_button.invoke()
        self.pump()
        self.assertEqual(str(self.window.preview.cget("state")), "disabled")
        self.assertIn("status: reviewed", self.window.preview.get("1.0", "end"))
        with patch("lumen_organizer.export_ui.filedialog.asksaveasfilename", return_value=str(self.output / "ui.lumen-atlas.json")):
            self.window.destination_button.invoke()
        self.window.review_button.invoke()
        self.pump()
        self.assertIsNotNone(self.window.dialog)
        self.assertEqual(self.flow.registry.records(), ())
        self.window.confirm_button.invoke()
        self.pump()
        self.assertTrue(self.flow.output.exists())

    def test_picker_cancellation_and_preview_cancel_create_no_package(self):
        with patch("lumen_organizer.export_ui.filedialog.askdirectory", return_value=""):
            self.window.vault_button.invoke()
        self.assertIsNone(self.flow.policy)
        review = self.ready()
        self.window.render()
        self.window.show_confirmation(review)
        self.window.confirm_cancel_button.invoke()
        self.root.update()
        self.assertIsNone(self.window.dialog)
        self.assertEqual(self.flow.registry.records(), ())

    def test_export_layout_scaling_focus_and_complete_long_paths(self):
        # Tk scaling only. This does not claim OS DPI/assistive-technology testing.
        for scale in (1.0, 1.25, 1.5, 2.0):
            with self.subTest(scale=scale):
                self.app.destroy()
                self.window = self.app = self.root = None
                gc.collect()
                self.root = tk.Tk()
                self.root.withdraw()
                self.root.tk.call("tk", "scaling", scale * 96 / 72)
                self.app = App(self.root, self.w.state, load_settings=False)
                self.app.export_button.invoke()
                self.window = self.app.export_window
                self.flow = self.window.workflow
                self.window.window.deiconify()
                minimum = self.window.window.minsize()
                self.window.window.geometry(f"{minimum[0]}x{minimum[1]}")
                self.root.update()
                for button in (self.window.review_button, self.window.cancel_button,
                               self.window.reconcile_button, self.window.resend_button):
                    x = button.winfo_rootx() - self.window.window.winfo_rootx()
                    y = button.winfo_rooty() - self.window.window.winfo_rooty()
                    self.assertGreaterEqual(x, 0)
                    self.assertGreaterEqual(y, 0)
                    self.assertLessEqual(x + button.winfo_width(), self.window.window.winfo_width())
                    self.assertLessEqual(y + button.winfo_height(), self.window.window.winfo_height())
                self.window.file_button.focus_force()
                self.root.update()
                self.assertIs(self.root.focus_get(), self.window.file_button)
        # Inspect the complete path and confirmation at the final tested scale.
        self.finish(self.flow.configure(self.w.vault))
        self.flow.select(source=self.source, category="ferramentas")
        self.finish(self.flow.validate())
        self.finish(self.flow.create_registry(confirmed=True))
        self.finish(self.flow.register(confirmed=True))
        self.finish(self.flow.prepare())
        self.flow.set_destination(self.output / ("fictional-" * 16 + ".lumen-atlas.json"))
        self.finish(self.flow.review())
        self.window.render()
        self.window.show_confirmation(self.flow.confirmation)
        self.root.update()
        self.assertIn(str(self.flow.destination), self.window.summary())
        self.assertEqual(self.window.destination_var.get(), str(self.flow.destination))
        self.assertIs(self.root.focus_get(), self.window.confirm_cancel_button)
        self.window.confirm_cancel_button.invoke()
