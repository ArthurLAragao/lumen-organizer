"""Portuguese presentation of domain codes; no validation or import rules."""

from .models import Issue, ImportResult

CATEGORY_LABELS = {
    "aws-cloud": "AWS e Cloud (aws-cloud)",
    "linux-devops": "Linux e DevOps (linux-devops)",
    "programacao": "Programação (programacao)",
    "ia": "Inteligência Artificial (ia)",
    "seguranca": "Segurança (seguranca)",
    "ferramentas": "Ferramentas e Workflow (ferramentas)",
    "indefinido": "Inbox / Pesquisas (indefinido)",
    "faculdade": "Faculdade — escolher pasta existente",
    "projetos": "Projetos — escolher pasta existente",
}
MESSAGES = {
    "extension": "Selecione um arquivo Markdown (.md).",
    "not_regular_file": "Selecione um arquivo regular, sem link simbólico.",
    "input_unreadable": "Não foi possível ler o arquivo selecionado.",
    "file_too_large": "O arquivo excede o limite de 2 MiB.",
    "frontmatter_too_large": "O YAML excede o limite de 64 KiB.",
    "encoding": "O arquivo deve usar UTF-8.",
    "nul_byte": "O arquivo contém um caractere NUL não permitido.",
    "missing_frontmatter": "O arquivo deve começar com o YAML entre linhas ---.",
    "unclosed_frontmatter": "O bloco YAML não possui a linha --- de fechamento.",
    "frontmatter_not_mapping": "O YAML deve conter propriedades com nomes e valores.",
    "duplicate_yaml_key": "Uma propriedade aparece mais de uma vez no YAML.",
    "invalid_yaml_key": "O YAML contém uma chave incompatível.",
    "yaml_merge_forbidden": "Mesclagens de propriedades YAML não são aceitas.",
    "yaml_feature_forbidden": "Tags, âncoras, aliases e diretivas YAML não são aceitos.",
    "unsupported_yaml_structure": "Use valores simples ou listas de strings no YAML.",
    "yaml_too_complex": "O YAML excede o limite de complexidade.",
    "yaml_too_deep": "O YAML contém estruturas excessivamente aninhadas.",
    "invalid_yaml_scalar": "Um valor YAML não pôde ser interpretado com segurança.",
    "yaml_syntax": "A sintaxe do YAML é inválida.",
    "required_field": "Uma propriedade obrigatória está ausente.",
    "nonempty_string": "A propriedade deve ser uma string não vazia.",
    "schema": "lumen_schema deve ser o inteiro 1.",
    "incompatible_value": "O valor é incompatível com uma nota de entrada Lumen v1.",
    "atlas_action": "atlas_action deve ser none ou suggest; ambos são metadados passivos.",
    "export_flag": "lumen_export deve ser o booleano false, sem aspas.",
    "topic": "Use letras minúsculas sem acentos e/ou números, separados por hífens simples.",
    "tags": "tags deve ser uma lista de strings.",
    "created": "created deve ser uma data válida no formato YYYY-MM-DD.",
    "empty_body": "A nota deve possuir conteúdo Markdown após o YAML.",
    "unknown_properties": "Propriedades adicionais serão preservadas e ignoradas pelo importador.",
    "title_heading": "O primeiro título Markdown deve corresponder à propriedade title.",
    "missing_section": "Uma seção recomendada está ausente.",
    "configuration_required": "Selecione a raiz de um vault para continuar.",
    "settings_location": "A configuração deve ficar na pasta .local do aplicativo.",
    "settings_unavailable": "Não foi possível salvar a configuração local.",
    "invalid_settings": "A configuração local é inválida ou inesperada; o arquivo foi preservado.",
    "state_inside_vault": "A configuração e o histórico devem ficar fora do vault. Escolha outra raiz.",
    "state_unavailable": "Não foi possível acessar o armazenamento local do aplicativo.",
    "unrecognized_history": "O arquivo de histórico é inesperado; ele foi preservado.",
    "history_unavailable": "O histórico local está indisponível.",
    "absolute_vault_required": "Selecione uma raiz de vault com caminho absoluto.",
    "directory_unavailable": "A pasta não existe ou está indisponível.",
    "directory_required": "O destino selecionado deve ser uma pasta existente.",
    "linked_directory_forbidden": "Pastas com links simbólicos ou junctions não são aceitas.",
    "network_path_forbidden": "Vaults em caminhos UNC ou de rede não são aceitos nesta versão.",
    "directory_lock_failed": "Não foi possível proteger a pasta para a operação.",
    "directory_changed": "A pasta mudou. Prepare e confirme o destino novamente.",
    "invalid_filename": "Use um nome de arquivo .md compatível com Windows, sem caminhos ou nomes reservados.",
    "invalid_relative_path": "A pasta escolhida não pertence a um caminho relativo permitido.",
    "outside_vault": "O destino está fora das áreas autorizadas.",
    "explicit_subfolder_required": "Escolha explicitamente uma pasta existente para esta categoria.",
    "unknown_category": "Escolha uma categoria disponível.",
    "prepare_unavailable": "Valide a nota e escolha um destino completo antes de continuar.",
    "select_file_required": "Selecione um arquivo .md primeiro.",
    "source_changed": "O arquivo mudou após a prévia. Valide novamente e prepare uma nova confirmação.",
    "destination_changed": "O destino mudou; uma nova confirmação é necessária.",
    "destination_collision": "O nome foi ocupado após a prévia. Prepare um novo destino para obter outro nome.",
    "confirmation_invalid": "A confirmação expirou. Prepare e confira o destino novamente.",
    "state_wrong_volume": "O armazenamento local e o destino devem estar no mesmo sistema de arquivos.",
    "state_busy": "Outra operação do Lumen está usando este histórico. Aguarde.",
    "operation_busy": "Aguarde a operação atual terminar.",
    "operation_cannot_cancel": "A operação já começou. Aguarde o resultado; nenhuma tentativa adicional será iniciada.",
    "permission_denied": "A gravação não foi concluída por falta de permissão.",
    "disk_full": "A gravação não foi concluída por falta de espaço.",
    "write_failed": "A gravação não foi concluída.",
    "filesystem_unavailable": "O sistema de arquivos está indisponível.",
    "reconciliation_required": "Existe uma importação pendente. Use Conferir histórico antes de continuar.",
    "prior_import_changed": "A nota já foi importada, mas o arquivo registrado mudou. Confira a importação anterior.",
    "prior_import_missing": "A nota já foi importada, mas o destino registrado não existe. Confira a importação anterior.",
    "prior_import_unavailable": "A nota já foi importada, mas o destino registrado está indisponível.",
    "unexpected_error": "A operação não pôde ser concluída. Nenhum detalhe do conteúdo foi registrado.",
    "unsupported_import_platform": "A importação segura desta versão requer Windows.",
}
STATUSES = {
    "configure": "Nenhum vault configurado. Selecione a raiz de um vault.",
    "choose_file": "Nenhuma nota selecionada. Selecione uma nota para começar.",
    "validate": "Nota selecionada. Clique em Validar nota.",
    "valid": "Nota válida. Escolha a categoria manualmente e prepare o destino.",
    "invalid": "Existem erros bloqueantes. Corrija o arquivo fora do Lumen e valide novamente.",
    "choose_destination": "Destino alterado. Prepare o caminho completo novamente.",
    "prepared": "Destino preparado. Clique em Revisar importação para conferir antes de confirmar.",
    "confirmation": "Aguardando sua confirmação explícita.",
    "configuration_cancelled": "Seleção de vault cancelada. A configuração anterior foi mantida.",
    "file_cancelled": "Seleção de arquivo cancelada. A seleção anterior foi mantida.",
    "cancelled": "Etapa cancelada. Nenhuma nota foi gravada.",
    "confirmation_cancelled": "Importação cancelada. Prepare novamente quando quiser continuar.",
    "closing": "Aguardando a operação terminar para fechar com segurança.",
}
BUSY = {
    "configuration": "Lendo ou salvando a configuração local…",
    "validation": "Validando nota…",
    "folders": "Listando somente as pastas existentes…",
    "folder_selection": "Conferindo a pasta escolhida…",
    "preparation": "Preparando o destino e conferindo duplicatas…",
    "import": "Importando nota… Aguarde o resultado.",
    "reconciliation": "Conferindo as operações pendentes no histórico…",
}


