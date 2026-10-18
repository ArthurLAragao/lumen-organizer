"""Fictional data and temporary workspace helpers, never real configuration."""

from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import os
import shutil
import sys
from urllib.parse import unquote, urlsplit
import uuid

from lumen_organizer.destinations import FIXED

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "research-none.md"
AUDIT_ROOT = ContextVar("fictional_test_root", default=None)


def _allowed(path, root):
    if isinstance(path, int):
        return  # File descriptor opened through a previously checked path.
    text = os.fsdecode(path)
    if text.startswith("file:"):
        text = unquote(urlsplit(text).path)
        if os.name == "nt" and text.startswith("/"):
            text = text[1:]
    if not Path(text).absolute().is_relative_to(root):
        raise AssertionError("Core attempted a write outside the fictional test workspace.")


def _audit(event, args):
    root = AUDIT_ROOT.get()
    if root is None:
        return
    if event == "open" and args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
        _allowed(args[0], root)
    elif event == "sqlite3.connect":
        _allowed(args[0], root)
    elif event in ("os.mkdir", "os.remove", "os.rmdir", "os.chmod"):
        _allowed(args[0], root)
    elif event in ("os.rename", "os.link"):
        _allowed(args[0], root)
        _allowed(args[1], root)


sys.addaudithook(_audit)


@contextmanager
def bounded_writes(root):
    token = AUDIT_ROOT.set(root)
    try:
        yield
    finally:
        AUDIT_ROOT.reset(token)


class FictionalWorkspace:
    def __enter__(self):
        base = ROOT / ".local" / "test-temp"
        base.mkdir(parents=True, exist_ok=True)
        self.root = base / uuid.uuid4().hex
        # Inherit the workspace ACL; mode 0700 is inaccessible in this sandbox.
        self.root.mkdir(mode=0o777)
        self.vault = self.root / "FictionalVault"
        self.vault.mkdir()
        for folder in FIXED.values():
            (self.vault / folder).mkdir(parents=True, exist_ok=True)
        (self.vault / "02 - Faculdade" / "Fictional Term" / "Fictional Subject").mkdir(parents=True)
        (self.vault / "03 - Projetos" / "Fictional Project").mkdir(parents=True)
        self.source = self.root / "fictional.md"
        self.source.write_bytes(FIXTURE.read_bytes())
        self.state = self.root / ".local"
        return self

    def __exit__(self, *args):
        if self.root.parent != ROOT / ".local" / "test-temp":
            raise AssertionError("Unsafe test cleanup target.")
        shutil.rmtree(self.root)


def changed_note(base: bytes, key: str, value: str) -> bytes:
    lines = base.decode("utf-8").splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.startswith(key + ":"):
            lines[index] = f"{key}: {value}\n"
            break
    return "".join(lines).encode("utf-8")
