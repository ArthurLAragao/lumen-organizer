from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import unittest

from lumen_organizer.destinations import DestinationPolicy, FIXED, check_filename
from lumen_organizer.filesystem import directory_guard
from lumen_organizer.importer import Organizer
from lumen_organizer.models import LumenError
from .support import FictionalWorkspace, bounded_writes


class DestinationTests(unittest.TestCase):
    def setUp(self):
        self.workspace = FictionalWorkspace()
        self.w = self.workspace.__enter__()
        self.policy = DestinationPolicy(self.w.vault)

    def tearDown(self):
        self.workspace.__exit__()

    def test_all_fixed_mappings(self):
        for category, relative in FIXED.items():
            with self.subTest(category=category):
                self.assertEqual(self.policy.target(category, "fictional.md"), self.w.vault / relative / "fictional.md")

    def test_explicit_existing_academic_and_project_subfolders(self):
        self.assertEqual(self.policy.target("faculdade", "note.md", "Fictional Term/Fictional Subject").parent.name, "Fictional Subject")
        self.assertEqual(self.policy.target("projetos", "note.md", "Fictional Project").parent.name, "Fictional Project")
        for category in ("faculdade", "projetos"):
            with self.subTest(category=category), self.assertRaises(LumenError):
                self.policy.target(category, "note.md")

    def test_picker_returns_directory_names_only(self):
        (self.w.vault / "02 - Faculdade" / "private-filename.md").write_text("FICTIONAL - MUST NOT READ", encoding="utf-8")
        self.assertEqual(self.policy.list_subfolders("faculdade"), ("Fictional Term",))
        self.assertEqual(self.policy.list_subfolders("faculdade", "Fictional Term"), ("Fictional Term/Fictional Subject",))

    def test_traversal_absolute_unc_and_alternate_stream_paths_blocked(self):
        for path in ("../outside", "..\\outside", "Fictional Project/../../outside", "C:\\outside", "\\\\server\\share", "/outside", "Fictional Project:stream", ".", ""):
            with self.subTest(path=path), self.assertRaises(LumenError):
                self.policy.target("projetos", "note.md", path)

    def test_windows_filenames(self):
        for filename in ("CON.md", "CON.note.md", "LPT1.md", "COM¹.md", "note.md ", "note.md.", "../note.md", "C:\\note.md", "note.md:stream", "note?.md", "note.txt", "note\x00.md"):
            with self.subTest(filename=filename), self.assertRaises(LumenError):
                check_filename(filename)
        self.assertEqual(check_filename("Árvore fictícia.MD"), "Árvore fictícia.MD")

    def test_invalid_categories_and_missing_folders_do_not_create_directories(self):
        for category, folder in (("invalid", None), ("projetos", "Missing Project"), ("aws-cloud", "arbitrary")):
            with self.subTest(category=category), self.assertRaises(LumenError):
                self.policy.target(category, "note.md", folder)
        self.assertFalse((self.w.vault / "03 - Projetos" / "Missing Project").exists())

    def test_configurable_root_and_invalid_settings(self):
        settings = self.w.root / "settings.local.json"
        settings.write_text(json.dumps({"vault_root": str(self.w.vault)}), encoding="utf-8")
        self.assertEqual(DestinationPolicy.from_settings(settings).root, self.w.vault)
        settings.write_text('{"vault_root": "relative"}', encoding="utf-8")
        with self.assertRaises(LumenError):
            DestinationPolicy.from_settings(settings)

    def test_recorded_destinations_cannot_escape_or_change_category(self):
        for category, relative in (("aws-cloud", "03 - Projetos/Fictional Project/x.md"),
                                   ("projetos", "../outside/x.md"),
                                   ("projetos", "03 - Projetos/x.md")):
            with self.subTest(relative=relative), self.assertRaises(LumenError):
                self.policy.recorded_target(category, relative)

    @unittest.skipUnless(os.name == "nt", "Native Windows directory guard")
    def test_directory_guard_prevents_ancestor_rename(self):
        parent = self.policy.folder("projetos", "Fictional Project")
        alternative = parent.with_name("Renamed Fictional Project")
        with directory_guard(parent), self.assertRaises(OSError):
            parent.rename(alternative)
        # Verify the failure was actually caused by the held guard.
        parent.rename(alternative)
        alternative.rename(parent)

    @unittest.skipUnless(os.name == "nt", "Windows junction test")
    def test_junction_destination_and_state_rejected(self):
        outside = self.w.root / "FictionalOutside"
        outside.mkdir()
        junction = self.w.vault / "03 - Projetos" / "Junction Project"
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(outside)], capture_output=True, text=True)
        if result.returncode:
            self.skipTest("This environment cannot create a Windows junction.")
        try:
            with self.assertRaises(LumenError):
                self.policy.target("projetos", "note.md", "Junction Project")
            self.assertNotIn("Junction Project", self.policy.list_subfolders("projetos"))
        finally:
            junction.rmdir()  # Remove only the junction, not the referenced directory.
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(self.w.state), str(outside)], capture_output=True, text=True)
        if result.returncode:
            self.skipTest("This environment cannot create a Windows state junction.")
        try:
            with self.assertRaises(LumenError):
                Organizer(self.policy, self.w.state)
            self.assertEqual(list(outside.iterdir()), [])
        finally:
            self.w.state.rmdir()

    def test_state_inside_vault_rejected_before_any_write(self):
        with bounded_writes(self.w.root), self.assertRaises(LumenError) as error:
            Organizer(self.policy, self.w.vault / ".local")
        self.assertEqual(error.exception.code, "state_inside_vault")
        self.assertFalse((self.w.vault / ".local").exists())
