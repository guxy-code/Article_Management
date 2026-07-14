"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { motion } from "framer-motion";
import { Boxes, GitBranch, Clock, Loader2, Lightbulb } from "lucide-react";
import {
  getInterestGraph,
  getInterestGraphStats,
  getInterestGraphSummary,
  getInterestGraphNode,
  getGrowthLog,
  type InterestGraphNode,
  type InterestGraphData,
  type InterestGraphHealth,
  type GraphSummaryField,
  type GrowthLogEntry,
} from "@/lib/api";
import InterestGraphView from "./components/interest-graph";
import NodeDetailPanel from "./components/node-detail-panel";
import DirectionSummary from "./components/direction-summary";
import GrowthLog from "./components/growth-log";

export default function MemoryPage() {
  const [graphData, setGraphData] = useState<InterestGraphData>({ nodes: [], edges: [] });
  const [stats, setStats] = useState<InterestGraphHealth | null>(null);
  const [summary, setSummary] = useState<GraphSummaryField[]>([]);
  const [logs, setLogs] = useState<GrowthLogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const [selectedNode, setSelectedNode] = useState<InterestGraphNode | null>(null);
  const [nodeChildren, setNodeChildren] = useState<any[]>([]);
  const [nodeAncestors, setNodeAncestors] = useState<any[]>([]);

  const load = useCallback(async () => {
    const [g, s, sm, l] = await Promise.all([
      getInterestGraph("active").catch(() => ({ nodes: [], edges: [] })),
      getInterestGraphStats().catch(() => null),
      getInterestGraphSummary().catch(() => ({ summary: [] })),
      getGrowthLog(20).catch(() => ({ logs: [] })),
    ]);
    setGraphData(g);
    setStats(s);
    setSummary(sm.summary);
    setLogs(l.logs);
    setIsLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleNodeClick = async (node: InterestGraphNode) => {
    setSelectedNode(node);
    try {
      const detail = await getInterestGraphNode(node.name);
      setNodeChildren(detail.children || []);
      setNodeAncestors(detail.ancestors || []);
    } catch {
      setNodeChildren([]);
      setNodeAncestors([]);
    }
  };

  const handleNodeDeleted = (name: string) => {
    setGraphData((prev) => ({
      nodes: prev.nodes.filter((n) => n.name !== name),
      edges: prev.edges.filter((e) => e.source !== name && e.target !== name),
    }));
    setSelectedNode(null);
  };

  // 洞察：从图谱数据中计算
  const insights = useMemo(() => {
    const items: string[] = [];
    // 对比关系
    const comparisons = graphData.edges.filter((e) => e.type === "COMPARES_WITH");
    for (const c of comparisons.slice(0, 2)) {
      items.push(`正在对比 ${c.source} 和 ${c.target}`);
    }
    // 盲区：weight 低 + hit_count 为 0 的节点
    const blindSpots = graphData.nodes.filter(
      (n) => (n.hit_count || 0) === 0 && (n.weight || 0) <= 0.15
    );
    if (blindSpots.length > 0) {
      const names = blindSpots.slice(0, 3).map((n) => n.name).join("、");
      items.push(`${names} 出现在论文中但未深入探索`);
    }
    // 高权重方向
    const deepNodes = graphData.nodes.filter((n) => (n.weight || 0) >= 0.6 && n.type !== "Field");
    if (deepNodes.length > 0) {
      items.push(`深入关注：${deepNodes.slice(0, 3).map((n) => n.name).join("、")}`);
    }
    return items;
  }, [graphData]);

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const fieldCount = stats?.field_count || 0;
  const topicCount = stats?.topic_count || 0;
  const directionCount = fieldCount + topicCount;
  const lastGrowth = logs.length > 0 ? logs[0].created_at : null;

  const formatLastGrowth = (iso: string | null) => {
    if (!iso) return "—";
    try {
      const d = new Date(iso);
      const now = new Date();
      const diff = (now.getTime() - d.getTime()) / 1000;
      if (diff < 60) return "刚刚";
      if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`;
      if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`;
      return `${Math.floor(diff / 86400)}天前`;
    } catch {
      return "—";
    }
  };

  return (
    <div className="h-full overflow-hidden flex flex-col">
      {/* Header */}
      <div className="px-6 pt-5 pb-3 shrink-0">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
        >
          <div className="flex items-center gap-2.5 mb-0.5">
            <div className="w-7 h-7 rounded-[8px] bg-indigo-50 flex items-center justify-center">
              <Boxes className="w-4 h-4 text-indigo-600" />
            </div>
            <h1 className="text-lg font-semibold tracking-tight">Memory Base</h1>
          </div>
          <p className="text-[12px] text-muted-foreground ml-[38px]">
            系统从你的每一次交互中构建研究方向图谱，越用越懂你
          </p>
        </motion.div>
      </div>

      {/* Main: Left-Right Layout */}
      <div className="flex-1 flex overflow-hidden px-6 pb-5 gap-4 min-h-0">
        {/* 左栏 */}
        <div className="w-[300px] shrink-0 flex flex-col gap-3 overflow-auto pr-1">
          {/* 统计卡片：研究方向 + 最近生长 */}
          <div className="grid grid-cols-2 gap-2">
            <MiniStatCard icon={GitBranch} label="研究方向" value={directionCount} color="text-purple-600" bg="bg-purple-50" />
            <MiniStatCard icon={Clock} label="最近生长" value={formatLastGrowth(lastGrowth)} color="text-emerald-600" bg="bg-emerald-50" />
          </div>

          {/* 研究方向认知 */}
          <div className="p-4 rounded-[12px] border border-border bg-white card-shadow">
            <h2 className="text-[13px] font-medium flex items-center gap-1.5 mb-2.5">
              <Boxes className="w-3.5 h-3.5 text-purple-600" />
              研究方向认知
            </h2>
            <DirectionSummary summary={summary} />
          </div>

          {/* 洞察 */}
          {insights.length > 0 && (
            <div className="p-4 rounded-[12px] border border-border bg-white card-shadow">
              <h2 className="text-[13px] font-medium flex items-center gap-1.5 mb-2.5">
                <Lightbulb className="w-3.5 h-3.5 text-amber-500" />
                洞察
              </h2>
              <div className="space-y-1.5">
                {insights.map((insight, i) => (
                  <p key={i} className="text-[12px] text-foreground leading-relaxed flex items-start gap-1.5">
                    <span className="text-amber-400 shrink-0 mt-0.5">•</span>
                    {insight}
                  </p>
                ))}
              </div>
            </div>
          )}

          {/* 最近动态 */}
          <div className="p-4 rounded-[12px] border border-border bg-white card-shadow flex-1 min-h-0 overflow-auto">
            <h2 className="text-[13px] font-medium flex items-center gap-1.5 mb-2.5">
              <GitBranch className="w-3.5 h-3.5 text-indigo-600" />
              最近动态
            </h2>
            <GrowthLog logs={logs} />
          </div>
        </div>

        {/* 右栏：图谱 */}
        <div className="flex-1 relative min-w-0 min-h-0">
          <InterestGraphView
            nodes={graphData.nodes}
            edges={graphData.edges}
            onNodeClick={handleNodeClick}
          />
          {selectedNode && (
            <NodeDetailPanel
              node={selectedNode}
              children={nodeChildren}
              ancestors={nodeAncestors}
              onClose={() => setSelectedNode(null)}
              onDeleted={handleNodeDeleted}
              onUpdated={load}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function MiniStatCard({
  icon: Icon,
  label,
  value,
  color,
  bg,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number | string;
  color: string;
  bg: string;
}) {
  return (
    <div className="flex items-center gap-2.5 p-3 rounded-[10px] border border-border bg-white card-shadow">
      <div className={`w-7 h-7 rounded-[7px] ${bg} flex items-center justify-center shrink-0`}>
        <Icon className={`w-3.5 h-3.5 ${color}`} />
      </div>
      <div>
        <p className="text-base font-bold tracking-tight leading-tight">{value}</p>
        <p className="text-[10px] text-muted-foreground">{label}</p>
      </div>
    </div>
  );
}
