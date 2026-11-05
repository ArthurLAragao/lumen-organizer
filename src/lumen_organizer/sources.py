"""Bounded text extraction. Remote fetches are pinned to validated public IPs."""
import http.client
import ipaddress
import socket
import ssl
from html.parser import HTMLParser
from io import BytesIO
from urllib.parse import urlsplit, urljoin

from .capture import CaptureError, MAX_TRANSCRIPT, fetch_transcript, video_id

MAX_UPLOAD = 20 * 1024 * 1024


class ArticleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'nav', 'footer', 'noscript', 'svg'):
            self.skip += 1
        if not self.skip and tag in ('p', 'div', 'h1', 'h2', 'h3', 'li', 'br'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'nav', 'footer', 'noscript', 'svg'):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def public_url(url):
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or parsed.username or parsed.password or not parsed.hostname:
        raise CaptureError('Use um endereço público HTTP ou HTTPS, sem credenciais.')
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    if port not in (80, 443):
        raise CaptureError('A fonte deve usar uma porta web padrão.')
    addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise CaptureError('Links para rede local ou endereços reservados não são aceitos como fonte.')
    address = next((item[4][0] for item in addresses if ':' not in item[4][0]), addresses[0][4][0])
    return parsed, port, address


def fetch_page(url):
    for _ in range(5):
        parsed, port, address = public_url(url)
        connection = http.client.HTTPConnection(parsed.hostname, port, timeout=25)
        connection.sock = socket.create_connection((address, port), timeout=25)
        if parsed.scheme == 'https':
            connection.sock = ssl.create_default_context().wrap_socket(connection.sock, server_hostname=parsed.hostname)
        try:
            connection.request('GET', (parsed.path or '/') + ('?' + parsed.query if parsed.query else ''),
                               headers={'User-Agent': 'Lumen/1.0 (personal study reader)', 'Accept-Encoding': 'identity'})
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                target = response.getheader('Location')
                if not target:
                    raise CaptureError('Redirecionamento da fonte sem destino.')
                url = urljoin(url, target)
                continue
            if response.status != 200:
                raise CaptureError(f'A fonte respondeu HTTP {response.status}. Você pode importar um arquivo de texto.')
            content_type = response.getheader('Content-Type', '').lower()
            if not any(t in content_type for t in ('text/html', 'text/plain', 'application/pdf', 'text/markdown')):
                raise CaptureError('Tipo de conteúdo da página não suportado.')
            body = response.read(2 * 1024 * 1024 + 1)
            if len(body) > 2 * 1024 * 1024:
                raise CaptureError('A página excede 2 MB. Importe o arquivo diretamente.')
            if 'application/pdf' in content_type:
                return extract_file('fonte.pdf', body)
            charset = response.headers.get_content_charset() or 'utf-8'
            try:
                text = body.decode(charset, errors='replace')
            except LookupError:
                text = body.decode('utf-8', errors='replace')
            if 'html' in content_type:
                parser = ArticleText()
                parser.feed(text)
                text = '\n'.join(line.strip() for line in ''.join(parser.parts).splitlines() if line.strip())
            return bounded_text(text)
        finally:
            connection.close()
    raise CaptureError('A página redirecionou vezes demais.')


def bounded_text(text):
    text = text.strip()
    if not text:
        raise CaptureError('Não foi encontrado texto legível. PDFs digitalizados precisam de OCR antes da importação.')
    if len(text) > MAX_TRANSCRIPT:
        raise CaptureError('O material excede 240 mil caracteres. Divida-o; não houve truncamento silencioso.')
    return text


def extract_file(name, data):
    if not data or len(data) > MAX_UPLOAD:
        raise CaptureError('Envie um arquivo não vazio de até 20 MB.')
    if name.lower().endswith('.pdf'):
        from pypdf import PdfReader
        try:
            reader = PdfReader(BytesIO(data))
            if reader.is_encrypted or len(reader.pages) > 300:
                raise CaptureError('PDF protegido ou com mais de 300 páginas. Divida ou desbloqueie o material.')
            parts, size = [], 0
            for page in reader.pages:
                text = page.extract_text() or ''
                size += len(text)
                if size > MAX_TRANSCRIPT:
                    raise CaptureError('O PDF excede o limite de texto. Divida o material.')
                parts.append(text)
            return bounded_text('\n\n'.join(parts))
        except CaptureError:
            raise
        except Exception:
            raise CaptureError('Não foi possível ler o PDF. Confira o arquivo ou importe seu texto.') from None
    if not name.lower().endswith(('.md', '.txt')):
        raise CaptureError('Formato aceito: PDF, Markdown ou texto UTF-8.')
    try:
        return bounded_text(data.decode('utf-8-sig'))
    except UnicodeError:
        raise CaptureError('Salve o arquivo de texto em UTF-8 antes de importar.') from None


def extract_source(source, kind, upload=None):
    if kind in ('pdf', 'document'):
        return extract_file(source, upload)
    if kind == 'idea':
        return bounded_text(source)
    if kind == 'video':
        return bounded_text(fetch_transcript(video_id(source)))
    return fetch_page(source)
