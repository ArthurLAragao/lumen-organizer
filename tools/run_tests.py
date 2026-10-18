"""Run fictional tests without installing the project or touching a real vault."""

from pathlib import Path
import os
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
# Some Windows environments configure TEMP outside the writable workspace.
# All test-created files are confined to an ignored local directory.
TEST_TEMP = ROOT / ".local" / "test-temp"
TEST_TEMP.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(TEST_TEMP)
os.environ["TEMP"] = str(TEST_TEMP)
os.environ["TMP"] = str(TEST_TEMP)

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(f"RESULT: {result.testsRun} run; {len(result.failures)} failures; "
          f"{len(result.errors)} errors; {len(result.skipped)} skipped")
    sys.exit(0 if result.wasSuccessful() else 1)
