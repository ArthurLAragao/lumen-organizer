"""Confirmed single-note package publication outside the vault; no GUI or Atlas I/O."""

from dataclasses import dataclass, field
from hashlib import sha256
import os
from pathlib import Path
import uuid

from .atlas_transfer import MAX_PACKAGE_BYTES, atlas_compatible, decode_package, encode_package
from .destinations import DestinationPolicy, check_directory_chain, check_filename, relative_parts
from .export_registry import ExportRegistry
from .filesystem import directory_guard, publish_no_replace, regular_file
from .models import Issue, LumenError, ValidatedNote, ValidationResult
from .validation import _validate_file_profile


def _location(source, policy, category, subfolder=None):
    path = Path(source).absolute()
    try:
        relative = path.relative_to(policy.root).as_posix()
    except ValueError:
        raise LumenError("export_source_outside_vault") from None
    relative_parts(relative)
    check_filename(path.name)
    folder = policy.folder(category, subfolder)
    if path.parent != folder or check_directory_chain(path.parent) != folder:
        raise LumenError("export_source_outside_area")
    return path, relative


def validate_export_file(source, policy: DestinationPolicy, category: str, subfolder=None) -> ValidationResult:
    """Check an explicit authorized area BEFORE opening a selected source file."""
    try:
        path, _ = _location(source, policy, category, subfolder)
        with directory_guard(path.parent):
            return atlas_compatible(_validate_file_profile(path, export_profile=True))
    except LumenError as exc:
        return ValidationResult(None, (Issue("error", exc.code, "Select a regular note in the explicitly authorized area."),))


@dataclass(frozen=True)
class ExportPlan:
    export_id: str
    integration_id: str
    note: ValidatedNote = field(repr=False)
    category: str = field(repr=False)
    subfolder: str | None = field(repr=False)
    relative_source: str = field(repr=False)
    package_bytes: bytes = field(repr=False)
    baseline_export_id: str | None = None


@dataclass(frozen=True)
class ExportResult:
    outcome: str
    code: str
    export_id: str | None = None
    package_path: Path | None = field(default=None, repr=False)
    delivery: str = "unknown"


