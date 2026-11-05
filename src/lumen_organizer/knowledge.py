"""Durable knowledge transfers, reviewed publication and per-destination receipts."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from threading import RLock
from urllib.parse import quote
from hashlib import sha256
import json
import re
import uuid
import yaml

from .capture import CaptureError, codex_summary, render_note, CHUNK_SIZE
from .notion_connected import publish_connected
from .sources import extract_source
from .validation import validate_file

from .public_config import VAULT
EXPORT_ROOT = VAULT / '10 - Biblioteca Lumen'
ACTIVE = ('queued', 'extracting', 'generating', 'publishing')


def validate_folder(folder):
    if not isinstance(folder, str) or not folder.strip() or len(folder) > 180:
        raise CaptureError('Informe uma pasta relativa dentro da Biblioteca Lumen.')
    folder = folder.replace('\\', '/').strip()
    parts = [part.strip() for part in folder.split('/')]
    if folder.startswith('/') or any(not p or p in ('.', '..') or re.search(r'[:<>"|?*\x00-\x1f]', p) or p.endswith('.') or re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', p) for p in parts):
        raise CaptureError('Use uma pasta relativa válida, sem atalhos para fora da biblioteca.')
    return '/'.join(parts)


class KnowledgeInbox:
    def __init__(self, root, *, summarize=codex_summary, extract=extract_source,
                 publisher=publish_connected, export_root=EXPORT_ROOT):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.export_root = Path(export_root)
        self.summarize, self.extract, self.publisher = summarize, extract, publisher
        self.lock = RLock()
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='lumen-knowledge')
        self.jobs = {}
        self.futures = {}
        for file in self.root.glob('*/estado.json'):
            try:
                job = json.loads(file.read_text(encoding='utf-8'))
                if not re.fullmatch('[a-f0-9]{32}', job['id']) or file.parent.name != job['id']:
                    continue
                if job['status'] in ACTIVE:
                    if job['status'] == 'publishing' and job.get('notionState') == 'pending':
                        job['notionState'] = 'uncertain'
                    job.update(status='failed', error='Operação interrompida. Fontes e comprovantes preservados; confira os destinos antes de repetir.')
                self.jobs[job['id']] = job
                self._save(job)
            except (ValueError, OSError, KeyError):
                continue

    def _save(self, job):
        directory = self.root / job['id']
        directory.mkdir(exist_ok=True)
        temporary = directory / 'estado.tmp'
        temporary.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(directory / 'estado.json')

    def import_legacy(self, directory):
        """Copy validated previous captures; original files and receipts stay untouched."""
        for state in Path(directory).glob('*/estado.json'):
            try:
                old = json.loads(state.read_text(encoding='utf-8'))
                identifier = old['id']
                if not re.fullmatch('[a-f0-9]{32}', identifier) or identifier in self.jobs:
                    continue
                note_path = state.parent / 'conteudo/nota.md'
                if note_path.is_symlink() or not validate_file(note_path).valid:
                    continue
                markdown = note_path.read_text(encoding='utf-8')
                _, metadata, body = markdown.split('---', 2)
                meta = yaml.safe_load(metadata)
                sections = {}
                headings = {'Resumo':'resumo', 'Explicação':'explicacao', 'Exemplos e aplicação':'aplicacao', 'Revisão':'revisao', 'Pontos de atenção':'atencao'}
                for heading, key in headings.items():
                    match = re.search(r'^## ' + re.escape(heading) + r'\s*\n(.*?)(?=^## |\Z)', body, re.M | re.S)
                    sections[key] = match.group(1).strip() if match else 'Revisão pendente.'
                receipts = {}
                notion_state = old.get('publication', 'none')
                if notion_state == 'published' and old.get('notion_url', '').startswith(('https://app.notion.com/p/', 'https://www.notion.so/')):
                    receipts['notion'] = dict(url=old['notion_url'], id=old.get('notion_id', ''))
                if notion_state == 'pending':
                    notion_state = 'uncertain'
                status = 'completed' if receipts else 'failed' if notion_state == 'uncertain' else 'review'
                job = dict(id=identifier, source=old.get('url', meta['source']), type='video', destination='notion',
                    createdAt=old['created'], status=status, note=dict(title=meta['title'], summary=sections['resumo'],
                    tags=meta.get('tags', []), folder='Estudos/Caixa de entrada', format='study'), sections=sections,
                    markdown=markdown, receipts=receipts, notionState=notion_state, legacyImported=True,
                    message='Captura anterior preservada. ' + old.get('message', ''), exercise=old.get('exercise', ''))
                if status == 'failed':
                    job['error'] = 'Entrega anterior incerta. Confira a biblioteca antes de repetir.'
                self.jobs[identifier] = job
                self._save(job)
                (self.root / identifier / 'nota.md').write_text(markdown, encoding='utf-8')
            except (ValueError, KeyError, OSError):
                continue

    def list(self):
        with self.lock:
            rows = json.loads(json.dumps(sorted(self.jobs.values(), key=lambda j: j['createdAt'], reverse=True)))
            for row in rows:
                if row.get('sourceText'):
                    row['sourceTruncated'] = len(row['sourceText']) > 12000
                    row['sourceText'] = row['sourceText'][:12000]
            return rows

    def get(self, identifier):
        with self.lock:
            if identifier not in self.jobs:
                raise CaptureError('Transferência não encontrada.')
            return json.loads(json.dumps(self.jobs[identifier]))

    def update(self, identifier, **values):
        with self.lock:
            if self.jobs[identifier]['status'] == 'cancelled' and values.get('status') != 'queued':
                return self.get(identifier)
            self.jobs[identifier].update(values)
            self._save(self.jobs[identifier])
            return self.get(identifier)

    def create(self, source, kind, destination, preferences, upload=None):
        if not isinstance(source, str) or not source.strip() or len(source) > 240_000 or kind not in ('idea', 'video', 'link', 'pdf', 'document') or destination not in ('obsidian', 'notion', 'both'):
            raise CaptureError('Fonte ou destino inválido.')
        folder = validate_folder(preferences.get('folder', 'Estudos/Caixa de entrada'))
        tags = preferences.get('tags', 'estudos, revisar')
        if not isinstance(tags, str) or len(tags) > 1000:
            raise CaptureError('Tags inválidas.')
        fingerprint = sha256(json.dumps([kind, source.strip(), destination, folder, tags,
            sha256(upload or b'').hexdigest()], ensure_ascii=False).encode()).hexdigest()
        with self.lock:
            for existing in self.jobs.values():
                if existing.get('fingerprint') == fingerprint and existing['status'] not in ('failed', 'cancelled'):
                    return self.get(existing['id'])
            if sum(j['status'] in ACTIVE for j in self.jobs.values()) >= 5:
                raise CaptureError('A fila está cheia. Aguarde uma transferência terminar.')
            identifier = uuid.uuid4().hex
            job = dict(id=identifier, source=source.strip(), type=kind, destination=destination,
                status='queued', createdAt=datetime.now(timezone.utc).isoformat(),
                note=dict(title=' '.join(str(preferences.get('title', '')).split())[:200] or (' '.join(source.split())[:100] if kind in ('idea', 'pdf', 'document') else 'Nova captura'), summary='',
                    tags=[t.strip().lstrip('#') for t in tags.split(',') if t.strip()][:20], folder=folder, format='study'),
                message='Na fila', receipts={}, notionState='none', fingerprint=fingerprint)
            self.jobs[identifier] = job
            self._save(job)
            if upload is not None:
                (self.root / identifier / 'original').write_bytes(upload)
            self.futures[identifier] = self.executor.submit(self._run, identifier)
            return self.get(identifier)

    def _cancelled(self, identifier):
        return self.get(identifier)['status'] == 'cancelled'

    def _run(self, identifier):
        try:
            if self._cancelled(identifier):
                return
            job = self.get(identifier)
            self.update(identifier, status='extracting', message='Lendo a fonte real', error=None)
            directory = self.root / identifier
            upload = (directory / 'original').read_bytes() if job['type'] in ('pdf', 'document') else None
            source_path = directory / 'fonte.txt'
            text = source_path.read_text(encoding='utf-8') if source_path.exists() else self.extract(job['source'], job['type'], upload)
            source_path.write_text(text, encoding='utf-8')
            if self._cancelled(identifier):
                return
            self.update(identifier, status='generating', message='Resumindo em português com seu Codex')
            chunks = [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]
            summaries = []
            for index, chunk in enumerate(chunks):
                if self._cancelled(identifier):
                    return
                self.update(identifier, message=f'Resumindo parte {index + 1} de {len(chunks)}')
                summaries.append(self.summarize(chunk, directory / f'ia-{uuid.uuid4().hex}'))
            summary = summaries[0] if len(summaries) == 1 else self.summarize(json.dumps(summaries, ensure_ascii=False), directory / f'ia-{uuid.uuid4().hex}')
            if self._cancelled(identifier):
                return
            note = job['note']
            if note['title'] == 'Nova captura':
                note['title'] = summary['resumo'].split('\n')[0].strip(' #*-')[:100] or 'Material de estudo'
            note['summary'] = summary['resumo']
            self.update(identifier, note=note, sections=summary, sourceText=text,
                        sourceHash=sha256(text.encode()).hexdigest(), exercise=summary['aplicacao'])
            self._render(identifier)
            self.update(identifier, status='review', message='Nota pronta. Revise antes de enviar.', validation='structure-only')
        except Exception as error:
            if not self._cancelled(identifier):
                self.update(identifier, status='failed', error=str(error) if isinstance(error, CaptureError) else 'Falha ao processar a fonte. O original foi preservado.', message='Precisa de atenção')

    def _render(self, identifier):
        job = self.get(identifier)
        sections = dict(job['sections'], resumo=job['note']['summary'])
        source = job['source'] if job['type'] in ('video', 'link') else 'Arquivo local: ' + job['source'] if job['type'] in ('pdf', 'document') else 'lumen://captura/' + identifier
        text = render_note(job['note']['title'], source, sections)
        metadata, body = text.split('---', 2)[1:]
        data = yaml.safe_load(metadata)
        data['tags'] = job['note']['tags']
        text = '---\n' + yaml.safe_dump(data, allow_unicode=True, sort_keys=False) + '---' + body
        text = text.replace('a partir de transcrição', 'a partir do conteúdo fornecido')
        path = self.root / identifier / 'nota.md'
        path.write_text(text, encoding='utf-8')
        if not validate_file(path).valid:
            raise CaptureError('A nota não passou na validação Lumen. Confira os campos.')
        self.update(identifier, markdown=text)
        return text

    def edit(self, identifier, note, destination):
        with self.lock:
            job = self.get(identifier)
            if job['status'] not in ('review', 'failed') or not job.get('sections') or job.get('receipts') or job.get('notionState') != 'none':
                raise CaptureError('A nota só pode ser editada antes da publicação. Os comprovantes existentes foram preservados.')
            if destination not in ('obsidian', 'notion', 'both') or not isinstance(note, dict):
                raise CaptureError('Destino ou nota inválido.')
            if not isinstance(note.get('title'), str) or not note['title'].strip() or len(note['title']) > 200 or not isinstance(note.get('summary'), str) or not note['summary'].strip() or len(note['summary']) > 100_000:
                raise CaptureError('Informe título (até 200 caracteres) e resumo válidos.')
            tags = note.get('tags')
            if not isinstance(tags, list) or len(tags) > 20 or any(not isinstance(t, str) or not t.strip() or len(t) > 80 for t in tags):
                raise CaptureError('Use até 20 tags, cada uma com até 80 caracteres.')
            note = dict(title=note['title'].strip(), summary=note['summary'].strip(), tags=tags,
                        folder=validate_folder(note.get('folder')), format='study')
            self.update(identifier, note=note, destination=destination, status='review', error=None)
            self._render(identifier)
            return self.get(identifier)

    def cancel(self, identifier):
        with self.lock:
            job = self.get(identifier)
            if job['status'] not in ('queued', 'extracting', 'generating'):
                raise CaptureError('A transferência não pode ser cancelada nesta etapa.')
            return self.update(identifier, status='cancelled', message='Cancelada. Original preservado; nenhuma publicação iniciada.')

    def retry(self, identifier):
        with self.lock:
            job = self.get(identifier)
            if job['status'] not in ('failed', 'cancelled') or job.get('notionState') in ('pending', 'uncertain'):
                raise CaptureError('Entrega incerta: confira o Notion antes de repetir. Nenhuma página será duplicada automaticamente.')
            if identifier in self.futures and not self.futures[identifier].done():
                raise CaptureError('Aguarde a operação anterior terminar antes de repetir. O cancelamento já foi registrado.')
            if job.get('sections'):
                return self.update(identifier, status='review', error=None, message='Nota preservada, pronta para revisar e continuar o envio.')
            if sum(j['status'] in ACTIVE for j in self.jobs.values()) >= 5:
                raise CaptureError('Fila cheia.')
            self.update(identifier, status='queued', error=None)
            self.futures[identifier] = self.executor.submit(self._run, identifier)
            return self.get(identifier)

    def publish(self, identifier):
        with self.lock:
            job = self.get(identifier)
            if job['status'] == 'completed':
                return job
            if job['status'] != 'review' or job.get('notionState') in ('pending', 'uncertain'):
                raise CaptureError('Revise a nota e confira qualquer entrega incerta antes de publicar.')
            self._render(identifier)
            self.update(identifier, status='publishing', message='Enviando a nota revisada')
            self.futures[identifier] = self.executor.submit(self._publish, identifier)
            return self.get(identifier)

    def _publish(self, identifier):
        try:
            job = self.get(identifier)
            receipts = job['receipts']
            if job['destination'] in ('obsidian', 'both') and 'obsidian' not in receipts:
                folder = self.export_root / job['note']['folder']
                resolved_root = self.export_root.resolve()
                if not folder.resolve().is_relative_to(resolved_root):
                    raise CaptureError('Destino fora da biblioteca.')
                for parent in (self.export_root, *folder.parents, folder):
                    if parent.exists() and (parent.is_symlink() or parent.is_junction()):
                        raise CaptureError('Atalhos de pasta não são aceitos para exportação.')
                folder.mkdir(parents=True, exist_ok=True)
                title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '-', job['note']['title']).strip(' .')[:90] or 'Nota'
                target = folder / f'{title} - {identifier}.md'
                content = job['markdown'].encode('utf-8')
                if target.exists():
                    if target.read_bytes() != content:
                        raise CaptureError('Arquivo existente diferente. Nada foi sobrescrito.')
                else:
                    with target.open('xb') as stream:
                        stream.write(content)
                if target.read_bytes() != content:
                    raise CaptureError('Falha na conferência da nota salva.')
                relative = target.relative_to(VAULT).as_posix() if target.is_relative_to(VAULT) else target.name
                receipts['obsidian'] = dict(path=str(target), sha256=sha256(content).hexdigest(), url='obsidian://open?vault=Repositorio&file=' + quote(relative, safe=''))
                self.update(identifier, receipts=receipts)
            if job['destination'] in ('notion', 'both') and 'notion' not in receipts:
                self.update(identifier, notionState='pending')
                body = job['markdown'].split('---', 2)[2].lstrip().split('\n', 1)[1]
                page = self.publisher(job['note']['title'], body, identifier, self.root / identifier,
                                      source_url=job['source'] if job['type'] in ('video', 'link') else '',
                                      content_type='Vídeo' if job['type'] == 'video' else 'Markdown' if job['type'] in ('idea', 'document') else 'Artigo')
                receipts['notion'] = page
                self.update(identifier, receipts=receipts, notionState='published')
            self.update(identifier, status='completed', message='Entrega confirmada nos destinos selecionados.', error=None)
        except Exception as error:
            job = self.get(identifier)
            self.update(identifier, status='failed', notionState='uncertain' if job.get('notionState') == 'pending' else job.get('notionState', 'none'),
                        error=str(error) if isinstance(error, CaptureError) else 'Entrega não confirmada. Confira os destinos; comprovantes preservados.', message='Precisa de atenção')

    def close(self):
        self.executor.shutdown(wait=False, cancel_futures=True)
