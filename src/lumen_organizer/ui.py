"""Portuguese Tkinter desktop. Domain work never runs in widget callbacks."""

from pathlib import Path, PurePosixPath
import tkinter as tk
from tkinter import filedialog, ttk
from tkinter.scrolledtext import ScrolledText

from .controller import Controller, Confirmation
from .destinations import CHOOSABLE
from .models import LumenError
from .presentation import CATEGORY_LABELS, STATUSES, issue_text, message, result_text, visual_status
from .styles import COLORS, VisualStyle
from .worker import Worker

LIFECYCLE = "Importação ≠ revisão do conteúdo ≠ autorização de exportação · status: inbox · lumen_export: false."


def readonly_text(parent, *, height=4, wrap="word", role="mono"):
    theme = parent._root().lumen_theme
    text = ScrolledText(parent, height=height, wrap=wrap, state="disabled", takefocus=True,
                        width=1, **theme.text_options(role))
    # ScrolledText's native Tk scrollbar ignores several colors on Windows.
    # Replace it with the existing themed ttk scrollbar, keeping Text inert.
    text.vbar.destroy()
    text.vbar = ttk.Scrollbar(text.frame, command=text.yview)
    text.vbar.pack(side="right", fill="y", before=text._w)
    text.configure(yscrollcommand=text.vbar.set)
    text.frame.configure(background=COLORS["background"])
    text.bind("<Tab>", lambda event: (event.widget.tk_focusNext().focus_set(), "break")[1])
    text.bind("<Shift-Tab>", lambda event: (event.widget.tk_focusPrev().focus_set(), "break")[1])
    def select_all(event):
        text.tag_add("sel", "1.0", "end-1c")
        return "break"
    text.bind("<Control-a>", select_all)
    def copy_selection(_event):
        try:
            selected = text.get("sel.first", "sel.last")
        except tk.TclError:
            return "break"
        text.clipboard_clear()
        text.clipboard_append(selected)
        return "break"
    text.bind("<Control-c>", copy_selection)
    return text


def replace_text(widget, value):
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", value)
    widget.configure(state="disabled")


