"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Sparkles, ExternalLink, Tag } from "lucide-react";
import { getRecommendations, type RecommendedPaper } from "@/lib/api";
import { cn } from "@/lib/utils";

const TIME_OPTIONS = [
  { value: "1year", label: "1 Year" },
  { value: "6months", label: "6 Months" },
  { value: "3months", label: "3 Months" },
];

const LEVEL_OPTIONS = [
  { value: "all", label: "All" },
  { value: "A", label: "CCF-A" },
  { value: "B", label: "CCF-B" },
  { value: "C", label: "CCF-C" },
];

const CCF_COLORS: Record<string, string> = {
  A: "bg-red-100 text-red-700",
  B: "bg-orange-100 text-orange-700",
  C: "bg-yellow-100 text-yellow-700",
};

export default function DiscoverPage() {
  const [papers, setPapers] = useState<RecommendedPaper[]>([]);
  const [keywords, setKeywords] = useState<string[]>([]);
  const [timeRange, setTimeRange] = useState("1year");
  const [level, setLevel] = useState("all");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchData = async (range: string, lvl: string) => {
    setIsLoading(true);
    setError("");
    try {
      const data = await getRecommendations(range, lvl);
      setPapers(data.papers);
      setKeywords(data.keywords);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData(timeRange, level);
  }, [timeRange, level]);

  return (
    <div className="h-full overflow-auto">
      <div className="px-6 py-6">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
        >
          {/* Header */}
          <div className="flex items-center justify-between mb-5">
            <div>
              <h1 className="text-lg font-semibold tracking-tight flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-primary" />
                Discover
              </h1>
              {keywords.length > 0 && (
                <p className="text-[12px] text-muted-foreground mt-1">
                  Based on your research: {keywords.join(", ")}
                </p>
              )}
            </div>

            {/* Filters */}
            <div className="flex items-center gap-2">
              <select
                value={timeRange}
                onChange={(e) => setTimeRange(e.target.value)}
                className="h-8 px-3 rounded-[8px] border border-border text-[12px] bg-white focus:outline-none focus:ring-2 focus:ring-primary/20"
              >
                {TIME_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
              <select
                value={level}
                onChange={(e) => setLevel(e.target.value)}
                className="h-8 px-3 rounded-[8px] border border-border text-[12px] bg-white focus:outline-none focus:ring-2 focus:ring-primary/20"
              >
                {LEVEL_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Content */}
          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="p-4 rounded-[14px] border border-border animate-pulse">
                  <div className="h-4 bg-secondary rounded w-3/4 mb-2" />
                  <div className="h-3 bg-secondary rounded w-1/2" />
                </div>
              ))}
            </div>
          ) : error ? (
            <div className="text-center py-12">
              <p className="text-sm text-destructive">{error}</p>
            </div>
          ) : papers.length === 0 ? (
            <div className="text-center py-12">
              <Sparkles className="w-10 h-10 text-muted-foreground/30 mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">
                {keywords.length === 0
                  ? "Upload papers first to get personalized recommendations."
                  : "No papers found for this filter combination."}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {papers.map((paper, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className="group p-4 rounded-[14px] border border-border bg-white hover:border-primary/20 hover:shadow-sm transition-all"
                >
                  <div className="flex items-start gap-3">
                    <div className="flex-1 min-w-0">
                      <h3 className="text-[13px] font-medium text-foreground leading-snug line-clamp-2 group-hover:text-primary transition-colors">
                        {paper.title}
                      </h3>
                      <p className="text-[11px] text-muted-foreground mt-1 truncate">
                        {paper.authors.join(", ")}
                      </p>
                      <div className="flex items-center gap-2 mt-2">
                        {paper.year && (
                          <span className="text-[10px] text-muted-foreground">{paper.year}</span>
                        )}
                        {paper.venue && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-secondary text-muted-foreground truncate max-w-[200px]">
                            {paper.venue}
                          </span>
                        )}
                        {paper.ccf_level && (
                          <span className={cn("text-[10px] px-1.5 py-0.5 rounded font-medium", CCF_COLORS[paper.ccf_level])}>
                            CCF-{paper.ccf_level}
                          </span>
                        )}
                      </div>
                    </div>

                    {paper.url && (
                      <a
                        href={paper.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="w-8 h-8 rounded-[8px] flex items-center justify-center hover:bg-secondary text-muted-foreground hover:text-primary transition-colors shrink-0"
                      >
                        <ExternalLink className="w-4 h-4" />
                      </a>
                    )}
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
}
