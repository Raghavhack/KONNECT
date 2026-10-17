    import { useState, useEffect, useRef, useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
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
  Cloud,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import GraphCanvas from "../components/shared/GraphCanvas";
import {
  healthCheck,
  sendQuery,
  triggerEdit,
  streamEvents,
  createConversation,
} from "../api/mockApi";

// ─── Constants ────────────────────────────────────────────────────────────────

const PRESET_QUERIES = [
  "What changed in the onboarding doc?",
  "Which entities connect to AuthService?",
  "Show PCST subgraph for permissions",
  "Who last edited Architecture.pdf?",
];

const INITIAL_NODES = [
  { id: "root", kind: "Doc", label: "Onboarding.md", x: 320, y: 210 },
  { id: "e1", kind: "Entity", label: "AuthService", x: 240, y: 150 },
  { id: "e2", kind: "Person", label: "Raghav", x: 400, y: 270 },
  { id: "e3", kind: "Topic", label: "PCST Subgraph", x: 420, y: 120 },
];

const INITIAL_LINKS = [
  { source: "root", target: "e1" },
  { source: "root", target: "e2" },
  { source: "e1", target: "e3" },
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

// ─── Sub-components ───────────────────────────────────────────────────────────

function TypingIndicator() {
  return (
    <div className="mr-auto flex max-w-[80%] items-center gap-3 rounded-2xl rounded-tl-sm border border-black/8 bg-white px-4 py-3.5 shadow-sm">
      <div className="flex items-center gap-1.5">
        <span className="h-2 w-2 animate-bounce rounded-full bg-amber-400 [animation-delay:0ms]" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-amber-400 [animation-delay:150ms]" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-amber-400 [animation-delay:300ms]" />
      </div>
      <span className="text-xs text-body-500">KONNECT is thinking…</span>
    </div>
  );
}

function MessageBubble({ message, onCitationClick }) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2 }}
        className="ml-auto flex max-w-[78%] flex-col"
      >
        <div className="rounded-2xl rounded-tr-sm bg-amber-400 px-4 py-3 text-sm leading-relaxed text-ink-950 shadow-sm">
          {message.text}
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="mr-auto flex max-w-[82%] flex-col gap-2"
    >
      {/* AI badge */}
      <div className="flex items-center gap-1.5">
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-amber-400 text-[9px] font-bold text-ink-950">
          K
        </span>
        <span className="text-[10px] font-semibold text-body-500">KONNECT AI</span>
      </div>

      {/* Bubble */}
      <div className="rounded-2xl rounded-tl-sm border border-black/8 bg-white px-4 py-3.5 text-sm leading-relaxed text-ink-950 shadow-sm">
        {/* Render simple markdown-like bold */}
        <p className="whitespace-pre-wrap">{formatText(message.text)}</p>

        {/* Citations */}
        {message.citations && message.citations.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-black/5 pt-2.5">
            <span className="text-[10px] text-body-500">Sources:</span>
            {message.citations.map((c) => (
              <button
                key={c.id}
                onClick={() => onCitationClick(c.id)}
                className="flex items-center gap-1 rounded-md bg-amber-400/15 px-2 py-0.5 text-[10px] font-medium text-amber-700 transition hover:bg-amber-400 hover:text-ink-950"
              >
                <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
                {c.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
}

// Very lightweight text formatter: **bold** → <strong>
function formatText(text) {
  if (!text.includes("**")) return text;
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) =>
    p.startsWith("**") && p.endsWith("**") ? (
      <strong key={i} className="font-semibold text-ink-950">
        {p.slice(2, -2)}
      </strong>
    ) : (
      p
    )
  );
}

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
            Queries are grounded in your live knowledge graph — every answer
            cites the exact source nodes.
          </p>
        </div>
      </div>

      {/* Preset chips */}
      <div className="grid w-full max-w-lg grid-cols-1 gap-2 sm:grid-cols-2">
        {PRESET_QUERIES.map((q) => (
          <button
            key={q}
            onClick={() => onPreset(q)}
            className="flex items-start gap-2.5 rounded-xl border border-black/8 bg-white px-4 py-3 text-left text-sm text-ink-950 shadow-sm transition hover:border-amber-400/60 hover:bg-amber-400/5 hover:shadow-md"
          >
            <Sparkles size={14} className="mt-0.5 shrink-0 text-amber-500" />
            <span className="leading-snug">{q}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

// ─── Auth gate overlay ─────────────────────────────────────────────────────────

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
            className="flex w-full items-center justify-center gap-2 rounded-2xl bg-amber-400 py-3 text-sm font-semibold text-ink-950 shadow transition hover:bg-amber-500"
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

// ─── Graph + Terminal panel ────────────────────────────────────────────────────

function GraphPanel({ highlightedNodes, onClose }) {
  const [log, setLog] = useState([
    { tag: "SYSTEM", text: "Knowledge ingestion stream ready", time: "12:40:00" },
    { tag: "CONNECTED", text: "Listening on gRPC graph-delta-stream", time: "12:40:01" },
  ]);
  const [terminalTab, setTerminalTab] = useState("stream");
  const [selectedNode, setSelectedNode] = useState(null);
  const logEndRef = useRef(null);
  const initialNodes = useMemo(() => INITIAL_NODES, []);
  const initialLinks = useMemo(() => INITIAL_LINKS, []);

  const [onedriveStatus, setOnedriveStatus] = useState({ connected: false });

  // Check backend health and OneDrive status
  useEffect(() => {
    fetch("/api/health")
      .then((res) => {
        if (res.ok) setBackendStatus("connected");
        else setBackendStatus("simulated");
      })
      .catch(() => setBackendStatus("simulated"));

    fetch("/api/auth/onedrive/status")
      .then((res) => res.json())
      .then((data) => setOnedriveStatus(data))
      .catch(() => {});
  }, []);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [log]);

  const handleTriggerEdit = async () => {
    const result = await triggerEdit();
    const now = new Date().toLocaleTimeString();
    setLog((prev) => [
      ...prev.slice(-20),
      ...result.logEvents.map((e) => ({ ...e, time: now })),
    ]);
  };

  return (
    <div className="flex h-full flex-col border-l border-black/8 bg-[#0E0E10]">
      {/* Panel header */}
      <div className="flex items-center justify-between border-b border-white/10 bg-[#141519] px-4 py-3">
        <div className="flex items-center gap-2">
          <Network size={14} className="text-amber-400" />
          <span className="text-xs font-semibold text-parchment-50">Knowledge Graph</span>
        </div>
        <button
          onClick={onClose}
          className="flex h-6 w-6 items-center justify-center rounded-md text-white/40 transition hover:bg-white/10 hover:text-white"
        >
          <X size={13} />
        </button>
      </div>

      {/* Graph canvas */}
      <div className="relative h-[240px] shrink-0 border-b border-white/10 bg-[#101114]">
        <GraphCanvas
          live
          initialNodes={initialNodes}
          initialLinks={initialLinks}
          highlightedNodeIds={highlightedNodes}
          onSelectNode={setSelectedNode}
          selectedNodeId={selectedNode?.id}
        />
      </div>

      {/* Selected node detail */}
      <AnimatePresence>
        {selectedNode && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="border-b border-white/10 bg-amber-400/10 px-4 py-2.5"
          >
            <p className="text-[11px] font-semibold text-amber-400">
              {selectedNode.label || selectedNode.id}
            </p>
            <p className="text-[10px] text-white/50">
              {selectedNode.kind} · ROLAND GRU Synced
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Terminal */}
      <div className="flex flex-1 flex-col overflow-hidden">
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
              className="flex items-center gap-1 rounded-full bg-amber-400/20 px-2 py-0.5 text-[10px] font-semibold text-amber-400 ring-1 ring-amber-400/30 transition hover:bg-amber-400 hover:text-ink-950"
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
                  <span className="shrink-0 text-white/25">{String(idx + 1).padStart(2, "0")}</span>
                  <span className="shrink-0 text-white/40">{entry.time}</span>
                  <span
                    className={`shrink-0 rounded border px-1 py-0.5 text-[8px] font-bold ${getBadgeColor(entry.tag)}`}
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
              <p className="text-amber-400">{">"} Committed 6 node state updates via bolt://localhost:7687</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Main component ────────────────────────────────────────────────────────────

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
  const [graphOpen, setGraphOpen] = useState(true);
  const [backendStatus, setBackendStatus] = useState("checking");

  const chatEndRef = useRef(null);
  const inputRef = useRef(null);

  const activeMessages = messagesByConv[activeConvId] ?? [];

  // ── Init ────────────────────────────────────────────────────────────────────

  // Health check
  useEffect(() => {
    healthCheck().then((r) => setBackendStatus(r.status));
  }, []);

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
            text: "Hello! I'm KONNECT's knowledge assistant. I can answer questions grounded in your connected workspace — Google Drive, Notion, and Slack. Ask me anything.",
            citations: [],
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
        setMessagesByConv((prev) => ({
          ...prev,
          [activeConvId]: [
            ...(prev[activeConvId] ?? []),
            {
              role: "assistant",
              text: res.answer,
              citations: res.citations,
            },
          ],
        }));
        setHighlightedNodes(res.citations.map((c) => c.id));
        setTimeout(() => setHighlightedNodes([]), 3000);
      } catch {
        setMessagesByConv((prev) => ({
          ...prev,
          [activeConvId]: [
            ...(prev[activeConvId] ?? []),
            {
              role: "assistant",
              text: "Something went wrong. Please try again.",
              citations: [],
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
        },
      ],
    }));
    inputRef.current?.focus();
  };

  const handleSimulateEdit = () => {
    const now = new Date().toLocaleTimeString();
    const editSources = ["OneDrive: SecurityAudit.md", "OneDrive: Architecture.docx", "OneDrive: SprintNotes.txt"];
    const chosen = editSources[Math.floor(Math.random() * editSources.length)];
    const docId = `onedrive-doc-${Math.floor(Math.random() * 900) + 100}`;

    // Trigger real backend webhook with debouncing & idempotency
    fetch("/api/webhooks/onedrive", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        value: [
          {
            subscriptionId: "live-demo-subscription",
            clientState: "konnect_onedrive_secret_state_token",
            changeType: "updated",
            resource: `me/drive/items/${docId}`,
            resourceData: { id: docId },
          },
        ],
      }),
    })
      .then((r) => r.json())
      .then((data) => {
        console.log("[LiveDemo] Real backend webhook response:", data);
      })
      .catch((err) => console.warn("[LiveDemo] Webhook ping failed:", err));

    setLog((prev) => [
      ...prev.slice(-15),
      { tag: "WEBHOOK", text: `Inbound edit: ${chosen}`, time: now },
      { tag: "QUEUE", text: "BullMQ debounce 3000ms quiet window started", time: now },
      { tag: "NEO4J", text: "Patched 4 nodes, 6 edges in Neo4j GDS", time: now },
      { tag: "GNN-GRU", text: "ROLAND updated hidden states for k=2 neighbourhood", time: now },
    ]);

    setHighlightedNodes(["root", "e1", "e2", "e3"]);
    setTimeout(() => setHighlightedNodes([]), 2000);
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
      {/* ── Sidebar ───────────────────────────────────────────────────────── */}
      <aside className="flex w-60 shrink-0 flex-col border-r border-black/8 bg-ink-950 lg:w-64">
        {/* Brand */}
        <div className="flex items-center justify-between px-4 py-4">
          <button
            onClick={() => navigate("/")}
            className="flex items-center gap-2 text-sm font-semibold text-parchment-50 transition hover:opacity-80"
          >
            <Server size={12} />
            {backendStatus === "connected" ? "Backend Connected (Port 5000)" : "Simulated Local Orchestration"}
          </span>
          {onedriveStatus.connected ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-500/10 px-3 py-1 text-xs font-medium text-blue-600 ring-1 ring-blue-500/30">
              <Cloud size={12} /> OneDrive: {onedriveStatus.account?.displayName || "Connected"}
            </span>
          ) : (
            <a
              href="http://localhost:5000/api/auth/onedrive/connect"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-full bg-blue-500/10 px-3 py-1 text-xs font-medium text-blue-600 ring-1 ring-blue-500/30 hover:bg-blue-600 hover:text-white transition"
              title="Click to authenticate Microsoft Graph OAuth 2.0"
            >
              <Cloud size={12} /> Connect OneDrive (OAuth 2.0)
            </a>
          )}
          {isAuthenticated && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-600 ring-1 ring-emerald-500/30">
              <CheckCircle2 size={12} /> Authenticated: {user?.name}
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
            className="flex w-full items-center gap-2 rounded-xl border border-white/10 px-3 py-2.5 text-xs font-medium text-white/70 transition hover:border-amber-400/40 hover:bg-white/5 hover:text-parchment-50 disabled:opacity-40"
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
                    className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-[11px] transition ${
                      conv.id === activeConvId
                        ? "bg-white/10 text-parchment-50"
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
                  <p className="truncate text-[9px] text-white/40">{user?.role ?? "Workspace Member"}</p>
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

      {/* ── Chat area ─────────────────────────────────────────────────────── */}
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

          <button
            onClick={() => setGraphOpen((v) => !v)}
            className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[11px] font-medium transition ${
              graphOpen
                ? "bg-ink-950 text-parchment-50"
                : "border border-black/10 text-body-500 hover:border-black/20 hover:text-ink-950"
            }`}
          >
            <LayoutGrid size={12} />
            Graph
            <ChevronRight
              size={12}
              className={`transition-transform ${graphOpen ? "rotate-180" : ""}`}
            />
          </button>
        </header>

        {/* Messages */}
        <div className="flex flex-1 overflow-hidden">
          <div className="flex flex-1 flex-col overflow-y-auto">
            {/* Welcome state or messages */}
            {activeMessages.length <= 1 && !isLoading && isAuthenticated ? (
              <WelcomeState onPreset={(q) => handleSend(q)} />
            ) : (
              <div className="mx-auto w-full max-w-2xl flex-1 px-4 py-6">
                <div className="flex flex-col gap-4">
                  {activeMessages.map((msg, i) => (
                    <MessageBubble
                      key={i}
                      message={msg}
                      onCitationClick={handleCitationClick}
                    />
                  ))}
                  {isLoading && <TypingIndicator />}
                  <div ref={chatEndRef} />
                </div>
              </div>
            )}
          </div>

          {/* Graph panel (collapsible) */}
          <AnimatePresence>
            {graphOpen && (
              <motion.div
                initial={{ width: 0, opacity: 0 }}
                animate={{ width: 340, opacity: 1 }}
                exit={{ width: 0, opacity: 0 }}
                transition={{ duration: 0.25, ease: "easeInOut" }}
                className="hidden shrink-0 overflow-hidden lg:block"
                style={{ width: 340 }}
              >
                <GraphPanel
                  highlightedNodes={highlightedNodes}
                  onClose={() => setGraphOpen(false)}
                />
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Input bar */}
        <div className="shrink-0 border-t border-black/8 bg-white/90 px-4 py-3.5 backdrop-blur">
          <div className="mx-auto flex w-full max-w-2xl items-end gap-3">
            <div className="flex flex-1 items-end rounded-2xl border border-black/10 bg-white shadow-sm transition-all focus-within:border-amber-400 focus-within:ring-2 focus-within:ring-amber-400/20">
              <textarea
                ref={inputRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={isAuthenticated ? "Ask your knowledge graph…" : "Sign in to start chatting"}
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
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-amber-400 text-ink-950 shadow transition hover:bg-amber-500 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-ink-950/30 border-t-ink-950" />
              ) : (
                <Send size={16} />
              )}
            </button>
          </div>
          <p className="mt-2 text-center text-[10px] text-body-500/60">
            KONNECT AI can make mistakes. Responses are grounded in your knowledge graph.
          </p>
        </div>
      </div>
    </div>
  );
}
