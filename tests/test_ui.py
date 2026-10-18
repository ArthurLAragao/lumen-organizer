"""Automated Tk widget checks; these are not visual/manual acceptance tests."""

from pathlib import Path
from types import SimpleNamespace
import threading
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from lumen_organizer.models import ImportResult, LumenError
from lumen_organizer.presentation import CATEGORY_LABELS, visual_status
from lumen_organizer.styles import COLORS, SPACING
from lumen_organizer.ui import App, ConfirmationDialog, FolderDialog, LIFECYCLE
from .support import FictionalWorkspace, bounded_writes


class TkWidgetTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest("Tk display unavailable: " + str(exc))
        self.root.withdraw()
        self.workspace = FictionalWorkspace()
        self.w = self.workspace.__enter__()
        self.bound = bounded_writes(self.w.root)
        self.bound.__enter__()
        self.app = App(self.root, self.w.state, load_settings=False)
        self.callback_errors = []
        self.root.report_callback_exception = lambda *args: self.callback_errors.append(args)
        self.release = threading.Event()
        self.owner = threading.get_ident()
        original_render = self.app.render
        def main_thread_render():
            self.assertEqual(threading.get_ident(), self.owner)
            return original_render()
        self.app.render = main_thread_render

    def tearDown(self):
        if not hasattr(self, "app"):
            return
        self.release.set()
        try:
            if not self.app.closed:
                self.pump(lambda: self.app.controller.active is None)
                self.app.destroy()
            self.assertEqual(self.callback_errors, [])
        finally:
            self.bound.__exit__(None, None, None)
            self.workspace.__exit__()

    def pump(self, predicate=None, timeout=6):
        predicate = predicate or (lambda: self.app.controller.active is None and self.app._preview_after_id is None)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self.app.closed:
                self.root.update()
            if predicate():
                self.assertEqual(self.callback_errors, [])
                return
            time.sleep(0.005)
        self.fail("Timed out waiting for the fictional desktop operation.")

    def enabled(self, widget):
        return str(widget.cget("state")) != "disabled"

    def configure(self):
        with patch("lumen_organizer.ui.filedialog.askdirectory", return_value=str(self.w.vault)):
            self.app.vault_button.invoke()
        self.pump()
        self.assertEqual(self.app.controller.state.vault, self.w.vault)

    def select(self):
        with patch("lumen_organizer.ui.filedialog.askopenfilename", return_value=str(self.w.source)):
            self.app.file_button.invoke()

    def validate(self):
        self.configure()
        self.select()
        self.app.validate_button.invoke()
        self.pump()

    def category(self, category):
        self.app.category_box.set(CATEGORY_LABELS[category])
        self.app.category_box.event_generate("<<ComboboxSelected>>")
        self.root.update()

    def prepare(self):
        self.validate()
        self.category("aws-cloud")
        self.app.prepare_button.invoke()
        self.pump()
        self.assertIsNotNone(self.app.controller.state.plan)

    def approve(self):
        self.app.import_button.invoke()
        self.assertIsInstance(self.app.dialog, ConfirmationDialog)
        self.app.dialog.confirm_button.invoke()
        self.pump()

    def test_initial_states_and_picker_cancellation_do_not_import(self):
        self.assertEqual(self.app.category_var.get(), "")
        self.assertFalse(self.enabled(self.app.file_button))
        self.assertFalse(self.enabled(self.app.import_button))
        with patch("lumen_organizer.ui.filedialog.askdirectory", return_value=""):
            self.app.vault_button.invoke()
        self.assertFalse(self.w.state.exists())
        self.configure()
        before = self.app.controller.store.path.read_bytes()
        with patch("lumen_organizer.ui.filedialog.askdirectory", return_value=""):
            self.app.vault_button.invoke()
        self.assertEqual(self.app.controller.store.path.read_bytes(), before)
        self.select()
        self.assertEqual(self.app.source_var.get(), str(self.w.source))
        self.assertIsNone(self.app.controller.state.validation)
        with patch("lumen_organizer.ui.filedialog.askopenfilename", return_value=""):
            self.app.file_button.invoke()
        self.assertEqual(self.app.controller.state.source, self.w.source)
        self.assertEqual(self.app.controller.organizer.history.operations(), ())
        self.assertEqual(list(self.w.vault.rglob("*.md")), [])

    def test_errors_warnings_metadata_and_inert_readonly_preview(self):
        original = self.w.source.read_bytes()
        self.w.source.write_bytes(original.replace(b"status: inbox", b"status: reviewed"))
        self.validate()
        self.assertIn("status", self.app.errors.get("1.0", "end"))
        self.assertFalse(self.enabled(self.app.prepare_button))
        self.assertFalse(self.enabled(self.app.category_box))
        inert = '\n<script>throw Error("fictional")</script>\n```python\nraise Exception("fictional")\n```\n[link](https://example.invalid)\n![[fictional-embed]]\n'
        self.w.source.write_bytes(original.replace(b"# Fictional queue study", b"# Fictional different title") + inert.encode())
        self.app.validate_button.invoke()
        self.pump()
        self.assertIn("title", self.app.warnings.get("1.0", "end"))
        self.assertIn("Nenhum erro", self.app.errors.get("1.0", "end"))
        self.assertIn(inert, self.app.preview.get("1.0", "end"))
        before = self.app.preview.get("1.0", "end")
        self.app.preview.insert("1.0", "ATTEMPTED EDIT")
        self.assertEqual(self.app.preview.get("1.0", "end"), before)
        self.assertEqual(str(self.app.preview.cget("state")), "disabled")
        metadata = dict(self.app.metadata.item(item, "values") for item in self.app.metadata.get_children())
        self.assertEqual(metadata["status"], "inbox")
        self.assertEqual(metadata["lumen_export"], "false")
        self.assertEqual(self.app.category_var.get(), "")
        self.assertFalse(self.enabled(self.app.prepare_button))
        self.category("aws-cloud")
        self.app.prepare_button.invoke()
        self.pump()
        self.app.import_button.invoke()
        self.assertIn("title", self.app.dialog.warnings.get("1.0", "end"))
        self.app.dialog.cancel_button.invoke()
        self.assertFalse(self.enabled(self.app.import_button))
        self.assertEqual(list(self.w.vault.rglob("*.md")), [])
        self.assertIn("status: inbox", LIFECYCLE)
        self.assertIn("lumen_export: false", LIFECYCLE)

    def test_confirmation_cancel_then_full_import_and_duplicate(self):
        self.prepare()
        plan = self.app.controller.state.plan
        self.assertIn(str(plan.destination), self.app.destination_var.get())
        self.app.import_button.invoke()
        self.assertIn(str(plan.destination), self.app.dialog.details.get("1.0", "end"))
        self.assertFalse(plan.destination.exists())
        self.app.dialog.cancel_button.invoke()
        self.assertEqual(self.app.controller.state.result.outcome, "cancelled")
        self.assertFalse(plan.destination.exists())
        self.app.prepare_button.invoke()
        self.pump()
        self.approve()
        self.assertEqual(self.app.controller.state.result.outcome, "imported")
        self.assertEqual(self.app.result_title_var.get(), "Importação concluída")
        self.assertEqual(plan.destination.read_bytes(), self.w.source.read_bytes())
        self.assertIn(b"status: inbox", plan.destination.read_bytes())
        self.assertIn(b"lumen_export: false", plan.destination.read_bytes())
        self.app.prepare_button.invoke()
        self.pump()
        self.assertEqual(self.app.controller.state.result.outcome, "duplicate")
        self.assertEqual(self.app.result_title_var.get(), "Duplicata identificada")
        self.assertFalse(self.enabled(self.app.import_button))
        self.assertEqual(len(list(self.w.vault.rglob("*.md"))), 1)

    def test_collision_suffix_is_presented_and_late_collision_is_preserved(self):
        occupied = self.w.vault / "01 - Conhecimento/AWS e Cloud" / self.w.source.name
        occupied.write_bytes(b"Fictional old note")
        self.prepare()
        plan = self.app.controller.state.plan
        self.assertNotEqual(plan.filename, self.w.source.name)
        self.app.import_button.invoke()
        self.assertIn(plan.filename, self.app.dialog.details.get("1.0", "end"))
        plan.destination.write_bytes(b"Fictional competing note")
        self.app.dialog.confirm_button.invoke()
        self.pump()
        self.assertEqual(self.app.controller.state.result.code, "destination_collision")
        self.assertEqual(occupied.read_bytes(), b"Fictional old note")
        self.assertEqual(plan.destination.read_bytes(), b"Fictional competing note")
        self.assertFalse(self.enabled(self.app.import_button))
        self.app.prepare_button.invoke()
        self.pump()
        self.assertNotEqual(self.app.controller.state.plan.filename, plan.filename)
        self.approve()
        self.assertEqual(self.app.controller.state.result.outcome, "imported")

    def test_folder_navigation_and_cancellation_require_explicit_child(self):
        self.validate()
        self.category("faculdade")
        self.assertFalse(self.enabled(self.app.prepare_button))
        self.app.folder_button.invoke()
        self.assertIsInstance(self.app.dialog, FolderDialog)
        self.pump()
        dialog = self.app.dialog
        dialog.select_button.invoke()  # Nothing selected, root cannot be used.
        self.assertIsNone(self.app.controller.state.subfolder)
        dialog.items.selection_set(0)
        dialog.enter_button.invoke()
        self.pump()
        self.assertEqual(dialog.parent, "Fictional Term")
        dialog.back_button.invoke()
        self.pump()
        self.assertIsNone(dialog.parent)
        dialog.cancel_button.invoke()
        self.assertIsNone(self.app.controller.state.subfolder)
        self.assertFalse(self.enabled(self.app.prepare_button))
        self.app.folder_button.invoke()
        self.pump()
        dialog = self.app.dialog
        dialog.items.selection_set(0)
        dialog.enter_button.invoke()
        self.pump()
        dialog.items.selection_set(0)
        dialog.select_button.invoke()
        self.pump()
        self.assertIsNone(self.app.dialog)
        self.assertEqual(self.app.controller.state.subfolder, "Fictional Term/Fictional Subject")
        self.assertTrue(self.enabled(self.app.prepare_button))

    def test_changes_to_filename_category_and_selection_expire_plan(self):
        self.prepare()
        self.app.filename_var.set("different-fictional.md")
        self.assertIsNone(self.app.controller.state.plan)
        self.assertFalse(self.enabled(self.app.import_button))
        self.app.prepare_button.invoke()
        self.pump()
        self.assertEqual(self.app.controller.state.plan.filename, "different-fictional.md")
        self.category("ia")
        self.assertIsNone(self.app.controller.state.plan)
        self.app.prepare_button.invoke()
        self.pump()
        self.app.clear_button.invoke()
        self.assertIsNone(self.app.controller.state.source)
        self.assertIsNone(self.app.controller.state.plan)
        self.assertEqual(self.app.category_var.get(), "")
        self.assertFalse(self.enabled(self.app.import_button))
        self.assertEqual(list(self.w.vault.rglob("*.md")), [])

    def test_external_source_change_before_preparation_and_after_confirmation(self):
        self.validate()
        self.category("aws-cloud")
        original = self.w.source.read_bytes()
        self.w.source.write_bytes(original + b"\nFictional new paragraph.\n")
        self.app.prepare_button.invoke()
        self.pump()
        self.assertEqual(self.app.controller.state.error_code, "source_changed")
        self.assertFalse(self.enabled(self.app.import_button))
        self.app.validate_button.invoke()
        self.pump()
        self.app.prepare_button.invoke()
        self.pump()
        target = self.app.controller.state.plan.destination
        self.app.import_button.invoke()
        self.w.source.write_bytes(original)
        self.app.dialog.confirm_button.invoke()
        self.pump()
        self.assertEqual(self.app.controller.state.result.code, "source_changed")
        self.assertFalse(target.exists())
        self.assertIsNone(self.app.controller.state.validation)

    def test_saved_history_incomplete_disables_retry_then_reconciles(self):
        self.prepare()
        target = self.app.controller.state.plan.destination
        with patch.object(self.app.controller.organizer.history, "complete", side_effect=LumenError("history_unavailable")):
            self.approve()
        self.assertEqual(target.read_bytes(), self.w.source.read_bytes())
        self.assertEqual(self.app.result_title_var.get(), "Arquivo salvo; histórico incompleto")
        self.assertIn("Não repita", self.app.result_detail.get("1.0", "end"))
        self.assertFalse(self.enabled(self.app.prepare_button))
        self.assertFalse(self.enabled(self.app.import_button))
        self.assertTrue(self.enabled(self.app.reconcile_button))
        self.assertIn("Não repita", self.app.status_var.get())
        self.assertEqual(self.app.status_label.cget("style"), "warning.Status.TLabel")
        self.assertEqual(self.app.reconcile_button.cget("style"), "Primary.TButton")
        self.assertIn(str(target), self.app.destination_text.get("1.0", "end"))
        self.root.deiconify()
        minimum = self.root.minsize()
        self.root.geometry(f"{minimum[0]}x{minimum[1]}"); self.root.update()
        self.visible_inside(self.app.reconcile_button, self.root)
        self.visible_inside(self.app.import_button, self.root)
        before = target.read_bytes()
        self.app.reconcile_button.invoke()
        self.pump()
        self.assertEqual(self.app.controller.state.result.outcome, "reconciled_import")
        self.assertEqual(target.read_bytes(), before)
        self.assertFalse(self.app.controller.state.requires_reconciliation)

    def test_worker_keeps_event_loop_responsive_and_cancel_discards_result(self):
        self.configure()
        self.select()
        from lumen_organizer.validation import validate_file
        workers = []
        def slow_validate(path):
            workers.append(threading.get_ident())
            self.release.wait(4)
            return validate_file(path)
        with patch("lumen_organizer.controller.validate_file", side_effect=slow_validate):
            self.app.validate_button.invoke()
            ticks = []
            self.root.after(5, lambda: ticks.append("main loop tick"))
            self.pump(lambda: bool(ticks))
            self.assertFalse(self.enabled(self.app.file_button))
            self.assertTrue(self.enabled(self.app.cancel_button))
            self.app.cancel_button.invoke()
            self.release.set()
            self.pump()
        self.assertTrue(workers)
        self.assertNotEqual(workers[0], self.owner)
        self.assertIsNone(self.app.controller.state.validation)
        self.assertEqual(self.app.controller.state.result.outcome, "cancelled")
        self.assertEqual(list(self.w.vault.rglob("*.md")), [])

    def test_cancel_preparation_and_folder_listing_ignores_late_results(self):
        self.validate()
        self.category("aws-cloud")
        original_prepare = self.app.controller.organizer.prepare
        def delayed_prepare(*args, **kwargs):
            self.release.wait(4)
            return original_prepare(*args, **kwargs)
        with patch.object(self.app.controller.organizer, "prepare", side_effect=delayed_prepare):
            self.app.prepare_button.invoke()
            self.app.cancel_button.invoke()
            self.release.set()
            self.pump()
        self.assertIsNone(self.app.controller.state.plan)
        self.assertFalse(self.enabled(self.app.import_button))
        self.category("projetos")
        self.app.folder_button.invoke()
        self.app.dialog.cancel_button.invoke()
        self.pump()
        self.assertIsNone(self.app.dialog)
        self.assertIsNone(self.app.controller.state.subfolder)
        self.assertEqual(list(self.w.vault.rglob("*.md")), [])

    def test_startup_exposes_pending_history_without_replaying_import(self):
        self.prepare()
        target = self.app.controller.state.plan.destination
        with patch.object(self.app.controller.organizer.history, "complete", side_effect=LumenError("history_unavailable")):
            self.approve()
        self.app.dispatch(self.app.controller.start_load_settings())
        self.pump()
        self.assertTrue(self.app.controller.state.requires_reconciliation)
        self.assertIn("Conferir histórico", self.app.status_var.get())
        self.assertTrue(self.enabled(self.app.reconcile_button))
        self.assertEqual(len(list(self.w.vault.rglob("*.md"))), 1)
        self.app.reconcile_button.invoke()
        self.pump()
        self.assertEqual(self.app.controller.state.result.outcome, "reconciled_import")
        self.assertEqual(target.read_bytes(), self.w.source.read_bytes())

    def test_unexpected_worker_failure_is_sanitized_and_halts_retries(self):
        self.prepare()
        with patch.object(self.app.controller.organizer, "commit", side_effect=RuntimeError("FICTITIOUS PRIVATE MARKER")):
            self.approve()
        self.assertEqual(self.app.result_title_var.get(), "Resultado da gravação incerto")
        self.assertIn("Não repita", self.app.result_detail.get("1.0", "end"))
        self.assertNotIn("PRIVATE MARKER", self.app.result_detail.get("1.0", "end"))
        self.assertFalse(self.enabled(self.app.prepare_button))
        self.assertTrue(self.enabled(self.app.reconcile_button))

    def test_window_close_waits_for_confirmed_write(self):
        self.prepare()
        original_commit = self.app.controller.organizer.commit
        target = self.app.controller.state.plan.destination
        def delayed_commit(*args, **kwargs):
            self.release.wait(4)
            return original_commit(*args, **kwargs)
        with patch.object(self.app.controller.organizer, "commit", side_effect=delayed_commit):
            self.app.import_button.invoke()
            self.app.dialog.confirm_button.invoke()
            self.app.close_requested()
            self.assertTrue(self.app.closing)
            self.assertFalse(self.app.closed)
            self.assertFalse(self.enabled(self.app.cancel_button))
            self.release.set()
            self.pump(lambda: self.app.closed)
        self.assertEqual(target.read_bytes(), self.w.source.read_bytes())
        self.assertEqual(self.app.controller.state.result.outcome, "imported")

    def test_large_preview_is_chunked_and_window_is_resizable(self):
        self.w.source.write_bytes(self.w.source.read_bytes() + b"\n" + b"Fictional plain text.\n" * 30000)
        self.validate()
        self.assertEqual(self.app.preview.get("1.0", "end-1c"), self.w.source.read_text(encoding="utf-8"))
        self.assertEqual(self.root.resizable(), (1, 1))
        self.assertEqual(str(self.app.preview.cget("takefocus")), "1")
        self.assertTrue(self.app.preview.bind("<Tab>"))
        self.assertTrue(self.app.preview.bind("<Shift-Tab>"))

    def visible_inside(self, widget, window):
        self.assertTrue(widget.winfo_ismapped())
        x = widget.winfo_rootx() - window.winfo_rootx()
        y = widget.winfo_rooty() - window.winfo_rooty()
        self.assertGreaterEqual(x, 0)
        self.assertGreaterEqual(y, 0)
        self.assertLessEqual(x + widget.winfo_width(), window.winfo_width())
        self.assertLessEqual(y + widget.winfo_height(), window.winfo_height())

    def test_primary_action_and_explicit_validation_states(self):
        self.assertIn("Nenhum vault", self.app.status_var.get())
        self.assertEqual(self.app.vault_button.cget("style"), "Primary.TButton")
        self.configure()
        self.assertIn("Nenhuma nota", self.app.status_var.get())
        self.assertEqual(self.app.file_button.cget("style"), "Primary.TButton")
        self.select()
        self.assertEqual(self.app.validate_button.cget("style"), "Primary.TButton")
        original = self.w.source.read_bytes()
        self.w.source.write_bytes(original.replace(b"status: inbox", b"status: reviewed"))
        self.app.validate_button.invoke(); self.pump()
        self.assertIn("Nota inválida", self.app.status_var.get())
        self.assertEqual(self.app.status_label.cget("style"), "error.Status.TLabel")
        self.w.source.write_bytes(original.replace(b"# Fictional queue study", b"# Fictional other title"))
        self.app.validate_button.invoke(); self.pump()
        self.assertIn("Nota válida com avisos", self.app.status_var.get())
        self.assertEqual(self.app.status_label.cget("style"), "warning.Status.TLabel")
        self.assertEqual(self.app.prepare_button.cget("style"), "Primary.TButton")
        self.category("aws-cloud")
        self.app.prepare_button.invoke(); self.pump()
        self.assertEqual(self.app.import_button.cget("style"), "Primary.TButton")
        self.app.import_button.invoke()
        self.assertEqual(self.app.dialog.confirm_button.cget("style"), "Primary.TButton")
        self.app.dialog.cancel()
        self.assertIn("cancelada", self.app.status_var.get())
        self.assertFalse(self.enabled(self.app.import_button))
        self.assertEqual(list(self.w.vault.rglob("*.md")), [])

    def test_long_paths_preserve_action_geometry_and_complete_bytes(self):
        source = self.w.root / ("fictional-" + "note-" * 26 + ".md")
        data = b"\xef\xbb\xbf" + self.w.source.read_bytes().replace(b"\n", b"\r\n")
        source.write_bytes(data)
        self.w.source = source
        self.root.deiconify()
        self.root.geometry("1120x760"); self.root.update()
        self.prepare()
        plan = self.app.controller.state.plan
        self.assertGreater(len(str(plan.destination)), 260)
        self.assertEqual(self.app.source_var.get(), str(source))
        self.assertIn(str(plan.destination), self.app.destination_text.get("1.0", "end"))
        self.visible_inside(self.app.import_button, self.root)
        self.visible_inside(self.app.cancel_button, self.root)
        geometry = (self.root.winfo_width(), self.root.winfo_height(), self.app.import_button.winfo_width())
        self.app.import_button.invoke(); self.root.update()
        dialog = self.app.dialog
        self.assertIn(str(source), dialog.details.get("1.0", "end"))
        self.assertIn(str(plan.destination), dialog.details.get("1.0", "end"))
        self.visible_inside(dialog.confirm_button, dialog.window)
        self.visible_inside(dialog.cancel_button, dialog.window)
        dialog.confirm_button.invoke(); self.pump()
        self.assertEqual(plan.destination.read_bytes(), data)
        self.assertEqual(source.read_bytes(), data)
        self.assertEqual(self.app.result_title_var.get(), "Importação concluída")
        self.assertEqual(geometry, (self.root.winfo_width(), self.root.winfo_height(), self.app.import_button.winfo_width()))

    def test_readonly_full_yaml_copy_and_keyboard_focus(self):
        self.prepare()
        self.root.deiconify(); self.root.focus_force(); self.root.update()
        self.app.preview.focus_set(); self.root.update()
        self.assertIs(self.root.focus_get(), self.app.preview)
        before = self.app.preview.get("1.0", "end-1c")
        self.app.preview.event_generate("<Control-a>"); self.root.update()
        self.assertEqual(self.app.preview.get("sel.first", "sel.last"), before)
        with patch.object(self.app.preview, "clipboard_clear") as clear, patch.object(self.app.preview, "clipboard_append") as copy:
            self.app.preview.event_generate("<Control-c>"); self.root.update()
            clear.assert_called_once()
            copy.assert_called_once_with(before)
        # No real system clipboard is read or replaced by this test.
        self.assertTrue(before.startswith("---\n"))
        self.assertIn("atlas_goal_id", before)
        following = self.app.preview.tk_focusNext()
        self.app.preview.event_generate("<Tab>"); self.root.update()
        self.assertIs(self.root.focus_get(), following)
        following.event_generate("<Shift-Tab>"); self.root.update()
        self.assertIs(self.root.focus_get(), self.app.preview)
        self.app.preview.event_generate("<KeyPress>", keysym="x"); self.root.update()
        self.assertEqual(self.app.preview.get("1.0", "end-1c"), before)
        self.app.destination_text.focus_set(); self.root.update()
        self.app.destination_text.event_generate("<Control-a>"); self.root.update()
        full = self.app.destination_var.get()
        with patch.object(self.app.destination_text, "clipboard_clear"), patch.object(self.app.destination_text, "clipboard_append") as copy:
            self.app.destination_text.event_generate("<Control-c>"); self.root.update()
            copy.assert_called_once_with(full)
        self.assertEqual(self.app.theme.ttk.lookup("TEntry", "bordercolor", ("focus",)), COLORS["accent"])
        self.assertEqual(self.app.preview.cget("highlightcolor"), COLORS["accent"])

    def test_scaled_layout_resize_focus_and_dialog_actions(self):
        # Actual Tk font/spacing scaling, not Windows OS DPI or physical monitors.
        for scale in (1.0, 1.25, 1.5, 2.0):
            with self.subTest(tk_scale=scale):
                self.app.destroy()
                self.root = tk.Tk(); self.root.withdraw()
                self.root.tk.call("tk", "scaling", scale * 96 / 72)
                self.app = App(self.root, self.w.state, load_settings=False)
                self.root.report_callback_exception = lambda *args: self.callback_errors.append(args)
                self.validate(); self.category("faculdade")
                self.root.deiconify(); self.root.focus_force(); self.root.update()
                minimum = self.root.minsize()
                self.root.geometry(f"{minimum[0]}x{minimum[1]}"); self.root.update()
                for widget in (self.app.vault_button, self.app.file_button, self.app.validate_button,
                               self.app.prepare_button, self.app.import_button, self.app.cancel_button,
                               self.app.reconcile_button, self.app.destination_text, self.app.tabs):
                    self.visible_inside(widget, self.root)
                self.assertGreater(self.app.preview.winfo_height(), 50)
                self.visible_inside(self.app.folder_button, self.root)
                for widget in (self.app.category_box, self.app.filename_entry):
                    widget.focus_set(); self.root.update()
                    self.assertIs(self.root.focus_get(), widget)
                    self.visible_inside(widget, self.app.destination_form.canvas)
                self.app.folder_button.invoke(); self.pump(); self.root.update()
                dialog = self.app.dialog
                for widget in (dialog.back_button, dialog.enter_button, dialog.select_button, dialog.cancel_button):
                    self.visible_inside(widget, dialog.window)
                self.assertEqual(dialog.path_entry.get(), str(self.w.vault / "02 - Faculdade"))
                dialog.cancel(); self.pump()
                self.category("aws-cloud")
                self.app.prepare_button.invoke(); self.pump()
                self.app.import_button.invoke(); self.root.update()
                dialog = self.app.dialog
                self.visible_inside(dialog.confirm_button, dialog.window)
                self.visible_inside(dialog.cancel_button, dialog.window)
                self.assertIn(str(self.app.controller.state.plan.destination), dialog.details.get("1.0", "end"))
                dialog.cancel()
                self.root.geometry(f"{min(self.root.winfo_screenwidth()-50, minimum[0]+200)}x{min(self.root.winfo_screenheight()-80, minimum[1]+120)}")
                self.root.update()
                self.visible_inside(self.app.import_button, self.root)
                self.assertEqual(list(self.w.vault.rglob("*.md")), [])
                self.assertAlmostEqual(self.app.theme.scale, scale, delta=.01)
                self.assertEqual(self.app.theme.ttk.theme_use(), "clam")
                self.assertEqual(SPACING, (4, 8, 12, 16, 24, 32))

    def test_result_states_have_explicit_text_beyond_color(self):
        cases = {"imported": ("Importação concluída", "success"),
                 "duplicate": ("Duplicata identificada", "accent"),
                 "cancelled": ("Operação cancelada", "muted"),
                 "failed": ("Operação não concluída", "error"),
                 "saved_history_incomplete": ("Arquivo salvo; histórico incompleto", "warning")}
        for outcome, (expected, tone) in cases.items():
            state = SimpleNamespace(busy=None, saved_uncertain=False,
                                    result=ImportResult(outcome, "write_failed"))
            text, actual = visual_status(state)
            self.assertIn(expected, text)
            self.assertEqual(actual, tone)
        state.result = ImportResult("reconciliation_empty", "")
        state.saved_uncertain = True
        self.assertIn("Não repita", visual_status(state)[0])
        state.busy = "validation"
        self.assertIn("Validando nota", visual_status(state)[0])
        state.busy = "import"
        self.assertIn("Importando nota", visual_status(state)[0])

