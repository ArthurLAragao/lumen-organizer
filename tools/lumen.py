"""Desktop launcher and read-only diagnostics without installing the package."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from lumen_organizer.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