def message(code: str) -> str:
    return MESSAGES.get(code, "Não foi possível concluir esta operação com segurança.")


def issue_text(issue: Issue) -> str:
    location = []
    if issue.field:
        location.append(issue.field)
    if issue.line:
        location.append(f"linha {issue.line}")
    text = message(issue.code)
    if issue.code == "missing_section" and ": " in issue.message:
        text += " " + issue.message.rsplit(": ", 1)[1]
    return ("[" + ", ".join(location) + "] " if location else "") + text


def result_text(result: ImportResult) -> tuple[str, str]:
    outcome = result.outcome
    if outcome == "imported":
        title, detail = "Importação concluída", "Os bytes aprovados foram salvos e o sucesso foi registrado."
    elif outcome == "duplicate":
        title, detail = "Duplicata identificada", "Esta nota já foi importada pelo Lumen. Nenhum novo arquivo foi gravado."
    elif outcome == "cancelled":
        title, detail = "Operação cancelada", "Nenhuma nota foi gravada nesta etapa."
    elif outcome == "saved_history_incomplete":
        title, detail = "Arquivo salvo; histórico incompleto", "O arquivo já foi salvo. Não repita a importação. Use Conferir histórico para verificar a operação pendente."
    elif outcome == "saved_unverified":
        title, detail = "Arquivo salvo; verificação incompleta", "Confira o arquivo salvo manualmente. Não repita a importação às cegas."
    elif outcome == "failed_history_incomplete":
        title, detail = "Falha na gravação e no histórico", "Confira as operações pendentes antes de tentar novamente."
    elif outcome == "save_state_unknown":
        title, detail = "Resultado da gravação incerto", "O arquivo pode ter sido salvo. Não repita a importação. Use Conferir histórico e confira o destino antes de continuar."
    elif outcome == "reconciled_import":
        title, detail = "Importação confirmada pelo histórico", "O arquivo existente corresponde ao registro pendente. Nenhuma nota foi regravada."
    elif outcome == "reconciled_failure":
        title, detail = "Operação pendente conferida", "A tentativa foi registrada como falha. Nenhuma nota existente foi alterada."
    elif outcome == "reconciliation_empty":
        title, detail = "Histórico conferido", "Não há operações pendentes para este vault."
    else:
        title, detail = "Operação não concluída", message(result.code)
    if result.destination is not None:
        detail += "\nDestino: " + str(result.destination)
    return title, detail