class AtlasExporter:
    def __init__(self, policy: DestinationPolicy, registry: ExportRegistry):
        if registry.directory.is_relative_to(policy.root):
            raise LumenError("export_state_inside_vault")
        self.policy, self.registry = policy, registry

    def _validated(self, source, category, subfolder=None):
        result = validate_export_file(source, self.policy, category, subfolder)
        if not result.valid:
            raise LumenError("export_validation_failed")
        return result.note

    def register(self, source, category, subfolder=None, *, confirmed=False):
        if confirmed is not True:
            raise LumenError("identity_confirmation_required")
        self._validated(source, category, subfolder)
        _, relative = _location(source, self.policy, category, subfolder)
        return self.registry.register(self.policy.vault_id, relative, confirmed=True)

    def rebind(self, integration_id, source, category, subfolder=None, *, confirmed=False):
        if confirmed is not True:
            raise LumenError("identity_confirmation_required")
        self._validated(source, category, subfolder)
        _, relative = _location(source, self.policy, category, subfolder)
        identity = self.registry.identity(integration_id)
        if identity.vault_id != self.policy.vault_id:
            raise LumenError("cross_vault_identity_rebind")
        old = self.policy.root.joinpath(*relative_parts(identity.relative_source))
        with directory_guard(old.parent):
            if os.path.lexists(old) and relative != identity.relative_source:
                raise LumenError("old_export_source_still_exists")
            return self.registry.rebind(integration_id, self.policy.vault_id, relative, confirmed=True)

    def _baseline(self, integration_id, baseline_export_id):
        if baseline_export_id is None:
            return None
        record = self.registry.record(baseline_export_id)
        if record.integration_id != integration_id:
            raise LumenError("cross_identity_baseline")
        # This is only an explicitly selected expected-content candidate.
        # Reading a prepared archive NEVER changes delivery or a confirmed baseline.
        return decode_package(self.read_prepared(baseline_export_id)).comparison_sha256

    def prepare(self, source, category, subfolder=None, *, baseline_export_id=None) -> ExportPlan:
        note = self._validated(source, category, subfolder)
        _, relative = _location(source, self.policy, category, subfolder)
        identity = self.registry.identity_for(self.policy.vault_id, relative)
        if identity is None:
            raise LumenError("identity_registration_required")
        if self.registry.pending():
            raise LumenError("export_reconciliation_required")
        baseline = self._baseline(identity.integration_id, baseline_export_id)
        data = encode_package(note, identity.integration_id, baseline)
        return ExportPlan(uuid.uuid4().hex, identity.integration_id, note, category, subfolder,
                          relative, data, baseline_export_id)

    def _read_owned(self, path, record):
        if not regular_file(path):
            raise LumenError("export_package_missing_or_unsafe")
        try:
            with path.open("rb") as stream:
                data = stream.read(MAX_PACKAGE_BYTES + 1)
        except OSError:
            raise LumenError("export_package_unreadable") from None
        if len(data) != record.package_size or sha256(data).hexdigest() != record.package_sha256:
            raise LumenError("export_package_conflict")
        package = decode_package(data)
        if (package.integration_id != record.integration_id or package.source_sha256 != record.source_sha256
                or package.comparison_sha256 != record.comparison_sha256 or package.baseline_sha256 != record.baseline_sha256):
            raise LumenError("export_package_conflict")
        return data

    def read_prepared(self, export_id) -> bytes:
        record = self.registry.record(export_id)
        if record.state != "prepared":
            raise LumenError("export_not_prepared")
        with directory_guard(self.registry.archives):
            return self._read_owned(self.registry.archive_path(export_id), record)

    def commit(self, plan: ExportPlan, *, confirmed=False) -> ExportResult:
        if confirmed is not True:
            return ExportResult("cancelled", "export_not_confirmed")
        if not isinstance(plan, ExportPlan):
            raise LumenError("export_plan_required")
        started, published, verified = False, False, False
        target = None
        try:
            with self.registry.locked():
                current = self._validated(plan.note.source, plan.category, plan.subfolder)
                _, relative = _location(current.source, self.policy, plan.category, plan.subfolder)
                identity = self.registry.identity_for(self.policy.vault_id, relative)
                if relative != plan.relative_source or not identity or identity.integration_id != plan.integration_id:
                    raise LumenError("export_identity_changed")
                if current.data != plan.note.data or current.fingerprint != plan.note.fingerprint:
                    raise LumenError("export_source_changed")
                expected = encode_package(current, plan.integration_id,
                                          self._baseline(plan.integration_id, plan.baseline_export_id))
                if expected != plan.package_bytes:
                    raise LumenError("export_plan_changed")
                package = decode_package(plan.package_bytes)
                target = self.registry.archive_path(plan.export_id)
                staged = self.registry.stage_path(plan.export_id)
                if os.path.lexists(target) or os.path.lexists(staged):
                    raise LumenError("export_package_collision")
                self.registry._start(plan.export_id, package, plan.package_bytes)
                started = True
                with staged.open("xb") as stream:
                    stream.write(plan.package_bytes)
                    stream.flush()
                    os.fsync(stream.fileno())
                publish_no_replace(staged, target)
                published = True
                self._read_owned(target, self.registry.record(plan.export_id))
                verified = True
                self.registry._complete(plan.export_id)
                return ExportResult("prepared", "export_prepared", plan.export_id, target)
        except LumenError as exc:
            # Pending/staging are retained for explicit reconciliation; no blind retry.
            return ExportResult(("prepared_registry_incomplete" if verified else "package_unverified") if published else "blocked", exc.code,
                                plan.export_id if started else None, target if published else None)
        except OSError:
            return ExportResult("prepared_registry_incomplete" if published else "recovery_required" if started else "blocked",
                                "export_write_failed", plan.export_id if started else None, target if published else None)
        except Exception:
            return ExportResult(("prepared_registry_incomplete" if verified else "package_unverified") if published else "recovery_required" if started else "blocked",
                                "export_unexpected_error", plan.export_id if started else None, target if published else None)

    def reconcile(self) -> tuple[ExportResult, ...]:
        """Verify archive; never replay writes, delete files or read current notes."""
        results = []
        with self.registry.locked():
            for record in self.registry.pending():
                target, staged = self.registry.archive_path(record.id), self.registry.stage_path(record.id)
                try:
                    if os.path.lexists(target):
                        self._read_owned(target, record)
                        self.registry._complete(record.id, recovered=True)
                        results.append(ExportResult("prepared", "export_recovered", record.id, target))
                    elif os.path.lexists(staged):
                        self._read_owned(staged, record)
                        results.append(ExportResult("recovery_required", "export_staging_retained", record.id))
                    else:
                        self.registry._fail(record.id, "export_interrupted")
                        results.append(ExportResult("failed", "export_interrupted", record.id))
                except LumenError as exc:
                    results.append(ExportResult("recovery_required", exc.code, record.id))
                except Exception:
                    results.append(ExportResult("recovery_required", "export_unexpected_error", record.id))
        return tuple(results)

    def recover(self, export_id, *, confirmed=False) -> ExportResult:
        """Explicitly publish preserved staging bytes only; no source reconstruction."""
        if confirmed is not True:
            return ExportResult("cancelled", "export_recovery_not_confirmed")
        published = False
        target = None
        try:
            with self.registry.locked():
                record = self.registry.record(export_id)
                if record.state != "pending":
                    raise LumenError("export_recovery_not_pending")
                target = self.registry.archive_path(export_id)
                if os.path.lexists(target):
                    self._read_owned(target, record)
                else:
                    staged = self.registry.stage_path(export_id)
                    self._read_owned(staged, record)
                    publish_no_replace(staged, target)
                published = True
                self._read_owned(target, record)
                self.registry._complete(export_id, recovered=True)
                return ExportResult("prepared", "export_recovered", export_id, target)
        except LumenError as exc:
            return ExportResult("prepared_registry_incomplete" if published else "recovery_required", exc.code, export_id,
                                target if published else None)
        except OSError:
            return ExportResult("prepared_registry_incomplete" if published else "recovery_required", "export_write_failed",
                                export_id, target if published else None)
        except Exception:
            return ExportResult("prepared_registry_incomplete" if published else "recovery_required", "export_unexpected_error",
                                export_id, target if published else None)
