"""Run fictional tests without installing the project or touching a real vault."""

from pathlib import Path
import os
import sys
import tempfile
import unittest

# The write-boundary audit also observes lazy codec imports. Python must not try
# creating standard-library bytecode outside a fictional test's directory.
sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

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
    if '--headless' in sys.argv:
        # Hosted Windows agents have a fixed 1024x768 non-interactive desktop.
        # Keep all desktop assertions in the default run and report explicit skips here.
        desktop_classes = ('tests.test_ui.TkWidgetTests.', 'tests.test_export_workflow.ExportWidgetTests.')
        desktop_methods = {
            'tests.test_capture.CaptureTests.test_capture_desk_opens_without_network_and_closes_cleanly',
            'tests.test_workspace.WorkspaceTests.test_one_window_contains_capture_organizer_and_context',
        }
        def mark_desktop(current):
            for case in current:
                if isinstance(case, unittest.TestSuite):
                    mark_desktop(case)
                elif case.id().startswith(desktop_classes) or case.id() in desktop_methods:
                    method = getattr(type(case), case._testMethodName)
                    setattr(type(case), case._testMethodName, unittest.skip(
                        'Interactive Tk display required; covered by the full local suite.')(method))
        mark_desktop(suite)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(f"RESULT: {result.testsRun} run; {len(result.failures)} failures; "
          f"{len(result.errors)} errors; {len(result.skipped)} skipped")
    sys.exit(0 if result.wasSuccessful() else 1)
