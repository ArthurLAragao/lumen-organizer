import { useState } from "react";
import { ChevronRight, Search } from "lucide-react";
import {
  Button,
  EmptyState,
  Skeletons,
  SourceIcon,
  StatusPill,
  Surface,
} from "../components";
import { destinations, statuses, types, type Transfer } from "../model";

export function Library({
  transfers,
  loading,
  error,
  onReload,
  onOpen,
}: {
  transfers: Transfer[];
  loading: boolean;
  error: boolean;
  onReload: () => void;
  onOpen: (t: Transfer) => void;
}) {
  const [query, setQuery] = useState("");
  const [type, setType] = useState("all");
  const [destination, setDestination] = useState("all");
  const [status, setStatus] = useState("all");
  const [date, setDate] = useState("all");
  const [source, setSource] = useState("all");
  const filtered = transfers.filter(
    (t) =>
      `${t.note.title} ${t.source} ${t.note.tags.join(" ")}`
        .toLocaleLowerCase("pt-BR")
        .includes(query.toLocaleLowerCase("pt-BR")) &&
      (type === "all" || type === t.type) &&
      (destination === "all" ||
        t.destination === destination ||
        t.destination === "both") &&
      (status === "all" || status === t.status) &&
      (source === "all" ||
        (source === "web"
          ? ["link", "video"].includes(t.type)
          : !["link", "video"].includes(t.type))) &&
      (date === "all" ||
        Date.now() - new Date(t.createdAt).getTime() < Number(date) * 86400000),
  );
  return (
    <Surface className="library-surface">
      <div className="library-search">
        <Search size={19} />
        <input
          aria-label="Buscar na biblioteca"
          placeholder="Buscar por título, fonte ou tag…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <span>{filtered.length} registros</span>
      </div>
      <div className="filters">
        <label>
          Tipo
          <select value={type} onChange={(e) => setType(e.target.value)}>
            <option value="all">Todos</option>
            {Object.entries(types).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Destino
          <select
            value={destination}
            onChange={(e) => setDestination(e.target.value)}
          >
            <option value="all">Todos</option>
            <option value="obsidian">Obsidian</option>
            <option value="notion">Notion</option>
            <option value="both">Ambos</option>
          </select>
        </label>
        <label>
          Estado
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="all">Todos</option>
            {Object.entries(statuses).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Fonte
          <select value={source} onChange={(e) => setSource(e.target.value)}>
            <option value="all">Todas</option>
            <option value="web">Web</option>
            <option value="local">Arquivo / ideia</option>
          </select>
        </label>
        <label>
          Período
          <select value={date} onChange={(e) => setDate(e.target.value)}>
            <option value="all">Todo o histórico</option>
            <option value="1">Últimas 24h</option>
            <option value="7">Últimos 7 dias</option>
            <option value="30">Últimos 30 dias</option>
          </select>
        </label>
      </div>
      {error ? (
        <EmptyState
          title="Não conseguimos abrir o histórico."
          text="Tente carregar os exemplos novamente."
          action={<Button onClick={onReload}>Tentar novamente</Button>}
        />
      ) : loading ? (
        <Skeletons />
      ) : filtered.length ? (
        <div className="history-list">
          {filtered.map((t) => (
            <button
              className="history-row"
              key={t.id}
              onClick={() => onOpen(t)}
            >
              <SourceIcon type={t.type} />
              <div className="history-title">
                <strong>{t.note.title}</strong>
                <span>{t.source}</span>
              </div>
              <span className="history-destination">
                {destinations[t.destination]}
              </span>
              <time dateTime={t.createdAt}>
                {new Intl.DateTimeFormat("pt-BR", {
                  day: "2-digit",
                  month: "short",
                }).format(new Date(t.createdAt))}
              </time>
              <StatusPill status={t.status} />
              <ChevronRight size={16} />
            </button>
          ))}
        </div>
      ) : (
        <EmptyState
          title="Nenhuma captura por aqui."
          text="Experimente outra busca ou ajuste os filtros."
        />
      )}
    </Surface>
  );
}
