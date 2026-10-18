# Fictional desktop review

This walkthrough includes the approved stage 6B visual refinement and 6C
regression review. Do not select a real vault or personal
notes for this review. The separately authorized single Stage 7 technical import
was verified; it does not authorize other real-note imports. See
[the controlled result](verification.md#stage-7b-7c-controlled-real-vault-result-2026-10-10).

From the project directory in PowerShell:

```powershell
.\.venv\Scripts\python.exe tools\create_demo.py
.\.venv\Scripts\python.exe tools\lumen.py gui
```

The first command creates a unique fictional vault and three notes under
`.local/demos/<id>/`. Repeating it creates a different directory; it does not
overwrite a prior demo. It prints the exact paths to select. The second command
opens the Portuguese desktop. It does not import anything on startup.

1. Click **Selecionar vault** and choose the generated `Vault-Ficticio` root.
   Its required destination folders already exist. The choice is saved only in
   `.local/settings.json`; the SQLite history remains in `.local/` outside the
   vault. Selecting or cancelling a folder never imports a note.
2. Click **Selecionar nota** and choose the printed `nota-ficticia.md` input.
   The selected path appears; long paths initially show their filename end.
   Use Home/End or selection/copy to consult the full read-only path.
   Click **Validar nota** to see the preview,
   **Erros e avisos**, and **Metadados** tabs. The preview is read-only text.
3. Choose **AWS e Cloud (aws-cloud)** manually. No category is preselected.
   Keep the requested filename, or enter another Windows-compatible `.md` name.
   Click **Preparar destino**. Check the complete path and final filename.
4. Click **Revisar importação**. The dialog displays the source, destination, final name,
   warnings, and any collision adjustment. First test **Cancelar**: the result
   must say the operation was cancelled and no note must be created. Prepare
   again, open the dialog, and click **Confirmar importação** explicitly.
5. The result must say **Importação concluída**. Inspect the new file only in
   the fictional vault. Its bytes should match the input, which remains intact.
   `status: inbox`, `lumen_export: false`, creation/source metadata, and empty
   Atlas IDs are preserved. Import is separate from review and export approval.
6. Prepare the same note again. **Duplicata identificada** should appear and
   no second file should be created. Detection uses only Lumen's local history.

Additional fictional checks:

- Select `nota-invalida.md`: its incompatible status produces a blocking error.
- Select `nota-com-avisos.md`: its mismatched title produces an editorial warning,
  which is also shown in the confirmation dialog without blocking import.
- Choose **Faculdade** or **Projetos**: click **Escolher pasta**, navigate into
  the generated folders, and explicitly select a child. The category root alone
  cannot be selected. Cancelling leaves the selection incomplete.
- To see a collision suffix, copy a fictional note to the proposed destination
  before preparation. Prepare again and check the new final name; the existing
  file must be preserved. A file that appears after preparation blocks the old
  plan and requires preparation/confirmation again.
- Change the filename/category or clear the selection after preparation: the
  import button becomes unavailable until a fresh destination is prepared.
- Edit only the fictional input after validation: preparation or commit must
  report that the source changed and require validation again.
- Cancel validation or preparation: the in-flight read may finish, but its
  result is discarded. A confirmed write runs to completion; closing waits for it.

**Arquivo salvo; histórico incompleto** means the save happened but history needs
checking. Do not try the import again. Use **Conferir histórico**. If recovery is
blocked or the result stays uncertain, inspect only the fictional destination
and local state before proceeding. Automated fault-injection tests cover this
case; this walkthrough does not ask you to damage a database or filesystem.

Keyboard support includes Tab/Shift+Tab focus navigation, Ctrl+O for selection,
Escape for cancelling a cancellable step/dialog, and Ctrl+A to select preview
text and Ctrl+C for copying. The full YAML is always retained in the preview.
The window and dialogs can be resized. At limited heights, destination fields
scroll and keyboard focus brings each field into view; folder/preparation and
footer actions remain outside that scrolling area. No HTML, code, link, or
embed is executed or loaded. Import does not mark content reviewed or authorize
export; the fixed footer states the unchanged lifecycle values.

For a short manual review, using only the generated fictional data:

- Resize to the minimum and then maximize. Check that selection, validation,
  folder selection, preparation, cancellation, and review actions remain visible.
- Use Tab/Shift+Tab, Ctrl+A/Ctrl+C, and scrolling in the preview, complete
  destination, and confirmation. Check the visible focus indicator and full YAML.
- Review errors and warnings, cancel final confirmation, and then explicitly
  confirm one fictional import. Check byte equality and the subsequent duplicate.
- Change the filename/category or edit the fictional input after preparation;
  check that the old confirmation cannot save.
- Check your actual Windows display scales/monitor setup and native file pickers.
  Report any clipped controls or unreadable text. Assistive-technology use needs
  a separate review; automated checks are not proof of complete accessibility.

Native ~100% and simulated 200% Tk app captures were visually inspected.
Automated layout/focus checks also ran at 125% and 150% Tk scaling. The user has
approved the manual fictional flow and confirmed the Stage 7 test's content and
properties in Obsidian. Actual Windows scale changes, broader accessibility,
native-picker interaction, and screen-reader checks remain separate verification
limits; no automated Obsidian visual test was performed.

Demo files and configuration stay local and ignored by Git. Tests create their
own temporary fictional workspaces and remove them afterwards. No demo helper
automatically configures a personal vault or publishes anything.

## Stage 9D: exportação separada

O cabeçalho oferece **Exportar para Atlas**, em uma janela independente do
importador do Obsidian. A seleção do vault dessa janela não muda a configuração
do importador. Validação, identidade, preparação e confirmação precedem a cópia
do pacote retido, sem sobrescrita nem mudança de propriedades da nota.
Consulte [o guia Stage 9D](stage9d-interfaces.md) para abrir uma demonstração
fictícia, selecionar explicitamente o ambiente do Atlas e revisar os limites.
