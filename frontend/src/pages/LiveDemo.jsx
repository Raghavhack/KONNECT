import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { Link, useSearchParams, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Send,
  Zap,
  PlusSquare,
  Sparkles,
  Server,
  Lock,
  ArrowRight,
  Terminal,
  Activity,
  CheckCircle2,
  ShieldCheck,
  MessageSquare,
  ChevronRight,
  ChevronDown,
  LayoutGrid,
  X,
  LogOut,
  User,
  Network,
  PlusCircle,
  ArrowLeft,
  Cloud,
  UploadCloud,
  FileText,
  RefreshCw,
  ExternalLink,
  Maximize2,
  Minimize2,
  Cpu,
  Layers,
  ArrowUpRight,
  Eye,
  FileSearch,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import GraphCanvas from "../components/shared/GraphCanvas";
import {
  healthCheck,
  sendQuery,
  triggerEdit,
  createConversation,
  uploadDocument,
  syncGDrive,
  syncOneDrive,
} from "../api/mockApi";

// ─── Constants ────────────────────────────────────────────────────────────────

const PRESET_QUERIES = [
  "tell me about pranay mehta",
  "which college ?",
  "What changed in the onboarding doc?",
  "Which entities connect to AuthService?",
];

const INITIAL_NODES = [
  { id: "root", kind: "Doc", label: "Onboarding.md", name: "Onboarding.md", x: 320, y: 210 },
  { id: "e1", kind: "Entity", label: "AuthService", name: "AuthService", x: 240, y: 150 },
  { id: "e2", kind: "Person", label: "Raghav", name: "Raghav", x: 400, y: 270 },
  { id: "e3", kind: "Topic", label: "PCST Subgraph", name: "PCST Subgraph", x: 420, y: 120 },
];

const INITIAL_LINKS = [
  { source: "root", target: "e1", type: "DEFINES" },
  { source: "root", target: "e2", type: "AUTHORED_BY" },
  { source: "e1", target: "e3", type: "OPTIMIZED_WITH" },
];

const BADGE_COLORS = {
  WEBHOOK: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  QUEUE: "bg-sky-500/15 text-sky-400 border-sky-500/30",
  NEO4J: "bg-amber-400/15 text-amber-400 border-amber-400/30",
  "GNN-GRU": "bg-purple-500/15 text-purple-400 border-purple-500/30",
  PCST: "bg-yellow-400/15 text-yellow-300 border-yellow-400/30",
  QUERY: "bg-yellow-400/15 text-yellow-300 border-yellow-400/30",
  PARSER: "bg-teal-400/15 text-teal-300 border-teal-400/30",
  LLM: "bg-pink-400/15 text-pink-300 border-pink-400/30",
  CACHE: "bg-indigo-400/15 text-indigo-300 border-indigo-400/30",
  CONNECTED: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
};

const getBadgeColor = (tag) =>
  BADGE_COLORS[tag] ?? "bg-white/10 text-white/50 border-white/10";

// Helper color for entity types
function colorForKind(kind = "") {
  const k = String(kind).toUpperCase();
  if (k.includes("DOC")) return "#38BDF8"; // Sky blue
  if (k.includes("PERSON")) return "#4ADE80"; // Mint green
  if (k.includes("TOPIC") || k.includes("CONCEPT")) return "#C084FC"; // Purple
  if (k.includes("ORG") || k.includes("COLLEGE") || k.includes("UNIV")) return "#F472B6"; // Pink
  if (k.includes("SKILL") || k.includes("TECH")) return "#FB923C"; // Orange
  return "#F2B33D"; // Amber
}

// ─── In-Text Formatter with Clickable Entities & Documents ────────────────────

function FormattedAnswer({ text, onSelectEntity, onOpenDocument }) {
  if (!text) return null;

  // Regex matches:
  // 1. Bracketed entities: [Entity Name] (optional (ENTITY) or [Relevance Prize: ...])
  // 2. Document names: doc_123_Resume.pdf, Architecture.pdf, etc.
  // 3. Bold markdown: **bold text**
  const regex = /(\[(?:[^\]]+)\](?:\s*\((?:ENTITY|PERSON|CONCEPT|DOC|TECH|TOPIC|ORGANIZATION)\))?(?:\s*\[Relevance Prize:[^\]]+\])?)|(\b(?:doc_\d+_[A-Za-z0-9_.-]+|[A-Za-z0-9_.-]+\.(?:pdf|docx|txt|md))\b)|(\*\*[^*]+\*\*)/gi;

  const paragraphs = text.split("\n");

  return (
    <div className="space-y-2">
      {paragraphs.map((para, pIdx) => {
        if (!para.trim()) return <div key={pIdx} className="h-1.5" />;

        const parts = [];
        let lastIndex = 0;
        let match;
        regex.lastIndex = 0;

        while ((match = regex.exec(para)) !== null) {
          if (match.index > lastIndex) {
            parts.push(para.slice(lastIndex, match.index));
          }

          const [fullMatch, entityToken, docToken, boldToken] = match;

          if (entityToken) {
            const nameMatch = entityToken.match(/^\[([^\]]+)\]/);
            const entityName = nameMatch ? nameMatch[1].trim() : entityToken.replace(/[[\]]/g, "").trim();

            const prizeMatch = entityToken.match(/\[Relevance Prize:\s*([^\]]+)\]/);
            const prize = prizeMatch ? prizeMatch[1].trim() : null;

            parts.push(
              <button
                key={`ent-${match.index}`}
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectEntity(entityName);
                }}
                className="inline-flex items-center gap-1 mx-0.5 px-1.5 py-0.5 rounded-md bg-amber-400/20 hover:bg-amber-400 text-amber-900 hover:text-ink-950 font-medium text-[11px] border border-amber-400/40 hover:border-amber-500 shadow-2xs transition group align-baseline cursor-pointer"
                title={`Click to focus "${entityName}" in Knowledge Graph`}
              >
                <span className="h-1.5 w-1.5 rounded-full bg-amber-500 group-hover:scale-125 transition-transform" />
                <span className="font-semibold">{entityName}</span>
                {prize && (
                  <span className="text-[9px] text-amber-700/80 font-mono">
                    {prize}
                  </span>
                )}
              </button>
            );
          } else if (docToken) {
            const cleanName = docToken.replace(/^doc_\d+_/, "");
            parts.push(
              <button
                key={`doc-${match.index}`}
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onOpenDocument(docToken);
                }}
                className="inline-flex items-center gap-1 mx-0.5 px-1.5 py-0.5 rounded-md bg-sky-500/15 hover:bg-sky-500 text-sky-800 hover:text-white font-medium text-[11px] border border-sky-400/30 transition group align-baseline cursor-pointer"
                title={`Click to view document excerpt: "${cleanName}"`}
              >
                <FileText size={11} className="text-sky-600 group-hover:text-white" />
                <span className="underline decoration-sky-400/50">{cleanName}</span>
              </button>
            );
          } else if (boldToken) {
            parts.push(
              <strong key={`bold-${match.index}`} className="font-semibold text-ink-950">
                {boldToken.slice(2, -2)}
              </strong>
            );
          }

          lastIndex = regex.lastIndex;
        }

        if (lastIndex < para.length) {
          parts.push(para.slice(lastIndex));
        }

        return (
          <p key={pIdx} className="leading-relaxed">
            {parts}
          </p>
        );
      })}
    </div>
  );
}

