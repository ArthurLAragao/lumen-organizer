import type { Transfer, Destination, ContentType, Preferences } from "./model";
let token = "";
export async function api<T>(path: string, body?: unknown): Promise<T> {
  if (!token) {
    const response = await fetch("/api/health", { cache: "no-store" });
    const health: unknown = await response.json();
    if (
      !response.ok ||
      !health ||
      typeof health !== "object" ||
      !("token" in health) ||
      typeof health.token !== "string" ||
      !("mode" in health) ||
      health.mode !== "live"
    )
      throw new Error(
        "Abra o Lumen pelo atalho atualizado para iniciar o serviço real.",
      );
    token = health.token;
  }
  const response = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      "X-Lumen-Token": token,
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  const value: unknown = await response.json();
  if (!response.ok) {
    if (response.status === 403) token = "";
    throw new Error(
      value && typeof value === "object" && "error" in value
        ? String(value.error)
        : "O serviço local não concluiu o pedido.",
    );
  }
  return value as T;
}
export interface TransferService {
  list(): Promise<Transfer[]>;
  create(
    source: string,
    type: ContentType,
    destination: Destination,
    preferences: Preferences,
    file?: File,
  ): Promise<Transfer>;
  save(transfer: Transfer): Promise<Transfer>;
  publish(transfer: Transfer): Promise<Transfer>;
  cancel(id: string): Promise<Transfer>;
  retry(id: string): Promise<Transfer>;
  open(id: string, destination: "obsidian" | "notion"): Promise<void>;
}
class LocalTransferService implements TransferService {
  list() {
    return api<Transfer[]>("/api/transfers");
  }
  async create(
    source: string,
    type: ContentType,
    destination: Destination,
    preferences: Preferences,
    file?: File,
  ) {
    let upload: string | undefined;
    if (file) {
      if (file.size > 20 * 1024 * 1024)
        throw new Error("O arquivo deve ter no máximo 20 MB.");
      const bytes = new Uint8Array(await file.arrayBuffer());
      const parts: string[] = [];
      for (let i = 0; i < bytes.length; i += 8192)
        parts.push(String.fromCharCode(...bytes.subarray(i, i + 8192)));
      upload = btoa(parts.join(""));
    }
    return api<Transfer>("/api/transfers", {
      source,
      type,
      destination,
      preferences,
      upload,
    });
  }
  save(t: Transfer) {
    return api<Transfer>(`/api/transfers/${t.id}/save`, {
      note: t.note,
      destination: t.destination,
    });
  }
  publish(t: Transfer) {
    return api<Transfer>(`/api/transfers/${t.id}/publish`, { reviewed: true });
  }
  cancel(id: string) {
    return api<Transfer>(`/api/transfers/${id}/cancel`, {});
  }
  retry(id: string) {
    return api<Transfer>(`/api/transfers/${id}/retry`, {});
  }
  async open(id: string, destination: "obsidian" | "notion") {
    await api(`/api/transfers/${id}/open`, { destination });
  }
}
export const transferService: TransferService = new LocalTransferService();
