"""Tk-independent workflow state. Work runs elsewhere; acceptance runs on owner thread."""

from dataclasses import dataclass, field
from pathlib import Path
import threading
from typing import Callable, Any
import uuid

from .destinations import CHOOSABLE, DestinationPolicy
from .importer import Organizer
from .models import ImportPlan, ImportResult, LumenError, ValidationResult
from .settings import SettingsStore
from .validation import validate_file


@dataclass
class ViewState:
    vault: Path | None = None
    source: Path | None = None
    validation: ValidationResult | None = None
    category: str | None = None
    subfolder: str | None = None
    filename: str = ""
    plan: ImportPlan | None = None
    result: ImportResult | None = None
    error_code: str | None = None
    status: str = "configure"
    busy: str | None = None
    requires_reconciliation: bool = False
    saved_uncertain: bool = False
    folders: tuple[str, ...] = ()
    folder_parent: str | None = None


@dataclass(frozen=True)
class Job:
    kind: str
    revision: int
    work: Callable[[], Any] = field(repr=False)
    accept: Callable[[Any], None] = field(repr=False)


@dataclass(frozen=True)
class Confirmation:
    id: str
    revision: int
    plan: ImportPlan


class Controller:
    def __init__(self, local_directory: Path):
        self.state = ViewState()
        self.store = SettingsStore(local_directory)
        self.policy: DestinationPolicy | None = None
        self.organizer: Organizer | None = None
        self.revision = 0
        self.active: Job | None = None
        self.confirmation: Confirmation | None = None
        self.owner_thread = threading.get_ident()

    def _owner(self):
        if threading.get_ident() != self.owner_thread:
            raise RuntimeError("Workflow state must be updated on its owner thread.")

    def _available(self):
        self._owner()
        if self.active is not None:
            raise LumenError("operation_busy")

    def _invalidate(self, clear_result=True):
        self.revision += 1
        self.confirmation = None
        self.state.plan = None
        self.state.error_code = None
        if clear_result:
            self.state.result = None

    def _job(self, kind, work, accept) -> Job:
        self._available()
        self.state.busy = kind
        self.state.error_code = None
        job = Job(kind, self.revision, work, accept)
        self.active = job
        return job

    def complete(self, job: Job, value=None, error_code: str | None = None):
        self._owner()
        if job is not self.active:
            return False
        self.active = None
        self.state.busy = None
        if job.revision != self.revision:
            return False
        if error_code:
            self.state.error_code = error_code
            self.state.status = "error"
            self.confirmation = None
            self.state.plan = None
            if error_code == "source_changed":
                self.state.validation = None
            if job.kind == "import":
                # Unknown worker failures may occur after saving. Halt rather
                # than inviting an unsafe retry; recovery decides what exists.
                self.state.requires_reconciliation = True
                self.state.saved_uncertain = True
                self.state.result = ImportResult("save_state_unknown", error_code)
                self.state.status = "result"
            return False
        job.accept(value)
        return True

    def start_load_settings(self):
        store = self.store
        def work():
            policy = store.load()
            if policy is None:
                return None
            organizer = Organizer(policy, store.directory)
            pending = bool(organizer.history.pending(policy.vault_id))
            return policy, organizer, pending
        def accept(value):
            if value is not None:
                policy, organizer, pending = value
                self.policy, self.organizer = policy, organizer
                self.state = ViewState(vault=policy.root, status="choose_file", requires_reconciliation=pending)
        return self._job("configuration", work, accept)

    def start_configure(self, vault: Path):
        self._available()
        self._invalidate()
        store = self.store
        def work():
            policy = DestinationPolicy(vault)
            organizer = Organizer(policy, store.directory)
            pending = bool(organizer.history.pending(policy.vault_id))
            store.save(policy)
            return policy, organizer, pending
        def accept(value):
            policy, organizer, pending = value
            self.policy, self.organizer = policy, organizer
            self.state = ViewState(vault=policy.root, status="choose_file", requires_reconciliation=pending)
        return self._job("configuration", work, accept)

    def select_file(self, path: Path | None):
        self._available()
        if path is None:
            self.cancel_step("file_cancelled")
            return
        self._invalidate()
        self.state.source = Path(path).absolute()
        self.state.validation = None
        self.state.category = self.state.subfolder = None
        self.state.filename = self.state.source.name
        self.state.status = "validate"

    def clear_file(self):
        self._available()
        self._invalidate()
        self.state.source = self.state.validation = None
        self.state.category = self.state.subfolder = None
        self.state.filename = ""
        self.state.status = "choose_file"

    def set_destination(self, *, category: str | None = None, filename: str | None = None):
        self._available()
        self._invalidate()
        if category is not None and category != self.state.category:
            self.state.category = category or None
            self.state.subfolder = None
        if filename is not None:
            self.state.filename = filename
        self.state.status = "choose_destination"

    def start_validate(self):
        self._available()
        if self.state.source is None:
            raise LumenError("select_file_required")
        self._invalidate()
        self.state.validation = None
        source = self.state.source
        def accept(result):
            self.state.validation = result
            self.state.status = "valid" if result.valid else "invalid"
        return self._job("validation", lambda: validate_file(source), accept)

    def start_list_folders(self, parent: str | None = None):
        policy, category = self.policy, self.state.category
        if policy is None:
            raise LumenError("configuration_required")
        def accept(folders):
            self.state.folders = folders
            self.state.folder_parent = parent
        return self._job("folders", lambda: policy.list_subfolders(category, parent), accept)

    def start_choose_folder(self, relative_folder: str):
        self._available()
        self._invalidate()
        policy, category = self.policy, self.state.category
        if policy is None:
            raise LumenError("configuration_required")
        def accept(_):
            self.state.subfolder = relative_folder
            self.state.status = "choose_destination"
        return self._job("folder_selection", lambda: policy.folder(category, relative_folder), accept)

    @property
    def can_prepare(self):
        return (self.active is None and self.organizer is not None and self.state.validation is not None
                and self.state.validation.valid and self.state.category is not None
                and bool(self.state.filename)
                and (self.state.category not in CHOOSABLE or self.state.subfolder is not None)
                and not self.state.requires_reconciliation and not self.state.saved_uncertain)

    def start_prepare(self):
        self._available()
        if not self.can_prepare:
            raise LumenError("prepare_unavailable")
        self._invalidate()
        note = self.state.validation.note
        organizer = self.organizer
        category, subfolder, filename = self.state.category, self.state.subfolder, self.state.filename
        def work():
            current = validate_file(note.source)
            if not current.valid or current.note.data != note.data:
                raise LumenError("source_changed")
            plan = organizer.prepare(note, category, subfolder, filename)
            status, target = organizer.duplicate_status(note)
            return plan, status, target
        def accept(value):
            plan, duplicate, target = value
            if duplicate == "identical":
                self.state.result = ImportResult("duplicate", "already_imported", destination=target)
                self.state.status = "result"
            elif duplicate != "new":
                self.state.result = ImportResult("blocked", "prior_import_" + duplicate, destination=target)
                self.state.status = "result"
            else:
                self.state.plan = plan
                self.state.status = "prepared"
        return self._job("preparation", work, accept)

    def request_confirmation(self) -> Confirmation:
        self._available()
        if self.state.plan is None:
            raise LumenError("prepare_unavailable")
        confirmation = Confirmation(uuid.uuid4().hex, self.revision, self.state.plan)
        self.confirmation = confirmation
        self.state.status = "confirmation"
        return confirmation

    def start_import(self, confirmation: Confirmation, approved: bool):
        self._available()
        if approved is not True:
            self.cancel_step("confirmation_cancelled")
            return None
        if (confirmation is not self.confirmation or confirmation.revision != self.revision
                or confirmation.plan is not self.state.plan):
            self.state.result = ImportResult("blocked", "confirmation_invalid")
            self.state.status = "result"
            return None
        organizer, plan = self.organizer, confirmation.plan
        self.confirmation = None  # one-shot approval, consumed before dispatch
        def accept(result):
            self.state.plan = None
            self.state.result = result
            self.state.status = "result"
            if result.code == "source_changed":
                self.state.validation = None
            if result.outcome in ("saved_history_incomplete", "failed_history_incomplete", "saved_unverified"):
                self.state.requires_reconciliation = True
                self.state.saved_uncertain = True
            elif result.code == "reconciliation_required":
                self.state.requires_reconciliation = True
        return self._job("import", lambda: organizer.commit(plan, confirmed=True), accept)

    def start_reconcile(self):
        self._available()
        if self.organizer is None:
            raise LumenError("configuration_required")
        self._invalidate(clear_result=False)
        organizer = self.organizer
        def work():
            results = organizer.reconcile()
            pending = bool(organizer.history.pending(organizer.policy.vault_id))
            return results, pending
        def accept(value):
            results, pending = value
            self.state.requires_reconciliation = pending
            if results and not pending:
                self.state.saved_uncertain = False
            self.state.result = results[-1] if results else ImportResult("reconciliation_empty", "no_pending_operations")
            self.state.status = "result"
        return self._job("reconciliation", work, accept)

    def cancel_step(self, status="cancelled"):
        self._owner()
        if self.active is not None:
            if self.active.kind not in ("validation", "preparation", "folders"):
                raise LumenError("operation_cannot_cancel")
            # The read finishes safely, but its now-stale result is discarded.
        self._invalidate()
        self.state.status = status
        self.state.result = ImportResult("cancelled", "not_confirmed")

    def cancel_configuration(self):
        self._available()
        self.cancel_step("configuration_cancelled")
