"""Launch only installed catalog entries; user text is never a shell command."""
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import unicodedata
import webbrowser

from .capture import CaptureError
from .public_config import SIDE_HUSTLE_URL, NOTION_LIBRARY_URL, VAULT
from urllib.parse import quote


def normalize(value):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFD', value.casefold()) if unicodedata.category(c) != 'Mn').split()).strip(' .!?')


class ApplicationCatalog:
    def __init__(self, root):
        self.root = Path(root)
        self.entries = {}
        self.refresh()

    def refresh(self):
        entries = {}
        def add(name, target, kind='file', aliases=()):
            identifier = sha256((kind + ':' + target).encode()).hexdigest()[:20]
            entries[identifier] = dict(id=identifier, name=name, target=target, kind=kind, aliases=list(aliases))
        add('Lumen', 'http://127.0.0.1:43128/', 'url', ('lumen',))
        if SIDE_HUSTLE_URL:
            add('Side Hustle', SIDE_HUSTLE_URL, 'url', ('side hustle', 'sidehustle', 'negocios', 'negócios'))
        add('YouTube', 'https://www.youtube.com/', 'url', ('youtube', 'you tube'))
        add('Atlas', 'http://127.0.0.1:4180/', 'url', ('atlas',))
        add('Spotify', 'spotify:', 'uri', ('spotify', 'musica'))
        add('Notion', NOTION_LIBRARY_URL, 'uri', ('notion', 'biblioteca'))
        add('Obsidian', 'obsidian://open?vault=' + quote(VAULT.name), 'uri', ('obsidian', 'contexto'))
        helper = self.root / 'tools/Conectar-Hermes.cmd'
        if helper.is_file():
            add('Conectar Hermes (ChatGPT)', str(helper), aliases=('conectar hermes',))
        local = Path(os.environ.get('LOCALAPPDATA', ''))
        for name, path, aliases in [('Orca', local / 'Programs/Orca/Orca.exe', ('orca', 'agentes')),
                                     ('Hermes', local / 'hermes/bin/hermes.exe', ('hermes',))]:
            if path.is_file():
                add(name, str(path), aliases=aliases)
        roots = [Path(os.environ.get('APPDATA', '')) / 'Microsoft/Windows/Start Menu/Programs',
                 Path(os.environ.get('PROGRAMDATA', r'C:\ProgramData')) / 'Microsoft/Windows/Start Menu/Programs']
        for root in roots:
            if root.is_dir():
                for path in root.rglob('*.lnk'):
                    if not path.is_symlink() and not any(word in normalize(path.stem) for word in ('uninstall', 'desinstalar', 'remove ')):
                        add(path.stem, str(path))
        try:
            result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', '[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress'],
                                    capture_output=True, encoding='utf-8', errors='replace', timeout=20,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            values = json.loads(result.stdout.lstrip('\ufeff'))
            for item in values if isinstance(values, list) else [values]:
                if isinstance(item.get('AppID'), str) and re.fullmatch(r'[A-Za-z0-9_.!{}\\-]{3,300}', item['AppID']):
                    add(item['Name'], item['AppID'], 'aumid')
        except (OSError, ValueError, subprocess.TimeoutExpired, TypeError):
            pass
        by_name = {}
        for entry in entries.values():
            name = normalize(entry['name'])
            score = (bool(entry['aliases']), entry['kind'] != 'aumid')
            previous = by_name.get(name)
            if previous is None or score > (bool(previous['aliases']), previous['kind'] != 'aumid'):
                by_name[name] = entry
        for name, entry in by_name.items():
            system_aliases = {'calculator': ('calculadora',), 'notepad': ('bloco de notas',),
                              'settings': ('configuracoes',), 'photos': ('fotos',),
                              'clock': ('relogio',), 'snipping tool': ('ferramenta de captura', 'recorte')}
            entry['aliases'].extend(system_aliases.get(name, ()))
            if 'visual studio code' in name:
                entry['aliases'].extend(('vs code', 'vscode', 'codigo'))
            if 'intellij' in name:
                entry['aliases'].append('intellij')
            if name == 'comet':
                entry['aliases'].append('navegador')
        self.entries = {entry['id']: entry for entry in by_name.values()}
        return self.list()

    def list(self):
        return sorted([dict(id=v['id'], name=v['name']) for v in self.entries.values()], key=lambda v: normalize(v['name']))

    def resolve(self, command):
        value = normalize(command)
        value = re.sub(r'^jarvis[, ]+', '', value)
        value = re.sub(r'^(?:(?:voce )?(?:pode|poderia|consegue)|can you|could you|would you) ', '', value)
        value = re.sub(r',? (?:por favor|pra mim|para mim|please|for me)$', '', value)
        value = re.sub(r'^(?:por favor |please )?(?:abrir|abra|iniciar|inicie|executar|execute|open|launch|start|run)(?: o| a)?\s+', '', value)
        exact = [v for v in self.entries.values() if value in [normalize(v['name']), *map(normalize, v['aliases'])]]
        if len(exact) > 1:
            # Prefer the explicit built-in alias to duplicate Windows shortcuts.
            aliased = [v for v in exact if value in map(normalize, v['aliases'])]
            exact = aliased or exact
        if len(exact) != 1:
            candidates = [v['name'] for v in self.entries.values() if value and value in normalize(v['name'])][:6]
            raise CaptureError('No unique application found. Choose from the catalog' + (': ' + ', '.join(candidates) if candidates else '.') )
        return exact[0]['id']

    def open(self, identifier=None, command=None):
        identifier = identifier or self.resolve(command or '')
        if identifier not in self.entries:
            raise CaptureError('This application is not in the local catalog.')
        entry = self.entries[identifier]
        if entry['kind'] == 'url':
            from .desktop import open_app
            open_app(entry['target'])
        elif entry['kind'] == 'aumid':
            subprocess.Popen(['explorer.exe', 'shell:AppsFolder\\' + entry['target']])
        elif entry['name'] == 'Hermes':
            subprocess.Popen([entry['target']], cwd=self.root,
                             creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0))
        else:
            os.startfile(entry['target'])
        return {'opened': entry['name']}
