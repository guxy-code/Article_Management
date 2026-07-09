"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { FileText, Cpu, Tag, GitBranch, Brain } from "lucide-react";
import {
  getGraphStats,
  getConceptFrequency,
  getPapersWithConcepts,
  type ConceptFrequency,
  type PaperWithConcepts,
} from "@/lib/api";

const NODE_COLORS: Record<string, string> = {
  Paper: "#4F46E5",
  Method: "#2563EB",
  Problem: "#DC2626",
  Dataset: "#CA8A04",
  Concept: "#7C3AED",
};

export default function StatsPage() {
  const [stats, setStats] = useState<Record<string, any>>({});
  const [concepts, setConcepts] = useState<ConceptFrequency[]>([]);
  const [papers, setPapers] = useState<PaperWithConcepts[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [hoveredBar, setHoveredBar] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      const [s, c, p] = await Promise.all([
        getGraphStats().catch(() => ({})),
        getConceptFrequency().catch(() => ({ concepts: [] })),
        getPapersWithConcepts().catch(() => ({ papers: [] })),
      ]);
      setStats(s);
      setConcepts(c.concepts);
      setPapers(p.papers);
      setIsLoading(false);
    }
    load();
  }, []);

  const nodeCount = stats.nodes || {};
  const paperCount = nodeCount.Paper || 0;
  const methodCount = nodeCount.Method || 0;
  const conceptCount = nodeCount.Concept || 0;
  const totalRelations = stats.total_edges || 0;
  const totalNodes = Object.values(nodeCount).reduce((a: number, b: any) => a + (b as number), 0) as number;

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <p className="text-sm text-muted-foreground animate-pulse">Loading...</p>
      </div>
    );
  }

  if (paperCount === 0) {
    return (
      <div className="h-full flex flex-col items-center justify-center">
        <Brain className="w-12 h-12 text-muted-foreground/30 mb-4" />
        <p className="text-sm text-muted-foreground">Upload papers to see statistics.</p>
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto">
      <div className="px-6 py-6">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          <h1 className="text-lg font-semibold tracking-tight mb-5">Research Overview</h1>

          {/* Stat Cards */}
          <div className="grid grid-cols-4 gap-3 mb-4">
            <StatCard icon={FileText} label="Papers" value={paperCount} bg="bg-indigo-50" iconColor="text-indigo-600" />
            <StatCard icon={Cpu} label="Methods" value={methodCount} bg="bg-blue-50" iconColor="text-blue-600" />
            <StatCard icon={Tag} label="Topics" value={conceptCount} bg="bg-purple-50" iconColor="text-purple-600" />
            <StatCard icon={GitBranch} label="Relations" value={totalRelations} bg="bg-emerald-50" iconColor="text-emerald-600" />
          </div>

          {/* Two Column */}
          <div className="grid grid-cols-2 gap-4 mb-4">
            {/* Research Focus */}
            <div className="p-5 rounded-[16px] border border-border bg-white">
              <h2 className="text-[13px] font-medium mb-4">Research Focus</h2>
              <div className="space-y-1.5">
                {concepts.slice(0, 5).map((c) => {
                  const maxCount = concepts[0]?.count || 1;
                  const pct = (c.count / maxCount) * 100;
                  const isHovered = hoveredBar === `focus-${c.name}`;
                  return (
                    <div
                      key={c.name}
                      className="flex items-center gap-2 px-2 py-1.5 rounded-[8px] transition-all duration-150 cursor-default hover:bg-indigo-50/50"
                      onMouseEnter={() => setHoveredBar(`focus-${c.name}`)}
                      onMouseLeave={() => setHoveredBar(null)}
                    >
                      <span className={`text-[11px] w-32 truncate shrink-0 transition-colors ${isHovered ? "text-primary font-medium" : "text-foreground"}`}>
                        {c.name}
                      </span>
                      <div className="flex-1 h-5 bg-secondary rounded-[6px] overflow-hidden">
                        <motion.div
                          className="h-full rounded-[6px] transition-colors duration-150"
                          style={{
                            width: `${Math.max(pct, 12)}%`,
                            backgroundColor: isHovered ? "#4F46E5" : "rgba(79, 70, 229, 0.2)",
                          }}
                          initial={{ width: 0 }}
                          animate={{ width: `${Math.max(pct, 12)}%` }}
                          transition={{ duration: 0.5, delay: 0.1 }}
                        />
                      </div>
                      <span className={`text-[11px] w-5 text-right shrink-0 font-medium transition-all ${isHovered ? "text-primary scale-110" : "text-muted-foreground"}`}>
                        {c.count}
                      </span>
                    </div>
                  );
                })}
                {concepts.length > 5 && (
                  <p className="text-[10px] text-muted-foreground px-2 pt-1">+{concepts.length - 5} more</p>
                )}
              </div>
            </div>

            {/* Knowledge Structure */}
            <div className="p-5 rounded-[16px] border border-border bg-white">
              <h2 className="text-[13px] font-medium mb-4">Knowledge Structure</h2>

              {/* Thick stacked bar */}
              <div className="h-10 rounded-[10px] overflow-hidden flex mb-5 shadow-inner">
                {Object.entries(nodeCount).map(([type, count]) => {
                  const pct = totalNodes > 0 ? ((count as number) / totalNodes) * 100 : 0;
                  const isHovered = hoveredBar === `struct-${type}`;
                  return (
                    <div
                      key={type}
                      className="h-full relative transition-all duration-200 cursor-default"
                      style={{
                        width: `${pct}%`,
                        backgroundColor: NODE_COLORS[type] || "#6B7280",
                        opacity: isHovered ? 1 : 0.7,
                        transform: isHovered ? "scaleY(1.1)" : "scaleY(1)",
                      }}
                      onMouseEnter={() => setHoveredBar(`struct-${type}`)}
                      onMouseLeave={() => setHoveredBar(null)}
                      title={`${type}: ${count}`}
                    >
                      {isHovered && (
                        <div className="absolute inset-0 flex items-center justify-center">
                          <span className="text-[10px] text-white font-bold drop-shadow">{count as number}</span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Legend */}
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(nodeCount).map(([type, count]) => {
                  const isHovered = hoveredBar === `struct-${type}`;
                  return (
                    <div
                      key={type}
                      className={`flex items-center gap-2 px-2 py-1.5 rounded-[8px] transition-all cursor-default ${isHovered ? "bg-secondary" : ""}`}
                      onMouseEnter={() => setHoveredBar(`struct-${type}`)}
                      onMouseLeave={() => setHoveredBar(null)}
                    >
                      <div
                        className="w-3 h-3 rounded-sm shrink-0"
                        style={{ backgroundColor: NODE_COLORS[type] || "#6B7280" }}
                      />
                      <span className="text-[11px] text-foreground flex-1">{type}</span>
                      <span className={`text-[11px] font-medium transition-colors ${isHovered ? "text-foreground" : "text-muted-foreground"}`}>
                        {count as number}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Paper Coverage */}
          <div className="p-5 rounded-[16px] border border-border bg-white">
            <h2 className="text-[13px] font-medium mb-4">Paper Topic Coverage</h2>
            <div className="space-y-1.5">
              {papers
                .sort((a, b) => b.concepts.length - a.concepts.length)
                .slice(0, 5)
                .map((paper) => {
                  const maxTopics = papers[0]?.concepts.length || 1;
                  const pct = (paper.concepts.length / maxTopics) * 100;
                  const isHovered = hoveredBar === `paper-${paper.title}`;
                  return (
                    <div
                      key={paper.title}
                      className={`flex items-center gap-3 px-2 py-2 rounded-[8px] transition-all duration-150 cursor-default ${isHovered ? "bg-purple-50/50" : ""}`}
                      onMouseEnter={() => setHoveredBar(`paper-${paper.title}`)}
                      onMouseLeave={() => setHoveredBar(null)}
                    >
                      <FileText className={`w-3.5 h-3.5 shrink-0 transition-colors ${isHovered ? "text-purple-600" : "text-muted-foreground"}`} />
                      <span className={`text-[11px] w-44 truncate shrink-0 transition-colors ${isHovered ? "text-foreground font-medium" : "text-foreground"}`}>
                        {paper.title}
                      </span>
                      <div className="flex-1 h-5 bg-secondary rounded-[6px] overflow-hidden">
                        <motion.div
                          className="h-full rounded-[6px] transition-colors duration-150"
                          style={{
                            backgroundColor: isHovered ? "#7C3AED" : "rgba(124, 58, 237, 0.2)",
                          }}
                          initial={{ width: 0 }}
                          animate={{ width: `${Math.max(pct, 8)}%` }}
                          transition={{ duration: 0.5, delay: 0.1 }}
                        />
                      </div>
                      <span className={`text-[11px] w-14 text-right shrink-0 transition-all ${isHovered ? "text-purple-600 font-medium scale-105" : "text-muted-foreground"}`}>
                        {paper.concepts.length} topics
                      </span>
                    </div>
                  );
                })}
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  bg,
  iconColor,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number;
  bg: string;
  iconColor: string;
}) {
  return (
    <motion.div
      whileHover={{ y: -2, boxShadow: "0 4px 12px rgba(0,0,0,0.08)" }}
      transition={{ duration: 0.15 }}
      className={`p-4 rounded-[14px] border border-border ${bg} cursor-default`}
    >
      <div className={`w-8 h-8 rounded-[10px] bg-white/80 flex items-center justify-center mb-3`}>
        <Icon className={`w-4 h-4 ${iconColor}`} />
      </div>
      <p className="text-2xl font-bold tracking-tight">{value}</p>
      <p className="text-[11px] text-muted-foreground mt-0.5">{label}</p>
    </motion.div>
  );
}
