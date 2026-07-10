/**
 * 论文阅读状态 - UI 配置与状态切换工具
 * 状态持久化已迁移到后端 SQLite，前端通过 API 管理。
 */

import type { PaperStatus } from "@/lib/api";

export type { PaperStatus };

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

export function getStatusConfig(status: PaperStatus) {
  return STATUS_CONFIG[status];
}

/** 纯函数：计算下一个阅读状态 unread → reading → read → unread */
export function cycleStatus(current: PaperStatus): PaperStatus {
  return current === "unread" ? "reading" : current === "reading" ? "read" : "unread";
}
