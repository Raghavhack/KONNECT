    import { useState, useEffect, useRef, useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Send,
  Zap,
  PlusCircle,
  Info,
  Sparkles,
  Server,
  Lock,
  ArrowRight,
  ArrowLeft,
  Terminal,
  Activity,
  CheckCircle2,
  ShieldCheck,
  Cloud,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { fadeUp, stagger } from "../lib/motion";
import Tag from "../components/shared/Tag";
import AppWindowMock from "../components/shared/AppWindowMock";
import GraphCanvas from "../components/shared/GraphCanvas";

const SCRIPTED_EVENTS = [
  { tag: "WEBHOOK", text: "Drive push: Onboarding Guide.md (rev 14b)", time: "12:44:01" },
  { tag: "QUEUE", text: "Debounced 3 rapid keystroke saves into job #819", time: "12:44:01" },
  { tag: "PARSER", text: "FastAPI parsed AST: +6 entities, +4 relations", time: "12:44:02" },
  { tag: "NEO4J", text: "Cypher MERGE: Patched 6 nodes, 9 edges in 8ms", time: "12:44:02" },
  { tag: "GNN-GRU", text: "ROLAND GRU re-embedded 2-hop neighbourhood (142 nodes)", time: "12:44:03" },
  { tag: "CACHE", text: "Semantic cache invalidated 2 dependent query hashes", time: "12:44:03" },
];

const PRESET_QUERIES = [
  "What changed in the onboarding doc?",
  "Which entities connect to AuthService?",
  "Show PCST subgraph for permissions",
  "Who last edited Architecture.pdf?",
];

const KNOWLEDGE_BASE_RESPONSES = {
  "what changed in the onboarding doc?": {
    text: "The Access & Permissions and Rollout Checklist sections were revised in Onboarding Guide.md. 3 entities were patched.",
    citations: ["root", "e1", "e2"],
  },
  "which entities connect to authservice?": {
    text: "AuthService connects to SessionStore, OAuthProvider, and UserCluster via authenticated gRPC streaming channels.",
    citations: ["e1", "e3"],
  },
  "show pcst subgraph for permissions": {
    text: "The Prize-Collecting Steiner Tree solver extracted a minimal connected subgraph linking UserRole, PermissionGate, and VaultToken with total prize weight 4.82.",
    citations: ["root", "e1", "e3"],
  },
  "who last edited architecture.pdf?": {
    text: "Architecture.pdf was committed by Raghav Rastogi 42 minutes ago, touching the gRPC transport spec and Neo4j schema definitions.",
    citations: ["root", "e2"],
  },
};

export default function LiveDemo() {
  const [searchParams] = useSearchParams();
  const initialQuery = searchParams.get("q") || "";
  const { isAuthenticated, user, loginAsDemo } = useAuth();

  const [log, setLog] = useState([
    { tag: "SYSTEM", text: "KONNECT Knowledge Ingestion Stream ready", time: "12:40:00" },
    { tag: "CONNECTED", text: "Listening on Redis channel: gRPC graph-delta-stream", time: "12:40:01" },
  ]);
  const [chat, setChat] = useState([
    {
      role: "assistant",
      text: "Hello! I am KONNECT's live knowledge assistant. Ask questions grounded in your Drive, Notion, and Slack workspace.",
      citations: [],
    },
  ]);
  const [inputMessage, setInputMessage] = useState("");
  const [selectedNode, setSelectedNode] = useState(null);
  const [highlightedNodes, setHighlightedNodes] = useState([]);
  const [backendStatus, setBackendStatus] = useState("checking");
  const [terminalTab, setTerminalTab] = useState("event-stream");
  const logEndRef = useRef(null);
  const chatEndRef = useRef(null);

  // Initial nodes for GraphCanvas
  const initialNodes = useMemo(
    () => [
      { id: "root", kind: "Doc", label: "Onboarding.md", x: 320, y: 210 },
      { id: "e1", kind: "Entity", label: "AuthService", x: 240, y: 150 },
      { id: "e2", kind: "Person", label: "Raghav", x: 400, y: 270 },
      { id: "e3", kind: "Topic", label: "PCST Subgraph", x: 420, y: 120 },
    ],
    []
  );

  const initialLinks = useMemo(
    () => [
      { source: "root", target: "e1" },
      { source: "root", target: "e2" },
      { source: "e1", target: "e3" },
    ],
    []
  );

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

  // Periodic simulated events
  useEffect(() => {
    if (!isAuthenticated) return;
    let i = 0;
    const interval = setInterval(() => {
      const ev = SCRIPTED_EVENTS[i % SCRIPTED_EVENTS.length];
      const now = new Date().toLocaleTimeString();
      setLog((prev) => [...prev.slice(-15), { ...ev, time: now }]);
      i++;
    }, 3200);
    return () => clearInterval(interval);
  }, [isAuthenticated]);

  // Auto-scroll log
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [log]);

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat]);

  // Handle query parameter from Home hero
  useEffect(() => {
    if (initialQuery && isAuthenticated) {
      handleSendMessage(initialQuery);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuery, isAuthenticated]);

  const handleSendMessage = (textToSend) => {
    const queryText = (textToSend || inputMessage).trim();
    if (!queryText) return;

    // Add user question
    setChat((prev) => [...prev, { role: "user", text: queryText }]);
    setInputMessage("");

    // Look up answer or generate one
    const normalized = queryText.toLowerCase();
    const matched =
      KNOWLEDGE_BASE_RESPONSES[normalized] || {
        text: `Retrieved grounded subgraph for: "${queryText}". Bounded GNN search returned 1 connected cluster citing 2 documents.`,
        citations: ["root", "e1"],
      };

    const time = new Date().toLocaleTimeString();
    setLog((prev) => [
      ...prev.slice(-15),
      { tag: "QUERY", text: `PCST solver received: "${queryText.slice(0, 28)}..."`, time },
      { tag: "PCST", text: "Retrieved minimal connected reasoning tree (0.94 score)", time },
    ]);

    setTimeout(() => {
      setChat((prev) => [
        ...prev,
        {
          role: "assistant",
          text: matched.text,
          citations: matched.citations,
        },
      ]);
      setHighlightedNodes(matched.citations);
    }, 600);
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

  const getBadgeColor = (tag) => {
    switch (tag) {
      case "WEBHOOK":
        return "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";
      case "QUEUE":
        return "bg-sky-500/15 text-sky-400 border-sky-500/30";
      case "NEO4J":
        return "bg-amber-400/15 text-amber-400 border-amber-400/30";
      case "GNN-GRU":
        return "bg-purple-500/15 text-purple-400 border-purple-500/30";
      case "PCST":
      case "QUERY":
        return "bg-yellow-400/15 text-yellow-300 border-yellow-400/30";
      default:
        return "bg-white/10 text-body-300 border-white/10";
    }
  };

  return (
    <div className="mx-auto max-w-6xl px-6 pb-28 pt-28 md:pt-36">
      {/* Top Breadcrumb navigation */}
      <div className="mb-6 flex items-center justify-between text-xs">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 font-medium text-body-500 hover:text-ink-950 transition"
        >
          <ArrowLeft size={14} /> Back to Home
        </Link>
        <span className="text-body-500 font-mono">KONNECT Workspace &rsaquo; Live Demo</span>
      </div>

      {/* Header section */}
      <motion.div initial="hidden" animate="show" variants={stagger(0.1)} className="text-center">
        <motion.div variants={fadeUp} className="flex flex-wrap items-center justify-center gap-3">
          <Tag color="amber">
            <Zap size={12} /> Live demo
          </Tag>
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
              backendStatus === "connected"
                ? "bg-emerald-500/10 text-emerald-600 ring-1 ring-emerald-500/30"
                : "bg-black/5 text-body-500 ring-1 ring-black/10"
            }`}
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
          )}
        </motion.div>

        <motion.h1 variants={fadeUp} className="mt-4 text-3xl font-bold tracking-tight text-ink-950 md:text-5xl">
          Edit a document. Watch it propagate.
        </motion.h1>

        <motion.p variants={fadeUp} className="mx-auto mt-4 max-w-2xl text-sm leading-relaxed text-body-500">
          The force-directed graph synchronizes live across Drive, Notion, and Slack. Ask queries grounded
          in the graph, inspect individual entities, and monitor incremental updates.
        </motion.p>
      </motion.div>

      {/* Main Workspace Area with Protected Auth Wall */}
      <div className="relative mt-10">
        {/* If user is not authenticated: Show beautiful frosted-glass Gate */}
        {!isAuthenticated && (
          <div className="absolute inset-0 z-30 flex flex-col items-center justify-center rounded-3xl bg-white/70 backdrop-blur-md p-6 text-center shadow-2xl ring-1 ring-black/10">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              className="w-full max-w-md rounded-3xl border border-black/10 bg-white p-8 shadow-2xl"
            >
              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-400/20 text-amber-600">
                <Lock size={24} />
              </div>

              <h2 className="text-xl font-bold tracking-tight text-ink-950 md:text-2xl">
                Sign in to access Live Demo
              </h2>

              <p className="mt-2 text-xs leading-relaxed text-body-500">
                The interactive knowledge graph and streaming orchestration engine require an active
                session. You can test it immediately using 1-Click Demo access.
              </p>

              <div className="mt-6 space-y-3">
                <button
                  onClick={loginAsDemo}
                  className="flex w-full items-center justify-center gap-2 rounded-2xl bg-amber-400 py-3 text-sm font-semibold text-ink-950 shadow-md transition hover:bg-amber-500"
                >
                  <Sparkles size={16} />
                  1-Click Instant Demo Access
                </button>

                <div className="grid grid-cols-2 gap-2">
                  <Link
                    to="/login?redirect=/live-demo"
                    className="flex items-center justify-center gap-1 rounded-xl border border-black/10 py-2.5 text-xs font-medium text-ink-950 transition hover:bg-black/5"
                  >
                    Sign in with email
                  </Link>
                  <Link
                    to="/signup?redirect=/live-demo"
                    className="flex items-center justify-center gap-1 rounded-xl bg-ink-950 py-2.5 text-xs font-medium text-parchment-50 transition hover:bg-ink-800"
                  >
                    Create account <ArrowRight size={12} />
                  </Link>
                </div>
              </div>

              <div className="mt-5 flex items-center justify-center gap-1.5 text-[11px] text-body-500">
                <ShieldCheck size={13} className="text-emerald-500" />
                Zero setup required · Pre-populated demo knowledge base
              </div>
            </motion.div>
          </div>
        )}

        {/* Live Workspace Grid (Visible, interactive when signed in) */}
        <div className={`grid gap-6 lg:grid-cols-3 ${!isAuthenticated ? "pointer-events-none select-none opacity-40 blur-[2px]" : ""}`}>
          {/* Graph and Terminal Column */}
          <div className="flex flex-col gap-5 lg:col-span-2">
            {/* Graph Visualizer Canvas */}
            <AppWindowMock title="neo4j-graph-canvas — live-sync-mode">
              <div className="relative h-[400px] w-full bg-[#101114]">
                <GraphCanvas
                  live={isAuthenticated}
                  initialNodes={initialNodes}
                  initialLinks={initialLinks}
                  onSelectNode={(node) => setSelectedNode(node)}
                  selectedNodeId={selectedNode?.id}
                  highlightedNodeIds={highlightedNodes}
                />
              </div>
            </AppWindowMock>

            {/* Selected Node Details Card */}
            <AnimatePresence>
              {selectedNode && (
                <motion.div
                  initial={{ opacity: 0, y: -8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  className="flex items-center justify-between rounded-2xl border border-amber-400/40 bg-amber-400/10 p-4 text-xs text-ink-950 shadow-sm"
                >
                  <div className="flex items-center gap-3">
                    <span className="flex h-8 w-8 items-center justify-center rounded-full bg-amber-400 text-ink-950 font-bold">
                      <Info size={16} />
                    </span>
                    <div>
                      <p className="font-semibold text-sm">
                        Selected Node: <span className="font-mono text-amber-700">{selectedNode.label || selectedNode.id}</span>
                      </p>
                      <p className="text-body-500">
                        Kind: <span className="font-medium text-ink-950">{selectedNode.kind}</span> · Embedding State: <span className="text-emerald-600 font-medium">ROLAND GRU Synced</span>
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleSendMessage(`Tell me about ${selectedNode.label || selectedNode.id}`)}
                      className="rounded-full bg-ink-950 px-3 py-1.5 text-xs font-medium text-parchment-50 transition hover:bg-ink-800"
                    >
                      Query Entity
                    </button>
                    <button
                      onClick={() => setSelectedNode(null)}
                      className="rounded-full border border-black/10 px-2.5 py-1 text-xs text-body-500 hover:bg-black/5"
                    >
                      Dismiss
                    </button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Refined Developer Terminal Console */}
            <div className="overflow-hidden rounded-2xl border border-black/15 bg-[#121316] shadow-xl ring-1 ring-white/5">
              {/* Terminal Top Bar with Tab Switchers */}
              <div className="flex flex-wrap items-center justify-between border-b border-white/10 bg-[#1A1B22] px-4 py-2 text-xs">
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1.5 mr-2">
                    <span className="h-2.5 w-2.5 rounded-full bg-[#FF5F57]/80" />
                    <span className="h-2.5 w-2.5 rounded-full bg-[#FEBC2E]/80" />
                    <span className="h-2.5 w-2.5 rounded-full bg-[#28C840]/80" />
                  </div>
                  <button
                    onClick={() => setTerminalTab("event-stream")}
                    className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 font-mono text-[11px] transition ${
                      terminalTab === "event-stream"
                        ? "bg-white/15 text-white font-medium shadow-sm"
                        : "text-body-300 hover:text-white"
                    }`}
                  >
                    <Terminal size={12} />
                    event-stream.log
                  </button>
                  <button
                    onClick={() => setTerminalTab("neo4j")}
                    className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 font-mono text-[11px] transition ${
                      terminalTab === "neo4j"
                        ? "bg-white/15 text-white font-medium shadow-sm"
                        : "text-body-300 hover:text-white"
                    }`}
                  >
                    <Activity size={12} />
                    neo4j-patch.cypher
                  </button>
                </div>

                <div className="flex items-center gap-3">
                  <span className="flex items-center gap-1.5 font-mono text-[10px] text-emerald-400">
                    <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
                    STREAM ACTIVE
                  </span>
                  <button
                    onClick={handleSimulateEdit}
                    className="flex items-center gap-1.5 rounded-full bg-amber-400/20 px-3 py-1 text-xs font-semibold text-amber-400 ring-1 ring-amber-400/40 transition hover:bg-amber-400 hover:text-ink-950"
                  >
                    <PlusCircle size={12} />
                    Trigger Edit
                  </button>
                </div>
              </div>

              {/* Terminal Body */}
              <div className="h-44 overflow-y-auto p-4 font-mono text-[11px] leading-relaxed text-parchment-50 no-scrollbar">
                {terminalTab === "event-stream" ? (
                  <div className="space-y-1.5">
                    {log.map((entry, idx) => (
                      <div key={idx} className="flex items-start gap-2">
                        <span className="text-body-300/40 select-none text-[10px]">{String(idx + 1).padStart(2, "0")}</span>
                        <span className="text-body-300/60 text-[10px]">{entry.time}</span>
                        <span className={`rounded px-1 py-0.2 text-[9px] font-bold border ${getBadgeColor(entry.tag)}`}>
                          {entry.tag}
                        </span>
                        <span className="text-body-300/90 flex-1">{entry.text}</span>
                      </div>
                    ))}
                    <div ref={logEndRef} />
                  </div>
                ) : (
                  <div className="space-y-2 text-sky-300">
                    <p className="text-body-300">// Active Neo4j Cypher transactional patch queue</p>
                    <p>MATCH (d:Doc &#123;id: $docId&#125;)-[r:MENTIONS]-&gt;(e:Entity)</p>
                    <p>WHERE e.lastSynced &lt; datetime($timestamp)</p>
                    <p>MERGE (d)-[:UPDATED_AT]-&gt;(t:Timestamp &#123;val: $timestamp&#125;)</p>
                    <p className="text-amber-400">&gt; Commited 6 node state updates via bolt://localhost:7687</p>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Interactive Chat Column */}
          <div className="flex flex-col gap-4">
            <AppWindowMock title="konnect-ai-chat — grounded-agent">
              <div className="flex h-[420px] flex-col justify-between bg-[#121316]">
                {/* Chat message bubbles */}
                <div className="flex flex-1 flex-col gap-3 overflow-y-auto p-4 text-xs no-scrollbar">
                  {chat.map((m, i) => (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={`max-w-[90%] rounded-2xl px-4 py-2.5 leading-relaxed ${
                        m.role === "user"
                          ? "ml-auto rounded-tr-sm bg-sky-500/25 text-sky-100 ring-1 ring-sky-500/30"
                          : "mr-auto rounded-tl-sm bg-white/10 text-parchment-50 ring-1 ring-white/10"
                      }`}
                    >
                      <p>{m.text}</p>
                      {m.citations && m.citations.length > 0 && (
                        <div className="mt-2 flex flex-wrap items-center gap-1 border-t border-white/10 pt-2 text-[10px]">
                          <span className="text-body-300">Citing:</span>
                          {m.citations.map((cId) => (
                            <button
                              key={cId}
                              onClick={() => setHighlightedNodes([cId])}
                              className="rounded bg-amber-400/20 px-1.5 py-0.5 font-mono text-amber-400 transition hover:bg-amber-400 hover:text-ink-950"
                            >
                              #{cId}
                            </button>
                          ))}
                        </div>
                      )}
                    </motion.div>
                  ))}
                  <div ref={chatEndRef} />
                </div>

                {/* Input form */}
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleSendMessage();
                  }}
                  className="flex items-center gap-2 border-t border-white/10 bg-[#16171D] p-3"
                >
                  <input
                    type="text"
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    placeholder="Ask your knowledge graph…"
                    className="flex-1 rounded-full bg-white/10 px-4 py-2 text-xs text-parchment-50 placeholder:text-body-300 focus:outline-none focus:ring-1 focus:ring-amber-400"
                  />
                  <button
                    type="submit"
                    aria-label="Send query"
                    className="flex h-8 w-8 items-center justify-center rounded-full bg-amber-400 text-ink-950 transition hover:bg-amber-500"
                  >
                    <Send size={14} />
                  </button>
                </form>
              </div>
            </AppWindowMock>

            {/* Preset Query Suggestions */}
            <div className="rounded-2xl border border-black/5 bg-white p-4 shadow-sm">
              <p className="mb-2.5 text-xs font-semibold text-ink-950 flex items-center gap-1.5">
                <Sparkles size={14} className="text-amber-500" />
                Try Sample Queries:
              </p>
              <div className="flex flex-col gap-1.5">
                {PRESET_QUERIES.map((q) => (
                  <button
                    key={q}
                    onClick={() => handleSendMessage(q)}
                    className="rounded-xl border border-black/5 bg-parchment-50/70 px-3 py-2 text-left text-xs text-ink-950 transition hover:border-amber-400 hover:bg-white"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
