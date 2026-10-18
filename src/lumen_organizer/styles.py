"""Atlas-led visual tokens and Tk/ttk styling. No workflow or filesystem rules."""

from types import MappingProxyType
from tkinter import font, ttk

COLORS = MappingProxyType({
    "background": "#101010", "surface": "#191919", "selected": "#242424",
    "text": "#F5F5F2", "muted": "#A6A6A0", "divider": "#3B3B3B",
    "border": "#707070", "accent": "#A3C4FF", "accent_hover": "#B6D0FF",
    "warning": "#E6BC73", "error": "#FF9A8E", "success": "#9BD1AD",
})
SPACING = (4, 8, 12, 16, 24, 32)
FONT_SIZES = MappingProxyType({"title": 18, "ui": 11, "section": 11, "small": 10, "mono": 12})


class VisualStyle:
    def __init__(self, root):
        self.root = root
        # Tk scaling is pixels/point: 96 dpi / 72 points is the 100% baseline.
        self.scale = float(root.tk.call("tk", "scaling")) / (96 / 72)
        available = set(font.families(root))
        ui = next((f for f in ("Segoe UI", "Arial") if f in available),
                  font.nametofont("TkDefaultFont", root=root).actual("family"))
        mono = next((f for f in ("Consolas", "Cascadia Mono") if f in available),
                    font.nametofont("TkFixedFont", root=root).actual("family"))
        self.fonts = {
            role: font.Font(root=root, family=mono if role == "mono" else ui,
                            size=size, weight="bold" if role in ("title", "section") else "normal")
            for role, size in FONT_SIZES.items()
        }
        self.ttk = ttk.Style(root)
        self.ttk.theme_use("clam")
        self._configure()
        root.configure(background=COLORS["background"])
        root.option_add("*TCombobox*Listbox.background", COLORS["surface"])
        root.option_add("*TCombobox*Listbox.foreground", COLORS["text"])
        root.option_add("*TCombobox*Listbox.selectBackground", COLORS["accent"])
        root.option_add("*TCombobox*Listbox.selectForeground", COLORS["background"])
        root.option_add("*TCombobox*Listbox.font", str(self.fonts["ui"]))

    def px(self, value):
        return max(0, round(value * self.scale))

    def pad(self, *values):
        return tuple(self.px(value) for value in values)

    def _configure(self):
        s, c = self.ttk, COLORS
        s.configure(".", font=self.fonts["ui"], background=c["background"], foreground=c["text"])
        s.configure("TFrame", background=c["background"])
        s.configure("Surface.TFrame", background=c["surface"])
        s.configure("TLabel", background=c["background"], foreground=c["text"])
        s.configure("Title.TLabel", font=self.fonts["title"], background=c["surface"])
        s.configure("Section.TLabel", font=self.fonts["section"])
        s.configure("Muted.TLabel", font=self.fonts["small"], foreground=c["muted"])
        s.configure("TSeparator", background=c["divider"])
        for tone in ("muted", "accent", "warning", "error", "success"):
            s.configure(tone + ".Status.TLabel", foreground=c[tone], font=self.fonts["section"])
        s.configure("TButton", padding=self.pad(12, 7), background=c["surface"],
                    foreground=c["text"], bordercolor=c["border"], borderwidth=1,
                    lightcolor=c["surface"], darkcolor=c["surface"],
                    focuscolor=c["accent"], focusthickness=self.px(2))
        s.map("TButton", background=[("disabled", c["selected"]), ("pressed", c["selected"]), ("active", c["selected"])],
              foreground=[("disabled", c["muted"])], bordercolor=[("disabled", c["divider"]), ("focus", c["accent"])])
        s.configure("Primary.TButton", background=c["accent"], foreground=c["background"],
                    bordercolor=c["accent"], lightcolor=c["accent"], darkcolor=c["accent"], focuscolor=c["text"])
        s.map("Primary.TButton", background=[("disabled", c["selected"]), ("pressed", c["accent"]), ("active", c["accent_hover"])],
              foreground=[("disabled", c["muted"])], bordercolor=[("disabled", c["divider"]), ("focus", c["text"])],
              lightcolor=[("disabled", c["selected"])], darkcolor=[("disabled", c["selected"])])
        for control in ("TEntry", "TCombobox"):
            s.configure(control, padding=self.pad(8, 6), fieldbackground=c["surface"], background=c["surface"],
                        foreground=c["text"], bordercolor=c["border"], lightcolor=c["surface"], darkcolor=c["surface"],
                        insertcolor=c["text"], selectbackground=c["accent"], selectforeground=c["background"],
                        arrowcolor=c["text"], borderwidth=1)
            s.map(control, fieldbackground=[("disabled", c["selected"]), ("readonly", c["surface"])],
                  foreground=[("disabled", c["muted"])], bordercolor=[("focus", c["accent"]), ("disabled", c["divider"])],
                  arrowcolor=[("disabled", c["muted"])])
        s.configure("TNotebook", background=c["background"], borderwidth=0, bordercolor=c["divider"],
                    lightcolor=c["background"], darkcolor=c["background"], tabmargins=self.pad(0, 0, 0, 8))
        s.configure("TNotebook.Tab", padding=self.pad(12, 8), background=c["surface"],
                    foreground=c["muted"], bordercolor=c["divider"], lightcolor=c["divider"], darkcolor=c["divider"],
                    focuscolor=c["accent"], focusthickness=self.px(2))
        s.map("TNotebook.Tab", background=[("selected", c["selected"]), ("active", c["selected"])],
              foreground=[("selected", c["text"])])
        s.configure("Treeview", background=c["background"], fieldbackground=c["background"], foreground=c["text"],
                    borderwidth=0, rowheight=self.px(30), font=self.fonts["ui"])
        s.map("Treeview", background=[("selected", c["accent"])], foreground=[("selected", c["background"])])
        s.configure("Treeview.Heading", background=c["surface"], foreground=c["text"], font=self.fonts["section"],
                    padding=self.pad(8, 6), relief="flat")
        s.map("Treeview.Heading", background=[("active", c["selected"])])
        for scrollbar in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
            s.configure(scrollbar, background=c["divider"], troughcolor=c["background"],
                        bordercolor=c["background"], arrowcolor=c["muted"],
                        lightcolor=c["divider"], darkcolor=c["divider"], width=self.px(14))
            s.map(scrollbar, background=[("active", c["border"]), ("pressed", c["border"])])

    def text_options(self, role="mono"):
        c = COLORS
        return dict(font=self.fonts[role], background=c["background"], foreground=c["text"],
                    selectbackground=c["accent"], selectforeground=c["background"],
                    insertbackground=c["text"], highlightbackground=c["background"], highlightcolor=c["accent"],
                    highlightthickness=self.px(2), borderwidth=0, relief="flat", exportselection=False,
                    padx=self.px(8), pady=self.px(8), spacing1=self.px(2), spacing3=self.px(2))

    def list_options(self):
        c = COLORS
        return dict(font=self.fonts["ui"], background=c["surface"], foreground=c["text"],
                    selectbackground=c["accent"], selectforeground=c["background"],
                    highlightbackground=c["border"], highlightcolor=c["accent"], highlightthickness=self.px(2),
                    borderwidth=0, disabledforeground=c["muted"], exportselection=False)

    def fit_window(self, window, default, minimum):
        window.update_idletasks()
        # Leave room for Windows chrome/taskbar; don't assume monitor resolution.
        available = (max(320, window.winfo_screenwidth() - self.px(48)),
                     max(240, window.winfo_screenheight() - self.px(80)))
        requested = (window.winfo_reqwidth(), window.winfo_reqheight())
        floor = tuple(min(available[i], max(self.px(minimum[i]), requested[i])) for i in (0, 1))
        size = tuple(min(available[i], max(self.px(default[i]), floor[i])) for i in (0, 1))
        window.minsize(*floor)
        window.geometry(f"{size[0]}x{size[1]}")

