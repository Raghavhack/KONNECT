import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide } from "d3-force";
import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  RotateCcw,
  FileText,
  User,
  Cpu,
  Sparkles,
  ExternalLink,
  X,
  ArrowRight,
  Search,
  Filter,
  Eye,
  Info,
  Layers,
  ChevronRight,
} from "lucide-react";

export default function GraphCanvas({
  live = false,
  initialNodes = [],
  initialLinks = [],
  className = "",
  onSelectNode,
  selectedNodeId,
  highlightedNodeIds = [],
  focusedNodeId = null,
  onOpenDocument,
}) {
  const containerRef = useRef(null);
  const svgRef = useRef(null);
  const [nodes, setNodes] = useState(initialNodes);
  const [links, setLinks] = useState(initialLinks);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [hoveredLink, setHoveredLink] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [selectedLink, setSelectedLink] = useState(null);
  const [transform, setTransform] = useState({ k: 1, x: 0, y: 0 });
  const [searchQuery, setSearchQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState("ALL");

  const simRef = useRef(null);
  const [, setTick] = useState(0);
  const draggingNodeRef = useRef(null);
  const isPanningRef = useRef(false);
  const panStartRef = useRef({ x: 0, y: 0 });

  const width = 800;
  const height = 540;

  // Sync initial nodes if props change
  useEffect(() => {
    if (initialNodes && initialNodes.length > 0) {
      setNodes(initialNodes.map((n) => ({ ...n })));
    }
  }, [initialNodes]);

  // Sync initial links if props change
  useEffect(() => {
    if (initialLinks && initialLinks.length > 0) {
      setLinks(initialLinks.map((l) => ({ ...l })));
    }
  }, [initialLinks]);

  // Sync selectedNode when selectedNodeId prop changes externally
  useEffect(() => {
    if (selectedNodeId) {
      const match = nodes.find(
        (n) =>
          n.id === selectedNodeId ||
          n.label?.toLowerCase() === selectedNodeId.toLowerCase() ||
          n.name?.toLowerCase() === selectedNodeId.toLowerCase()
      );
      if (match) {
        setSelectedNode(match);
      }
    }
  }, [selectedNodeId, nodes]);

  // Smoothly center and zoom onto focusedNodeId when user clicks an entity/relation
  useEffect(() => {
    if (!focusedNodeId || nodes.length === 0) return;

    const target = nodes.find(
      (n) =>
        n.id === focusedNodeId ||
        n.label?.toLowerCase() === focusedNodeId.toLowerCase() ||
        n.name?.toLowerCase() === focusedNodeId.toLowerCase()
    );

    if (target && target.x !== undefined && target.y !== undefined) {
      setSelectedNode(target);
      onSelectNode?.(target);
      // Smoothly pan camera to center on target node with 1.4x zoom
      setTransform({
        k: 1.4,
        x: width / 2 - target.x * 1.4,
        y: height / 2 - target.y * 1.4,
      });
    }
  }, [focusedNodeId, nodes, onSelectNode]);

  // D3 force simulation setup
  useEffect(() => {
    simRef.current?.stop();
    const nodeIds = new Set(nodes.map((n) => n.id));
    const safeLinks = links
      .map((l) => ({
        ...l,
        source: typeof l.source === "object" ? l.source.id : l.source,
        target: typeof l.target === "object" ? l.target.id : l.target,
      }))
      .filter((l) => nodeIds.has(l.source) && nodeIds.has(l.target));

    const sim = forceSimulation(nodes)
      .force("charge", forceManyBody().strength(-280))
      .force(
        "link",
        forceLink(safeLinks)
          .id((d) => d.id)
          .distance(110)
      )
      .force("center", forceCenter(width / 2, height / 2))
      .force("collide", forceCollide(36))
      .on("tick", () => setTick((t) => (t + 1) % 1000000));

    simRef.current = sim;
    return () => sim.stop();
  }, [nodes.length, links.length]);

  // Zoom controls
  const handleZoomIn = () => {
    setTransform((prev) => {
      const newK = Math.min(3.5, prev.k * 1.25);
      return {
        k: newK,
        x: width / 2 - (width / 2 - prev.x) * (newK / prev.k),
        y: height / 2 - (height / 2 - prev.y) * (newK / prev.k),
      };
    });
  };

  const handleZoomOut = () => {
    setTransform((prev) => {
      const newK = Math.max(0.3, prev.k * 0.8);
      return {
        k: newK,
        x: width / 2 - (width / 2 - prev.x) * (newK / prev.k),
        y: height / 2 - (height / 2 - prev.y) * (newK / prev.k),
      };
    });
  };

  const handleResetZoom = () => {
    setTransform({ k: 1, x: 0, y: 0 });
    setSelectedNode(null);
    setSelectedLink(null);
    setSearchQuery("");
    setActiveFilter("ALL");
  };

  // Wheel zoom handler
  const handleWheel = (e) => {
    e.preventDefault();
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const factor = e.deltaY < 0 ? 1.12 : 0.89;
    setTransform((prev) => {
      const newK = Math.max(0.3, Math.min(3.5, prev.k * factor));
      const newX = mouseX - (mouseX - prev.x) * (newK / prev.k);
      const newY = mouseY - (mouseY - prev.y) * (newK / prev.k);
      return { k: newK, x: newX, y: newY };
    });
  };

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    el.addEventListener("wheel", handleWheel, { passive: false });
    return () => el.removeEventListener("wheel", handleWheel);
  }, []);

  // Helper to convert screen coordinates to SVG coordinates
  const screenToGraphCoords = useCallback(
    (clientX, clientY) => {
      if (!svgRef.current) return { x: 0, y: 0 };
      const pt = svgRef.current.createSVGPoint();
      pt.x = clientX;
      pt.y = clientY;
      const ctm = svgRef.current.getScreenCTM();
      if (!ctm) return { x: 0, y: 0 };
      const svgP = pt.matrixTransform(ctm.inverse());
      return {
        x: (svgP.x - transform.x) / transform.k,
        y: (svgP.y - transform.y) / transform.k,
      };
    },
    [transform]
  );

  // Canvas Pan Handlers
  const handleCanvasPointerDown = (e) => {
    if (e.target.tagName === "svg" || e.target.classList.contains("canvas-background")) {
      isPanningRef.current = true;
      panStartRef.current = {
        x: e.clientX - transform.x,
        y: e.clientY - transform.y,
      };
      if (svgRef.current) {
        svgRef.current.setPointerCapture(e.pointerId);
      }
    }
  };

  // Node Drag Handlers
  const handleNodePointerDown = (e, node) => {
    e.stopPropagation();
    draggingNodeRef.current = node;

    const coords = screenToGraphCoords(e.clientX, e.clientY);
    node.fx = coords.x;
    node.fy = coords.y;
    simRef.current?.alphaTarget(0.25).restart();

    setSelectedNode(node);
    setSelectedLink(null);
    onSelectNode?.(node);

    if (svgRef.current) {
      svgRef.current.setPointerCapture(e.pointerId);
    }
  };

  const handlePointerMove = (e) => {
    if (isPanningRef.current) {
      setTransform((prev) => ({
        ...prev,
        x: e.clientX - panStartRef.current.x,
        y: e.clientY - panStartRef.current.y,
      }));
      return;
    }

    if (draggingNodeRef.current) {
      const coords = screenToGraphCoords(e.clientX, e.clientY);
      draggingNodeRef.current.fx = coords.x;
      draggingNodeRef.current.fy = coords.y;
    }
  };

  const handlePointerUp = () => {
    isPanningRef.current = false;
    if (draggingNodeRef.current) {
      draggingNodeRef.current.fx = null;
      draggingNodeRef.current.fy = null;
      draggingNodeRef.current = null;
      simRef.current?.alphaTarget(0);
    }
  };

  // Color scheme based on entity kind
  const colorFor = (kind) => {
    const k = (kind || "").toUpperCase();
    if (k.includes("DOC")) return "#38BDF8"; // Sky blue
    if (k.includes("PERSON")) return "#4ADE80"; // Mint green
    if (k.includes("TOPIC") || k.includes("CONCEPT")) return "#C084FC"; // Purple
    if (k.includes("ORG") || k.includes("COLLEGE") || k.includes("UNIV")) return "#F472B6"; // Pink
    if (k.includes("SKILL") || k.includes("TECH")) return "#FB923C"; // Orange
    return "#F2B33D"; // Amber
  };

  // Node icon helper
  const renderNodeIcon = (kind) => {
    const k = (kind || "").toUpperCase();
    if (k.includes("DOC")) return <FileText size={10} className="text-white" />;
    if (k.includes("PERSON")) return <User size={10} className="text-white" />;
    if (k.includes("TOPIC") || k.includes("CONCEPT")) return <Sparkles size={10} className="text-white" />;
    return <Cpu size={10} className="text-white" />;
  };

  // Get neighbors of selected node
  const selectedNeighbors = useMemo(() => {
    if (!selectedNode) return [];
    const directLinks = links.filter((l) => {
      const sId = typeof l.source === "object" ? l.source.id : l.source;
      const tId = typeof l.target === "object" ? l.target.id : l.target;
      return sId === selectedNode.id || tId === selectedNode.id;
    });

    const neighborIds = new Set();
    directLinks.forEach((l) => {
      const sId = typeof l.source === "object" ? l.source.id : l.source;
      const tId = typeof l.target === "object" ? l.target.id : l.target;
      if (sId !== selectedNode.id) neighborIds.add(sId);
      if (tId !== selectedNode.id) neighborIds.add(tId);
    });

    return nodes.filter((n) => neighborIds.has(n.id));
  }, [selectedNode, links, nodes]);

  // Filtering & search
  const filteredNodes = useMemo(() => {
    return nodes.filter((n) => {
      const label = (n.label || n.name || n.id).toLowerCase();
      const kind = (n.kind || n.type || "").toUpperCase();

      const matchesSearch = !searchQuery || label.includes(searchQuery.toLowerCase());
      const matchesFilter =
        activeFilter === "ALL" ||
        (activeFilter === "DOCS" && kind.includes("DOC")) ||
        (activeFilter === "PERSONS" && kind.includes("PERSON")) ||
        (activeFilter === "ENTITIES" && !kind.includes("DOC") && !kind.includes("PERSON"));

      return matchesSearch && matchesFilter;
    });
  }, [nodes, searchQuery, activeFilter]);

  const filteredNodeIds = useMemo(() => new Set(filteredNodes.map((n) => n.id)), [filteredNodes]);

  return (
    <div
      ref={containerRef}
      className={`relative h-full w-full select-none overflow-hidden bg-[#0A0B0E] font-sans ${className}`}
      onPointerDown={handleCanvasPointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onDoubleClick={handleResetZoom}
    >
      {/* ── Top Bar Controls: Search & Category Filter ────────────────────── */}
      <div className="absolute top-2.5 left-2.5 right-2.5 z-30 flex flex-wrap items-center justify-between gap-2 pointer-events-none">
        {/* Quick Search */}
        <div className="pointer-events-auto flex items-center gap-1.5 rounded-xl border border-white/10 bg-ink-950/90 px-2.5 py-1.5 shadow-2xl backdrop-blur">
          <Search size={12} className="text-white/40" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search nodes..."
            className="w-28 sm:w-36 bg-transparent text-[11px] text-white placeholder:text-white/30 focus:outline-none"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="text-white/40 hover:text-white"
            >
              <X size={11} />
            </button>
          )}
        </div>

        {/* Category Filter Chips */}
        <div className="pointer-events-auto flex items-center gap-1 rounded-xl border border-white/10 bg-ink-950/90 p-1 shadow-2xl backdrop-blur">
          {["ALL", "DOCS", "ENTITIES", "PERSONS"].map((f) => (
            <button
              key={f}
              onClick={() => setActiveFilter(f)}
              className={`rounded-lg px-2 py-0.5 text-[9px] font-semibold tracking-wide transition ${
                activeFilter === f
                  ? "bg-amber-400 text-ink-950 shadow"
                  : "text-white/50 hover:bg-white/10 hover:text-white"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* ── Zoom & Navigation Overlay Controls ────────────────────────────── */}
      <div className="absolute bottom-3 right-3 z-30 flex items-center gap-1 rounded-xl border border-white/10 bg-ink-950/90 p-1 shadow-2xl backdrop-blur">
        <button
          onClick={handleZoomIn}
          title="Zoom In (+)"
          className="flex h-7 w-7 items-center justify-center rounded-lg text-white/70 hover:bg-white/10 hover:text-white transition cursor-pointer"
        >
          <ZoomIn size={14} />
        </button>
        <button
          onClick={handleZoomOut}
          title="Zoom Out (-)"
          className="flex h-7 w-7 items-center justify-center rounded-lg text-white/70 hover:bg-white/10 hover:text-white transition cursor-pointer"
        >
          <ZoomOut size={14} />
        </button>
        <div className="h-4 w-px bg-white/15 mx-0.5" />
        <button
          onClick={handleResetZoom}
          title="Fit & Reset Camera"
          className="flex items-center gap-1 px-2 h-7 rounded-lg text-[10px] font-mono text-white/70 hover:bg-white/10 hover:text-white transition cursor-pointer"
        >
          <Maximize2 size={12} />
          <span>{Math.round(transform.k * 100)}%</span>
        </button>
      </div>

      {/* ── Visual Legend (Bottom Left) ────────────────────────────────────── */}
      <div className="absolute bottom-3 left-3 z-20 hidden sm:flex items-center gap-2 rounded-xl border border-white/10 bg-ink-950/80 px-2.5 py-1 text-[9px] font-medium text-white/60 backdrop-blur">
        <span className="flex items-center gap-1">
          <span className="h-1.5 w-1.5 rounded-full bg-[#38BDF8]" /> Docs
        </span>
        <span className="flex items-center gap-1">
          <span className="h-1.5 w-1.5 rounded-full bg-[#4ADE80]" /> Persons
        </span>
        <span className="flex items-center gap-1">
          <span className="h-1.5 w-1.5 rounded-full bg-[#FB923C]" /> Skills
        </span>
        <span className="flex items-center gap-1">
          <span className="h-1.5 w-1.5 rounded-full bg-[#F2B33D]" /> Entities
        </span>
      </div>

      {/* ── SVG Knowledge Graph Canvas ─────────────────────────────────────── */}
      <svg
        ref={svgRef}
        viewBox={`0 0 ${width} ${height}`}
        className="h-full w-full cursor-grab active:cursor-grabbing canvas-background"
      >
        <defs>
          <marker
            id="arrowhead-highlight"
            viewBox="0 0 10 10"
            refX="22"
            refY="5"
            markerWidth="5"
            markerHeight="5"
            orient="auto-start-reverse"
          >
            <path d="M 0 1.5 L 10 5 L 0 8.5 z" fill="#F2B33D" />
          </marker>
          <marker
            id="arrowhead-default"
            viewBox="0 0 10 10"
            refX="20"
            refY="5"
            markerWidth="4"
            markerHeight="4"
            orient="auto-start-reverse"
          >
            <path d="M 0 1.5 L 10 5 L 0 8.5 z" fill="rgba(255, 255, 255, 0.3)" />
          </marker>
        </defs>

        <g transform={`translate(${transform.x}, ${transform.y}) scale(${transform.k})`}>
          {/* 1. Links / Relationships */}
          {links.map((l, i) => {
            const s = typeof l.source === "object" ? l.source : nodes.find((n) => n.id === l.source);
            const t = typeof l.target === "object" ? l.target : nodes.find((n) => n.id === l.target);
            if (!s || !t) return null;

            const isSelected = selectedLink === l;
            const isNodeSelected = selectedNode && (selectedNode.id === s.id || selectedNode.id === t.id);
            const isHighlighted =
              highlightedNodeIds.includes(s.id) && highlightedNodeIds.includes(t.id);

            const isDimmed =
              (searchQuery || activeFilter !== "ALL") &&
              (!filteredNodeIds.has(s.id) || !filteredNodeIds.has(t.id));

            const midX = (s.x + t.x) / 2;
            const midY = (s.y + t.y) / 2;
            const relLabel = l.relation_type || l.type || "RELATES_TO";

            return (
              <g
                key={`link-${s.id || s}-${t.id || t}-${i}`}
                className="cursor-pointer transition-opacity duration-200"
                opacity={isDimmed ? 0.15 : 1}
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedLink(l);
                  setSelectedNode(null);
                }}
                onMouseEnter={() => setHoveredLink(l)}
                onMouseLeave={() => setHoveredLink(null)}
              >
                <line
                  x1={s.x}
                  y1={s.y}
                  x2={t.x}
                  y2={t.y}
                  stroke={
                    isSelected || isNodeSelected || isHighlighted
                      ? "#F2B33D"
                      : "rgba(255, 255, 255, 0.22)"
                  }
                  strokeWidth={isSelected || isNodeSelected ? "2.5" : isHighlighted ? "2" : "1.2"}
                  strokeDasharray={isSelected ? "4 2" : "none"}
                  markerEnd={
                    isSelected || isNodeSelected || isHighlighted
                      ? "url(#arrowhead-highlight)"
                      : "url(#arrowhead-default)"
                  }
                />

                {/* Edge Label Badge */}
                {(isNodeSelected || isSelected || hoveredLink === l || transform.k > 1.25) && (
                  <g transform={`translate(${midX}, ${midY})`}>
                    <rect
                      x="-30"
                      y="-8"
                      width="60"
                      height="16"
                      rx="5"
                      fill="#12141A"
                      stroke={isSelected ? "#F2B33D" : "rgba(255,255,255,0.25)"}
                      strokeWidth="1"
                    />
                    <text
                      y="3.5"
                      textAnchor="middle"
                      fill={isSelected ? "#F2B33D" : "#E2E8F0"}
                      fontSize="8"
                      fontFamily="monospace"
                      fontWeight="bold"
                    >
                      {relLabel.length > 12 ? `${relLabel.slice(0, 10)}…` : relLabel}
                    </text>
                  </g>
                )}
              </g>
            );
          })}

          {/* 2. Nodes */}
          {nodes.map((n) => {
            const isSelected = selectedNode?.id === n.id || selectedNodeId === n.id;
            const isHighlighted = highlightedNodeIds.includes(n.id) || focusedNodeId === n.id;
            const isDoc = (n.kind || n.type || "").toUpperCase().includes("DOC");
            const radius = isDoc ? 15 : 12;
            const nodeLabel = n.label || n.name || n.id;
            const isDimmed = !filteredNodeIds.has(n.id);

            return (
              <g
                key={n.id}
                className="cursor-pointer group transition-opacity duration-200"
                opacity={isDimmed ? 0.2 : 1}
                onPointerDown={(e) => handleNodePointerDown(e, n)}
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedNode(n);
                  setSelectedLink(null);
                  onSelectNode?.(n);
                }}
                onMouseEnter={() => setHoveredNode(n)}
                onMouseLeave={() => setHoveredNode(null)}
              >
                {/* Active Focus / Highlight Rotating Ring */}
                {(isSelected || isHighlighted) && (
                  <circle
                    cx={n.x}
                    cy={n.y}
                    r={radius + 8}
                    fill="none"
                    stroke="#F2B33D"
                    strokeWidth="2.5"
                    strokeDasharray="4 2"
                    className="animate-spin origin-center"
                    style={{ animationDuration: "6s" }}
                  />
                )}

                {/* Pulse wave for focused node */}
                {isHighlighted && (
                  <circle
                    cx={n.x}
                    cy={n.y}
                    r={radius + 14}
                    fill="none"
                    stroke="#F2B33D"
                    strokeWidth="1.5"
                    opacity="0.4"
                    className="animate-ping"
                  />
                )}

                {/* Solid Node Body */}
                <circle
                  cx={n.x}
                  cy={n.y}
                  r={radius}
                  fill={colorFor(n.kind || n.type)}
                  opacity={isSelected || isHighlighted ? "1" : "0.94"}
                  stroke={isSelected ? "#FFFFFF" : "rgba(255,255,255,0.4)"}
                  strokeWidth={isSelected ? "2.5" : "1.2"}
                  className="transition-transform duration-200 group-hover:scale-110"
                />

                {/* Node Pill Label (readable dark background) */}
                <g transform={`translate(${n.x}, ${n.y + radius + 11})`}>
                  <rect
                    x={-(nodeLabel.length * 3.5 + 8)}
                    y="-8"
                    width={nodeLabel.length * 7 + 16}
                    height="16"
                    rx="5"
                    fill="rgba(14, 16, 21, 0.88)"
                    stroke={isSelected || isHighlighted ? "#F2B33D" : "rgba(255, 255, 255, 0.15)"}
                    strokeWidth={isSelected || isHighlighted ? "1" : "0.5"}
                    className="pointer-events-none"
                  />
                  <text
                    y="3.5"
                    textAnchor="middle"
                    fill={isSelected || isHighlighted ? "#F2B33D" : "#F8FAFC"}
                    fontSize="9.5"
                    fontFamily="sans-serif"
                    fontWeight={isSelected || isHighlighted ? "bold" : "600"}
                    className="pointer-events-none"
                  >
                    {nodeLabel.length > 20 ? `${nodeLabel.slice(0, 18)}…` : nodeLabel}
                  </text>
                </g>
              </g>
            );
          })}
        </g>
      </svg>

      {/* ── Selected Node Inspector Drawer / Card ─────────────────────────── */}
      {selectedNode && (
        <div className="absolute bottom-3 left-3 right-3 sm:right-auto sm:max-w-xs z-40 rounded-2xl border border-white/15 bg-ink-950/95 p-4 text-parchment-50 shadow-2xl backdrop-blur">
          <div className="flex items-start justify-between gap-2 border-b border-white/10 pb-2.5">
            <div className="flex items-center gap-2">
              <span
                className="flex h-7 w-7 items-center justify-center rounded-lg text-ink-950 font-bold"
                style={{ backgroundColor: colorFor(selectedNode.kind || selectedNode.type) }}
              >
                {renderNodeIcon(selectedNode.kind || selectedNode.type)}
              </span>
              <div>
                <h4 className="text-xs font-bold text-white tracking-tight">
                  {selectedNode.label || selectedNode.name || selectedNode.id}
                </h4>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span
                    className="rounded px-1.5 py-0.2 text-[9px] font-semibold uppercase"
                    style={{
                      backgroundColor: `${colorFor(selectedNode.kind || selectedNode.type)}25`,
                      color: colorFor(selectedNode.kind || selectedNode.type),
                    }}
                  >
                    {selectedNode.kind || selectedNode.type || "ENTITY"}
                  </span>
                  {(selectedNode.importance_score || selectedNode.prize) && (
                    <span className="text-[9px] text-amber-400 font-mono">
                      Prize: {Number(selectedNode.importance_score || selectedNode.prize).toFixed(2)}
                    </span>
                  )}
                </div>
              </div>
            </div>
            <button
              onClick={() => setSelectedNode(null)}
              className="rounded-lg p-1 text-white/50 hover:bg-white/10 hover:text-white transition cursor-pointer"
            >
              <X size={14} />
            </button>
          </div>

          {/* Excerpt / Grounding Description */}
          <div className="mt-2.5 max-h-24 overflow-y-auto text-[11px] leading-relaxed text-white/80">
            {selectedNode.description ? (
              <p className="italic bg-white/5 rounded-lg p-2 border border-white/5">
                "{selectedNode.description}"
              </p>
            ) : (
              <p className="text-white/40">Grounded node maintained via ROLAND GRU vector representations.</p>
            )}
          </div>

          {/* Connected Neighbors Navigation */}
          {selectedNeighbors.length > 0 && (
            <div className="mt-2.5 pt-2 border-t border-white/10">
              <span className="text-[10px] font-semibold uppercase text-white/40 mb-1.5 block">
                Connected Neighbors ({selectedNeighbors.length})
              </span>
              <div className="flex flex-wrap gap-1 max-h-20 overflow-y-auto">
                {selectedNeighbors.map((nbr) => (
                  <button
                    key={nbr.id}
                    onClick={() => {
                      setSelectedNode(nbr);
                      onSelectNode?.(nbr);
                      setTransform({
                        k: 1.4,
                        x: width / 2 - (nbr.x || 0) * 1.4,
                        y: height / 2 - (nbr.y || 0) * 1.4,
                      });
                    }}
                    className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-white/5 hover:bg-white/15 text-[10px] text-white/80 transition cursor-pointer"
                  >
                    <span
                      className="h-1.5 w-1.5 rounded-full"
                      style={{ backgroundColor: colorFor(nbr.kind || nbr.type) }}
                    />
                    <span>{nbr.label || nbr.name || nbr.id}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Source Document Link */}
          {(selectedNode.document_id || selectedNode.source_doc) && (
            <div className="mt-2.5 pt-2 border-t border-white/10 flex items-center justify-between">
              <span className="text-[10px] text-white/50">Source Document:</span>
              <button
                onClick={() => onOpenDocument?.(selectedNode.document_id || selectedNode.source_doc)}
                className="inline-flex items-center gap-1 text-[10px] font-semibold text-amber-400 hover:text-amber-300 transition cursor-pointer"
              >
                <span>{selectedNode.document_id || selectedNode.source_doc}</span>
                <ExternalLink size={10} />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
