"""UI workflow adapter. Export rules remain in AtlasExporter and ExportRegistry."""
from dataclasses import dataclass, field
from pathlib import Path
from hashlib import sha256
import os
import threading
import uuid

from .atlas_export import AtlasExporter, ExportPlan, validate_export_file
from .controller import Job
from .destinations import DestinationPolicy, check_directory_chain, relative_parts
from .export_registry import ExportRegistry
from .filesystem import directory_guard, publish_no_replace, regular_file
from .models import LumenError, ValidationResult


@dataclass(frozen=True)
class ExportReview:
    revision: int
    plan: ExportPlan = field(repr=False)
    destination: Path = field(repr=False)


def package_destination(value, policy, registry):
    """Filesystem output checks only; no note/domain validation is duplicated."""
    path = Path(value).absolute()
    parts = relative_parts(path.name)
    if len(parts) != 1 or len(path.name) > 180 or not path.name.lower().endswith(".lumen-atlas.json"):
        raise LumenError("package_filename")
    parent = check_directory_chain(path.parent)
    if parent.is_relative_to(policy.root) or parent.is_relative_to(registry.directory):
        raise LumenError("package_destination_forbidden")
    if os.path.lexists(path):
        raise LumenError("export_package_collision")
    return parent / path.name


def save_prepared(exporter, export_id, destination):
    """Copy verified retained bytes, atomically, with no replace; never advances delivery."""
    target = package_destination(destination, exporter.policy, exporter.registry)
    with directory_guard(target.parent):
        data = exporter.read_prepared(export_id)
        staged = target.parent / ("lumen-" + uuid.uuid4().hex + ".tmp")
        published = False
        try:
            with staged.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            publish_no_replace(staged, target)
            published = True
            if not regular_file(target) or target.stat().st_size != len(data):
                raise LumenError("export_copy_unverified")
            with target.open("rb") as stream:
                copied = stream.read(len(data) + 1)
            if sha256(copied).digest() != sha256(data).digest():
                raise LumenError("export_copy_unverified")
        except Exception:
            if published:
                raise LumenError("export_copy_unverified") from None
            raise
        finally:
            # Only the unique, owned stage can be removed. Never remove a destination.
            if regular_file(staged):
                staged.unlink()
    return target


