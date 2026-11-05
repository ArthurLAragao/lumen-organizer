import { Capture } from "./views/Capture";
import { Preview } from "./views/Preview";
import { Library } from "./views/Library";
import { Settings } from "./views/Settings";
import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  AudioLines,
  BookOpen,
  Check,
  ChevronRight,
  Command,
  FileText,
  Layers3,
  Plus,
  Search,
  Settings2,
  ShieldCheck,
  X,
} from "lucide-react";
import {
  Button,
  EmptyState,
  Modal,
  PipelineFlow,
  Skeletons,
  SourceIcon,
  StatusPill,
  Surface,
  TransferCard,
} from "./components";
import {
  destinations,
  initialPreferences,
  processing,
  type ContentType,
  type Destination,
  type Note,
  type Preferences,
  type Transfer,
  type View,
} from "./model";
import { transferService } from "./service";

const nav = [
  { id: "capture", title: "Capturar", icon: Plus },
  { id: "pipeline", title: "Transferências", icon: Layers3 },
  { id: "preview", title: "Prévia", icon: FileText },
  { id: "library", title: "Biblioteca", icon: BookOpen },
  { id: "settings", title: "Preferências", icon: Settings2 },
] as const;
const titles: Record<
  View,
  { eyebrow: string; title: string; description: string }
> = {
  capture: {
    eyebrow: "DA CURIOSIDADE À CLAREZA",
    title: "Dê um lugar às suas ideias.",
    description:
      "Traga o que importa. O Lumen organiza o caminho até o seu conhecimento.",
  },
  pipeline: {
    eyebrow: "CONHECIMENTO EM MOVIMENTO",
    title: "Cada etapa, com clareza.",
    description:
      "Acompanhe suas capturas enquanto continua o que estava fazendo.",
  },
  preview: {
    eyebrow: "UMA PAUSA PARA REVISAR",
    title: "A sua nota, do seu jeito.",
    description: "Ajuste os detalhes antes de dar um novo lugar ao conteúdo.",
  },
  library: {
    eyebrow: "SEU HISTÓRICO DE DESCOBERTAS",
    title: "Boas ideias merecem voltar.",
    description: "Encontre o que você capturou e retome de onde parou.",
  },
  settings: {
    eyebrow: "FEITO PARA O SEU FLUXO",
    title: "Menos ajustes. Mais fluidez.",
    description: "Defina uma vez. Deixe as próximas capturas mais simples.",
  },
};
function loadPreferences(): Preferences {
  try {
    const saved: unknown = JSON.parse(
      localStorage.getItem("lumen-ui-preferences") ?? "null",
    );
    if (!saved || typeof saved !== "object") return initialPreferences;
    const s = saved as Record<string, unknown>;
    return {
      theme: ["dark", "light", "system"].includes(String(s.theme))
        ? (s.theme as Preferences["theme"])
        : "dark",
      accent: s.accent === "ice" ? "ice" : "blue",
      density: s.density === "compact" ? "compact" : "comfortable",
      motion: s.motion !== false,
      destination: ["obsidian", "notion", "both"].includes(
        String(s.destination),
      )
        ? (s.destination as Destination)
        : "both",
      tags: typeof s.tags === "string" ? s.tags : initialPreferences.tags,
      folder:
        typeof s.folder === "string" ? s.folder : initialPreferences.folder,
      template: ["study", "summary", "atomic"].includes(String(s.template))
        ? (s.template as Note["format"])
        : "study",
      review: s.review !== false,
    };
  } catch {
    return initialPreferences;
  }
}

