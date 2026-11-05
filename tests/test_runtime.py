from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.request import urlopen
from urllib.error import HTTPError

from lumen_organizer.applications import ApplicationCatalog, normalize
from lumen_organizer.capture import CaptureError
from lumen_organizer.runtime import AtlasHandler


class RuntimeTests(unittest.TestCase):
    def test_portuguese_alias_for_english_windows_app(self):
        with patch('pathlib.Path.is_dir', return_value=False), patch('pathlib.Path.is_file', return_value=False), patch('subprocess.run', return_value=SimpleNamespace(stdout='[{"Name":"Calculator","AppID":"Microsoft.Calculator!App"}]')):
            catalog = ApplicationCatalog(Path('.'))
        self.assertEqual(catalog.entries[catalog.resolve('abrir calculadora')]['name'], 'Calculator')

    def test_atlas_deep_links_reload_and_missing_assets(self):
        with TemporaryDirectory() as directory:
            atlas = Path(directory)
            (atlas / 'dist/assets').mkdir(parents=True)
            (atlas / 'dist/index.html').write_text('<!doctype html><title>Atlas</title>', encoding='utf-8')
            (atlas / 'dist/assets/test.js').write_text('console.log("Atlas")', encoding='utf-8')
            with patch('lumen_organizer.runtime.ATLAS', atlas):
                server = ThreadingHTTPServer(('127.0.0.1', 0), AtlasHandler)
                Thread(target=server.serve_forever, daemon=True).start()
                base = f'http://127.0.0.1:{server.server_port}'
                try:
                    for route in ('/', '/tarefas', '/estudos', '/notas'):
                        with urlopen(base + route) as response:
                            self.assertEqual(response.status, 200)
                            self.assertIn('Atlas', response.read().decode())
                    with urlopen(base + '/assets/test.js') as response:
                        self.assertIn('javascript', response.headers['Content-Type'])
                    with self.assertRaises(HTTPError) as error:
                        urlopen(base + '/assets/antigo.js')
                    self.assertEqual(error.exception.code, 404)
                finally:
                    server.shutdown(); server.server_close()

    def test_app_text_is_resolved_to_catalog_entry_never_a_shell(self):
        catalog = ApplicationCatalog.__new__(ApplicationCatalog)
        catalog.root = Path('.')
        catalog.entries = {'cursor':dict(id='cursor', name='Cursor', target='C:/Programs/Cursor.lnk',kind='file',aliases=[])}
        self.assertEqual(catalog.resolve('Abra o Cursor.'), 'cursor')
        with patch('os.startfile') as launch:
            catalog.open(command='abrir Cursor')
            launch.assert_called_once_with('C:/Programs/Cursor.lnk')
        for command in ('abrir Cursor e apagar arquivos', 'powershell -Command qualquer-coisa', 'abrir ../../arquivo'):
            with self.subTest(command=command), self.assertRaises(CaptureError):
                catalog.resolve(command)
        self.assertEqual(normalize('  CÓDIGO! '), 'codigo')


if __name__ == '__main__':
    unittest.main()
