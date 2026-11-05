import { useEffect, useState } from "react";
import { api } from "../service";
import {
  ArrowDownToLine,
  FolderOpen,
  Moon,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { Button, DestinationChips, Surface } from "../components";
import { destinations, type Note, type Preferences } from "../model";

export function Settings({
  preferences: p,
  onChange,
  onExplain,
}: {
  preferences: Preferences;
  onChange: (p: Preferences) => void;
  onExplain: (s: string) => void;
}) {
  const [connection, setConnection] = useState("Verificando serviço local…");
  const [hermes, setHermes] = useState("Verificando Hermes…");
  useEffect(() => {
    api<{ message: string }>("/api/hermes/status")
      .then((value) => setHermes(value.message))
      .catch((e) => setHermes(String(e.message)));
  }, []);
  useEffect(() => {
    api<{ obsidian: boolean; codex: boolean; exportRoot: string }>(
      "/api/connections",
    )
      .then((c) =>
        setConnection(
          `Obsidian: ${c.obsidian ? "vault disponível" : "vault não encontrado"}. Codex: ${c.codex ? "instalado" : "não encontrado"}. Pasta: ${c.exportRoot}. Notion usa sua conexão no Codex; a entrega é conferida a cada envio.`,
        ),
      )
      .catch((e) => setConnection(String(e.message)));
  }, []);
  function change(patch: Partial<Preferences>) {
    onChange({ ...p, ...patch });
  }
  return (
    <div className="settings-grid">
      <Surface className="settings-panel">
        <div className="settings-title">
          <FolderOpen size={20} />
          <div>
            <h2>Seus destinos</h2>
            <p>Conhecimento onde você já se organiza.</p>
          </div>
        </div>
        {(["obsidian", "notion"] as const).map((d) => (
          <div className="account-row" key={d}>
            <span className="app-symbol">{d === "notion" ? "N" : "O"}</span>
            <div>
              <strong>{destinations[d]}</strong>
              <span>
                {d === "obsidian"
                  ? "Pasta local do seu conhecimento"
                  : "Sua biblioteca de estudos"}
              </span>
            </div>
            <Button
              onClick={() =>
                onExplain(
                  "Obsidian salva numa pasta dedicada do seu vault. Notion usa a conexão do Codex e confirma a página após o envio.",
                )
              }
            >
              Sobre a conexão
            </Button>
          </div>
        ))}
        <p className="settings-hint">{connection}</p>
        <div className="account-row">
          <div>
            <strong>Hermes + Orca</strong>
            <span>{hermes}</span>
          </div>
          <Button
            onClick={() => {
              void api("/api/apps/open", { command: "conectar hermes" }).catch(
                (e) => onExplain(String(e.message)),
              );
            }}
          >
            Conectar Hermes
          </Button>
        </div>
      </Surface>
      <Surface className="settings-panel">
        <div className="settings-title">
          <Moon size={20} />
          <div>
            <h2>Aparência</h2>
            <p>Um espaço confortável para pensar.</p>
          </div>
        </div>
        <label className="field horizontal-field">
          Tema
          <select
            value={p.theme}
            onChange={(e) =>
              change({ theme: e.target.value as Preferences["theme"] })
            }
          >
            <option value="dark">Escuro</option>
            <option value="light">Claro</option>
            <option value="system">Sistema</option>
          </select>
        </label>
        <label className="field horizontal-field">
          Azul de destaque
          <select
            value={p.accent}
            onChange={(e) =>
              change({ accent: e.target.value as Preferences["accent"] })
            }
          >
            <option value="blue">Azul</option>
            <option value="ice">Azul gelo</option>
          </select>
        </label>
        <label className="field horizontal-field">
          Densidade
          <select
            value={p.density}
            onChange={(e) =>
              change({ density: e.target.value as Preferences["density"] })
            }
          >
            <option value="comfortable">Confortável</option>
            <option value="compact">Compacta</option>
          </select>
        </label>
        <label className="toggle-row">
          <span>
            <strong>Reduzir movimento</strong>
            <small>A preferência do sistema também é respeitada.</small>
          </span>
          <input
            type="checkbox"
            role="switch"
            checked={!p.motion}
            onChange={(e) => change({ motion: !e.target.checked })}
          />
        </label>
      </Surface>
      <Surface className="settings-panel">
        <div className="settings-title">
          <ArrowDownToLine size={20} />
          <div>
            <h2>Padrões de captura</h2>
            <p>Um ponto de partida para cada nova ideia.</p>
          </div>
        </div>
        <DestinationChips
          value={p.destination}
          onChange={(destination) => change({ destination })}
        />
        <label className="field">
          Tags padrão
          <input
            value={p.tags}
            onChange={(e) => change({ tags: e.target.value })}
          />
        </label>
        <label className="field">
          Pasta ou banco de dados padrão
          <input
            value={p.folder}
            onChange={(e) => change({ folder: e.target.value })}
          />
        </label>
        <label className="field">
          Modelo da nota
          <select
            value={p.template}
            onChange={(e) =>
              change({ template: e.target.value as Note["format"] })
            }
          >
            <option value="study">Estudo · resumo, conexões e prática</option>
          </select>
        </label>
        <p className="settings-hint">
          As escolhas são aplicadas às próximas capturas. A pasta é relativa à
          Biblioteca Lumen do Obsidian; o banco do Notion é a Biblioteca Lumen.
        </p>
      </Surface>
      <Surface className="settings-panel processing-settings">
        <div className="settings-title">
          <Sparkles size={20} />
          <div>
            <h2>Processamento</h2>
            <p>Clareza sobre cada etapa.</p>
          </div>
        </div>
        <div className="preference-description">
          <ShieldCheck size={26} />
          <h3>Revisar faz parte do fluxo.</h3>
          <p>
            Toda nota passa por revisão antes do envio. A validação estrutural
            não substitui a revisão dos fatos na fonte.
          </p>
        </div>
        <dl className="settings-facts">
          <div>
            <dt>Idioma da nota</dt>
            <dd>Português</dd>
          </div>
          <div>
            <dt>Processamento</dt>
            <dd>Codex / ChatGPT, em português</dd>
          </div>
          <div>
            <dt>Publicação automática</dt>
            <dd>Somente após sua confirmação</dd>
          </div>
          <div>
            <dt>Persistência</dt>
            <dd>Histórico local e preferências</dd>
          </div>
        </dl>
      </Surface>
    </div>
  );
}
