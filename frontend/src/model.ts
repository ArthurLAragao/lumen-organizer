export type Destination = "obsidian" | "notion" | "both";
export type ContentType = "video" | "link" | "pdf" | "document" | "idea";
export type TransferStatus =
  | "queued"
  | "extracting"
  | "generating"
  | "review"
  | "publishing"
  | "completed"
  | "failed"
  | "cancelled";
export type View = "capture" | "pipeline" | "preview" | "library" | "settings";
export interface Note {
  title: string;
  summary: string;
  tags: string[];
  folder: string;
  format: "study" | "summary" | "atomic";
}
export interface Transfer {
  id: string;
  source: string;
  type: ContentType;
  destination: Destination;
  status: TransferStatus;
  createdAt: string;
  note: Note;
  error?: string;
  sourceText?: string;
  sourceTruncated?: boolean;
  markdown?: string;
  message?: string;
  exercise?: string;
  receipts?: Partial<
    Record<"obsidian" | "notion", { url: string; path?: string }>
  >;
  notionState?: string;
}
export interface Preferences {
  theme: "dark" | "light" | "system";
  accent: "blue" | "ice";
  density: "comfortable" | "compact";
  motion: boolean;
  destination: Destination;
  tags: string;
  folder: string;
  template: Note["format"];
  review: boolean;
}
export const initialPreferences: Preferences = {
  theme: "dark",
  accent: "blue",
  density: "comfortable",
  motion: true,
  destination: "both",
  tags: "estudos, biblioteca",
  folder: "Estudos / Caixa de entrada",
  template: "study",
  review: true,
};
export const destinations: Record<Destination, string> = {
  obsidian: "Obsidian",
  notion: "Notion",
  both: "Obsidian + Notion",
};
export const statuses: Record<TransferStatus, string> = {
  queued: "Na fila",
  extracting: "Extraindo",
  generating: "Gerando nota",
  review: "Revisar",
  publishing: "Publicando",
  completed: "Concluída",
  failed: "Falhou",
  cancelled: "Cancelada",
};
export const types: Record<ContentType, string> = {
  video: "Vídeo",
  link: "Link",
  pdf: "PDF",
  document: "Arquivo",
  idea: "Ideia",
};
export const processing = (s: TransferStatus) =>
  ["queued", "extracting", "generating", "publishing"].includes(s);
export const progress: Record<TransferStatus, number> = {
  queued: 4,
  extracting: 24,
  generating: 55,
  review: 76,
  publishing: 88,
  completed: 100,
  failed: 0,
  cancelled: 0,
};
