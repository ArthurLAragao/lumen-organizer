"""Persistent capture inbox, one bounded worker, explicit Notion publication."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import RLock
import uuid

from .capture import CaptureError, process_video, video_id


class CaptureInbox:
    def __init__(self, directory, processor=process_video, publisher=None):
        self.root = Path(directory)
        self.root.mkdir(parents=True, exist_ok=True)
        self.processor = processor
        self.publisher = publisher
        self.lock = RLock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='lumen-capture')
        self.jobs = {}
        self.closed = False
        for path in self.root.glob('*/estado.json'):
            try:
                job = json.loads(path.read_text(encoding='utf-8'))
                if job['state'] in ('queued', 'running'):
                    job.update(state='failed', message='Processamento interrompido. Envie a URL novamente.')
                if job.get('publication') == 'pending':
                    job.update(publication='uncertain', message='Publicação interrompida. Confira a biblioteca antes de repetir.')
                self.jobs[job['id']] = job
            except (ValueError, KeyError, OSError):
                continue

    def _save(self, job):
        directory = self.root / job['id']
        directory.mkdir(exist_ok=True)
        temporary = directory / 'estado.tmp'
        temporary.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(directory / 'estado.json')

    def list(self):
        with self.lock:
            return [dict(job) for job in reversed(list(self.jobs.values()))]

    def get(self, identifier):
        with self.lock:
            if identifier not in self.jobs:
                raise CaptureError('Captura não encontrada.')
            return dict(self.jobs[identifier])

    def submit(self, url, title='', transcript=None):
        identifier = video_id(url)
        with self.lock:
            if self.closed:
                raise CaptureError('Caixa de entrada encerrada.')
            for job in self.jobs.values():
                if job['video_id'] == identifier and job['state'] in ('queued', 'running', 'ready'):
                    return dict(job)
            if sum(job['state'] in ('queued', 'running') for job in self.jobs.values()) >= 5:
                raise CaptureError('A fila está cheia. Aguarde uma captura terminar.')
            job = dict(id=uuid.uuid4().hex, video_id=identifier, url=url,
                       title=' '.join(title.split())[:200] or f'Vídeo {identifier}', state='queued',
                       message='Aguardando processamento', publication='none',
                       created=datetime.now(timezone.utc).isoformat())
            self.jobs[job['id']] = job
            self._save(job)
            self.executor.submit(self._run, job['id'], transcript)
            return dict(job)

    def _update(self, identifier, **values):
        with self.lock:
            self.jobs[identifier].update(values)
            self._save(self.jobs[identifier])

    def _run(self, identifier, transcript):
        job = self.get(identifier)
        self._update(identifier, state='running', message='Iniciando captura')
        try:
            result = self.processor(job['url'], job['title'], self.root / identifier / 'conteudo',
                transcript=transcript, progress=lambda message: self._update(identifier, message=message))
            self._update(identifier, state='ready', message='Formato válido; revisão factual pendente.',
                         validation=result['validation'], exercise=result.get('exercise', ''))
        except CaptureError as error:
            self._update(identifier, state='failed', message=str(error))
        except Exception:
            self._update(identifier, state='failed', message='Falha inesperada. A fonte já obtida foi preservada.')
        else:
            if self.publisher:
                self._update(identifier, publication='pending', message='Nota válida; publicando rascunho no Notion')
                try:
                    # Deterministic metadata remains in the local original; Notion receives the body.
                    body = self.note(identifier).split('---', 2)[2].lstrip().split('\n', 1)[1]
                    page = self.publisher(job['title'], body, identifier, self.root / identifier)
                    self._update(identifier, publication='published', notion_id=page['id'], notion_url=page['url'],
                                 message='Rascunho publicado no Notion; revisão factual pendente.')
                except Exception:
                    self._update(identifier, publication='uncertain', message='Nota local pronta. Publicação Notion não confirmada; confira a biblioteca.')

    def note(self, identifier):
        if self.get(identifier)['state'] != 'ready':
            raise CaptureError('A nota ainda não está pronta.')
        return (self.root / identifier / 'conteudo' / 'nota.md').read_text(encoding='utf-8')

    def publish(self, identifier, token, parent_id, reviewed=False):
        from .notion_publish import publish_note
        from .validation import validate_file
        with self.lock:
            job = self.get(identifier)
            if not reviewed or job['state'] != 'ready':
                raise CaptureError('Revise a nota antes de publicar no Notion.')
            if job['publication'] == 'published':
                return job['notion_url']
            if job['publication'] != 'none':
                raise CaptureError('Entrega anterior incerta ou em andamento. Confira o Notion antes de repetir.')
            if not token or not parent_id:
                raise CaptureError('Conecte o destino do Notion primeiro.')
            source = self.root / identifier / 'conteudo' / 'nota.md'
            validation = validate_file(source)
            if not validation.valid:
                raise CaptureError('A nota foi alterada e não passou na validação. Publicação bloqueada.')
            content = self.note(identifier)
            self._update(identifier, publication='pending')
        try:
            page = publish_note(job['title'], content, token, parent_id)
        except Exception:
            self._update(identifier, publication='uncertain', message='Entrega ao Notion não confirmada. Confira o destino antes de repetir.')
            raise CaptureError('Entrega ao Notion não confirmada; não será repetida automaticamente.') from None
        self._update(identifier, publication='published', notion_url=page['url'], notion_id=page['id'], message='Publicação verificada no Notion.')
        return page['url']

    def close(self):
        self.closed = True
        self.executor.shutdown(wait=False, cancel_futures=True)
