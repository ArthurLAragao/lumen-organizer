"""Application windows using the user's Comet profile; no browser tabs required."""
import os
from pathlib import Path
import subprocess


def browser_executable():
    local = Path(os.environ.get('LOCALAPPDATA', ''))
    candidates = [local / 'Perplexity/Comet/Application/comet.exe',
                  Path(os.environ.get('PROGRAMFILES(X86)', r'C:\Program Files (x86)')) / 'Microsoft/Edge/Application/msedge.exe',
                  Path(os.environ.get('PROGRAMFILES', r'C:\Program Files')) / 'Microsoft/Edge/Application/msedge.exe']
    return next((path for path in candidates if path.is_file()), None)


def open_app(url):
    executable = browser_executable()
    if executable is None:
        raise RuntimeError('Comet ou Microsoft Edge não encontrado para abrir a janela do aplicativo.')
    subprocess.Popen([str(executable), '--app=' + url, '--new-window'],
                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
