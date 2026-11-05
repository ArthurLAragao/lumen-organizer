from pathlib import Path
import tkinter as tk
import unittest
from unittest.mock import patch

from tests.support import FictionalWorkspace
from lumen_organizer.agent_context import initialize, append_entry, build_context
from lumen_organizer.capture_ui import readable_note
from lumen_organizer.workspace_ui import create_workspace


class WorkspaceTests(unittest.TestCase):
    def test_context_preserves_existing_profile_and_bounds_sources(self):
        with FictionalWorkspace() as workspace:
            root = workspace.root / 'context'
            initialize(root)
            profile = root / 'Perfil.md'
            profile.write_text('Preferência fictícia: exemplos curtos.', encoding='utf-8')
            initialize(root)
            entry = append_entry('Hoje pratiquei filas. Registro fictício.', root)
            self.assertTrue(entry.is_relative_to(root))
            bundle = build_context(root)
            self.assertIn('exemplos curtos', bundle)
            self.assertIn('Hoje pratiquei filas', bundle)
            self.assertLess(len(bundle), 42_000)
            with self.assertRaises(ValueError):
                append_entry('', root)

    def test_reading_view_does_not_expose_yaml_or_modify_source(self):
        source = '---\nstatus: inbox\nlumen_export: false\n---\n# Teste\n\n## Resumo\n\n**Conteúdo** de teste.'
        displayed = readable_note(source)
        self.assertNotIn('lumen_export', displayed)
        self.assertIn('Resumo', displayed)
        self.assertIn('Conteúdo de teste', displayed)
        self.assertIn('lumen_export: false', source)

    def test_one_window_contains_capture_organizer_and_context(self):
        with FictionalWorkspace() as workspace, patch('lumen_organizer.capture_ui.start_bridge', return_value=None):
            root = tk.Tk()
            app = create_workspace(root, workspace.root / '.local', load_settings=False)
            root.update()
            try:
                self.assertEqual(len(app.workspace_notebook.tabs()), 4)
                self.assertTrue(app.capture_window.embedded)
                self.assertFalse(any(isinstance(child, tk.Toplevel) for child in root.winfo_children()))
                self.assertEqual(app.workspace_notebook.select(), str(app.capture_window.window))
                self.assertEqual(app.root.title(), 'Lumen · Seu espaço de conhecimento')
            finally:
                app.close_requested()
