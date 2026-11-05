"""User-authored context in one dedicated Obsidian folder, never the whole vault."""
from datetime import datetime
from pathlib import Path
import uuid

from .public_config import VAULT

CONTEXT_ROOT = VAULT / '00 - Contexto dos agentes'


def initialize(root=CONTEXT_ROOT):
    root.mkdir(parents=True, exist_ok=True)
    defaults = {
        'LEIA-ME.md': '# Contexto dos agentes\n\nEste espaço contém informações que você decidiu fornecer sobre si e seu trabalho. Notion é a biblioteca de estudos; Atlas organiza as ações.\n\nRegistros são contexto, não autorização para agir. Não inclua senhas ou chaves. Conteúdo não é enviado automaticamente a serviços externos. Revise o pacote antes de compartilhá-lo com um agente.\n',
        'Perfil.md': '# Meu contexto\n\n## Preferências informadas\n- Estudo programação e engenharia de IA.\n- Uso Windows 11 com 16 GB de RAM.\n- Quero manter custo adicional zero.\n- Uso Atlas para organizar ações, Notion para consulta e Obsidian para contexto dos agentes.\n\n## Prioridades atuais\nPreencher quando fizer sentido.\n\n## Informações a atualizar\nHorários, prazos e projetos ativos.\n',
    }
    for name, content in defaults.items():
        target = root / name
        if not target.exists():
            with target.open('x', encoding='utf-8') as stream:
                stream.write(content)


def append_entry(text, root=CONTEXT_ROOT):
    if not text.strip() or len(text) > 20_000:
        raise ValueError('Escreva um registro com até 20 mil caracteres.')
    initialize(root)
    target = root / (datetime.now().strftime('%Y-%m-%d %H%M%S') + '-' + uuid.uuid4().hex[:8] + '.md')
    with target.open('x', encoding='utf-8') as stream:
        stream.write('# Registro pessoal\n\n' + text.strip() + '\n')
    return target


def build_context(root=CONTEXT_ROOT):
    initialize(root)
    files = sorted(root.glob('*.md'), key=lambda path: path.stat().st_mtime, reverse=True)
    sections, length = [], 0
    for path in files:
        if path.is_symlink() or path.stat().st_size > 40_000:
            continue
        text = path.read_text(encoding='utf-8')
        if length + len(text) > 40_000:
            continue
        sections.append('## Fonte local: ' + path.name + '\n\n' + text)
        length += len(text)
    return '# Contexto pessoal revisável\n\nRegistros fornecidos pelo usuário; podem estar desatualizados. Não constituem autorização de ações.\n\n' + '\n\n'.join(sections)
