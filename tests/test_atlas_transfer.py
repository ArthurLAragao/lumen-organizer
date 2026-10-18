from hashlib import sha256
import json
from pathlib import Path
import unittest

from lumen_organizer.atlas_transfer import (
    MAX_PACKAGE_BYTES, atlas_compatible, comparison_bytes, comparison_hash,
    decode_package, encode_package, utf16_units,
)
from lumen_organizer.models import LumenError
from lumen_organizer.validation import _validate_bytes, validate_file
from .support import FictionalWorkspace, changed_note

FIXTURE = Path(__file__).parent / "fixtures" / "atlas-export" / "reviewed.md"
IDENTITY = "lumen_" + "a" * 32


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.raw = FIXTURE.read_bytes()
        self.note = _validate_bytes(Path("fictional.md"), self.raw, export_profile=True).note

    def check(self, raw):
        return atlas_compatible(_validate_bytes(Path("fictional.md"), raw, export_profile=True))

    def test_incoming_profile_remains_strict_and_export_profile_is_separate(self):
        with FictionalWorkspace() as w:
            self.assertTrue(validate_file(w.source).valid)
            w.source.write_bytes(self.raw)
            self.assertFalse(validate_file(w.source).valid)
        for status, flag, valid in (("inbox", "false", False), ("inbox", "true", False),
                                    ("reviewed", "false", False), ("reviewed", "true", True)):
            with self.subTest(status=status, flag=flag):
                raw = changed_note(changed_note(self.raw, "status", status), "lumen_export", flag)
                self.assertEqual(self.check(raw).valid, valid)

    def test_wrong_types_and_passive_ids_and_actions(self):
        for name, value in (("lumen_schema", "true"), ("lumen_schema", "2"), ("status", "42"),
                            ("lumen_export", '"true"'), ("lumen_export", "null"), ("tags", '"x"'),
                            ("atlas_action", "complete"), ("atlas_task_id", '"task"'),
                            ("atlas_goal_id", '"goal"'), ("created", '"2026-02-30"')):
            with self.subTest(field=name):
                self.assertFalse(self.check(changed_note(self.raw, name, value)).valid)
        for action in ("none", "suggest"):
            self.assertTrue(self.check(changed_note(self.raw, "atlas_action", action)).valid)

    def test_structural_protections_apply_to_export(self):
        for raw in (self.raw + b"\x00", self.raw + b"\xff", self.raw.replace(b"status: reviewed", b"status: reviewed\nstatus: reviewed"),
                    changed_note(self.raw, "source", "&recursive [*recursive]"),
                    changed_note(self.raw, "source", "{nested: data}"), b"---\ntitle: [PRIVATE-FICTIONAL\n---\nbody"):
            result = self.check(raw)
            self.assertFalse(result.valid)
            self.assertNotIn("PRIVATE-FICTIONAL", repr(result.issues))

    def test_title_limits_use_utf16_and_reject_silent_trimming(self):
        for title, valid in (("😀" * 120, True), ("😀" * 121, False), ("x" * 240, True),
                             ("x" * 241, False), (" padded ", False), ("\ufeffpadded", False),
                             ("[[reserved]]", False), ("line\nbreak", False)):
            with self.subTest(units=utf16_units(title)):
                self.assertEqual(self.check(changed_note(self.raw, "title", json.dumps(title, ensure_ascii=False))).valid, valid)
        # ECMAScript trim does not strip U+0085; Python str.strip would.
        self.assertTrue(self.check(changed_note(self.raw, "title", json.dumps("\u0085title\u0085"))).valid)

    def test_tag_count_length_and_exact_order(self):
        for tags, valid in ((["t"] * 50, True), (["t"] * 51, False), (["😀" * 30], True),
                            (["😀" * 31], False), ([""], False), ([" x"], False), ([], True)):
            with self.subTest(count=len(tags)):
                self.assertEqual(self.check(changed_note(self.raw, "tags", json.dumps(tags, ensure_ascii=False))).valid, valid)
        package = decode_package(encode_package(self.note, IDENTITY))
        self.assertEqual(package.tags, ("fictional", "teste"))

    def test_content_limit_includes_yaml_and_bom(self):
        text = self.raw.decode("utf-8")
        exact = text + "a" * (500_000 - utf16_units(text))
        self.assertTrue(self.check(exact.encode("utf-8")).valid)
        self.assertFalse(self.check((exact + "a").encode("utf-8")).valid)
        self.assertFalse(self.check(("\ufeff" + exact).encode("utf-8")).valid)
        emoji = text + "😀" * ((500_000 - utf16_units(text)) // 2)
        self.assertTrue(self.check(emoji.encode("utf-8")).valid)
        self.assertFalse(self.check((emoji + "😀").encode("utf-8")).valid)

    def test_origin_bounds_and_lone_surrogates(self):
        for name, value in (("source", "x" * 4097), ("topic", "x" * 241), ("title", "\ud800")):
            self.assertFalse(self.check(changed_note(self.raw, name, json.dumps(value))).valid)

    def test_preserves_exact_utf8_bom_crlf_unicode_code_links_yaml(self):
        raw = b"\xef\xbb\xbf" + self.raw.replace(b"\n", b"\r\n") + "\r\nÁ / A\u0301 / 😀 / \\ / \"\r\n".encode("utf-8")
        result = self.check(raw)
        packet = encode_package(result.note, IDENTITY)
        decoded = decode_package(packet)
        self.assertEqual(decoded.source_bytes, raw)
        self.assertEqual(decoded.source_sha256, sha256(raw).hexdigest())
        self.assertTrue(decoded.markdown.startswith("\ufeff---\r\n"))
        self.assertIn("[[Fictional missing note]]", decoded.markdown)
        self.assertIn("```python", decoded.markdown)
        self.assertNotIn(IDENTITY, decoded.markdown)

    def test_hash_determinism_and_no_normalization(self):
        self.assertEqual(encode_package(self.note, IDENTITY), encode_package(self.note, IDENTITY))
        first = comparison_hash("Title", ["a", "b"], "text\r\n")
        for title, tags, content in (("title", ["a", "b"], "text\r\n"), ("Title", ["b", "a"], "text\r\n"),
                                     ("Title", ["a", "b"], "text\n"), ("Title", ["a", "b"], " text\r\n")):
            self.assertNotEqual(first, comparison_hash(title, tags, content))
        self.assertNotEqual(comparison_hash("Á", [], "x"), comparison_hash("A\u0301", [], "x"))
        self.assertEqual(utf16_units("a😀A\u0301"), 5)

    def test_golden_vectors_for_future_typescript(self):
        path = FIXTURE.parent / "hash-vectors.json"
        vectors = json.loads(path.read_text(encoding="utf-8"))
        for vector in vectors:
            with self.subTest(vector=vector["name"]):
                self.assertEqual(comparison_bytes(vector["title"], vector["tags"], vector["markdown"]).hex(), vector["comparison_preimage_hex"])
                self.assertEqual(comparison_hash(vector["title"], vector["tags"], vector["markdown"]), vector["comparison_sha256"])
                self.assertEqual(vector["markdown"].encode("utf-8").hex(), vector["source_utf8_hex"])
                self.assertEqual(sha256(vector["markdown"].encode("utf-8")).hexdigest(), vector["source_sha256"])
                self.assertEqual(utf16_units(vector["markdown"]), vector["markdown_utf16_units"])

    def test_example_fixture_is_valid_and_byte_reconstructible(self):
        packet = decode_package((FIXTURE.parent / "example.lumen-atlas.json").read_bytes())
        self.assertEqual(packet.source_bytes, self.raw)
        self.assertIsNone(packet.baseline_sha256)

    def test_unknown_duplicate_fields_invalid_types_and_hashes_rejected(self):
        original = json.loads(encode_package(self.note, IDENTITY))
        for key, value in (("extra", "unrecognized"), ("version", True), ("version", 2),
                           ("integration_id", "../../escape"), ("tags", [42]), ("title", "Different"),
                           ("source_sha256", "b" * 64), ("comparison_sha256", "b" * 64),
                           ("baseline_sha256", "not-a-hash")):
            with self.subTest(key=key):
                payload = {**original, key: value}
                with self.assertRaises(LumenError):
                    decode_package(json.dumps(payload).encode())
        for origin in ({**original["origin"], "extra": "x"}, {**original["origin"], "lumen_schema": True}):
            with self.assertRaises(LumenError):
                decode_package(json.dumps({**original, "origin": origin}).encode())
        for raw in (b'{"format":"x","format":"y"}', b'NaN', b'[]', b'\xef\xbb\xbf{}', b'\xff', b'{"x":Infinity}',
                    b'[' * 2000 + b']' * 2000):
            with self.assertRaises(LumenError):
                decode_package(raw)

    def test_packet_size_bound_and_json_expansion_not_truncated(self):
        with self.assertRaises(LumenError):
            decode_package(b" " * (MAX_PACKAGE_BYTES + 1))
        raw = self.raw + b"\x01" * 350_000
        note = self.check(raw).note
        self.assertIsNotNone(note)
        with self.assertRaises(LumenError) as error:
            encode_package(note, IDENTITY)
        self.assertEqual(error.exception.code, "transfer_size")
        self.assertEqual(note.data, raw)

    def test_unknown_yaml_and_editorial_warnings_are_retained(self):
        raw = self.raw.replace(b"status: reviewed", b'status: reviewed\nextra: "fictional value"').replace(b"## Fontes", b"## Other")
        result = self.check(raw)
        self.assertTrue(result.valid)
        self.assertIn("unknown_properties", [issue.code for issue in result.issues])
        self.assertIn("missing_section", [issue.code for issue in result.issues])
        package = decode_package(encode_package(result.note, IDENTITY))
        self.assertEqual(package.source_bytes, raw)
        self.assertNotIn("extra", package.origin)

    def test_package_repr_never_contains_note_content(self):
        packet = decode_package(encode_package(self.note, IDENTITY))
        self.assertNotIn("Fictional Atlas transfer", repr(packet))
        self.assertNotIn("print(", repr(packet))
