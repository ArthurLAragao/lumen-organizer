"""Install pinned capture dependencies only in this project's virtualenv."""
from pathlib import Path
import os
import sys
import tempfile
import uuid

root = Path(__file__).resolve().parents[1]
if Path(sys.prefix).resolve() != (root / '.venv').resolve():
    raise SystemExit('Use o Python da .venv do Lumen.')
temporary = root / '.local' / 'capture-setup'
temporary.mkdir(parents=True, exist_ok=True)
os.environ['TEMP'] = os.environ['TMP'] = str(temporary)
tempfile.tempdir = str(temporary)

def inherited_tempdir(suffix=None, prefix=None, dir=None):
    target = temporary / ((prefix or 'tmp') + uuid.uuid4().hex + (suffix or ''))
    target.mkdir(mode=0o777)
    return str(target)

tempfile.mkdtemp = inherited_tempdir
from pip._internal.cli.main import main
raise SystemExit(main(['--isolated', 'install', '--no-cache-dir', '--disable-pip-version-check',
    '--only-binary=:all:', '--index-url', 'https://pypi.org/simple', 'youtube-transcript-api==1.2.4']))
