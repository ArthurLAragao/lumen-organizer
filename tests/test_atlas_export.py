from dataclasses import replace
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

from lumen_organizer.atlas_export import AtlasExporter, validate_export_file
from lumen_organizer.atlas_transfer import decode_package
from lumen_organizer.destinations import DestinationPolicy
from lumen_organizer.export_registry import ExportRegistry
from lumen_organizer.filesystem import publish_no_replace
from lumen_organizer.importer import Organizer
from lumen_organizer.models import LumenError
from .support import FictionalWorkspace, bounded_writes, changed_note
from .test_atlas_transfer import FIXTURE


class SimulatedInterruption(BaseException):
    pass


@unittest.skipUnless(os.name == "nt", "Safe publication uses Windows no-replace and directory guards")
class ExportTests(unittest.TestCase):
    def setUp(self):
        self.workspace = FictionalWorkspace()
        self.w = self.workspace.__enter__()
        self.bound = bounded_writes(self.w.root)
        self.bound.__enter__()
        self.policy = DestinationPolicy(self.w.vault)
        self.source = self.policy.folder("ia") / "fictional-reviewed.md"
        self.source.write_bytes(FIXTURE.read_bytes())
        self.w.state.mkdir()
        self.registry = ExportRegistry.create(self.w.state / "atlas-export", self.w.vault)
        self.exporter = AtlasExporter(self.policy, self.registry)
        self.identity = self.exporter.register(self.source, "ia", confirmed=True)

    def tearDown(self):
        self.bound.__exit__(None, None, None)
        self.workspace.__exit__()

    def prepare(self, **kwargs):
        return self.exporter.prepare(self.source, "ia", **kwargs)

    def commit(self, **kwargs):
        plan = self.prepare(**kwargs)
        result = self.exporter.commit(plan, confirmed=True)
        self.assertEqual(result.outcome, "prepared", result)
        return result

    def test_complete_package_is_outside_vault_and_vault_source_untouched(self):
        before = {p.relative_to(self.w.vault).as_posix(): p.read_bytes() for p in self.w.vault.rglob("*") if p.is_file()}
        result = self.commit()
        packet = decode_package(result.package_path.read_bytes())
        self.assertEqual(packet.source_bytes, self.source.read_bytes())
        self.assertEqual(packet.integration_id, self.identity.integration_id)
        self.assertFalse(result.package_path.is_relative_to(self.w.vault))
        after = {p.relative_to(self.w.vault).as_posix(): p.read_bytes() for p in self.w.vault.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(self.registry.record(result.export_id).delivery, "unknown")

    def test_repeated_exports_keep_identity_and_all_prior_bytes(self):
        first = self.commit()
        saved = first.package_path.read_bytes()
        second = self.commit()
        self.assertNotEqual(first.export_id, second.export_id)
        self.assertEqual(second.package_path.read_bytes(), saved)
        self.assertEqual(first.package_path.read_bytes(), saved)
        self.assertIsNone(decode_package(saved).baseline_sha256)
        reopened = ExportRegistry.open(self.registry.directory, self.w.vault)
        self.assertEqual(reopened.identity_for(self.policy.vault_id, self.source.relative_to(self.w.vault).as_posix()), self.identity)
        self.assertTrue(all(row.delivery == "unknown" for row in reopened.records()))

    def test_changed_note_keeps_identity_without_advancing_baseline(self):
        first = self.commit()
        self.source.write_bytes(self.source.read_bytes() + b"\nNew fictional version.\n")
        second = self.commit()
        a, b = decode_package(first.package_path.read_bytes()), decode_package(second.package_path.read_bytes())
        self.assertEqual(a.integration_id, b.integration_id)
        self.assertNotEqual(a.source_sha256, b.source_sha256)
        self.assertNotEqual(a.comparison_sha256, b.comparison_sha256)
        self.assertIsNone(b.baseline_sha256)
        self.assertTrue(all(row.delivery == "unknown" for row in self.registry.records()))

    def test_previous_package_can_be_explicit_candidate_without_delivery_claim(self):
        first = self.commit()
        self.source.write_bytes(self.source.read_bytes() + b"\nLater fictional version.\n")
        plan = self.prepare(baseline_export_id=first.export_id)
        old = decode_package(first.package_path.read_bytes())
        new = decode_package(plan.package_bytes)
        self.assertEqual(new.baseline_sha256, old.comparison_sha256)
        result = self.exporter.commit(plan, confirmed=True)
        self.assertEqual(result.outcome, "prepared")
        self.assertEqual(self.registry.record(first.export_id).delivery, "unknown")
        self.assertIsNone(decode_package(self.prepare().package_bytes).baseline_sha256)

    def test_cross_identity_or_unprepared_baseline_rejected(self):
        first = self.commit()
        other = self.source.with_name("different.md")
        other.write_bytes(self.source.read_bytes())
        self.exporter.register(other, "ia", confirmed=True)
        with self.assertRaises(LumenError) as error:
            self.exporter.prepare(other, "ia", baseline_export_id=first.export_id)
        self.assertEqual(error.exception.code, "cross_identity_baseline")
        with self.assertRaises(LumenError):
            self.prepare(baseline_export_id="f" * 32)

    def test_literal_confirmation_required_and_cancel_does_not_prepare(self):
        plan = self.prepare()
        for value in (False, None, "yes", 1):
            self.assertEqual(self.exporter.commit(plan, confirmed=value).outcome, "cancelled")
        self.assertEqual(self.registry.records(), ())
        other = self.source.with_name("unregistered.md")
        other.write_bytes(self.source.read_bytes())
        for value in (False, "yes", 1):
            with self.assertRaises(LumenError):
                self.exporter.register(other, "ia", confirmed=value)
        with self.assertRaises(LumenError) as error:
            self.exporter.prepare(other, "ia")
        self.assertEqual(error.exception.code, "identity_registration_required")

    def test_changed_source_after_preparation_is_blocked(self):
        plan = self.prepare()
        self.source.write_bytes(self.source.read_bytes() + b"\nCHANGED-FICTIONAL\n")
        result = self.exporter.commit(plan, confirmed=True)
        self.assertEqual(result.code, "export_source_changed")
        self.assertEqual(self.registry.records(), ())
        self.assertFalse(self.registry.archive_path(plan.export_id).exists())

    def test_revoked_eligibility_after_preparation_blocks_package(self):
        plan = self.prepare()
        self.source.write_bytes(changed_note(self.source.read_bytes(), "lumen_export", "false"))
        self.assertEqual(self.exporter.commit(plan, confirmed=True).code, "export_validation_failed")
        self.assertEqual(self.registry.records(), ())

    def test_tampered_plan_bytes_and_identity_rejected(self):
        plan = self.prepare()
        for modified in (replace(plan, package_bytes=plan.package_bytes + b" "),
                         replace(plan, integration_id="lumen_" + "b" * 32),
                         replace(plan, relative_source="../../escape.md")):
            self.assertEqual(self.exporter.commit(modified, confirmed=True).outcome, "blocked")
        self.assertEqual(self.registry.records(), ())

    def test_outside_and_private_areas_are_rejected_before_reading(self):
        forbidden = self.w.vault / "Pessoal" / "private.md"
        forbidden.parent.mkdir()
        forbidden.write_bytes(b"FICTIONAL-PRIVATE-MARKER")
        for path, category in ((forbidden, "ia"), (self.w.source, "ia"), (self.source, "indefinido"),
                               (self.w.vault / "01 - Conhecimento" / "Inteligência Artificial" / ".." / "escape.md", "ia")):
            with patch("pathlib.Path.open", side_effect=AssertionError("Unauthorized content was read")):
                result = validate_export_file(path, self.policy, category)
            self.assertFalse(result.valid)
        self.assertTrue(validate_export_file(self.source, self.policy, "ia").valid)

    def test_faculdade_and_projetos_require_explicit_existing_subfolder(self):
        for category, subfolder in (("faculdade", "Fictional Term/Fictional Subject"), ("projetos", "Fictional Project")):
            source = self.policy.folder(category, subfolder) / "reviewed.md"
            source.write_bytes(FIXTURE.read_bytes())
            self.assertFalse(validate_export_file(source, self.policy, category).valid)
            self.assertTrue(validate_export_file(source, self.policy, category, subfolder).valid)

    def test_publication_collision_never_overwrites(self):
        plan = self.prepare()
        target = self.registry.archive_path(plan.export_id)
        target.write_bytes(b"FICTIONAL-OCCUPANT")
        self.assertEqual(self.exporter.commit(plan, confirmed=True).code, "export_package_collision")
        self.assertEqual(target.read_bytes(), b"FICTIONAL-OCCUPANT")
        self.assertEqual(self.registry.records(), ())

    def test_late_collision_keeps_pending_and_conflicting_file(self):
        plan = self.prepare()
        def collide(staged, target):
            target.write_bytes(b"FICTIONAL-CONCURRENT")
            publish_no_replace(staged, target)
        with patch("lumen_organizer.atlas_export.publish_no_replace", side_effect=collide):
            self.assertEqual(self.exporter.commit(plan, confirmed=True).outcome, "recovery_required")
        self.assertEqual(self.registry.record(plan.export_id).state, "pending")
        result = self.exporter.reconcile()[0]
        self.assertEqual(result.code, "export_package_conflict")
        self.assertEqual(self.registry.archive_path(plan.export_id).read_bytes(), b"FICTIONAL-CONCURRENT")
        self.assertTrue(self.registry.stage_path(plan.export_id).exists())

    def test_registry_failure_after_publication_is_reconciled_without_rewrite(self):
        plan = self.prepare()
        with patch.object(self.registry, "_complete", side_effect=LumenError("export_registry_unavailable")):
            result = self.exporter.commit(plan, confirmed=True)
        self.assertEqual(result.outcome, "prepared_registry_incomplete")
        saved = result.package_path.read_bytes()
        with self.assertRaises(LumenError):
            self.prepare()
        with patch("lumen_organizer.atlas_export.publish_no_replace", side_effect=AssertionError("No publication allowed")):
            reconciled = self.exporter.reconcile()[0]
        self.assertEqual(reconciled.outcome, "prepared")
        self.assertEqual(result.package_path.read_bytes(), saved)
        self.assertEqual(self.registry.record(plan.export_id).delivery, "unknown")

    def test_unexpected_exception_text_is_not_exposed(self):
        plan = self.prepare()
        with patch.object(self.registry, "_complete", side_effect=RuntimeError("FICTIONAL-SENSITIVE-EXCEPTION")):
            result = self.exporter.commit(plan, confirmed=True)
        self.assertEqual(result.code, "export_unexpected_error")
        self.assertNotIn("FICTIONAL-SENSITIVE-EXCEPTION", repr(result))
        self.assertEqual(self.registry.record(plan.export_id).state, "pending")
        self.assertEqual(self.exporter.reconcile()[0].outcome, "prepared")

    def test_registry_process_lock_blocks_second_session(self):
        from lumen_organizer.filesystem import session_lock
        plan = self.prepare()
        with session_lock(self.registry.directory):
            result = self.exporter.commit(plan, confirmed=True)
        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(result.code, "state_busy")
        self.assertEqual(self.registry.records(), ())

    def test_junction_source_ancestor_is_rejected_without_reading(self):
        import subprocess
        # Replace an EMPTY fictional approved folder, so rejection exercises
        # the reparse guard rather than merely the category allowlist.
        junction = self.policy.folder("aws-cloud")
        junction.rmdir()
        subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(self.source.parent)],
                       check=True, capture_output=True)
        try:
            with patch("pathlib.Path.open", side_effect=AssertionError("Do not read through a junction")):
                result = validate_export_file(junction / self.source.name, self.policy, "aws-cloud")
            self.assertFalse(result.valid)
            self.assertIn("linked_directory_forbidden", [issue.code for issue in result.issues])
        finally:
            # Remove only the exact test-owned junction, never its target tree.
            junction.rmdir()
            junction.mkdir()

    def test_interruption_before_publication_retains_stage_and_requires_recovery(self):
        plan = self.prepare()
        with patch("lumen_organizer.atlas_export.publish_no_replace", side_effect=SimulatedInterruption()):
            with self.assertRaises(SimulatedInterruption):
                self.exporter.commit(plan, confirmed=True)
        self.source.write_bytes(b"changed after interruption; do not reconstruct")
        self.assertEqual(self.exporter.reconcile()[0].code, "export_staging_retained")
        self.assertFalse(self.registry.archive_path(plan.export_id).exists())
        self.assertEqual(self.exporter.recover(plan.export_id, confirmed="yes").outcome, "cancelled")
        with patch("lumen_organizer.atlas_export.validate_export_file", side_effect=AssertionError("Recovery must not read source")):
            recovered = self.exporter.recover(plan.export_id, confirmed=True)
        self.assertEqual(recovered.outcome, "prepared")
        self.assertEqual(recovered.package_path.read_bytes(), plan.package_bytes)
        self.assertEqual(self.registry.record(plan.export_id).delivery, "unknown")

    def test_interruption_after_publication_is_reconciled_on_reopen(self):
        plan = self.prepare()
        with patch.object(self.registry, "_complete", side_effect=SimulatedInterruption()):
            with self.assertRaises(SimulatedInterruption):
                self.exporter.commit(plan, confirmed=True)
        registry = ExportRegistry.open(self.registry.directory, self.w.vault)
        recovered = AtlasExporter(self.policy, registry).reconcile()[0]
        self.assertEqual(recovered.outcome, "prepared")
        self.assertEqual(recovered.package_path.read_bytes(), plan.package_bytes)

    def test_interruption_before_staging_cannot_reconstruct_prior_content(self):
        plan = self.prepare()
        original = self.registry._start
        def interrupt(*args):
            original(*args)
            raise SimulatedInterruption()
        with patch.object(self.registry, "_start", side_effect=interrupt):
            with self.assertRaises(SimulatedInterruption):
                self.exporter.commit(plan, confirmed=True)
        result = self.exporter.reconcile()[0]
        self.assertEqual(result.code, "export_interrupted")
        self.assertEqual(self.registry.record(plan.export_id).state, "failed")
        self.assertFalse(self.registry.archive_path(plan.export_id).exists())
        self.assertEqual(self.exporter.recover(plan.export_id, confirmed=True).code, "export_recovery_not_pending")

    def test_tampered_stage_is_never_replayed(self):
        plan = self.prepare()
        with patch("lumen_organizer.atlas_export.publish_no_replace", side_effect=SimulatedInterruption()):
            with self.assertRaises(SimulatedInterruption):
                self.exporter.commit(plan, confirmed=True)
        staged = self.registry.stage_path(plan.export_id)
        staged.write_bytes(b"FICTIONAL-PARTIAL")
        self.assertEqual(self.exporter.reconcile()[0].code, "export_package_conflict")
        self.assertEqual(self.exporter.recover(plan.export_id, confirmed=True).code, "export_package_conflict")
        self.assertEqual(staged.read_bytes(), b"FICTIONAL-PARTIAL")
        self.assertFalse(self.registry.archive_path(plan.export_id).exists())

    def test_resend_previous_archive_does_not_read_changed_source(self):
        first = self.commit()
        saved = first.package_path.read_bytes()
        self.source.write_bytes(b"later invalid fictional content")
        with patch("lumen_organizer.atlas_export.validate_export_file", side_effect=AssertionError("Do not read source")):
            self.assertEqual(self.exporter.read_prepared(first.export_id), saved)
        first.package_path.write_bytes(b"FICTIONAL-TAMPERING")
        with self.assertRaises(LumenError):
            self.exporter.read_prepared(first.export_id)

    def test_missing_archive_not_regenerated_silently(self):
        first = self.commit()
        first.package_path.unlink()
        with self.assertRaises(LumenError):
            self.exporter.read_prepared(first.export_id)
        self.assertFalse(first.package_path.exists())
        self.assertEqual(self.registry.record(first.export_id).delivery, "unknown")

    def test_moved_source_requires_explicit_same_identity_rebind(self):
        self.commit()
        moved = self.source.with_name("moved.md")
        self.source.rename(moved)
        with self.assertRaises(LumenError) as error:
            self.exporter.prepare(moved, "ia")
        self.assertEqual(error.exception.code, "identity_registration_required")
        with self.assertRaises(LumenError):
            self.exporter.rebind(self.identity.integration_id, moved, "ia", confirmed=False)
        rebound = self.exporter.rebind(self.identity.integration_id, moved, "ia", confirmed=True)
        self.assertEqual(rebound.integration_id, self.identity.integration_id)
        packet = decode_package(self.exporter.prepare(moved, "ia").package_bytes)
        self.assertEqual(packet.integration_id, self.identity.integration_id)

    def test_rebind_does_not_adopt_a_copy_or_an_occupied_binding(self):
        other = self.source.with_name("copy.md")
        other.write_bytes(self.source.read_bytes())
        with self.assertRaises(LumenError) as error:
            self.exporter.rebind(self.identity.integration_id, other, "ia", confirmed=True)
        self.assertEqual(error.exception.code, "old_export_source_still_exists")
        different = self.exporter.register(other, "ia", confirmed=True)
        self.assertNotEqual(different.integration_id, self.identity.integration_id)
        self.source.unlink()
        with self.assertRaises(LumenError) as error:
            self.exporter.rebind(self.identity.integration_id, other, "ia", confirmed=True)
        self.assertEqual(error.exception.code, "export_binding_occupied")

    def test_registry_loss_does_not_initialize_new_identity(self):
        self.commit()
        self.registry.path.unlink()
        with self.assertRaises(LumenError):
            ExportRegistry.open(self.registry.directory, self.w.vault)
        self.assertFalse(self.registry.path.exists())
        self.assertTrue(any(self.registry.archives.iterdir()))

    def test_unexpected_registry_and_state_inside_vault_are_rejected(self):
        bad = self.w.state / "unexpected"
        bad.mkdir()
        path = bad / "export-registry.sqlite3"
        path.write_bytes(b"FICTIONAL-UNEXPECTED")
        with self.assertRaises(LumenError):
            ExportRegistry.create(bad, self.w.vault)
        self.assertEqual(path.read_bytes(), b"FICTIONAL-UNEXPECTED")
        with self.assertRaises(LumenError):
            ExportRegistry.create(self.w.vault / ".local" / "bad", self.w.vault)
        self.assertFalse((self.w.vault / ".local").exists())

    def test_existing_import_history_is_unchanged(self):
        organizer = Organizer(self.policy, self.w.state)
        before = organizer.history.path.read_bytes()
        old_operations = organizer.history.operations()
        self.commit()
        self.assertEqual(organizer.history.path.read_bytes(), before)
        self.assertEqual(organizer.history.operations(), old_operations)

    def test_private_content_not_in_registry_diagnostics_or_repr(self):
        marker = "FICTIONAL-PRIVATE-CONTENT-NOT-A-LOG"
        self.source.write_bytes(self.source.read_bytes() + marker.encode())
        plan = self.prepare()
        result = self.exporter.commit(plan, confirmed=True)
        self.assertEqual(result.outcome, "prepared")
        with closing(sqlite3.connect(self.registry.path)) as connection:
            dump = "\n".join(connection.iterdump())
        self.assertNotIn(marker, dump)
        self.assertNotIn("Fictional Atlas transfer", dump)
        self.assertNotIn(marker, repr(plan))
        self.assertNotIn(marker, repr(result))
        self.assertNotIn(str(self.w.vault), result.package_path.read_text(encoding="utf-8"))
        # Private approved artifacts contain content intentionally, outside diagnostic logs.
        self.assertIn(marker, self.exporter.read_prepared(result.export_id).decode())

    def test_no_commands_or_external_resources_are_executed(self):
        self.source.write_bytes(self.source.read_bytes() + b'\n<script>fictional()</script>\n![](https://example.invalid/image.png)\n')
        with patch("subprocess.run", side_effect=AssertionError("Execution forbidden")), \
             patch("urllib.request.urlopen", side_effect=AssertionError("Network forbidden")):
            result = self.commit()
        self.assertIn(b"<script>", decode_package(result.package_path.read_bytes()).source_bytes)
