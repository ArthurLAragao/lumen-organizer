"""Existing-folder allowlist. Note metadata never controls filesystem paths."""

from hashlib import sha256
import json
import os
from pathlib import Path, PureWindowsPath
import re
import stat

from .models import LumenError

FIXED = {
    "aws-cloud": "01 - Conhecimento/AWS e Cloud",
    "linux-devops": "01 - Conhecimento/Linux e DevOps",
    "programacao": "01 - Conhecimento/Programação",
    "ia": "01 - Conhecimento/Inteligência Artificial",
    "seguranca": "01 - Conhecimento/Segurança",
    "ferramentas": "01 - Conhecimento/Ferramentas e Workflow",
    "indefinido": "00 - Inbox/Pesquisas",
}
CHOOSABLE = {"faculdade": "02 - Faculdade", "projetos": "03 - Projetos"}
CATEGORIES = frozenset(FIXED) | frozenset(CHOOSABLE)
FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED = re.compile(r"(?:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])\Z", re.I)


def check_filename(filename: str) -> str:
    if (not isinstance(filename, str) or not filename or len(filename) > 180
            or FORBIDDEN.search(filename) or filename.endswith((" ", "."))
            or RESERVED.fullmatch(filename.split(".")[0].rstrip(" "))
            or Path(filename).suffix.casefold() != ".md"):
        raise LumenError("invalid_filename")
    return filename


def relative_parts(value: str) -> tuple[str, ...]:
    if not isinstance(value, str) or not value or PureWindowsPath(value).drive or value.startswith(("/", "\\")):
        raise LumenError("invalid_relative_path")
    parts = tuple(value.replace("\\", "/").split("/"))
    if any(part in ("", ".", "..") or FORBIDDEN.search(part)
           or part.endswith((" ", ".")) or RESERVED.fullmatch(part.split(".")[0].rstrip(" "))
           for part in parts):
        raise LumenError("invalid_relative_path")
    return parts


def check_directory_chain(directory: Path) -> Path:
    """No links/reparse points, including ancestors of the configured vault."""
    directory = Path(directory).absolute()
    if os.name == "nt" and directory.drive.startswith("\\"):
        raise LumenError("network_path_forbidden")
    try:
        for item in reversed((directory, *directory.parents)):
            info = item.lstat()
            if not stat.S_ISDIR(info.st_mode):
                raise LumenError("directory_required")
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise LumenError("linked_directory_forbidden")
        return directory.resolve(strict=True)
    except OSError:
        raise LumenError("directory_unavailable") from None


class DestinationPolicy:
    def __init__(self, vault_root: str | Path):
        path = Path(vault_root)
        if not path.is_absolute():
            raise LumenError("absolute_vault_required")
        self.root = check_directory_chain(path)
        self.vault_id = sha256(os.path.normcase(str(self.root)).encode("utf-8")).hexdigest()

    @classmethod
    def from_settings(cls, settings: str | Path) -> "DestinationPolicy":
        try:
            data = json.loads(Path(settings).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            raise LumenError("invalid_settings") from None
        if not isinstance(data, dict) or set(data) != {"vault_root"} or not isinstance(data["vault_root"], str):
            raise LumenError("invalid_settings")
        return cls(data["vault_root"])

    def folder(self, category: str, subfolder: str | None = None) -> Path:
        if not isinstance(category, str):
            raise LumenError("unknown_category")
        if category in FIXED:
            if subfolder is not None:
                raise LumenError("fixed_category_subfolder")
            parent = self.root.joinpath(*FIXED[category].split("/"))
        elif category in CHOOSABLE:
            if subfolder is None:
                raise LumenError("explicit_subfolder_required")
            parent = self.root.joinpath(*CHOOSABLE[category].split("/"), *relative_parts(subfolder))
        else:
            raise LumenError("unknown_category")
        checked = check_directory_chain(parent)
        if not checked.is_relative_to(self.root):
            raise LumenError("outside_vault")
        return checked

    def target(self, category: str, filename: str, subfolder: str | None = None) -> Path:
        return self.folder(category, subfolder) / check_filename(filename)

    def suggest_target(self, category: str, filename: str, subfolder: str | None = None) -> Path:
        target = self.target(category, filename, subfolder)
        if not os.path.lexists(target):
            return target
        for index in range(2, 10000):
            candidate = self.target(category, f"{target.stem}-{index}{target.suffix}", subfolder)
            if not os.path.lexists(candidate):
                return candidate
        raise LumenError("collision_limit")

    def list_subfolders(self, category: str, parent: str | None = None) -> tuple[str, ...]:
        """One level of directory names only; never read files or follow links."""
        if category not in CHOOSABLE:
            raise LumenError("category_has_no_folder_picker")
        base = self.root / CHOOSABLE[category]
        folder = self.folder(category, parent) if parent is not None else check_directory_chain(base)
        results = []
        try:
            for child in folder.iterdir():
                try:
                    check_directory_chain(child)
                except LumenError:
                    continue
                results.append(child.relative_to(base).as_posix())
        except OSError:
            raise LumenError("directory_unavailable") from None
        return tuple(sorted(results, key=str.casefold))

    def recorded_target(self, category: str, relative_destination: str) -> Path:
        parts = relative_parts(relative_destination)
        if len(parts) < 2:
            raise LumenError("invalid_history_destination")
        if category in FIXED:
            prefix = tuple(FIXED[category].split("/"))
            if parts[:-1] != prefix:
                raise LumenError("invalid_history_destination")
            return self.target(category, parts[-1])
        if category in CHOOSABLE and parts[0] == CHOOSABLE[category] and len(parts) >= 3:
            return self.target(category, parts[-1], "/".join(parts[1:-1]))
        raise LumenError("invalid_history_destination")
