"""Separate private identity/export journal. No import-history access or note logs."""

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
import sqlite3
import uuid

from .atlas_transfer import HEX64, INTEGRATION_ID
from .destinations import check_directory_chain, relative_parts
from .filesystem import directory_guard, regular_file, session_lock
from .models import LumenError

APPLICATION_ID = 0x4C554D41
SCHEMA = f"""
CREATE TABLE identities (
    integration_id TEXT PRIMARY KEY,
    vault_id TEXT NOT NULL,
    binding_key TEXT NOT NULL,
    relative_source TEXT NOT NULL,
    UNIQUE(vault_id, binding_key)
);
CREATE TABLE exports (
    id TEXT PRIMARY KEY,
    integration_id TEXT NOT NULL REFERENCES identities(integration_id),
    source_sha256 TEXT NOT NULL,
    comparison_sha256 TEXT NOT NULL,
    baseline_sha256 TEXT,
    package_sha256 TEXT NOT NULL,
    package_size INTEGER NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('pending', 'prepared', 'failed')),
    delivery TEXT NOT NULL CHECK(delivery = 'unknown'),
    error_code TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT
);
CREATE TABLE events (
    id INTEGER PRIMARY KEY,
    subject_id TEXT NOT NULL,
    code TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
PRAGMA application_id = {APPLICATION_ID};
PRAGMA user_version = 1;
"""
EVENT_CODES = frozenset({"identity_registered", "identity_rebound", "export_pending", "export_prepared",
                         "export_recovered", "export_interrupted", "export_write_failed"})


def _now():
    return datetime.now(timezone.utc).isoformat()


