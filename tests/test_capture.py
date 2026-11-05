from pathlib import Path
from contextlib import contextmanager
import unittest
from unittest.mock import patch
from threading import Event
import requests

from lumen_organizer.capture import CaptureError, video_id, process_video, render_note, FIELDS
from lumen_organizer.capture_service import CaptureInbox
from lumen_organizer.capture_bridge import start_bridge
from lumen_organizer.validation import validate_file
from lumen_organizer.notion_publish import publish_note
from tests.support import FictionalWorkspace


class tempfile:
    @staticmethod
    @contextmanager
    def TemporaryDirectory():
        with FictionalWorkspace() as workspace:
            yield str(workspace.root)

URL = 'https://www.youtube.com/watch?v=x7X9w_GIm1s'
SUMMARY = {key: 'Conteúdo fictício para testar o fluxo.' for key in FIELDS}


class CaptureTests(unittest.TestCase):
    def test_urls(self):
        for url in (URL, 'https://youtu.be/x7X9w_GIm1s', 'https://youtube.com/shorts/x7X9w_GIm1s'):
            self.assertEqual(video_id(url), 'x7X9w_GIm1s')
        for url in ('http://youtube.com/watch?v=x7X9w_GIm1s', 'https://youtube.com.evil.test/watch?v=x7X9w_GIm1s',
                    'https://127.0.0.1/', 'file:///secret', 'https://youtube.com/playlist?list=test'):
            with self.assertRaises(CaptureError):
                video_id(url)

    def test_note_is_valid_but_not_reviewed(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / 'capture'
            result = process_video(URL, 'Teste: título', folder, transcript='Fonte fictícia', summarize=lambda *_: SUMMARY)
            self.assertTrue(validate_file(folder / 'nota.md').valid)
            self.assertFalse(result['reviewed'])
            self.assertEqual(result['validation'], 'structure-only')
            self.assertEqual(result['exercise'], SUMMARY['aplicacao'])
            self.assertIn('lumen_export: false', (folder / 'nota.md').read_text(encoding='utf-8'))

    def test_long_transcript_uses_all_parts_and_reduce(self):
        seen = []
        def summarize(text, _):
            seen.append(text)
            return SUMMARY
        with tempfile.TemporaryDirectory() as temp:
            process_video(URL, '', Path(temp) / 'capture', transcript='a' * 18000 + 'b' * 100,
                          summarize=summarize)
        self.assertEqual(seen[0], 'a' * 18000)
        self.assertEqual(seen[1], 'b' * 100)
        self.assertEqual(len(seen), 3)

    def test_transcript_failure_never_calls_model(self):
        def fetch(_):
            raise CaptureError('Sem transcrição')
        with tempfile.TemporaryDirectory() as temp:
            with patch('lumen_organizer.capture.codex_summary') as model:
                with self.assertRaises(CaptureError):
                    process_video(URL, '', Path(temp) / 'capture', fetch=fetch, summarize=model)
                model.assert_not_called()

    def test_blank_and_oversized_source_rejected(self):
        for source in ('', 'a' * 240001):
            with tempfile.TemporaryDirectory() as temp:
                with self.assertRaises(CaptureError):
                    process_video(URL, '', Path(temp) / 'capture', transcript=source)

    def test_source_saved_after_model_failure(self):
        def fail(*_):
            raise CaptureError('Limite de uso')
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / 'capture'
            with self.assertRaises(CaptureError):
                process_video(URL, '', folder, transcript='Preservar', summarize=fail)
            self.assertEqual((folder / 'transcricao.txt').read_text(), 'Preservar')
            self.assertFalse((folder / 'nota.md').exists())

    def test_inbox_deduplicates_and_persists(self):
        gate = Event()
        def processor(*args, **kwargs):
            gate.wait(3)
            return {'validation': 'structure-only'}
        with tempfile.TemporaryDirectory() as temp:
            inbox = CaptureInbox(temp, processor)
            try:
                first = inbox.submit(URL)
                second = inbox.submit(URL)
                self.assertEqual(first['id'], second['id'])
                self.assertEqual(len(inbox.list()), 1)
                with self.assertRaises(CaptureError):
                    inbox.publish(first['id'], 'token', 'parent', False)
            finally:
                gate.set(); inbox.executor.shutdown(wait=True)
            restored = CaptureInbox(temp)
            self.assertEqual(restored.get(first['id'])['state'], 'ready')
            restored.close()

    def test_automatic_publication_stays_unreviewed_and_preserves_note(self):
        done = Event()
        def processor(url, title, folder, **kwargs):
            return process_video(url, title, folder, transcript='Fonte fictícia', summarize=lambda *_: SUMMARY)
        def publisher(title, body, identifier, folder):
            self.assertIn('revisão', body.lower())
            done.set()
            return {'id': 'b' * 32, 'url': 'https://app.notion.com/p/' + 'b' * 32}
        with tempfile.TemporaryDirectory() as temp:
            inbox = CaptureInbox(temp, processor, publisher)
            job = inbox.submit(URL)
            inbox.executor.shutdown(wait=True)
            self.assertTrue(done.is_set())
            self.assertEqual(inbox.get(job['id'])['publication'], 'published')
            self.assertIn('status: inbox', inbox.note(job['id']))
            inbox.close()

    def test_bridge_rejects_untrusted_origin_and_missing_token(self):
        with tempfile.TemporaryDirectory() as temp:
            inbox = CaptureInbox(temp)
            bridge = start_bridge(inbox, 0)
            base = f'http://127.0.0.1:{bridge.server_port}'
            try:
                self.assertEqual(requests.get(base + '/health', timeout=3).status_code, 403)
                bad = {'Origin': 'https://evil.test'}
                self.assertEqual(requests.get(base + '/health', headers=bad, timeout=3).status_code, 403)
                headers = {'Origin': 'http://127.0.0.1:4180'}
                health = requests.get(base + '/health', headers=headers, timeout=3).json()
                self.assertEqual(health['service'], 'lumen-capture-v1')
                self.assertEqual(requests.get(base + '/captures', headers=headers, timeout=3).status_code, 403)
                headers['X-Lumen-Token'] = health['token']
                self.assertEqual(requests.get(base + '/captures', headers=headers, timeout=3).json(), {'captures': []})
                self.assertEqual(requests.post(base + '/captures', json={'url': 'file:///x'}, headers=headers, timeout=3).status_code, 400)
            finally:
                bridge.shutdown(); bridge.server_close(); inbox.close()

    def test_desktop_actions_are_allowlisted_and_require_session(self):
        actions = []
        with tempfile.TemporaryDirectory() as temp:
            inbox = CaptureInbox(temp)
            bridge = start_bridge(inbox, 0, on_action=actions.append)
            base = f'http://127.0.0.1:{bridge.server_port}'
            headers = {'Origin': 'http://127.0.0.1:4180'}
            try:
                health = requests.get(base + '/health', headers=headers, timeout=3).json()
                self.assertEqual(requests.post(base + '/actions', json={'action': 'notion'}, headers=headers, timeout=3).status_code, 403)
                headers['X-Lumen-Token'] = health['token']
                self.assertEqual(requests.post(base + '/actions', json={'action': 'notion'}, headers=headers, timeout=3).status_code, 202)
                self.assertEqual(actions, ['notion'])
                self.assertEqual(requests.post(base + '/actions', json={'action': 'powershell arbitrary'}, headers=headers, timeout=3).status_code, 400)
                self.assertEqual(actions, ['notion'])
            finally:
                bridge.shutdown(); bridge.server_close(); inbox.close()

    def test_notion_verifies_page_without_redirects(self):
        from unittest.mock import Mock
        client = Mock()
        page = {'id': 'a' * 32, 'url': 'https://www.notion.so/' + 'a' * 32}
        client.post.return_value.status_code = 200
        client.post.return_value.json.return_value = page
        client.get.return_value.status_code = 200
        client.get.return_value.json.return_value = page
        self.assertEqual(publish_note('Teste', '# Fonte', 'secret-test', 'b' * 32, client), page)
        self.assertFalse(client.post.call_args.kwargs['allow_redirects'])
        client.get.return_value.status_code = 403
        with self.assertRaises(CaptureError):
            publish_note('Teste', 'Nota', 'secret-test', 'b' * 32, client)

    def test_capture_desk_opens_without_network_and_closes_cleanly(self):
        import tkinter as tk
        from lumen_organizer.ui import App
        with tempfile.TemporaryDirectory() as temp, patch('lumen_organizer.capture_ui.start_bridge', return_value=None):
            root = tk.Tk()
            root.withdraw()
            app = App(root, Path(temp) / '.local', load_settings=False)
            try:
                root.deiconify()
                root.update()
                app.open_capture()
                window = app.capture_window
                window.window.deiconify()
                window.advanced.pack(fill='x')
                root.update()
                window.window.update_idletasks()
                self.assertEqual(len(window.inbox.list()), 0)
                self.assertGreater(window.publish_button.winfo_height(), 1,
                    str((window.window.winfo_geometry(), [(child.winfo_class(), child.winfo_reqheight(), child.winfo_height())
                         for child in window.publish_button.master.winfo_children()])))
                self.assertLess(window.publish_button.winfo_rooty() + window.publish_button.winfo_height(),
                                window.window.winfo_rooty() + window.window.winfo_height())
                self.assertTrue(window.close())
                self.assertIsNone(app.capture_window)
            finally:
                app.destroy()

    def test_no_notion_retry_after_uncertain_delivery(self):
        with tempfile.TemporaryDirectory() as temp:
            inbox = CaptureInbox(temp)
            identifier = 'a' * 32
            inbox.jobs[identifier] = {'id': identifier, 'title': 'Teste', 'state': 'ready', 'publication': 'none'}
            folder = Path(temp) / identifier / 'conteudo'; folder.mkdir(parents=True)
            (folder / 'nota.md').write_text(render_note('Teste', URL, SUMMARY), encoding='utf-8')
            with patch('lumen_organizer.notion_publish.publish_note', side_effect=TimeoutError) as publisher:
                for _ in range(2):
                    with self.assertRaises(CaptureError):
                        inbox.publish(identifier, 'token', 'b' * 32, True)
                self.assertEqual(publisher.call_count, 1)
            inbox.close()
