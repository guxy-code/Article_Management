"use client";

import { useState } from "react";
import { X, Trash2, Edit3, Check } from "lucide-react";
import type { InterestGraphNode } from "@/lib/api";
import { deleteInterestGraphNode, patchInterestGraphNode } from "@/lib/api";

interface Props {
  node: InterestGraphNode;
  children?: { name: string; type: string; description: string }[];
  ancestors?: { name: string }[];
  onClose: () => void;
  onDeleted: (name: string) => void;
  onUpdated: () => void;
}

export default function NodeDetailPanel({ node, children, ancestors, onClose, onDeleted, onUpdated }: Props) {
  const [editing, setEditing] = useState(false);
  const [editDesc, setEditDesc] = useState(node.description || "");

  const handleDelete = async () => {
    try {
      await deleteInterestGraphNode(node.name);
      onDeleted(node.name);
    } catch {
      // 静默
    }
  };

  const handleSave = async () => {
    try {
      await patchInterestGraphNode(node.name, { description: editDesc });
      setEditing(false);
      onUpdated();
    } catch {
      // 静默
    }
  };

  const TYPE_LABELS: Record<string, string> = {
    Field: "研究方向",
    Topic: "研究问题",
    Entity: "方法/概念",
  };

  // Engagement level
  const engagementLabel = (hitCount: number) => {
    if (hitCount >= 5) return { text: "深入了解", color: "#059669" };
    if (hitCount >= 2) return { text: "持续关注", color: "#2563EB" };
    return { text: "初步接触", color: "#9CA3AF" };
  };
  const engagement = engagementLabel(node.hit_count || 0);

  // Relative time
  const lastActive = (() => {
    if (!node.last_seen) return "";
    const days = Math.floor((Date.now() - new Date(node.last_seen).getTime()) / 86400000);
    if (days === 0) return "今天";
    if (days === 1) return "昨天";
    if (days < 7) return `${days} 天前`;
    if (days < 30) return `${Math.floor(days / 7)} 周前`;
    return `${Math.floor(days / 30)} 个月前`;
  })();

  return (
    <div className="absolute top-0 right-0 w-72 h-full bg-white border-l border-border shadow-lg z-20 overflow-auto">
      <div className="p-4">
        {/* 头部 */}
        <div className="flex items-start justify-between mb-3">
          <div>
            <h3 className="text-sm font-semibold">{node.name}</h3>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              {TYPE_LABELS[node.type] || node.type}
              {ancestors && ancestors.length > 0 && ` · ${ancestors[0].name}`}
            </p>
          </div>
          <button onClick={onClose} className="p-1 rounded-[6px] hover:bg-secondary">
            <X className="w-4 h-4 text-muted-foreground" />
          </button>
        </div>

        {/* 描述 */}
        <div className="mb-4">
          {/* 关注程度 & 最近活跃 */}
          <div className="flex items-center gap-3 mb-3 pb-2 border-b border-border">
            <span className="text-[11px] font-medium" style={{ color: engagement.color }}>
              {engagement.text}
            </span>
            {lastActive && (
              <span className="text-[10px] text-muted-foreground">最近提及: {lastActive}</span>
            )}
          </div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-[11px] text-muted-foreground font-medium">描述</span>
            {!editing && (
              <button onClick={() => setEditing(true)} className="p-0.5 rounded hover:bg-secondary">
                <Edit3 className="w-3 h-3 text-muted-foreground" />
              </button>
            )}
          </div>
          {editing ? (
            <div className="flex gap-1.5">
              <textarea
                value={editDesc}
                onChange={(e) => setEditDesc(e.target.value)}
                className="flex-1 text-[12px] border border-border rounded-[6px] px-2 py-1.5 resize-none"
                rows={3}
              />
              <button onClick={handleSave} className="p-1 rounded-[6px] bg-primary text-white hover:bg-primary/90 self-end">
                <Check className="w-3 h-3" />
              </button>
            </div>
          ) : (
            <p className="text-[12px] text-foreground leading-relaxed">
              {node.description || "暂无描述"}
            </p>
          )}
        </div>

        {/* 子节点 */}
        {children && children.length > 0 && (
          <div className="mb-4">
            <span className="text-[11px] text-muted-foreground font-medium">包含的概念</span>
            <div className="mt-1.5 space-y-1">
              {children.map((c) => (
                <div key={c.name} className="text-[12px] px-2 py-1 rounded-[6px] bg-secondary/50">
                  <span className="font-medium">{c.name}</span>
                  {c.description && (
                    <span className="text-muted-foreground ml-1">— {c.description}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 删除 */}
        <div className="pt-3 border-t border-border">
          <button
            onClick={handleDelete}
            className="flex items-center gap-1.5 text-[12px] text-destructive hover:text-destructive/80 transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
            删除此节点
          </button>
          <p className="text-[10px] text-muted-foreground mt-1">删除后 30 天内可恢复</p>
        </div>
      </div>
    </div>
  );
}