def _binding(relative: str):
    relative_parts(relative)
    return sha256(os.path.normcase(relative).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Identity:
    integration_id: str
    vault_id: str
    binding_key: str
    relative_source: str = field(repr=False)


@dataclass(frozen=True)
class ExportRecord:
    id: str
    integration_id: str
    source_sha256: str
    comparison_sha256: str
    baseline_sha256: str | None
    package_sha256: str
    package_size: int
    state: str
    delivery: str
    error_code: str | None
    started_at: str
    finished_at: str | None


class ExportRegistry:
    """Use create/open explicitly: missing state must not silently reset identity."""

    def __init__(self, state_directory: str | Path, vault_root: Path, *, create: bool = False):
        state = Path(state_directory).absolute()
        root = check_directory_chain(vault_root)
        if ".local" not in (part.casefold() for part in state.parts):
            raise LumenError("export_state_requires_local")
        if state.is_relative_to(root):
            raise LumenError("export_state_inside_vault")
        parent = check_directory_chain(state.parent)
        if create:
            with directory_guard(parent):
                try:
                    state.mkdir(exist_ok=True)
                except OSError:
                    raise LumenError("export_registry_unavailable") from None
        self.directory = check_directory_chain(state)
        if self.directory.is_relative_to(root):
            raise LumenError("export_state_inside_vault")
        self.path = self.directory / "export-registry.sqlite3"
        self.archives = self.directory / "packages"
        self.staging = self.directory / "staging"
        with directory_guard(self.directory):
            if create:
                if os.path.lexists(self.path):
                    raise LumenError("export_registry_exists")
                try:
                    fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    os.close(fd)
                    with self._connect(write=True) as connection:
                        connection.executescript(SCHEMA)
                    self.archives.mkdir()
                    self.staging.mkdir()
                except (OSError, sqlite3.Error):
                    # Preserve unexpected/partially initialized state for diagnosis.
                    raise LumenError("export_registry_unavailable") from None
            if not regular_file(self.path):
                raise LumenError("export_registry_missing_or_unsafe")
            self._check_existing()
            check_directory_chain(self.archives)
            check_directory_chain(self.staging)

    @classmethod
    def create(cls, state_directory, vault_root):
        return cls(state_directory, vault_root, create=True)

    @classmethod
    def open(cls, state_directory, vault_root):
        return cls(state_directory, vault_root)

    @contextmanager
    def _connect(self, *, write=False):
        connection = None
        try:
            connection = sqlite3.connect(self.path.as_uri() + ("?mode=rw" if write else "?mode=ro"),
                                         uri=True, timeout=2)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            with connection:
                yield connection
        except sqlite3.Error:
            raise LumenError("export_registry_unavailable") from None
        finally:
            if connection is not None:
                connection.close()

    def _check_existing(self):
        with self._connect() as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            forbidden = connection.execute("SELECT count(*) FROM sqlite_master WHERE type IN ('trigger','view')").fetchone()[0]
            expected = {"identities": tuple(Identity.__dataclass_fields__),
                        "exports": tuple(ExportRecord.__dataclass_fields__),
                        "events": ("id", "subject_id", "code", "timestamp")}
            if (tables != set(expected) or forbidden or connection.execute("PRAGMA user_version").fetchone()[0] != 1
                    or connection.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID
                    or any(tuple(row[1] for row in connection.execute(f"PRAGMA table_info({table})")) != columns
                           for table, columns in expected.items())):
                raise LumenError("unrecognized_export_registry")

    @contextmanager
    def locked(self):
        with directory_guard(self.directory, self.archives, self.staging), session_lock(self.directory):
            if not regular_file(self.path):
                raise LumenError("export_registry_missing_or_unsafe")
            yield

    def _event(self, connection, subject_id, code):
        if code not in EVENT_CODES:
            raise LumenError("invalid_export_event")
        connection.execute("INSERT INTO events(subject_id,code,timestamp) VALUES (?,?,?)", (subject_id, code, _now()))

    def identity_for(self, vault_id, relative_source) -> Identity | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM identities WHERE vault_id=? AND binding_key=?",
                                     (vault_id, _binding(relative_source))).fetchone()
        return Identity(**dict(row)) if row else None

    def identity(self, integration_id) -> Identity:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM identities WHERE integration_id=?", (integration_id,)).fetchone()
        if not row:
            raise LumenError("export_identity_missing")
        return Identity(**dict(row))

    def register(self, vault_id, relative_source, *, confirmed=False) -> Identity:
        if confirmed is not True:
            raise LumenError("identity_confirmation_required")
        if not isinstance(vault_id, str) or not HEX64.fullmatch(vault_id):
            raise LumenError("invalid_export_binding")
        key = _binding(relative_source)
        with self.locked():
            existing = self.identity_for(vault_id, relative_source)
            if existing:
                return existing
            identity = Identity("lumen_" + uuid.uuid4().hex, vault_id, key, relative_source)
            with self._connect(write=True) as connection:
                connection.execute("INSERT INTO identities VALUES (?,?,?,?)", tuple(identity.__dict__.values()))
                self._event(connection, identity.integration_id, "identity_registered")
            return identity

    def rebind(self, integration_id, vault_id, relative_source, *, confirmed=False):
        """Location checks and old-file absence are enforced by AtlasExporter."""
        if confirmed is not True:
            raise LumenError("identity_confirmation_required")
        key = _binding(relative_source)
        with self.locked():
            existing = self.identity(integration_id)
            if existing.vault_id != vault_id:
                raise LumenError("cross_vault_identity_rebind")
            occupant = self.identity_for(vault_id, relative_source)
            if occupant and occupant.integration_id != integration_id:
                raise LumenError("export_binding_occupied")
            if self.pending():
                raise LumenError("export_reconciliation_required")
            with self._connect(write=True) as connection:
                connection.execute("UPDATE identities SET binding_key=?,relative_source=? WHERE integration_id=?",
                                   (key, relative_source, integration_id))
                self._event(connection, integration_id, "identity_rebound")
        return self.identity(integration_id)

    def record(self, export_id) -> ExportRecord:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM exports WHERE id=?", (export_id,)).fetchone()
        if not row:
            raise LumenError("export_record_missing")
        return ExportRecord(**dict(row))

    def records(self) -> tuple[ExportRecord, ...]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM exports ORDER BY rowid").fetchall()
        return tuple(ExportRecord(**dict(row)) for row in rows)

    def pending(self):
        return tuple(row for row in self.records() if row.state == "pending")

    def archive_path(self, export_id):
        if not isinstance(export_id, str) or len(export_id) != 32 or any(c not in "0123456789abcdef" for c in export_id):
            raise LumenError("invalid_export_record_id")
        return self.archives / (export_id + ".lumen-atlas.json")

    def stage_path(self, export_id):
        return self.staging / (self.archive_path(export_id).stem + ".tmp")

    def _start(self, export_id, package, package_bytes):
        # Caller holds the OS session lock through publication and completion.
        self.archive_path(export_id)
        if self.pending():
            raise LumenError("export_reconciliation_required")
        if not INTEGRATION_ID.fullmatch(package.integration_id):
            raise LumenError("transfer_identity")
        self.identity(package.integration_id)
        record = ExportRecord(export_id, package.integration_id, package.source_sha256, package.comparison_sha256,
                              package.baseline_sha256, sha256(package_bytes).hexdigest(), len(package_bytes),
                              "pending", "unknown", None, _now(), None)
        with self._connect(write=True) as connection:
            connection.execute("INSERT INTO exports VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", tuple(record.__dict__.values()))
            self._event(connection, export_id, "export_pending")

    def _complete(self, export_id, *, recovered=False):
        with self._connect(write=True) as connection:
            changed = connection.execute("UPDATE exports SET state='prepared',error_code=NULL,finished_at=? WHERE id=? AND state='pending'",
                                         (_now(), export_id)).rowcount
            if changed != 1:
                raise LumenError("export_state_changed")
            self._event(connection, export_id, "export_recovered" if recovered else "export_prepared")

    def _fail(self, export_id, code):
        if code not in ("export_interrupted", "export_write_failed"):
            raise LumenError("invalid_export_event")
        with self._connect(write=True) as connection:
            connection.execute("UPDATE exports SET state='failed',error_code=?,finished_at=? WHERE id=? AND state='pending'",
                               (code, _now(), export_id))
            self._event(connection, export_id, code)