export default function App() {
  const [view, setView] = useState<View>("capture");
  const [preferences, setPreferences] = useState(loadPreferences);
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [palette, setPalette] = useState(false);
  const [command, setCommand] = useState("");
  const [toast, setToast] = useState("");
  const [detail, setDetail] = useState<Transfer | null>(null);
  const [storageError, setStorageError] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const selectedTransfer =
    transfers.find((t) => t.id === selected) ??
    transfers.find((t) => t.status === "review") ??
    transfers[0];
  const active = transfers.filter((t) => processing(t.status)).length;
  async function load() {
    setLoading(true);
    setLoadError(false);
    try {
      setTransfers(await transferService.list());
    } catch {
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    let alive = true;
    transferService
      .list()
      .then((data) => {
        if (alive) setTransfers(data);
      })
      .catch(() => {
        if (alive) setLoadError(true);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);
  useEffect(() => {
    const media = matchMedia("(prefers-color-scheme: dark)");
    function apply() {
      document.documentElement.dataset.theme =
        preferences.theme === "system"
          ? media.matches
            ? "dark"
            : "light"
          : preferences.theme;
    }
    apply();
    document.documentElement.dataset.accent = preferences.accent;
    document.documentElement.dataset.density = preferences.density;
    document.documentElement.dataset.motion = preferences.motion
      ? "full"
      : "reduce";
    media.addEventListener("change", apply);
    try {
      localStorage.setItem("lumen-ui-preferences", JSON.stringify(preferences));
    } catch {
      setStorageError(true);
    }
    return () => media.removeEventListener("change", apply);
  }, [preferences]);
  useEffect(() => {
    function key(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPalette((p) => !p);
        setCommand("");
      }
    }
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  const drafts = useRef(new Map<string, Partial<Transfer>>());
  useEffect(() => {
    let alive = true;
    let running = false;
    async function refresh() {
      if (running) return;
      running = true;
      try {
        const rows = await transferService.list();
        if (alive) {
          setLoadError(false);
          setTransfers(
            rows.map((t) => ({
              ...t,
              ...(t.status === "review" ? drafts.current.get(t.id) : {}),
            })),
          );
        }
      } catch {
        if (alive) setLoadError(true);
      } finally {
        running = false;
      }
    }
    const timer = window.setInterval(() => void refresh(), 2000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);
  function go(next: View) {
    setView(next);
    setPalette(false);
    requestAnimationFrame(() => heading.current?.focus());
  }
  function open(t: Transfer) {
    setSelected(t.id);
    go("preview");
  }
  function update(id: string, patch: Partial<Transfer>) {
    drafts.current.set(id, { ...drafts.current.get(id), ...patch });
    setTransfers((current) =>
      current.map((t) => (t.id === id ? { ...t, ...patch } : t)),
    );
  }
  async function cancel(t: Transfer) {
    try {
      const job = await transferService.cancel(t.id);
      setTransfers((current) => current.map((v) => (v.id === t.id ? job : v)));
      setToast(
        "Cancelamento registrado. A operação em curso termina sem publicar.",
      );
    } catch (e) {
      setToast(e instanceof Error ? e.message : "Não foi possível cancelar.");
    }
  }
  async function retry(t: Transfer) {
    try {
      const job = await transferService.retry(t.id);
      setTransfers((current) => current.map((v) => (v.id === t.id ? job : v)));
      setToast(
        "Solicitação registrada. Os comprovantes de entrega foram preservados.",
      );
    } catch (e) {
      setToast(e instanceof Error ? e.message : "Não foi possível repetir.");
    }
  }
  async function capture(
    source: string,
    type: ContentType,
    destination: Destination,
    file?: File,
  ) {
    const transfer = await transferService.create(
      source,
      type,
      destination,
      preferences,
      file,
    );
    setTransfers((ts) => [transfer, ...ts.filter(item => item.id !== transfer.id)]);
    setSelected(transfer.id);
    setToast(
      "Captura recebida. O processamento real continua em segundo plano.",
    );
    go("pipeline");
  }
  async function publish(t: Transfer) {
    try {
      const saved = Object.keys(t.receipts ?? {}).length
        ? t
        : await transferService.save(t);
      drafts.current.delete(t.id);
      const job = await transferService.publish(saved);
      setTransfers((current) => current.map((v) => (v.id === t.id ? job : v)));
      setToast("Envio iniciado. Acompanhe a confirmação de cada destino.");
    } catch (e) {
      setToast(
        e instanceof Error
          ? e.message
          : "O envio não foi confirmado. Confira os destinos antes de repetir.",
      );
    }
  }
  async function saveDraft(t: Transfer) {
    try {
      const saved = await transferService.save(t);
      drafts.current.delete(t.id);
      setTransfers((current) =>
        current.map((v) => (v.id === t.id ? saved : v)),
      );
      setToast("Rascunho salvo no histórico local. Nada foi publicado.");
    } catch (e) {
      setToast(
        e instanceof Error ? e.message : "Não foi possível salvar o rascunho.",
      );
    }
  }
  const page = titles[view];
  return (
    <div className="lumen-shell">
      <a href="#workspace" className="skip-link">
        Pular para o conteúdo
      </a>
      <aside className="sidebar">
        <a
          className="wordmark"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            go("capture");
          }}
          aria-label="Lumen — início"
        >
          <span className="brand-symbol">
            <AudioLines size={23} />
          </span>
          lumen<span className="wordmark-dot">.</span>
        </a>
        <span className="sidebar-caption">SEU ESPAÇO DE CONHECIMENTO</span>
        <nav aria-label="Navegação principal">
          {nav.map((item) => (
            <button
              key={item.id}
              aria-current={view === item.id ? "page" : undefined}
              onClick={() => go(item.id)}
            >
              <item.icon size={18} aria-hidden="true" />
              <span>{item.title}</span>
              {item.id === "pipeline" && active > 0 && (
                <span className="nav-count">{active}</span>
              )}
            </button>
          ))}
        </nav>
        <button className="sidebar-command" onClick={() => setPalette(true)}>
          <Command size={16} />
          <span>Ir para…</span>
          <kbd>Ctrl K</kbd>
        </button>
        <div className="sidebar-bottom">
          <div className="workspace-avatar">T</div>
          <div>
            <strong>Meu espaço</strong>
            <span>Biblioteca pessoal</span>
          </div>
          <ShieldCheck size={16} />
        </div>
      </aside>
      <div className="main-column">
        <header className="topbar">
          <div>
            <span>Meu espaço</span>
            <ChevronRight size={13} aria-hidden="true" />
            <strong>{nav.find((n) => n.id === view)?.title}</strong>
          </div>
          <div>
            <span className="demo-badge">
              <span />
              Serviço local
            </span>
            <Button
              variant="ghost"
              aria-label="Abrir paleta de comandos"
              onClick={() => setPalette(true)}
            >
              <Search size={18} />
            </Button>
          </div>
        </header>
        <main id="workspace">
          <div className="page-heading">
            <div>
              <p className="eyebrow">{page.eyebrow}</p>
              <h1 tabIndex={-1} ref={heading}>
                {page.title}
              </h1>
              <p>{page.description}</p>
            </div>
            {view !== "capture" && (
              <Button onClick={() => go("capture")}>
                <Plus size={16} />
                Nova captura
              </Button>
            )}
          </div>
          <p className="demo-notice">
            <ShieldCheck size={14} aria-hidden="true" />
            Seu conteúdo é processado pelo Codex. Revise antes de enviar ao
            Obsidian ou Notion.
          </p>
          {storageError && (
            <p role="alert" className="error-text">
              As preferências funcionam nesta sessão, mas o navegador bloqueou
              seu salvamento.
            </p>
          )}
          {loadError && (
            <p role="alert" className="error-text">
              O serviço local não respondeu. Reabra pelo atalho Lumen e tente
              novamente.
            </p>
          )}
          {view === "capture" && (
            <Capture
              preferences={preferences}
              recent={transfers.slice(0, 3)}
              loading={loading}
              onCapture={capture}
              onOpen={open}
              onHistory={() => go("library")}
            />
          )}
          {view === "pipeline" && (
            <>
              <Surface className="flow-surface">
                <div className="section-header">
                  <div>
                    <p className="eyebrow">SEU FLUXO</p>
                    <h2>Da entrada ao destino.</h2>
                  </div>
                  <span className="muted">{active} em processamento</span>
                </div>
                <PipelineFlow transfer={selectedTransfer} />
              </Surface>
              <div className="section-header">
                <h2>Transferências</h2>
                <span className="muted">
                  A revisão acontece antes de publicar
                </span>
              </div>
              {loading ? (
                <Skeletons />
              ) : (
                <div className="transfer-grid">
                  {transfers.map((t) => (
                    <TransferCard
                      key={t.id}
                      transfer={t}
                      onOpen={() => open(t)}
                      onCancel={() => cancel(t)}
                      onRetry={() => retry(t)}
                    />
                  ))}
                </div>
              )}
              {!loading && transfers.length === 0 && (
                <EmptyState
                  title="Seu fluxo começa com uma captura."
                  text="Adicione uma fonte para acompanhar o caminho até sua nota."
                  action={
                    <Button onClick={() => go("capture")}>
                      Capturar conteúdo
                    </Button>
                  }
                />
              )}
            </>
          )}
          {view === "preview" &&
            (selectedTransfer ? (
              <Preview
                key={selectedTransfer.id}
                transfer={selectedTransfer}
                onSave={(note) => update(selectedTransfer.id, { note })}
                onDestination={(destination) =>
                  update(selectedTransfer.id, { destination })
                }
                onPublish={publish}
                onPersist={saveDraft}
                onDetails={setDetail}
              />
            ) : (
              <EmptyState
                title="Sua próxima nota começa aqui."
                text="Capture um conteúdo para revisar sua prévia lado a lado."
                action={
                  <Button onClick={() => go("capture")}>
                    Fazer uma captura
                  </Button>
                }
              />
            ))}
          {view === "library" && (
            <Library
              transfers={transfers}
              loading={loading}
              error={loadError}
              onReload={load}
              onOpen={open}
            />
          )}
          {view === "settings" && (
            <Settings
              preferences={preferences}
              onChange={setPreferences}
              onExplain={setToast}
            />
          )}

          <footer className="page-footer">
            <span>
              <AudioLines size={14} /> Menos conteúdo perdido. Mais conexões.
            </span>
            <span>Lumen / Interface de estudo</span>
          </footer>
        </main>
      </div>
      {toast && (
        <div role="status" className="toast">
          <Check size={18} />
          <p>{toast}</p>
          <Button
            variant="ghost"
            aria-label="Fechar notificação"
            onClick={() => setToast("")}
          >
            <X size={16} />
          </Button>
        </div>
      )}
      {palette && (
        <Modal title="Aonde vamos?" onClose={() => setPalette(false)}>
          <label className="command-search">
            <Search size={18} />
            <input
              autoFocus
              placeholder="Buscar uma página ou ação…"
              aria-label="Buscar comando"
              value={command}
              onChange={(e) => setCommand(e.target.value)}
            />
            <kbd>Esc</kbd>
          </label>
          <div className="command-list">
            {nav
              .filter((n) =>
                n.title
                  .toLocaleLowerCase("pt-BR")
                  .includes(command.toLocaleLowerCase("pt-BR")),
              )
              .map((n) => (
                <button key={n.id} onClick={() => go(n.id)}>
                  <n.icon size={18} />
                  {n.title}
                  <ArrowRight size={16} />
                </button>
              ))}
            {!nav.some((n) =>
              n.title
                .toLocaleLowerCase("pt-BR")
                .includes(command.toLocaleLowerCase("pt-BR")),
            ) && <p className="muted">Nenhum comando encontrado.</p>}
          </div>
        </Modal>
      )}
      {detail && (
        <Modal
          title="Detalhes da transferência"
          onClose={() => setDetail(null)}
        >
          <div className="detail-content">
            <SourceIcon type={detail.type} />
            <h3>{detail.note.title}</h3>
            <StatusPill status={detail.status} />
            <dl>
              <dt>Fonte</dt>
              <dd>{detail.source}</dd>
              <dt>Destino</dt>
              <dd>{destinations[detail.destination]}</dd>
              <dt>Identificador</dt>
              <dd>{detail.id}</dd>
            </dl>
            <p>
              A fonte original e os comprovantes de entrega são preservados no
              histórico local.
            </p>
          </div>
        </Modal>
      )}
    </div>
  );
}
