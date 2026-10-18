"""Explicit local configuration storage; no personal path defaults."""

import json
import os
from pathlib import Path
import uuid

from .destinations import DestinationPolicy, check_directory_chain
from .filesystem import directory_guard, regular_file
from .models import LumenError


class SettingsStore:
    def __init__(self, local_directory: Path):
        self.directory = Path(local_directory).absolute()
        if self.directory.name != ".local":
            raise LumenError("settings_location")
        self.path = self.directory / "settings.json"

    def load(self) -> DestinationPolicy | None:
        if not os.path.lexists(self.path):
            return None
        check_directory_chain(self.directory)
        if not regular_file(self.path):
            raise LumenError("invalid_settings")
        return DestinationPolicy.from_settings(self.path)

    def save(self, policy: DestinationPolicy) -> None:
        parent = check_directory_chain(self.directory.parent)
        if self.directory.is_relative_to(policy.root):
            raise LumenError("state_inside_vault")
        with directory_guard(parent):
            self.directory.mkdir(exist_ok=True)
            check_directory_chain(self.directory)
            with directory_guard(self.directory):
                if os.path.lexists(self.path):
                    if not regular_file(self.path):
                        raise LumenError("invalid_settings")
                    try:
                        previous = json.loads(self.path.read_text(encoding="utf-8"))
                    except (OSError, UnicodeError, ValueError):
                        raise LumenError("invalid_settings") from None
                    # Recognize the configuration before explicitly replacing
                    # it. A deleted old vault does not prevent reconfiguration.
                    if (not isinstance(previous, dict) or set(previous) != {"vault_root"}
                            or not isinstance(previous["vault_root"], str)):
                        raise LumenError("invalid_settings")
                staged = self.directory / ("settings-" + uuid.uuid4().hex + ".tmp")
                try:
                    with staged.open("x", encoding="utf-8", newline="\n") as stream:
                        json.dump({"vault_root": str(policy.root)}, stream, ensure_ascii=False, indent=2)
                        stream.write("\n")
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(staged, self.path)
                except OSError:
                    raise LumenError("settings_unavailable") from None
                finally:
                    if regular_file(staged):
                        staged.unlink()
