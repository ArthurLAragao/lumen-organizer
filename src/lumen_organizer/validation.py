"""Bounded, non-executing Lumen v1 validation. Original bytes are never rewritten."""

from datetime import date
from hashlib import sha256
from pathlib import Path
import re
import stat
from types import MappingProxyType

import yaml
from yaml import tokens
from yaml.nodes import ScalarNode

from .models import Issue, ValidatedNote, ValidationResult

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_FRONTMATTER_BYTES = 64 * 1024
FIELDS = frozenset({"lumen_schema", "title", "type", "topic", "tags", "source", "created",
                    "status", "lumen_export", "atlas_action", "atlas_task_id", "atlas_goal_id"})
TOPIC = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
SECTIONS = ("Resumo", "Explicação", "Exemplos e aplicação", "Revisão", "Fontes", "Registro pessoal")


class RestrictedYAMLError(Exception):
    def __init__(self, code: str, line: int | None = None):
        self.code, self.line = code, line


class LumenLoader(yaml.SafeLoader):
    """SafeLoader without custom constructors, with duplicate/string-key checks."""

    # Dates remain scalars so invalid dates produce our field-specific error,
    # not a constructor exception; the original YAML is never reserialized.
    yaml_implicit_resolvers = {
        char: [(tag, pattern) for tag, pattern in resolvers
               if tag != "tag:yaml.org,2002:timestamp"]
        for char, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }

    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            line = key_node.start_mark.line + 2  # account for opening ---
            if not isinstance(key_node, ScalarNode) or key_node.tag != "tag:yaml.org,2002:str":
                raise RestrictedYAMLError("invalid_yaml_key", line)
            key = key_node.value
            if key == "<<":
                raise RestrictedYAMLError("yaml_merge_forbidden", line)
            if key in result:
                raise RestrictedYAMLError("duplicate_yaml_key", line)
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def _error(code: str, message: str, field=None, line=None) -> Issue:
    return Issue("error", code, message, field, line)


def _warning(code: str, message: str, field=None) -> Issue:
    return Issue("warning", code, message, field)


def _frontmatter(data: bytes) -> tuple[str, str]:
    if b"\x00" in data:
        raise RestrictedYAMLError("nul_byte")
    text = data.decode("utf-8-sig")
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        raise RestrictedYAMLError("missing_frontmatter")
    length = 0
    for index, line in enumerate(lines[1:], start=1):
        if line.rstrip("\r\n") == "---":
            return "".join(lines[1:index]), "".join(lines[index + 1:])
        length += len(line.encode("utf-8"))
        if length > MAX_FRONTMATTER_BYTES:
            raise RestrictedYAMLError("frontmatter_too_large")
    raise RestrictedYAMLError("unclosed_frontmatter")


def _parse(frontmatter: str) -> dict:
    depth = 0
    opening = (tokens.BlockMappingStartToken, tokens.BlockSequenceStartToken,
               tokens.FlowMappingStartToken, tokens.FlowSequenceStartToken)
    closing = (tokens.BlockEndToken, tokens.FlowMappingEndToken, tokens.FlowSequenceEndToken)
    for count, token in enumerate(yaml.scan(frontmatter, Loader=LumenLoader), start=1):
        if count > 4096:
            raise RestrictedYAMLError("yaml_too_complex")
        if isinstance(token, (tokens.AnchorToken, tokens.AliasToken, tokens.TagToken,
                              tokens.DirectiveToken, tokens.DocumentStartToken, tokens.DocumentEndToken)):
            raise RestrictedYAMLError("yaml_feature_forbidden", token.start_mark.line + 2)
        if isinstance(token, opening):
            depth += 1
            if depth > 8:
                raise RestrictedYAMLError("yaml_too_deep", token.start_mark.line + 2)
        elif isinstance(token, closing):
            depth -= 1
    loader = LumenLoader(frontmatter)
    try:
        mapping = loader.get_single_data()
    finally:
        loader.dispose()
    if not isinstance(mapping, dict):
        raise RestrictedYAMLError("frontmatter_not_mapping")
    # Even safe YAML can construct sets, bytes, or nested containers. The note
    # contract permits simple scalars and lists of strings only.
    for value in mapping.values():
        if isinstance(value, list):
            if not all(isinstance(item, str) for item in value):
                raise RestrictedYAMLError("unsupported_yaml_structure")
        elif type(value) not in (str, int, float, bool, type(None), date):
            raise RestrictedYAMLError("unsupported_yaml_structure")
    return mapping


def _headings(body: str) -> tuple[list[str], set[str]]:
    titles, sections = [], set()
    fence = None
    for line in body.splitlines():
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = (marker[0], len(marker))
            elif marker[0] == fence[0] and len(marker) >= fence[1]:
                fence = None
            continue
        if fence is not None:
            continue
        if line.startswith("# "):
            titles.append(line[2:].strip())
        elif line.startswith("## "):
            sections.add(line[3:].strip())
    return titles, sections


def validate_file(source: str | Path) -> ValidationResult:
    """Incoming-only public entry point: inbox/false remains mandatory."""
    return _validate_file_profile(source, export_profile=False)


