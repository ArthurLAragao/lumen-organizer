"""Launch only a unique fictional workspace; never load personal settings."""
from pathlib import Path
import tkinter as tk
from create_demo import create_demo, ROOT
from lumen_organizer.destinations import FIXED
from lumen_organizer.ui import App


def stage9d_demo():
    directory, vault, source = create_demo(ROOT / ".local")
    note = vault / FIXED["ferramentas"] / "nota-ficticia-autorizada.md"
    note.write_bytes((ROOT / "tests" / "fixtures" / "atlas-export" / "reviewed.md").read_bytes())
    output = directory / "Pacotes-Ficticios"
    output.mkdir()
    local = directory / ".local"
    root = tk.Tk()
    app = App(root, local, load_settings=False)
    root.title("Lumen Organizer — DEMO FICTÍCIA Stage 9D")
    app.act(lambda: app.controller.start_configure(vault))
    print("Ambiente fictício isolado; nenhuma configuração pessoal foi carregada.")
    print("Vault de origem:", vault)
    print("Nota autorizada:", note)
    print("Categoria: ferramentas")
    print("Destino dos pacotes:", output)
    root.mainloop()


if __name__ == "__main__":
    stage9d_demo()
