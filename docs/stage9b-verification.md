# Stage 9B verification — 2026-10-10

Only the Lumen transfer core was implemented. Atlas code was consulted for
compatibility; Atlas files, database, schema and personal data were not changed.
No real research was read/exported, no real vault was accessed by the new tests,
no skill was changed and no dependencies were added. No commit/push/deploy.

## Actual execution

| Run | Result | Time |
|---|---|---|
| Existing baseline, before edits | 99 tests; 0 failures/errors/skips | 14.857 s |
| Final focused transfer/export suite | 45 tests; 0 failures/errors/skips | 4.256 s |
| Final complete suite | 144 tests; 0 failures/errors/skips | 18.163 s |

These are automated Python/core/Tk widget regressions. They are not a visual
review of an export interface, an Atlas import, a real-data test, or executed
Python/TypeScript interoperability. No export UI/Atlas importer exists yet.
Recovery tests inject interruptions/failed writes; physical power loss and
hardware durability were not tested. Windows junction rejection, no-replace
collisions, locks and the write boundary executed in the Windows environment.

The first focused run had two fixture encoding failures (JSON surrogate escapes
used for YAML emoji limit tests) and one test cleanup error (unclosed SQLite
connection). Fixtures now use actual UTF-8 emoji and the test closes its database.
No behavioral test was removed. Subsequent focused and full suites passed.

## Reproduce

From a PowerShell terminal in the Lumen project, with its existing `.venv`:

```powershell
.\.venv\Scripts\python.exe -B tools\run_tests.py
```

Focused suite:

```powershell
.\.venv\Scripts\python.exe -B -c "import sys, unittest; sys.path.insert(0, 'src'); suite=unittest.defaultTestLoader.loadTestsFromNames(['tests.test_atlas_transfer','tests.test_atlas_export']); result=unittest.TextTestRunner(verbosity=2).run(suite); sys.exit(not result.wasSuccessful())"
```

Tests create only fictional notes/vaults under `.local/test-temp`, use the
existing audited write boundary for export operations, and remove their own
temporary workspaces. No test uses local real-vault settings or real browser DBs.
Tests assert unchanged fictional source/vault bytes and unchanged import-history
bytes/operations across export. Real history is not opened for those assertions.

## Core API (no new CLI or UI)

- `validate_export_file(source, policy, category, subfolder=None)` checks an
  explicitly allowed location before reading, then shared structural validation,
  reviewed/true eligibility and Atlas compatibility. Returns errors/warnings.
- `ExportRegistry.create(state_directory, vault_root)` explicitly initializes
  separate private state; `open(...)` refuses missing/unrecognized state.
- `AtlasExporter(policy, registry).register(..., confirmed=True)` explicitly
  registers a note identity. `prepare(...)` does not publish a package.
- `commit(plan, confirmed=True)` checks the current source against the selected
  version, journals pending, publishes outside the vault without replacement,
  verifies the archive and records prepared/delivery-unknown.
- `prepare(..., baseline_export_id=...)` requires explicit selection of a verified
  previous package of the same identity. It is an expected-content candidate,
  never proof of delivery. Omitting it always leaves the baseline null.
- `read_prepared(export_id)` retrieves exact archived bytes for resend.
- `reconcile()` verifies archives/metadata only. `recover(export_id,
  confirmed=True)` can publish a complete verified retained stage; it never
  reconstructs it from the current source.
- `rebind(integration_id, source, category, ..., confirmed=True)` preserves the
  explicit identity after a move; a present old source, occupied binding,
  pending export or another vault blocks it.

The first version targets Windows for safe file publication/directory guards.
Other platforms are explicitly unsupported for that operation. These low-level
confirmation booleans are intended for a future reviewed UI workflow; they do
not themselves prove human consent or review of note content.

## Fictitious inspectable artifacts

- `tests/fixtures/atlas-export/reviewed.md`: authorized reviewed/true technical
  fixture, no real research or personal data.
- `tests/fixtures/atlas-export/example.lumen-atlas.json`: 1,579-byte strict package
  for that fixture, fixed fictitious ID `lumen_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`,
  baseline null. Reconstructed source SHA-256:
  `f57f8ac5e245538b6701c364d4be0de714dc23b5e13849f6dca9ad495efb904c`.
- `tests/fixtures/atlas-export/hash-vectors.json`: five independently framed
  vectors covering ASCII, BOM/CRLF, Unicode/emoji/decomposed characters, escaping
  and tag order. Python verifies raw bytes, preimage hex and expected digests.
  TypeScript execution is pending; do not claim it passed.

Fixtures remain included in Git; private `.local/` databases/archives are ignored.
The source/example fixtures disable Git text conversion in `.gitattributes` so
Windows `core.autocrlf` cannot invalidate their exact-byte reference relationship.
The vector file uses LF. Attributes were checked with `git check-attr`; no actual
commit/checkout round trip was performed in this stage.
Package archives intentionally contain the one approved note. SQLite events and
record diagnostics do not store bodies, titles, tags or raw exceptions. Input
content is not redacted: the generator adds no paths/secrets, but a future user
must review the selected note before explicitly approving its unchanged contents.

## Recovery/Atlas work still pending

- No delivery receipt or operation can mark an Atlas import confirmed.
- No automatic baseline advancement or bidirectional synchronization.
- A lost archive without retained staging cannot be reconstructed as an old
  version; a partial/conflicting stage remains blocked and untouched.
- Registry loss/partially initialized registry needs a separately approved
  restoration procedure; no scanning/similarity reconstruction is implemented.
- Native GUI confirmation, drafts/conflicts, one-note transactional Atlas import,
  before/after storage and recovery in `meta.noteHistory`, and backup/undo
  coexistence remain pending. Details are in `lumen-atlas-transfer-v1.md`.
- Atlas origin/browser isolation and title-only wikilink resolution remain.
  Source date/origin are preserved in the full Markdown; no source time is invented.

Git inspection: Atlas clean on `main` at `5a113da`; Lumen has an unborn `master`
and pre-existing untracked project files. Changes in this stage are only the new
transfer modules/tests/fixtures/docs and edits to README/shared validation. No
tracked/staged files, commits or existing work were discarded.
