"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  forceSimulation,
  forceLink,
  forceManyBody,
  forceCenter,
  forceCollide,
  type SimulationNodeDatum,
  type SimulationLinkDatum,
} from "d3-force";
import { Brain, X } from "lucide-react";
import { getGraph, getPaperGraph, getKeywordGraph, type GraphNode, type GraphEdge } from "@/lib/api";
import { cn } from "@/lib/utils";

// Node type config
const TYPE_CONFIG: Record<string, { color: string; size: number }> = {
  Paper: { color: "#4F46E5", size: 56 },
  Method: { color: "#2563EB", size: 44 },
  Problem: { color: "#DC2626", size: 40 },
  Dataset: { color: "#CA8A04", size: 36 },
  Concept: { color: "#7C3AED", size: 34 },
  Keyword: { color: "#059669", size: 38 },
};

function truncateLabel(label: string, maxLen: number = 18): string {
  return label.length > maxLen ? label.slice(0, maxLen) + "…" : label;
}

// Force-directed layout
function computeLayout(
  graphNodes: GraphNode[],
  graphEdges: GraphEdge[]
): { x: number; y: number; id: string }[] {
  interface SimNode extends SimulationNodeDatum {
    id: string;
    type: string;
  }

  const simNodes: SimNode[] = graphNodes.map((n) => ({
    id: n.id,
    type: n.type,
    x: Math.random() * 800,
    y: Math.random() * 600,
  }));

  const simLinks: SimulationLinkDatum<SimNode>[] = graphEdges.map((e) => ({
    source: e.source,
    target: e.target,
  }));

  const simulation = forceSimulation<SimNode>(simNodes)
    .force(
      "link",
      forceLink<SimNode, SimulationLinkDatum<SimNode>>(simLinks)
        .id((d) => d.id)
        .distance(120)
    )
    .force("charge", forceManyBody().strength(-400))
    .force("center", forceCenter(500, 400))
    .force(
      "collide",
      forceCollide<SimNode>().radius((d) => {
        const cfg = TYPE_CONFIG[d.type];
        return cfg ? cfg.size + 20 : 40;
      })
    )
    .stop();

  // Run simulation synchronously
  for (let i = 0; i < 300; i++) {
    simulation.tick();
  }

  return simNodes.map((n) => ({
    id: n.id,
    x: n.x || 0,
    y: n.y || 0,
  }));
}

