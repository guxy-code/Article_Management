"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { X, Trash2, MessageSquare, Edit3, Check } from "lucide-react";
import type { Annotation } from "@/lib/api";
import { updateAnnotation, deleteAnnotation } from "@/lib/api";

const COLOR_DOT: Record<string, string> = {
  yellow: "#facc15",
  green: "#4ade80",
  blue: "#60a5fa",
  pink: "#f472b6",
  purple: "#a78bfa",
};

interface AnnotationPanelProps {
  annotations: Annotation[];
  activeId: string | null;
  hoveredId: string | null;
  onHover: (id: string | null) => void;
  onClick: (id: string) => void;
  onClose: () => void;
  onUpdate: () => void;
  editingId: string | null;
  onEditStart: (id: string) => void;
  onEditEnd: () => void;
}

export function AnnotationPanel({
  annotations,
  activeId,
  hoveredId,
  onHover,
  onClick,
  onClose,
  onUpdate,
  editingId,
  onEditStart,
  onEditEnd,
}: AnnotationPanelProps) {
  return (
    <motion.div
      initial={{ width: 0, opacity: 0 }}
      animate={{ width: 320, opacity: 1 }}
      exit={{ width: 0, opacity: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="h-full border-l border-border bg-white flex flex-col overflow-hidden shrink-0"
    >
      {/* Panel Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <h3 className="text-sm font-medium text-foreground">Annotations</h3>
        <button
          onClick={onClose}
          className="w-7 h-7 rounded-[8px] flex items-center justify-center hover:bg-secondary text-muted-foreground hover:text-foreground transition-all"
          aria-label="Close panel"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Annotation List */}
      <div className="flex-1 overflow-auto p-3 space-y-2">
        {annotations.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <MessageSquare className="w-8 h-8 text-muted-foreground/40 mb-2" />
            <p className="text-xs text-muted-foreground">No annotations yet</p>
            <p className="text-[11px] text-muted-foreground mt-1">Select text in the PDF to highlight</p>
          </div>
        ) : (
          annotations.map((annotation) => (
            <AnnotationCard
              key={annotation.id}
              annotation={annotation}
              isActive={activeId === annotation.id}
              isHovered={hoveredId === annotation.id}
              isEditing={editingId === annotation.id}
              onHover={onHover}
              onClick={onClick}
              onUpdate={onUpdate}
              onEditStart={onEditStart}
              onEditEnd={onEditEnd}
            />
          ))
        )}
      </div>
    </motion.div>
  );
}

// --- Single Annotation Card ---

function AnnotationCard({
  annotation,
  isActive,
  isHovered,
  isEditing,
  onHover,
  onClick,
  onUpdate,
  onEditStart,
  onEditEnd,
}: {
  annotation: Annotation;
  isActive: boolean;
  isHovered: boolean;
  isEditing: boolean;
  onHover: (id: string | null) => void;
  onClick: (id: string) => void;
  onUpdate: () => void;
  onEditStart: (id: string) => void;
  onEditEnd: () => void;
}) {
  const [noteText, setNoteText] = useState(annotation.note);
  const [saving, setSaving] = useState(false);

  const handleSaveNote = async () => {
    setSaving(true);
    try {
      await updateAnnotation(annotation.id, { note: noteText });
      onUpdate();
      onEditEnd();
    } catch (err) {
      console.error("Failed to save note:", err);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    try {
      await deleteAnnotation(annotation.id);
      onUpdate();
    } catch (err) {
      console.error("Failed to delete:", err);
    }
  };

  return (
    <div
      className={`group relative rounded-[10px] border p-3 transition-all duration-150 cursor-pointer ${
        isActive
          ? "border-primary/40 bg-primary/5 shadow-sm"
          : isHovered
          ? "border-primary/20 bg-secondary/50"
          : "border-border hover:border-primary/20 hover:bg-secondary/30"
      }`}
      onMouseEnter={() => onHover(annotation.id)}
      onMouseLeave={() => onHover(null)}
      onClick={() => onClick(annotation.id)}
    >
      {/* Color dot + page */}
      <div className="flex items-center gap-2 mb-1.5">
        <div
          className="w-3 h-3 rounded-full shrink-0"
          style={{ backgroundColor: COLOR_DOT[annotation.color] || COLOR_DOT.yellow }}
        />
        <span className="text-[11px] text-muted-foreground">Page {annotation.page}</span>

        {/* Actions (visible on hover) */}
        <div className="ml-auto flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onEditStart(annotation.id);
            }}
            className="w-6 h-6 rounded-[6px] flex items-center justify-center hover:bg-secondary text-muted-foreground hover:text-foreground transition-all"
            aria-label="Edit note"
          >
            <Edit3 className="w-3 h-3" />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleDelete();
            }}
            className="w-6 h-6 rounded-[6px] flex items-center justify-center hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-all"
            aria-label="Delete annotation"
          >
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
      </div>

      {/* Highlighted text */}
      <p className="text-xs text-foreground/80 line-clamp-2 leading-relaxed">
        &ldquo;{annotation.text}&rdquo;
      </p>

      {/* Note */}
      {isEditing ? (
        <div className="mt-2" onClick={(e) => e.stopPropagation()}>
          <textarea
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            placeholder="Add your note..."
            className="w-full text-xs border border-border rounded-[8px] px-2.5 py-2 resize-none focus:outline-none focus:ring-1 focus:ring-primary/40 min-h-[60px]"
            autoFocus
          />
          <div className="flex items-center gap-1.5 mt-1.5">
            <button
              onClick={handleSaveNote}
              disabled={saving}
              className="h-6 px-2.5 rounded-[6px] bg-primary text-white text-[11px] font-medium hover:bg-primary/90 transition-colors flex items-center gap-1 disabled:opacity-50"
            >
              <Check className="w-3 h-3" />
              Save
            </button>
            <button
              onClick={() => {
                setNoteText(annotation.note);
                onEditEnd();
              }}
              className="h-6 px-2.5 rounded-[6px] border border-border text-[11px] hover:bg-secondary transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : annotation.note ? (
        <p className="mt-1.5 text-[11px] text-muted-foreground italic line-clamp-2">
          {annotation.note}
        </p>
      ) : null}
    </div>
  );
}
