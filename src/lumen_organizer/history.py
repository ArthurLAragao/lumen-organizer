"""Minimal local SQLite journal; it contains no bodies or YAML excerpts."""

from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
import os
from pathlib import Path
import re
import sqlite3
import uuid

from .destinations import CATEGORIES, check_directory_chain
from .filesystem import directory_guard, regular_file
from .models import LumenError, Operation


class AuditCode(str, Enum):
    PENDING = "import_pending"
    SUCCESS = "import_succeeded"
    RECOVERED = "reconciled_saved_file"
    DUPLICATE = "already_imported"
    SOURCE_CHANGED = "source_changed"
    COLLISION = "destination_collision"
    PERMISSION = "permission_denied"
    DISK_FULL = "disk_full"
    WRITE_FAILED = "write_failed"
    UNSAFE_DESTINATION = "unsafe_destination"
    VERIFY_FAILED = "saved_verification_failed"
    INTERRUPTED = "interrupted_before_save"
    RECOVERY_CONFLICT = "recovery_destination_conflict"


SCHEMA = """
CREATE TABLE operations (
    id TEXT PRIMARY KEY,
    vault_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    category TEXT NOT NULL,
    relative_destination TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('pending', 'succeeded', 'failed')),
    error_code TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT
);
CREATE INDEX imports_by_fingerprint ON operations(vault_id, fingerprint, state);
CREATE TABLE events (
    id INTEGER PRIMARY KEY,
    operation_id TEXT,
    code TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
PRAGMA user_version = 1;
"""
HEX32 = re.compile(r"[0-9a-f]{32}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class History:
    def __init__(self, state_directory: str | Path, vault_root: Path):
        state = Path(state_directory).absolute()
        parent = check_directory_chain(state.parent)
        state = parent / state.name
        if state.is_relative_to(vault_root):
            raise LumenError("state_inside_vault")
        with directory_guard(parent):
            try:
                state.mkdir(exist_ok=True)
                self.directory = check_directory_chain(state)
                self.staging = state / "staging"
                self.staging.mkdir(exist_ok=True)
                check_directory_chain(self.staging)
            except OSError:
                raise LumenError("state_unavailable") from None
        self.path = state / "history.sqlite3"
        with directory_guard(state):
            if os.path.lexists(self.path):
                if not regular_file(self.path):
                    raise LumenError("unrecognized_history")
                self._check_existing()
            else:
                try:
                    # Do not take over an unexpected file that appears here.
                    fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    os.close(fd)
                    with self._connect() as connection:
                        connection.executescript(SCHEMA)
                except (OSError, sqlite3.Error):
                    raise LumenError("history_unavailable") from None

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=2)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _check_existing(self):
        try:
            connection = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=2)
            try:
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                forbidden = connection.execute("SELECT count(*) FROM sqlite_master WHERE type IN ('trigger', 'view')").fetchone()[0]
                columns = tuple(row[1] for row in connection.execute("PRAGMA table_info(operations)"))
                event_columns = tuple(row[1] for row in connection.execute("PRAGMA table_info(events)"))
                if (version != 1 or tables != {"operations", "events"} or forbidden
                        or columns != tuple(Operation.__dataclass_fields__)
                        or event_columns != ("id", "operation_id", "code", "timestamp")):
                    raise LumenError("unrecognized_history")
            finally:
                connection.close()
        except sqlite3.Error:
            raise LumenError("unrecognized_history") from None

    def _event(self, connection, code: AuditCode, operation_id: str | None = None):
        if not isinstance(code, AuditCode):
            raise LumenError("invalid_audit_code")
        connection.execute("INSERT INTO events(operation_id, code, timestamp) VALUES (?, ?, ?)",
                           (operation_id, code.value, _now()))

    def audit(self, code: AuditCode):
        try:
            with self._connect() as connection:
                self._event(connection, code)
        except sqlite3.Error:
            raise LumenError("history_unavailable") from None

    def start(self, vault_id: str, fingerprint: str, category: str, relative_destination: str) -> str:
        if not HEX64.fullmatch(vault_id) or not HEX64.fullmatch(fingerprint) or category not in CATEGORIES:
            raise LumenError("invalid_history_record")
        operation_id = uuid.uuid4().hex
        try:
            with self._connect() as connection:
                connection.execute("INSERT INTO operations VALUES (?, ?, ?, ?, ?, 'pending', NULL, ?, NULL)",
                                   (operation_id, vault_id, fingerprint, category, relative_destination, _now()))
                self._event(connection, AuditCode.PENDING, operation_id)
        except sqlite3.Error:
            raise LumenError("history_unavailable") from None
        return operation_id

    def complete(self, operation_id: str, recovered: bool = False):
        try:
            with self._connect() as connection:
                result = connection.execute("UPDATE operations SET state='succeeded', error_code=NULL, finished_at=? WHERE id=? AND state='pending'",
                                            (_now(), operation_id))
                if result.rowcount != 1:
                    raise LumenError("invalid_history_transition")
                self._event(connection, AuditCode.RECOVERED if recovered else AuditCode.SUCCESS, operation_id)
        except sqlite3.Error:
            raise LumenError("history_unavailable") from None

    def fail(self, operation_id: str, code: AuditCode):
        if not isinstance(code, AuditCode):
            raise LumenError("invalid_audit_code")
        try:
            with self._connect() as connection:
                result = connection.execute("UPDATE operations SET state='failed', error_code=?, finished_at=? WHERE id=? AND state='pending'",
                                            (code.value, _now(), operation_id))
                if result.rowcount != 1:
                    raise LumenError("invalid_history_transition")
                self._event(connection, code, operation_id)
        except sqlite3.Error:
            raise LumenError("history_unavailable") from None

    def _read(self, query: str, parameters: tuple) -> tuple[Operation, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(query, parameters).fetchall()
        except sqlite3.Error:
            raise LumenError("history_unavailable") from None
        operations = []
        for row in rows:
            operation = Operation(*row)
            if (not HEX32.fullmatch(operation.id) or not HEX64.fullmatch(operation.vault_id)
                    or not HEX64.fullmatch(operation.fingerprint) or operation.category not in CATEGORIES
                    or operation.state not in ("pending", "failed", "succeeded")):
                raise LumenError("invalid_history_record")
            operations.append(operation)
        return tuple(operations)

    def previous(self, vault_id: str, fingerprint: str) -> Operation | None:
        operations = self._read("SELECT * FROM operations WHERE vault_id=? AND fingerprint=? AND state='succeeded' ORDER BY started_at DESC LIMIT 1",
                                (vault_id, fingerprint))
        return operations[0] if operations else None

    def pending(self, vault_id: str) -> tuple[Operation, ...]:
        return self._read("SELECT * FROM operations WHERE vault_id=? AND state='pending' ORDER BY started_at", (vault_id,))

    def operations(self) -> tuple[Operation, ...]:
        return self._read("SELECT * FROM operations ORDER BY started_at", ())
