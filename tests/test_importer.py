from contextlib import closing
from dataclasses import replace
import errno
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import textwrap
import unittest
from unittest.mock import patch

from lumen_organizer.destinations import DestinationPolicy
from lumen_organizer.filesystem import publish_no_replace, session_lock
from lumen_organizer.history import AuditCode
from lumen_organizer.importer import Organizer
from lumen_organizer.models import LumenError
from lumen_organizer.validation import validate_file
from .support import FictionalWorkspace, bounded_writes, changed_note


class SimulatedInterruption(BaseException):
    """Mimics abrupt interruption while still releasing test process locks."""


@unittest.skipUnless(os.name == "nt", "Safe importer initially supports Windows only")
class ImportTests(unittest.TestCase):
    def setUp(self):
        self.workspace = FictionalWorkspace()
        self.w = self.workspace.__enter__()
        self.bound = bounded_writes(self.w.root)
        self.bound.__enter__()
        self.policy = DestinationPolicy(self.w.vault)
        self.organizer = Organizer(self.policy, self.w.state)
        self.note = validate_file(self.w.source).note

    def tearDown(self):
        self.bound.__exit__(None, None, None)
        self.workspace.__exit__()

    def plan(self, **kwargs):
        return self.organizer.prepare(self.note, kwargs.pop("category", "aws-cloud"), **kwargs)

    def test_exact_bytes_source_preservation_and_passive_lifecycle(self):
        for action in ("none", "suggest"):
            with self.subTest(action=action):
                data = changed_note(self.note.data, "atlas_action", action)
                data = b"\xef\xbb\xbf" + data.replace(b"\n", b"\r\n")
                self.w.source.write_bytes(data)
                note = validate_file(self.w.source).note
                plan = self.organizer.prepare(note, "indefinido", filename=action + ".md")
                result = self.organizer.commit(plan, confirmed=True)
                self.assertEqual(result.outcome, "imported")
                self.assertEqual(plan.destination.read_bytes(), data)
                self.assertEqual(self.w.source.read_bytes(), data)
                imported = validate_file(plan.destination)
                self.assertEqual(imported.note.metadata["status"], "inbox")
                self.assertIs(imported.note.metadata["lumen_export"], False)

    def test_cancellation_has_no_note_or_history_operation(self):
        plan = self.plan()
        result = self.organizer.commit(plan, confirmed=False)
        self.assertEqual(result.outcome, "cancelled")
        self.assertFalse(plan.destination.exists())
        self.assertEqual(self.organizer.history.operations(), ())

    def test_confirmation_and_repeat_require_actual_booleans(self):
        self.assertEqual(self.organizer.commit(self.plan(), confirmed="yes").outcome, "cancelled")
        with self.assertRaises(LumenError):
            self.plan(allow_repeat="yes")
        with self.assertRaises(LumenError):
            self.plan(filename="")

    def test_duplicate_detected_even_with_different_source_name_and_category(self):
        first = self.organizer.commit(self.plan(), confirmed=True)
        renamed = self.w.root / "renamed.md"
        renamed.write_bytes(self.note.data)
        second_note = validate_file(renamed).note
        plan = self.organizer.prepare(second_note, "ia")
        second = self.organizer.commit(plan, confirmed=True)
        self.assertEqual(second.outcome, "duplicate")
        self.assertEqual(second.destination, first.destination)
        self.assertFalse(plan.destination.exists())
        self.assertEqual(len(self.organizer.history.operations()), 1)

    def test_untracked_identical_note_is_only_a_filename_collision(self):
        original = self.policy.target("aws-cloud", self.w.source.name)
        original.write_bytes(self.note.data)
        self.assertEqual(self.organizer.duplicate_status(self.note), ("new", None))
        plan = self.plan()
        self.assertEqual(plan.filename, "fictional-2.md")
        result = self.organizer.commit(plan, confirmed=True)
        self.assertEqual(result.outcome, "imported")
        self.assertEqual(original.read_bytes(), self.note.data)

    def test_collision_created_after_confirmation_never_overwrites(self):
        plan = self.plan()
        def concurrent_collision(staged, destination):
            destination.write_bytes(b"FICTIONAL EXISTING FILE")
            publish_no_replace(staged, destination)
        with patch("lumen_organizer.importer.publish_no_replace", side_effect=concurrent_collision):
            result = self.organizer.commit(plan, confirmed=True)
        self.assertEqual(result.code, "destination_collision")
        self.assertEqual(plan.destination.read_bytes(), b"FICTIONAL EXISTING FILE")
        self.assertEqual(self.organizer.history.operations()[0].state, "failed")
        self.assertEqual(list(self.organizer.history.staging.iterdir()), [])

    def test_occupied_destination_requires_a_new_plan(self):
        plan = self.plan()
        plan.destination.write_bytes(b"FICTIONAL COLLISION")
        result = self.organizer.commit(plan, confirmed=True)
        self.assertEqual(result.code, "destination_collision")
        replacement = self.plan()
        self.assertNotEqual(replacement.destination, plan.destination)
        self.assertEqual(self.organizer.commit(replacement, confirmed=False).outcome, "cancelled")

    def test_source_change_after_validation_blocks_import(self):
        plan = self.plan()
        self.w.source.write_bytes(self.note.data + b"\nFictional changed content.\n")
        result = self.organizer.commit(plan, confirmed=True)
        self.assertEqual(result.code, "source_changed")
        self.assertFalse(plan.destination.exists())
        self.assertEqual(self.organizer.history.operations(), ())

    def test_deleted_source_blocks_import(self):
        plan = self.plan()
        self.w.source.unlink()
        self.assertEqual(self.organizer.commit(plan, confirmed=True).code, "source_changed")
        self.assertFalse(plan.destination.exists())

    def test_tampered_plan_destination_is_blocked(self):
        plan = replace(self.plan(), destination=self.w.root / "outside.md")
        self.assertEqual(self.organizer.commit(plan, confirmed=True).code, "destination_changed")
        self.assertFalse(plan.destination.exists())

    def test_changed_or_missing_prior_import_requires_explicit_repeat(self):
        result = self.organizer.commit(self.plan(), confirmed=True)
        result.destination.write_bytes(b"FICTIONAL MANUAL EDIT")
        plan = self.plan()
        self.assertEqual(self.organizer.commit(plan, confirmed=True).code, "prior_import_changed")
        self.assertEqual(result.destination.read_bytes(), b"FICTIONAL MANUAL EDIT")
        result.destination.unlink()
        self.assertEqual(self.organizer.commit(plan, confirmed=True).code, "prior_import_missing")
        explicit_plan = self.plan(allow_repeat=True)
        self.assertEqual(self.organizer.commit(explicit_plan, confirmed=True).outcome, "imported")

    def test_permission_and_disk_full_failures_are_sanitized(self):
        for exception, code in ((PermissionError("FICTIONAL PRIVATE EXCEPTION"), "permission_denied"),
                                (OSError(errno.ENOSPC, "FICTIONAL PRIVATE EXCEPTION"), "disk_full")):
            with self.subTest(code=code), patch("lumen_organizer.importer.publish_no_replace", side_effect=exception):
                plan = self.plan()
                result = self.organizer.commit(plan, confirmed=True)
                self.assertEqual(result.code, code)
                self.assertFalse(plan.destination.exists())
                self.assertEqual(list(self.organizer.history.staging.iterdir()), [])
        self.assertNotIn(b"FICTIONAL PRIVATE EXCEPTION", self.organizer.history.path.read_bytes())

    def test_history_start_failure_prevents_file_creation(self):
        plan = self.plan()
        with patch.object(self.organizer.history, "start", side_effect=LumenError("history_unavailable")):
            result = self.organizer.commit(plan, confirmed=True)
        self.assertEqual(result.outcome, "blocked")
        self.assertFalse(plan.destination.exists())
        self.assertEqual(list(self.organizer.history.staging.iterdir()), [])

    def test_history_failure_after_save_and_reconciliation(self):
        plan = self.plan()
        with patch.object(self.organizer.history, "complete", side_effect=LumenError("history_unavailable")):
            result = self.organizer.commit(plan, confirmed=True)
        self.assertEqual(result.outcome, "saved_history_incomplete")
        self.assertEqual(plan.destination.read_bytes(), self.note.data)
        self.assertEqual(self.organizer.history.operations()[0].state, "pending")
        reopened = Organizer(self.policy, self.w.state)
        recovered = reopened.reconcile()
        self.assertEqual(recovered[0].outcome, "reconciled_import")
        self.assertEqual(reopened.history.operations()[0].state, "succeeded")
        self.assertEqual(plan.destination.read_bytes(), self.note.data)
        self.assertEqual(reopened.reconcile(), ())

    def test_interruption_before_save_marks_failure_without_replaying(self):
        plan = self.plan()
        with patch("lumen_organizer.importer.publish_no_replace", side_effect=SimulatedInterruption), self.assertRaises(SimulatedInterruption):
            self.organizer.commit(plan, confirmed=True)
        self.assertFalse(plan.destination.exists())
        self.assertEqual(len(list(self.organizer.history.staging.iterdir())), 1)
        self.assertEqual(self.organizer.commit(self.plan(), confirmed=True).code, "reconciliation_required")
        results = Organizer(self.policy, self.w.state).reconcile()
        self.assertEqual(results[0].code, "interrupted_before_save")
        self.assertFalse(plan.destination.exists())
        self.assertEqual(list(self.organizer.history.staging.iterdir()), [])

    def test_interruption_after_save_recovers_completed_file(self):
        plan = self.plan()
        with patch.object(self.organizer.history, "complete", side_effect=SimulatedInterruption), self.assertRaises(SimulatedInterruption):
            self.organizer.commit(plan, confirmed=True)
        self.assertEqual(plan.destination.read_bytes(), self.note.data)
        self.assertEqual(Organizer(self.policy, self.w.state).reconcile()[0].outcome, "reconciled_import")

    def test_recovery_never_modifies_conflicting_final_file(self):
        plan = self.plan()
        with patch("lumen_organizer.importer.publish_no_replace", side_effect=SimulatedInterruption), self.assertRaises(SimulatedInterruption):
            self.organizer.commit(plan, confirmed=True)
        plan.destination.write_bytes(b"FICTIONAL CONFLICTING NOTE")
        results = self.organizer.reconcile()
        self.assertEqual(results[0].code, "recovery_destination_conflict")
        self.assertEqual(plan.destination.read_bytes(), b"FICTIONAL CONFLICTING NOTE")

    def test_recovery_does_not_delete_unmanaged_staging_files(self):
        orphan = self.organizer.history.staging / "unexpected.tmp"
        orphan.write_bytes(b"FICTIONAL UNMANAGED FILE")
        self.organizer.reconcile()
        self.assertEqual(orphan.read_bytes(), b"FICTIONAL UNMANAGED FILE")

    def test_raw_note_content_is_absent_from_persistent_history(self):
        data = changed_note(self.note.data, "title", '"PRIVATE-FICTIONAL-TITLE-MARKER"') + b"\nPRIVATE-FICTIONAL-BODY-MARKER\n"
        self.w.source.write_bytes(data)
        note = validate_file(self.w.source).note
        self.organizer.commit(self.organizer.prepare(note, "ia"), confirmed=True)
        database_bytes = self.organizer.history.path.read_bytes()
        self.assertNotIn(b"PRIVATE-FICTIONAL", database_bytes)
        with closing(sqlite3.connect(self.organizer.history.path)) as connection:
            for row in connection.execute("SELECT * FROM events"):
                self.assertNotIn("PRIVATE-FICTIONAL", repr(row))

    def test_windows_process_lock_blocks_second_operation(self):
        with session_lock(self.organizer.history.directory):
            result = self.organizer.commit(self.plan(), confirmed=True)
        self.assertEqual(result.code, "state_busy")

    def test_same_volume_required(self):
        plan = self.plan()
        from types import SimpleNamespace
        real_stat = os.stat
        def different_volume(path, *args, **kwargs):
            if Path(path) == self.organizer.history.staging:
                info = real_stat(path, *args, **kwargs)
                attributes = {name: getattr(info, name) for name in dir(info) if name.startswith("st_")}
                attributes["st_dev"] = -123
                return SimpleNamespace(**attributes)
            return real_stat(path, *args, **kwargs)
        with patch("lumen_organizer.importer.os.stat", side_effect=different_volume):
            self.assertEqual(self.organizer.commit(plan, confirmed=True).code, "state_wrong_volume")
        self.assertFalse(plan.destination.exists())

    def test_unexpected_database_preserved(self):
        other_state = self.w.root / "UnexpectedState"
        other_state.mkdir()
        database = other_state / "history.sqlite3"
        database.write_bytes(b"FICTIONAL UNEXPECTED FILE")
        with self.assertRaises(LumenError):
            Organizer(self.policy, other_state)
        self.assertEqual(database.read_bytes(), b"FICTIONAL UNEXPECTED FILE")

    def test_write_boundary_covers_core_and_rejects_outside_paths(self):
        # Every test in this class executes the core with this audit boundary.
        # This deliberately prohibited write is outside the mock workspace,
        # not a probe of any real vault.
        with self.assertRaises(AssertionError):
            (self.w.root.parent / "prohibited-probe.tmp").write_bytes(b"fictional")
        self.assertEqual(self.organizer.commit(self.plan(), confirmed=True).outcome, "imported")

    def test_actual_child_process_exit_before_and_after_publication(self):
        # Unlike SimulatedInterruption, os._exit does not unwind Python
        # finally blocks. Windows must release the file/byte locks itself.
        script = textwrap.dedent('''
            from pathlib import Path
            import os, sys
            from lumen_organizer.destinations import DestinationPolicy
            from lumen_organizer.importer import Organizer
            import lumen_organizer.importer as importer
            from lumen_organizer.validation import validate_file
            from tests.support import bounded_writes
            root = Path(sys.argv[1])
            with bounded_writes(root):
                organizer = Organizer(DestinationPolicy(root / 'FictionalVault'), root / '.local')
                note = validate_file(root / 'fictional.md').note
                plan = organizer.prepare(note, 'aws-cloud', filename=sys.argv[2] + '.md')
                if sys.argv[2] == 'before':
                    importer.publish_no_replace = lambda *args: os._exit(23)
                else:
                    organizer.history.complete = lambda *args: os._exit(23)
                organizer.commit(plan, confirmed=True)
        ''')
        for stage in ("before", "after"):
            with self.subTest(stage=stage):
                child_env = os.environ.copy()
                project = Path(__file__).resolve().parents[1]
                child_env["PYTHONPATH"] = os.pathsep.join((str(project / "src"), str(project)))
                process = subprocess.run([sys.executable, "-c", script, str(self.w.root), stage],
                                         env=child_env, capture_output=True, text=True, timeout=20)
                self.assertEqual(process.returncode, 23, process.stderr)
                target = self.policy.target("aws-cloud", stage + ".md")
                self.assertEqual(target.exists(), stage == "after")
                result = Organizer(self.policy, self.w.state).reconcile()[0]
                self.assertEqual(result.outcome, "reconciled_import" if stage == "after" else "reconciled_failure")
                self.assertEqual(list(self.organizer.history.staging.iterdir()), [])
