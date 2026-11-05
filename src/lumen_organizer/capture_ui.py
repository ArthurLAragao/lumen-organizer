"""Capture desk: worker results are polled on Tk's thread."""
from .public_config import NOTION_LIBRARY_URL
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
from queue import Queue, Empty
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText

from .capture import CaptureError
from .capture_service import CaptureInbox
from .capture_bridge import start_bridge
from .notion_connected import publish_connected
from .styles import COLORS


class CaptureWindow:
    def __init__(self, app, parent=None):
        self.app = app
        self.embedded = parent is not None
        self.window = parent if self.embedded else tk.Toplevel(app.root)
        if not self.embedded:
            self.window.title('Lumen — Captura e revisão')
            self.window.geometry('980x760')
        self.inbox = CaptureInbox(app.export_local / 'capturas', publisher=publish_connected)
        self.publisher = ThreadPoolExecutor(max_workers=1)
        self.results = Queue()
        self.actions = Queue()
        self.publishing = False
        self.bridge = None
        self.selected = None
        self.last_preview = None
        self.closed = False
        if not self.embedded:
            self.window.protocol('WM_DELETE_WINDOW', self.close)
        frame = ttk.Frame(self.window, padding=16)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Transforme uma ideia em conhecimento.', style='Title.TLabel').pack(anchor='w', pady=(0, 8))
        ttk.Label(frame, text='Usa seu Codex/ChatGPT e publica um rascunho na Biblioteca Lumen do Notion, sem API paga.').pack(anchor='w')
        ttk.Label(frame, text='URL do YouTube').pack(anchor='w')
        self.url = ttk.Entry(frame); self.url.pack(fill='x')
        ttk.Label(frame, text='Título (opcional)').pack(anchor='w')
        self.title = ttk.Entry(frame); self.title.pack(fill='x')
        actions = ttk.Frame(frame); actions.pack(fill='x', pady=8)
        ttk.Button(actions, text='Capturar e resumir', style='Primary.TButton', command=self.submit).pack(side='left')
        ttk.Button(actions, text='Abrir cópia Markdown', command=self.open_note).pack(side='left', padx=8)
        ttk.Button(actions, text='Abrir no Notion', command=self.open_notion).pack(side='left')
        self.technical = tk.BooleanVar(value=False)
        ttk.Checkbutton(actions, text='Detalhes técnicos', variable=self.technical, command=self.refresh_preview).pack(side='right')
        self.status = tk.StringVar(value='Pronto para capturar.')
        self.listbox = tk.Listbox(frame, height=3, **app.theme.list_options())
        self.listbox.pack(fill='x'); self.listbox.bind('<<ListboxSelect>>', self.select)
        self.preview = ScrolledText(frame, wrap='word', height=5, state='disabled', **app.theme.text_options('ui'))
        self.preview.pack(fill='both', expand=True, pady=8)
        self.preview.configure(state='normal')
        self.preview.insert('1.0', 'Seu conhecimento, em um só lugar.\n\nCole a URL de um vídeo para começar.\n\nO Lumen prepara um resumo em português, sugere uma prática e salva uma nota na sua biblioteca do Notion.\n\nSelecione uma captura para ler o resultado aqui. Os arquivos originais continuam disponíveis na aba Arquivos; seu contexto pessoal fica na aba Contexto dos agentes.')
        self.preview.configure(state='disabled')
        ttk.Label(frame, textvariable=self.status, wraplength=920).pack(anchor='w')
        self.reviewed = tk.BooleanVar(value=False)
        self.advanced = ttk.Frame(frame)
        advanced_visible = tk.BooleanVar(value=False)
        self.advanced_visible = advanced_visible
        def toggle_advanced():
            if advanced_visible.get():
                self.advanced.pack(fill='x')
            else:
                self.advanced.pack_forget()
        self.api_toggle = ttk.Checkbutton(frame, text='Conexão alternativa com o Notion', variable=advanced_visible,
                        command=toggle_advanced)
        ttk.Checkbutton(self.advanced, text='Revisei a nota selecionada e quero publicá-la pela API alternativa', variable=self.reviewed).pack(anchor='w')
        credentials = ttk.Frame(self.advanced); credentials.pack(fill='x', pady=8)
        credentials.columnconfigure(1, weight=1)
        ttk.Label(credentials, text='Token Notion (somente nesta sessão)').grid(row=0, column=0, sticky='w')
        self.token = ttk.Entry(credentials, show='•', width=25)
        self.token.insert(0, os.environ.get('NOTION_TOKEN', '')); self.token.grid(row=0, column=1, sticky='ew', padx=8)
        ttk.Label(credentials, text='ID da página de destino').grid(row=1, column=0, sticky='w')
        self.parent = ttk.Entry(credentials, width=34)
        self.parent.insert(0, os.environ.get('NOTION_PARENT_PAGE_ID', '')); self.parent.grid(row=1, column=1, sticky='ew', padx=8)
        self.publish_button = ttk.Button(self.advanced, text='Publicar nota revisada pela API alternativa', command=self.publish)
        self.publish_button.pack(anchor='w')
        try:
            self.bridge = start_bridge(self.inbox, on_action=self.actions.put)
        except OSError:
            self.status.set('Captura desktop disponível. Ponte Atlas indisponível: porta local já em uso.')
        self.poll()

    def submit(self):
        try:
            job = self.inbox.submit(self.url.get(), self.title.get())
            self.selected = job['id']; self.reviewed.set(False)
        except (CaptureError, ValueError) as error:
            self.status.set(str(error))

    def select(self, _event=None):
        selection = self.listbox.curselection()
        if selection and selection[0] < len(self.rows):
            self.selected = self.rows[selection[0]]['id']
            self.reviewed.set(False)

    def poll(self):
        if self.closed:
            return
        try:
            action = self.actions.get_nowait()
            if action == 'lumen':
                self.app.root.deiconify(); self.app.root.lift()
                if self.embedded:
                    self.app.workspace_notebook.select(self.window)
            else:
                destinations = {'notion': NOTION_LIBRARY_URL,
                    'spotify': 'spotify:', 'obsidian': 'obsidian://open?vault=Repositorio&file=00%20-%20Contexto%20dos%20agentes%2FPerfil',
                    'orca': str(Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Orca' / 'Orca.exe')}
                os.startfile(destinations[action])
        except Empty:
            pass
        except OSError:
            self.status.set('Não foi possível abrir o aplicativo. Confira sua instalação.')
        self.rows = self.inbox.list()
        if self.selected is None and self.rows:
            self.selected = self.rows[0]['id']
        self.listbox.delete(0, 'end')
        for index, job in enumerate(self.rows):
            self.listbox.insert('end', job['title'] + ' — ' + job['message'])
            if job['id'] == self.selected:
                self.listbox.selection_set(index)
        if not self.rows:
            self.listbox.insert('end', 'Nenhuma captura ainda. Cole uma URL para começar.')
        if self.selected:
            job = self.inbox.get(self.selected)
            self.status.set(job['message'])
            key = (self.selected, job['state'])
            if key != self.last_preview:
                self.last_preview = key
                content = self.reading_content(job)
                self.preview.configure(state='normal'); self.preview.delete('1.0', 'end')
                self.preview.insert('1.0', content); self.preview.configure(state='disabled')
                if not self.technical.get():
                    self.preview.tag_configure('headline', font=self.app.theme.fonts['title'], spacing3=16)
                    self.preview.tag_add('headline', '1.0', '1.end')
                    self.preview.tag_configure('section', font=self.app.theme.fonts['section'], foreground=COLORS['accent'], spacing1=16, spacing3=6)
                    for line_number, line in enumerate(content.splitlines(), 1):
                        if line in ('Resumo', 'Explicação', 'Exemplos e aplicação', 'Pontos de atenção', 'Revisão', 'Fontes', 'Registro pessoal'):
                            self.preview.tag_add('section', f'{line_number}.0', f'{line_number}.end')
        try:
            message = self.results.get_nowait()
            self.publishing = False
            self.publish_button.configure(state='normal')
            messagebox.showinfo('Publicação', message, parent=self.window)
        except Empty:
            pass
        self.after = self.window.after(700, self.poll)

    def reading_content(self, job):
        if job['state'] != 'ready':
            return job['message']
        note = self.inbox.note(self.selected)
        if self.technical.get():
            return note
        return readable_note(note)

    def refresh_preview(self):
        self.last_preview = None
        if self.technical.get():
            self.api_toggle.pack(anchor='w')
        else:
            self.api_toggle.pack_forget()
            self.advanced.pack_forget()
            self.advanced_visible.set(False)

    def open_notion(self):
        import webbrowser
        target = self.inbox.get(self.selected).get('notion_url') if self.selected else None
        url = target or NOTION_LIBRARY_URL
        try:
            os.startfile(url.replace('https://', 'notion://', 1))
        except OSError:
            webbrowser.open(url)

    def open_note(self):
        if self.selected:
            try:
                self.inbox.note(self.selected)
                os.startfile(self.inbox.root / self.selected / 'conteudo' / 'nota.md')
            except (OSError, CaptureError) as error:
                self.status.set(str(error))

    def publish(self):
        identifier, token, parent, reviewed = self.selected, self.token.get(), self.parent.get(), self.reviewed.get()
        if not identifier or not token or not parent or not reviewed:
            self.status.set('Selecione e revise uma nota, e informe a conexão do Notion.')
            return
        self.publishing = True
        self.publish_button.configure(state='disabled')
        def work():
            try:
                url = self.inbox.publish(identifier, token, parent, reviewed)
                self.results.put('Publicação verificada: ' + url)
            except CaptureError as error:
                self.results.put(str(error))
        self.publisher.submit(work)

    def close(self):
        if self.publishing or any(job['state'] in ('queued', 'running') or job['publication'] == 'pending' for job in self.inbox.list()):
            self.status.set('Aguarde o processamento terminar antes de fechar.')
            return False
        self.closed = True
        self.window.after_cancel(self.after)
        if self.bridge:
            self.bridge.shutdown(); self.bridge.server_close()
        self.inbox.close(); self.publisher.shutdown(wait=False)
        self.window.destroy()
        self.app.capture_window = None
        return True


def readable_note(note):
    """Reading view only; the original Markdown and validator bytes stay intact."""
    import re
    if note.startswith('---\n'):
        note = note.split('---', 2)[2].lstrip()
    note = re.sub(r'^#{1,6} ', '', note, flags=re.MULTILINE)
    note = re.sub(r'^> ?', '', note, flags=re.MULTILINE)
    note = re.sub(r'\*\*(.*?)\*\*', r'\1', note)
    return note