def _validate_file_profile(source: str | Path, *, export_profile: bool) -> ValidationResult:
    path = Path(source).absolute()
    issues = []
    if path.suffix.casefold() != ".md":
        return ValidationResult(None, (_error("extension", "Select a Markdown (.md) file."),))
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            return ValidationResult(None, (_error("not_regular_file", "Select a regular file, not a link."),))
        with path.open("rb") as stream:
            data = stream.read(MAX_FILE_BYTES + 1)
    except OSError:
        return ValidationResult(None, (_error("input_unreadable", "The selected file cannot be read."),))
    if len(data) > MAX_FILE_BYTES:
        return ValidationResult(None, (_error("file_too_large", "The note exceeds 2 MiB."),))
    return _validate_bytes(path, data, export_profile=export_profile)


def _validate_bytes(path: Path, data: bytes, *, export_profile: bool) -> ValidationResult:
    """Shared structure and fields; lifecycle profiles never alter source bytes."""
    issues = []
    if len(data) > MAX_FILE_BYTES:
        return ValidationResult(None, (_error("file_too_large", "The note exceeds 2 MiB."),))
    try:
        frontmatter, body = _frontmatter(data)
        metadata = _parse(frontmatter)
    except UnicodeDecodeError:
        return ValidationResult(None, (_error("encoding", "The note must use UTF-8."),))
    except RestrictedYAMLError as exc:
        return ValidationResult(None, (_error(exc.code, "The frontmatter or file structure is unsupported.", line=exc.line),))
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        # Never echo str(exc): PyYAML errors can include a private YAML excerpt.
        return ValidationResult(None, (_error("yaml_syntax", "Invalid YAML syntax.", line=mark.line + 2 if mark else None),))
    except (ValueError, OverflowError):
        # For example, Python refuses extremely long integer scalars.
        return ValidationResult(None, (_error("invalid_yaml_scalar", "A YAML scalar cannot be interpreted safely."),))

    for field in sorted(FIELDS - metadata.keys()):
        issues.append(_error("required_field", "A required property is missing.", field))
    for field in ("title", "source"):
        if field in metadata and (not isinstance(metadata[field], str) or not metadata[field].strip()):
            issues.append(_error("nonempty_string", "Expected a nonempty string.", field))
    if "lumen_schema" in metadata and (type(metadata["lumen_schema"]) is not int or metadata["lumen_schema"] != 1):
        issues.append(_error("schema", "Expected integer schema 1.", "lumen_schema"))
    exact = {"type": "research", "status": "reviewed" if export_profile else "inbox",
             "atlas_task_id": "", "atlas_goal_id": ""}
    for field, expected in exact.items():
        if field in metadata and (type(metadata[field]) is not str or metadata[field] != expected):
            label = "export-ready" if export_profile else "incoming"
            issues.append(_error("incompatible_value", f"The property is incompatible with {label} Lumen v1 notes.", field))
    if "atlas_action" in metadata and metadata["atlas_action"] not in ("none", "suggest"):
        issues.append(_error("atlas_action", "Expected none or suggest; both are passive metadata.", "atlas_action"))
    if "lumen_export" in metadata and (type(metadata["lumen_export"]) is not bool or metadata["lumen_export"] is not export_profile):
        issues.append(_error("export_flag", "Expected boolean true." if export_profile else "Expected boolean false.", "lumen_export"))
    if "topic" in metadata and (not isinstance(metadata["topic"], str) or TOPIC.fullmatch(metadata["topic"]) is None):
        issues.append(_error("topic", "Expected lowercase words or digits separated by single hyphens.", "topic"))
    if "tags" in metadata and (not isinstance(metadata["tags"], list) or not all(isinstance(t, str) for t in metadata["tags"])):
        issues.append(_error("tags", "Expected a list of strings.", "tags"))
    if "created" in metadata:
        value = metadata["created"]
        date_text = value.isoformat() if type(value) is date else value
        try:
            if not isinstance(date_text, str) or DATE.fullmatch(date_text) is None:
                raise ValueError
            date.fromisoformat(date_text)
        except ValueError:
            issues.append(_error("created", "Expected a valid YYYY-MM-DD date.", "created"))
    if not body.strip():
        issues.append(_error("empty_body", "The note must have a Markdown body."))
    if metadata.keys() - FIELDS:
        issues.append(_warning("unknown_properties", "Additional properties are preserved and ignored by the importer."))
    titles, sections = _headings(body)
    if not titles or titles[0] != metadata.get("title"):
        issues.append(_warning("title_heading", "The first heading should match the YAML title."))
    for section in SECTIONS:
        if section not in sections:
            issues.append(_warning("missing_section", "A recommended section is missing: " + section))
    if any(issue.severity == "error" for issue in issues):
        return ValidationResult(None, tuple(issues))
    warnings = tuple(issue for issue in issues if issue.severity == "warning")
    note = ValidatedNote(path, data, sha256(data).hexdigest(), MappingProxyType(metadata), warnings)
    return ValidationResult(note, tuple(issues))
