"""Separate export window. Filesystem work uses the existing queue worker."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .export_workflow import ExportWorkflow
from .worker import Worker
from .destinations import CHOOSABLE
from .models import LumenError
from .presentation import CATEGORY_LABELS, issue_text, message
from .styles import COLORS
from .ui import readonly_text, replace_text, ScrollableForm


def export_message(code):
    return {
        "export_selection_required": "Selecione o vault, a nota e a categoria da pasta de origem.",
        "export_validation_failed": "A nota não é elegível. Valide novamente; exige reviewed e true booleano.",
        "identity_registration_required": "Registre explicitamente a identidade desta nova nota.",
        "export_registry_unavailable": "Registro indisponível. Preserve os arquivos locais e confira o registro.",
        "export_source_changed": "A origem mudou após a prévia. Valide e prepare novamente.",
        "export_package_collision": "O destino já existe. Escolha outro nome; nenhum arquivo será sobrescrito.",
        "package_destination_forbidden": "Escolha um destino fora do vault e do registro privado.",
        "package_filename": "Use um nome válido terminado em .lumen-atlas.json.",
        "export_copy_failed": "A cópia falhou. O pacote retido pode ser salvo sem gerar outra exportação.",
        "export_reconciliation_required": "Confira o registro antes de continuar. Não repita a exportação às cegas.",
        "export_confirmation_stale": "A confirmação venceu. Prepare e revise novamente.",
    }.get(code, message(code) if code else "")


class ExportWindow:
    def __init__(self, app, local_directory):
        self.app, self.theme = app, app.theme
        self.workflow = ExportWorkflow(local_directory)
        self.worker = Worker()
        self.window = tk.Toplevel(app.root)
        self.window.title("Lumen — Exportar para Atlas")
        self.window.configure(background=COLORS["background"])
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(1, weight=1)
        self.closed = self.closing = False
        self.dialog = None
        self.preview_generation = 0
        self.preview_after_id = None
        self._preview_note = None
        self.window.protocol("WM_DELETE_WINDOW", self.cancel)
        t = self.theme
        header = ttk.Frame(self.window, padding=t.pad(24, 12))
        header.grid(sticky="ew")
        ttk.Label(header, text="Exportar para Atlas", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="Pacote manual de uma nota autorizada. Separado da importação para o Obsidian.", style="Muted.TLabel").pack(anchor="w")
        body = ttk.Frame(self.window, padding=t.pad(24, 12))
        body.grid(row=1, sticky="nsew")
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        form = ScrollableForm(body, t)
        form.grid(row=0, column=0, sticky="nsew", padx=(0, t.px(20)))
        left = form.content
        left.columnconfigure(0, weight=1)
        self.vault_var = tk.StringVar(value="Nenhum vault selecionado")
        self.source_var = tk.StringVar(value="Nenhuma nota selecionada")
        self.folder_var = tk.StringVar()
        self.category_var = tk.StringVar()
        self.baseline_var = tk.StringVar(value="Sem baseline")
        ttk.Label(left, text="Origem autorizada", style="Section.TLabel").grid(row=0, sticky="w")
        self.vault_entry = ttk.Entry(left, textvariable=self.vault_var, state="readonly", width=1)
        self.vault_entry.grid(row=1, sticky="ew", pady=t.px(8))
        self.vault_button = ttk.Button(left, text="Selecionar vault de origem", command=self.choose_vault)
        self.vault_button.grid(row=2, sticky="ew")
        self.source_entry = ttk.Entry(left, textvariable=self.source_var, state="readonly", width=1)
        self.source_entry.grid(row=3, sticky="ew", pady=t.px(8))
        self.file_button = ttk.Button(left, text="Selecionar nota para exportação", command=self.choose_file)
        self.file_button.grid(row=4, sticky="ew")
        ttk.Label(left, text="Categoria da pasta onde a nota já está").grid(row=5, sticky="w", pady=(t.px(12), 0))
        self.category_box = ttk.Combobox(left, textvariable=self.category_var, values=tuple(CATEGORY_LABELS.values()), state="readonly", width=24)
        self.category_box.grid(row=6, sticky="ew", pady=t.px(8))
        self.category_box.bind("<<ComboboxSelected>>", self.selection_changed)
        self.folder_entry = ttk.Entry(left, textvariable=self.folder_var, state="readonly", width=1)
        self.folder_entry.grid(row=7, sticky="ew")
        self.folder_button = ttk.Button(left, text="Escolher subpasta existente", command=self.choose_folder)
        self.folder_button.grid(row=8, sticky="ew", pady=t.px(8))
        self.validate_button = ttk.Button(left, text="Validar exportação", command=lambda: self.act(self.workflow.validate))
        self.validate_button.grid(row=9, sticky="ew")
        ttk.Separator(left).grid(row=10, sticky="ew", pady=t.px(16))
        self.registry_button = ttk.Button(left, text="Criar registro local novo", command=self.create_registry)
        self.registry_button.grid(row=11, sticky="ew")
        self.identity_button = ttk.Button(left, text="Registrar identidade de nova nota", command=self.register)
        self.identity_button.grid(row=12, sticky="ew", pady=t.px(8))
        ttk.Label(left, text="Referência anterior (escolha explícita)").grid(row=13, sticky="w")
        self.baseline_box = ttk.Combobox(left, textvariable=self.baseline_var, state="readonly", width=24)
        self.baseline_box.grid(row=14, sticky="ew", pady=t.px(8))
        self.baseline_box.bind("<<ComboboxSelected>>", self.baseline_changed)
        self.prepare_button = ttk.Button(left, text="Preparar versão selecionada", command=lambda: self.act(self.workflow.prepare))
        self.prepare_button.grid(row=15, sticky="ew")
        self.destination_button = ttk.Button(left, text="Escolher destino do pacote", command=self.choose_destination)
        self.destination_button.grid(row=16, sticky="ew", pady=t.px(8))
        right = ttk.Frame(body)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)
        self.status_var = tk.StringVar()
        status_label = ttk.Label(right, textvariable=self.status_var, wraplength=t.px(540), style="Section.TLabel")
        status_label.grid(row=0, sticky="ew")
        right.bind("<Configure>", lambda e: status_label.configure(wraplength=max(t.px(180), e.width)))
        self.metadata = readonly_text(right, height=6, role="ui")
        self.metadata.grid(row=1, sticky="ew", pady=t.px(12))
        tabs = ttk.Notebook(right)
        tabs.grid(row=2, sticky="nsew")
        self.preview = readonly_text(tabs, height=10, wrap="none")
        horizontal = ttk.Scrollbar(self.preview.frame, orient="horizontal", command=self.preview.xview)
        horizontal.pack(side="bottom", fill="x", before=self.preview._w)
        self.preview.configure(xscrollcommand=horizontal.set)
        self.issues = readonly_text(tabs, height=8, role="ui")
        tabs.add(self.preview.frame, text="Markdown completo (inerte)")
        tabs.add(self.issues.frame, text="Erros e avisos")
        footer = ttk.Frame(self.window, padding=t.pad(24, 12))
        footer.grid(row=2, sticky="ew")
        footer.columnconfigure(0, weight=1)
        self.destination_var = tk.StringVar(value="Destino não escolhido")
        ttk.Entry(footer, textvariable=self.destination_var, state="readonly", width=1).grid(row=0, columnspan=4, sticky="ew", pady=(0, t.px(8)))
        self.cancel_button = ttk.Button(footer, text="Cancelar etapa", command=lambda: self.act(self.workflow.cancel))
        self.cancel_button.grid(row=1, column=0, sticky="w")
        self.reconcile_button = ttk.Button(footer, text="Conferir registro", command=lambda: self.act(self.workflow.reconcile))
        self.reconcile_button.grid(row=1, column=1, padx=t.px(8))
        self.resend_button = ttk.Button(footer, text="Salvar pacote já preparado", command=self.resend)
        self.resend_button.grid(row=1, column=2, padx=t.px(8))
        self.review_button = ttk.Button(footer, text="Revisar exportação", command=lambda: self.act(self.workflow.review), style="Primary.TButton")
        self.review_button.grid(row=1, column=3)
        ttk.Label(footer, text="Importar ≠ revisar conteúdo ≠ autorizar exportação. Nenhuma propriedade será alterada.", style="Muted.TLabel").grid(row=2, columnspan=4, sticky="w", pady=(t.px(8), 0))
        self.controls = [self.vault_button, self.file_button, self.category_box, self.folder_button,
                         self.validate_button, self.registry_button, self.identity_button, self.baseline_box,
                         self.prepare_button, self.destination_button, self.review_button, self.cancel_button,
                         self.reconcile_button, self.resend_button]
        self.theme.fit_window(self.window, (1180, 800), (900, 620))
        self.render()
        self.poll_id = self.window.after(40, self.poll)

    def act(self, action):
        try:
            job = action()
            if job:
                self.worker.submit(job)
            self.render()
        except LumenError as exc:
            self.workflow.error = exc.code
            self.render()

    def category(self):
        return next((key for key, text in CATEGORY_LABELS.items() if text == self.category_var.get()), None)

    def selection_changed(self, _event=None):
        self.act(lambda: self.workflow.select(source=Path(self.source_var.get()) if self.workflow.source else None,
                                             category=self.category(), subfolder=None))
        self.folder_var.set("")

    def choose_vault(self):
        path = filedialog.askdirectory(parent=self.window, title="Vault de origem", mustexist=True)
        if path:
            self.vault_var.set(path)
            self.source_var.set("Nenhuma nota selecionada")
            self.category_var.set("")
            self.folder_var.set("")
            self.act(lambda: self.workflow.configure(Path(path)))
        else:
            self.act(self.workflow.cancel)

    def choose_file(self):
        path = filedialog.askopenfilename(parent=self.window, title="Nota autorizada para Atlas", filetypes=(("Markdown", "*.md"),))
        if path:
            self.source_var.set(path)
            self.act(lambda: self.workflow.select(source=Path(path), category=self.category(), subfolder=self.workflow.subfolder))
        else:
            self.act(self.workflow.cancel)

    def choose_folder(self):
        if self.category() not in CHOOSABLE or not self.workflow.policy:
            return
        base = self.workflow.policy.root / CHOOSABLE[self.category()]
        path = filedialog.askdirectory(parent=self.window, initialdir=str(base), title="Escolha explicitamente uma subpasta existente", mustexist=True)
        if path:
            try:
                relative = Path(path).relative_to(base).as_posix()
            except ValueError:
                self.workflow.error = "outside_vault"
                self.render()
                return
            self.folder_var.set(relative)
            self.act(lambda: self.workflow.select(source=self.workflow.source, category=self.category(), subfolder=relative))
        else:
            self.act(self.workflow.cancel)

    def create_registry(self):
        if messagebox.askyesno("Criar registro local novo", "Crie somente se este é seu primeiro registro. Se perdeu um registro anterior, cancele e recupere-o: criar outro pode gerar outra identidade. Não altera notas nem declara revisão humana.", parent=self.window, default="no"):
            self.act(lambda: self.workflow.create_registry(confirmed=True))

    def register(self):
        if messagebox.askyesno("Registrar nova nota", "Confirmar que esta é uma nova nota? Se a nota foi movida ou seu registro foi perdido, cancele e recupere a vinculação explícita. Nenhum UUID será inserido no Markdown.", parent=self.window, default="no"):
            self.act(lambda: self.workflow.register(confirmed=True))

    def baseline_changed(self, _event=None):
        self.workflow._available()
        index = self.baseline_box.current()
        self.workflow.baseline = self.workflow.records[index - 1].id if index > 0 else None
        self.workflow.revision += 1
        self.workflow.plan = self.workflow.confirmation = None
        self.workflow.status = "Baseline escolhido explicitamente; isso não confirma entrega ao Atlas. Prepare novamente."
        self.render()

    def choose_destination(self):
        path = filedialog.asksaveasfilename(parent=self.window, title="Destino do pacote (sem sobrescrita)",
            defaultextension=".lumen-atlas.json", initialfile="nota.lumen-atlas.json", confirmoverwrite=False,
            filetypes=(("Pacote Lumen", "*.lumen-atlas.json"),))
        self.act(lambda: self.workflow.set_destination(path or None))

    def resend(self):
        if messagebox.askyesno("Salvar pacote retido", "Salvar exatamente a versão já preparada no destino exibido? A origem atual não será lida, não será gerada outra exportação e a entrega continua desconhecida.", parent=self.window, default="no"):
            self.act(lambda: self.workflow.resend(confirmed=True))

    def summary(self):
        w = self.workflow
        p = w.plan
        if not p:
            return "Nenhuma versão preparada."
        return ("Título: " + p.note.metadata["title"] + "\nIdentidade: " + p.integration_id +
                "\nSHA-256 da origem: " + p.note.fingerprint + "\nOrigem: " + str(p.note.source) +
                "\nDestino completo: " + str(w.destination) + "\nBaseline: " + (p.baseline_export_id or "nenhum") +
                "\n\nReferências anteriores não comprovam recebimento. Os links do Obsidian podem não resolver no Atlas.\n\nAvisos:\n" +
                ("\n".join(issue_text(issue) for issue in p.note.warnings) or "Nenhum aviso editorial."))

    def show_confirmation(self, review):
        dialog = tk.Toplevel(self.window)
        dialog.title("Confirmar exportação")
        dialog.transient(self.window)
        dialog.configure(background=COLORS["background"])
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)
        frame = ttk.Frame(dialog, padding=self.theme.pad(24, 16))
        frame.grid(sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        text = readonly_text(frame, height=15, role="ui")
        text.grid(row=0, sticky="nsew")
        replace_text(text, self.summary() + "\n\nO pacote será apenas preparado; a importação no Atlas continua não confirmada.")
        buttons = ttk.Frame(frame)
        buttons.grid(row=1, sticky="e", pady=(self.theme.px(12), 0))
        def finish(approved):
            dialog.grab_release()
            dialog.destroy()
            self.dialog = None
            self.act(lambda: self.workflow.commit(review, confirmed=approved))
        self.confirm_cancel_button = ttk.Button(buttons, text="Cancelar", command=lambda: finish(False))
        self.confirm_cancel_button.pack(side="left")
        self.confirm_button = ttk.Button(buttons, text="Confirmar exportação", style="Primary.TButton", command=lambda: finish(True))
        self.confirm_button.pack(side="left", padx=self.theme.px(12))
        dialog.protocol("WM_DELETE_WINDOW", lambda: finish(False))
        dialog.bind("<Escape>", lambda _event: finish(False))
        self.theme.fit_window(dialog, (790, 600), (620, 440))
        dialog.grab_set()
        buttons.winfo_children()[0].focus_set()
        self.dialog = dialog

    def render(self):
        w = self.workflow
        busy = w.active is not None
        for widget in self.controls:
            widget.configure(state="disabled" if busy else "readonly" if isinstance(widget, ttk.Combobox) else "normal")
        def enable(widget, condition):
            if not busy:
                widget.configure(state="normal" if condition else "disabled")
        valid = bool(w.validation and w.validation.valid)
        enable(self.registry_button, w.policy is not None and w.registry is None)
        enable(self.identity_button, valid and w.exporter is not None and w.identity is None)
        enable(self.validate_button, w.policy is not None and w.source is not None and bool(w.category))
        enable(self.prepare_button, valid and w.identity is not None and not w.halted)
        enable(self.destination_button, w.plan is not None or w.archive_id is not None)
        enable(self.review_button, w.plan is not None and w.destination is not None and not w.halted and w.archive_id is None)
        enable(self.reconcile_button, w.exporter is not None)
        enable(self.resend_button, w.archive_id is not None and not w.halted and w.output is None and w.destination is not None)
        enable(self.folder_button, self.category() in CHOOSABLE and w.policy is not None)
        self.status_var.set("Aguarde — operação em andamento…" if busy else w.status)
        self.destination_var.set(str(w.output or w.destination or "Destino não escolhido"))
        labels = ["Sem baseline"] + [r.id + " | " + r.comparison_sha256[:12] for r in w.records]
        self.baseline_box.configure(values=labels)
        if not w.baseline:
            self.baseline_var.set("Sem baseline")
        meta = ("Elegibilidade: " + ("elegível" if valid else "a validar / bloqueada") +
                "\nIdentidade: " + (w.identity.integration_id if w.identity else "não registrada") +
                "\nTítulo: " + (w.validation.note.metadata["title"] if valid else "—") +
                "\nExige status: reviewed e lumen_export: true booleano. Nenhuma propriedade é alterada.")
        replace_text(self.metadata, meta)
        issues = []
        if w.validation:
            issues = ["ERRO: " + issue_text(i) if i.severity == "error" else "AVISO: " + issue_text(i) for i in w.validation.issues]
        if w.error:
            issues.append(export_message(w.error))
        replace_text(self.issues, "\n\n".join(issues) or "Nenhum diagnóstico nesta etapa.")
        note = w.validation.note if valid else None
        if note is not self._preview_note:
            self._preview_note = note
            self.preview_generation += 1
            generation = self.preview_generation
            self.preview.configure(state="normal")
            self.preview.delete("1.0", "end")
            self.preview.configure(state="disabled")
            text = note.data.decode("utf-8") if note else "Selecione e valide uma nota autorizada."
            def insert(offset=0):
                self.preview_after_id = None
                if self.closed or generation != self.preview_generation:
                    return
                self.preview.configure(state="normal")
                self.preview.insert("end", text[offset:offset + 32768])
                self.preview.configure(state="disabled")
                if offset + 32768 < len(text):
                    self.preview_after_id = self.window.after(1, lambda: insert(offset + 32768))
            insert()

    def poll(self):
        if self.closed:
            return
        for completion in self.worker.drain():
            self.workflow.complete(completion.job, completion.value, completion.error_code)
            self.render()
            if self.workflow.confirmation and not self.dialog:
                self.show_confirmation(self.workflow.confirmation)
        if self.closing and self.workflow.active is None:
            self.destroy()
            return
        self.poll_id = self.window.after(40, self.poll)

    def cancel(self):
        if self.dialog:
            self.dialog.event_generate("<Escape>")
        if self.workflow.active:
            self.closing = True
            self.workflow.status = "Aguarde a conclusão da operação antes de fechar."
        else:
            self.destroy()

    def destroy(self):
        self.closed = True
        self.preview_generation += 1
        self.worker.close()
        if self.preview_after_id is not None:
            self.window.after_cancel(self.preview_after_id)
        self.window.after_cancel(self.poll_id)
        self.window.destroy()
        self.app.export_window = None
        self.app.export_button.focus_set()
