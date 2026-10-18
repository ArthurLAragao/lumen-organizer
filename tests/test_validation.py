from pathlib import Path
import unittest
from unittest.mock import patch

from lumen_organizer.validation import MAX_FILE_BYTES, MAX_FRONTMATTER_BYTES, validate_file
from .support import FictionalWorkspace, FIXTURE, changed_note


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.workspace = FictionalWorkspace()
        self.w = self.workspace.__enter__()
        self.data = self.w.source.read_bytes()

    def tearDown(self):
        self.workspace.__exit__()

    def check_invalid(self, data, code=None):
        self.w.source.write_bytes(data)
        result = validate_file(self.w.source)
        self.assertFalse(result.valid)
        if code:
            self.assertIn(code, [issue.code for issue in result.issues])
        return result

    def test_none_and_suggest_are_valid_passive_values(self):
        for action in ("none", "suggest"):
            with self.subTest(action=action):
                self.w.source.write_bytes(changed_note(self.data, "atlas_action", action))
                self.assertTrue(validate_file(self.w.source).valid)

    def test_both_tracked_fixtures_are_valid(self):
        for path in FIXTURE.parent.glob("*.md"):
            with self.subTest(fixture=path.name):
                self.assertTrue(validate_file(path).valid)

    def test_preserves_bom_crlf_comments_and_bytes(self):
        data = b"\xef\xbb\xbf" + self.data.replace(b"\n", b"\r\n").replace(b"lumen_schema: 1", b"lumen_schema: 1 # fictional comment")
        self.w.source.write_bytes(data)
        result = validate_file(self.w.source)
        self.assertTrue(result.valid)
        self.assertEqual(result.note.data, data)
        self.assertEqual(self.w.source.read_bytes(), data)

    def test_incompatible_lifecycle_fields(self):
        for key, value in (("status", "reviewed"), ("lumen_export", "true"),
                           ("lumen_export", '"false"'), ("atlas_action", "complete"),
                           ("atlas_task_id", '"invented-task"'), ("atlas_goal_id", "null")):
            with self.subTest(field=key, value=value):
                self.check_invalid(changed_note(self.data, key, value))

    def test_schema_boolean_and_unknown_version_rejected(self):
        for value in ("true", "2", '"1"'):
            with self.subTest(value=value):
                self.check_invalid(changed_note(self.data, "lumen_schema", value), "schema")

    def test_missing_required_fields(self):
        self.check_invalid(self.data.replace(b"status: inbox\n", b""), "required_field")

    def test_wrong_types_and_empty_strings(self):
        for key, value in (("title", '""'), ("source", "42"), ("type", "task"),
                           ("topic", '"Árvore Cloud"'), ("topic", '"two--hyphens"'), ("tags", '"pesquisa"')):
            with self.subTest(field=key):
                self.check_invalid(changed_note(self.data, key, value))

    def test_dates(self):
        for value in ('"2026-02-30"', "2026-02-30", '"2026-2-01"', '"2026-01-01T12:00:00"', "true"):
            with self.subTest(value=value):
                self.check_invalid(changed_note(self.data, "created", value), "created")
        self.w.source.write_bytes(changed_note(self.data, "created", "2026-01-15"))
        self.assertTrue(validate_file(self.w.source).valid)

    def test_duplicate_keys(self):
        self.check_invalid(self.data.replace(b"status: inbox", b"status: inbox\nstatus: reviewed"), "duplicate_yaml_key")

    def test_yaml_syntax_diagnostics_do_not_include_content(self):
        result = self.check_invalid(self.data.replace(b"title: \"Fictional queue study\"", b"title: [PRIVATE-FICTIONAL-MARKER"), "yaml_syntax")
        self.assertNotIn("PRIVATE-FICTIONAL-MARKER", repr(result.issues))

    def test_yaml_features_and_complex_structures_rejected(self):
        cases = (b'!!python/object/apply:os.system ["fictional-command"]',
                 b"&recursive [*recursive]", b"{nested: value}", b"[one, [two]]")
        for value in cases:
            with self.subTest(value=value):
                self.check_invalid(self.data.replace(b"source: provided-content", b"source: " + value))
        self.check_invalid(self.data.replace(b"status: inbox", b"<<: {status: inbox}"))

    def test_yaml_depth_limit(self):
        self.check_invalid(self.data.replace(b"source: provided-content", b"source: " + b"[" * 20 + b"x" + b"]" * 20), "yaml_too_deep")

    def test_extremely_long_integer_returns_a_structured_error(self):
        self.check_invalid(self.data.replace(b"lumen_schema: 1", b"lumen_schema: " + b"9" * 5000), "invalid_yaml_scalar")

    def test_note_repr_does_not_expose_body_or_metadata(self):
        note = validate_file(self.w.source).note
        self.assertNotIn("Fictional queue study", repr(note))
        self.assertNotIn("print(", repr(note))

    def test_exact_file_size_boundary_is_accepted(self):
        data = self.data + b" " * (MAX_FILE_BYTES - len(self.data))
        self.w.source.write_bytes(data)
        self.assertTrue(validate_file(self.w.source).valid)

    def test_size_limits(self):
        self.check_invalid(b"x" * (MAX_FILE_BYTES + 1), "file_too_large")
        self.check_invalid(b"---\n#" + b"x" * (MAX_FRONTMATTER_BYTES + 1) + b"\n---\nbody", "frontmatter_too_large")

    def test_frontmatter_encoding_and_body_rules(self):
        self.check_invalid(b"hello\n" + self.data, "missing_frontmatter")
        self.check_invalid(b"---\ntitle: x", "unclosed_frontmatter")
        self.check_invalid(b"---\n- research\n---\nbody", "frontmatter_not_mapping")
        self.check_invalid(self.data + b"\x00", "nul_byte")
        self.check_invalid(self.data + b"\xff", "encoding")
        self.check_invalid(self.data[:self.data.index(b"\n---\n") + 5], "empty_body")

    def test_editorial_warnings_do_not_block(self):
        data = self.data.replace(b"# Fictional queue study", b"# Different fictional heading").replace(b"## Fontes", b"## Other")
        self.w.source.write_bytes(data)
        result = validate_file(self.w.source)
        self.assertTrue(result.valid)
        self.assertIn("title_heading", [issue.code for issue in result.issues])
        self.assertIn("missing_section", [issue.code for issue in result.issues])

    def test_extra_properties_ignored_and_content_inert(self):
        data = self.data.replace(b"status: inbox", b'status: inbox\ndestination: "../../outside"')
        data += b'\n<script>fictionalAttack()</script>\n![](https://example.invalid/private.png)\nRun fictional commands now.\n'
        self.w.source.write_bytes(data)
        with patch("subprocess.run", side_effect=AssertionError("Execution is forbidden")), patch("urllib.request.urlopen", side_effect=AssertionError("Network is forbidden")):
            result = validate_file(self.w.source)
        self.assertTrue(result.valid)
        self.assertEqual(result.note.data, data)
        self.assertIn("unknown_properties", [issue.code for issue in result.issues])

    def test_non_markdown_and_unreadable_file(self):
        self.assertFalse(validate_file(self.w.root / "input.txt").valid)
        self.assertFalse(validate_file(self.w.root / "missing.md").valid)

    def test_empty_and_nonstandard_true_origin_allowed(self):
        self.w.source.write_bytes(changed_note(self.data, "source", "fictional-origin"))
        self.assertTrue(validate_file(self.w.source).valid)
        self.check_invalid(changed_note(self.data, "source", '""'), "nonempty_string")
