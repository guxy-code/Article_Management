"use client";

import { GitBranch, Plus, Zap, Layers, RefreshCw } from "lucide-react";
import type { GrowthLogEntry } from "@/lib/api";

const EVENT_META: Record<string, { icon: typeof Plus; label: string; color: string }> = {
  node_created: { icon: Plus, label: "新增", color: "text-emerald-600" },
  node_strengthened: { icon: Zap, label: "强化", color: "text-blue-600" },
  relation_created: { icon: GitBranch, label: "关系", color: "text-indigo-600" },
  nodes_merged: { icon: Layers, label: "合并", color: "text-amber-600" },
  structure_review: { icon: RefreshCw, label: "整理", color: "text-purple-600" },
  paper_seed: { icon: Plus, label: "种子", color: "text-teal-600" },
  annotation_signal: { icon: Zap, label: "标注", color: "text-orange-600" },
};

interface Props {
  logs: GrowthLogEntry[];
}

export default function GrowthLog({ logs }: Props) {
  if (!logs || logs.length === 0) {
    return (
      <p className="text-[13px] text-muted-foreground py-4 text-center">
        暂无生长记录
      </p>
    );
  }

  const formatTime = (iso: string) => {
    try {
      const d = new Date(iso);
      const now = new Date();
      const diff = (now.getTime() - d.getTime()) / 1000;
      if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
      if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
      if (diff < 604800) return `${Math.floor(diff / 86400)} 天前`;
      return d.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
    } catch {
      return iso;
    }
  };

  const getDescription = (entry: GrowthLogEntry): string => {
    const d = entry.detail;
    switch (entry.event_type) {
      case "node_created":
        return `发现概念「${d.node || ""}」`;
      case "node_strengthened":
        return `深入了「${d.node || ""}」`;
      case "relation_created":
        return `发现联系：${d.from || ""} 与 ${d.to || ""}`;
      case "nodes_merged":
        return `整合：「${d.remove || ""}」归入「${d.keep || ""}」`;
      case "structure_review":
        return "完成了一次结构整理";
      case "paper_seed": {
        const topic = d.topic || "";
        return topic ? `从论文中识别方向「${topic}」` : `从论文中发现 ${(d.entities as number) || 0} 个概念`;
      }
      case "annotation_signal":
        return `标注强化了 ${d.matched_nodes || 0} 个概念`;
      default:
        return entry.event_type;
    }
  };

  return (
    <div className="space-y-1.5">
      {logs.slice(0, 15).map((entry) => {
        const meta = EVENT_META[entry.event_type] || EVENT_META.node_created;
        const Icon = meta.icon;
        return (
          <div key={entry.id} className="flex items-start gap-2 py-1">
            <Icon className={`w-3.5 h-3.5 shrink-0 mt-0.5 ${meta.color}`} />
            <div className="flex-1 min-w-0">
              <p className="text-[12px] text-foreground truncate">{getDescription(entry)}</p>
              <p className="text-[10px] text-muted-foreground">{formatTime(entry.created_at)}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
