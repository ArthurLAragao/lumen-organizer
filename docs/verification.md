# Verification evidence

Only fictional notes and temporary mock vaults are used by the suite. The real
vault is neither configured nor read by tests. Core import tests enable a Python
audit boundary that rejects filesystem writes and SQLite connections outside
their individual fictional workspace. Native directory handles request read
access only; publication uses Python's audited rename operation.

## Environment observed

- Windows, Python 3.13.6.
- PyYAML 6.0.3, installed only in the project virtual environment.
- Tcl/Tk 8.6.15. Tk windows/widgets can be created in this environment. The
  original desktop checks use withdrawn windows. Phase 6C also exercises visible
  windows and inspects app captures; human/manual review remains pending.
- Git initially clean on unborn `master`, without tracked project files.

Pip was bootstrapped from Python's bundled local wheel. PyYAML download was
explicitly authorized. No other remote service or model was contacted.

## Covered behavior

- `atlas_action` values, lifecycle/type errors, bounds, malformed YAML, duplicate
  keys, restricted YAML features, depth, invalid dates and oversized scalars.
- Inert command/HTML/link/image content and original byte preservation, including
  BOM, comments, and CRLF.
- All categories, explicit folder selection, traversal/UNC/alternate streams,
  Windows device names, existing-folder restrictions, configurable vault roots.
- Native Windows junction rejection and actual ancestor-rename blocking.
- Cancellation, same-byte renamed duplicates, untracked-note collisions,
  concurrent final-name collisions, altered/deleted sources, and tampered plans.
- Pending history before saving, failure after saving, recovery without replay,
  recovery conflict preservation, and unmanaged staging preservation.
- Abrupt child-process exits before and after publication, followed by reopening
  history and recovery. These test actual OS lock release without Python cleanup.
- Note markers and parser exception excerpts absent from persistent history.
- Unexpected database preservation, state outside the vault, and same-volume
  enforcement.

Run the suite with:

```powershell
.\.venv\Scripts\python.exe tools\run_tests.py
```

Stage 4 execution on 2026-10-09:

```text
Ran 56 tests in 3.320s
OK
RESULT: 56 run; 0 failures; 0 errors; 0 skipped
```

Both read-only developer commands also passed: the environment report returned
the versions above, and validation of `research-none.md` returned `valid: true`
with no issues. The native junction/rename tests and actual child-process exit
tests executed successfully; they were not skipped.

Git's final inspection showed 25 untracked new project files on unborn `master`.
There were no preexisting tracked changes. Ignore checks confirmed `.venv` and
`.local` were excluded and both fictional Markdown fixtures were visible to Git.
Public source/documentation checks found no personal vault path. There is no
real `.local/settings.json` or `.local/history.sqlite3`; SQLite files created by
tests belonged only to temporary fictional workspaces.

## Stages 5-6 verification on 2026-10-10

Before implementation, README, the validation contract, this earlier evidence,
the core modules, and Git state were inspected. The repository still had 25
untracked public files on unborn `master`; no tracked changes existed. All
56 original tests were rerun to establish the baseline:

```text
Ran 56 tests in 2.672s
OK
RESULT: 56 run; 0 failures; 0 errors; 0 skipped
```

The core's validator, destinations, filesystem guards, history, and importer
needed no changes. A local settings store, a Tk-independent controller, a worker
queue, Portuguese presentation, and a Tkinter/ttk desktop were added. The launch
entry point and documentation were updated. No dependency was installed in this
stage. The validation contract and fictional fixtures remain unchanged.

Final full-suite execution:

```text
Ran 94 tests in 8.878s
OK
RESULT: 94 run; 0 failures; 0 errors; 0 skipped
```

This comprises the original 56 tests plus 20 controller tests, three worker
tests, one fictional-demo test, and 14 automated Tk widget tests. None of the
Tk, native junction/locking, or child-process recovery tests were skipped.

Automated controller/widget coverage includes:

- Local configuration persistence/reload, preservation of unexpected settings,
  initially empty category, selection without automatic import, and cancellation
  of configuration/file pickers. Native pickers are mocked to return only
  fictional paths or a cancellation.
