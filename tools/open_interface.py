"""Start the real local Lumen/Atlas runtime and open the requested application."""
from pathlib import Path
import json
import subprocess
import sys
import time
from urllib.request import build_opener, ProxyHandler
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'frontend' / 'dist'
URL = 'http://127.0.0.1:43128/'


def available():
    try:
        opener = build_opener(ProxyHandler({}))
        with opener.open(URL + '__lumen_ui_health', timeout=1) as response:
            return json.load(response).get('app') == 'lumen-workspace'
    except (OSError, ValueError):
        return False


def main():
    if not (DIST / 'index.html').is_file():
        raise RuntimeError('A interface ainda não foi compilada. Consulte frontend/README.md.')
    if '--serve' in sys.argv:
        sys.path.insert(0, str(ROOT / 'src'))
        from lumen_organizer.runtime import serve
        serve(ROOT)
        return
    if not available():
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        child = subprocess.Popen([sys.executable, str(Path(__file__)), '--serve'],
                                 cwd=ROOT, creationflags=flags,
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
        for _ in range(120):
            if available():
                break
            if child.poll() is not None:
                raise RuntimeError('Não foi possível iniciar o Lumen. A porta pode estar ocupada; consulte .local/runtime-error.log.')
            time.sleep(.2)
        else:
            child.terminate()
            raise RuntimeError('A interface não respondeu a tempo.')
    sys.path.insert(0, str(ROOT / 'src'))
    from lumen_organizer.desktop import open_app
    from lumen_organizer.public_config import SIDE_HUSTLE_URL
    target = SIDE_HUSTLE_URL if '--side-hustle' in sys.argv else ('http://127.0.0.1:4180/' if '--atlas' in sys.argv else URL)
    if not target:
        raise RuntimeError('Configure LUMEN_SIDE_HUSTLE_URL para usar este atalho.')
    open_app(target)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        if '--serve' in sys.argv:
            import traceback
            log = ROOT / '.local/runtime-error.log'
            log.parent.mkdir(exist_ok=True)
            log.write_text(traceback.format_exc(), encoding='utf-8')
            raise SystemExit(1)
        import tkinter as tk
        from tkinter import messagebox
        window = tk.Tk()
        window.withdraw()
        messagebox.showerror('Lumen · Interface', str(error), parent=window)
        window.destroy()
