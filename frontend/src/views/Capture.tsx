import { useRef, useState, type FormEvent } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  FileText,
  Link2,
  ShieldCheck,
  Upload,
} from "lucide-react";
import {
  Button,
  DestinationChips,
  EmptyState,
  Skeletons,
  Surface,
  TransferCard,
} from "../components";
import type { ContentType, Destination, Preferences, Transfer } from "../model";

export function Capture({
  preferences,
  recent,
  loading,
  onCapture,
  onOpen,
  onHistory,
}: {
  preferences: Preferences;
  recent: Transfer[];
  loading: boolean;
  onCapture: (
    s: string,
    t: ContentType,
    d: Destination,
    file?: File,
  ) => Promise<void>;
  onOpen: (t: Transfer) => void;
  onHistory: () => void;
}) {
  const [submitting, setSubmitting] = useState(false);
  const [mode, setMode] = useState<"link" | "file" | "idea">("link");
  const [source, setSource] = useState("");
  const [idea, setIdea] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [destination, setDestination] = useState(preferences.destination);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const picker = useRef<HTMLInputElement>(null);
  function choose(f?: File) {
    if (!f) return;
    if (!/\.(pdf|md|txt)$/i.test(f.name)) {
      setError("Escolha um PDF, Markdown ou arquivo de texto.");
      return;
    }
    setFile(f);
    setMode("file");
    setError("");
  }
  async function submit(e: FormEvent) {
    e.preventDefault();
    const content =
      mode === "idea"
        ? idea.trim()
        : mode === "file"
          ? (file?.name ?? "")
          : source.trim();
    if (!content) {
      setError("Adicione uma URL, um arquivo ou uma ideia para continuar.");
      return;
    }
    let type: ContentType =
      mode === "file"
        ? file?.name.toLowerCase().endsWith(".pdf")
          ? "pdf"
          : "document"
        : mode === "idea"
          ? "idea"
          : "link";
    if (mode === "link") {
      try {
        const url = new URL(content);
        if (!["https:", "http:"].includes(url.protocol)) throw new Error();
        if (
          ["youtube.com", "www.youtube.com", "youtu.be"].includes(url.hostname)
        )
          type = "video";
      } catch {
        setError("Use uma URL completa, começando com https://.");
        return;
      }
    }
    setSubmitting(true);
    try {
      await onCapture(
        content,
        type,
        destination,
        mode === "file" ? (file ?? undefined) : undefined,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível capturar.");
    } finally {
      setSubmitting(false);
    }
  }
  return (
    <>
      <div className="capture-layout">
        <Surface className="capture-surface">
          <div className="capture-label">
            <span>
              <ArrowDownToLine size={17} />
              NOVA CAPTURA
            </span>
            <span>01 / Entrada</span>
          </div>
          <form onSubmit={submit}>
            <div
              className={`drop-zone ${dragging ? "dragging" : ""}`}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                const f = e.dataTransfer.files[0];
                if (f) choose(f);
                else {
                  setSource(e.dataTransfer.getData("text/plain"));
                  setMode("link");
                }
              }}
            >
              <span className="capture-orbit">
                <ArrowDownToLine size={28} />
              </span>
              <h2>
                Um vídeo, um link, um PDF.
                <br />
                <span>Ou aquela ideia que não pode escapar.</span>
              </h2>
              <p>Arraste um arquivo até aqui ou escolha como começar.</p>
              <div
                className="capture-tabs"
                role="group"
                aria-label="Tipo de captura"
              >
                {[
                  { id: "link", text: "Colar link", icon: Link2 },
                  { id: "file", text: "Adicionar arquivo", icon: Upload },
                  { id: "idea", text: "Escrever ideia", icon: FileText },
                ].map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    aria-pressed={mode === item.id}
                    onClick={() => {
                      setMode(item.id as typeof mode);
                      setError("");
                    }}
                  >
                    <item.icon size={15} />
                    {item.text}
                  </button>
                ))}
              </div>
            </div>
            <div className="capture-entry">
              {mode === "link" ? (
                <label className="universal-input">
                  <Link2 size={19} />
                  <input
                    aria-label="URL do conteúdo"
                    placeholder="Cole a URL de um vídeo ou página…"
                    value={source}
                    onChange={(e) => {
                      setSource(e.target.value);
                      setError("");
                    }}
                  />
                  <kbd>URL</kbd>
                </label>
              ) : mode === "idea" ? (
                <label className="field">
                  Sua ideia
                  <textarea
                    autoFocus
                    rows={3}
                    placeholder="O que você quer guardar ou explorar?"
                    value={idea}
                    onChange={(e) => setIdea(e.target.value)}
                  />
                </label>
              ) : (
                <div className="file-choice">
                  <FileText size={21} />
                  <div>
                    <strong>
                      {file?.name ?? "Escolha seu material de estudo"}
                    </strong>
                    <span>
                      PDF com texto, Markdown ou texto UTF-8 · Até 20 MB
                    </span>
                  </div>
                  <Button onClick={() => picker.current?.click()}>
                    {file ? "Trocar" : "Escolher"}
                  </Button>
                </div>
              )}
              <input
                ref={picker}
                type="file"
                accept=".pdf,.md,.txt"
                aria-label="Selecionar arquivo"
                className="sr-only"
                onChange={(e) => choose(e.target.files?.[0])}
              />
              {error && (
                <p role="alert" className="error-text">
                  {error}
                </p>
              )}
            </div>
            <div className="capture-submit">
              <DestinationChips value={destination} onChange={setDestination} />
              <Button type="submit" variant="primary" disabled={submitting}>
                {submitting ? "Recebendo…" : "Transferir"}
                <ArrowRight size={17} />
              </Button>
            </div>
          </form>
          <div className="capture-footnote">
            <ShieldCheck size={14} />
            <span>Você revisa a nota antes de confirmar o destino.</span>
          </div>
        </Surface>
        <aside className="capture-context">
          <div className="context-number">ENTENDER. CONECTAR. LEMBRAR.</div>
          <h2>
            Mais do que
            <br />
            salvar para depois.
          </h2>
          <p>
            Transforme o que desperta sua curiosidade em algo que faz parte do
            seu repertório.
          </p>
          <div className="context-steps">
            <div>
              <span>01</span>
              <div>
                <strong>Traga a fonte</strong>
                <p>Conteúdo de onde você aprende.</p>
              </div>
            </div>
            <div>
              <span>02</span>
              <div>
                <strong>Dê forma à nota</strong>
                <p>Revise, ajuste e conecte ideias.</p>
              </div>
            </div>
            <div>
              <span>03</span>
              <div>
                <strong>Escolha seu espaço</strong>
                <p>Obsidian, Notion ou os dois.</p>
              </div>
            </div>
          </div>
          <div className="destination-note">
            <span className="app-symbol">O</span>
            <span className="app-symbol">N</span>
            <p>
              Seu conhecimento.
              <br />
              <strong>Nas ferramentas que você usa.</strong>
            </p>
          </div>
        </aside>
      </div>
      <section className="recent-section">
        <div className="section-header">
          <div>
            <p className="eyebrow">RETOME UMA IDEIA</p>
            <h2>Capturas recentes</h2>
          </div>
          <Button variant="ghost" onClick={onHistory}>
            Ver biblioteca
            <ArrowUpRight size={15} />
          </Button>
        </div>
        {loading ? (
          <Skeletons />
        ) : recent.length ? (
          <div className="transfer-grid">
            {recent.map((t) => (
              <TransferCard key={t.id} transfer={t} onOpen={() => onOpen(t)} />
            ))}
          </div>
        ) : (
          <EmptyState
            title="Espaço para a próxima descoberta."
            text="Suas capturas aparecem aqui depois da primeira transferência."
          />
        )}
      </section>
    </>
  );
}
