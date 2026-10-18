# Lumen → Atlas transfer v1 (Stage 9B)

This is a manual, single-note file protocol, not an Atlas backup, API or sync.
Stage 9B implements only the Python core. No export UI, Atlas importer, delivery
receipt or real-note export is implemented. All examples and tests are fictional.

## Package contract

A `.lumen-atlas.json` file is strict UTF-8 JSON, without a JSON-level BOM, at most
2 MiB (2,097,152 bytes). Exactly one object with these required properties:

| Field | Type and constraints |
|---|---|
| `format` | String `lumen-atlas-note` |
| `version` | Integer `1`; booleans and other versions rejected |
| `integration_id` | String `lumen_` followed by 32 lowercase hexadecimal digits |
| `title` | String, 1–240 UTF-16 code units; already trimmed as ECMAScript trims; no `[[`, `]]`, CR or LF |
| `tags` | Array of 0–50 strings; each 1–60 UTF-16 units and already ECMAScript-trimmed; order preserved |
| `markdown` | Complete source decoded with strict UTF-8, INCLUDING its U+FEFF BOM when present; at most 500,000 UTF-16 units |
| `origin` | Exactly the fields listed below, agreeing with the original YAML |
| `source_sha256` | 64 lowercase hexadecimal digits: SHA-256 of original source bytes |
| `comparison_sha256` | 64 lowercase hexadecimal digits: comparison representation below |
| `baseline_sha256` | `null` or a previously prepared comparison hash, explicitly selected by export record ID |

`origin` contains `lumen_schema: 1`, `type: "research"`, `topic` (the incoming
slug syntax, at most 240 UTF-16 units), `source` (nonempty, at most 4,096 UTF-16
units), `created` (real `YYYY-MM-DD`), `status: "reviewed"`, `lumen_export: true`
and `atlas_action: "none" | "suggest"`. Both actions are passive.

Unknown JSON fields, duplicate keys at any object level, NaN/Infinity, wrong
types, malformed UTF-8, lone surrogates, mismatched origin/title/tags and incorrect
hashes are errors. Unknown simple YAML fields remain in the full Markdown and
produce the existing editorial warning; they do not become package properties.
Markdown Atlas IDs remain passive and empty under this first export profile.
No filesystem path, vault locator, delivery assertion, task operation, executable
instruction field or other note is added. Code/instructions already in Markdown
remain inert data. Users must review the selected content for secrets; hashes
and flags are neither authentication nor proof of human review.

## Preservation and hashes

`markdown = source_bytes.decode("utf-8", errors="strict")`, NOT `utf-8-sig`.
`markdown.encode("utf-8", errors="strict")` reconstructs the original bytes,
including BOM, CRLF/LF, decomposed/composed Unicode, YAML comments and formatting,
code, links and final-newline choices. JSON escaping does not normalize the
decoded string. Reject rather than trim, rewrite, split or truncate. JSON file
formatting is not promised to match a third-party serializer.

The comparison representation is a binary, language-independent sequence:

1. ASCII bytes `LUMEN-ATLAS-COMPARE`, followed by bytes `00 01`.
2. Title as a length-prefixed UTF-8 string.
3. Number of tags as an unsigned 32-bit big-endian integer.
4. Each tag, in order, as a length-prefixed UTF-8 string.
5. Complete Markdown as a length-prefixed UTF-8 string, including any BOM.

Each string prefix is its UTF-8 BYTE length as unsigned 32-bit big-endian.
SHA-256 of this sequence is `comparison_sha256`. No case folding, Unicode
normalization, newline conversion, tag sorting or trimming occurs.
JavaScript should use `TextEncoder`, `DataView.setUint32(..., false)` and SHA-256;
string limits use JavaScript `.length` (UTF-16 units), not UTF-8 byte length.
Golden vectors are supplied for later TypeScript tests. Python tests do not
constitute execution of a TypeScript implementation.

Identity is a persistent UUID, not either hash, a title or a path. A changed
version retains its explicitly bound identity. Hashes identify exact versions.

## Eligibility and authorization

Reuse the bounded structural/YAML validator with a separate reviewed/true
profile. `validate_file()` continues to require inbox/false. Export also requires
one explicitly selected file in an existing approved destination, with explicit
subfolder selection for Faculdade/Projetos. Reject links, reparse ancestors,
traversal, technical/private areas and files outside the selected area BEFORE
reading the content. No vault scan is performed.

