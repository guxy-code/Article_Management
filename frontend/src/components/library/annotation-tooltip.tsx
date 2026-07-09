"use client";

import { motion } from "framer-motion";
import type { Annotation } from "@/lib/api";

interface AnnotationTooltipProps {
  annotation: Annotation;
  position: { x: number; y: number };
}

export function AnnotationTooltip({ annotation, position }: AnnotationTooltipProps) {
  if (!annotation.note) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 4 }}
      transition={{ duration: 0.12 }}
      className="absolute z-50 max-w-[280px] bg-white border border-border rounded-[10px] px-3 py-2 shadow-lg pointer-events-none"
      style={{
        left: position.x,
        top: position.y,
        transform: "translate(-50%, -100%) translateY(-10px)",
      }}
    >
      <p className="text-xs text-muted-foreground line-clamp-3">{annotation.note}</p>
      <div
        className="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-full w-0 h-0 border-l-[6px] border-r-[6px] border-t-[6px] border-transparent border-t-white"
      />
    </motion.div>
  );
}
