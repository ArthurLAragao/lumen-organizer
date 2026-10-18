"""Desktop launcher and read-only developer commands; no import CLI."""

import argparse
import importlib.metadata
import json
import platform
from pathlib import Path

from .validation import validate_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Lumen Organizer")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check-environment")
    commands.add_parser("gui", help="Abrir a interface desktop em português")
    validator = commands.add_parser("validate")
    validator.add_argument("markdown_file")
    args = parser.parse_args()
    if args.command == "gui":
        from .ui import launch
        launch(Path(__file__).resolve().parents[2] / ".local")
        return 0
    if args.command == "check-environment":
        import tkinter
        print(json.dumps({"python": platform.python_version(), "pyyaml": importlib.metadata.version("PyYAML"),
                          "tcl": tkinter.Tcl().call("info", "patchlevel"), "platform": platform.system()}, indent=2))
        return 0
    result = validate_file(args.markdown_file)
    print(json.dumps({"valid": result.valid, "issues": [issue.__dict__ for issue in result.issues]}, ensure_ascii=False, indent=2))
    return 0 if result.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