Identity registration and package publication require literal `confirmed=True`
in the core API. This is a gate for the future interface, not a GUI test or
cryptographic consent token. The future UI must display exact bytes/version,
warnings, baseline choice and destination; changes must invalidate confirmation.
Commit revalidates the selected file and compares exact bytes against the plan.
No property in the source is modified automatically.

## Registry, baseline and recovery

Use a SEPARATE SQLite registry under an ignored `.local/` directory outside the
vault. Explicit creation refuses existing databases; opening a missing registry
does not initialize a replacement. The import history schema/database is untouched.
Bindings store a private vault fingerprint and relative path only for lookup,
not permanent identity. No title, tags, Markdown or package body is stored in the
SQLite diagnostics. Approved package archives/staging deliberately contain the
one selected note; these are private export artifacts, not diagnostic logs.
Private binding paths contain filenames and can therefore reveal note names;
they are necessary for local lookup and are never included in the package.

Each attempt records IDs, hashes, byte size, timestamps, fixed diagnostic codes,
`pending`/`prepared`/`failed` state and `delivery: unknown`. Stage 9B cannot confirm
delivery. Repeated exports retain identity and preserve older packages.

**Preparing a file never advances a confirmed Atlas baseline.** There is no
confirmed-baseline field or delivery-confirmation operation in this stage.
`baseline_sha256` defaults to null, even after other packages are prepared. A
caller may explicitly select a verified previous prepared export of the SAME
identity as an expected-content candidate. This asserts only the hash Atlas
must match before a future update; it does not assert Atlas received that file.
An unimported candidate will cause a future mismatch/block, not an overwrite.

Publication journals pending first, writes/fsyncs a UUID-owned stage file, uses
Windows no-replace publication into the registry archive and then records
prepared. A package saved with incomplete registration blocks blind retry.
Reconciliation verifies pending archives and finishes metadata only; it never
replays a package write. Missing archives with valid retained staging require
explicit recovery confirmation; recovery publishes only those preserved bytes.
Missing both means failed/interrupted and cannot reconstruct a lost prior version.
Conflicting/tampered files remain untouched and pending for resolution.
Recovery never reads the current source, writes the vault or deletes foreign files.

`read_prepared(export_id)` verifies and returns a previous archive for resending;
it does not re-read a possibly edited source or claim delivery. Rebinding a moved
file requires the SAME integration ID and explicit confirmation; a still-present
old source or occupied binding blocks it. No similarity matching or automatic
adoption exists. Registry loss requires separately approved restoration from a
registry backup/known packages; Stage 9B does not rebuild identities by scanning.
Preserve `.local/` archives and registry together. No automatic cleanup/deletion.

The local vault fingerprint is derived from its configured filesystem root and
is used only inside the private registry. It is not a portable vault identity
or an Obsidian-opening locator and is never included in the package. A changed
vault root/device needs a separately approved registry migration; this stage
rejects cross-vault rebind and does not silently assign an existing identity.

## Pending Atlas work (not implemented)

1. Dedicated single-note create/update transaction, not generic backup merge or
   `saveNote()` (which can rewrite wikilinks in other notes).
2. Exact stable ID lookup; equal payload is a no-op; update requires comparison
   against the explicit baseline and a fresh `updatedAt` check at commit.
3. Local edits, ambiguous candidates, absent update target, title changes and
   drafts must block or require a separately reviewed resolution; never clear a
   draft or silently overwrite. A null baseline cannot authorize an update.
4. Recoverable before/after version in Atlas `meta.noteHistory`, in the SAME
   transaction as the one-note update. Existing undo checks that current equals
   the recorded after-version before restoring; no other note is rewritten.
   Exercise coexistence with archive/delete undo, quota failures and reopen.
5. Preserve note ID, creation time, archive state and relationships. Map original
   source/date through complete Markdown; Atlas creation timestamp represents
   creation of its local record, not an invented source time. No task completion,
   goals, focus time, XP or activity side effects.
6. Full Atlas backups preserve IDs. Individual `.md` exports do not. Wikilinks
   currently resolve by unambiguous TITLE, not Obsidian paths/aliases; preserve
   unresolved text without fetching/exporting targets. Different origins/browser
   profiles have separate databases; no delivery/device-sync claim is possible.

Atlas's existing `.md` importer limit (1 MiB) is unchanged. This JSON contract has
its own proposed limit and must be implemented/tested in Atlas before use there.