class ExportWorkflow:
    def __init__(self, local_directory):
        self.local = Path(local_directory).absolute()
        self.owner = threading.get_ident()
        self.active = None
        self.revision = 0
        self.policy = self.registry = self.exporter = None
        self.source = self.category = self.subfolder = self.baseline = self.destination = None
        self.validation = self.identity = self.plan = self.confirmation = None
        self.archive_id = None
        self.error = None
        self.status = "Selecione o vault de origem."
        self.halted = False
        self.output = None
        self.records = ()

    def _available(self):
        if threading.get_ident() != self.owner:
            raise RuntimeError("UI state belongs to its owner thread.")
        if self.active is not None:
            raise LumenError("operation_busy")

    def invalidate(self):
        self._available()
        self.revision += 1
        self.validation = self.identity = self.plan = self.confirmation = None
        self.archive_id = self.output = self.error = None
        self.records = ()

    def select(self, *, source=None, category=None, subfolder=None, baseline=None):
        self.invalidate()
        self.source, self.category, self.subfolder, self.baseline = source, category, subfolder, baseline
        self.status = "Valide a localização e o perfil de exportação."

    def job(self, kind, work, accept):
        self._available()
        self.error = None
        self.active = Job(kind, self.revision, work, accept)
        return self.active

    def complete(self, job, value=None, error_code=None):
        self._available_owner()
        if job is not self.active:
            return False
        self.active = None
        if job.revision != self.revision:
            return False
        if error_code:
            self.error = error_code
            self.status = "Não foi possível concluir esta etapa. Confira o aviso."
            if job.kind in ("export_commit", "export_resend"):
                self.halted = True
                self.status = "Resultado incerto. Confira o registro; não repita a exportação."
        else:
            job.accept(value)
        return True

    def _available_owner(self):
        if threading.get_ident() != self.owner:
            raise RuntimeError("UI state belongs to its owner thread.")

    def configure(self, vault):
        self.invalidate()
        self.source = self.category = self.subfolder = self.baseline = self.destination = None
        def work():
            policy = DestinationPolicy(vault)
            state = self.local / "atlas-export"
            registry = ExportRegistry.open(state, policy.root) if state.exists() else None
            return policy, registry
        def accept(value):
            self.policy, self.registry = value
            self.exporter = AtlasExporter(self.policy, self.registry) if self.registry else None
            self.halted = False
            self.status = "Vault selecionado. Abra ou crie explicitamente o registro local."
        return self.job("export_configuration", work, accept)

    def create_registry(self, confirmed=False):
        self._available()
        if confirmed is not True or self.policy is None:
            raise LumenError("identity_confirmation_required")
        def work():
            check_directory_chain(self.local.parent)
            self.local.mkdir(exist_ok=True)
            return ExportRegistry.create(self.local / "atlas-export", self.policy.root)
        def accept(registry):
            self.registry = registry
            self.exporter = AtlasExporter(self.policy, registry)
            self.status = "Registro local criado. Isso não declara revisão de conteúdo."
        return self.job("export_registry", work, accept)

    def validate(self):
        self._available()
        if self.policy is None or not self.source or not self.category:
            raise LumenError("export_selection_required")
        self.plan = self.confirmation = None
        def work():
            result = validate_export_file(self.source, self.policy, self.category, self.subfolder)
            identity = None
            records = ()
            if result.valid and self.registry:
                relative = result.note.source.relative_to(self.policy.root).as_posix()
                identity = self.registry.identity_for(self.policy.vault_id, relative)
                if identity:
                    records = tuple(r for r in self.registry.records()
                                    if r.integration_id == identity.integration_id and r.state == "prepared")
            return result, identity, records
        def accept(value):
            self.validation, self.identity, self.records = value
            self.status = ("Elegível para exportação." if self.validation.valid else
                           "Exportação bloqueada. Exige estrutura válida, status: reviewed e lumen_export: true booleano.")
        return self.job("export_validation", work, accept)

    def register(self, confirmed=False):
        self._available()
        if confirmed is not True or not self.exporter or not self.validation or not self.validation.valid:
            raise LumenError("identity_confirmation_required")
        def accept(identity):
            self.identity = identity
            self.status = "Identidade registrada; o Markdown permanece intacto."
        return self.job("export_identity",
                        lambda: self.exporter.register(self.source, self.category, self.subfolder, confirmed=True), accept)

    def prepare(self):
        self._available()
        if self.halted or not self.exporter:
            raise LumenError("export_reconciliation_required")
        self.confirmation = None
        def accept(plan):
            self.plan = plan
            self.validation = ValidationResult(plan.note, plan.note.warnings)
            self.archive_id = None
            self.status = "Versão preparada para revisão; nenhum pacote foi gravado."
        return self.job("export_preparation",
                        lambda: self.exporter.prepare(self.source, self.category, self.subfolder,
                                                      baseline_export_id=self.baseline), accept)

    def set_destination(self, path):
        self._available()
        self.revision += 1
        self.confirmation = None
        self.destination = Path(path).absolute() if path else None
        self.status = "Destino selecionado. Revise a exportação." if path else "Escolha de destino cancelada."

    def review(self):
        self._available()
        if not self.plan or not self.destination or self.halted:
            raise LumenError("export_review_required")
        def accept(path):
            self.confirmation = ExportReview(self.revision, self.plan, path)
            self.status = "Confira a versão, a identidade e o caminho completo antes de confirmar."
        return self.job("export_review",
                        lambda: package_destination(self.destination, self.policy, self.registry), accept)

    def commit(self, review, *, confirmed=False):
        self._available()
        if confirmed is not True:
            self.confirmation = None
            self.status = "Exportação cancelada. Nenhum pacote novo foi gerado."
            return None
        if review is not self.confirmation or review.revision != self.revision or review.plan is not self.plan:
            raise LumenError("export_confirmation_stale")
        self.confirmation = None
        def work():
            # Guard and recheck the selected target BEFORE generating an archive.
            with directory_guard(review.destination.parent):
                package_destination(review.destination, self.policy, self.registry)
                result = self.exporter.commit(review.plan, confirmed=True)
                if result.outcome != "prepared":
                    return result, None, None
                try:
                    return result, save_prepared(self.exporter, result.export_id, review.destination), None
                except LumenError as exc:
                    return result, None, exc.code
                except Exception:
                    return result, None, "export_copy_failed"
        def accept(value):
            result, self.output, copy_error = value
            self.archive_id = result.export_id
            self.error = copy_error or (result.code if result.outcome != "prepared" else None)
            self.halted = result.outcome in ("prepared_registry_incomplete", "package_unverified", "recovery_required")
            self.halted = self.halted or copy_error == "export_copy_unverified"
            if self.output:
                self.status = "Pacote preparado. A importação no Atlas ainda não foi confirmada."
            elif copy_error == "export_copy_unverified":
                self.status = "Cópia publicada, mas não verificada. Preserve o pacote retido e confira o destino; não repita a exportação."
            elif result.outcome == "prepared":
                self.status = "Pacote arquivado; a cópia escolhida falhou. Salve o pacote já preparado, sem gerar outra exportação."
            elif self.halted:
                self.status = "Registro incompleto. Confira o registro antes de tentar novamente; não repita a exportação."
            else:
                self.status = "Exportação bloqueada ou não concluída. Valide novamente."
                self.plan = None
        return self.job("export_commit", work, accept)

    def reconcile(self):
        self._available()
        if not self.exporter:
            raise LumenError("export_registry_unavailable")
        def accept(results):
            self.halted = any(r.outcome != "prepared" and r.outcome != "failed" for r in results)
            self.status = ("Registro conferido; escolha explicitamente salvar o pacote retido." if not self.halted else
                           "Há uma operação pendente. Preserve o registro; recuperação técnica ainda necessária.")
        return self.job("export_reconciliation", self.exporter.reconcile, accept)

    def resend(self, confirmed=False):
        self._available()
        if confirmed is not True or not self.archive_id or self.halted or not self.destination:
            raise LumenError("export_review_required")
        def accept(path):
            self.output = path
            self.status = "Pacote preparado. A importação no Atlas ainda não foi confirmada."
        return self.job("export_resend",
                        lambda: save_prepared(self.exporter, self.archive_id, self.destination), accept)

    def cancel(self):
        self._available()
        self.confirmation = None
        self.status = "Operação cancelada. Nenhum pacote novo foi gerado."
