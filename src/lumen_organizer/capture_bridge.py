"""Loopback-only Atlas bridge. Exact origins, JSON, session token and bounded bodies."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
from threading import Thread

from .capture import CaptureError

ORIGINS = frozenset('http://' + host + ':' + port for host in ('127.0.0.1', 'localhost') for port in ('5173', '4180'))
PORT = 43127


def start_bridge(inbox, port=PORT, on_action=None):
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, status, data):
            body = json.dumps(data, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            origin = self.headers.get('Origin')
            if origin in ORIGINS:
                self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def allowed(self, authenticated=True):
            if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}' or self.headers.get('Origin') not in ORIGINS:
                self.reply(403, {'error': 'Origem não autorizada.'})
                return False
            if authenticated and not secrets.compare_digest(self.headers.get('X-Lumen-Token', ''), token):
                self.reply(403, {'error': 'Sessão inválida. Reconecte ao Lumen.'})
                return False
            return True

        def do_OPTIONS(self):
            if not self.allowed(False):
                return
            self.send_response(204)
            self.send_header('Access-Control-Allow-Origin', self.headers['Origin'])
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Lumen-Token')
            self.end_headers()

        def do_GET(self):
            if not self.allowed(self.path != '/health'):
                return
            if self.path == '/health':
                self.reply(200, {'service': 'lumen-capture-v1', 'token': token})
            elif self.path == '/captures':
                self.reply(200, {'captures': inbox.list()})
            else:
                self.reply(404, {'error': 'Rota inexistente.'})

        def do_POST(self):
            if not self.allowed():
                return
            if self.path not in ('/captures', '/actions'):
                return self.reply(404, {'error': 'Rota inexistente.'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4096 or self.headers.get('Content-Type') != 'application/json':
                    raise ValueError()
                value = json.loads(self.rfile.read(length))
                if self.path == '/actions':
                    if not isinstance(value, dict) or value.get('action') not in ('notion', 'spotify', 'obsidian', 'orca', 'lumen') or on_action is None:
                        raise ValueError()
                    on_action(value['action'])
                    return self.reply(202, {'accepted': True})
                if not isinstance(value, dict) or not isinstance(value.get('url'), str) or not isinstance(value.get('title', ''), str):
                    raise ValueError()
                self.reply(202, inbox.submit(value['url'], value.get('title', '')))
            except CaptureError as error:
                self.reply(400, {'error': str(error)})
            except (ValueError, TypeError):
                self.reply(400, {'error': 'Pedido inválido.'})

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    Thread(target=server.serve_forever, daemon=True, name='lumen-bridge').start()
    return server
