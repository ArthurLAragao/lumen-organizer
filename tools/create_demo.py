"""Create a unique fictional vault/inputs under .local, without configuring the app."""

from pathlib import Path
import shutil
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lumen_organizer.destinations import FIXED, CHOOSABLE, check_directory_chain


def create_demo(local_directory: Path):
    local_directory = Path(local_directory).absolute()
    if local_directory.name != ".local":
        raise ValueError("The demo must stay under .local.")
    check_directory_chain(local_directory.parent)
    local_directory.mkdir(exist_ok=True)
    check_directory_chain(local_directory)
    demos = local_directory / "demos"
    demos.mkdir(exist_ok=True)
    check_directory_chain(demos)
    directory = demos / uuid.uuid4().hex
    directory.mkdir()
    vault = directory / "Vault-Ficticio"
    vault.mkdir()
    for path in FIXED.values():
        (vault / path).mkdir(parents=True, exist_ok=True)
    for path in CHOOSABLE.values():
        (vault / path / "Pasta-Ficticia" / "Subpasta-Ficticia").mkdir(parents=True)
    source = directory / "nota-ficticia.md"
    shutil.copyfile(ROOT / "tests" / "fixtures" / "research-none.md", source)
    data = source.read_bytes()
    (directory / "nota-com-avisos.md").write_bytes(data.replace(b"# Fictional queue study", b"# Fictional different title"))
    (directory / "nota-invalida.md").write_bytes(data.replace(b"status: inbox", b"status: reviewed"))
    return directory, vault, source


if __name__ == "__main__":
    directory, vault, source = create_demo(ROOT / ".local")
    print("Demonstração fictícia criada; nenhuma configuração foi alterada.")
    print("Vault:", vault)
    print("Arquivo:", source)
    print("Outros exemplos:", directory)
