import { useEffect, useRef, useState, useCallback } from "react";
import { forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide } from "d3-force";

export default function GraphCanvas({
  live = false,
  initialNodes = [],
  initialLinks = [],
  className = "",
  onSelectNode,
  selectedNodeId,
  highlightedNodeIds = [],
}) {
  const svgRef = useRef(null);
  const [nodes, setNodes] = useState(initialNodes);
  const [links, setLinks] = useState(initialLinks);
  const [hoveredNode, setHoveredNode] = useState(null);
  const simRef = useRef(null);
  const [, setTick] = useState(0);
  const idCounterRef = useRef(initialNodes.length);
  const draggingNodeRef = useRef(null);

  const width = 640;
  const height = 420;

  // Sync initial nodes/links if they change from props
  useEffect(() => {
    if (initialNodes.length > 0) {
      setNodes(initialNodes);
      idCounterRef.current = initialNodes.length;
    }
  }, [initialNodes]);

  useEffect(() => {
    if (initialLinks.length > 0) {
      setLinks(initialLinks);
    }
  }, [initialLinks]);

  // (re)build simulation whenever node/link counts change
  useEffect(() => {
    simRef.current?.stop();
    const nodeIds = new Set(nodes.map((n) => n.id));
    const safeLinks = links
      .map((l) => ({
        source: typeof l.source === "object" ? l.source.id : l.source,
        target: typeof l.target === "object" ? l.target.id : l.target,
      }))
      .filter((l) => nodeIds.has(l.source) && nodeIds.has(l.target));

    const sim = forceSimulation(nodes)
      .force("charge", forceManyBody().strength(-140))
      .force(
        "link",
        forceLink(safeLinks)
          .id((d) => d.id)
          .distance(70)
      )
      .force("center", forceCenter(width / 2, height / 2))
      .force("collide", forceCollide(20))
      .on("tick", () => setTick((t) => (t + 1) % 1000000));

    simRef.current = sim;
    return () => sim.stop();
  }, [nodes.length, links.length]);

  // scripted incremental "edit" event loop for the demo/hero mock
  useEffect(() => {
    if (!live) return;
    const kinds = ["Doc", "Entity", "Person", "Topic"];
    const labels = {
      Doc: ["API Specs.md", "Onboarding.md", "Architecture.pdf", "Runbook.md"],
      Entity: ["AuthToken", "SessionStore", "UserCluster", "QueryPlanner"],
      Person: ["Raghav", "Pranay", "Aarav", "Manas"],
      Topic: ["PCST Retrieval", "Community Detection", "GRU Updates", "Leiden"],
    };

    const interval = setInterval(() => {
      setNodes((prev) => {
        if (prev.length > 22) {
          const [dropped, ...rest] = prev;
          setLinks((l) =>
            l.filter((link) => {
              const s = typeof link.source === "object" ? link.source.id : link.source;
              const t = typeof link.target === "object" ? link.target.id : link.target;
              return s !== dropped.id && t !== dropped.id;
            })
          );
          return rest;
        }
        const n = idCounterRef.current++;
        const id = `n${n}`;
        const kind = kinds[n % kinds.length];
        const kindLabels = labels[kind];
        const label = kindLabels[n % kindLabels.length];
        const parent = prev[Math.floor(Math.random() * prev.length)];
        const next = [
          ...prev,
          {
            id,
            kind,
            label,
            x: parent?.x ? parent.x + (Math.random() * 20 - 10) : width / 2,
            y: parent?.y ? parent.y + (Math.random() * 20 - 10) : height / 2,
          },
        ];
        if (parent) {
          setLinks((l) => [...l, { source: parent.id, target: id }]);
        }
        return next;
      });
    }, 1100);

    return () => clearInterval(interval);
  }, [live]);

  // Drag interaction handlers
  const handlePointerDown = useCallback((e, node) => {
    e.stopPropagation();
    e.target.setPointerCapture(e.pointerId);
    draggingNodeRef.current = node;
    node.fx = node.x;
    node.fy = node.y;
    simRef.current?.alphaTarget(0.3).restart();
  }, []);

  const handlePointerMove = useCallback((e) => {
    if (!draggingNodeRef.current || !svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const scaleX = width / rect.width;
    const scaleY = height / rect.height;
    const mouseX = (e.clientX - rect.left) * scaleX;
    const mouseY = (e.clientY - rect.top) * scaleY;

    draggingNodeRef.current.fx = Math.max(15, Math.min(width - 15, mouseX));
    draggingNodeRef.current.fy = Math.max(15, Math.min(height - 15, mouseY));
  }, []);

  const handlePointerUp = useCallback(() => {
    if (draggingNodeRef.current) {
      draggingNodeRef.current.fx = null;
      draggingNodeRef.current.fy = null;
      draggingNodeRef.current = null;
      simRef.current?.alphaTarget(0);
    }
  }, []);

  const colorFor = (kind) =>
    ({ Doc: "#3B9FE0", Entity: "#F2B33D", Person: "#7FC4EF", Topic: "#E29A1F" }[kind] || "#F2B33D");

  return (
    <div className="relative h-full w-full select-none">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${width} ${height}`}
        className={`h-full w-full ${className}`}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
      >
        {/* Render links */}
        {links.map((l, i) => {
          const s = typeof l.source === "object" ? l.source : nodes.find((n) => n.id === l.source);
          const t = typeof l.target === "object" ? l.target : nodes.find((n) => n.id === l.target);
          if (!s || !t) return null;
          const isHighlighted =
            highlightedNodeIds.includes(s.id) && highlightedNodeIds.includes(t.id);

          return (
            <line
              key={`${s.id || s}-${t.id || t}-${i}`}
              x1={s.x}
              y1={s.y}
              x2={t.x}
              y2={t.y}
              stroke={isHighlighted ? "rgba(242, 179, 61, 0.8)" : "rgba(255,255,255,0.18)"}
              strokeWidth={isHighlighted ? "2" : "1"}
            />
          );
        })}

        {/* Render nodes */}
        {nodes.map((n) => {
          const isSelected = selectedNodeId === n.id;
          const isHighlighted = highlightedNodeIds.includes(n.id);
          const isDoc = n.kind === "Doc";
          const radius = isDoc ? 9 : 6;

          return (
            <g
              key={n.id}
              className="cursor-pointer"
              onPointerDown={(e) => handlePointerDown(e, n)}
              onClick={() => onSelectNode?.(n)}
              onMouseEnter={() => setHoveredNode(n)}
              onMouseLeave={() => setHoveredNode(null)}
            >
              {/* Highlight / selection ring */}
              {(isSelected || isHighlighted) && (
                <circle
                  cx={n.x}
                  cy={n.y}
                  r={radius + 5}
                  fill="none"
                  stroke="#F2B33D"
                  strokeWidth="2"
                  strokeDasharray="3 2"
                  className="animate-spin origin-center"
                />
              )}

              {/* Node body */}
              <circle
                cx={n.x}
                cy={n.y}
                r={radius}
                fill={colorFor(n.kind)}
                opacity={isSelected || isHighlighted ? "1" : "0.9"}
                stroke={isSelected ? "#FFF" : "none"}
                strokeWidth={isSelected ? 1.5 : 0}
              />

              {/* Node label */}
              {isDoc && (
                <text
                  x={n.x}
                  y={n.y - 12}
                  textAnchor="middle"
                  fill="rgba(255,255,255,0.7)"
                  fontSize="9"
                  className="pointer-events-none font-mono font-medium"
                >
                  {n.label || n.id}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Tooltip on hover */}
      {hoveredNode && (
        <div
          className="pointer-events-none absolute z-20 rounded-lg border border-white/10 bg-ink-950/90 px-2.5 py-1.5 text-xs text-parchment-50 shadow-xl backdrop-blur"
          style={{
            left: `${Math.min(80, Math.max(10, (hoveredNode.x / width) * 100))}%`,
            top: `${Math.min(80, Math.max(10, (hoveredNode.y / height) * 100))}%`,
            transform: "translate(-50%, -120%)",
          }}
        >
          <div className="flex items-center gap-1.5 font-medium">
            <span
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: colorFor(hoveredNode.kind) }}
            />
            <span>{hoveredNode.label || hoveredNode.id}</span>
          </div>
          <p className="text-[10px] text-body-300">
            Type: <span className="text-amber-400">{hoveredNode.kind}</span>
          </p>
        </div>
      )}

      {/* Interactive indicator badge */}
      <div className="pointer-events-none absolute bottom-3 right-3 rounded-md bg-white/10 px-2 py-0.5 text-[10px] text-body-300 backdrop-blur">
        Drag nodes · Click to inspect
      </div>
    </div>
  );
}
