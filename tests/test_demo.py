import importlib.util
from pathlib import Path
import unittest

from lumen_organizer.validation import validate_file
from .support import FictionalWorkspace, bounded_writes

spec = importlib.util.spec_from_file_location("fictional_demo", Path(__file__).resolve().parents[1] / "tools/create_demo.py")
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


class DemoTests(unittest.TestCase):
    def test_demo_is_unique_fictional_and_never_configures_app(self):
        with FictionalWorkspace() as w, bounded_writes(w.root):
            directory, vault, source = demo.create_demo(w.state)
            other, _, _ = demo.create_demo(w.state)
            self.assertNotEqual(directory, other)
            self.assertTrue(vault.is_relative_to(w.state))
            self.assertEqual(source.read_bytes(), demo.ROOT.joinpath("tests/fixtures/research-none.md").read_bytes())
            self.assertTrue(validate_file(source).valid)
            warning = validate_file(directory / "nota-com-avisos.md")
            self.assertTrue(warning.valid)
            self.assertTrue(warning.note.warnings)
            self.assertFalse(validate_file(directory / "nota-invalida.md").valid)
            self.assertFalse((w.state / "settings.json").exists())
            self.assertFalse((w.state / "history.sqlite3").exists())
            self.assertEqual(list(vault.rglob("*.md")), [])