// ─── Structured Message Bubble ────────────────────────────────────────────────

function MessageBubble({
  message,
  onSelectEntity,
  onSelectRelation,
  onOpenDocument,
}) {
  const isUser = message.role === "user";
  const [evidenceOpen, setEvidenceOpen] = useState(true);

  if (isUser) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2 }}
        className="ml-auto flex max-w-[78%] flex-col"
      >
        <div className="rounded-2xl rounded-tr-sm bg-amber-400 px-4 py-3 text-sm leading-relaxed text-ink-950 shadow-sm font-medium">
          {message.text}
        </div>
      </motion.div>
    );
  }

  // Aggregate relevant entities from subgraph and citations
  const subgraphNodes = message.subgraph?.nodes || [];
  const citations = message.citations || [];

  // Deduplicated list of entities
  const relevantEntities = useMemo(() => {
    const map = new Map();
    citations.forEach((c) => {
      const name = c.entity_name || c.label || c.id;
      if (name && !map.has(name.toLowerCase())) {
        map.set(name.toLowerCase(), {
          id: c.id,
          name,
          kind: c.entity_type || c.kind || "Entity",
          prize: c.score || c.prize,
          doc: c.document_id,
        });
      }
    });

    subgraphNodes.forEach((n) => {
      const name = n.name || n.label || n.id;
      if (name && !map.has(name.toLowerCase())) {
        map.set(name.toLowerCase(), {
          id: n.id,
          name,
          kind: n.type || n.kind || "Entity",
          prize: message.subgraph?.prizes?.[n.id] || n.prize,
          doc: n.document_id,
        });
      }
    });

    return Array.from(map.values());
  }, [citations, subgraphNodes, message.subgraph]);

  // Relevant relationships from subgraph edges
  const relevantEdges = useMemo(() => {
    const edges = message.subgraph?.edges || [];
    return edges.map((e) => {
      const src = typeof e.source === "object" ? e.source.id : e.source;
      const tgt = typeof e.target === "object" ? e.target.id : e.target;
      return {
        source: src,
        target: tgt,
        type: e.type || e.relationship || "CONNECTED_TO",
        cost: e.cost,
      };
    });
  }, [message.subgraph]);

  // Source documents
  const sourceDocs = useMemo(() => {
    const docs = new Set();
    citations.forEach((c) => {
      if (c.document_id) docs.add(c.document_id);
      if (c.kind === "Doc" || c.entity_type === "Doc") docs.add(c.label || c.id);
    });
    subgraphNodes.forEach((n) => {
      if (n.document_id) docs.add(n.document_id);
      if (n.kind === "Doc" || n.type === "Doc") docs.add(n.name || n.label || n.id);
    });
    return Array.from(docs);
  }, [citations, subgraphNodes]);

  const hasEvidence =
    relevantEntities.length > 0 || relevantEdges.length > 0 || sourceDocs.length > 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="mr-auto flex max-w-[85%] flex-col gap-2 w-full"
    >
      {/* AI badge */}
      <div className="flex items-center gap-1.5">
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-amber-400 text-[9px] font-bold text-ink-950">
          K
        </span>
        <span className="text-[10px] font-semibold text-body-500">KONNECT AI</span>
      </div>

      {/* Main Answer Bubble */}
      <div className="rounded-2xl rounded-tl-sm border border-black/8 bg-white px-4 py-3.5 text-sm leading-relaxed text-ink-950 shadow-sm">
        {/* Solution text with clickable entities & documents */}
        <FormattedAnswer
          text={message.text}
          onSelectEntity={onSelectEntity}
          onOpenDocument={onOpenDocument}
        />

        {/* Knowledge Graph Grounding & Subgraph Evidence Card */}
        {hasEvidence && (
          <div className="mt-3.5 rounded-xl border border-black/8 bg-[#FBF9F5] p-3 text-ink-950">
            <div className="flex items-center justify-between pb-2 border-b border-black/5">
              <button
                onClick={() => setEvidenceOpen((v) => !v)}
                className="flex items-center gap-1.5 text-xs font-semibold text-ink-950 hover:text-amber-600 transition"
              >
                <Network size={14} className="text-amber-500" />
                <span>Knowledge Graph Evidence (PCST Subgraph)</span>
                {evidenceOpen ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
              </button>
              <div className="flex items-center gap-2 text-[10px] text-body-500">
                <span className="flex items-center gap-1 font-medium">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                  {relevantEntities.length} Entities
                </span>
                {relevantEdges.length > 0 && (
                  <span className="flex items-center gap-1 font-medium">
                    <span className="h-1.5 w-1.5 rounded-full bg-sky-500" />
                    {relevantEdges.length} Relations
                  </span>
                )}
              </div>
            </div>

            {evidenceOpen && (
              <div className="mt-2.5 space-y-3">
                {/* 1. Relevant Entities */}
                {relevantEntities.length > 0 && (
                  <div>
                    <div className="text-[10px] font-semibold uppercase tracking-wider text-body-500 mb-1.5 flex items-center justify-between">
                      <span>Relevant Entities (Click to focus node)</span>
                      <span className="text-[9px] text-amber-600 font-normal">Interactive Node Target</span>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {relevantEntities.map((ent, idx) => (
                        <button
                          key={idx}
                          onClick={() => onSelectEntity(ent.name || ent.id)}
                          className="group inline-flex items-center gap-1.5 rounded-lg border border-black/8 bg-white px-2 py-1 text-xs text-ink-950 shadow-2xs hover:border-amber-400 hover:bg-amber-400/10 hover:shadow-xs transition"
                          title={`Focus and center "${ent.name}" in Knowledge Graph`}
                        >
                          <span
                            className="h-2 w-2 rounded-full"
                            style={{ backgroundColor: colorForKind(ent.kind) }}
                          />
                          <span className="font-semibold text-[11px] group-hover:text-amber-900">
                            {ent.name}
                          </span>
                          <span className="text-[9px] font-medium uppercase px-1 py-0.2 rounded bg-black/5 text-body-500">
                            {ent.kind}
                          </span>
                          {ent.prize && (
                            <span className="text-[9px] font-mono text-amber-700 bg-amber-400/20 px-1 rounded">
                              ★ {Number(ent.prize).toFixed(2)}
                            </span>
                          )}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* 2. Relevant Relationships */}
                {relevantEdges.length > 0 && (
                  <div>
                    <div className="text-[10px] font-semibold uppercase tracking-wider text-body-500 mb-1.5">
                      Relevant Relationships (Click to highlight link)
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {relevantEdges.map((edge, idx) => (
                        <button
                          key={idx}
                          onClick={() => onSelectRelation(edge)}
                          className="group inline-flex items-center gap-1.5 rounded-lg border border-black/8 bg-white px-2.5 py-1 text-[11px] text-ink-950 shadow-2xs hover:border-sky-400 hover:bg-sky-500/10 transition"
                          title={`Highlight relationship "${edge.source} -> ${edge.type} -> ${edge.target}"`}
                        >
                          <span className="font-medium text-ink-950">{edge.source}</span>
                          <span className="flex items-center text-[9px] font-mono font-bold text-sky-600 bg-sky-500/15 px-1 py-0.2 rounded">
                            ── {edge.type} ──►
                          </span>
                          <span className="font-medium text-ink-950">{edge.target}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* 3. Source Documents */}
                {sourceDocs.length > 0 && (
                  <div>
                    <div className="text-[10px] font-semibold uppercase tracking-wider text-body-500 mb-1.5">
                      Source Documents (Click to view excerpt)
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {sourceDocs.map((doc, idx) => {
                        const cleanDoc = doc.replace(/^doc_\d+_/, "");
                        return (
                          <button
                            key={idx}
                            onClick={() => onOpenDocument(doc)}
                            className="inline-flex items-center gap-1.5 rounded-lg border border-black/8 bg-white px-2.5 py-1 text-[11px] text-sky-800 hover:bg-sky-50 hover:border-sky-400 transition"
                            title={`Open document grounding excerpt for "${cleanDoc}"`}
                          >
                            <FileText size={12} className="text-sky-600" />
                            <span className="font-medium">{cleanDoc}</span>
                            <ArrowUpRight size={11} className="text-sky-500 opacity-60" />
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
}

// ─── Document Excerpt Slide-Over Modal ────────────────────────────────────────

function DocumentExcerptModal({ doc, nodes, onClose, onSelectNode }) {
  if (!doc) return null;

  // Filter nodes that belong to this document
  const relatedNodes = nodes.filter(
    (n) =>
      n.document_id === doc.id ||
      n.document_id === doc.fullName ||
      (doc.title && n.label?.toLowerCase().includes(doc.title.toLowerCase()))
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 10 }}
        className="relative w-full max-w-xl rounded-3xl border border-black/10 bg-white p-6 shadow-2xl overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-start justify-between border-b border-black/8 pb-4">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-sky-500/15 text-sky-600 font-bold">
              <FileSearch size={22} />
            </div>
            <div>
              <h3 className="text-base font-bold text-ink-950 tracking-tight">
                {doc.title || doc.id}
              </h3>
              <p className="text-xs text-body-500">
                Source Document Grounded in Knowledge Graph
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-xl text-black/40 hover:bg-black/5 hover:text-ink-950 transition"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="mt-4 space-y-4 max-h-[60vh] overflow-y-auto pr-1">
          {/* Metadata pill */}
          <div className="flex flex-wrap items-center gap-2 text-[11px]">
            <span className="rounded-md bg-emerald-500/15 px-2 py-0.5 font-medium text-emerald-700">
              Synced & Verified
            </span>
            <span className="rounded-md bg-black/5 px-2 py-0.5 font-mono text-body-500">
              ID: {doc.id}
            </span>
            <span className="rounded-md bg-amber-400/20 px-2 py-0.5 font-medium text-amber-800">
              ROLAND GRU Indexed
            </span>
          </div>

          {/* Excerpt grounding quote */}
          <div className="rounded-2xl border border-black/8 bg-parchment-50/70 p-4">
            <h4 className="text-xs font-semibold text-ink-950 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
              <Sparkles size={12} className="text-amber-500" /> Grounded Text Excerpt
            </h4>
            <p className="text-xs leading-relaxed text-body-600 italic">
              {doc.excerpt ||
                `Extracted knowledge entities and topological graph relationships parsed from ${doc.title}. Fully partitioned into PCST subgraphs for sub-second semantic retrieval.`}
            </p>
          </div>

          {/* Related Entities in this document */}
          <div>
            <h4 className="text-xs font-semibold text-ink-950 uppercase tracking-wider mb-2">
              Extracted Entities in this Document ({relatedNodes.length})
            </h4>
            {relatedNodes.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {relatedNodes.map((n) => (
                  <button
                    key={n.id}
                    onClick={() => {
                      onSelectNode(n);
                      onClose();
                    }}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-black/8 bg-white px-2.5 py-1 text-xs text-ink-950 shadow-2xs hover:border-amber-400 hover:bg-amber-400/10 transition"
                  >
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ backgroundColor: colorForKind(n.kind || n.type) }}
                    />
                    <span className="font-semibold">{n.label || n.name || n.id}</span>
                    <span className="text-[9px] uppercase text-body-500">
                      {n.kind || n.type}
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-xs text-body-500">
                Click any highlighted entity in the answer to focus its node directly on the graph.
              </p>
            )}
          </div>
        </div>

        {/* Footer actions */}
        <div className="mt-5 border-t border-black/8 pt-3 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-xl border border-black/10 px-4 py-2 text-xs font-semibold text-ink-950 hover:bg-black/5 transition"
          >
            Close
          </button>
        </div>
      </motion.div>
    </div>
  );
}

// ─── Welcome State ────────────────────────────────────────────────────────────

function WelcomeState({ onPreset }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-8 px-6 py-12">
      <div className="flex flex-col items-center gap-4 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-400 text-2xl font-bold text-ink-950 shadow-md">
          K
        </div>
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-ink-950">
            Ask KONNECT anything
          </h2>
          <p className="mt-1.5 max-w-sm text-sm text-body-500 leading-relaxed">
            Queries are grounded in your live knowledge graph — drag, zoom, and click
            entities to trace exact reasoning subgraphs.
          </p>
        </div>
      </div>

      {/* Preset chips */}
      <div className="grid w-full max-w-lg grid-cols-1 gap-2 sm:grid-cols-2">
        {PRESET_QUERIES.map((q) => (
          <button
            key={q}
            onClick={() => onPreset(q)}
            className="flex items-start gap-2.5 rounded-xl border border-black/8 bg-white px-4 py-3 text-left text-sm text-ink-950 shadow-sm transition hover:border-amber-400/60 hover:bg-amber-400/5 hover:shadow-md cursor-pointer"
          >
            <Sparkles size={14} className="mt-0.5 shrink-0 text-amber-500" />
            <span className="leading-snug">{q}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

// ─── Typing Indicator ─────────────────────────────────────────────────────────

function TypingIndicator() {
  return (
    <div className="mr-auto flex max-w-[80%] items-center gap-3 rounded-2xl rounded-tl-sm border border-black/8 bg-white px-4 py-3.5 shadow-sm">
      <div className="flex items-center gap-1.5">
        <span className="h-2 w-2 animate-bounce rounded-full bg-amber-400 [animation-delay:0ms]" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-amber-400 [animation-delay:150ms]" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-amber-400 [animation-delay:300ms]" />
      </div>
      <span className="text-xs text-body-500 font-medium">KONNECT is retrieving PCST subgraph & reasoning…</span>
    </div>
  );
}

// ─── Auth Gate Overlay ────────────────────────────────────────────────────────

function AuthGate({ onDemo }) {
  return (
    <div className="absolute inset-0 z-40 flex items-center justify-center bg-parchment-50/80 backdrop-blur-md">
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 12 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.3, ease: "easeOut" }}
        className="w-full max-w-sm rounded-3xl border border-black/10 bg-white p-8 shadow-2xl"
      >
        <div className="mx-auto mb-5 flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-400/20 text-amber-600">
          <Lock size={22} />
        </div>

        <h2 className="text-center text-xl font-bold tracking-tight text-ink-950">
          Sign in to continue
        </h2>
        <p className="mt-2 text-center text-xs leading-relaxed text-body-500">
          The interactive knowledge graph and chat require an active session.
          Try it instantly with 1-Click Demo access.
        </p>

        <div className="mt-6 flex flex-col gap-2.5">
          <button
            onClick={onDemo}
            className="flex w-full items-center justify-center gap-2 rounded-2xl bg-amber-400 py-3 text-sm font-semibold text-ink-950 shadow transition hover:bg-amber-500 cursor-pointer"
          >
            <Sparkles size={15} />
            1-Click Instant Demo Access
          </button>

          <div className="grid grid-cols-2 gap-2">
            <Link
              to="/login?redirect=/live-demo"
              className="flex items-center justify-center gap-1 rounded-xl border border-black/10 py-2.5 text-xs font-medium text-ink-950 transition hover:bg-black/5"
            >
              Sign in
            </Link>
            <Link
              to="/signup?redirect=/live-demo"
              className="flex items-center justify-center gap-1 rounded-xl bg-ink-950 py-2.5 text-xs font-medium text-parchment-50 transition hover:bg-ink-800"
            >
              Create account <ArrowRight size={11} />
            </Link>
          </div>
        </div>

        <p className="mt-5 flex items-center justify-center gap-1.5 text-[10px] text-body-500">
          <ShieldCheck size={12} className="text-emerald-500" />
          Zero setup · Pre-populated demo knowledge base
        </p>
      </motion.div>
    </div>
  );
}

// ─── Graph + Terminal Panel ───────────────────────────────────────────────────

function GraphPanel({
  highlightedNodes,
  focusedNodeId,
  onClose,
  nodes = INITIAL_NODES,
  links = INITIAL_LINKS,
  onOpenDocument,
  isExpanded = false,
  onToggleExpand,
}) {
  const [log, setLog] = useState([
    { tag: "SYSTEM", text: "Knowledge ingestion stream ready", time: "12:40:00" },
    { tag: "CONNECTED", text: "Listening on gRPC graph-delta-stream", time: "12:40:01" },
  ]);
  const [terminalTab, setTerminalTab] = useState("stream");
  const [selectedNode, setSelectedNode] = useState(null);
  const logEndRef = useRef(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [log]);

  const handleTriggerEdit = async () => {
    const result = await triggerEdit();
    const now = new Date().toLocaleTimeString();

    fetch("/api/webhooks/onedrive", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        value: [
          {
            subscriptionId: "live-demo-subscription",
            clientState: "konnect_onedrive_secret_state_token",
            changeType: "updated",
            resource: "me/drive/items/doc-sample",
            resourceData: { id: "doc-sample" },
          },
        ],
      }),
    }).catch(() => {});

    setLog((prev) => [
      ...prev.slice(-20),
      ...result.logEvents.map((e) => ({ ...e, time: now })),
    ]);
  };

  return (
    <div className="flex h-full flex-col border-l border-black/8 bg-[#0E0E10] text-parchment-50">
      {/* Panel header */}
      <div className="flex items-center justify-between border-b border-white/10 bg-[#141519] px-4 py-3">
        <div className="flex items-center gap-2.5">
          <Network size={15} className="text-amber-400" />
          <span className="text-xs font-bold text-parchment-50 tracking-tight">
            Live Knowledge Graph
          </span>
          <span className="rounded-full bg-white/10 px-2 py-0.5 text-[9px] font-mono text-white/70">
            {nodes.length} nodes · {links.length} edges
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={onToggleExpand}
            title={isExpanded ? "Standard View (460px)" : "Expand Graph Canvas (640px)"}
            className="flex h-6 w-6 items-center justify-center rounded-md text-white/50 transition hover:bg-white/10 hover:text-white cursor-pointer"
          >
            {isExpanded ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
          </button>
          <button
            onClick={onClose}
            title="Close Panel"
            className="flex h-6 w-6 items-center justify-center rounded-md text-white/50 transition hover:bg-white/10 hover:text-white cursor-pointer"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Graph canvas container */}
      <div
        className={`relative transition-all duration-300 border-b border-white/10 bg-[#101114] ${
          isExpanded ? "flex-1 min-h-[400px]" : "h-[360px] shrink-0"
        }`}
      >
        <GraphCanvas
          live
          initialNodes={nodes}
          initialLinks={links}
          highlightedNodeIds={highlightedNodes}
          focusedNodeId={focusedNodeId}
          onSelectNode={setSelectedNode}
          selectedNodeId={selectedNode?.id}
          onOpenDocument={onOpenDocument}
        />
      </div>

      {/* Terminal and Logs (visible in split mode) */}
      {!isExpanded && (
        <div className="flex flex-1 flex-col overflow-hidden bg-[#0A0A0C]">
          {/* Terminal tabs + trigger */}
          <div className="flex items-center justify-between border-b border-white/10 bg-[#141519] px-3 py-2">
            <div className="flex items-center gap-1">
              <button
                onClick={() => setTerminalTab("stream")}
                className={`flex items-center gap-1 rounded px-2 py-1 font-mono text-[10px] transition ${
                  terminalTab === "stream"
                    ? "bg-white/15 text-white"
                    : "text-white/40 hover:text-white"
                }`}
              >
                <Terminal size={10} /> event-stream
              </button>
              <button
                onClick={() => setTerminalTab("cypher")}
                className={`flex items-center gap-1 rounded px-2 py-1 font-mono text-[10px] transition ${
                  terminalTab === "cypher"
                    ? "bg-white/15 text-white"
                    : "text-white/40 hover:text-white"
                }`}
              >
                <Activity size={10} /> neo4j.cypher
              </button>
            </div>
            <div className="flex items-center gap-2">
              <span className="flex items-center gap-1 font-mono text-[9px] text-emerald-400">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
                LIVE
              </span>
              <button
                onClick={handleTriggerEdit}
                className="flex items-center gap-1 rounded-full bg-amber-400/20 px-2 py-0.5 text-[10px] font-semibold text-amber-400 ring-1 ring-amber-400/30 transition hover:bg-amber-400 hover:text-ink-950 cursor-pointer"
              >
                <PlusCircle size={10} /> Trigger Edit
              </button>
            </div>
          </div>

          {/* Log body */}
          <div className="flex-1 overflow-y-auto p-3 font-mono text-[10px] leading-relaxed no-scrollbar">
            {terminalTab === "stream" ? (
              <div className="space-y-1.5">
                {log.map((entry, idx) => (
                  <div key={idx} className="flex items-start gap-1.5">
                    <span className="shrink-0 text-white/25">
                      {String(idx + 1).padStart(2, "0")}
                    </span>
                    <span className="shrink-0 text-white/40">{entry.time}</span>
                    <span
                      className={`shrink-0 rounded border px-1 py-0.5 text-[8px] font-bold ${getBadgeColor(
                        entry.tag
                      )}`}
                    >
                      {entry.tag}
                    </span>
                    <span className="text-white/70">{entry.text}</span>
                  </div>
                ))}
                <div ref={logEndRef} />
              </div>
            ) : (
              <div className="space-y-1.5 text-sky-300">
                <p className="text-white/40">// Neo4j GDS — active patch queue</p>
                <p>{"MATCH (d:Doc {id: $docId})-[r:MENTIONS]->(e:Entity)"}</p>
                <p>{"WHERE e.lastSynced < datetime($timestamp)"}</p>
                <p>{"MERGE (d)-[:UPDATED_AT]->(t:Timestamp {val: $timestamp})"}</p>
                <p className="text-amber-400">
                  {">"} Committed active node state updates via bolt://localhost:7687
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Main Component ────────────────────────────────────────────────────────────

export default function LiveDemo() {
  const [searchParams] = useSearchParams();
  const initialQuery = searchParams.get("q") || "";
  const navigate = useNavigate();
  const { isAuthenticated, user, loginAsDemo, logout } = useAuth();

  // Conversations
  const [conversations, setConversations] = useState([]);
  const [activeConvId, setActiveConvId] = useState(null);

  // Messages keyed by conversation id
  const [messagesByConv, setMessagesByConv] = useState({});

  // UI state
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [highlightedNodes, setHighlightedNodes] = useState([]);
  const [focusedNodeId, setFocusedNodeId] = useState(null);
  const [viewingDocument, setViewingDocument] = useState(null);
  const [graphOpen, setGraphOpen] = useState(true);
  const [isGraphExpanded, setIsGraphExpanded] = useState(false);
  const [backendStatus, setBackendStatus] = useState("checking");
  const [onedriveStatus, setOnedriveStatus] = useState({ connected: false });
  const [gdriveStatus, setGdriveStatus] = useState({ connected: false });
  const [graphNodes, setGraphNodes] = useState(INITIAL_NODES);
  const [graphLinks, setGraphLinks] = useState(INITIAL_LINKS);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadToast, setUploadToast] = useState(null);

  const chatEndRef = useRef(null);
  const inputRef = useRef(null);
  const fileInputRef = useRef(null);

  const activeMessages = messagesByConv[activeConvId] ?? [];

  // ── Init ────────────────────────────────────────────────────────────────────

  useEffect(() => {
    healthCheck().then((r) => setBackendStatus(r.status));

    fetch("/api/auth/onedrive/status")
      .then((res) => res.json())
      .then((data) => setOnedriveStatus(data))
      .catch(() => setOnedriveStatus({ connected: false }));

    fetch("/api/auth/gdrive/status")
      .then((res) => res.json())
      .then((data) => setGdriveStatus(data))
      .catch(() => setGdriveStatus({ connected: false }));
  }, []);

  // Update status when returning from OAuth redirect callbacks
  useEffect(() => {
    if (searchParams.get("gdrive") === "connected") {
      fetch("/api/auth/gdrive/status")
        .then((res) => res.json())
        .then((data) => setGdriveStatus(data))
        .catch(() => setGdriveStatus({ connected: false }));
      setUploadToast("Google Drive connected successfully!");
      setTimeout(() => setUploadToast(null), 5000);
    }
    if (searchParams.get("onedrive") === "connected") {
      fetch("/api/auth/onedrive/status")
        .then((res) => res.json())
        .then((data) => setOnedriveStatus(data))
        .catch(() => setOnedriveStatus({ connected: false }));
      setUploadToast("OneDrive connected successfully!");
      setTimeout(() => setUploadToast(null), 5000);
    }
  }, [searchParams]);

  // Bootstrap first conversation when authenticated
  useEffect(() => {
    if (!isAuthenticated) return;
    if (conversations.length > 0) return;

    createConversation().then((conv) => {
      setConversations([conv]);
      setActiveConvId(conv.id);
      setMessagesByConv({
        [conv.id]: [
          {
            role: "assistant",
            text: "Hello! I'm KONNECT's knowledge assistant. I can answer questions grounded in your connected workspace — Google Drive, OneDrive, and uploaded documents. Ask me anything.",
            citations: [],
            subgraph: null,
          },
        ],
      });
    });
  }, [isAuthenticated, conversations.length]);

  // Handle pre-filled query from homepage
  useEffect(() => {
    if (initialQuery && isAuthenticated && activeConvId) {
      handleSend(initialQuery);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuery, isAuthenticated, activeConvId]);

  // Auto-scroll
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeMessages, isLoading]);

  // ── Entity & Relation Redirection Handlers ──────────────────────────────────

  const handleSelectEntity = useCallback(
    (nameOrId) => {
      if (!nameOrId) return;
      const targetLabel = String(nameOrId).trim();
      setGraphOpen(true);

      const match = graphNodes.find(
        (n) =>
          n.id === targetLabel ||
          n.label?.toLowerCase() === targetLabel.toLowerCase() ||
          n.name?.toLowerCase() === targetLabel.toLowerCase()
      );

      if (match) {
        setFocusedNodeId(match.id);
        setHighlightedNodes([match.id]);
      } else {
        // Dynamic node injection so that referenced entity appears on graph
        const newNodeId = `node_${Date.now()}`;
        const newNode = {
          id: newNodeId,
          kind: "Entity",
          label: targetLabel,
          name: targetLabel,
          description: `Grounded entity referenced in answer`,
          prize: 0.9,
          x: 380 + (Math.random() - 0.5) * 150,
          y: 250 + (Math.random() - 0.5) * 150,
        };
        setGraphNodes((prev) => [...prev, newNode]);
        setFocusedNodeId(newNodeId);
        setHighlightedNodes([newNodeId]);
      }

      setTimeout(() => setHighlightedNodes([]), 4500);
    },
    [graphNodes]
  );

  const handleSelectRelation = useCallback(
    (edge) => {
      if (!edge) return;
      setGraphOpen(true);
      const srcId = typeof edge.source === "object" ? edge.source.id : edge.source;
      const tgtId = typeof edge.target === "object" ? edge.target.id : edge.target;

      const srcNode = graphNodes.find(
        (n) => n.id === srcId || n.label?.toLowerCase() === String(srcId).toLowerCase()
      );
      const tgtNode = graphNodes.find(
        (n) => n.id === tgtId || n.label?.toLowerCase() === String(tgtId).toLowerCase()
      );

      const activeSrc = srcNode?.id || srcId;
      const activeTgt = tgtNode?.id || tgtId;

      setFocusedNodeId(activeSrc);
      setHighlightedNodes([activeSrc, activeTgt]);
      setTimeout(() => setHighlightedNodes([]), 4500);
    },
    [graphNodes]
  );

  const handleOpenDocument = useCallback(
    (docIdOrName) => {
      if (!docIdOrName) return;
      const cleanTitle = String(docIdOrName).replace(/^doc_\d+_/, "");
      setViewingDocument({
        id: docIdOrName,
        title: cleanTitle,
        fullName: docIdOrName,
        excerpt: `Document grounded in live knowledge graph. Topological PCST subgraphs connect all entities mentioned in ${cleanTitle}.`,
      });
    },
    []
  );

  // ── Actions ─────────────────────────────────────────────────────────────────

  const handleSend = useCallback(
    async (textOverride) => {
      const text = (textOverride ?? inputValue).trim();
      if (!text || isLoading || !activeConvId) return;

      setInputValue("");
      setIsLoading(true);

      // Append user message
      setMessagesByConv((prev) => ({
        ...prev,
        [activeConvId]: [...(prev[activeConvId] ?? []), { role: "user", text }],
      }));

      // Update conversation title from first user message
      setConversations((prev) =>
        prev.map((c) =>
          c.id === activeConvId && c.title === "New conversation"
            ? { ...c, title: text.slice(0, 40) }
            : c
        )
      );

      try {
        const res = await sendQuery(text, activeConvId);

        // Append assistant message with full subgraph and citations
        setMessagesByConv((prev) => ({
          ...prev,
          [activeConvId]: [
            ...(prev[activeConvId] ?? []),
            {
              role: "assistant",
              text: res.answer,
              citations: res.citations || [],
              subgraph: res.subgraph || null,
            },
          ],
        }));

        // Dynamic Graph Sync: Merge PCST Subgraph Nodes into live graph
        if (res.subgraph && Array.isArray(res.subgraph.nodes) && res.subgraph.nodes.length > 0) {
          setGraphNodes((prevNodes) => {
            const existingIds = new Set(prevNodes.map((n) => n.id));
            const newNodes = res.subgraph.nodes
              .filter((n) => !existingIds.has(n.id))
              .map((n) => ({
                id: n.id,
                label: n.name || n.label || n.id,
                name: n.name || n.label || n.id,
                kind: n.type || n.kind || "Entity",
                document_id: n.document_id,
                description: n.description,
                prize: res.subgraph.prizes?.[n.id] || n.prize || n.score || 0.85,
                x: 380 + (Math.random() - 0.5) * 220,
                y: 250 + (Math.random() - 0.5) * 220,
              }));
            return [...prevNodes, ...newNodes];
          });
        }

        // Dynamic Graph Sync: Merge PCST Subgraph Edges into live graph
        if (res.subgraph && Array.isArray(res.subgraph.edges) && res.subgraph.edges.length > 0) {
          setGraphLinks((prevLinks) => {
            const existingKeys = new Set(
              prevLinks.map(
                (l) =>
                  `${typeof l.source === "object" ? l.source.id : l.source}->${
                    typeof l.target === "object" ? l.target.id : l.target
                  }:${l.type || ""}`
              )
            );
            const newLinks = res.subgraph.edges
              .filter(
                (e) => !existingKeys.has(`${e.source}->${e.target}:${e.type || e.relationship || ""}`)
              )
              .map((e) => ({
                source: e.source,
                target: e.target,
                type: e.type || e.relationship || "CONNECTED_TO",
                cost: e.cost,
              }));
            return [...prevLinks, ...newLinks];
          });
        }

        // Highlight cited nodes
        const citedIds = (res.citations || []).map((c) => c.id);
        if (citedIds.length > 0) {
          setHighlightedNodes(citedIds);
          setFocusedNodeId(citedIds[0]);
          setTimeout(() => setHighlightedNodes([]), 4500);
        }
      } catch {
        setMessagesByConv((prev) => ({
          ...prev,
          [activeConvId]: [
            ...(prev[activeConvId] ?? []),
            {
              role: "assistant",
              text: "Something went wrong retrieving grounded knowledge graph context. Please try again.",
              citations: [],
              subgraph: null,
            },
          ],
        }));
      } finally {
        setIsLoading(false);
        inputRef.current?.focus();
      }
    },
    [inputValue, isLoading, activeConvId]
  );

  const handleNewConversation = async () => {
    const conv = await createConversation();
    setConversations((prev) => [conv, ...prev]);
    setActiveConvId(conv.id);
    setMessagesByConv((prev) => ({
      ...prev,
      [conv.id]: [
        {
          role: "assistant",
          text: "New conversation started. What would you like to know?",
          citations: [],
          subgraph: null,
        },
      ],
    }));
    inputRef.current?.focus();
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadToast(`Ingesting "${file.name}" into knowledge graph...`);

    try {
      const res = await uploadDocument(file);
      const docId = res.documentId || `doc_${Date.now()}`;

      const newDocNode = {
        id: docId,
        kind: "Doc",
        label: file.name,
        name: file.name,
        x: 320 + (Math.random() - 0.5) * 80,
        y: 210 + (Math.random() - 0.5) * 80,
      };

      setGraphNodes((prev) => [...prev, newDocNode]);
      setFocusedNodeId(docId);
      setHighlightedNodes([docId]);
      setGraphOpen(true);

      const count = res.graphUpdate?.nodesUpdated || "Multiple";
      setUploadToast(`"${file.name}" ingested successfully! ${count} entities synchronized.`);
      setTimeout(() => setUploadToast(null), 6000);
    } catch (err) {
      setUploadToast(`Failed to ingest document: ${err.message}`);
      setTimeout(() => setUploadToast(null), 6000);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleSyncGDrive = async () => {
    setIsUploading(true);
    setUploadToast("Fast-scanning private 'KONNECT' folder in Google Drive...");
    try {
      const res = await syncGDrive();
      setUploadToast(res.message);
      if (res.documents && res.documents.length > 0) {
        const newNodes = res.documents.map((d, i) => ({
          id: d.documentId || `doc_gdrive_${i}_${Date.now()}`,
          kind: "Doc",
          label: d.fileName,
          name: d.fileName,
          document_id: d.documentId,
          description: `Ingested from Google Drive (${d.nodesUpdated || 0} entities synchronized)`,
          x: 340 + (Math.random() - 0.5) * 120,
          y: 220 + (Math.random() - 0.5) * 120,
        }));
        setGraphNodes((prev) => {
          const existingIds = new Set(prev.map((n) => n.id));
          return [...prev, ...newNodes.filter((n) => !existingIds.has(n.id))];
        });
        setFocusedNodeId(newNodes[0].id);
        setHighlightedNodes(newNodes.map((n) => n.id));
        setGraphOpen(true);
      }
      setTimeout(() => setUploadToast(null), 6000);
    } catch (err) {
      setUploadToast(`Google Drive sync error: ${err.message}`);
      setTimeout(() => setUploadToast(null), 6000);
    } finally {
      setIsUploading(false);
    }
  };

  const handleSyncOneDrive = async () => {
    setIsUploading(true);
    setUploadToast("Fast-scanning private 'KONNECT' folder in OneDrive...");
    try {
      const res = await syncOneDrive();
      setUploadToast(res.message);
      if (res.documents && res.documents.length > 0) {
        const newNodes = res.documents.map((d, i) => ({
          id: d.documentId || `doc_onedrive_${i}_${Date.now()}`,
          kind: "Doc",
          label: d.fileName,
          name: d.fileName,
          document_id: d.documentId,
          description: `Ingested from OneDrive (${d.nodesUpdated || 0} entities synchronized)`,
          x: 340 + (Math.random() - 0.5) * 120,
          y: 220 + (Math.random() - 0.5) * 120,
        }));
        setGraphNodes((prev) => {
          const existingIds = new Set(prev.map((n) => n.id));
          return [...prev, ...newNodes.filter((n) => !existingIds.has(n.id))];
        });
        setFocusedNodeId(newNodes[0].id);
        setHighlightedNodes(newNodes.map((n) => n.id));
        setGraphOpen(true);
      }
      setTimeout(() => setUploadToast(null), 6000);
    } catch (err) {
      setUploadToast(`OneDrive sync error: ${err.message}`);
      setTimeout(() => setUploadToast(null), 6000);
    } finally {
      setIsUploading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleDemoLogin = () => {
    loginAsDemo();
  };

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="fixed inset-0 flex bg-parchment-50">
      {/* ── Document Excerpt Modal ────────────────────────────────────────── */}
      <AnimatePresence>
        {viewingDocument && (
          <DocumentExcerptModal
            doc={viewingDocument}
            nodes={graphNodes}
            onClose={() => setViewingDocument(null)}
            onSelectNode={(node) => {
              setFocusedNodeId(node.id);
              setHighlightedNodes([node.id]);
              setGraphOpen(true);
            }}
          />
        )}
      </AnimatePresence>

      {/* ── Sidebar ───────────────────────────────────────────────────────── */}
      <aside className="flex w-60 shrink-0 flex-col border-r border-black/8 bg-ink-950 lg:w-64">
        {/* Brand */}
        <div className="flex items-center justify-between px-4 py-4">
          <button
            onClick={() => navigate("/")}
            className="flex items-center gap-2 text-sm font-semibold text-parchment-50 transition hover:opacity-80 cursor-pointer"
          >
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-amber-400 text-[11px] font-bold text-ink-950">
              K
            </span>
            KONNECT
          </button>
          <div className="flex items-center gap-1">
            {backendStatus === "connected" ? (
              <span title="Backend connected" className="flex h-5 w-5 items-center justify-center">
                <CheckCircle2 size={13} className="text-emerald-400" />
              </span>
            ) : (
              <span title="Simulated mode" className="flex h-5 w-5 items-center justify-center">
                <Server size={12} className="text-white/30" />
              </span>
            )}
          </div>
        </div>

        {/* New Chat */}
        <div className="px-3 pb-2">
          <button
            onClick={handleNewConversation}
            disabled={!isAuthenticated}
            className="flex w-full items-center gap-2 rounded-xl border border-white/10 px-3 py-2.5 text-xs font-medium text-white/70 transition hover:border-amber-400/40 hover:bg-white/5 hover:text-parchment-50 disabled:opacity-40 cursor-pointer"
          >
            <PlusSquare size={14} />
            New chat
          </button>
        </div>

        {/* Conversation history */}
        <nav className="flex-1 overflow-y-auto px-2 py-1 no-scrollbar">
          {conversations.length > 0 && (
            <>
              <p className="mb-1 px-2 text-[10px] font-semibold uppercase tracking-wider text-white/25">
                Recent
              </p>
              <div className="flex flex-col gap-0.5">
                {conversations.map((conv) => (
                  <button
                    key={conv.id}
                    onClick={() => setActiveConvId(conv.id)}
                    className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-[11px] transition cursor-pointer ${
                      conv.id === activeConvId
                        ? "bg-white/10 text-parchment-50 font-semibold"
                        : "text-white/50 hover:bg-white/5 hover:text-white/80"
                    }`}
                  >
                    <MessageSquare size={12} className="shrink-0 opacity-60" />
                    <span className="truncate leading-snug">{conv.title}</span>
                  </button>
                ))}
              </div>
            </>
          )}
        </nav>

        {/* User info */}
        <div className="border-t border-white/10 p-3">
          {isAuthenticated ? (
            <div className="flex items-center justify-between rounded-xl bg-white/5 px-3 py-2.5">
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-amber-400 text-[10px] font-bold text-ink-950">
                  {user?.avatar ?? user?.name?.[0]?.toUpperCase() ?? "U"}
                </div>
                <div className="min-w-0">
                  <p className="truncate text-[11px] font-semibold text-parchment-50">
                    {user?.name ?? "Demo User"}
                  </p>
                  <p className="truncate text-[9px] text-white/40">
                    {user?.role ?? "Workspace Member"}
                  </p>
                </div>
              </div>
              <button
                onClick={logout}
                title="Sign out"
                className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-white/40 transition hover:bg-white/10 hover:text-white/80"
              >
                <LogOut size={12} />
              </button>
            </div>
          ) : (
            <Link
              to="/login"
              className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-white/10 py-2.5 text-[11px] font-medium text-white/50 transition hover:border-amber-400/40 hover:text-parchment-50"
            >
              <User size={12} /> Sign in
            </Link>
          )}
        </div>

        {/* Back to home */}
        <div className="border-t border-white/10 px-3 py-2.5">
          <Link
            to="/"
            className="flex items-center gap-1.5 text-[10px] text-white/30 transition hover:text-white/60"
          >
            <ArrowLeft size={10} /> Back to home
          </Link>
        </div>
      </aside>

      {/* ── Chat & Graph Area ──────────────────────────────────────────────── */}
      <div className="relative flex flex-1 flex-col overflow-hidden">
        {/* Auth gate */}
        {!isAuthenticated && <AuthGate onDemo={handleDemoLogin} />}

        {/* Top bar */}
        <header className="flex shrink-0 items-center justify-between border-b border-black/8 bg-white/80 px-5 py-3 backdrop-blur">
          <div className="flex items-center gap-2">
            <Zap size={14} className="text-amber-500" />
            <span className="text-xs font-semibold text-ink-950">
              {conversations.find((c) => c.id === activeConvId)?.title || "KONNECT AI"}
            </span>
            {backendStatus === "simulated" && (
              <span className="rounded-full bg-black/5 px-2 py-0.5 text-[9px] text-body-500">
                Simulated
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              accept=".pdf,.docx,.txt,.md"
              className="hidden"
            />

            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              className="inline-flex items-center gap-1.5 rounded-full bg-amber-400/20 px-3 py-1 text-[11px] font-semibold text-amber-700 border border-amber-400/40 hover:bg-amber-400 hover:text-ink-950 transition disabled:opacity-50 cursor-pointer"
              title="Upload PDF, Word (DOCX), or Text to build Knowledge Graph"
            >
              <UploadCloud size={13} className={isUploading ? "animate-bounce" : ""} />
              {isUploading ? "Ingesting..." : "Upload Document"}
            </button>

            {/* Google Drive Button */}
            {gdriveStatus.connected ? (
              <div className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 pl-2.5 pr-1 py-0.5 text-[11px] font-medium text-emerald-600 ring-1 ring-emerald-500/30">
                <CheckCircle2 size={12} />
                <span>GDrive: KONNECT</span>
                <button
                  onClick={handleSyncGDrive}
                  disabled={isUploading}
                  title="Sync documents from Google Drive 'KONNECT' folder"
                  className="rounded-full p-1 text-emerald-600 hover:bg-emerald-500/20 transition disabled:opacity-50 cursor-pointer"
                >
                  <RefreshCw size={11} className={isUploading ? "animate-spin" : ""} />
                </button>
              </div>
            ) : (
              <a
                href="http://localhost:5000/api/auth/google/connect"
                className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-3 py-1 text-[11px] font-semibold text-emerald-600 ring-1 ring-emerald-500/30 hover:bg-emerald-600 hover:text-white transition cursor-pointer"
                title="Connect Google Drive (Private 'KONNECT' folder only)"
              >
                <Cloud size={13} /> Google Drive
              </a>
            )}

            {/* OneDrive Button */}
            {onedriveStatus.connected ? (
              <div className="inline-flex items-center gap-1.5 rounded-full bg-blue-500/10 pl-2.5 pr-1 py-0.5 text-[11px] font-medium text-blue-600 ring-1 ring-blue-500/30">
                <CheckCircle2 size={12} />
                <span>OneDrive: KONNECT</span>
                <button
                  onClick={handleSyncOneDrive}
                  disabled={isUploading}
                  title="Sync documents from OneDrive 'KONNECT' folder"
                  className="rounded-full p-1 text-blue-600 hover:bg-blue-500/20 transition disabled:opacity-50 cursor-pointer"
                >
                  <RefreshCw size={11} className={isUploading ? "animate-spin" : ""} />
                </button>
              </div>
            ) : (
              <a
                href="http://localhost:5000/api/auth/onedrive/connect"
                className="inline-flex items-center gap-1.5 rounded-full bg-blue-500/10 px-3 py-1 text-[11px] font-semibold text-blue-600 ring-1 ring-blue-500/30 hover:bg-blue-600 hover:text-white transition cursor-pointer"
                title="Connect OneDrive (Private 'KONNECT' folder only)"
              >
                <Cloud size={13} /> OneDrive
              </a>
            )}

            <button
              onClick={() => setGraphOpen((v) => !v)}
              className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[11px] font-medium transition cursor-pointer ${
                graphOpen
                  ? "bg-ink-950 text-parchment-50 shadow-sm"
                  : "border border-black/10 text-body-500 hover:border-black/20 hover:text-ink-950"
              }`}
            >
              <LayoutGrid size={12} />
              Live Graph
              <ChevronRight
                size={12}
                className={`transition-transform duration-200 ${graphOpen ? "rotate-180" : ""}`}
              />
            </button>
          </div>
        </header>

        {uploadToast && (
          <div className="flex shrink-0 items-center justify-between bg-amber-400 px-4 py-2 text-xs font-semibold text-ink-950 transition-all">
            <span className="flex items-center gap-1.5">
              <CheckCircle2 size={14} /> {uploadToast}
            </span>
            <button onClick={() => setUploadToast(null)}>
              <X size={13} />
            </button>
          </div>
        )}

        {/* Content Area: Chat messages + Live Graph Panel */}
        <div className="flex flex-1 overflow-hidden">
          {/* Chat Messages */}
          <div className="flex flex-1 flex-col overflow-y-auto">
            {activeMessages.length <= 1 && !isLoading && isAuthenticated ? (
              <WelcomeState onPreset={(q) => handleSend(q)} />
            ) : (
              <div className="mx-auto w-full max-w-2xl flex-1 px-4 py-6">
                <div className="flex flex-col gap-4">
                  {activeMessages.map((msg, i) => (
                    <MessageBubble
                      key={i}
                      message={msg}
                      onSelectEntity={handleSelectEntity}
                      onSelectRelation={handleSelectRelation}
                      onOpenDocument={handleOpenDocument}
                    />
                  ))}
                  {isLoading && <TypingIndicator />}
                  <div ref={chatEndRef} />
                </div>
              </div>
            )}
          </div>

          {/* Live Graph Panel (Interactive Dragging, Zooming, Node/Relation Inspection) */}
          <AnimatePresence>
            {graphOpen && (
              <motion.div
                initial={{ width: 0, opacity: 0 }}
                animate={{ width: isGraphExpanded ? 640 : 460, opacity: 1 }}
                exit={{ width: 0, opacity: 0 }}
                transition={{ duration: 0.25, ease: "easeInOut" }}
                className="hidden shrink-0 overflow-hidden lg:block border-l border-black/10 shadow-lg"
                style={{ width: isGraphExpanded ? 640 : 460 }}
              >
                <GraphPanel
                  highlightedNodes={highlightedNodes}
                  focusedNodeId={focusedNodeId}
                  nodes={graphNodes}
                  links={graphLinks}
                  isExpanded={isGraphExpanded}
                  onToggleExpand={() => setIsGraphExpanded((v) => !v)}
                  onClose={() => setGraphOpen(false)}
                  onOpenDocument={handleOpenDocument}
                />
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Input Bar */}
        <div className="shrink-0 border-t border-black/8 bg-white/90 px-4 py-3.5 backdrop-blur">
          <div className="mx-auto flex w-full max-w-2xl items-end gap-3">
            <div className="flex flex-1 items-end rounded-2xl border border-black/10 bg-white shadow-sm transition-all focus-within:border-amber-400 focus-within:ring-2 focus-within:ring-amber-400/20">
              <textarea
                ref={inputRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Enter Your Query"
                disabled={!isAuthenticated || isLoading}
                rows={1}
                className="flex-1 resize-none rounded-2xl bg-transparent px-4 py-3 text-sm text-ink-950 placeholder:text-body-500/60 focus:outline-none disabled:opacity-50"
                style={{ maxHeight: 120, overflowY: "auto" }}
                onInput={(e) => {
                  e.target.style.height = "auto";
                  e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
                }}
              />
            </div>
            <button
              onClick={() => handleSend()}
              disabled={!isAuthenticated || isLoading || !inputValue.trim()}
              aria-label="Send"
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-amber-400 text-ink-950 shadow transition hover:bg-amber-500 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
            >
              {isLoading ? (
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-ink-950/30 border-t-ink-950" />
              ) : (
                <Send size={16} />
              )}
            </button>
          </div>
          <p className="mt-2 text-center text-[10px] text-body-500/60">
            KONNECT AI answers are grounded in your PCST Subgraphs. Click any entity or relation to inspect on graph.
          </p>
        </div>
      </div>
    </div>
  );
}