export default function KnowledgePage() {
  const searchParams = useSearchParams();
  const paperTitle = searchParams.get("paper");

  const [viewMode, setViewMode] = useState<"structure" | "keywords">("keywords");
  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<GraphEdge[]>([]);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [hoveredEdge, setHoveredEdge] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      setIsLoading(true);
      setError("");
      try {
        let data;
        if (paperTitle) {
          // 单篇论文视图，始终用结构图
          data = await getPaperGraph(paperTitle);
        } else if (viewMode === "keywords") {
          data = await getKeywordGraph();
        } else {
          data = await getGraph();
        }
        setGraphNodes(data.nodes);
        setGraphEdges(data.edges);
      } catch (err) {
        setError(err instanceof Error ? err.message : "加载失败");
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, [paperTitle, viewMode]);

  // Compute layout and build React Flow nodes/edges
  useEffect(() => {
    if (graphNodes.length === 0) return;

    const positions = computeLayout(graphNodes, graphEdges);
    const posMap = new Map(positions.map((p) => [p.id, { x: p.x, y: p.y }]));

    const rfNodes: Node[] = graphNodes.map((node) => {
      const pos = posMap.get(node.id) || { x: 0, y: 0 };
      const cfg = TYPE_CONFIG[node.type] || { color: "#6B7280", size: 36 };
      const label = truncateLabel(node.label);

      return {
        id: node.id,
        position: pos,
        data: { label, nodeType: node.type, fullLabel: node.label },
        style: {
          background: cfg.color,
          color: "white",
          border: "2px solid transparent",
          borderRadius: `${cfg.size / 2}px`,
          width: `${cfg.size * 2.2}px`,
          height: `${cfg.size}px`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: node.type === "Paper" ? "11px" : "10px",
          fontWeight: 500,
          padding: "4px 8px",
          textAlign: "center" as const,
          lineHeight: "1.2",
          boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
          cursor: "pointer",
        },
      };
    });

    const rfEdges: Edge[] = graphEdges.map((e, i) => ({
      id: `e-${i}`,
      source: e.source,
      target: e.target,
      label: undefined, // hidden by default
      style: { stroke: "#D1D5DB", strokeWidth: 1.5 },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        width: 10,
        height: 10,
        color: "#9CA3AF",
      },
      data: { relType: e.type },
    }));

    setNodes(rfNodes);
    setEdges(rfEdges);
  }, [graphNodes, graphEdges, setNodes, setEdges]);

  const handleNodeClick = useCallback(
    (_: any, node: Node) => {
      const original = graphNodes.find((n) => n.id === node.id);
      setSelectedNode(original || null);

      // Highlight connected edges
      setEdges((eds) =>
        eds.map((e) => {
          const isConnected = e.source === node.id || e.target === node.id;
          return {
            ...e,
            label: isConnected
              ? (e.data?.relType as string)
              : undefined,
            labelStyle: { fontSize: 9, fill: "#4F46E5", fontWeight: 600 },
            style: {
              stroke: isConnected ? "#4F46E5" : "#D1D5DB",
              strokeWidth: isConnected ? 2.5 : 1.5,
            },
            animated: isConnected,
          };
        })
      );
    },
    [graphNodes, setEdges]
  );

  const handlePaneClick = useCallback(() => {
    setSelectedNode(null);
    // Reset edge styles
    setEdges((eds) =>
      eds.map((e) => ({
        ...e,
        label: undefined,
        style: { stroke: "#D1D5DB", strokeWidth: 1.5 },
        animated: false,
      }))
    );
  }, [setEdges]);

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-sm text-muted-foreground animate-pulse">Loading knowledge graph...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-sm text-destructive">{error}</div>
      </div>
    );
  }

  if (graphNodes.length === 0) {
    return (
      <div className="h-full flex flex-col items-center justify-center">
        <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-6">
          <Brain className="w-8 h-8 text-primary" />
        </div>
        <h2 className="text-lg font-semibold mb-2">No knowledge graph yet</h2>
        <p className="text-sm text-muted-foreground">
          Upload papers to build the knowledge graph.
        </p>
      </div>
    );
  }

  return (
    <div className="h-full flex">
      {/* Graph */}
      <div className="flex-1 relative">
        {/* Legend */}
        <div className="absolute top-4 left-4 z-10 bg-white/95 backdrop-blur-sm rounded-[12px] border border-border p-3 shadow-sm">
          {paperTitle && (
            <div className="mb-2 pb-2 border-b border-border">
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Paper</p>
              <p className="text-[11px] text-foreground font-medium mt-0.5 max-w-[160px] truncate">{paperTitle}</p>
            </div>
          )}

          {/* View Mode Tabs (only on global view) */}
          {!paperTitle && (
            <div className="mb-3 pb-2 border-b border-border">
              <div className="flex items-center bg-secondary rounded-[8px] p-0.5">
                <button
                  onClick={() => setViewMode("keywords")}
                  className={cn(
                    "flex-1 text-[10px] font-medium px-2 py-1 rounded-[6px] transition-all",
                    viewMode === "keywords"
                      ? "bg-white shadow-sm text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  Keywords
                </button>
                <button
                  onClick={() => setViewMode("structure")}
                  className={cn(
                    "flex-1 text-[10px] font-medium px-2 py-1 rounded-[6px] transition-all",
                    viewMode === "structure"
                      ? "bg-white shadow-sm text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  Structure
                </button>
              </div>
            </div>
          )}

          <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2 font-medium">
            Node Types
          </p>
          <div className="space-y-1.5">
            {Object.entries(TYPE_CONFIG).map(([type, cfg]) => (
              <div key={type} className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ background: cfg.color }}
                />
                <span className="text-[11px] text-foreground">{type}</span>
              </div>
            ))}
          </div>
          <div className="mt-3 pt-2 border-t border-border">
            <p className="text-[10px] text-muted-foreground">
              Click a node to see relations
            </p>
          </div>
        </div>

        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={handleNodeClick}
          onPaneClick={handlePaneClick}
          fitView
          fitViewOptions={{ padding: 0.3 }}
          minZoom={0.2}
          maxZoom={3}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={24} size={1} color="#F3F4F6" />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>

      {/* Detail Panel */}
      {selectedNode && (
        <motion.div
          initial={{ x: 20, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          transition={{ duration: 0.2 }}
          className="w-72 border-l border-border bg-white p-5 overflow-auto shrink-0"
        >
          <div className="flex items-center justify-between mb-4">
            <span
              className="text-[11px] font-medium px-2.5 py-1 rounded-full text-white"
              style={{
                background: TYPE_CONFIG[selectedNode.type]?.color || "#6B7280",
              }}
            >
              {selectedNode.type}
            </span>
            <button
              onClick={() => {
                setSelectedNode(null);
                handlePaneClick();
              }}
              className="w-6 h-6 rounded flex items-center justify-center hover:bg-secondary"
            >
              <X className="w-3.5 h-3.5 text-muted-foreground" />
            </button>
          </div>

          <h3 className="text-[14px] font-semibold leading-snug mb-4">
            {selectedNode.label}
          </h3>

          {/* Properties */}
          <div className="space-y-3">
            {Object.entries(selectedNode.properties).map(([key, value]) => {
              if (!value || key === "name" || key === "title") return null;
              return (
                <div key={key}>
                  <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-medium">
                    {key}
                  </p>
                  <p className="text-[12px] text-foreground mt-0.5 leading-relaxed">
                    {String(value)}
                  </p>
                </div>
              );
            })}
          </div>

          {/* Relations */}
          <div className="mt-5 pt-4 border-t border-border">
            <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-medium mb-2">
              Relations
            </p>
            <div className="space-y-1.5">
              {graphEdges
                .filter(
                  (e) =>
                    e.source === selectedNode.id ||
                    e.target === selectedNode.id
                )
                .map((e, i) => {
                  const isOutgoing = e.source === selectedNode.id;
                  const otherId = isOutgoing ? e.target : e.source;
                  const otherNode = graphNodes.find((n) => n.id === otherId);
                  return (
                    <div
                      key={i}
                      className="flex items-center gap-1.5 text-[11px]"
                    >
                      <span className="text-muted-foreground">
                        {isOutgoing ? "→" : "←"}
                      </span>
                      <span className="text-primary font-medium">
                        {e.type}
                      </span>
                      <span className="text-foreground truncate">
                        {otherNode?.label || "?"}
                      </span>
                    </div>
                  );
                })}
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
}
