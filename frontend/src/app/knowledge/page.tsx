"use client";

import { useState, useEffect, useCallback, useRef, useMemo, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import dynamic from "next/dynamic";
import { Brain, X, RefreshCw, WifiOff } from "lucide-react";
import {
  getGraph,
  getPaperGraph,
  getKeywordGraph,
  getPapersGraph,
  reextractGraph,
  type GraphNode,
  type GraphEdge,
} from "@/lib/api";
import { cn } from "@/lib/utils";

// Cytoscape — client-side only
const CytoscapeComponent = dynamic(
  async () => {
    const cytoscape = (await import("cytoscape")).default;
    const dagre = (await import("cytoscape-dagre")).default;
    try { cytoscape.use(dagre); } catch {}
    return import("react-cytoscapejs");
  },
  { ssr: false }
);

// ── Visual config ────────────────────────────────────────────────────────────
// concentric weight: higher = closer to center
const TYPE_CONFIG: Record<string, {
  color: string;
  border: string;
  size: number;
  concentricWeight: number;
}> = {
  Paper:   { color: "#4F46E5", border: "#6366F1", size: 72, concentricWeight: 10 },
  Method:  { color: "#2563EB", border: "#3B82F6", size: 54, concentricWeight: 7  },
  Problem: { color: "#DC2626", border: "#EF4444", size: 50, concentricWeight: 6  },
  Dataset: { color: "#D97706", border: "#F59E0B", size: 46, concentricWeight: 4  },
  Concept: { color: "#7C3AED", border: "#A78BFA", size: 42, concentricWeight: 3  },
  Keyword: { color: "#059669", border: "#34D399", size: 44, concentricWeight: 3  },
};
const DEFAULT_CFG = { color: "#6B7280", border: "#9CA3AF", size: 42, concentricWeight: 2 };

function getNodeCfg(type: string) {
  return TYPE_CONFIG[type] ?? DEFAULT_CFG;
}

function truncateLabel(label: string, maxLen = 22): string {
  return label.length > maxLen ? label.slice(0, maxLen) + "…" : label;
}

// ── Stylesheet ───────────────────────────────────────────────────────────────
function buildStylesheet() {
  const typeStyles = Object.entries(TYPE_CONFIG).map(([type, cfg]) => ({
    selector: `node[nodeType="${type}"]`,
    style: {
      "background-color": cfg.color,
      "border-color": cfg.border,
      width: cfg.size,
      height: cfg.size,
    } as any,
  }));

  return [
    // ── Base node ──
    {
      selector: "node",
      style: {
        shape: "ellipse",
        "background-color": DEFAULT_CFG.color,
        "border-width": 3,
        "border-color": DEFAULT_CFG.border,
        "border-opacity": 0.6,
        width: DEFAULT_CFG.size,
        height: DEFAULT_CFG.size,
        // Label outside, below the circle
        label: "data(label)",
        "text-valign": "bottom",
        "text-halign": "center",
        "text-margin-y": 6,
        color: "#1F2937",
        "font-size": 11,
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

    // ── Hover ──
    {
      selector: "node.hover",
      style: {
        "border-width": 4,
        "border-opacity": 1,
        "background-opacity": 0.9,
      } as any,
    },

    // ── Selected / highlighted ──
    {
      selector: "node.highlighted",
      style: {
        "border-width": 4,
        "border-opacity": 1,
        "overlay-color": "#fff",
        "overlay-opacity": 0.12,
        "overlay-padding": 4,
      } as any,
    },

    // ── Dimmed nodes ──
    {
      selector: "node.dimmed",
      style: { opacity: 0.2 } as any,
    },

    // ── Base edge ──
    {
      selector: "edge",
      style: {
        width: 1.2,
        "line-color": "#C4CBD8",
        "target-arrow-color": "#C4CBD8",
        "target-arrow-shape": "triangle",
        "arrow-scale": 0.8,
        "curve-style": "bezier",
        opacity: 0.55,
      } as any,
    },

    // ── Highlighted edge ──
    {
      selector: "edge.highlighted",
      style: {
        width: 2.5,
        "line-color": "#6366F1",
        "target-arrow-color": "#6366F1",
        opacity: 1,
        label: "data(relType)",
        "font-size": 9,
        color: "#4F46E5",
        "text-background-color": "#EEF2FF",
        "text-background-opacity": 1,
        "text-background-padding": "3px",
        "text-background-shape": "roundrectangle",
        "text-rotation": "autorotate",
      } as any,
    },

    // ── Dimmed edge ──
    {
      selector: "edge.dimmed",
      style: { opacity: 0.06 } as any,
    },
  ];
}

// ── Main component ───────────────────────────────────────────────────────────
function KnowledgeContent() {
  const searchParams = useSearchParams();
  const paperTitle  = searchParams.get("paper");
  const papersParam = searchParams.get("papers");
  const paperTitles = papersParam ? papersParam.split("||") : null;

  const [viewMode, setViewMode]         = useState<"structure" | "keywords">("keywords");
  const [graphNodes, setGraphNodes]     = useState<GraphNode[]>([]);
  const [graphEdges, setGraphEdges]     = useState<GraphEdge[]>([]);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [isLoading, setIsLoading]       = useState(true);
  const [error, setError]               = useState("");
  const [neo4jUnavailable, setNeo4jUnavailable] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractMsg, setExtractMsg]     = useState("");

  const cyRef = useRef<any>(null);

  // ── Tooltip state ──
  const [tooltip, setTooltip] = useState<{
    node: GraphNode;
    x: number;
    y: number;
  } | null>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  // Keep a ref to latest graphNodes so event callbacks always see fresh data
  const graphNodesRef = useRef<GraphNode[]>([]);
  useEffect(() => { graphNodesRef.current = graphNodes; }, [graphNodes]);

  // Track whether events are already bound to this cy instance
  const eventsBoundRef = useRef(false);

  // ── Cytoscape event wiring ──
  const handleCyReady = useCallback((cy: any) => {
    cyRef.current = cy;

    // Ensure nodes are draggable
    cy.nodes().grabify();

    // Guard: only bind once per cy instance
    if (eventsBoundRef.current) return;
    eventsBoundRef.current = true;

    // Unbind on destroy so we reset the guard for the next cy instance
    cy.on("destroy", () => { eventsBoundRef.current = false; });

    function resetAll() {
      cy.elements().removeClass("highlighted dimmed hover");
      setSelectedNode(null);
      setTooltip(null);
    }

    // Hover → tooltip
    // mousemove is intentionally NOT used here — calling setTooltip on every
    // mousemove triggers React re-renders that interrupt Cytoscape's drag state machine
    cy.on("mouseover", "node", (evt: any) => {
      evt.target.addClass("hover");
      cy.container().style.cursor = "pointer";
      const nodeId: string = evt.target.id();
      const original = graphNodesRef.current.find((n) => n.id === nodeId) ?? null;
      if (!original) return;
      const { clientX: x, clientY: y } = evt.originalEvent;
      setTooltip({ node: original, x, y });
    });
    cy.on("mouseout", "node", () => {
      cy.container().style.cursor = "default";
      setTooltip(null);
    });
    // Hide tooltip the moment user starts dragging
    cy.on("grab", "node", () => { setTooltip(null); });

    // Click node → highlight + detail panel
    cy.on("tap", "node", (evt: any) => {
      const node = evt.target;
      const nodeId: string = node.id();
      const original = graphNodesRef.current.find((n) => n.id === nodeId) ?? null;

      cy.elements().removeClass("highlighted dimmed hover");
      setTooltip(null);

      const connectedEdges = node.connectedEdges();
      const neighborhood   = connectedEdges.connectedNodes();
      node.addClass("highlighted");
      connectedEdges.addClass("highlighted");
      neighborhood.addClass("highlighted");
      cy.elements().not(node).not(connectedEdges).not(neighborhood).addClass("dimmed");

      setSelectedNode(original);

      cy.animate({
        fit: { eles: node.union(neighborhood), padding: 80 },
        duration: 400,
        easing: "ease-out-cubic",
      });
    });

    // Click background → reset
    cy.on("tap", (evt: any) => {
      if (evt.target === cy) {
        resetAll();
        cy.animate({ fit: { eles: cy.elements(), padding: 60 }, duration: 350 });
      }
    });
  }, []); // empty deps — reads graphNodes via ref

  // ── Data loading ──
  useEffect(() => {
    async function load() {
      setIsLoading(true);
      setError("");
      setNeo4jUnavailable(false);
      setSelectedNode(null);
      try {
        let data;
        if (paperTitle)       data = await getPaperGraph(paperTitle);
        else if (paperTitles) data = await getPapersGraph(paperTitles);
        else if (viewMode === "keywords") data = await getKeywordGraph();
        else                  data = await getGraph();

        if ((data as any).neo4j_unavailable) {
          setNeo4jUnavailable(true);
          setGraphNodes([]); setGraphEdges([]);
        } else {
          setGraphNodes(data.nodes);
          setGraphEdges(data.edges);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "加载失败");
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, [paperTitle, papersParam, viewMode]);

  // ── Cytoscape elements — memoized to prevent unnecessary patchElements calls ──
  const elements = useMemo(() => [
    ...graphNodes.filter(Boolean).map((n) => ({
      data: {
        id: n.id,
        label: truncateLabel(n.label),
        fullLabel: n.label,
        nodeType: n.type,
        properties: n.properties,
        concentricWeight: getNodeCfg(n.type).concentricWeight,
      },
    })),
    ...graphEdges.filter(Boolean).map((e, i) => ({
      data: { id: `e-${i}`, source: e.source, target: e.target, relType: e.type },
    })),
  ], [graphNodes, graphEdges]);

  // ── Layout — memoized so it only changes when data/mode actually changes,
  // preventing patchLayout from re-running on every React re-render ──
  const layout = useMemo<any>(() => paperTitle
    ? {
        name: "breadthfirst",
        directed: true,
        circle: true,
        spacingFactor: 1.6,
        padding: 60,
        animate: true,
        animationDuration: 600,
        animationEasing: "ease-out-cubic",
      }
    : {
        name: "concentric",
        concentric: (node: any) => node.data("concentricWeight"),
        levelWidth: () => 2,
        minNodeSpacing: 40,
        spacingFactor: 1.8,
        padding: 60,
        animate: true,
        animationDuration: 700,
        animationEasing: "ease-out-cubic",
      },
  [paperTitle, viewMode, graphNodes.length]); // eslint-disable-line

  // ── Loading / error states ──
  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-sm text-muted-foreground animate-pulse">Loading knowledge graph...</div>
      </div>
    );
  }

  if (neo4jUnavailable) {
    return (
      <div className="h-full flex flex-col items-center justify-center">
        <div className="w-16 h-16 rounded-2xl bg-orange-50 flex items-center justify-center mb-5">
          <WifiOff className="w-8 h-8 text-orange-500" />
        </div>
        <h2 className="text-lg font-semibold mb-2">Knowledge Graph Unavailable</h2>
        <p className="text-sm text-muted-foreground text-center max-w-sm leading-relaxed">
          Neo4j is not connected. Start Neo4j and restart the backend to enable this feature.
        </p>
        <p className="text-[11px] text-muted-foreground mt-3 font-mono bg-secondary px-3 py-1.5 rounded-[8px]">
          NEO4J_URI={process.env.NEXT_PUBLIC_NEO4J_URI || "bolt://localhost:7687"}
        </p>
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
        <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-5">
          <Brain className="w-8 h-8 text-primary" />
        </div>
        <h2 className="text-lg font-semibold mb-2">No knowledge graph yet</h2>
        {paperTitle ? (
          <>
            <p className="text-sm text-muted-foreground text-center max-w-sm leading-relaxed mb-5">
              No graph data found for this paper. Extraction may have failed during upload.
            </p>
            <button
              onClick={async () => {
                setIsExtracting(true); setExtractMsg("");
                try {
                  const result = await reextractGraph(paperTitle);
                  setExtractMsg(`Extracted ${result.methods} methods, ${result.concepts} concepts`);
                  setIsLoading(true);
                  const data = await getPaperGraph(paperTitle);
                  setGraphNodes(data.nodes); setGraphEdges(data.edges);
                  setIsLoading(false);
                } catch (err) {
                  setExtractMsg(err instanceof Error ? err.message : "Extraction failed");
                } finally { setIsExtracting(false); }
              }}
              disabled={isExtracting}
              className="h-9 px-4 rounded-[10px] bg-primary text-white text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors flex items-center gap-2"
            >
              {isExtracting
                ? <><RefreshCw className="w-4 h-4 animate-spin" />Extracting...</>
                : <><RefreshCw className="w-4 h-4" />Re-extract Graph</>}
            </button>
            {extractMsg && <p className="text-[12px] text-muted-foreground mt-3">{extractMsg}</p>}
          </>
        ) : (
          <p className="text-sm text-muted-foreground">Upload papers to build the knowledge graph.</p>
        )}
      </div>
    );
  }

  return (
    <div className="h-full flex">
      {/* ── Graph canvas ── */}
      <div className="flex-1 relative" style={{ background: "#F0F2F7" }}>

        {/* Legend */}
        <div className="absolute top-4 left-4 z-10 bg-white/95 backdrop-blur-sm rounded-[12px] border border-border p-3 shadow-sm">
          {paperTitle && (
            <div className="mb-2 pb-2 border-b border-border">
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Paper</p>
              <p className="text-[11px] text-foreground font-medium mt-0.5 max-w-[160px] truncate">{paperTitle}</p>
            </div>
          )}
          {paperTitles && (
            <div className="mb-2 pb-2 border-b border-border">
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider">
                Comparing {paperTitles.length} papers
              </p>
              {paperTitles.map((t, i) => (
                <p key={i} className="text-[10px] text-foreground mt-0.5 max-w-[160px] truncate">• {t}</p>
              ))}
            </div>
          )}

          {/* View mode (global only) */}
          {!paperTitle && !paperTitles && (
            <div className="mb-3 pb-2 border-b border-border">
              <div className="flex items-center bg-secondary rounded-[8px] p-0.5">
                {(["keywords", "structure"] as const).map((m) => (
                  <button
                    key={m}
                    onClick={() => setViewMode(m)}
                    className={cn(
                      "flex-1 text-[10px] font-medium px-2 py-1 rounded-[6px] transition-all capitalize",
                      viewMode === m
                        ? "bg-white shadow-sm text-foreground"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >{m}</button>
                ))}
              </div>
            </div>
          )}

          <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2 font-medium">Node Types</p>
          <div className="space-y-1.5">
            {Object.entries(TYPE_CONFIG).map(([type, cfg]) => (
              <div key={type} className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full" style={{ background: cfg.color }} />
                <span className="text-[11px] text-foreground">{type}</span>
              </div>
            ))}
          </div>
          <div className="mt-3 pt-2 border-t border-border">
            <p className="text-[10px] text-muted-foreground">Click a node to explore</p>
          </div>
        </div>

        {/* Cytoscape */}
        <CytoscapeComponent
          key={`${paperTitle ?? "global"}-${viewMode}-${graphNodes.length}`}
          elements={elements}
          stylesheet={buildStylesheet()}
          layout={layout}
          style={{ width: "100%", height: "100%" }}
          cy={handleCyReady}
          userZoomingEnabled
          userPanningEnabled
          autoungrabify={false}
          boxSelectionEnabled={false}
          minZoom={0.15}
          maxZoom={4}
        />

        {/* Hover tooltip */}
        {tooltip && (() => {
          const cfg = getNodeCfg(tooltip.node.type);
          const desc = tooltip.node.properties.description;
          const authors = tooltip.node.properties.authors;
          const fullName = tooltip.node.properties.title || tooltip.node.properties.name || tooltip.node.label;
          // Compute position: keep tooltip inside viewport
          const OFFSET = 16;
          const TIP_W = 260;
          const container = cyRef.current?.container();
          const rect = container?.getBoundingClientRect();
          const rightEdge = rect ? rect.right : window.innerWidth;
          const flipX = tooltip.x + OFFSET + TIP_W > rightEdge - 8;
          const left = flipX ? tooltip.x - TIP_W - OFFSET : tooltip.x + OFFSET;
          const top  = tooltip.y + OFFSET;
          return (
            <div
              ref={tooltipRef}
              className="fixed z-50 pointer-events-none"
              style={{ left, top, width: TIP_W }}
            >
              <div className="bg-white border border-border rounded-[12px] shadow-lg overflow-hidden">
                {/* Type badge header */}
                <div
                  className="px-3 py-2 flex items-center gap-2"
                  style={{ background: cfg.color }}
                >
                  <span className="text-[10px] font-semibold text-white/80 uppercase tracking-wider">
                    {tooltip.node.type}
                  </span>
                </div>
                <div className="p-3 space-y-2">
                  {/* Full name */}
                  <p className="text-[12px] font-semibold text-foreground leading-snug">
                    {fullName}
                  </p>
                  {/* Description */}
                  {desc && (
                    <p className="text-[11px] text-muted-foreground leading-relaxed">
                      {desc}
                    </p>
                  )}
                  {/* Authors */}
                  {authors && (
                    <p className="text-[10px] text-muted-foreground leading-relaxed">
                      {authors}
                    </p>
                  )}
                </div>
              </div>
            </div>
          );
        })()}
      </div>

      {/* ── Detail panel ── */}
      {selectedNode && (
        <motion.div
          initial={{ x: 24, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: 24, opacity: 0 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className="w-80 border-l border-border bg-white shrink-0 flex flex-col"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-5 pt-5 pb-3 border-b border-border shrink-0">
            <span
              className="text-[11px] font-medium px-2.5 py-1 rounded-full text-white"
              style={{ background: getNodeCfg(selectedNode.type).color }}
            >
              {selectedNode.type}
            </span>
            <button
              onClick={() => {
                setSelectedNode(null);
                const cy = cyRef.current;
                if (cy) {
                  cy.elements().removeClass("highlighted dimmed hover");
                  cy.animate({ fit: { eles: cy.elements(), padding: 60 }, duration: 350 });
                }
              }}
              className="w-6 h-6 rounded flex items-center justify-center hover:bg-secondary"
            >
              <X className="w-3.5 h-3.5 text-muted-foreground" />
            </button>
          </div>

          {/* Scrollable body */}
          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">

            {/* Full title — no truncation */}
            <div>
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-medium mb-1">
                {selectedNode.type === "Paper" ? "Title" : "Name"}
              </p>
              <p className="text-[13px] font-semibold leading-snug text-foreground">
                {selectedNode.properties.title || selectedNode.properties.name || selectedNode.label}
              </p>
            </div>

            {/* Description — most important field, prominent */}
            {selectedNode.properties.description && (
              <div className="rounded-[10px] bg-secondary/60 p-3">
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-medium mb-1.5">
                  Description
                </p>
                <p className="text-[12px] text-foreground leading-relaxed">
                  {selectedNode.properties.description}
                </p>
              </div>
            )}

            {/* Authors (Paper only) */}
            {selectedNode.properties.authors && (
              <div>
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-medium mb-1">
                  Authors
                </p>
                <p className="text-[12px] text-foreground leading-relaxed">
                  {selectedNode.properties.authors}
                </p>
              </div>
            )}

            {/* Other properties — skip already-shown ones */}
            {Object.entries(selectedNode.properties)
              .filter(([key, val]) =>
                val &&
                !["name", "title", "description", "authors"].includes(key)
              )
              .map(([key, value]) => (
                <div key={key}>
                  <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-medium mb-1">
                    {key}
                  </p>
                  <p className="text-[12px] text-foreground leading-relaxed">{String(value)}</p>
                </div>
              ))}

            {/* Relations */}
            {(() => {
              const rels = graphEdges.filter(
                (e) => e.source === selectedNode.id || e.target === selectedNode.id
              );
              if (rels.length === 0) return null;
              return (
                <div className="pt-2 border-t border-border">
                  <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-medium mb-2">
                    Relations ({rels.length})
                  </p>
                  <div className="space-y-2">
                    {rels.map((e, i) => {
                      const isOut  = e.source === selectedNode.id;
                      const otherId = isOut ? e.target : e.source;
                      const other  = graphNodes.find((n) => n.id === otherId);
                      const cfg    = getNodeCfg(other?.type ?? "");
                      return (
                        <div key={i} className="flex items-start gap-2">
                          {/* Direction + type badge */}
                          <div className="flex items-center gap-1 mt-0.5 shrink-0">
                            <span className="text-[10px] text-muted-foreground">
                              {isOut ? "→" : "←"}
                            </span>
                            <span
                              className="text-[9px] font-medium px-1.5 py-0.5 rounded text-white"
                              style={{ background: "#6366F1" }}
                            >
                              {e.type}
                            </span>
                          </div>
                          {/* Other node — full label, no truncate */}
                          <div className="flex items-center gap-1.5 min-w-0">
                            <div
                              className="w-2 h-2 rounded-full shrink-0"
                              style={{ background: cfg.color }}
                            />
                            <span className="text-[11px] text-foreground break-words">
                              {other?.properties.title || other?.properties.name || other?.label || "?"}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })()}
          </div>
        </motion.div>
      )}
    </div>
  );
}

export default function KnowledgePage() {
  return (
    <Suspense fallback={<div className="h-full" />}>
      <KnowledgeContent />
    </Suspense>
  );
}
