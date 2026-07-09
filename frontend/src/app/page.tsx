"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import {
  MessageSquare,
  Library,
  Brain,
  ArrowRight,
  FileText,
  Tag,
  Layers,
} from "lucide-react";
import { getConcepts, getPapersWithConcepts, type PaperWithConcepts } from "@/lib/api";

const MAX_KEYWORDS = 8;
const MAX_PAPERS = 3;

export default function HomePage() {
  const [concepts, setConcepts] = useState<string[]>([]);
  const [papers, setPapers] = useState<PaperWithConcepts[]>([]);

  useEffect(() => {
    async function load() {
      const [c, p] = await Promise.all([
        getConcepts().catch(() => ({ concepts: [] })),
        getPapersWithConcepts().catch(() => ({ papers: [] })),
      ]);
      setConcepts(c.concepts);
      setPapers(p.papers);
    }
    load();
  }, []);

  return (
    <div className="h-full overflow-auto">
      <div className="max-w-3xl mx-auto px-6 py-12">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
        >
          {/* Hero */}
          <div className="mb-10">
            <h1 className="text-2xl font-semibold tracking-tight">
              Welcome back
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Continue your research.
            </p>
          </div>

          {/* Stats Cards Row */}
          <div className="grid grid-cols-2 gap-4 mb-8">
            {/* Papers Card */}
            <Link
              href="/library"
              className="group p-5 rounded-[16px] border border-border bg-white hover:border-primary/20 hover:shadow-sm transition-all"
            >
              <div className="flex items-center justify-between mb-3">
                <FileText className="w-5 h-5 text-primary" />
                <ArrowRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
              <p className="text-2xl font-semibold">{papers.length}</p>
              <p className="text-[12px] text-muted-foreground mt-0.5">
                Papers in library
              </p>
            </Link>

            {/* Keywords Card */}
            <Link
              href="/knowledge"
              className="group p-5 rounded-[16px] border border-border bg-white hover:border-primary/20 hover:shadow-sm transition-all"
            >
              <div className="flex items-center justify-between mb-3">
                <Tag className="w-5 h-5 text-purple-600" />
                <ArrowRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
              <p className="text-2xl font-semibold">{concepts.length}</p>
              <p className="text-[12px] text-muted-foreground mt-0.5">
                Research topics
              </p>
            </Link>
          </div>

          {/* Top Keywords */}
          {concepts.length > 0 && (
            <div className="mb-8 p-5 rounded-[16px] border border-border bg-white">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-medium">Top Keywords</h2>
                <Link
                  href="/knowledge"
                  className="text-[11px] text-primary hover:underline"
                >
                  View all →
                </Link>
              </div>
              <div className="flex flex-wrap gap-2">
                {concepts.slice(0, MAX_KEYWORDS).map((c) => (
                  <span
                    key={c}
                    className="px-2.5 py-1 rounded-full bg-primary/5 border border-primary/10 text-[11px] text-primary font-medium"
                  >
                    {c}
                  </span>
                ))}
                {concepts.length > MAX_KEYWORDS && (
                  <span className="px-2.5 py-1 rounded-full bg-secondary text-[11px] text-muted-foreground">
                    +{concepts.length - MAX_KEYWORDS} more
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Recent Papers */}
          {papers.length > 0 && (
            <div className="mb-8 p-5 rounded-[16px] border border-border bg-white">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-medium">Recent Papers</h2>
                <Link
                  href="/library"
                  className="text-[11px] text-primary hover:underline"
                >
                  View all →
                </Link>
              </div>
              <div className="space-y-3">
                {papers.slice(0, MAX_PAPERS).map((paper) => (
                  <div key={paper.title} className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-[8px] bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
                      <FileText className="w-4 h-4 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-[13px] font-medium text-foreground line-clamp-1">
                        {paper.title}
                      </p>
                      <div className="flex items-center gap-2 mt-1">
                        <Layers className="w-3 h-3 text-muted-foreground" />
                        <span className="text-[11px] text-muted-foreground">
                          {paper.concepts.length} topics
                        </span>
                        {paper.concepts.slice(0, 2).map((c) => (
                          <span
                            key={c}
                            className="text-[10px] px-1.5 py-0.5 rounded bg-secondary text-muted-foreground"
                          >
                            {c}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Quick Actions */}
          <div className="grid grid-cols-3 gap-3">
            <Link
              href="/chat"
              className="group p-4 rounded-[14px] border border-border bg-white hover:border-primary/20 hover:shadow-sm transition-all text-center"
            >
              <MessageSquare className="w-5 h-5 text-muted-foreground group-hover:text-primary mx-auto mb-2 transition-colors" />
              <p className="text-[12px] font-medium">Ask AI</p>
            </Link>
            <Link
              href="/library"
              className="group p-4 rounded-[14px] border border-border bg-white hover:border-primary/20 hover:shadow-sm transition-all text-center"
            >
              <Library className="w-5 h-5 text-muted-foreground group-hover:text-primary mx-auto mb-2 transition-colors" />
              <p className="text-[12px] font-medium">Library</p>
            </Link>
            <Link
              href="/knowledge"
              className="group p-4 rounded-[14px] border border-border bg-white hover:border-primary/20 hover:shadow-sm transition-all text-center"
            >
              <Brain className="w-5 h-5 text-muted-foreground group-hover:text-primary mx-auto mb-2 transition-colors" />
              <p className="text-[12px] font-medium">Knowledge</p>
            </Link>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
