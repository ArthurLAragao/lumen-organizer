"""Bootstrap pip locally and optionally download only PyYAML into .venv.

Run with .venv's Python. No global package installation. On this Windows
sandbox, mode-0700 temporary directories are inaccessible to the process;
setup directories inherit the workspace ACL instead. This adjustment is
confined to this setup process and the ignored .local/setup-temp directory.
"""

from pathlib import Path
import argparse
import os
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--download-pyyaml", action="store_true")
    args = parser.parse_args()
    if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
        parser.error("Run this tool with the project's .venv Python.")
    temp_root = ROOT / ".local" / "setup-temp"
    temp_root.mkdir(parents=True, exist_ok=True)
    os.environ["TEMP"] = os.environ["TMP"] = str(temp_root)
    import tempfile
    tempfile.tempdir = str(temp_root)

    def inherited_tempdir(suffix=None, prefix=None, dir=None):
        # Do not create anything in a caller-supplied external directory.
        directory = temp_root / ((prefix or "tmp") + uuid.uuid4().hex + (suffix or ""))
        directory.mkdir(mode=0o777)
        return str(directory)

    tempfile.mkdtemp = inherited_tempdir
    wheels = sorted((Path(sys.base_prefix) / "Lib" / "ensurepip" / "_bundled").glob("pip-*.whl"))
    if not wheels:
        raise SystemExit("The base Python distribution has no bundled pip wheel.")
    sys.path.insert(0, str(wheels[-1]))
    from pip._internal.cli.main import main as pip_main
    result = pip_main(["--isolated", "install", "--no-index", "--no-deps",
                       "--disable-pip-version-check", str(wheels[-1])])
    if result or not args.download_pyyaml:
        return result
    return pip_main(["--isolated", "install", "--no-deps", "--no-cache-dir",
                     "--disable-pip-version-check", "--only-binary=:all:",
                     "--index-url", "https://pypi.org/simple", "PyYAML==6.0.3"])


if __name__ == "__main__":
    sys.exit(main())