- Blocking errors versus editorial warnings, metadata summary, disabled import
  states, inert HTML/code/link/embed text, and a read-only scrolling preview.
  A large fictional note is inserted in chunks. Resize capability and keyboard
  binding presence are checked; visual layout/accessibility are not established.
- Existing-child folder navigation/back/explicit selection and cancellation,
  without reading notes from those directories.
- Cancellation during validation, folder listing, destination preparation, and
  confirmation. Late results from cancelled reads are ignored.
- Full confirmation-driven desktop imports into temporary fictional vaults,
  exact byte equality, source preservation, unchanged lifecycle, and subsequent
  duplicate detection with no second file.
- Filename suffix presentation, preservation of old/competing files, rejection
  of a collision appearing after preparation, and preparation of a new name.
- Expired plans after filename/category/source selection changes; source edits
  before preparation and after confirmation rejected by fresh core checks.
- Fault-injected history failure after a successful save: the desktop displays
  that the file was saved, disables retries, and reconciles without writing the
  note again. Loading settings exposes pending history instead of replaying it.
- Unknown worker exceptions use fixed diagnostic codes, expose no fictional
  private marker, and halt retries when the outcome of saving is uncertain.
- Work executes in a background thread; owner-thread acceptance and rendering
  are checked. A Tk timer still executes while validation waits in the worker.
  Closing during a confirmed save waits for its successful completion.

The Python audit write boundary is enabled for controller, demo, and Tk tests,
and propagated into worker threads. It rejects writes and SQLite connections
outside each test's temporary fictional workspace. A negative worker test proves
that the propagated boundary rejects an attempted outside write. The runtime
does not have an additional generic filesystem sandbox; its core path guards
remain the actual import policy.

The environment command, fictional fixture validation, GUI command parsing, and
fictional-demo helper also ran successfully. The demo helper created only unique
fake inputs/folders under `.local/demos/` and did not configure the application.
No project-root `.local/settings.json` or `.local/history.sqlite3` exists after
verification. Preexisting local test/setup artifacts were preserved.

Final Git inspection: unborn `master`, 36 untracked public files, no staged or
tracked changes. `.local/` and `.venv/` are ignored; the two fictional fixtures
are not ignored. Public source/documentation checks found no personal vault path.
No commit, push, publication, packaging, model/API call, or skill modification
was performed.

The real vault was not selected, configured, read for tests, or written by this
session. The evidence is the fictional test write boundary and the project-only
scope of all implementation/setup commands. No content scan or before/after
hash comparison of personal notes was performed; this does not claim that other
programs could not have changed the vault independently.

## Limits of the evidence

- Disk-full, permission-denial, history-write failures, and different-volume
  conditions are fault-injected. No disk was filled, real ACLs were modified,
  or second volume used to test those conditions.
- Abrupt process exits are tested; power loss and physical disk failure are not.
  `fsync` and SQLite commits do not establish hardware-level crash guarantees.
- Windows filesystem behavior is tested on this machine only, not every Windows
  version, network filesystem, or cloud-sync provider. UNC vaults are rejected.
- GUI widgets and fictional imports were tested automatically. No visual/manual
  GUI acceptance, native picker interaction, screen-reader testing, real-vault
  import, or Atlas behavior was tested. Markdown is plain text, never rendered.
- No packaging/build test has been run. Source commands work without installing
  build dependencies or the project package.
- SQLite history is private local state, not encrypted storage. Someone with
  access to it can see recorded relative destinations.
- External source changes are detected at preparation and commit, not through a
  continuous watcher. Cancellation of reads discards results; it cannot forcibly
  interrupt an OS read. A confirmed save/recovery/configuration is allowed to
  finish. A hung OS call could therefore delay closing the window.
- The desktop blocks a repeat when a recorded note is missing/changed; it offers
  no override or history-clearing feature. An uncertain save with no recoverable
  journal entry requires manual investigation and remains blocked in-session.
- Stage 7 (real-vault import) has not been authorized. Stages 5-6 stop here.

The implementation session does not modify the real vault, the research skill,
or old notes. No commit, push, or publication is performed.

## Approved visual refinement, stages 6B-6C, 2026-10-10

Before edits, README, the validation contract, and existing test evidence were
read, Git was inspected, and the original suite was rerun:

```text
Ran 94 tests in 8.693s
OK
RESULT: 94 run; 0 failures; 0 errors; 0 skipped
```

