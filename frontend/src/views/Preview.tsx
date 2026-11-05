import { useEffect, useState } from "react";
import { ArrowRight, ArrowUpRight, FileText, ShieldCheck } from "lucide-react";
import {
  Button,
  DestinationChips,
  Modal,
  Skeletons,
  SourceIcon,
  StatusPill,
  Surface,
  TagInput,
} from "../components";
import {
  processing,
  types,
  type Destination,
  type Note,
  type Transfer,
} from "../model";
import { transferService } from "../service";

export function Preview({
  transfer: t,
  onSave,
  onDestination,
  onPublish,
  onPersist,
  onDetails,
}: {
  transfer: Transfer;
  onSave: (n: Note) => void;
  onDestination: (d: Destination) => void;
  onPublish: (t: Transfer) => Promise<void>;
  onPersist: (t: Transfer) => Promise<void>;
  onDetails: (t: Transfer) => void;
}) {
  const [note, setNote] = useState(t.note);
  const [tab, setTab] = useState<"note" | "markdown">("note");
  const [error, setError] = useState("");
  const [destinationOpen, setDestinationOpen] = useState(false);
  const [sending, setSending] = useState(false);
  useEffect(() => setNote(t.note), [t.note]);
  function edit(patch: Partial<Note>) {
    const next = { ...note, ...patch };
    setNote(next);
    onSave(next);
  }
  async function send() {
    if (!note.title.trim() || !note.summary.trim() || !note.folder.trim()) {
      setError("Preencha título, resumo e destino da nota antes de continuar.");
      return;
    }
    setError("");
    setSending(true);
    try {
      await onPublish({ ...t, note });
    } finally {
      setSending(false);
    }
  }
  const markdown = t.markdown ?? `# ${note.title}\n\n${note.summary}`;
  const ready = t.status === "review";
  return (
    <>
      <div className="preview-toolbar">
        <DestinationChips value={t.destination} onChange={onDestination} />
        <StatusPill status={t.status} />
      </div>
      <div className="preview-grid">
        <Surface className="source-panel">
          <div className="panel-heading">
            <span>01 / Fonte original</span>
            <Button variant="ghost" onClick={() => onDetails(t)}>
              Detalhes
              <ArrowUpRight size={14} />
            </Button>
          </div>
          <div className="source-preview">
            <SourceIcon type={t.type} />
            <span className="eyebrow">{types[t.type]}</span>
            <h2>{t.type === "idea" ? t.source : t.note.title}</h2>
            <p>{t.source}</p>
            <div className="source-placeholder">
              <FileText size={32} />
              <p>Prévia da fonte</p>
              <span>
                {t.sourceText
                  ? t.sourceText.slice(0, 12000)
                  : "A fonte será exibida após a extração."}
              </span>
            </div>
            {t.sourceTruncated && (
              <p className="settings-hint">
                Exibindo os primeiros 12 mil caracteres. O texto completo foi
                preservado localmente e processado sem truncamento.
              </p>
            )}
          </div>
          <div className="panel-note">
            <ShieldCheck size={15} />A fonte original permanece intacta.
          </div>
        </Surface>
        <Surface className="note-panel">
          <div className="panel-heading">
            <span>02 / Sua nota</span>
            <div className="mini-tabs">
              <button
                aria-pressed={tab === "note"}
                onClick={() => setTab("note")}
              >
                Nota
              </button>
              <button
                aria-pressed={tab === "markdown"}
                onClick={() => setTab("markdown")}
              >
                Markdown
              </button>
            </div>
          </div>
          <div className="note-editor">
            {processing(t.status) && t.status !== "publishing" ? (
              <>
                <p className="muted">
                  {t.message ?? "O Lumen está preparando sua nota…"}
                </p>
                <Skeletons />
              </>
            ) : tab === "markdown" ? (
              <pre className="markdown-preview">{markdown}</pre>
            ) : (
              <>
                <label className="field">
                  Título
                  <input
                    value={note.title}
                    onChange={(e) => edit({ title: e.target.value })}
                  />
                </label>
                <label className="field">
                  Resumo
                  <textarea
                    rows={7}
                    value={note.summary}
                    onChange={(e) => edit({ summary: e.target.value })}
                    placeholder="O resumo aparecerá aqui para revisão."
                  />
                </label>
                <div className="field">
                  <span>Tags</span>
                  <TagInput
                    value={note.tags}
                    onChange={(tags) => edit({ tags })}
                  />
                </div>
                <label className="field">
                  Pasta ou banco de dados
                  <input
                    value={note.folder}
                    onChange={(e) => edit({ folder: e.target.value })}
                  />
                </label>
                <label className="field">
                  Formato da nota
                  <select
                    value={note.format}
                    onChange={(e) =>
                      edit({ format: e.target.value as Note["format"] })
                    }
                  >
                    <option value="study">Nota de estudo</option>
                  </select>
                </label>
              </>
            )}
          </div>
        </Surface>
      </div>
      <div className="confirm-bar">
        <p>
          <ShieldCheck size={16} />
          {t.status === "completed"
            ? "Entrega confirmada. Abra o destino para revisar a nota."
            : "Revise o conteúdo. Ao confirmar, a nota será enviada aos destinos selecionados."}
        </p>
        <div>
          {t.status === "completed" && (
            <Button onClick={() => setDestinationOpen(true)}>
              Abrir destino
              <ArrowUpRight size={14} />
            </Button>
          )}
          <Button onClick={() => onDetails(t)}>Ver detalhes</Button>
          {ready && (
            <Button onClick={() => void onPersist({ ...t, note })}>
              Salvar rascunho
            </Button>
          )}
          <Button
            variant="primary"
            disabled={!ready || sending}
            onClick={() => void send()}
          >
            {t.status === "publishing"
              ? "Enviando…"
              : t.destination === "both"
                ? "Enviar para ambos"
                : t.destination === "notion"
                  ? "Criar página no Notion"
                  : "Enviar ao Obsidian"}
            <ArrowRight size={16} />
          </Button>
        </div>
      </div>
      {error && (
        <p role="alert" className="error-text">
          {error}
        </p>
      )}
      {destinationOpen && (
        <Modal
          title="Destinos da nota"
          onClose={() => setDestinationOpen(false)}
        >
          <div className="detail-content">
            <p>Abra a nota salva e conferida no destino escolhido.</p>
            <h3>{note.title}</h3>
            <p>{note.summary}</p>
            <div>
              {note.tags.map((tag) => (
                <span className="tag" key={tag}>
                  #{tag}
                </span>
              ))}
            </div>
            <p>{note.folder}</p>
            {(["obsidian", "notion"] as const).map(
              (destination) =>
                t.receipts?.[destination] && (
                  <Button
                    key={destination}
                    onClick={() => {
                      void transferService
                        .open(t.id, destination)
                        .catch((e) => setError(String(e.message)));
                    }}
                  >
                    Abrir {destination === "notion" ? "Notion" : "Obsidian"}
                  </Button>
                ),
            )}
          </div>
        </Modal>
      )}
    </>
  );
}
