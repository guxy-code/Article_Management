"use client";

import type { Annotation, AnnotationRect } from "@/lib/api";

const SOLID_COLORS: Record<string, string> = {
  yellow: "#facc15",
  green: "#4ade80",
  blue: "#60a5fa",
  pink: "#f472b6",
  purple: "#a78bfa",
};

const HIGHLIGHT_ALPHA = 0.35;
const HIGHLIGHT_ALPHA_ACTIVE = 0.6;

interface AnnotationLayerProps {
  annotations: Annotation[];
  pageNumber: number;
  scale: number;
  pageWidth: number;
  pageHeight: number;
  activeId: string | null;
  hoveredId: string | null;
  onHover: (id: string | null) => void;
  onClick: (id: string) => void;
}

function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function getRectStyle(
  annotation: Annotation,
  rect: AnnotationRect,
  pageWidth: number,
  pageHeight: number,
  scale: number,
  isActive: boolean,
  isHovered: boolean
): React.CSSProperties {
  const color = SOLID_COLORS[annotation.color] || SOLID_COLORS.yellow;
  const alpha = isActive || isHovered ? HIGHLIGHT_ALPHA_ACTIVE : HIGHLIGHT_ALPHA;
  const base: React.CSSProperties = {
    position: "absolute",
    left: rect.x * pageWidth * scale,
    top: rect.y * pageHeight * scale,
    width: rect.width * pageWidth * scale,
    height: rect.height * pageHeight * scale,
    zIndex: 11,
    transition: "all 150ms",
  };

  const type = annotation.type ?? "highlight";

  if (type === "highlight") {
    return {
      ...base,
      backgroundColor: hexToRgba(color, alpha),
      borderRadius: 2,
      boxShadow: isActive ? `0 0 0 2px ${hexToRgba(color, 0.7)}` : "none",
    };
  }

  if (type === "underline") {
    // Thin line at the bottom of the rect
    const lineHeight = Math.max(2, 2 * scale);
    return {
      ...base,
      top: rect.y * pageHeight * scale + rect.height * pageHeight * scale - lineHeight,
      height: lineHeight,
      backgroundColor: hexToRgba(color, isActive || isHovered ? 1 : 0.85),
      borderRadius: 1,
      boxShadow: isActive ? `0 0 0 1px ${hexToRgba(color, 0.4)}` : "none",
    };
  }

  if (type === "strikethrough") {
    // Thin line at the vertical center of the rect
    const lineHeight = Math.max(2, 2 * scale);
    const rectHeightPx = rect.height * pageHeight * scale;
    return {
      ...base,
      top: rect.y * pageHeight * scale + rectHeightPx / 2 - lineHeight / 2,
      height: lineHeight,
      backgroundColor: hexToRgba(color, isActive || isHovered ? 1 : 0.85),
      borderRadius: 1,
      boxShadow: isActive ? `0 0 0 1px ${hexToRgba(color, 0.4)}` : "none",
    };
  }

  return base;
}

export function AnnotationLayer({
  annotations,
  pageNumber,
  scale,
  pageWidth,
  pageHeight,
  activeId,
  hoveredId,
  onHover,
  onClick,
}: AnnotationLayerProps) {
  const pageAnnotations = annotations.filter((a) => a.page === pageNumber);

  if (pageAnnotations.length === 0) return null;

  return (
    <div
      className="absolute top-0 left-0 pointer-events-none"
      style={{ width: pageWidth * scale, height: pageHeight * scale, zIndex: 10 }}
    >
      {pageAnnotations.map((annotation) =>
        annotation.rects.map((rect, i) => {
          const isActive = activeId === annotation.id;
          const isHovered = hoveredId === annotation.id;
          const style = getRectStyle(annotation, rect, pageWidth, pageHeight, scale, isActive, isHovered);

          return (
            <div
              key={`${annotation.id}-${i}`}
              data-annotation-rect="true"
              className="absolute pointer-events-auto cursor-pointer"
              style={style}
              onMouseEnter={() => onHover(annotation.id)}
              onMouseLeave={() => onHover(null)}
              onClick={(e) => {
                e.stopPropagation();
                onClick(annotation.id);
              }}
            />
          );
        })
      )}
    </div>
  );
}
