"use client";

import { useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  ZoomIn,
  ZoomOut,
  Loader2,
} from "lucide-react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { getPaperPdfUrl } from "@/lib/api";

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface PdfViewerProps {
  title: string;
  onBack: () => void;
}

export function PdfViewer({ title, onBack }: PdfViewerProps) {
  const [numPages, setNumPages] = useState(0);
  const [scale, setScale] = useState(1.2);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const pdfUrl = getPaperPdfUrl(title);

  const onDocumentLoadSuccess = useCallback(({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
    setLoading(false);
  }, []);

  const zoomIn = () => setScale((s) => Math.min(3, s + 0.2));
  const zoomOut = () => setScale((s) => Math.max(0.5, s - 0.2));
  const resetZoom = () => setScale(1.2);

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
        {/* Back button */}
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors shrink-0"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back</span>
        </button>

        {/* Divider */}
        <div className="w-px h-5 bg-border" />

        {/* Title */}
        <h2 className="text-sm font-medium text-foreground truncate flex-1 min-w-0">
          {title}
        </h2>

        {/* Controls */}
        <div className="flex items-center gap-1 shrink-0">
          {/* Page count */}
          <span className="text-xs text-muted-foreground mr-2 select-none">
            {numPages > 0 ? `${numPages} pages` : ""}
          </span>

          {/* Zoom */}
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
            title="Reset zoom"
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
        </div>
      </div>

      {/* PDF Content - scrollable, all pages rendered */}
      <div className="flex-1 overflow-auto bg-neutral-50 flex justify-center py-6">
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
              <button
                onClick={onBack}
                className="text-sm text-primary hover:underline"
              >
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
              <Page
                key={`page_${index + 1}`}
                pageNumber={index + 1}
                scale={scale}
                className="shadow-lg rounded-sm"
                loading=""
              />
            ))}
        </Document>
      </div>
    </motion.div>
  );
}
