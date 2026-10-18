"""Windows directory guards and no-replace publication; no shell operations."""

from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import stat

from .destinations import check_directory_chain
from .models import LumenError


@contextmanager
def directory_guard(*directories: Path):
    """Pin ancestor directories against rename/deletion on Windows.

    Omitting FILE_SHARE_DELETE makes an ancestor swap fail while its handle
    is held. Open reparse points themselves and reject them, rather than
    following them. This supplements path checks at confirmation/commit.
    """
    if os.name != "nt":
        raise LumenError("unsupported_import_platform")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.GetFileInformationByHandleEx.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.GetFileInformationByHandleEx.restype = wintypes.BOOL
    kernel.GetFinalPathNameByHandleW.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
    kernel.GetFinalPathNameByHandleW.restype = wintypes.DWORD

    class AttributeTag(ctypes.Structure):
        _fields_ = [("attributes", wintypes.DWORD), ("tag", wintypes.DWORD)]

    handles, seen = [], set()
    try:
        for directory in directories:
            check_directory_chain(directory)
            for item in reversed((directory, *directory.parents)):
                identity = os.path.normcase(str(item))
                if identity in seen:
                    continue
                # FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES. Attribute-only
                # handles do not participate in deletion sharing checks.
                # Share read/write; OPEN_EXISTING;
                # FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT.
                handle = kernel.CreateFileW(str(item), 0x81, 3, None, 3, 0x02200000, None)
                if handle == ctypes.c_void_p(-1).value:
                    raise LumenError("directory_lock_failed")
                handles.append(handle)
                info = AttributeTag()
                if not kernel.GetFileInformationByHandleEx(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
                    raise LumenError("directory_lock_failed")
                if info.attributes & 0x400 or not info.attributes & 0x10:
                    raise LumenError("linked_directory_forbidden")
                buffer = ctypes.create_unicode_buffer(32768)
                length = kernel.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
                if not length or length >= len(buffer):
                    raise LumenError("directory_lock_failed")
                final = buffer.value
                if final.startswith("\\\\?\\"):
                    final = final[4:]
                if os.path.normcase(os.path.normpath(final)) != os.path.normcase(os.path.normpath(str(item))):
                    raise LumenError("directory_changed")
                seen.add(identity)
        yield
    finally:
        for handle in reversed(handles):
            kernel.CloseHandle(handle)


def publish_no_replace(staged: Path, destination: Path) -> None:
    if os.name != "nt":
        raise LumenError("unsupported_import_platform")
    # Windows rename refuses existing destinations. Never use replace() or
    # a check-then-copy operation here; both could overwrite a concurrent file.
    os.rename(staged, destination)


def regular_file(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    return stat.S_ISREG(info.st_mode) and not (getattr(info, "st_file_attributes", 0) & 0x400)


@contextmanager
def session_lock(state_directory: Path):
    """An OS byte lock is released on crash; no stale lock-file deletion."""
    if os.name != "nt":
        raise LumenError("unsupported_import_platform")
    import msvcrt
    path = state_directory / "import.lock"
    if os.path.lexists(path) and not regular_file(path):
        raise LumenError("invalid_state_lock")
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_BINARY, 0o600)
    acquired = False
    try:
        if os.fstat(fd).st_size == 0:
            os.write(fd, b"\x00")
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            acquired = True
        except OSError:
            raise LumenError("state_busy") from None
        yield
    finally:
        if acquired:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        os.close(fd)
