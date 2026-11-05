"""Persistent loopback application server, authenticated API and Atlas SPA host."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import base64
import json
import mimetypes
import os
import secrets
import subprocess
import time
from urllib.parse import urlsplit
from .applications import ApplicationCatalog
from .capture import CaptureError
from .capture_bridge import start_bridge
from .knowledge import KnowledgeInbox
from .sources import MAX_UPLOAD
ORIGINS = frozenset(('http://127.0.0.1:43128', 'http://127.0.0.1:4180', 'http://localhost:4180'))
from .public_config import ATLAS, NOTION_LIBRARY_URL
mimetypes.add_type('text/javascript', '.js')
mimetypes.add_type('text/css', '.css')

class AtlasHandler(SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ATLAS / 'dist'), **kwargs)

    def do_GET(self):
        path = urlsplit(self.path).path
        if not Path(self.translate_path(path)).exists() and (not Path(path).suffix):
            self.path = '/index.html'
        super().do_GET()

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache' if not urlsplit(self.path).path.startswith('/assets/') else 'public, max-age=31536000, immutable')
        self.send_header('X-Content-Type-Options', 'nosniff')
        super().end_headers()

    def log_message(self, *_):
        pass

class LegacyAdapter:

    def __init__(self, inbox):
        self.inbox = inbox

    def convert(self, job):
        state = 'ready' if job['status'] in ('review', 'completed') else 'queued' if job['status'] == 'queued' else 'running' if job['status'] in ('extracting', 'generating', 'publishing') else 'failed'
        return dict(id=job['id'], state=state, url=job['source'], video_id='', title=job['note']['title'], message=job.get('message', ''), created=job['createdAt'], exercise=job.get('exercise', ''), publication='published' if 'notion' in job.get('receipts', {}) else 'none', notion_url=job.get('receipts', {}).get('notion', {}).get('url', ''))

    def list(self):
        return [self.convert(j) for j in self.inbox.list()]

    def submit(self, url, title=''):
        from .capture import video_id
        video_id(url)
        job = self.inbox.create(url, 'video', 'notion', {'title': title})
        return self.convert(job)

def make_handler(root, inbox, apps):
    root = Path(root)
    token = secrets.token_urlsafe(32)

    class Handler(SimpleHTTPRequestHandler):

        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root / 'frontend/dist'), **kwargs)

        def log_message(self, *_):
            pass

        def reply(self, status, value):
            body = json.dumps(value, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            origin = self.headers.get('Origin')
            if origin in ORIGINS:
                self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def allowed(self, auth=True):
            if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}' or self.headers.get('Origin') not in (*ORIGINS, None) or self.headers.get('Sec-Fetch-Site') == 'cross-site':
                self.reply(403, {'error': 'Origem não autorizada.'})
                return False
            if auth and (not secrets.compare_digest(self.headers.get('X-Lumen-Token', ''), token)):
                self.reply(403, {'error': 'Reconecte ao aplicativo local.'})
                return False
            return True

        def do_OPTIONS(self):
            if not self.allowed(False):
                return
            self.send_response(204)
            self.send_header('Access-Control-Allow-Origin', self.headers.get('Origin', 'http://127.0.0.1:43128'))
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Lumen-Token')
            self.end_headers()

        def do_GET(self):
            if self.path in ('/api/health', '/__lumen_ui_health'):
                if self.allowed(False):
                    self.reply(200, dict(app='lumen-workspace', mode='live', version=2, token=token))
                return
            if self.path.startswith('/api/'):
                if not self.allowed():
                    return
                try:
                    if self.path == '/api/transfers':
                        self.reply(200, inbox.list())
                    elif self.path == '/api/apps':
                        self.reply(200, apps.list())
                    elif self.path == '/api/connections':
                        from .capture import find_codex
                        self.reply(200, dict(obsidian=inbox.export_root.parent.is_dir(), notion='codex-connected', codex=bool(find_codex()), exportRoot=str(inbox.export_root), notionLibrary=NOTION_LIBRARY_URL))
                    elif self.path == '/api/hermes/status':
                        executable = Path(os.environ.get('LOCALAPPDATA', '')) / 'hermes/bin/hermes.exe'
                        if not executable.is_file():
                            self.reply(200, dict(installed=False, message='Hermes não encontrado.'))
                        else:
                            result = subprocess.run([str(executable), 'auth', 'status', 'openai-codex'], capture_output=True, encoding='utf-8', errors='replace', timeout=20, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                            self.reply(200, dict(installed=True, message='Login pendente. Use Conectar Hermes.' if 'logged out' in result.stdout.lower() else result.stdout.strip()[:1000] or 'Confira o login pelo atalho Conectar Hermes.'))
                    else:
                        self.reply(404, {'error': 'Rota não encontrada.'})
                except CaptureError as error:
                    self.reply(400, {'error': str(error)})
                return
            if not self.allowed(False):
                return
            if not Path(self.translate_path(self.path)).exists() and (not Path(urlsplit(self.path).path).suffix):
                self.path = '/index.html'
            super().do_GET()

        def end_headers(self):
            self.send_header('X-Content-Type-Options', 'nosniff')
            if not self.path.startswith('/api/'):
                self.send_header('Cache-Control', 'no-cache')
            super().end_headers()

        def do_POST(self):
            if not self.allowed():
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 28 * 1024 * 1024 or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                    raise CaptureError('Pedido vazio ou maior que o limite permitido.')
                value = json.loads(self.rfile.read(length))
                if not isinstance(value, dict):
                    raise CaptureError('Pedido inválido.')
                if self.path == '/api/transfers':
                    upload = None
                    if value.get('type') in ('pdf', 'document'):
                        encoded = value.get('upload')
                        if not isinstance(encoded, str) or len(encoded) > MAX_UPLOAD * 4 // 3 + 8:
                            raise CaptureError('Envie um arquivo de até 20 MB.')
                        upload = base64.b64decode(encoded, validate=True)
                        if len(upload) > MAX_UPLOAD or not upload:
                            raise CaptureError('Arquivo vazio ou maior que 20 MB.')
                    preferences = value.get('preferences', {})
                    if not isinstance(preferences, dict):
                        raise CaptureError('Preferências inválidas.')
                    self.reply(202, inbox.create(value.get('source'), value.get('type'), value.get('destination'), preferences, upload))
                elif self.path.startswith('/api/transfers/'):
                    parts = self.path.split('/')
                    if len(parts) != 5:
                        raise CaptureError('Ação inválida.')
                    identifier, action = parts[3:]
                    if action == 'save':
                        result = inbox.edit(identifier, value.get('note'), value.get('destination'))
                    elif action == 'publish' and value.get('reviewed') is True:
                        result = inbox.publish(identifier)
                    elif action == 'cancel':
                        result = inbox.cancel(identifier)
                    elif action == 'retry':
                        result = inbox.retry(identifier)
                    elif action == 'open':
                        job = inbox.get(identifier)
                        destination = value.get('destination')
                        if destination not in ('notion', 'obsidian') or destination not in job['receipts']:
                            raise CaptureError('Destino sem comprovante de entrega.')
                        import webbrowser
                        webbrowser.open(job['receipts'][destination]['url'])
                        result = {'opened': destination}
                    else:
                        raise CaptureError('Confirme a revisão antes de publicar.')
                    self.reply(200, result)
                elif self.path == '/api/apps/open':
                    self.reply(200, apps.open(value.get('id'), value.get('command')))
                elif self.path == '/api/apps/refresh':
                    self.reply(200, apps.refresh())
                else:
                    self.reply(404, {'error': 'Rota não encontrada.'})
            except (ValueError, TypeError, CaptureError) as error:
                self.reply(400, {'error': str(error) if isinstance(error, CaptureError) else 'Pedido inválido.'})
            except Exception:
                self.reply(500, {'error': 'Não foi possível concluir. Consulte o estado da transferência antes de repetir.'})
    return Handler

def serve(root):
    root = Path(root)
    inbox = KnowledgeInbox(root / '.local/transferencias')
    inbox.import_legacy(root / '.local/capturas')
    apps = ApplicationCatalog(root)
    atlas = ThreadingHTTPServer(('127.0.0.1', 4180), AtlasHandler)
    app = ThreadingHTTPServer(('127.0.0.1', 43128), make_handler(root, inbox, apps))
    Thread(target=atlas.serve_forever, daemon=True, name='atlas-static').start()
    bridge = None
    try:
        bridge = start_bridge(LegacyAdapter(inbox), on_action=lambda action: apps.open(command='abrir ' + action))
    except OSError:
        pass
    try:
        app.serve_forever()
    finally:
        atlas.shutdown()
        atlas.server_close()
        if bridge:
            bridge.shutdown()
        inbox.close()
