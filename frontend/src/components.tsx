import {
  useEffect,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type ReactNode,
} from "react";
import {
  ArrowUpRight,
  BookOpen,
  Check,
  FileText,
  Link2,
  Loader2,
  Video,
  X,
  Lightbulb,
  Inbox,
  ArrowRight,
} from "lucide-react";
import {
  destinations,
  progress,
  statuses,
  types,
  processing,
  type Destination,
  type Transfer,
  type TransferStatus,
  type ContentType,
} from "./model";
export function Button({
  variant = "secondary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
}) {
  return (
    <button
      type="button"
      className={`btn btn-${variant} ${className}`}
      {...props}
    />
  );
}
export function Surface({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <section className={`surface ${className}`}>{children}</section>;
}
export function SourceIcon({ type }: { type: ContentType }) {
  const Icon = {
    video: Video,
    link: Link2,
    pdf: FileText,
    document: FileText,
    idea: Lightbulb,
  }[type];
  return (
    <span className={`source-icon source-${type}`}>
      <Icon size={20} aria-hidden="true" />
    </span>
  );
}
export function StatusPill({ status }: { status: TransferStatus }) {
  return (
    <span className="status-pill" data-status={status}>
      {status === "completed" ? (
        <Check size={12} aria-hidden="true" />
      ) : processing(status) ? (
        <Loader2 size={12} aria-hidden="true" className="activity-icon" />
      ) : (
        <span className="status-dot" />
      )}
      {statuses[status]}
    </span>
  );
}
export function DestinationChips({
  value,
  onChange,
}: {
  value: Destination;
  onChange: (d: Destination) => void;
}) {
  return (
    <fieldset className="destination-chips">
      <legend>Destino</legend>
      {(["obsidian", "notion", "both"] as const).map((d) => (
        <label key={d}>
          <input
            type="radio"
            name="destination"
            value={d}
            checked={value === d}
            onChange={() => onChange(d)}
          />
          <span>
            {d === "both" ? "Ambos" : destinations[d]}
            {value === d && <Check size={14} aria-hidden="true" />}
          </span>
        </label>
      ))}
    </fieldset>
  );
}
export function TagInput({
  value,
  onChange,
}: {
  value: string[];
  onChange: (tags: string[]) => void;
}) {
  const [draft, setDraft] = useState("");
  function commit() {
    if (draft.trim())
      onChange([...new Set([...value, draft.trim().replace(/^#/, "")])]);
    setDraft("");
  }
  return (
    <div className="tag-input">
      {value.map((tag) => (
        <span className="tag" key={tag}>
          #{tag}
          <button
            type="button"
            aria-label={`Remover tag ${tag}`}
            onClick={() => onChange(value.filter((t) => t !== tag))}
          >
            <X size={12} />
          </button>
        </span>
      ))}
      <input
        aria-label="Adicionar tag"
        placeholder="Nova tag…"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === ",") {
            e.preventDefault();
            commit();
          }
        }}
      />
    </div>
  );
}
export function TransferCard({
  transfer: t,
  onOpen,
  onCancel,
  onRetry,
}: {
  transfer: Transfer;
  onOpen: () => void;
  onCancel?: () => void;
  onRetry?: () => void;
}) {
  return (
    <article className="transfer-card">
      <div className="transfer-row">
        <SourceIcon type={t.type} />
        <button className="transfer-title" onClick={onOpen}>
          <strong>{t.note.title}</strong>
          <span>
            {types[t.type]} <span aria-hidden="true">→</span>{" "}
            {destinations[t.destination]}
          </span>
        </button>
        <StatusPill status={t.status} />
      </div>
      {processing(t.status) && (
        <progress
          max={100}
          value={progress[t.status]}
          aria-label={`Progresso de ${t.note.title}`}
        />
      )}
      <div className="transfer-bottom">
        <time dateTime={t.createdAt}>
          {new Intl.DateTimeFormat("pt-BR", {
            day: "2-digit",
            month: "short",
            hour: "2-digit",
            minute: "2-digit",
          }).format(new Date(t.createdAt))}
        </time>
        <div>
          {processing(t.status) && onCancel && (
            <Button variant="ghost" onClick={onCancel}>
              Cancelar
            </Button>
          )}
          {t.status === "failed" && onRetry && (
            <Button variant="ghost" onClick={onRetry}>
              Tentar novamente
            </Button>
          )}
          <Button variant="ghost" onClick={onOpen}>
            {t.status === "review" ? "Revisar nota" : "Ver detalhes"}
            <ArrowUpRight size={14} />
          </Button>
        </div>
      </div>
      {t.error && <p className="error-text">{t.error}</p>}
      {t.message && <p className="settings-hint">{t.message}</p>}
    </article>
  );
}
export function EmptyState({
  title,
  text,
  action,
}: {
  title: string;
  text: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Inbox size={26} />
      </span>
      <h3>{title}</h3>
      <p>{text}</p>
      {action}
    </div>
  );
}
export function Skeletons() {
  return (
    <div role="status" aria-label="Carregando histórico" className="skeletons">
      {[0, 1, 2].map((i) => (
        <div className="skeleton" key={i} />
      ))}
    </div>
  );
}
export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const el = ref.current;
    el?.showModal();
    return () => el?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className="glass-modal"
      aria-label={title}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal-head">
        <h2>{title}</h2>
        <Button variant="ghost" aria-label="Fechar" onClick={onClose}>
          <X size={18} />
        </Button>
      </div>
      {children}
    </dialog>
  );
}
export function PipelineFlow({ transfer }: { transfer?: Transfer }) {
  const state = transfer?.status ?? "queued";
  return (
    <div className="pipeline-flow">
      {[
        {
          title: "Entrada",
          text: "Vídeo, link, arquivo ou ideia",
          icon: FileText,
          active: true,
        },
        {
          title: "Processamento",
          text:
            state === "failed"
              ? "Precisa de atenção"
              : "Extração e organização",
          icon: Loader2,
          active: state !== "queued",
        },
        {
          title: "Destino",
          text: transfer
            ? destinations[transfer.destination]
            : "Obsidian e Notion",
          icon: BookOpen,
          active: ["publishing", "completed"].includes(state),
        },
      ].map((step, index) => (
        <div className="flow-wrapper" key={step.title}>
          {index > 0 && (
            <ArrowRight size={18} className="flow-arrow" aria-hidden="true" />
          )}
          <div className="flow-step" data-active={step.active}>
            <step.icon size={22} aria-hidden="true" />
            <div>
              <strong>{step.title}</strong>
              <span>{step.text}</span>
            </div>
            {step.active && index === 2 && (
              <Check size={16} aria-hidden="true" />
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
