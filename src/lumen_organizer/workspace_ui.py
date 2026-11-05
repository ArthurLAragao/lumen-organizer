"""One Lumen window: capture, library, file organizer and personal context."""
from .public_config import NOTION_LIBRARY_URL
import os
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
import webbrowser

from .ui import App
from .capture_ui import CaptureWindow
from .agent_context import initialize, append_entry, build_context, CONTEXT_ROOT

LIBRARY = NOTION_LIBRARY_URL


def launch_workspace(local_directory):
    root = tk.Tk()
    create_workspace(root, local_directory)
    root.mainloop()


def create_workspace(root, local_directory, *, load_settings=True):
    notebook = ttk.Notebook(root)
    capture_tab, library_tab, organizer_tab, context_tab = [ttk.Frame(notebook) for _ in range(4)]
    app = App(root, Path(local_directory), content_parent=organizer_tab, load_settings=load_settings)
    app.workspace_notebook = notebook
    root.title('Lumen · Seu espaço de conhecimento')
    interface_path = Path(__file__).resolve().parents[2] / 'tools' / 'open_interface.py'
    if (interface_path.parents[1] / 'frontend' / 'dist' / 'index.html').is_file():
        interface_bar = ttk.Frame(root, padding=(16, 8))
        interface_bar.pack(fill='x')
        ttk.Label(interface_bar, text='Lumen · Captura, revisão e envio reais', style='Muted.TLabel').pack(side='left')
        ttk.Button(interface_bar, text='Abrir nova interface', command=lambda: subprocess.Popen(
            [sys.executable, str(interface_path)], creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))).pack(side='right')
    notebook.pack(fill='both', expand=True, padx=12, pady=12)
    for tab, title in [(capture_tab, '  Capturar  '), (library_tab, '  Biblioteca  '),
                       (organizer_tab, '  Arquivos  '), (context_tab, '  Contexto dos agentes  ')]:
        notebook.add(tab, text=title)
    app.capture_window = CaptureWindow(app, parent=capture_tab)
    build_library(library_tab)
    build_context_panel(context_tab, app)
    notebook.select(capture_tab)
    app.theme.fit_window(root, (1180, 820), (860, 640))
    return app


def build_library(parent):
    pane = ttk.Frame(parent, padding=32)
    pane.pack(fill='both', expand=True)
    ttk.Label(pane, text='Conhecimento que você pode revisitar.', style='Title.TLabel').pack(anchor='w', pady=(0, 16))
    ttk.Label(pane, text='Seus resumos, fontes e práticas ficam na Biblioteca Lumen do Notion.', wraplength=700).pack(anchor='w')
    ttk.Button(pane, text='Abrir biblioteca no Notion', style='Primary.TButton',
               command=lambda: os.startfile(LIBRARY)).pack(anchor='w', pady=24)
    ttk.Button(pane, text='Abrir no navegador', command=lambda: webbrowser.open(LIBRARY.replace('notion://', 'https://'))).pack(anchor='w')
    ttk.Label(pane, text='No celular, abra a mesma conta do Notion. A biblioteca acompanha a sincronização do próprio Notion.', wraplength=700, style='Muted.TLabel').pack(anchor='w', pady=24)


def build_context_panel(parent, app):
    frame = ttk.Frame(parent, padding=24)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='Um contexto que evolui com você.', style='Title.TLabel').pack(anchor='w', pady=(0, 12))
    ttk.Label(frame, text='Registre preferências, decisões e o que fez hoje. Apenas esta pasta de contexto é usada; seu acervo não é varrido.', wraplength=900).pack(anchor='w')
    editor = ScrolledText(frame, height=8, wrap='word', **app.theme.text_options('ui'))
    editor.pack(fill='both', expand=True, pady=16)
    status = tk.StringVar(value='Nada é enviado automaticamente para uma IA.')
    buttons = ttk.Frame(frame); buttons.pack(fill='x')
    def save():
        try:
            target = append_entry(editor.get('1.0', 'end'))
            editor.delete('1.0', 'end')
            status.set('Registro salvo no Obsidian: ' + target.name)
        except (OSError, ValueError) as error:
            status.set(str(error))
    def prepare():
        try:
            text = build_context()
            output = app.export_local / 'contexto-agentes.md'
            output.write_text(text, encoding='utf-8')
            preview = tk.Toplevel(app.root)
            preview.title('Revisar contexto antes de compartilhar')
            preview.geometry('800x650')
            content = ScrolledText(preview, wrap='word', **app.theme.text_options('ui'))
            content.pack(fill='both', expand=True)
            content.insert('1.0', text); content.configure(state='disabled')
            def copy():
                app.root.clipboard_clear(); app.root.clipboard_append(text)
                status.set('Contexto copiado. Compartilhe somente com o agente escolhido por você.')
            ttk.Button(preview, text='Copiar contexto revisado', command=copy).pack(pady=12)
        except OSError as error:
            status.set('Não foi possível preparar o contexto: ' + str(error))
    ttk.Button(buttons, text='Salvar no Obsidian', command=save, style='Primary.TButton').pack(side='left')
    ttk.Button(buttons, text='Preparar contexto para agente', command=prepare).pack(side='left', padx=12)
    ttk.Button(buttons, text='Abrir no Obsidian', command=lambda: os.startfile('obsidian://open?vault=Repositorio&file=00%20-%20Contexto%20dos%20agentes%2FPerfil')).pack(side='left')
    ttk.Label(frame, textvariable=status, wraplength=900, style='Muted.TLabel').pack(anchor='w', pady=12)
