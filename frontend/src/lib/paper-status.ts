/**
 * 论文阅读状态管理 - localStorage
 * 状态：unread | reading | read
 */

export type PaperStatus = "unread" | "reading" | "read";

const STORAGE_KEY = "papermind_paper_status";

const STATUS_CONFIG: Record<PaperStatus, {
  label: string;
  color: string;
  bg: string;
  border: string;
  dot: string;
  cardOpacity: string;
  titleClass: string;
}> = {
  unread: {
    label: "Unread",
    color: "text-gray-500",
    bg: "bg-gray-100",
    border: "border-l-gray-300",
    dot: "bg-gray-400",
    cardOpacity: "opacity-70",
    titleClass: "",
  },
  reading: {
    label: "Reading",
    color: "text-blue-600",
    bg: "bg-blue-50",
    border: "border-l-blue-400",
    dot: "bg-blue-500",
    cardOpacity: "",
    titleClass: "font-semibold",
  },
  read: {
    label: "Read",
    color: "text-emerald-600",
    bg: "bg-emerald-50",
    border: "border-l-emerald-400",
    dot: "bg-emerald-500",
    cardOpacity: "",
    titleClass: "text-muted-foreground",
  },
};

function loadAll(): Record<string, PaperStatus> {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function saveAll(data: Record<string, PaperStatus>) {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
}

export function getPaperStatus(title: string): PaperStatus {
  const all = loadAll();
  return all[title] || "unread";
}

export function setPaperStatus(title: string, status: PaperStatus) {
  const all = loadAll();
  all[title] = status;
  saveAll(all);
}

export function cyclePaperStatus(title: string): PaperStatus {
  const current = getPaperStatus(title);
  const next: PaperStatus = current === "unread" ? "reading" : current === "reading" ? "read" : "unread";
  setPaperStatus(title, next);
  return next;
}

export function getStatusConfig(status: PaperStatus) {
  return STATUS_CONFIG[status];
}