class ScrollableForm(ttk.Frame):
    """A small destination viewport for limited work areas and large fonts."""

    def __init__(self, parent, theme):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, background=COLORS["background"], borderwidth=0,
                                highlightthickness=0, width=1, height=theme.px(230), takefocus=False)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scroll = ttk.Scrollbar(self, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.content = ttk.Frame(self.canvas)
        self.item = self.canvas.create_window(0, 0, window=self.content, anchor="nw")
        self.canvas.bind("<Configure>", self._resize)
        self.content.bind("<Configure>", self._resize)
        self.canvas.bind("<MouseWheel>", self._wheel)

    def _resize(self, _event=None):
        self.canvas.itemconfigure(self.item, width=max(1, self.canvas.winfo_width()))
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        if self.content.winfo_reqheight() > self.canvas.winfo_height():
            self.scroll.grid(row=0, column=1, sticky="ns")
        else:
            self.scroll.grid_remove()
            self.canvas.yview_moveto(0)

    def _wheel(self, event):
        self.canvas.yview_scroll(-int(event.delta / 120), "units")
        return "break"

    def reveal_focus(self, event):
        widget = event.widget
        top = widget.winfo_y()
        bottom = top + widget.winfo_height()
        height = max(1, self.content.winfo_height())
        visible_top = self.canvas.canvasy(0)
        if top < visible_top:
            self.canvas.yview_moveto(top / height)
        elif bottom > visible_top + self.canvas.winfo_height():
            self.canvas.yview_moveto(max(0, bottom - self.canvas.winfo_height()) / height)


class App:
    def __init__(self, root: tk.Tk, local_directory: Path, *, load_settings=True):
        self.root = root
        self.controller = Controller(local_directory)
        self.export_local = Path(local_directory)
        self.export_window = None
        self.worker = Worker()
        self.closed = self.closing = self._rendering = False
        self._poll_id = None
        self._hooks = {}
        self._preview_key = object()
        self._preview_generation = 0
        self._preview_after_id = None
        self._last_result = None
        self._last_status = None
        self.dialog = None
        root.title("Lumen Organizer")
        self.theme = VisualStyle(root)
        root.lumen_theme = self.theme
        root.protocol("WM_DELETE_WINDOW", self.close_requested)
        root.report_callback_exception = self._callback_error
        self._build()
        self.render()
        self.theme.fit_window(root, (1120, 760), (900, 620))
        # The destination viewport may scroll; keep resizing useful below its
        # preferred height while retaining the fixed header and action area.
        root.minsize(min(self.theme.px(900), root.winfo_screenwidth() - self.theme.px(48)),
                     min(self.theme.px(620), root.winfo_screenheight() - self.theme.px(80)))
        self._poll_id = root.after(40, self.poll)
        if load_settings:
            self.dispatch(self.controller.start_load_settings())

    def _build(self):
        root, theme = self.root, self.theme
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        self.header = ttk.Frame(root, style="Surface.TFrame", padding=theme.pad(24, 12))
        self.header.grid(row=0, sticky="ew")
        self.header.columnconfigure(1, weight=1)
        ttk.Label(self.header, text="Lumen", style="Title.TLabel").grid(row=0, column=0, padx=(0, theme.px(24)))
        self.vault_var = tk.StringVar(value="Nenhum vault configurado")
        self.vault_entry = ttk.Entry(self.header, textvariable=self.vault_var, state="readonly", width=1, takefocus=True, font=theme.fonts["ui"])
        self.vault_entry.grid(row=0, column=1, sticky="ew")
        self.vault_button = ttk.Button(self.header, text="Selecionar vault", command=self.choose_vault)
        self.vault_button.grid(row=0, column=2, padx=(theme.px(12), 0))
        self.export_button = ttk.Button(self.header, text="Exportar para Atlas", command=self.open_export)
        self.export_button.grid(row=0, column=3, padx=(theme.px(12), 0))
        ttk.Separator(root).grid(row=1, sticky="ew")

        self.body = ttk.Frame(root, padding=theme.pad(24, 16))
        self.body.grid(row=2, sticky="nsew")
        self.body.columnconfigure(0, minsize=theme.px(300))
        self.body.columnconfigure(2, weight=1)
        self.body.rowconfigure(0, weight=1)
        self.sidebar = ttk.Frame(self.body)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.columnconfigure(0, weight=1)
        self.sidebar.rowconfigure(2, weight=1)

        source = ttk.Frame(self.sidebar)
        source.grid(row=0, sticky="ew")
        source.columnconfigure(0, weight=1)
        ttk.Label(source, text="01  Nota", style="Section.TLabel").grid(row=0, sticky="w", pady=(0, theme.px(8)))
        self.source_var = tk.StringVar(value="Nenhuma nota selecionada")
        self.source_entry = ttk.Entry(source, textvariable=self.source_var, state="readonly", width=1, takefocus=True, font=theme.fonts["ui"])
        self.source_entry.grid(row=1, sticky="ew")
        selection = ttk.Frame(source)
        selection.grid(row=2, sticky="ew", pady=theme.px(8))
        selection.columnconfigure(0, weight=1)
        self.file_button = ttk.Button(selection, text="Selecionar nota", command=self.choose_file)
        self.file_button.grid(row=0, column=0, sticky="ew", padx=(0, theme.px(8)))
        self.clear_button = ttk.Button(selection, text="Limpar seleção", command=lambda: self.act(self.controller.clear_file))
        self.clear_button.grid(row=0, column=1)
        self.validate_button = ttk.Button(source, text="Validar nota", command=lambda: self.act(self.controller.start_validate))
        self.validate_button.grid(row=3, sticky="ew")
        ttk.Separator(self.sidebar).grid(row=1, sticky="ew", pady=theme.px(16))

        self.destination_form = ScrollableForm(self.sidebar, theme)
        self.destination_form.grid(row=2, sticky="nsew")
        route = self.destination_form.content
        route.columnconfigure(0, weight=1)
        ttk.Label(route, text="02  Destino", style="Section.TLabel").grid(row=0, sticky="w", pady=(0, theme.px(12)))
        ttk.Label(route, text="Categoria").grid(row=1, sticky="w", pady=(0, theme.px(4)))
        self.category_var = tk.StringVar()
        self.category_box = ttk.Combobox(route, textvariable=self.category_var, values=tuple(CATEGORY_LABELS.values()), state="readonly", width=1, font=theme.fonts["ui"])
        self.category_box.grid(row=2, sticky="ew", pady=(0, theme.px(8)))
        self.category_box.bind("<<ComboboxSelected>>", self.category_changed)
        self.folder_var = tk.StringVar(value="")
        self.folder_entry = ttk.Entry(route, textvariable=self.folder_var, state="readonly", width=1, takefocus=True, font=theme.fonts["ui"])
        self.folder_entry.grid(row=3, sticky="ew", pady=(0, theme.px(8)))
        self.folder_button = ttk.Button(self.sidebar, text="Escolher pasta", command=self.choose_folder)
        self.folder_button.grid(row=3, sticky="ew", pady=(theme.px(12), 0))
        ttk.Label(route, text="Nome do arquivo").grid(row=5, sticky="w", pady=(0, theme.px(4)))
        self.filename_var = tk.StringVar()
        self.filename_entry = ttk.Entry(route, textvariable=self.filename_var, width=1, font=theme.fonts["ui"])
        self.filename_entry.grid(row=6, sticky="ew")
        self.filename_var.trace_add("write", self.filename_changed)
        for widget in (self.category_box, self.folder_entry, self.filename_entry):
            widget.bind("<FocusIn>", self.destination_form.reveal_focus, add="+")
        for widget in route.winfo_children():
            widget.bind("<MouseWheel>", self.destination_form._wheel, add="+")
        self.prepare_button = ttk.Button(self.sidebar, text="Preparar destino", command=lambda: self.act(self.controller.start_prepare))
        self.prepare_button.grid(row=4, sticky="ew", pady=(theme.px(12), 0))

        ttk.Separator(self.body, orient="vertical").grid(row=0, column=1, sticky="ns", padx=theme.px(24))
        self.reading_area = ttk.Frame(self.body)
        self.reading_area.grid(row=0, column=2, sticky="nsew")
        self.reading_area.columnconfigure(0, weight=1)
        self.reading_area.rowconfigure(2, weight=1)
        self.status_var = tk.StringVar()
        self.status_label = ttk.Label(self.reading_area, textvariable=self.status_var, style="muted.Status.TLabel",
                                      wraplength=theme.px(620))
        self.status_label.grid(row=0, sticky="ew", pady=(0, theme.px(4)))
        self.count_var = tk.StringVar(value="Erros: —   Avisos: —")
        ttk.Label(self.reading_area, textvariable=self.count_var, style="Muted.TLabel").grid(row=1, sticky="w", pady=(0, theme.px(12)))
        self.tabs = ttk.Notebook(self.reading_area)
        self.tabs.grid(row=2, sticky="nsew")

        preview_page = ttk.Frame(self.tabs)
        preview_page.columnconfigure(0, weight=1)
        preview_page.rowconfigure(0, weight=1)
        self.preview = readonly_text(preview_page, height=10, wrap="none")
        self.preview.grid(row=0, sticky="nsew")
        scroll_x = ttk.Scrollbar(preview_page, orient="horizontal", command=self.preview.xview)
        scroll_x.grid(row=1, sticky="ew")
        self.preview.configure(xscrollcommand=scroll_x.set)
        self.preview_hint = ttk.Label(preview_page, text="Texto completo, incluindo YAML · somente leitura · conteúdo inerte",
                                      style="Muted.TLabel", wraplength=theme.px(600))
        self.preview_hint.grid(row=2, sticky="ew", pady=(theme.px(8), 0))
        self.tabs.add(preview_page, text="Prévia")

        issues_page = ttk.Frame(self.tabs, padding=theme.pad(8))
        issues_page.columnconfigure(0, weight=1)
        issues_page.rowconfigure(1, weight=1)
        issues_page.rowconfigure(3, weight=1)
        ttk.Label(issues_page, text="Erros bloqueantes", style="error.Status.TLabel").grid(row=0, sticky="w")
        self.errors = readonly_text(issues_page, height=3, role="ui")
        self.errors.grid(row=1, sticky="nsew", pady=(theme.px(4), theme.px(12)))
        ttk.Label(issues_page, text="Avisos editoriais", style="warning.Status.TLabel").grid(row=2, sticky="w")
        self.warnings = readonly_text(issues_page, height=3, role="ui")
        self.warnings.grid(row=3, sticky="nsew", pady=(theme.px(4), 0))
        self.tabs.add(issues_page, text="Erros e avisos")

        metadata_page = ttk.Frame(self.tabs, padding=theme.pad(8))
        metadata_page.columnconfigure(0, weight=1)
        metadata_page.rowconfigure(0, weight=1)
        self.metadata = ttk.Treeview(metadata_page, columns=("property", "value"), show="headings", height=8)
        self.metadata.heading("property", text="Propriedade")
        self.metadata.heading("value", text="Valor (resumo)")
        self.metadata.column("property", width=theme.px(155), stretch=False)
        self.metadata.column("value", width=theme.px(250))
        self.metadata.grid(row=0, sticky="nsew")
        metadata_y = ttk.Scrollbar(metadata_page, orient="vertical", command=self.metadata.yview)
        metadata_y.grid(row=0, column=1, sticky="ns")
        metadata_x = ttk.Scrollbar(metadata_page, orient="horizontal", command=self.metadata.xview)
        metadata_x.grid(row=1, sticky="ew")
        self.metadata.configure(yscrollcommand=metadata_y.set, xscrollcommand=metadata_x.set)
        self.metadata_hint = ttk.Label(metadata_page, text="Todos os metadados e valores completos estão no YAML da prévia.",
                                       style="Muted.TLabel", wraplength=theme.px(600))
        self.metadata_hint.grid(row=2, sticky="ew", pady=(theme.px(8), 0))
        self.tabs.add(metadata_page, text="Metadados")

        result_page = ttk.Frame(self.tabs, padding=theme.pad(8))
        result_page.columnconfigure(0, weight=1)
        result_page.rowconfigure(1, weight=1)
        self.result_title_var = tk.StringVar()
        self.result_label = ttk.Label(result_page, textvariable=self.result_title_var, style="Section.TLabel")
        self.result_label.grid(row=0, sticky="w", pady=(0, theme.px(8)))
        self.result_detail = readonly_text(result_page, height=6, role="ui")
        self.result_detail.grid(row=1, sticky="nsew")
        self.tabs.add(result_page, text="Resultado")

        ttk.Separator(root).grid(row=3, sticky="ew")
        self.footer = ttk.Frame(root, padding=theme.pad(24, 12))
        self.footer.grid(row=4, sticky="ew")
        self.footer.columnconfigure(0, weight=1)
        self.destination_var = tk.StringVar()
        self.destination_text = readonly_text(self.footer, height=2, role="ui")
        self.destination_text.grid(row=0, sticky="ew", pady=(0, theme.px(8)))
        actions = ttk.Frame(self.footer)
        actions.grid(row=1, sticky="ew")
        actions.columnconfigure(1, weight=1)
        self.cancel_button = ttk.Button(actions, text="Cancelar etapa", command=lambda: self.act(self.controller.cancel_step))
        self.cancel_button.grid(row=0, column=0, sticky="w")
        self.reconcile_button = ttk.Button(actions, text="Conferir histórico", command=lambda: self.act(self.controller.start_reconcile))
        self.reconcile_button.grid(row=0, column=1, sticky="w", padx=theme.px(12))
        self.import_button = ttk.Button(actions, text="Revisar importação", command=self.confirm_import)
        self.import_button.grid(row=0, column=2, sticky="e")
        self.lifecycle_label = ttk.Label(self.footer, text=LIFECYCLE, style="Muted.TLabel", wraplength=theme.px(1000))
        self.lifecycle_label.grid(row=2, sticky="ew", pady=(theme.px(8), 0))
        self.reading_area.bind("<Configure>", lambda event: self.status_label.configure(wraplength=max(theme.px(300), event.width)))
        preview_page.bind("<Configure>", lambda event: self.preview_hint.configure(wraplength=max(theme.px(300), event.width)))
        metadata_page.bind("<Configure>", lambda event: self.metadata_hint.configure(wraplength=max(theme.px(300), event.width - theme.px(16))))
        self.footer.bind("<Configure>", lambda event: self.lifecycle_label.configure(wraplength=max(theme.px(400), event.width - theme.px(48))))
        root.bind("<Control-o>", lambda event: self.choose_file() if not self.controller.active else None)
        root.bind("<Escape>", lambda event: self.act(self.controller.cancel_step) if self.dialog is None else None)

    def open_export(self):
        if self.export_window is not None:
            self.export_window.window.lift()
            return
        from .export_ui import ExportWindow
        self.export_window = ExportWindow(self, self.export_local)

    def act(self, action):
        try:
            value = action()
            if value is not None:
                self.dispatch(value)
            else:
                self.render()
            return value
        except LumenError as exc:
            self.controller.state.error_code = exc.code
            self.render()
            return None

    def dispatch(self, job, hook=None):
        if hook:
            self._hooks[id(job)] = hook
        self.worker.submit(job)
        self.render()

    def poll(self):
        if self.closed:
            return
        for completion in self.worker.drain():
            accepted = self.controller.complete(completion.job, completion.value, completion.error_code)
            self.render()
            hook = self._hooks.pop(id(completion.job), None)
            if hook:
                hook(accepted)
        if self.closing and self.controller.active is None:
            self.destroy()
            return
        self._poll_id = self.root.after(40, self.poll)

    def choose_vault(self):
        if self.controller.active:
            return
        path = filedialog.askdirectory(parent=self.root, title="Selecione a raiz do vault", mustexist=True)
        self.act(lambda: self.controller.start_configure(Path(path)) if path else self.controller.cancel_configuration())

    def choose_file(self):
        if self.controller.active:
            return
        path = filedialog.askopenfilename(parent=self.root, title="Selecione uma nota Markdown", filetypes=(("Markdown", "*.md"),))
        self.act(lambda: self.controller.select_file(Path(path) if path else None))

    def category_changed(self, _event=None):
        if self._rendering:
            return
        category = next((key for key, label in CATEGORY_LABELS.items() if label == self.category_var.get()), "")
        self.act(lambda: self.controller.set_destination(category=category))

    def filename_changed(self, *_args):
        if not self._rendering:
            self.act(lambda: self.controller.set_destination(filename=self.filename_var.get()))

    def choose_folder(self):
        try:
            self.controller._available()
            self.dialog = FolderDialog(self)
        except LumenError as exc:
            self.controller.state.error_code = exc.code
            self.render()

    def confirm_import(self):
        try:
            confirmation = self.controller.request_confirmation()
            self.dialog = ConfirmationDialog(self, confirmation)
            self.render()
        except LumenError as exc:
            self.controller.state.error_code = exc.code
            self.render()

    def finish_confirmation(self, confirmation, approved):
        self.act(lambda: self.controller.start_import(confirmation, approved))

    def _enabled(self, widget, enabled, readonly=False):
        widget.configure(state=("readonly" if readonly else "normal") if enabled else "disabled")

    def _show_preview(self, note):
        key = (str(note.source), note.fingerprint) if note else None
        if key == self._preview_key:
            return
        self._preview_key = key
        self._preview_generation += 1
        if self._preview_after_id is not None:
            self.root.after_cancel(self._preview_after_id)
            self._preview_after_id = None
        generation = self._preview_generation
        text = note.data.decode("utf-8-sig").replace("\r\n", "\n") if note else "Prévia disponível após a validação estrutural da nota."
        replace_text(self.preview, "")
        # Chunk insertion keeps Tk responsive even for a maximum-size note.
        def append(offset=0):
            self._preview_after_id = None
            if self.closed or generation != self._preview_generation:
                return
            self.preview.configure(state="normal")
            self.preview.insert("end", text[offset:offset + 16384])
            self.preview.configure(state="disabled")
            if offset + 16384 < len(text):
                self._preview_after_id = self.root.after(1, lambda: append(offset + 16384))
            else:
                self.preview.yview_moveto(0)
        append()

    def render(self):
        if self.closed:
            return
        self._rendering = True
        try:
            state = self.controller.state
            idle = state.busy is None and not self.closing
            valid = state.validation is not None and state.validation.valid
            self.vault_var.set(str(state.vault) if state.vault else "Nenhum vault configurado")
            source = str(state.source) if state.source else "Nenhuma nota selecionada"
            if self.source_var.get() != source:
                self.source_var.set(source)
                self.source_entry.xview_moveto(1)
            self.category_var.set(CATEGORY_LABELS.get(state.category, ""))
            if self.filename_var.get() != state.filename:
                self.filename_var.set(state.filename)
            self.folder_var.set("Pasta: " + state.subfolder if state.subfolder else
                                ("Escolha explicitamente uma pasta existente." if state.category in CHOOSABLE else ""))
            self._enabled(self.vault_button, idle)
            self._enabled(self.file_button, idle and state.vault is not None)
            self._enabled(self.validate_button, idle and state.source is not None)
            self._enabled(self.clear_button, idle and state.source is not None)
            self._enabled(self.category_box, idle and valid, readonly=True)
            self._enabled(self.filename_entry, idle and valid)
            self._enabled(self.folder_button, idle and valid and state.category in CHOOSABLE)
            for widget in (self.folder_entry, self.folder_button):
                widget.grid() if state.category in CHOOSABLE else widget.grid_remove()
            self._enabled(self.prepare_button, idle and self.controller.can_prepare)
            self._enabled(self.import_button, idle and state.plan is not None)
            self._enabled(self.cancel_button, not self.closing and (idle or state.busy in ("validation", "preparation", "folders")))
            self._enabled(self.reconcile_button, idle and state.vault is not None and (state.requires_reconciliation or state.saved_uncertain))
            status, tone = visual_status(state)
            if self.closing:
                status = STATUSES["closing"]
                tone = "muted"
            self.status_var.set(status)
            self.status_label.configure(style=tone + ".Status.TLabel")
            primary = (self.reconcile_button if state.requires_reconciliation or state.saved_uncertain else
                       self.vault_button if state.vault is None else
                       self.file_button if state.source is None else
                       self.validate_button if not valid else
                       self.import_button if state.plan is not None else self.prepare_button)
            for button in (self.vault_button, self.file_button, self.validate_button,
                           self.prepare_button, self.import_button, self.reconcile_button):
                button.configure(style="Primary.TButton" if button is primary else "TButton")
            issues = state.validation.issues if state.validation else ()
            errors = [issue_text(issue) for issue in issues if issue.severity == "error"]
            warnings = [issue_text(issue) for issue in issues if issue.severity == "warning"]
            self.count_var.set(f"Erros: {len(errors)}   Avisos: {len(warnings)}" if state.validation else "Erros: —   Avisos: —")
            replace_text(self.errors, "\n\n".join(errors) or "Nenhum erro bloqueante identificado." if state.validation else "Valide o arquivo primeiro.")
            replace_text(self.warnings, "\n\n".join(warnings) or "Nenhum aviso identificado." if state.validation else "Valide o arquivo primeiro.")
            note = state.validation.note if valid else None
            self._show_preview(note)
            for item in self.metadata.get_children():
                self.metadata.delete(item)
            if note:
                for key in ("title", "topic", "tags", "source", "created", "type", "status", "lumen_export", "atlas_action"):
                    value = note.metadata.get(key)
                    text = ", ".join(value) if isinstance(value, list) else str(value).lower() if isinstance(value, bool) else str(value)
                    self.metadata.insert("", "end", values=(key, text[:240] + ("… (veja o YAML na prévia)" if len(text) > 240 else "")))
            if state.plan:
                self.destination_var.set("Destino completo: " + str(state.plan.destination) + "\nNome final: " + state.plan.filename)
            elif state.result and state.result.destination:
                self.destination_var.set("Destino da operação: " + str(state.result.destination) + "\nNome do arquivo: " + state.result.destination.name)
            elif state.requires_reconciliation or state.saved_uncertain:
                self.destination_var.set("Confira o histórico e o resultado antes de preparar outra importação.")
            else:
                self.destination_var.set("Destino ainda não definido. Escolha a categoria e prepare o destino.")
            if self.destination_text.get("1.0", "end-1c") != self.destination_var.get():
                replace_text(self.destination_text, self.destination_var.get())
            if state.result:
                title, detail = result_text(state.result)
                self.result_title_var.set(title)
                self.result_label.configure(style=tone + ".Status.TLabel")
                replace_text(self.result_detail, detail)
            else:
                self.result_title_var.set("")
                replace_text(self.result_detail, "")
            if state.status == "invalid" and state.status != self._last_status:
                self.tabs.select(1)
            elif state.status == "valid" and state.status != self._last_status:
                self.tabs.select(0)
            elif state.result is not None and state.result is not self._last_result:
                self.tabs.select(3)
            self._last_status = state.status
            self._last_result = state.result
        finally:
            self._rendering = False

    def _callback_error(self, *_args):
        # Tk's default handler prints arbitrary exceptions. Show a fixed message.
        self.status_var.set(message("unexpected_error"))
        self.import_button.configure(state="disabled")

    def close_requested(self):
        if self.export_window is not None:
            if self.export_window.workflow.active is not None:
                self.export_window.window.lift()
                self.export_window.workflow.status = "Aguarde a exportação antes de fechar o aplicativo."
                return
            self.export_window.cancel()
        if self.dialog is not None:
            self.dialog.cancel()
        self.closing = True
        if self.controller.active is not None:
            if self.controller.active.kind in ("validation", "preparation", "folders"):
                self.controller.cancel_step("closing")
            self.render()
        else:
            self.destroy()

    def destroy(self):
        if self.closed:
            return
        self.closed = True
        if self.export_window is not None:
            self.export_window.destroy()
        self._preview_generation += 1
        self.worker.close()
        if self._poll_id is not None:
            self.root.after_cancel(self._poll_id)
        if self._preview_after_id is not None:
            self.root.after_cancel(self._preview_after_id)
        self.root.destroy()


class ConfirmationDialog:
    def __init__(self, app: App, confirmation: Confirmation):
        self.app, self.confirmation = app, confirmation
        self.window = tk.Toplevel(app.root)
        window = self.window
        window.title("Confirmar importação")
        window.transient(app.root)
        theme = app.theme
        window.configure(background=COLORS["background"])
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)
        frame = ttk.Frame(window, padding=theme.pad(24, 16))
        frame.grid(sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(3, weight=1)
        ttk.Label(frame, text="Confira antes de gravar", style="Section.TLabel").grid(row=0, sticky="w", pady=(0, theme.px(12)))
        plan = confirmation.plan
        details = "Arquivo de entrada: " + str(plan.note.source) + "\n\nDestino completo: " + str(plan.destination) + "\n\nNome final: " + plan.filename
        self.details = readonly_text(frame, height=7, role="ui")
        self.details.grid(row=1, sticky="ew")
        replace_text(self.details, details)
        collision = "Nome ajustado por colisão: " + plan.filename if plan.filename != app.controller.state.filename else "O arquivo de entrada será preservado. Nenhum arquivo será sobrescrito."
        self.collision = readonly_text(frame, height=2, role="ui")
        self.collision.grid(row=2, sticky="ew", pady=theme.px(8))
        replace_text(self.collision, collision)
        self.warnings = readonly_text(frame, height=4, role="ui")
        self.warnings.grid(row=3, sticky="nsew")
        replace_text(self.warnings, "Avisos:\n" + ("\n\n".join(issue_text(w) for w in plan.note.warnings) or "Nenhum aviso editorial."))
        lifecycle = ttk.Label(frame, text=LIFECYCLE, style="Muted.TLabel", wraplength=theme.px(640))
        lifecycle.grid(row=4, sticky="ew", pady=theme.px(12))
        frame.bind("<Configure>", lambda event: lifecycle.configure(wraplength=max(theme.px(400), event.width - theme.px(48))))
        buttons = ttk.Frame(frame)
        buttons.grid(row=5, sticky="e")
        self.cancel_button = ttk.Button(buttons, text="Cancelar", command=self.cancel)
        self.cancel_button.grid(row=0, column=0, padx=(0, theme.px(12)))
        self.confirm_button = ttk.Button(buttons, text="Confirmar importação", command=self.approve, style="Primary.TButton")
        self.confirm_button.grid(row=0, column=1)
        window.protocol("WM_DELETE_WINDOW", self.cancel)
        window.bind("<Escape>", lambda _event: self.cancel())
        window.grab_set()
        self.cancel_button.focus_set()
        theme.fit_window(window, (760, 570), (620, 480))

    def _close(self):
        if self.window.winfo_exists():
            self.window.grab_release()
            self.window.destroy()
        self.app.dialog = None

    def cancel(self):
        self._close()
        self.app.finish_confirmation(self.confirmation, False)

    def approve(self):
        self.confirm_button.configure(state="disabled")
        self._close()
        self.app.finish_confirmation(self.confirmation, True)


class FolderDialog:
    def __init__(self, app: App):
        self.app = app
        self.window = tk.Toplevel(app.root)
        window = self.window
        window.title("Escolher pasta existente")
        window.transient(app.root)
        theme = app.theme
        window.configure(background=COLORS["background"])
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)
        frame = ttk.Frame(window, padding=theme.pad(24, 16))
        frame.grid(sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)
        self.path_var = tk.StringVar()
        self.path_entry = ttk.Entry(frame, textvariable=self.path_var, state="readonly", width=1, takefocus=True, font=theme.fonts["ui"])
        self.path_entry.grid(row=0, columnspan=2, sticky="ew", pady=(0, theme.px(12)))
        self.items = tk.Listbox(frame, height=10, **theme.list_options())
        self.items.grid(row=1, sticky="nsew")
        scrollbar = ttk.Scrollbar(frame, command=self.items.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.items.configure(yscrollcommand=scrollbar.set)
        self.info_var = tk.StringVar(value="Somente pastas existentes são listadas; nenhuma nota é aberta.")
        info = ttk.Label(frame, textvariable=self.info_var, style="Muted.TLabel", wraplength=theme.px(600))
        info.grid(row=2, columnspan=2, sticky="ew", pady=theme.px(12))
        frame.bind("<Configure>", lambda event: info.configure(wraplength=max(theme.px(400), event.width - theme.px(48))))
        buttons = ttk.Frame(frame)
        buttons.grid(row=3, columnspan=2, sticky="ew")
        buttons.columnconfigure(2, weight=1)
        self.back_button = ttk.Button(buttons, text="Voltar", command=self.back)
        self.back_button.grid(row=0, column=0, padx=(0, theme.px(8)))
        self.enter_button = ttk.Button(buttons, text="Entrar", command=self.enter)
        self.enter_button.grid(row=0, column=1, padx=(0, theme.px(8)))
        self.select_button = ttk.Button(buttons, text="Usar pasta selecionada", command=self.select, style="Primary.TButton")
        self.select_button.grid(row=0, column=2, sticky="e", padx=(0, theme.px(8)))
        self.cancel_button = ttk.Button(buttons, text="Cancelar", command=self.cancel)
        self.cancel_button.grid(row=0, column=3)
        self.parent = None
        self.folders = ()
        self.items.bind("<Double-Button-1>", lambda _event: self.enter())
        self.items.bind("<Return>", lambda _event: self.enter())
        window.bind("<Escape>", lambda _event: self.cancel())
        window.protocol("WM_DELETE_WINDOW", self.cancel)
        window.grab_set()
        self.items.focus_set()
        self.load(None)
        theme.fit_window(window, (700, 460), (620, 380))

    def load(self, parent):
        for button in (self.back_button, self.enter_button, self.select_button):
            button.configure(state="disabled")
        try:
            job = self.app.controller.start_list_folders(parent)
            self.app.dispatch(job, self.loaded)
        except LumenError as exc:
            self.info_var.set(message(exc.code))

    def loaded(self, accepted):
        if not self.window.winfo_exists():
            return
        if not accepted:
            self.info_var.set(message(self.app.controller.state.error_code or "unexpected_error"))
            return
        state = self.app.controller.state
        self.parent, self.folders = state.folder_parent, state.folders
        base = self.app.controller.policy.root / CHOOSABLE[state.category]
        self.path_var.set(str(base / self.parent) if self.parent else str(base))
        self.items.delete(0, "end")
        for folder in self.folders:
            self.items.insert("end", PurePosixPath(folder).name)
        self.back_button.configure(state="normal" if self.parent else "disabled")
        self.enter_button.configure(state="normal" if self.folders else "disabled")
        self.select_button.configure(state="normal" if self.folders or self.parent else "disabled")
        self.info_var.set("Selecione uma pasta filha ou use a pasta atual. A raiz da categoria não pode ser escolhida.")

    def selected(self):
        selection = self.items.curselection()
        return self.folders[selection[0]] if selection else None

    def enter(self):
        folder = self.selected()
        if folder and self.app.controller.active is None:
            self.load(folder)

    def back(self):
        if self.parent and self.app.controller.active is None:
            parent = str(PurePosixPath(self.parent).parent)
            self.load(None if parent == "." else parent)

    def select(self):
        folder = self.selected() or self.parent
        if folder is None or self.app.controller.active:
            return
        try:
            self.cancel_button.configure(state="disabled")
            job = self.app.controller.start_choose_folder(folder)
            self.app.dispatch(job, self.chosen)
        except LumenError as exc:
            self.info_var.set(message(exc.code))
            self.cancel_button.configure(state="normal")

    def chosen(self, accepted):
        if not self.window.winfo_exists():
            return
        if accepted:
            self.window.grab_release()
            self.window.destroy()
            self.app.dialog = None
        else:
            self.info_var.set(message(self.app.controller.state.error_code or "unexpected_error"))
            self.cancel_button.configure(state="normal")

    def cancel(self):
        if self.app.controller.active and self.app.controller.active.kind == "folder_selection":
            return
        self.app.act(self.app.controller.cancel_step)
        self.window.grab_release()
        self.window.destroy()
        self.app.dialog = None


def launch(local_directory: Path):
    root = tk.Tk()
    App(root, local_directory)
    root.mainloop()
