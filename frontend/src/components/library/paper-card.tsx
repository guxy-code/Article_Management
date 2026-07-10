"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { FileText, Trash2, User, Layers, Brain, Check, Eye, BookMarked } from "lucide-react";
import type { PaperInfo } from "@/lib/api";
import { getPaperStatus, cyclePaperStatus, getStatusConfig } from "@/lib/paper-status";
import { cn } from "@/lib/utils";

interface PaperCardProps {
  paper: PaperInfo;
  selected?: boolean;
  onSelect?: (title: string) => void;
  onDelete: (title: string) => void;
  onView?: (title: string) => void;
}

export function PaperCard({ paper, selected, onSelect, onDelete, onView }: PaperCardProps) {
  const router = useRouter();
  const [status, setStatus] = useState(getPaperStatus(paper.title));
  const statusConfig = getStatusConfig(status);

  const handleStatusClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    const next = cyclePaperStatus(paper.title);
    setStatus(next);
  };

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.2 }}
      className={cn(
        "group relative bg-white border border-l-4 rounded-[16px] p-5 card-shadow hover:card-shadow-hover transition-all duration-200",
        statusConfig.border,
        statusConfig.cardOpacity,
        selected
          ? "border-t-primary/50 border-r-primary/50 border-b-primary/50 bg-primary/5"
          : "border-t-border border-r-border border-b-border hover:border-t-primary/20 hover:border-r-primary/20 hover:border-b-primary/20"
      )}
    >
      {/* Checkbox */}
      <button
        onClick={() => onSelect?.(paper.title)}
        className={cn(
          "absolute top-3 left-3 w-5 h-5 rounded-[6px] border-2 flex items-center justify-center transition-all z-10",
          selected
            ? "bg-primary border-primary"
            : "border-border opacity-0 group-hover:opacity-100 hover:border-primary/50"
        )}
      >
        {selected && <Check className="w-3 h-3 text-white" />}
      </button>

      {/* Top-right: actions only */}
      <div className="absolute top-3 right-3 flex items-center gap-1 z-10">
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-all">
          <button
            onClick={() => onView?.(paper.title)}
            className="w-7 h-7 rounded-[8px] flex items-center justify-center hover:bg-primary/10 text-muted-foreground hover:text-primary transition-all"
            aria-label={`View PDF for ${paper.title}`}
            title="View PDF"
          >
            <Eye className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => router.push(`/knowledge?paper=${encodeURIComponent(paper.title)}`)}
            className="w-7 h-7 rounded-[8px] flex items-center justify-center hover:bg-primary/10 text-muted-foreground hover:text-primary transition-all"
            aria-label={`View knowledge graph for ${paper.title}`}
            title="View Knowledge Graph"
          >
            <Brain className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => onDelete(paper.title)}
            className="w-7 h-7 rounded-[8px] flex items-center justify-center hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-all"
            aria-label={`Delete ${paper.title}`}
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Icon */}
      <div className={cn(
        "w-10 h-10 rounded-[12px] flex items-center justify-center mb-4 transition-colors",
        status === "read" ? "bg-secondary" : "bg-primary/10"
      )}>
        <FileText className={cn("w-5 h-5 transition-colors", status === "read" ? "text-muted-foreground" : "text-primary")} />
      </div>

      {/* Title */}
      <h3 className={cn(
        "text-sm line-clamp-2 leading-snug mb-2 pr-6 transition-all",
        statusConfig.titleClass || "font-medium text-foreground"
      )}>
        {paper.title}
      </h3>

      {/* Meta */}
      <div className="space-y-1.5">
        <div className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
          <User className="w-3 h-3 shrink-0" />
          <span className="truncate">{paper.authors}</span>
        </div>
        {paper.venue && (
          <div className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
            <BookMarked className="w-3 h-3 shrink-0" />
            <span className="truncate">{paper.venue}</span>
          </div>
        )}
        {/* Bottom row: chunks (left) + status badge (right) */}
        <div className="flex items-center justify-between pt-1">
          <div className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
            <Layers className="w-3 h-3 shrink-0" />
            <span>{paper.chunks} chunks</span>
          </div>
          <button
            onClick={handleStatusClick}
            className={cn(
              "flex items-center gap-1.5 h-6 px-2 rounded-full text-[10px] font-medium transition-all hover:scale-105",
              statusConfig.bg, statusConfig.color
            )}
            title="Click to change status"
          >
            <span className={cn("w-1.5 h-1.5 rounded-full", statusConfig.dot)} />
            {statusConfig.label}
          </button>
        </div>
      </div>
    </motion.div>
  );
}
