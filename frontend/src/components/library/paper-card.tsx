"use client";

import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { FileText, Trash2, User, Layers, Brain } from "lucide-react";
import type { PaperInfo } from "@/lib/api";

interface PaperCardProps {
  paper: PaperInfo;
  onDelete: (title: string) => void;
}

export function PaperCard({ paper, onDelete }: PaperCardProps) {
  const router = useRouter();

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.2 }}
      className="group relative bg-white border border-border rounded-[16px] p-5 hover:shadow-md hover:border-primary/20 transition-all duration-200"
    >
      {/* Top-right actions */}
      <div className="absolute top-3 right-3 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-all">
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

      {/* Icon */}
      <div className="w-10 h-10 rounded-[12px] bg-primary/10 flex items-center justify-center mb-4">
        <FileText className="w-5 h-5 text-primary" />
      </div>

      {/* Title */}
      <h3 className="text-sm font-medium text-foreground line-clamp-2 leading-snug mb-2 pr-6">
        {paper.title}
      </h3>

      {/* Meta */}
      <div className="space-y-1.5">
        <div className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
          <User className="w-3 h-3 shrink-0" />
          <span className="truncate">{paper.authors}</span>
        </div>
        <div className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
          <Layers className="w-3 h-3 shrink-0" />
          <span>{paper.chunks} chunks</span>
        </div>
      </div>
    </motion.div>
  );
}