Only the approved interface/presentation/test/documentation files changed:
`src/lumen_organizer/styles.py` (new), `ui.py`, `presentation.py`,
`tests/test_ui.py`, `README.md`, `docs/gui-workflow.md`, and this evidence file.
The before/after SHA-256 comparison matched all 22 protected source, behavioral
test, contract, and dependency files. This includes the controller, worker,
validator, destinations, filesystem guards, history, importer, and settings.
No core change was needed; existing behavioral tests were retained.

The approved references were the supplied current Atlas and portfolio images.
Atlas leads surfaces, controls, spacing, and the restrained blue primary action;
the portfolio contributes quiet typography and muted neutral text. Approximate
visual tokens (not asserted to be the projects' original CSS values):

| Role | Token |
|---|---|
| Background / surface / selected | `#101010` / `#191919` / `#242424` |
| Text / secondary text | `#F5F5F2` / `#A6A6A0` |
| Dividers / control borders | `#3B3B3B` / `#707070` |
| Primary action and focus / hover | `#A3C4FF` / `#B6D0FF` |
| Warning / error / success | `#E6BC73` / `#FF9A8E` / `#9BD1AD` |
| Spacing | 4, 8, 12, 16, 24, 32 logical pixels, scaled through Tk |
| Typography | Segoe UI 11 pt controls, 18 pt bold title, 11 pt bold sections, 10 pt supporting text; Consolas 12 pt complete raw preview |

Arial/TkDefaultFont and Cascadia Mono/TkFixedFont are available fallback paths.
Segoe UI, Arial, Consolas, and Cascadia Mono were found locally; Inter/Geist were
not assumed or downloaded. `clam` provides standard square ttk controls and
focus indicators. Native title bars/file pickers remain controlled by Windows.
No dependencies, fonts, icons, images, or other assets were installed/downloaded.

The final full suite, after the interface changes:

```text
Ran 99 tests in 14.380s
OK
RESULT: 99 run; 0 failures; 0 errors; 0 skipped
```

This is the original 94 plus five new UI/presentation tests (19 Tk tests total).
The added checks cover:

- A primary action per stage, explicit no-vault/no-note/valid/invalid/warning
  text, confirmation cancellation, and distinct success/duplicate/cancel/failure
  and incomplete-history messages. Color supplements the text.
- A complete confirmed fictional import with a destination longer than 260
  characters, unchanged source and destination bytes including BOM and CRLF,
  complete scrolling paths, visible actions, and stable action/window geometry.
- Real Tk focus events and Tab/Shift+Tab movement, Ctrl+A selection of the full
  YAML/Markdown, intercepted Ctrl+C calls for full preview/destination text,
  blocked keyboard edits, and focus styling. The test does not read or replace
  the user's clipboard. Native OS clipboard integration remains a manual check.
- Visible resized windows at minimum/larger sizes, focus-driven destination
  field scrolling, and folder/confirmation actions inside their windows at
  100%, 125%, 150%, and 200% simulated Tk scaling. Folder and preparation actions
  stay outside the scrolling form. This does not emulate Windows monitor DPI.
- Saved-with-incomplete-history displays a warning and the operation destination,
  highlights history checking, and retains disabled repeat/preparation controls.
  Existing recovery, cancellation, collision, changed-source/destination, worker
  responsiveness, and log-content tests continue to pass.

One intermediate direct `python -m unittest tests.test_ui` invocation failed to
locate the source package, because this source checkout is not installed. It
was corrected by adding `src` to that targeted run. The documented
`tools/run_tests.py` command sets the source path and passed as reported above.

### Visual evidence versus manual acceptance

The actual display observed was 2560×1440 with approximately 96.05 DPI
(native ~100% Tk scaling). The main window minimum there is 900×620; the initial
preferred window observed was 1121×776. Dimensions can vary with font metrics.
Automated layout checks additionally set Tk scaling to 125%, 150%, and 200%.
At simulated 200%, the observed minimum was 1798×1239, with the action controls
visible and destination fields scrollable. Scale tests resize the windows and
exercise focus; they do not merely instantiate widgets or calculate contrast.

The app's own Windows window handles were captured with standard-library/GDI
calls; no other app or desktop content was captured. Captures were visually
inspected at native ~100% and simulated 200% Tk scaling. The local PNGs are:

- `.local/visual-review/prepared-100.png`
- `.local/visual-review/confirmation-100.png`
- `.local/visual-review/history-incomplete-100.png`
- `.local/visual-review/minimum-200-tk.png`
- `.local/visual-review/folders-200-tk.png`

They show only fictional inputs/vaults and stay ignored/local. During this
assisted visual check, a fault-injected fictional save with incomplete history
was followed by successful reconciliation, without replaying the note write.
The earlier sizing/scrollbar findings were corrected within UI styling only.
No human/manual acceptance, native file-picker interaction, screen-reader use,
actual Windows 125/150/200% setting changes, mixed-DPI monitors, other display
resolutions, or hardware accessibility testing was performed. These remain
pending; passing layout/focus checks does not establish complete accessibility.

### Scope and Git verification

All test/import/capture state was in unique temporary fictional workspaces, with
the existing audit boundary rejecting writes outside them (also in the worker).
Only generated PNGs were subsequently saved in the ignored visual-review folder.
Existing project-root `.local/settings.json` and `.local/history.sqlite3` were
present with modification times from before this visual-refinement work; their
contents were not read or changed. They remain ignored and are not public
repository artifacts. Historical absence statements above describe the earlier
stage executions, not the current local state.

Final Git inspection: unborn `master`, 37 untracked public files, no tracked or
staged changes. The new public file is `styles.py`; the existing untracked work
was preserved. `.local/` and `.venv/` remain ignored, while fictional fixtures
remain visible to Git. Public source/documentation checks found no personal
vault path. No commit, push, publication, packaging, network/model call, or
change to Atlas, portfolio, research skill, or old notes was performed.

The real vault was not selected, read for testing, or written by this work.
The evidence is the isolated fictional roots, audit boundary, protected-file
comparison, and project-only scope of implementation/capture commands; no scan
or before/after content hash of personal notes was performed. Changes by other
programs are not assessed. Stage 7 remains unauthorized. This implementation
stops for the user's visual/manual review.

## Stage 7A controlled real-vault preparation, 2026-10-10

The user approved the manual fictional-vault flow and authorized preparation
for one technical test note. The only permitted real-vault write is the note
the user explicitly confirms in Lumen's final dialog, in `00 - Inbox/Pesquisas`.
No real-vault import was performed during this preparation.

Current project/Git state, the validation contract, and the GUI workflow were
inspected. The current suite was executed without assuming its test count:

```text
Ran 99 tests in 15.989s
OK
RESULT: 99 run; 0 failures; 0 errors; 0 skipped
```

Filesystem metadata confirmed that the user-specified real vault, root
`.obsidian` directory, and existing `00 - Inbox/Pesquisas` destination exist.
`LUMEN - Teste de importação real.md` was unoccupied at preparation time.
No personal note or `.obsidian` content was opened; no vault file was written.

The outside-vault input is the ignored local artifact
`.local/stage7/2026-10-10-119281d5/LUMEN - Teste de importação real.md`.
It contains only a technical test description, truthful `source: lumen-test`,
and `created: "2026-10-10"`, using the actual local date. Its lifecycle is
`status: inbox`, `lumen_export: false`, `atlas_action: none`, with empty Atlas IDs.

- Size: 694 bytes.
- SHA-256: `da229332fc1950fb06bd844fd10b2f7ea3eec0985475618cb181351da1492e9a`.
- Validation: valid, zero blocking errors.
- Six visible editorial warnings: missing recommended `Resumo`, `Explicação`,
  `Exemplos e aplicação`, `Revisão`, `Fontes`, and `Registro pessoal` sections.
  This short technical test intentionally includes no research or fabricated
  sources; warnings are retained and must be reviewed in the interface.

The adjacent ignored `preparation.json` records the input hash, size, validation
warnings, intended relative destination, tests, and local-state metadata.
Application configuration/history were not changed by this preparation. No
runtime source, tests, dependency, skill, existing note, or vault setting changed.
Public Git state remains unborn `master`, with 37 untracked files and no staged
or tracked changes; the preexisting work is preserved. The test input and local
record are ignored. This evidence document is the only public project file
edited for Stage 7A.

Next: the user selects the real vault and this input in the current GUI, chooses
`indefinido`, prepares the destination, reviews the complete path and six warnings,
and explicitly confirms the final dialog. Any newly occurring collision must
show a reviewed alternative filename; no manual copy or confirmation automation
is permitted. Verification of the real file and matching history waits until
the user reports that confirmation. Obsidian opening/content/property verification
also awaits the user's report. Stage 7 is not complete.

## Stage 7B-7C controlled real-vault result, 2026-10-10

The user reported completing the import through the current Lumen interface,
explicitly confirming the final dialog, and receiving the completed-import
result. The effective filename remained `LUMEN - Teste de importação real.md`.
No confirmation click was automated, and no script or terminal copied the
note into the vault. The user also reported opening this note in real Obsidian
and confirmed that its content and properties were correct and well organized.
This is user-confirmed visual/manual evidence; the agent did not perform an
independent visual inspection or automate Obsidian.

After that confirmation, read-only verification at
`2026-10-10T21:52:17.809084+00:00` inspected only the authorized technical test
destination, its prepared input, and matching local-history records. The
effective destination relative to the user-specified real vault was:

```text
00 - Inbox/Pesquisas/LUMEN - Teste de importação real.md
```

### Byte and YAML result

- The input and destination both exist as regular files and are 694 bytes.
- Direct binary comparison: identical.
- Both SHA-256 values match the Stage 7A preparation:
  `da229332fc1950fb06bd844fd10b2f7ea3eec0985475618cb181351da1492e9a`.
- The input still matches its original approved size/hash; it was preserved.
- Frontmatter bytes and parsed YAML metadata are identical. Both notes remain
  structurally valid. The six expected missing-section warnings remain present.
- Lifecycle values are unchanged: `created: "2026-10-10"`, `source: lumen-test`,
  `status: inbox`, `lumen_export: false`, `atlas_action: none`, and empty
  `atlas_task_id`/`atlas_goal_id`.

### History result

The existing project-local SQLite history was queried using URI `mode=ro` and
`query_only=ON`; the application's mutable History/Organizer constructors,
commit, and reconciliation methods were not called. Queries were limited to
the configured real-vault identity and the test fingerprint/relative destination,
then the events for that matching operation. Unrelated imports were not dumped.

- Exactly one matching operation was found.
- Category: `indefinido`; relative destination matches the authorized test path.
- State: `succeeded`; error code: null.
- Started: `2026-10-10T21:48:23.738970+00:00`.
- Finished: `2026-10-10T21:48:23.747243+00:00`.
- Its events were `import_pending` followed by `import_succeeded`.
- There are zero matching pending or failed test operations.

The outcome is **file saved and success recorded**, rather than saved with
incomplete history or an uncompleted import. Source, destination, and history
size/modification-time metadata stayed unchanged during verification. A
verification-time Python audit hook rejected filesystem writes/mutations and
non-read-only SQLite connections; no vault write, repeat import, recovery,
cleanup, or deletion was performed. This does not claim a global filesystem
sandbox or assess concurrent changes by other applications.

### Completion and boundaries

Stage 7's criteria are satisfied: a user-confirmed GUI import, physical file
existence, exact approved bytes, clearly successful history, and the user's
confirmation of opening/content/properties in Obsidian.

The Stage 7A suite result remains 99 tests passed in 15.989 seconds, with zero
failures, errors, or skips. The suite was not rerun in 7C: application code and
tests were not changed; this phase performed the actual file/history checks
described above. It verifies this one technical import on this Windows setup,
not arbitrary notes, batch import, other platforms, or independent Obsidian
visual automation. Atlas, AI/APIs, task/goal changes, packaging, and publication
remain outside this stage.

Only `README.md`, `docs/gui-workflow.md`, and `docs/verification.md` were edited
for the final technical documentation. No personal vault path or unrelated
history/content was copied into public documentation. The original input,
preparation record, local application state, and real test note were retained.
The agent did not change existing notes, `.obsidian`, plugins, the research skill,
or application code, and did not create a commit, push, or publication.

Final Git state: unborn `master`, 37 untracked public files, no staged or tracked
changes. Existing work was preserved; `.local/` remains ignored. Stage 7 stops
here. This single test grants no authorization for another import or deletion.
