# Lumen Organizer

Local Python application for validating Lumen v1 Markdown notes and importing
an explicitly approved file into a configured Obsidian vault. Stages 1-6 include
the core, a Portuguese Tkinter/ttk desktop interface, and automated verification
with fictional vaults. The approved stage 6B visual refinement and stage 6C
regression review are implemented; the user approved the manual fictional flow.
Stage 7 verified one explicitly confirmed technical test import into the real
vault: exact bytes, successful history, and user-confirmed opening in Obsidian.
This authorizes no additional real-note imports, batch work, or automatic cleanup.
See [the controlled Stage 7 evidence](docs/verification.md#stage-7b-7c-controlled-real-vault-result-2026-10-10).

The desktop reuses the validator, destination policy, SQLite history, safe
importer, and recovery. The developer CLI offers environment inspection and
validation only; it has no command for importing files.
No AI, API keys, Atlas connection, interface automation, or network activity
exists in the runtime. Initial dependency installation is a separate step.

Stage 9B adds a tested, single-note `.lumen-atlas.json` transfer core: a separate
reviewed/true export profile, persistent identity registry and confirmed package
publication/recovery outside the vault. Stage 9D exposes it through a separate
desktop export window; the matching Atlas import interface lives in the Atlas
project. Saving a package does not confirm delivery. There is no export CLI.
The incoming inbox/false contract and byte-preserving Obsidian importer remain
unchanged.
See [transfer v1 and recovery](docs/lumen-atlas-transfer-v1.md) and
[Stage 9B evidence and API](docs/stage9b-verification.md). All transfer tests and
the sample package use fictional data; no real research was read or exported.

## Environment and tests

From the project directory, in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe tools\run_tests.py
.\.venv\Scripts\python.exe tools\lumen.py check-environment
.\.venv\Scripts\python.exe tools\lumen.py validate tests\fixtures\research-none.md
```

Use a trusted local wheel with `pip install --no-index --find-links <wheel-folder>`
when fully offline setup is required. No global installation is needed.

Some managed Windows environments make Python's mode-0700 temporary directories
inaccessible. For that case, the local bootstrap helper uses inherited workspace
ACLs under `.local/setup-temp`:

```powershell
python -m venv --without-pip .venv
.\.venv\Scripts\python.exe tools\setup_environment.py
# Only with permission to download the PyYAML dependency:
.\.venv\Scripts\python.exe tools\setup_environment.py --download-pyyaml
```

The helper installs pip from Python's bundled wheel. The optional download is
limited to PyYAML from PyPI; it installs no transitive dependencies. Runtime
code and tests never request external resources. Test workspaces use inherited
ACLs under `.local/test-temp`, and are removed after each test.

See [the test evidence and limitations](docs/verification.md).

## Open the desktop

With the existing virtual environment, from the project directory:

```powershell
.\.venv\Scripts\python.exe tools\lumen.py gui
```

No additional runtime dependencies are required. Tkinter/ttk and SQLite belong
to Python's standard library; PyYAML remains the only external runtime package.
The desktop uses one background worker for filesystem and history operations.
Tk's main thread receives results through a queue and `after`; workers never
update widgets. Large previews are inserted in short chunks on the main thread.

The desktop has an Atlas-led neutral dark theme using built-in `clam` styles.
A compact vault header sits above a selection/destination sidebar and a broad
reading area. Errors, metadata, and results remain secondary tabs; pending
history is checked through **Conferir histórico**. The fixed lower area keeps
the full destination and **Revisar importação** available before the separate
**Confirmar importação** dialog. Folder actions appear for Faculdade/Projetos.
Long paths stay in selectable, read-only scrolling fields. The preview retains
the complete YAML and Markdown, with Ctrl+A/Ctrl+C and two-axis scrolling.

`styles.py` centralizes colors, point sizes, font fallbacks, and the spacing
scale. Segoe UI/Arial and Consolas/Cascadia Mono fall back to Tk system fonts.
No font or asset is downloaded. Sizes follow Tk's current display scaling; the
window minimum is approximately 900×620 at 100%, scaled and capped to the screen.
Destination fields scroll when space is limited, while action buttons remain
outside that viewport. Actual Windows DPI/monitor changes require manual review.

For this review, generate only fictional inputs and folders:

```powershell
.\.venv\Scripts\python.exe tools\create_demo.py
```

The helper prints a unique `.local/demos/<id>/Vault-Ficticio` root and input
paths. It does not change the application's configuration or history. See
[the fictional desktop walkthrough](docs/gui-workflow.md) for the full flow.

## Local configuration

There is no default personal vault path in the code. `config.example.json`
contains only a fictional example. Choosing **Selecionar vault** saves the
configuration in the project's ignored `.local/settings.json`:

```json
{
  "vault_root": "C:\\Vaults\\Fictional-Lumen-Demo"
}
```

Startup loads this local configuration if it exists. Cancelling a picker keeps
the previous selection. Unexpected settings files are preserved and reported.
Loading and saving delegate path checks to the existing core; settings and
history must remain outside the selected vault. No vault folder is created by
the desktop. Every target folder must already exist.
University and project categories require an explicitly chosen existing
descendant folder. `.local/` and local configuration files are ignored by Git;
fictional fixtures remain visible to Git.

## Core API and confirmation boundary

The core separates these operations:

1. `validate_file(path)` returns errors/warnings or an immutable byte snapshot.
2. `DestinationPolicy(vault_root)` binds the authorized destination tree.
3. `Organizer(policy, state_directory)` opens local history outside the vault.
4. `prepare(note, category, subfolder, filename)` proposes a complete destination.
5. `commit(plan, confirmed=True)` is called only after the user approves that
   exact destination. Omitting confirmation or passing false cancels the import.
6. `reconcile()` checks recorded pending operations after interruption. It does
   not replay writes into the vault.

The interface presents these three separate concepts:

| Concept | Meaning in this version |
|---|---|
| Import completed | The approved bytes were saved and success was journaled |
| Content reviewed | A separate manual activity; import leaves `status: inbox` |
| Export authorized | A separate manual activity; import leaves `lumen_export: false` |

`atlas_action: none` and `suggest` are both passive metadata. Neither authorizes
an Atlas operation. Notes never trigger filesystem paths, commands, model calls,
task completion, or goal updates.

## Saving, duplicates, and recovery

- The selected source is revalidated and compared to the approved bytes at commit.
- The destination is derived from the allowlist, never from note metadata.
- Fixed categories use exact mapped folders. Folder selection lists directory
  names only; existing notes are not scanned.
- A filename collision proposes a numbered alternative in a new plan. A collision
  appearing after preparation blocks the old plan; it never overwrites a file.
- Windows directory handles prevent ancestor renames while committing. Reparse
  points and junctions are rejected. Publication uses Windows no-replace rename.
- A fully written, flushed staging file is kept outside the vault on the same
  filesystem. An incompatible staging volume blocks import.
- A pending operation is committed to SQLite before publication. The saved
  checksum is verified before recording success.
- `saved_history_incomplete` means the file exists but the success record failed.
  It must not be presented as an ordinary failed save or retried blindly.
- Recovery marks a matching pending destination successful. An absent or
  conflicting destination becomes a failed operation. Recovery never edits or
  deletes a vault note; cleanup is limited to journal-owned staging filenames.
- Missing/unsafe destination parents leave recovery blocked and pending. Resolve
  the folder issue explicitly before new imports; no folder is recreated silently.

Duplicate detection compares SHA-256 of exact bytes against successful operations
recorded for this configured vault. It recognizes renamed input files, but does
not identify semantic duplicates, differences in line endings, or untracked old
notes. A changed/missing recorded note is reported separately. A repeat requires
an explicit new core plan with `allow_repeat=True` and a new confirmation; intact
duplicates remain blocked. The desktop does not expose repeat overrides for
missing/changed previous imports. It asks the user to inspect the previous
import instead. Clearing history removes this detection capability.

The desktop starts with no category selected. It displays structural errors and
editorial warnings separately, a metadata summary, and the complete original
Markdown as inert read-only text. HTML, links, embeds, and code are displayed
without rendering, opening, or fetching resources. The category is chosen
manually. A prepared destination includes the complete path and final filename.
**Revisar importação** opens the confirmation dialog, which repeats the complete
destination, collision suffix, and warnings in selectable scrolling fields.
It requires clicking **Confirmar importação** before the core can save.

Changing the selected input, category, chosen folder, filename, or vault discards
the plan and confirmation. External source changes are detected during
preparation and again by the core at commit; files are not continuously watched.
A late destination collision blocks saving and requires a new prepared plan.

Read-only validation, folder listing, and preparation can be cancelled: their
background work finishes, but its result is discarded. A confirmed save cannot
be cancelled halfway through. Closing the window waits for that operation and
its result. Incomplete history or an uncertain save disables further imports
until pending operations have been checked. Recovery never replays a vault write.
If uncertainty remains with no journal entry, manual inspection is required;
the desktop does not offer a blind retry button.

The history retains only an operation ID, hash, category, relative destination,
state, fixed error code, and UTC timestamps. Its event table contains fixed codes
and IDs. It stores no input path, note body, metadata dump, or raw exception.
Relative destinations can themselves contain private filenames, so the database
stays local and must not be shared as public project data.

## Boundaries

Read [the validation contract](docs/lumen-v1-validation.md) for exact rules.
The safe importer initially supports Windows only and fails closed elsewhere.
The runtime protects against untrusted notes and tested path/collision races;
it does not provide a sandbox against a malicious process with the same user's
access, filesystem corruption, or a compromised operating system.

The GUI has automated widget tests, including full fictional-vault imports.
Captured app windows were inspected at native ~100% and simulated 200% Tk
scaling. The user approved the manual fictional flow and confirmed opening the
single Stage 7 test in real Obsidian; broader accessibility, native picker, and
Windows scaling review remain separate. Rounded web controls are approximated with standard ttk
borders; native Windows title bars and file pickers follow the operating system.
No executable packaging, import-history migration, history-clear interface, Atlas
importer or export interface is included. The real-vault check was limited to the one authorized
technical note and its matching history record.

## Project layout

```text
src/lumen_organizer/   core, local settings, controller, worker, desktop
tests/fixtures/       fictitious Markdown inputs (included in Git)
tests/                core, controller, worker, demo, Tk widget tests
tools/                launch, tests, dependency bootstrap, fictional demo
docs/                 validation contract, workflow, test evidence
.local/               private settings/history and temporary test/demo data
.venv/                project-only dependency environment
```

The last two directories are ignored. Configuration examples and fixtures use
fictitious data; real configurations and history are never repository artifacts.

## Stage 9D: manual Lumen → Atlas interfaces

The desktop now has a separate **Exportar para Atlas** window. It prepares one
authorized package with explicit review and confirmation; saving does not
confirm delivery. Use `python -B tools/stage9d_demo.py` through the local venv
for a new fictional workspace without loading personal settings.
See [the interface guide and verification](docs/stage9d-interfaces.md).
Stage 9E manual acceptance and real-note transfer remain separately authorized.

## Repository contents

The repository contains application source, tools, tests, fictional fixtures and
technical documentation. Personal settings/history in `.local/`, virtual
environments, generated notes and unrelated files in `outputs/`, and the local
vault link catalog are excluded. These exclusions do not delete local files.
