import json
import threading
import unittest
from unittest.mock import patch

from lumen_organizer.controller import Controller
from lumen_organizer.models import LumenError
from lumen_organizer.presentation import result_text
from .support import FictionalWorkspace, bounded_writes


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.workspace = FictionalWorkspace()
        self.w = self.workspace.__enter__()
        self.bound = bounded_writes(self.w.root)
        self.bound.__enter__()
        self.c = Controller(self.w.state)

    def tearDown(self):
        self.bound.__exit__(None, None, None)
        self.workspace.__exit__()

    def run_job(self, job):
        try:
            value = job.work()
        except LumenError as exc:
            return self.c.complete(job, error_code=exc.code)
        return self.c.complete(job, value)

    def configure(self):
        self.run_job(self.c.start_configure(self.w.vault))

    def validate(self):
        self.configure()
        self.c.select_file(self.w.source)
        self.run_job(self.c.start_validate())

    def prepare(self):
        self.validate()
        self.c.set_destination(category="aws-cloud")
        self.run_job(self.c.start_prepare())

    def import_prepared(self):
        token = self.c.request_confirmation()
        self.run_job(self.c.start_import(token, True))

    def test_initial_configuration_is_empty_and_loading_does_not_write(self):
        self.run_job(self.c.start_load_settings())
        self.assertIsNone(self.c.state.vault)
        self.assertIsNone(self.c.state.category)
        self.assertFalse(self.w.state.exists())

    def test_local_configuration_saved_and_reloaded_without_note_content(self):
        self.configure()
        self.assertEqual(json.loads(self.c.store.path.read_text())["vault_root"], str(self.w.vault))
        other = Controller(self.w.state)
        job = other.start_load_settings()
        other.complete(job, job.work())
        self.assertEqual(other.state.vault, self.w.vault)
        self.assertIsNone(other.state.source)
        self.assertIsNone(other.state.category)

    def test_configuration_and_file_selection_cancellation(self):
        self.c.cancel_configuration()
        self.assertFalse(self.w.state.exists())
        self.validate()
        before = self.c.store.path.read_bytes()
        source = self.c.state.source
        self.c.cancel_configuration()
        self.c.select_file(None)
        self.assertEqual(self.c.state.source, source)
        self.assertEqual(self.c.store.path.read_bytes(), before)
        self.assertEqual(self.c.organizer.history.operations(), ())

    def test_category_is_not_selected_by_validation(self):
        self.validate()
        self.assertTrue(self.c.state.validation.valid)
        self.assertIsNone(self.c.state.category)
        self.assertFalse(self.c.can_prepare)
        self.c.set_destination(category="faculdade")
        self.assertFalse(self.c.can_prepare)
        self.run_job(self.c.start_choose_folder("Fictional Term/Fictional Subject"))
        self.assertTrue(self.c.can_prepare)

    def test_invalid_notes_and_editorial_warnings(self):
        self.configure()
        original = self.w.source.read_bytes()
        self.w.source.write_bytes(original.replace(b"status: inbox", b"status: reviewed"))
        self.c.select_file(self.w.source)
        self.run_job(self.c.start_validate())
        self.assertFalse(self.c.state.validation.valid)
        self.assertFalse(self.c.can_prepare)
        self.w.source.write_bytes(original.replace(b"# Fictional queue study", b"# Another fictional title"))
        self.run_job(self.c.start_validate())
        self.assertTrue(self.c.state.validation.valid)
        self.assertTrue(self.c.state.validation.note.warnings)
        self.c.set_destination(category="ia")
        self.assertTrue(self.c.can_prepare)

    def test_cancelled_validation_discards_late_completion(self):
        self.configure()
        self.c.select_file(self.w.source)
        job = self.c.start_validate()
        self.c.cancel_step()
        self.assertFalse(self.c.complete(job, job.work()))
        self.assertIsNone(self.c.state.validation)
        self.assertIsNone(self.c.state.plan)
        self.assertEqual(self.c.state.result.outcome, "cancelled")

    def test_cancelled_folder_listing_does_not_select_a_folder(self):
        self.validate()
        self.c.set_destination(category="projetos")
        job = self.c.start_list_folders()
        self.c.cancel_step()
        self.assertFalse(self.c.complete(job, job.work()))
        self.assertIsNone(self.c.state.subfolder)
        self.assertFalse(self.c.can_prepare)

    def test_cancelling_preparation_and_confirmation_never_writes_notes(self):
        self.validate()
        self.c.set_destination(category="aws-cloud")
        job = self.c.start_prepare()
        self.c.cancel_step()
        self.assertFalse(self.c.complete(job, job.work()))
        self.run_job(self.c.start_prepare())
        target = self.c.state.plan.destination
        token = self.c.request_confirmation()
        self.assertIsNone(self.c.start_import(token, False))
        self.assertFalse(target.exists())
        self.assertEqual(self.c.organizer.history.operations(), ())

    def test_full_import_preserves_bytes_and_lifecycle(self):
        self.prepare()
        target = self.c.state.plan.destination
        original = self.w.source.read_bytes()
        self.import_prepared()
        self.assertEqual(self.c.state.result.outcome, "imported")
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(self.w.source.read_bytes(), original)
        self.assertEqual(self.c.state.validation.note.metadata["status"], "inbox")
        self.assertIs(self.c.state.validation.note.metadata["lumen_export"], False)

    def test_duplicate_display_does_not_start_another_import(self):
        self.prepare()
        self.import_prepared()
        self.c.set_destination(category="ia")
        self.run_job(self.c.start_prepare())
        self.assertEqual(self.c.state.result.outcome, "duplicate")
        self.assertIsNone(self.c.state.plan)
        self.assertEqual(len(self.c.organizer.history.operations()), 1)

    def test_collision_suffix_and_concurrent_collision(self):
        self.validate()
        self.c.set_destination(category="aws-cloud")
        existing = self.c.policy.target("aws-cloud", self.w.source.name)
        existing.write_bytes(b"FICTITIOUS EXISTING NOTE")
        self.run_job(self.c.start_prepare())
        target = self.c.state.plan.destination
        self.assertEqual(target.name, "fictional-2.md")
        target.write_bytes(b"FICTITIOUS LATE COLLISION")
        self.import_prepared()
        self.assertEqual(self.c.state.result.code, "destination_collision")
        self.assertEqual(target.read_bytes(), b"FICTITIOUS LATE COLLISION")
        self.assertEqual(existing.read_bytes(), b"FICTITIOUS EXISTING NOTE")

    def test_destination_edit_expires_confirmation(self):
        self.prepare()
        target = self.c.state.plan.destination
        token = self.c.request_confirmation()
        self.c.set_destination(category="ia", filename="different.md")
        self.assertIsNone(self.c.start_import(token, True))
        self.assertEqual(self.c.state.result.code, "confirmation_invalid")
        self.assertFalse(target.exists())

    def test_source_selection_edit_expires_confirmation(self):
        self.prepare()
        token = self.c.request_confirmation()
        self.c.select_file(self.w.source)
        self.assertIsNone(self.c.start_import(token, True))
        self.assertIsNone(self.c.state.category)
        self.assertEqual(self.c.organizer.history.operations(), ())

    def test_changed_source_before_preparation_clears_stale_preview(self):
        self.validate()
        self.c.set_destination(category="aws-cloud")
        self.w.source.write_bytes(self.w.source.read_bytes() + b"\nFictitious edit\n")
        self.run_job(self.c.start_prepare())
        self.assertEqual(self.c.state.error_code, "source_changed")
        self.assertIsNone(self.c.state.validation)
        self.assertFalse(self.c.can_prepare)

    def test_changed_source_after_confirmation_is_blocked_by_core(self):
        self.prepare()
        target = self.c.state.plan.destination
        token = self.c.request_confirmation()
        self.w.source.write_bytes(self.w.source.read_bytes() + b"\nFictitious edit\n")
        self.run_job(self.c.start_import(token, True))
        self.assertEqual(self.c.state.result.code, "source_changed")
        self.assertFalse(target.exists())
        self.assertIsNone(self.c.state.validation)

    def test_confirmation_is_one_shot(self):
        self.prepare()
        token = self.c.request_confirmation()
        self.run_job(self.c.start_import(token, True))
        self.assertIsNone(self.c.start_import(token, True))
        self.assertEqual(len(self.c.organizer.history.operations()), 1)

    def test_history_incomplete_halts_import_and_reconciles(self):
        self.prepare()
        target = self.c.state.plan.destination
        with patch.object(self.c.organizer.history, "complete", side_effect=LumenError("history_unavailable")):
            self.import_prepared()
        self.assertEqual(self.c.state.result.outcome, "saved_history_incomplete")
        self.assertIn("Não repita", result_text(self.c.state.result)[1])
        self.assertEqual(target.read_bytes(), self.w.source.read_bytes())
        self.assertTrue(self.c.state.requires_reconciliation)
        self.assertFalse(self.c.can_prepare)
        self.run_job(self.c.start_reconcile())
        self.assertEqual(self.c.state.result.outcome, "reconciled_import")
        self.assertFalse(self.c.state.requires_reconciliation)
        self.assertFalse(self.c.state.saved_uncertain)

    def test_unknown_import_error_halts_without_exposing_exception(self):
        self.prepare()
        token = self.c.request_confirmation()
        job = self.c.start_import(token, True)
        self.c.complete(job, error_code="unexpected_error")
        self.assertTrue(self.c.state.saved_uncertain)
        self.assertEqual(self.c.state.result.outcome, "save_state_unknown")
        self.assertIn("Não repita", result_text(self.c.state.result)[1])
        self.assertFalse(self.c.can_prepare)
        self.run_job(self.c.start_reconcile())
        self.assertTrue(self.c.state.saved_uncertain)

    def test_state_updates_must_use_owner_thread(self):
        errors = []
        def mutate():
            try:
                self.c.select_file(self.w.source)
            except RuntimeError as exc:
                errors.append(type(exc))
        thread = threading.Thread(target=mutate)
        thread.start()
        thread.join()
        self.assertEqual(errors, [RuntimeError])
        self.assertIsNone(self.c.state.source)

    def test_unexpected_settings_preserved(self):
        self.w.state.mkdir()
        self.c.store.path.write_bytes(b"FICTITIOUS UNEXPECTED FILE")
        self.run_job(self.c.start_configure(self.w.vault))
        self.assertEqual(self.c.state.error_code, "invalid_settings")
        self.assertEqual(self.c.store.path.read_bytes(), b"FICTITIOUS UNEXPECTED FILE")
