"""Pure, bounded single-note protocol. No I/O, execution, network or repair."""

from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path
import re
import struct
from types import MappingProxyType
from typing import Mapping

from .models import Issue, LumenError, ValidatedNote, ValidationResult
from .validation import _validate_bytes

FORMAT = "lumen-atlas-note"
VERSION = 1
MAX_PACKAGE_BYTES = 2 * 1024 * 1024
MAX_TITLE_UNITS = 240
MAX_TAGS = 50
MAX_TAG_UNITS = 60
MAX_MARKDOWN_UNITS = 500_000
ORIGIN_FIELDS = frozenset({"lumen_schema", "type", "topic", "source", "created",
                           "status", "lumen_export", "atlas_action"})
PACKAGE_FIELDS = frozenset({"format", "version", "integration_id", "title", "tags", "markdown",
                            "origin", "source_sha256", "comparison_sha256", "baseline_sha256"})
INTEGRATION_ID = re.compile(r"lumen_[0-9a-f]{32}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HASH_PREFIX = b"LUMEN-ATLAS-COMPARE\x00\x01"
# ECMAScript WhiteSpace + LineTerminator: Python strip() has a different set.
JS_TRIM = "\u0009\u000a\u000b\u000c\u000d\u0020\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"


def utf16_units(value: str) -> int:
    """JavaScript .length for valid Unicode scalar strings; reject lone surrogates."""
    return len(value.encode("utf-16-le", errors="strict")) // 2


def comparison_bytes(title: str, tags: list[str] | tuple[str, ...], markdown: str) -> bytes:
    def text(value):
        encoded = value.encode("utf-8", errors="strict")
        return struct.pack(">I", len(encoded)) + encoded
    return HASH_PREFIX + text(title) + struct.pack(">I", len(tags)) + b"".join(text(tag) for tag in tags) + text(markdown)


def comparison_hash(title: str, tags: list[str] | tuple[str, ...], markdown: str) -> str:
    return sha256(comparison_bytes(title, tags, markdown)).hexdigest()


def atlas_compatible(result: ValidationResult) -> ValidationResult:
    """Additional export bounds; no trimming/normalization or hidden corrections."""
    if not result.valid:
        return result
    note, issues = result.note, list(result.issues)
    metadata = note.metadata
    try:
        title, tags = metadata["title"], metadata["tags"]
        if (not 1 <= utf16_units(title) <= MAX_TITLE_UNITS or title.strip(JS_TRIM) != title
                or any(token in title for token in ("[[", "]]", "\r", "\n"))):
            issues.append(Issue("error", "atlas_title", "Title exceeds Atlas limits or requires editing.", "title"))
        if len(tags) > MAX_TAGS or any(not 1 <= utf16_units(tag) <= MAX_TAG_UNITS
                                     or tag.strip(JS_TRIM) != tag for tag in tags):
            issues.append(Issue("error", "atlas_tags", "Tags exceed Atlas limits or require editing.", "tags"))
        if utf16_units(note.data.decode("utf-8", errors="strict")) > MAX_MARKDOWN_UNITS:
            issues.append(Issue("error", "atlas_content", "Complete Markdown exceeds Atlas content limit."))
        for name, limit in (("topic", 240), ("source", 4096)):
            if utf16_units(metadata[name]) > limit:
                issues.append(Issue("error", "origin_limit", "An origin field exceeds the transfer limit.", name))
            metadata[name].encode("utf-8", errors="strict")
    except UnicodeError:
        issues.append(Issue("error", "invalid_unicode", "Unicode scalar strings are required."))
    if any(issue.severity == "error" for issue in issues):
        return ValidationResult(None, tuple(issues))
    return result


@dataclass(frozen=True)
class TransferPackage:
    integration_id: str
    title: str = field(repr=False)
    tags: tuple[str, ...] = field(repr=False)
    markdown: str = field(repr=False)
    origin: Mapping[str, object] = field(repr=False)
    source_sha256: str
    comparison_sha256: str
    baseline_sha256: str | None

    @property
    def source_bytes(self) -> bytes:
        return self.markdown.encode("utf-8", errors="strict")


def _keys(value, expected):
    if type(value) is not dict or set(value) != expected:
        raise LumenError("invalid_transfer_fields")


def _hex(value) -> bool:
    return isinstance(value, str) and HEX64.fullmatch(value) is not None


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise LumenError("duplicate_transfer_key")
        result[key] = value
    return result


def _constant(_value):
    raise LumenError("invalid_transfer_number")


def decode_package(data: bytes) -> TransferPackage:
    """Validate transport and original YAML without trusting duplicated metadata."""
    if type(data) is not bytes or len(data) > MAX_PACKAGE_BYTES:
        raise LumenError("transfer_size")
    try:
        payload = json.loads(data.decode("utf-8", errors="strict"), object_pairs_hook=_object,
                             parse_constant=_constant)
        _keys(payload, PACKAGE_FIELDS)
        if payload["format"] != FORMAT or type(payload["version"]) is not int or payload["version"] != VERSION:
            raise LumenError("transfer_version")
        integration = payload["integration_id"]
        if not isinstance(integration, str) or not INTEGRATION_ID.fullmatch(integration):
            raise LumenError("transfer_identity")
        if type(payload["title"]) is not str or type(payload["markdown"]) is not str:
            raise LumenError("transfer_types")
        if type(payload["tags"]) is not list or any(type(tag) is not str for tag in payload["tags"]):
            raise LumenError("transfer_types")
        _keys(payload["origin"], ORIGIN_FIELDS)
        for key in ("source_sha256", "comparison_sha256"):
            if not _hex(payload[key]):
                raise LumenError("transfer_hash")
        if payload["baseline_sha256"] is not None and not _hex(payload["baseline_sha256"]):
            raise LumenError("transfer_baseline")
        raw = payload["markdown"].encode("utf-8", errors="strict")
        checked = atlas_compatible(_validate_bytes(Path("transfer.md"), raw, export_profile=True))
        if not checked.valid:
            raise LumenError("invalid_transfer_note")
        metadata = checked.note.metadata
        if payload["title"] != metadata["title"] or payload["tags"] != metadata["tags"]:
            raise LumenError("transfer_metadata_mismatch")
        if any(type(payload["origin"][key]) is not type(metadata[key])
               or payload["origin"][key] != metadata[key] for key in ORIGIN_FIELDS):
            raise LumenError("transfer_metadata_mismatch")
        if sha256(raw).hexdigest() != payload["source_sha256"]:
            raise LumenError("transfer_hash_mismatch")
        if comparison_hash(payload["title"], payload["tags"], payload["markdown"]) != payload["comparison_sha256"]:
            raise LumenError("transfer_hash_mismatch")
        return TransferPackage(integration, payload["title"], tuple(payload["tags"]), payload["markdown"],
                               MappingProxyType(payload["origin"]), payload["source_sha256"],
                               payload["comparison_sha256"], payload["baseline_sha256"])
    except (ValueError, UnicodeError, RecursionError, OverflowError):
        # Never include parser text or an excerpt of the selected note.
        raise LumenError("invalid_transfer_json") from None


def encode_package(note: ValidatedNote, integration_id: str, baseline_sha256: str | None = None) -> bytes:
    checked = atlas_compatible(_validate_bytes(note.source, note.data, export_profile=True))
    if not checked.valid:
        raise LumenError("export_validation_failed")
    metadata = checked.note.metadata
    markdown = note.data.decode("utf-8", errors="strict")
    payload = {
        "format": FORMAT, "version": VERSION, "integration_id": integration_id,
        "title": metadata["title"], "tags": metadata["tags"], "markdown": markdown,
        "origin": {key: metadata[key] for key in sorted(ORIGIN_FIELDS)},
        "source_sha256": sha256(note.data).hexdigest(),
        "comparison_sha256": comparison_hash(metadata["title"], metadata["tags"], markdown),
        "baseline_sha256": baseline_sha256,
    }
    data = (json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8")
    decode_package(data)
    return data