def visual_status(state) -> tuple[str, str]:
    """Describe existing workflow state; color is supplementary to the text."""
    if state.busy:
        return BUSY.get(state.busy, "Operação em andamento…"), "accent"
    if state.saved_uncertain and state.result and state.result.outcome == "reconciliation_empty":
        return "Resultado da gravação ainda incerto. Confira o destino manualmente. Não repita a importação.", "warning"
    if state.result:
        title, detail = result_text(state.result)
        tone = {"imported": "success", "reconciled_import": "success", "duplicate": "accent",
                "cancelled": "muted", "reconciliation_empty": "muted", "reconciled_failure": "warning",
                "saved_history_incomplete": "warning", "saved_unverified": "warning", "save_state_unknown": "warning"}.get(state.result.outcome, "error")
        return title + ". " + detail.split("\n", 1)[0], tone
    if state.error_code:
        return message(state.error_code), "error"
    if state.requires_reconciliation:
        return message("reconciliation_required"), "warning"
    if state.status in ("configuration_cancelled", "file_cancelled", "cancelled", "confirmation_cancelled"):
        return STATUSES[state.status], "muted"
    validation = state.validation
    if validation and not validation.valid:
        errors = sum(issue.severity == "error" for issue in validation.issues)
        return f"Nota inválida — {errors} erros bloqueantes. Corrija o arquivo e valide novamente.", "error"
    if validation and validation.valid and state.status not in ("prepared", "confirmation"):
        warnings = len(validation.note.warnings)
        if warnings:
            return f"Nota válida com avisos — {warnings} avisos. Consulte Erros e avisos antes de revisar a importação.", "warning"
        return "Nota válida. Escolha o destino e prepare a importação.", "success"
    tone = "warning" if validation and validation.valid and validation.note.warnings else "muted"
    return STATUSES.get(state.status, "Destino ainda não definido."), tone
