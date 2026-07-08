"use client";

import { useState, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, X, FileText, Loader2, CheckCircle, XCircle } from "lucide-react";
import { uploadPaper } from "@/lib/api";

interface UploadDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

interface FileStatus {
  file: File;
  status: "pending" | "uploading" | "success" | "error";
  message?: string;
}

export function UploadDialog({ open, onClose, onSuccess }: UploadDialogProps) {
  const [files, setFiles] = useState<FileStatus[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const reset = () => {
    setFiles([]);
    setIsUploading(false);
    setCurrentIndex(0);
  };

  const handleClose = () => {
    if (!isUploading) {
      reset();
      onClose();
    }
  };

  const addFiles = (newFiles: FileList | File[]) => {
    const pdfFiles = Array.from(newFiles).filter(
      (f) => f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf")
    );

    if (pdfFiles.length === 0) return;

    setFiles((prev) => [
      ...prev,
      ...pdfFiles.map((file) => ({ file, status: "pending" as const })),
    ]);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    addFiles(e.dataTransfer.files);
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      addFiles(e.target.files);
    }
    // Reset input so same files can be selected again
    e.target.value = "";
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (files.length === 0) return;

    setIsUploading(true);
    let hasSuccess = false;

    for (let i = 0; i < files.length; i++) {
      if (files[i].status === "success") continue; // Skip already done

      setCurrentIndex(i);
      setFiles((prev) =>
        prev.map((f, idx) => (idx === i ? { ...f, status: "uploading" } : f))
      );

      try {
        await uploadPaper(files[i].file);
        setFiles((prev) =>
          prev.map((f, idx) =>
            idx === i ? { ...f, status: "success", message: "入库成功" } : f
          )
        );
        hasSuccess = true;
      } catch (err) {
        setFiles((prev) =>
          prev.map((f, idx) =>
            idx === i
              ? { ...f, status: "error", message: err instanceof Error ? err.message : "上传失败" }
              : f
          )
        );
      }
    }

    setIsUploading(false);
    if (hasSuccess) {
      onSuccess();
    }
  };

  const completedCount = files.filter((f) => f.status === "success").length;
  const totalCount = files.length;

  if (!open) return null;

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={handleClose}
            className="fixed inset-0 bg-black/40 z-50"
          />

          {/* Dialog */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.2 }}
            className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-lg bg-white rounded-[20px] shadow-xl z-50 p-6"
          >
            {/* Header */}
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-semibold">Upload Papers</h2>
              <button
                onClick={handleClose}
                disabled={isUploading}
                className="w-8 h-8 rounded-[10px] flex items-center justify-center hover:bg-secondary text-muted-foreground transition-colors disabled:opacity-50"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Drop Zone */}
            <div
              onDrop={handleDrop}
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragOver(true);
              }}
              onDragLeave={() => setIsDragOver(false)}
              onClick={() => fileInputRef.current?.click()}
              className={`
                border-2 border-dashed rounded-[16px] p-6 text-center cursor-pointer transition-all
                ${isDragOver ? "border-primary bg-primary/5" : "border-border hover:border-primary/40 hover:bg-secondary/50"}
              `}
            >
              <Upload className="w-6 h-6 text-muted-foreground mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">
                Drag & drop PDFs here, or click to browse
              </p>
              <p className="text-[11px] text-muted-foreground mt-1">
                Supports multiple files
              </p>
            </div>

            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              multiple
              onChange={handleFileSelect}
              className="hidden"
            />

            {/* File List */}
            {files.length > 0 && (
              <div className="mt-4 max-h-48 overflow-auto space-y-1.5">
                {files.map((item, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-3 px-3 py-2 rounded-[10px] bg-secondary/50"
                  >
                    {/* Status Icon */}
                    {item.status === "pending" && (
                      <FileText className="w-4 h-4 text-muted-foreground shrink-0" />
                    )}
                    {item.status === "uploading" && (
                      <Loader2 className="w-4 h-4 text-primary animate-spin shrink-0" />
                    )}
                    {item.status === "success" && (
                      <CheckCircle className="w-4 h-4 text-green-500 shrink-0" />
                    )}
                    {item.status === "error" && (
                      <XCircle className="w-4 h-4 text-destructive shrink-0" />
                    )}

                    {/* File Name */}
                    <div className="flex-1 min-w-0">
                      <p className="text-[12px] text-foreground truncate">
                        {item.file.name}
                      </p>
                      {item.message && (
                        <p
                          className={`text-[11px] ${
                            item.status === "error"
                              ? "text-destructive"
                              : "text-muted-foreground"
                          }`}
                        >
                          {item.message}
                        </p>
                      )}
                    </div>

                    {/* Size */}
                    <span className="text-[11px] text-muted-foreground shrink-0">
                      {(item.file.size / 1024 / 1024).toFixed(1)}MB
                    </span>

                    {/* Remove (only before upload starts) */}
                    {!isUploading && item.status === "pending" && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          removeFile(i);
                        }}
                        className="w-5 h-5 rounded flex items-center justify-center hover:bg-secondary text-muted-foreground"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Progress */}
            {isUploading && (
              <div className="mt-3">
                <div className="flex items-center justify-between text-[11px] text-muted-foreground mb-1">
                  <span>Uploading {currentIndex + 1} of {totalCount}...</span>
                  <span>{completedCount}/{totalCount} done</span>
                </div>
                <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary rounded-full transition-all duration-300"
                    style={{ width: `${(completedCount / totalCount) * 100}%` }}
                  />
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="mt-5 flex gap-3">
              <button
                onClick={handleClose}
                disabled={isUploading}
                className="flex-1 h-10 rounded-[10px] border border-border text-sm font-medium hover:bg-secondary transition-colors disabled:opacity-50"
              >
                {completedCount > 0 && !isUploading ? "Close" : "Cancel"}
              </button>
              <button
                onClick={handleUpload}
                disabled={files.length === 0 || isUploading || completedCount === totalCount}
                className="flex-1 h-10 rounded-[10px] bg-primary text-white text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {isUploading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Uploading...
                  </>
                ) : completedCount === totalCount && totalCount > 0 ? (
                  "All Done ✓"
                ) : (
                  `Upload ${files.length} file${files.length !== 1 ? "s" : ""}`
                )}
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
