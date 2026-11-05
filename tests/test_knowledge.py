import base64
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
import time
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from lumen_organizer.capture import CaptureError
from lumen_organizer.knowledge import KnowledgeInbox, validate_folder
from lumen_organizer.runtime import AtlasHandler, make_handler
from lumen_organizer.sources import extract_file, public_url, ArticleText

SUMMARY = dict(resumo='Resumo factual de uma fonte fictícia.', explicacao='Conceito explicado.', aplicacao='Proponha um exercício.', revisao='Cinco perguntas de revisão.', atencao='Verifique a fonte.')


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.inbox = KnowledgeInbox(self.root / 'jobs', summarize=lambda *_: SUMMARY.copy(),
                                    extract=lambda source, *_: 'Texto original: ' + source,
                                    export_root=self.root / 'vault')

    def tearDown(self):
        self.inbox.executor.shutdown(wait=True)
        self.tmp.cleanup()

    def wait(self, identifier, target='review'):
        limit = time.monotonic() + 5
        while time.monotonic() < limit:
            job = self.inbox.get(identifier)
            if job['status'] == target:
                return job
            if job['status'] == 'failed' and target != 'failed':
                self.fail(job.get('error'))
            time.sleep(.01)
        self.fail('Timeout: ' + str(self.inbox.get(identifier)))

    def create(self, destination='obsidian'):
        job = self.inbox.create('Uma fonte fictícia', 'idea', destination, {})
        return self.wait(job['id'])

    def test_real_file_export_and_restart_persistence(self):
        job = self.create()
        job['note']['title'] = 'Nota revisada'
        self.inbox.edit(job['id'], job['note'], 'obsidian')
        self.inbox.publish(job['id'])
        done = self.wait(job['id'], 'completed')
        target = Path(done['receipts']['obsidian']['path'])
        self.assertIn('Nota revisada', target.read_text(encoding='utf-8'))
        self.inbox.publish(job['id'])
        self.assertEqual(len(list(self.inbox.export_root.rglob('*.md'))), 1)
        repeated = self.inbox.create('Uma fonte fictícia', 'idea', 'obsidian', {})
        self.assertEqual(repeated['id'], job['id'])
        restored = KnowledgeInbox(self.root / 'jobs', export_root=self.inbox.export_root)
        try:
            self.assertEqual(restored.get(job['id'])['status'], 'completed')
        finally:
            restored.close()

    def test_cancel_retained_during_running_summary(self):
        started, release = Event(), Event()
        def summarize(*_):
            started.set(); release.wait(2); return SUMMARY.copy()
        self.inbox.summarize = summarize
        job = self.inbox.create('Exemplo', 'idea', 'obsidian', {})
        self.assertTrue(started.wait(2))
        self.inbox.cancel(job['id'])
        with self.assertRaises(CaptureError):
            self.inbox.retry(job['id'])
        release.set()
        self.inbox.futures[job['id']].result(3)
        self.assertEqual(self.inbox.get(job['id'])['status'], 'cancelled')
        self.assertFalse(self.inbox.export_root.exists())

    def test_partial_export_preserved_and_uncertain_notion_blocks_retry(self):
        def fail(*_, **__):
            raise CaptureError('Entrega incerta.')
        self.inbox.publisher = fail
        job = self.create('both')
        self.inbox.publish(job['id'])
        failed = self.wait(job['id'], 'failed')
        self.assertIn('obsidian', failed['receipts'])
        self.assertEqual(failed['notionState'], 'uncertain')
        with self.assertRaises(CaptureError):
            self.inbox.retry(job['id'])
        self.assertEqual(len(list(self.inbox.export_root.rglob('*.md'))), 1)

    def test_notion_publication_receipt_and_no_repeat(self):
        calls = []
        def publish(*args, **kwargs):
            calls.append((args, kwargs))
            return dict(id='a' * 32, url='https://www.notion.so/' + 'a' * 32)
        self.inbox.publisher = publish
        job = self.create('notion')
        self.inbox.publish(job['id'])
        done = self.wait(job['id'], 'completed')
        self.inbox.publish(job['id'])
        self.assertEqual(len(calls), 1)
        self.assertIn('notion', done['receipts'])

    def test_existing_different_file_is_not_overwritten(self):
        job = self.create()
        directory = self.inbox.export_root / job['note']['folder']
        directory.mkdir(parents=True)
        target = directory / f"{job['note']['title']} - {job['id']}.md"
        target.write_text('Dado pessoal existente', encoding='utf-8')
        self.inbox.publish(job['id'])
        self.wait(job['id'], 'failed')
        self.assertEqual(target.read_text(encoding='utf-8'), 'Dado pessoal existente')

    def test_folder_escape_and_windows_names_rejected(self):
        self.assertEqual(validate_folder('Estudos / Caixa de entrada'), 'Estudos/Caixa de entrada')
        for folder in ('../outside', 'a/../b', 'C:/Users', '/absolute', 'NUL', 'a:stream'):
            with self.subTest(folder=folder), self.assertRaises(CaptureError):
                validate_folder(folder)

    def test_unicode_markdown_and_invalid_upload(self):
        self.assertIn('ação', extract_file('nota.md', '# Uma ação'.encode()))
        with self.assertRaises(CaptureError):
            extract_file('executar.exe', b'not text')
        with self.assertRaises(CaptureError):
            extract_file('nota.txt', b'')

    def test_private_source_dns_is_blocked_and_html_scripts_ignored(self):
        with patch('socket.getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 80))]):
            with self.assertRaises(CaptureError):
                public_url('http://example.com/')
        parser = ArticleText(); parser.feed('<script>segredo()</script><h1>Fonte</h1><p>Texto visível.</p>')
        self.assertNotIn('segredo', ''.join(parser.parts))
        self.assertIn('visível', ''.join(parser.parts))

    def test_http_origin_token_and_upload(self):
        class Apps:
            def list(self): return []
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.root, self.inbox, Apps()))
        thread = Thread(target=server.serve_forever, daemon=True); thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(base + '/api/health', headers={'Origin': 'https://evil.example'}))
            self.assertEqual(error.exception.code, 403)
            with urlopen(base + '/api/health') as response:
                token = json.load(response)['token']
            with self.assertRaises(HTTPError):
                urlopen(base + '/api/transfers')
            headers = {'Origin':'http://127.0.0.1:43128', 'X-Lumen-Token': token, 'Content-Type':'application/json'}
            data = json.dumps(dict(source='nota.md', type='document', destination='obsidian', preferences={}, upload=base64.b64encode(b'# Teste').decode())).encode()
            with urlopen(Request(base + '/api/transfers', data=data, headers=headers)) as response:
                job = json.load(response)
            self.wait(job['id'])
        finally:
            server.shutdown(); server.server_close()


if __name__ == '__main__':
    unittest.main()
