"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import dynamic from "next/dynamic";
import { motion, AnimatePresence } from "framer-motion";
import { Plus, LayoutGrid, List, Library as LibraryIcon, Brain, X, ChevronLeft, ChevronRight } from "lucide-react";
import { listPapers, deletePaper, getAllPaperStatuses, updatePaperStatus, type PaperInfo, type PaperStatus } from "@/lib/api";
import { PaperCard } from "@/components/library/paper-card";
import { PaperListItem } from "@/components/library/paper-list-item";
import { UploadDialog } from "@/components/library/upload-dialog";
import { cn } from "@/lib/utils";

// Dynamic import to avoid SSR issues with react-pdf (requires browser APIs)
const PdfViewer = dynamic(
  () => import("@/components/library/pdf-viewer").then((mod) => mod.PdfViewer),
  { ssr: false }
);

type ViewMode = "grid" | "list";

function LibraryContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [papers, setPapers] = useState<PaperInfo[]>([]);
  const [totalChunks, setTotalChunks] = useState(0);
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [isLoading, setIsLoading] = useState(true);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [selectedPapers, setSelectedPapers] = useState<Set<string>>(new Set());
  const [statusMap, setStatusMap] = useState<Record<string, PaperStatus>>({});
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  // Derive viewingPaper from URL so it survives navigation
  const viewingPaper = searchParams.get("paper");

  const fetchPapers = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await listPapers();
      setPapers(data.papers);
      setTotalChunks(data.total_chunks);
      // 批量加载阅读状态
      const statusData = await getAllPaperStatuses().catch(() => ({ statuses: {} }));
      setStatusMap(statusData.statuses || {});
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
      setSelectedPapers((prev) => {
        const next = new Set(prev);
        next.delete(title);
        return next;
      });
      fetchPapers();
    } catch (err) {
      alert(err instanceof Error ? err.message : "删除失败");
    }
  };

  const handleUploadSuccess = () => {
    fetchPapers();
  };

  const handleStatusChange = async (title: string, newStatus: PaperStatus) => {
    // 乐观更新：先更新 UI
    setStatusMap((prev) => ({ ...prev, [title]: newStatus }));
    // 再异步调 API
    try {
      await updatePaperStatus(title, newStatus);
    } catch (err) {
      console.error("Failed to update paper status:", err);
      // 失败时回滚
      setStatusMap((prev) => ({ ...prev, [title]: "unread" }));
    }
  };

  const handleSelect = (title: string) => {
    setSelectedPapers((prev) => {
      const next = new Set(prev);
      if (next.has(title)) {
        next.delete(title);
      } else {
        next.add(title);
      }
      return next;
    });
  };

  const handleViewSelectedGraph = () => {
    const titles = Array.from(selectedPapers);
    router.push(`/knowledge?papers=${encodeURIComponent(titles.join("||"))}`);
  };

  const openPaper = (title: string) => {
    router.push(`/library?paper=${encodeURIComponent(title)}`);
  };

  const closePaper = () => {
    router.push("/library");
  };

  // If viewing a PDF, show the inline viewer instead of the library list
  if (viewingPaper) {
    return (
      <div className="h-full flex flex-col">
        <PdfViewer title={viewingPaper} onBack={closePaper} />
      </div>
    );
  }

  // Pagination
  const totalPages = Math.ceil(papers.length / pageSize);
  const startIndex = (currentPage - 1) * pageSize;
  const endIndex = Math.min(startIndex + pageSize, papers.length);
  const paginatedPapers = papers.slice(startIndex, endIndex);

  // Reset page when papers change
  useEffect(() => {
    setCurrentPage(1);
  }, [papers.length, pageSize]);

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-5 py-3 border-b border-border bg-white shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold tracking-tight">Library</h1>
            <p className="text-[12px] text-muted-foreground mt-0.5">
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
      <div className="flex-1 overflow-auto p-4">
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
                  status={statusMap[paper.title] || "unread"}
                  onStatusChange={handleStatusChange}
                  selected={selectedPapers.has(paper.title)}
                  onSelect={handleSelect}
                  onDelete={handleDelete}
                  onView={(title) => openPaper(title)}
                />
              ))}
            </AnimatePresence>
          </motion.div>
        ) : (
          <div className="border border-border rounded-[14px] overflow-hidden card-shadow">
            {/* Sticky Table Header */}
            <div className="sticky top-0 z-10 flex items-center gap-4 px-4 py-2 bg-secondary/90 backdrop-blur-sm border-b border-border text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
              <div className="w-7 shrink-0" />
              <div className="flex-1 min-w-0">Title & Authors</div>
              <div className="w-32 shrink-0 truncate">Venue</div>
              <div className="w-20 text-center shrink-0">Status</div>
              <div className="w-16 text-right shrink-0">Chunks</div>
              <div className="w-28 text-center shrink-0">Actions</div>
            </div>
            {/* Table Rows */}
            <AnimatePresence>
              {paginatedPapers.map((paper, i) => (
                <PaperListItem
                  key={paper.title}
                  paper={paper}
                  status={statusMap[paper.title] || "unread"}
                  onStatusChange={handleStatusChange}
                  onDelete={handleDelete}
                  onView={(title) => openPaper(title)}
                  zebra={i % 2 === 1}
                />
              ))}
            </AnimatePresence>
            {/* Pagination Footer */}
            <div className="flex items-center justify-between px-4 py-2.5 border-t border-border bg-white">
              <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                <span>Rows per page:</span>
                <select
                  value={pageSize}
                  onChange={(e) => setPageSize(Number(e.target.value))}
                  className="h-7 px-1.5 rounded-[6px] border border-border text-[11px] text-foreground bg-white focus:outline-none focus:ring-2 focus:ring-primary/20 cursor-pointer"
                >
                  <option value={10}>10</option>
                  <option value={20}>20</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </select>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-[11px] text-muted-foreground tabular-nums">
                  {startIndex + 1}-{endIndex} of {papers.length}
                </span>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                    disabled={currentPage === 1}
                    className="w-6 h-6 rounded-[6px] flex items-center justify-center text-muted-foreground hover:bg-secondary disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                    aria-label="Previous page"
                  >
                    <ChevronLeft className="w-3.5 h-3.5" />
                  </button>
                  {Array.from({ length: totalPages }, (_, i) => i + 1).map(pg => (
                    <button
                      key={pg}
                      onClick={() => setCurrentPage(pg)}
                      className={cn(
                        "w-6 h-6 rounded-[6px] flex items-center justify-center text-[11px] font-medium transition-all",
                        pg === currentPage
                          ? "bg-primary text-white"
                          : "text-muted-foreground hover:bg-secondary"
                      )}
                    >
                      {pg}
                    </button>
                  ))}
                  <button
                    onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                    disabled={currentPage === totalPages}
                    className="w-6 h-6 rounded-[6px] flex items-center justify-center text-muted-foreground hover:bg-secondary disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                    aria-label="Next page"
                  >
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Selection Toolbar */}
      <AnimatePresence>
        {selectedPapers.size >= 2 && (
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 20, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 bg-foreground text-white rounded-[14px] px-5 py-3 shadow-xl flex items-center gap-4"
          >
            <span className="text-sm">
              {selectedPapers.size} papers selected
            </span>
            <button
              onClick={handleViewSelectedGraph}
              className="h-8 px-3 rounded-[8px] bg-white/20 hover:bg-white/30 text-sm font-medium flex items-center gap-1.5 transition-colors"
            >
              <Brain className="w-3.5 h-3.5" />
              View Graph
            </button>
            <button
              onClick={() => setSelectedPapers(new Set())}
              className="w-7 h-7 rounded-[8px] flex items-center justify-center hover:bg-white/20 transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Upload Dialog */}
      <UploadDialog
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onSuccess={handleUploadSuccess}
      />
    </div>
  );
}

// Default export wraps in Suspense (required for useSearchParams in Next.js)
export default function LibraryPage() {
  return (
    <Suspense fallback={<div className="h-full" />}>
      <LibraryContent />
    </Suspense>
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
