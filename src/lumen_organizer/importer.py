"""Confirmed byte-preserving imports and reconciliation, without a GUI."""

import errno
from hashlib import sha256
import os
from pathlib import Path

from .destinations import DestinationPolicy
from .filesystem import directory_guard, publish_no_replace, regular_file, session_lock
from .history import AuditCode, History
from .models import ImportPlan, ImportResult, LumenError, ValidatedNote
from .validation import MAX_FILE_BYTES, validate_file


def _file_digest(path: Path) -> str | None:
    if not regular_file(path):
        return None
    try:
        with path.open("rb") as stream:
            data = stream.read(MAX_FILE_BYTES + 1)
    except OSError:
        return None
    return sha256(data).hexdigest() if len(data) <= MAX_FILE_BYTES else None


class Organizer:
    def __init__(self, policy: DestinationPolicy, state_directory: str | Path):
        self.policy = policy
        self.history = History(state_directory, policy.root)

    def prepare(self, note: ValidatedNote, category: str, subfolder: str | None = None,
                filename: str | None = None, allow_repeat: bool = False) -> ImportPlan:
        if not isinstance(note, ValidatedNote):
            raise LumenError("validated_note_required")
        if type(allow_repeat) is not bool:
            raise LumenError("explicit_repeat_flag_required")
        target = self.policy.suggest_target(category, filename if filename is not None else note.source.name, subfolder)
        return ImportPlan(note, category, subfolder, target.name, target, allow_repeat)

    def duplicate_status(self, note: ValidatedNote) -> tuple[str, Path | None]:
        previous = self.history.previous(self.policy.vault_id, note.fingerprint)
        if previous is None:
            return "new", None
        try:
            target = self.policy.recorded_target(previous.category, previous.relative_destination)
            with directory_guard(target.parent):
                if not os.path.lexists(target):
                    return "missing", target
                digest = _file_digest(target)
        except LumenError:
            return "unavailable", None
        return ("identical" if digest == note.fingerprint else "changed"), target

    def _best_effort_failure(self, operation_id: str, code: AuditCode):
        try:
            self.history.fail(operation_id, code)
            return True
        except LumenError:
            return False

    def _remove_staging(self, staged: Path):
        if staged.parent == self.history.staging and regular_file(staged):
            try:
                staged.unlink()
            except OSError:
                pass  # Reconciliation can retry cleanup; never remove a target note.

    def commit(self, plan: ImportPlan, *, confirmed: bool = False) -> ImportResult:
        if confirmed is not True:
            return ImportResult("cancelled", "not_confirmed")
        if not isinstance(plan, ImportPlan):
            raise LumenError("import_plan_required")
        operation_id = None
        staged = None
        published = False
        try:
            with directory_guard(self.history.staging), session_lock(self.history.directory):
                target = self.policy.target(plan.category, plan.filename, plan.subfolder)
                if target != plan.destination:
                    return ImportResult("blocked", "destination_changed")
                # Lock destination ancestors until publication completes.
                with directory_guard(target.parent):
                    current = validate_file(plan.note.source)
                    if (not current.valid or current.note.fingerprint != plan.note.fingerprint
                            or current.note.data != plan.note.data):
                        self.history.audit(AuditCode.SOURCE_CHANGED)
                        return ImportResult("blocked", "source_changed")
                    if self.history.pending(self.policy.vault_id):
                        return ImportResult("blocked", "reconciliation_required")
                    status, previous_target = self.duplicate_status(plan.note)
                    if status == "identical":
                        self.history.audit(AuditCode.DUPLICATE)
                        return ImportResult("duplicate", "already_imported", destination=previous_target)
                    if status != "new" and plan.allow_repeat is not True:
                        return ImportResult("blocked", "prior_import_" + status, destination=previous_target)
                    if os.path.lexists(target):
                        self.history.audit(AuditCode.COLLISION)
                        return ImportResult("blocked", "destination_collision", destination=target)
                    if os.stat(self.history.staging).st_dev != os.stat(target.parent).st_dev:
                        return ImportResult("blocked", "state_wrong_volume")
                    operation_id = self.history.start(self.policy.vault_id, plan.note.fingerprint,
                                                      plan.category, target.relative_to(self.policy.root).as_posix())
                    staged = self.history.staging / (operation_id + ".tmp")
                    try:
                        with staged.open("xb") as stream:
                            stream.write(plan.note.data)
                            stream.flush()
                            os.fsync(stream.fileno())
                        publish_no_replace(staged, target)
                        published = True
                        if _file_digest(target) != plan.note.fingerprint:
                            self._best_effort_failure(operation_id, AuditCode.VERIFY_FAILED)
                            return ImportResult("saved_unverified", "saved_verification_failed", operation_id, target)
                        try:
                            self.history.complete(operation_id)
                        except LumenError:
                            return ImportResult("saved_history_incomplete", "history_incomplete", operation_id, target)
                        return ImportResult("imported", "import_succeeded", operation_id, target)
                    except OSError as exc:
                        if isinstance(exc, FileExistsError):
                            code = AuditCode.COLLISION
                        elif isinstance(exc, PermissionError):
                            code = AuditCode.PERMISSION
                        elif exc.errno == errno.ENOSPC:
                            code = AuditCode.DISK_FULL
                        else:
                            code = AuditCode.WRITE_FAILED
                        recorded = self._best_effort_failure(operation_id, code)
                        self._remove_staging(staged)
                        return ImportResult("failed" if recorded else "failed_history_incomplete",
                                            code.value, operation_id, target if published else None)
        except LumenError as exc:
            if operation_id and not published:
                self._best_effort_failure(operation_id, AuditCode.UNSAFE_DESTINATION)
            return ImportResult("saved_history_incomplete" if published else "blocked", exc.code,
                                operation_id, plan.destination if published else None)
        except OSError:
            # No raw OS exception text is stored or displayed.
            return ImportResult("blocked", "filesystem_unavailable", operation_id)

    def reconcile(self) -> tuple[ImportResult, ...]:
        """Verify pending destinations; never replay a write into the vault.

        If no complete matching final file exists, mark the attempt failed.
        Cleanup is limited to this journal's UUID staging files outside the
        vault. No existing Markdown is removed or changed during recovery.
        """
        results = []
        with directory_guard(self.history.staging), session_lock(self.history.directory):
            for operation in self.history.pending(self.policy.vault_id):
                staged = self.history.staging / (operation.id + ".tmp")
                try:
                    target = self.policy.recorded_target(operation.category, operation.relative_destination)
                    with directory_guard(target.parent):
                        if _file_digest(target) == operation.fingerprint:
                            self.history.complete(operation.id, recovered=True)
                            result = ImportResult("reconciled_import", "reconciled_saved_file", operation.id, target)
                        else:
                            exists = os.path.lexists(target)
                            code = AuditCode.RECOVERY_CONFLICT if exists else AuditCode.INTERRUPTED
                            self.history.fail(operation.id, code)
                            result = ImportResult("reconciled_failure", code.value, operation.id)
                    self._remove_staging(staged)
                    results.append(result)
                except LumenError as exc:
                    # An unsafe/missing parent or inaccessible history remains
                    # pending for explicit resolution; do not touch the target.
                    results.append(ImportResult("reconciliation_blocked", exc.code, operation.id))
        return tuple(results)
