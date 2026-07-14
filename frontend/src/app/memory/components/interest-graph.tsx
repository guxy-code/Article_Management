"use client";

import { useRef, useCallback, useEffect, useState, useMemo } from "react";
import dynamic from "next/dynamic";
import { Search } from "lucide-react";
import type { InterestGraphNode, InterestGraphEdge } from "@/lib/api";

// Cytoscape — client-side only (same as Knowledge page)
const CytoscapeComponent = dynamic(
  async () => {
    const cytoscape = (await import("cytoscape")).default;
    const dagre = (await import("cytoscape-dagre")).default;
    try { cytoscape.use(dagre); } catch {}
    return import("react-cytoscapejs");
  },
  { ssr: false }
);

// ── Visual config by UserTopic type ──
const TYPE_CONFIG: Record<string, { color: string; border: string; baseSize: number; concentricWeight: number }> = {
  Field:  { color: "#7C3AED", border: "#A78BFA", baseSize: 28, concentricWeight: 10 },
  Topic:  { color: "#2563EB", border: "#60A5FA", baseSize: 22, concentricWeight: 7  },
  Entity: { color: "#059669", border: "#34D399", baseSize: 16, concentricWeight: 3  },
};
const DEFAULT_CFG = { color: "#6B7280", border: "#9CA3AF", baseSize: 16, concentricWeight: 2 };

const EDGE_COLORS: Record<string, string> = {
  CONTAINS: "#9CA3AF",
  RELATES_TO: "#6366F1",
  COMPARES_WITH: "#F59E0B",
};

function getNodeCfg(type: string) {
  return TYPE_CONFIG[type] ?? DEFAULT_CFG;
}

function truncateLabel(label: string, maxLen = 18): string {
  return label.length > maxLen ? label.slice(0, maxLen) + "…" : label;
}

// ── Helper: engagement level from hit_count ──
function getEngagementLabel(hitCount: number): { text: string; color: string } {
  if (hitCount >= 5) return { text: "深入了解", color: "#059669" };
  if (hitCount >= 2) return { text: "持续关注", color: "#2563EB" };
  return { text: "初步接触", color: "#9CA3AF" };
}

// ── Helper: relative time from ISO string ──
function relativeTime(isoStr: string): string {
  if (!isoStr) return "";
  const diff = Date.now() - new Date(isoStr).getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return "今天";
  if (days === 1) return "昨天";
  if (days < 7) return `${days} 天前`;
  if (days < 30) return `${Math.floor(days / 7)} 周前`;
  return `${Math.floor(days / 30)} 个月前`;
}

// ── Helper: is node recently active (within 7 days) ──
function isRecentlyActive(lastSeen: string): boolean {
  if (!lastSeen) return false;
  return (Date.now() - new Date(lastSeen).getTime()) < 7 * 86400000;
}

// ── Stylesheet ──
function buildStylesheet() {
  const typeStyles = Object.entries(TYPE_CONFIG).map(([type, cfg]) => ({
    selector: `node[nodeType="${type}"]`,
    style: {
      "background-color": cfg.color,
      "border-color": cfg.border,
    } as any,
  }));

  return [
    {
      selector: "node",
      style: {
        shape: "ellipse",
        "background-color": DEFAULT_CFG.color,
        "border-width": 0,
        "border-color": DEFAULT_CFG.border,
        "border-opacity": 0,
        "background-opacity": "data(opacity)",
        width: "data(size)",
        height: "data(size)",
        label: "data(label)",
        "text-valign": "bottom",
        "text-halign": "center",
        "text-margin-y": 6,
        color: "#1F2937",
        "font-size": 7,
        "font-weight": "500",
        "text-wrap": "wrap",
        "text-max-width": 90,
        "text-background-color": "#F0F2F7",
        "text-background-opacity": 0.75,
        "text-background-padding": "2px",
        "text-background-shape": "roundrectangle",
        cursor: "pointer",
      } as any,
    },
    ...typeStyles,
    {
      selector: "node.hover",
      style: { "border-width": 2, "border-opacity": 0.8 } as any,
    },
    {
      selector: "node.highlighted",
      style: { "border-width": 4, "border-opacity": 1, "overlay-color": "#fff", "overlay-opacity": 0.12, "overlay-padding": 4 } as any,
    },
    {
      selector: "node.dimmed",
      style: { opacity: 0.2 } as any,
    },
    {
      selector: "node.search-match",
      style: { "border-width": 5, "border-color": "#EF4444", "border-opacity": 1 } as any,
    },
    {
      selector: "edge",
      style: {
        width: "data(edgeWidth)",
        "line-color": "data(edgeColor)",
        "target-arrow-color": "data(edgeColor)",
        "target-arrow-shape": "triangle",
        "arrow-scale": 0.7,
        "curve-style": "bezier",
        opacity: 0.5,
      } as any,
    },
    {
      selector: "edge.highlighted",
      style: {
        width: 2.5,
        "line-color": "#6366F1",
        "target-arrow-color": "#6366F1",
        opacity: 1,
        label: "data(edgeLabel)",
        "font-size": 8,
        color: "#4F46E5",
        "text-background-color": "#EEF2FF",
        "text-background-opacity": 1,
        "text-background-padding": "3px",
        "text-background-shape": "roundrectangle",
        "text-rotation": "autorotate",
      } as any,
    },
    {
      selector: "edge.dimmed",
      style: { opacity: 0.06 } as any,
    },
    {
      selector: "edge[edgeStyle='dashed']",
      style: { "line-style": "dashed" } as any,
    },
  ];
}

