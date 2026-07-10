"use client";

import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { FileText, Trash2, Eye, Brain } from "lucide-react";
import type { PaperInfo, PaperStatus } from "@/lib/api";
import { cycleStatus, getStatusConfig } from "@/lib/paper-status";
import { cn } from "@/lib/utils";

interface PaperListItemProps {
  paper: PaperInfo;
  status: PaperStatus;
  onStatusChange?: (title: string, status: PaperStatus) => void;
  onDelete: (title: string) => void;
  onView?: (title: string) => void;
  zebra?: boolean;
}

export function PaperListItem({ paper, status, onStatusChange, onDelete, onView, zebra }: PaperListItemProps) {
  const router = useRouter();
  const statusConfig = getStatusConfig(status);

  const handleStatusClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    const next = cycleStatus(status);
    onStatusChange?.(paper.title, next);
  };

  return (
    <motion.div
      layout
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.12 }}
      className={cn(
        "group flex items-center gap-4 px-4 py-3 border-b border-border/50 border-l-4 hover:bg-primary/5 transition-colors",
        zebra ? "bg-muted/20" : "bg-white",
        statusConfig.border,
        statusConfig.cardOpacity
      )}
    >
      {/* Icon */}
      <div className={cn(
        "w-7 h-7 rounded-[7px] flex items-center justify-center shrink-0 transition-colors",
        status === "read" ? "bg-secondary" : "bg-primary/10"
      )}>
        <FileText className={cn("w-3.5 h-3.5 transition-colors", status === "read" ? "text-muted-foreground" : "text-primary")} />
      </div>

      {/* Title & Authors */}
      <div className="flex-1 min-w-0">
        <p className={cn(
          "text-[13px] line-clamp-2 leading-snug transition-all",
          statusConfig.titleClass || "font-medium text-foreground"
        )}>
          {paper.title}
        </p>
        <div className="text-[11px] text-muted-foreground mt-0.5 truncate">
          {paper.authors}
        </div>
      </div>

      {/* Venue */}
      <div className="w-32 shrink-0 flex items-center">
        <span className="text-[11px] text-muted-foreground truncate">{paper.venue || "—"}</span>
      </div>

      {/* Status */}
      <div className="w-20 shrink-0 flex justify-center">
        <button
          onClick={handleStatusClick}
          className={cn(
            "flex items-center gap-1 h-6 px-2 rounded-full text-[10px] font-medium transition-all hover:scale-105",
            statusConfig.bg, statusConfig.color
          )}
          title="Click to change status"
        >
          <span className={cn("w-1.5 h-1.5 rounded-full", statusConfig.dot)} />
          {statusConfig.label}
        </button>
      </div>

      {/* Chunks */}
      <div className="w-16 shrink-0 text-right">
        <span className="text-[11px] text-muted-foreground tabular-nums">{paper.chunks}</span>
      </div>

      {/* Actions */}
      <div className="w-28 shrink-0 flex items-center justify-center gap-1">
        <button
          onClick={() => onView?.(paper.title)}
          className="w-8 h-8 rounded-[8px] flex items-center justify-center hover:bg-primary/10 text-muted-foreground hover:text-primary transition-all"
          aria-label={`View PDF for ${paper.title}`}
          title="View PDF"
        >
          <Eye className="w-4 h-4" />
        </button>
        <button
          onClick={() => router.push(`/knowledge?paper=${encodeURIComponent(paper.title)}`)}
          className="w-8 h-8 rounded-[8px] flex items-center justify-center hover:bg-primary/10 text-muted-foreground hover:text-primary transition-all"
          aria-label={`View knowledge graph for ${paper.title}`}
          title="Knowledge Graph"
        >
          <Brain className="w-4 h-4" />
        </button>
        <button
          onClick={() => onDelete(paper.title)}
          className="w-8 h-8 rounded-[8px] flex items-center justify-center hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-all"
          aria-label={`Delete ${paper.title}`}
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    </motion.div>
  );
}
