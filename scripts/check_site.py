"""Check the public site's local assets without accessing accounts or the network."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

root = Path(__file__).resolve().parents[1] / 'site'
class Check(HTMLParser):
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for key in ('href', 'src'):
            value = attrs.get(key, '')
            url = urlsplit(value)
            if value and not url.scheme and not url.netloc and url.path:
                path = (root / url.path).resolve()
                assert path.is_relative_to(root.resolve()) and path.is_file(), value
checker = Check()
checker.feed((root / 'index.html').read_text(encoding='utf-8'))
assert (root / '.nojekyll').is_file()
print('Public site: local links and assets verified.')