// ── Component ──
interface Props {
  nodes: InterestGraphNode[];
  edges: InterestGraphEdge[];
  onNodeClick: (node: InterestGraphNode) => void;
}

export default function InterestGraphView({ nodes, edges, onNodeClick }: Props) {
  const cyRef = useRef<any>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const nodesRef = useRef<InterestGraphNode[]>([]);
  const eventsBoundRef = useRef(false);

  // Tooltip
  const [tooltip, setTooltip] = useState<{ node: InterestGraphNode; x: number; y: number } | null>(null);

  useEffect(() => { nodesRef.current = nodes; }, [nodes]);

  // Convert to Cytoscape elements
  const elements = useMemo(() => {
    const nodeEls = nodes.map((n) => {
      const cfg = getNodeCfg(n.type);
      // Size based on weight
      const size = cfg.baseSize * (0.6 + (n.weight || 0.3) * 0.6);
      // Opacity based on weight (0.4 ~ 1.0)
      const opacity = 0.4 + (n.weight || 0.3) * 0.6;
      const data: any = {
        id: n.name,
        label: truncateLabel(n.name),
        fullLabel: n.name,
        nodeType: n.type,
        description: n.description || "",
        weight: n.weight,
        size: Math.round(size),
        opacity: Math.min(1, Math.max(0.4, opacity)),
        concentricWeight: cfg.concentricWeight + (n.weight || 0) * 3,
      };
      return { data };
    });

    const edgeEls = edges.map((e, i) => ({
      data: {
        id: `e-${i}`,
        source: e.source,
        target: e.target,
        relType: e.type,
        edgeLabel: e.description || e.type,
        relDesc: e.description || "",
        edgeColor: EDGE_COLORS[e.type] || EDGE_COLORS.RELATES_TO,
        edgeWidth: Math.max(0.3, (e.weight || 0.3) * 1.2),
        edgeStyle: (e.confidence || 0.5) < 0.5 ? "dashed" : "solid",
      },
    }));

    return [...nodeEls, ...edgeEls];
  }, [nodes, edges]);

  const layout = useMemo<any>(() => ({
    name: "concentric",
    concentric: (node: any) => node.data("concentricWeight"),
    levelWidth: () => 4,
    minNodeSpacing: 22,
    spacingFactor: 1.1,
    padding: 50,
    animate: true,
    animationDuration: 600,
    animationEasing: "ease-out-cubic",
  }), [nodes.length]);

  // Cy event wiring
  const handleCyReady = useCallback((cy: any) => {
    cyRef.current = cy;
    cy.nodes().grabify();

    if (eventsBoundRef.current) return;
    eventsBoundRef.current = true;
    cy.on("destroy", () => { eventsBoundRef.current = false; });

    function resetAll() {
      cy.elements().removeClass("highlighted dimmed hover search-match");
      setTooltip(null);
    }

    // Hover
    cy.on("mouseover", "node", (evt: any) => {
      evt.target.addClass("hover");
      cy.container().style.cursor = "pointer";
      const nodeId: string = evt.target.id();
      const original = nodesRef.current.find((n) => n.name === nodeId) ?? null;
      if (!original) return;
      const { clientX: x, clientY: y } = evt.originalEvent;
      setTooltip({ node: original, x, y });
    });
    cy.on("mouseout", "node", () => {
      cy.container().style.cursor = "default";
      setTooltip(null);
    });
    cy.on("grab", "node", () => { setTooltip(null); });

    // Click node
    cy.on("tap", "node", (evt: any) => {
      const node = evt.target;
      const nodeId: string = node.id();
      const original = nodesRef.current.find((n) => n.name === nodeId) ?? null;

      resetAll();
      const connectedEdges = node.connectedEdges();
      const neighborhood = connectedEdges.connectedNodes();
      node.addClass("highlighted");
      connectedEdges.addClass("highlighted");
      neighborhood.addClass("highlighted");
      cy.elements().not(node).not(connectedEdges).not(neighborhood).addClass("dimmed");

      if (original) onNodeClick(original);

      cy.animate({
        fit: { eles: node.union(neighborhood), padding: 80 },
        duration: 400,
        easing: "ease-out-cubic",
      });
    });

    // Click background
    cy.on("tap", (evt: any) => {
      if (evt.target === cy) {
        resetAll();
        cy.animate({ fit: { eles: cy.elements(), padding: 50 }, duration: 350 });
      }
    });
  }, [onNodeClick]);

  // Search
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.nodes().removeClass("search-match");
    if (!searchTerm.trim()) return;
    const term = searchTerm.toLowerCase();
    cy.nodes().forEach((node: any) => {
      const name = (node.data("fullLabel") || "").toLowerCase();
      if (name.includes(term)) {
        node.addClass("search-match");
        cy.animate({ center: { eles: node }, duration: 300 });
      }
    });
  }, [searchTerm]);

  if (nodes.length === 0) {
    return (
      <div className="w-full h-full rounded-[14px] border border-border bg-[#F0F2F7] flex items-center justify-center">
        <p className="text-sm text-muted-foreground">
          上传论文并开始问答后，系统将逐步构建你的研究方向图谱
        </p>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full rounded-[14px] border border-border overflow-hidden" style={{ background: "#F0F2F7" }}>
      {/* Search */}
      <div className="absolute top-3 left-3 z-10 flex items-center gap-1.5 bg-white/95 backdrop-blur-sm rounded-[8px] border border-border px-2.5 py-1.5 shadow-sm">
        <Search className="w-3.5 h-3.5 text-muted-foreground" />
        <input
          type="text"
          placeholder="搜索节点..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="text-[12px] bg-transparent outline-none w-28 placeholder:text-muted-foreground"
        />
      </div>

      {/* Legend */}
      <div className="absolute top-3 right-3 z-10 bg-white/95 backdrop-blur-sm rounded-[10px] border border-border p-2.5 shadow-sm">
        <p className="text-[9px] text-muted-foreground uppercase tracking-wider font-medium mb-1.5">节点类型</p>
        <div className="space-y-1">
          {Object.entries(TYPE_CONFIG).map(([type, cfg]) => (
            <div key={type} className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full" style={{ background: cfg.color }} />
              <span className="text-[10px] text-foreground">{type === "Field" ? "研究方向" : type === "Topic" ? "研究问题" : "方法/概念"}</span>
            </div>
          ))}
        </div>
        <div className="mt-2 pt-1.5 border-t border-border space-y-0.5">
          <p className="text-[9px] text-muted-foreground">点击节点查看详情</p>
        </div>
      </div>

      {/* Cytoscape */}
      <CytoscapeComponent
        key={`interest-${nodes.length}-${edges.length}`}
        elements={elements}
        stylesheet={buildStylesheet()}
        layout={layout}
        style={{ width: "100%", height: "100%" }}
        cy={handleCyReady}
        userZoomingEnabled
        userPanningEnabled
        autoungrabify={false}
        boxSelectionEnabled={false}
        minZoom={0.2}
        maxZoom={4}
      />

      {/* Hover tooltip */}
      {tooltip && (() => {
        const cfg = getNodeCfg(tooltip.node.type);
        const engagement = getEngagementLabel(tooltip.node.hit_count || 0);
        const lastActive = relativeTime(tooltip.node.last_seen);
        const OFFSET = 14;
        const TIP_W = 240;
        const flipX = tooltip.x + OFFSET + TIP_W > window.innerWidth - 20;
        const left = flipX ? tooltip.x - TIP_W - OFFSET : tooltip.x + OFFSET;
        const top = tooltip.y + OFFSET;
        return (
          <div className="fixed z-50 pointer-events-none" style={{ left, top, width: TIP_W }}>
            <div className="bg-white border border-border rounded-[10px] shadow-lg overflow-hidden">
              <div className="px-3 py-1.5" style={{ background: cfg.color }}>
                <span className="text-[10px] font-semibold text-white/90 uppercase tracking-wider">
                  {tooltip.node.type === "Field" ? "研究方向" : tooltip.node.type === "Topic" ? "研究问题" : "方法/概念"}
                </span>
              </div>
              <div className="p-3 space-y-1.5">
                <p className="text-[12px] font-semibold text-foreground leading-snug">{tooltip.node.name}</p>
                {tooltip.node.description && (
                  <p className="text-[11px] text-muted-foreground leading-relaxed">{tooltip.node.description}</p>
                )}
                <div className="flex items-center gap-3 pt-1">
                  <span className="text-[10px] font-medium" style={{ color: engagement.color }}>
                    {engagement.text}
                  </span>
                  {lastActive && (
                    <span className="text-[10px] text-muted-foreground">
                      {lastActive}提及
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
}
