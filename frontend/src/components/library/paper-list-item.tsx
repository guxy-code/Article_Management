"use client";

import { motion } from "framer-motion";
import { FileText, Trash2, Eye } from "lucide-react";
import type { PaperInfo } from "@/lib/api";

interface PaperListItemProps {
  paper: PaperInfo;
  onDelete: (title: string) => void;
  onView?: (title: string) => void;
}

export function PaperListItem({ paper, onDelete, onView }: PaperListItemProps) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -8 }}
      transition={{ duration: 0.15 }}
      className="group flex items-center gap-4 px-4 py-3 rounded-[12px] hover:bg-secondary/80 transition-colors"
    >
      {/* Icon */}
      <div className="w-8 h-8 rounded-[8px] bg-primary/10 flex items-center justify-center shrink-0">
        <FileText className="w-4 h-4 text-primary" />
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-foreground truncate">
          {paper.title}
        </p>
        <p className="text-[12px] text-muted-foreground truncate">
          {paper.authors}
        </p>
      </div>

      {/* Chunks Badge */}
      <span className="text-[11px] text-muted-foreground bg-secondary px-2 py-0.5 rounded-full shrink-0">
        {paper.chunks} chunks
      </span>

      {/* View PDF */}
      <button
        onClick={() => onView?.(paper.title)}
        className="w-7 h-7 rounded-[8px] flex items-center justify-center opacity-0 group-hover:opacity-100 hover:bg-primary/10 text-muted-foreground hover:text-primary transition-all shrink-0"
        aria-label={`View PDF for ${paper.title}`}
        title="View PDF"
      >
        <Eye className="w-3.5 h-3.5" />
      </button>

      {/* Delete */}
      <button
        onClick={() => onDelete(paper.title)}
        className="w-7 h-7 rounded-[8px] flex items-center justify-center opacity-0 group-hover:opacity-100 hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-all shrink-0"
        aria-label={`Delete ${paper.title}`}
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>
    </motion.div>
  );
}
