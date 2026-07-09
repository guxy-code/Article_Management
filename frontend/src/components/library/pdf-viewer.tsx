"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft,
  ZoomIn,
  ZoomOut,
  Loader2,
  StickyNote,
} from "lucide-react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import {
  getPaperPdfUrl,
  getAnnotations,
  createAnnotation,
  type Annotation,
  type AnnotationRect,
} from "@/lib/api";
import { AnnotationLayer } from "./annotation-layer";
import { HighlightToolbar } from "./highlight-toolbar";
import { AnnotationTooltip } from "./annotation-tooltip";
import { AnnotationPanel } from "./annotation-panel";

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface PdfViewerProps {
  title: string;
  onBack: () => void;
}

// Default PDF page dimensions (will be updated on load)
const DEFAULT_PAGE_WIDTH = 612;
const DEFAULT_PAGE_HEIGHT = 792;

export function PdfViewer({ title, onBack }: PdfViewerProps) {
  const [numPages, setNumPages] = useState(0);
  const [scale, setScale] = useState(1.2);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Annotations
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [panelOpen, setPanelOpen] = useState(false);
  const [activeAnnotationId, setActiveAnnotationId] = useState<string | null>(null);
  const [hoveredAnnotationId, setHoveredAnnotationId] = useState<string | null>(null);
  const [editingAnnotationId, setEditingAnnotationId] = useState<string | null>(null);

  // Selection toolbar
  const [selectionToolbar, setSelectionToolbar] = useState<{
    position: { x: number; y: number };
    text: string;
    page: number;
    rects: AnnotationRect[];
  } | null>(null);

  // Tooltip
  const [tooltipData, setTooltipData] = useState<{
    annotation: Annotation;
    position: { x: number; y: number };
  } | null>(null);

  // Page dimensions
  const [pageDimensions, setPageDimensions] = useState<{ width: number; height: number }>({
    width: DEFAULT_PAGE_WIDTH,
    height: DEFAULT_PAGE_HEIGHT,
  });

  const containerRef = useRef<HTMLDivElement>(null);
  const pdfUrl = getPaperPdfUrl(title);

  // Intercept Ctrl+wheel to zoom PDF instead of browser
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const handleWheel = (e: WheelEvent) => {
      if (!e.ctrlKey) return;
      e.preventDefault();
      const delta = e.deltaY > 0 ? -0.1 : 0.1;
      setScale((s) => Math.min(3, Math.max(0.5, Math.round((s + delta) * 10) / 10)));
    };

    el.addEventListener("wheel", handleWheel, { passive: false });
    return () => {
      el.removeEventListener("wheel", handleWheel);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [containerRef.current]);

  // Load annotations
  const fetchAnnotations = useCallback(async () => {
    try {
      const data = await getAnnotations(title);
      setAnnotations(data.annotations);
    } catch (err) {
      // Ignore AbortError from strict mode double-invoke cleanup
      if (err instanceof TypeError && err.message === "Failed to fetch") return;
      console.error("Failed to load annotations:", err);
    }
  }, [title]);

  useEffect(() => {
    let cancelled = false;
    getAnnotations(title)
      .then((data) => { if (!cancelled) setAnnotations(data.annotations); })
      .catch((err) => { if (!cancelled) console.error("Failed to load annotations:", err); });
    return () => { cancelled = true; };
  }, [title]);

  const onDocumentLoadSuccess = useCallback(({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
    setLoading(false);
  }, []);

  const onPageLoadSuccess = useCallback((page: any) => {
    setPageDimensions({ width: page.originalWidth, height: page.originalHeight });
  }, []);

  const zoomIn = () => setScale((s) => Math.min(3, s + 0.2));
  const zoomOut = () => setScale((s) => Math.max(0.5, s - 0.2));
  const resetZoom = () => setScale(1.2);

  // Handle text selection for creating highlights
  const handleMouseUp = useCallback(() => {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed || !selection.toString().trim()) {
      // Don't dismiss toolbar on empty clicks inside toolbar itself
      return;
    }

    const text = selection.toString().trim();
    if (!text) return;

    const range = selection.getRangeAt(0);
    const rects = range.getClientRects();

    if (rects.length === 0) return;

    // Find which page this selection is in
    const pageElement = range.startContainer.parentElement?.closest(".react-pdf__Page");
    if (!pageElement) return;

    const pageNumber = parseInt(pageElement.getAttribute("data-page-number") || "1");
    const pageRect = pageElement.getBoundingClientRect();
    const containerRect = containerRef.current?.getBoundingClientRect();

    if (!containerRect) return;

    // Convert rects to relative coordinates (0-1 range) and merge same-line rects
    const rawRects = Array.from(rects).filter((r) => r.width > 0 && r.height > 0);

    // Group by line: rects whose vertical centers are within 3px of each other are the same line
    const rows: { left: number; top: number; right: number; bottom: number }[] = [];
    for (const r of rawRects) {
      const centerY = r.top + r.height / 2;
      const existing = rows.find(
        (row) => Math.abs((row.top + (row.bottom - row.top) / 2) - centerY) < 3
      );
      if (existing) {
        existing.left = Math.min(existing.left, r.left);
        existing.right = Math.max(existing.right, r.right);
        existing.top = Math.min(existing.top, r.top);
        existing.bottom = Math.max(existing.bottom, r.bottom);
      } else {
        rows.push({ left: r.left, top: r.top, right: r.right, bottom: r.bottom });
      }
    }

    const pageW = pageDimensions.width * scale;
    const pageH = pageDimensions.height * scale;
    const annotationRects: AnnotationRect[] = rows.map((r) => ({
      x: (r.left - pageRect.left) / pageW,
      y: (r.top - pageRect.top) / pageH,
      width: (r.right - r.left) / pageW,
      height: (r.bottom - r.top) / pageH,
    }));

    // Position toolbar above the selection
    const firstRect = rects[0];
    const toolbarX = firstRect.left + firstRect.width / 2 - containerRect.left;
    const toolbarY = firstRect.top - containerRect.top;

    setSelectionToolbar({
      position: { x: toolbarX, y: toolbarY },
      text,
      page: pageNumber,
      rects: annotationRects,
    });
  }, [pageDimensions, scale]);

  // Create highlight
  const handleCreateHighlight = useCallback(async (color: string, type: "highlight" | "underline" | "strikethrough", withNote: boolean = false) => {
    if (!selectionToolbar) return;

    try {
      const annotation = await createAnnotation({
        paper_title: title,
        page: selectionToolbar.page,
        text: selectionToolbar.text,
        color,
        type,
        rects: selectionToolbar.rects,
      });

      setAnnotations((prev) => [...prev, annotation]);
      setSelectionToolbar(null);
      window.getSelection()?.removeAllRanges();

      if (withNote) {
        setPanelOpen(true);
        setActiveAnnotationId(annotation.id);
        setEditingAnnotationId(annotation.id);
      }
    } catch (err) {
      console.error("Failed to create highlight:", err);
    }
  }, [selectionToolbar, title]);

  // Handle annotation hover for tooltip
  const handleAnnotationHover = useCallback((id: string | null) => {
    setHoveredAnnotationId(id);

    if (id && !panelOpen) {
      const annotation = annotations.find((a) => a.id === id);
      if (annotation && annotation.note) {
        // Find the first rect of this annotation to position tooltip
        const pageEl = containerRef.current?.querySelector(`[data-page-number="${annotation.page}"]`);
        const containerRect = containerRef.current?.getBoundingClientRect();
        if (pageEl && containerRect) {
          const pageRect = pageEl.getBoundingClientRect();
          const rect = annotation.rects[0];
          const x = pageRect.left - containerRect.left + rect.x * pageDimensions.width * scale + (rect.width * pageDimensions.width * scale) / 2;
          const y = pageRect.top - containerRect.top + rect.y * pageDimensions.height * scale;
          setTooltipData({ annotation, position: { x, y } });
        }
      } else {
        setTooltipData(null);
      }
    } else {
      setTooltipData(null);
    }
  }, [annotations, panelOpen, pageDimensions, scale]);

  // Handle annotation click
  const handleAnnotationClick = useCallback((id: string) => {
    setActiveAnnotationId(id);
    setPanelOpen(true);
  }, []);

  // Dismiss toolbar when clicking elsewhere (only if no active selection)
  const handleContainerClick = useCallback((e: React.MouseEvent) => {
    // If the click originated from an annotation highlight, don't interfere
    const target = e.target as HTMLElement;
    if (target.closest("[data-annotation-rect]")) return;

    const selection = window.getSelection();
    if (selectionToolbar && (!selection || selection.isCollapsed)) {
      setSelectionToolbar(null);
    }
  }, [selectionToolbar]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="h-full flex flex-col"
    >
      {/* Header */}
      <div className="px-6 py-4 border-b border-border bg-white flex items-center gap-4">
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors shrink-0"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back</span>
        </button>

        <div className="w-px h-5 bg-border" />

        <h2 className="text-sm font-medium text-foreground truncate flex-1 min-w-0">
          {title}
        </h2>

        <div className="flex items-center gap-1 shrink-0">
          <span className="text-xs text-muted-foreground mr-2 select-none">
            {numPages > 0 ? `${numPages} pages` : ""}
          </span>

          <button
            onClick={zoomOut}
            disabled={scale <= 0.5}
            className="w-8 h-8 rounded-[8px] flex items-center justify-center hover:bg-secondary text-muted-foreground hover:text-foreground disabled:opacity-30 transition-all"
            aria-label="Zoom out"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            onClick={resetZoom}
            className="h-8 px-2 rounded-[8px] flex items-center justify-center hover:bg-secondary text-xs text-muted-foreground hover:text-foreground transition-all min-w-[48px]"
            aria-label="Reset zoom"
          >
            {Math.round(scale * 100)}%
          </button>
          <button
            onClick={zoomIn}
            disabled={scale >= 3}
            className="w-8 h-8 rounded-[8px] flex items-center justify-center hover:bg-secondary text-muted-foreground hover:text-foreground disabled:opacity-30 transition-all"
            aria-label="Zoom in"
          >
            <ZoomIn className="w-4 h-4" />
          </button>

          <div className="w-px h-5 bg-border mx-1.5" />

          {/* Toggle annotation panel */}
          <button
            onClick={() => setPanelOpen(!panelOpen)}
            className={`w-8 h-8 rounded-[8px] flex items-center justify-center transition-all ${
              panelOpen
                ? "bg-primary/10 text-primary"
                : "hover:bg-secondary text-muted-foreground hover:text-foreground"
            }`}
            aria-label="Toggle annotations panel"
            title="Annotations"
          >
            <StickyNote className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Body: PDF + Panel */}
      <div className="flex-1 flex overflow-hidden">
        {/* PDF Content */}
        <div
          ref={containerRef}
          className="flex-1 overflow-auto bg-neutral-50 flex justify-center py-6 relative"
          onMouseUp={handleMouseUp}
          onClick={handleContainerClick}
          onContextMenu={(e) => e.preventDefault()}
        >
          {loading && !error && (
            <div className="flex items-center justify-center h-full">
              <div className="flex flex-col items-center gap-3">
                <Loader2 className="w-8 h-8 text-primary animate-spin" />
                <p className="text-sm text-muted-foreground">Loading PDF...</p>
              </div>
            </div>
          )}

          {error && (
            <div className="flex items-center justify-center h-full">
              <div className="flex flex-col items-center gap-3 text-center max-w-sm">
                <div className="w-12 h-12 rounded-full bg-destructive/10 flex items-center justify-center">
                  <span className="text-destructive text-lg">!</span>
                </div>
                <p className="text-sm text-muted-foreground">{error}</p>
                <button onClick={onBack} className="text-sm text-primary hover:underline">
                  Return to Library
                </button>
              </div>
            </div>
          )}

          <Document
            file={pdfUrl}
            onLoadSuccess={onDocumentLoadSuccess}
            onLoadError={(err) => {
              console.error("PDF load error:", err);
              setError("Failed to load PDF. The file may have been moved or deleted.");
              setLoading(false);
            }}
            loading=""
            className={`flex flex-col items-center gap-4 ${loading || error ? "hidden" : ""}`}
          >
            {numPages > 0 &&
              Array.from({ length: numPages }, (_, index) => (
                <div key={`page_wrapper_${index + 1}`} className="relative">
                  <Page
                    pageNumber={index + 1}
                    scale={scale}
                    className="shadow-lg rounded-sm"
                    loading=""
                    renderAnnotationLayer={false}
                    onLoadSuccess={index === 0 ? onPageLoadSuccess : undefined}
                  />
                  <AnnotationLayer
                    annotations={annotations}
                    pageNumber={index + 1}
                    scale={scale}
                    pageWidth={pageDimensions.width}
                    pageHeight={pageDimensions.height}
                    activeId={activeAnnotationId}
                    hoveredId={hoveredAnnotationId}
                    onHover={handleAnnotationHover}
                    onClick={handleAnnotationClick}
                  />
                </div>
              ))}
          </Document>

          {/* Selection Toolbar */}
          <AnimatePresence>
            {selectionToolbar && (
              <HighlightToolbar
                position={selectionToolbar.position}
                onAnnotate={(color, type, withNote) => handleCreateHighlight(color, type, withNote)}
              />
            )}
          </AnimatePresence>

          {/* Hover Tooltip */}
          <AnimatePresence>
            {tooltipData && (
              <AnnotationTooltip
                annotation={tooltipData.annotation}
                position={tooltipData.position}
              />
            )}
          </AnimatePresence>
        </div>

        {/* Annotation Panel (right sidebar) */}
        <AnimatePresence>
          {panelOpen && (
            <AnnotationPanel
              annotations={annotations}
              activeId={activeAnnotationId}
              hoveredId={hoveredAnnotationId}
              onHover={setHoveredAnnotationId}
              onClick={handleAnnotationClick}
              onClose={() => setPanelOpen(false)}
              onUpdate={fetchAnnotations}
              editingId={editingAnnotationId}
              onEditStart={setEditingAnnotationId}
              onEditEnd={() => setEditingAnnotationId(null)}
            />
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
