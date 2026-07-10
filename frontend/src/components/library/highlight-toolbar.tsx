"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { MessageSquarePlus, Highlighter, UnderlineIcon, Strikethrough, MessageCircle } from "lucide-react";

type AnnotationType = "highlight" | "underline" | "strikethrough";

const COLORS = [
  { name: "yellow", bg: "#facc15" },
  { name: "green", bg: "#4ade80" },
  { name: "blue", bg: "#60a5fa" },
  { name: "pink", bg: "#f472b6" },
  { name: "purple", bg: "#a78bfa" },
];

const TYPES: { type: AnnotationType; icon: React.ReactNode; label: string }[] = [
  { type: "highlight", icon: <Highlighter className="w-3.5 h-3.5" />, label: "Highlight" },
  { type: "underline", icon: <UnderlineIcon className="w-3.5 h-3.5" />, label: "Underline" },
  { type: "strikethrough", icon: <Strikethrough className="w-3.5 h-3.5" />, label: "Strikethrough" },
];

interface HighlightToolbarProps {
  position: { x: number; y: number };
  onAnnotate: (color: string, type: AnnotationType, withNote: boolean) => void;
  onAskAI: () => void;
}

export function HighlightToolbar({ position, onAnnotate, onAskAI }: HighlightToolbarProps) {
  const [selectedType, setSelectedType] = useState<AnnotationType>("highlight");

  return (
    <motion.div
      initial={{ opacity: 0, y: 4, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 4, scale: 0.95 }}
      transition={{ duration: 0.15 }}
      className="absolute z-50 flex items-center gap-1 bg-white border border-border rounded-[12px] px-2.5 py-1.5 shadow-lg"
      style={{
        left: position.x,
        top: position.y,
        transform: "translate(-50%, -100%) translateY(-8px)",
      }}
      onMouseDown={(e) => e.stopPropagation()}
      onClick={(e) => e.stopPropagation()}
    >
      {/* Type selector */}
      {TYPES.map((t) => (
        <button
          key={t.type}
          onClick={() => setSelectedType(t.type)}
          className={`w-7 h-7 rounded-[8px] flex items-center justify-center transition-all ${
            selectedType === t.type
              ? "bg-primary/10 text-primary"
              : "hover:bg-secondary text-muted-foreground hover:text-foreground"
          }`}
          title={t.label}
          aria-label={t.label}
        >
          {t.icon}
        </button>
      ))}

      {/* Divider */}
      <div className="w-px h-5 bg-border mx-0.5" />

      {/* Color picker */}
      {COLORS.map((c) => (
        <button
          key={c.name}
          onClick={() => onAnnotate(c.name, selectedType, false)}
          className="w-5 h-5 rounded-full border-2 border-transparent hover:border-foreground/20 transition-all hover:scale-110"
          style={{ backgroundColor: c.bg }}
          title={`${TYPES.find(t => t.type === selectedType)?.label} — ${c.name}`}
          aria-label={`${selectedType} ${c.name}`}
        />
      ))}

      {/* Divider */}
      <div className="w-px h-5 bg-border mx-0.5" />

      {/* Add note */}
      <button
        onClick={() => onAnnotate("yellow", selectedType, true)}
        className="w-7 h-7 rounded-[8px] flex items-center justify-center hover:bg-secondary text-muted-foreground hover:text-foreground transition-all"
        title="Add Note"
        aria-label="Add note"
      >
        <MessageSquarePlus className="w-4 h-4" />
      </button>

      {/* Divider */}
      <div className="w-px h-5 bg-border mx-0.5" />

      {/* Ask AI */}
      <button
        onClick={onAskAI}
        className="w-7 h-7 rounded-[8px] flex items-center justify-center hover:bg-primary/10 text-muted-foreground hover:text-primary transition-all"
        title="Ask AI about this"
        aria-label="Ask AI"
      >
        <MessageCircle className="w-4 h-4" />
      </button>
    </motion.div>
  );
}
