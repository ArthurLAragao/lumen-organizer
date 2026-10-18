"""Immutable snapshots and structured results; no note content in diagnostics."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    message: str
    field: str | None = None
    line: int | None = None


@dataclass(frozen=True)
class ValidatedNote:
    source: Path = field(repr=False)
    data: bytes = field(repr=False)
    fingerprint: str
    metadata: Mapping[str, object] = field(repr=False)
    warnings: tuple[Issue, ...]


@dataclass(frozen=True)
class ValidationResult:
    note: ValidatedNote | None
    issues: tuple[Issue, ...]

    @property
    def valid(self) -> bool:
        return self.note is not None


@dataclass(frozen=True)
class ImportPlan:
    note: ValidatedNote
    category: str
    subfolder: str | None
    filename: str
    destination: Path
    allow_repeat: bool = False


@dataclass(frozen=True)
class ImportResult:
    outcome: str
    code: str
    operation_id: str | None = None
    destination: Path | None = None


@dataclass(frozen=True)
class Operation:
    id: str
    vault_id: str
    fingerprint: str
    category: str
    relative_destination: str
    state: str
    error_code: str | None
    started_at: str
    finished_at: str | None


class LumenError(Exception):
    """Only fixed application codes, never raw parser/OS exception messages."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)
