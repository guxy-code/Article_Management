"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Plus, LayoutGrid, List, Library as LibraryIcon, Loader2 } from "lucide-react";
import { listPapers, deletePaper, type PaperInfo } from "@/lib/api";
import { PaperCard } from "@/components/library/paper-card";
import { PaperListItem } from "@/components/library/paper-list-item";
import { UploadDialog } from "@/components/library/upload-dialog";
import { cn } from "@/lib/utils";

type ViewMode = "grid" | "list";

export default function LibraryPage() {
  const [papers, setPapers] = useState<PaperInfo[]>([]);
  const [totalChunks, setTotalChunks] = useState(0);
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [isLoading, setIsLoading] = useState(true);
  const [uploadOpen, setUploadOpen] = useState(false);

  const fetchPapers = useCallback(async () => {
    try {
      const data = await listPapers();
      setPapers(data.papers);
      setTotalChunks(data.total_chunks);
    } catch (err) {
      console.error("Failed to fetch papers:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPapers();
  }, [fetchPapers]);

  const handleDelete = async (title: string) => {
    if (!confirm(`确定删除《${title}》？此操作不可撤销。`)) return;

    try {
      await deletePaper(title);
      fetchPapers();
    } catch (err) {
      alert(err instanceof Error ? err.message : "删除失败");
    }
  };

  const handleUploadSuccess = () => {
    fetchPapers();
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-6 py-5 border-b border-border bg-white">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold tracking-tight">Library</h1>
            <p className="text-[13px] text-muted-foreground mt-0.5">
              {papers.length} papers · {totalChunks} chunks indexed
            </p>
          </div>

          <div className="flex items-center gap-2">
            {/* View Mode Toggle */}
            <div className="flex items-center bg-secondary rounded-[10px] p-0.5">
              <button
                onClick={() => setViewMode("grid")}
                className={cn(
                  "w-8 h-8 rounded-[8px] flex items-center justify-center transition-all",
                  viewMode === "grid"
                    ? "bg-white shadow-sm text-foreground"
                    : "text-muted-foreground hover:text-foreground"
                )}
                aria-label="Grid view"
              >
                <LayoutGrid className="w-4 h-4" />
              </button>
              <button
                onClick={() => setViewMode("list")}
                className={cn(
                  "w-8 h-8 rounded-[8px] flex items-center justify-center transition-all",
                  viewMode === "list"
                    ? "bg-white shadow-sm text-foreground"
                    : "text-muted-foreground hover:text-foreground"
                )}
                aria-label="List view"
              >
                <List className="w-4 h-4" />
              </button>
            </div>

            {/* Upload Button */}
            <button
              onClick={() => setUploadOpen(true)}
              className="h-9 px-4 rounded-[10px] bg-primary text-white text-sm font-medium hover:bg-primary/90 transition-colors flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Upload
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        {isLoading ? (
          <LoadingSkeleton viewMode={viewMode} />
        ) : papers.length === 0 ? (
          <EmptyState onUpload={() => setUploadOpen(true)} />
        ) : viewMode === "grid" ? (
          <motion.div
            layout
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
          >
            <AnimatePresence>
              {papers.map((paper) => (
                <PaperCard
                  key={paper.title}
                  paper={paper}
                  onDelete={handleDelete}
                />
              ))}
            </AnimatePresence>
          </motion.div>
        ) : (
          <div className="space-y-1 max-w-3xl">
            <AnimatePresence>
              {papers.map((paper) => (
                <PaperListItem
                  key={paper.title}
                  paper={paper}
                  onDelete={handleDelete}
                />
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>

      {/* Upload Dialog */}
      <UploadDialog
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onSuccess={handleUploadSuccess}
      />
    </div>
  );
}

// --- Sub-components ---

function EmptyState({ onUpload }: { onUpload: () => void }) {
  return (
    <div className="h-full flex flex-col items-center justify-center">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.3 }}
        className="text-center max-w-sm"
      >
        <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-6">
          <LibraryIcon className="w-8 h-8 text-primary" />
        </div>
        <h2 className="text-lg font-semibold mb-2">No papers yet</h2>
        <p className="text-sm text-muted-foreground mb-6">
          Upload your first PDF paper to start building your knowledge base.
        </p>
        <button
          onClick={onUpload}
          className="h-10 px-5 rounded-[10px] bg-primary text-white text-sm font-medium hover:bg-primary/90 transition-colors inline-flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Upload Paper
        </button>
      </motion.div>
    </div>
  );
}

function LoadingSkeleton({ viewMode }: { viewMode: ViewMode }) {
  if (viewMode === "grid") {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="rounded-[16px] border border-border p-5 animate-pulse"
          >
            <div className="w-10 h-10 rounded-[12px] bg-secondary mb-4" />
            <div className="h-4 bg-secondary rounded w-3/4 mb-2" />
            <div className="h-3 bg-secondary rounded w-1/2" />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-2 max-w-3xl">
      {Array.from({ length: 4 }).map((_, i) => (
        <div
          key={i}
          className="flex items-center gap-4 px-4 py-3 rounded-[12px] animate-pulse"
        >
          <div className="w-8 h-8 rounded-[8px] bg-secondary" />
          <div className="flex-1">
            <div className="h-4 bg-secondary rounded w-2/3 mb-1" />
            <div className="h-3 bg-secondary rounded w-1/3" />
          </div>
        </div>
      ))}
    </div>
  );
}
