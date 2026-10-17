/**
 * KONNECT Mock API
 *
 * Mirrors the real backend contract so the frontend never needs to change
 * when the real Node.js / Python services come online.
 *
 * Real endpoints (not yet live):
 *   GET  /api/health
 *   POST /api/query          → Python intelligence service (PCST retrieval + LLM)
 *   POST /api/simulate-edit  → Webhook ingestion simulation
 *   GET  /api/conversations
 *   POST /api/conversations
 *   DEL  /api/conversations/:id
 *
 * WebSocket:  ws://localhost:5000/graph-delta-stream
 */

const LATENCY = { min: 400, max: 1100 };
const delay = (ms) => new Promise((r) => setTimeout(r, ms));
const rand = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;
const jitter = () => delay(rand(LATENCY.min, LATENCY.max));

// ─── Knowledge base (demo responses) ──────────────────────────────────────────

const KB = {
  "what changed in the onboarding doc": {
    answer:
      "The **Access & Permissions** and **Rollout Checklist** sections were revised in `Onboarding Guide.md` 42 minutes ago. Three entity nodes were patched and two cache entries invalidated.",
    citations: [
      { id: "root", label: "Onboarding.md", kind: "Doc" },
      { id: "e1", label: "AuthService", kind: "Entity" },
      { id: "e2", label: "Raghav", kind: "Person" },
    ],
    logEvents: [
      { tag: "QUERY", text: 'PCST solver received: "What changed in the onboarding doc"' },
      { tag: "PCST", text: "Retrieved minimal connected reasoning tree (score: 0.94)" },
      { tag: "LLM", text: "Grounded answer generated via Anthropic claude-3-opus" },
    ],
  },
  "which entities connect to authservice": {
    answer:
      "**AuthService** connects to `SessionStore`, `OAuthProvider`, and `UserCluster` via authenticated gRPC streaming channels. The relationship was last updated when `Architecture.pdf` was revised.",
    citations: [
      { id: "e1", label: "AuthService", kind: "Entity" },
      { id: "e3", label: "PCST Subgraph", kind: "Topic" },
    ],
    logEvents: [
      { tag: "QUERY", text: 'Graph traversal: k=2 neighbourhood of "AuthService"' },
      { tag: "NEO4J", text: "Cypher returned 3 direct neighbours in 6 ms" },
      { tag: "LLM", text: "Relationship summary generated" },
    ],
  },
  "show pcst subgraph for permissions": {
    answer:
      "The **Prize-Collecting Steiner Tree** solver extracted a minimal connected subgraph linking `UserRole`, `PermissionGate`, and `VaultToken` with total prize weight **4.82**. Edge density: 3 edges / 3 nodes.",
    citations: [
      { id: "root", label: "Onboarding.md", kind: "Doc" },
      { id: "e1", label: "AuthService", kind: "Entity" },
      { id: "e3", label: "PCST Subgraph", kind: "Topic" },
    ],
    logEvents: [
      { tag: "PCST", text: "Prize assignment: cosine similarity scored 12 candidate nodes" },
      { tag: "PCST", text: "pcst_fast solver returned optimal tree (3 nodes, 3 edges)" },
      { tag: "LLM", text: "Subgraph serialised into prompt context" },
    ],
  },
  "who last edited architecture.pdf": {
    answer:
      "**Architecture.pdf** was committed by **Raghav Rastogi** 42 minutes ago. The diff touched the gRPC transport spec and Neo4j schema definitions — 6 nodes and 9 edges were updated downstream.",
    citations: [
      { id: "root", label: "Onboarding.md", kind: "Doc" },
      { id: "e2", label: "Raghav", kind: "Person" },
    ],
    logEvents: [
      { tag: "WEBHOOK", text: "Drive push: Architecture.pdf (rev 22c)" },
      { tag: "NEO4J", text: "Patched 6 nodes, 9 edges in 8 ms" },
    ],
  },
};

const normalise = (text) =>
  text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, "")
    .trim();

const matchKB = (text) => {
  const n = normalise(text);
  for (const [key, val] of Object.entries(KB)) {
    if (n.includes(key)) return val;
  }
  return null;
};

const fallbackResponse = (text) => ({
  answer: `Grounded subgraph retrieved for: *"${text}"*\n\nBounded GNN search (k=2) returned 1 connected cluster citing 2 source documents. PCST solver score: **0.87**.`,
  citations: [
    { id: "root", label: "Onboarding.md", kind: "Doc" },
    { id: "e1", label: "AuthService", kind: "Entity" },
  ],
  logEvents: [
    { tag: "QUERY", text: `PCST solver received: "${text.slice(0, 32)}…"` },
    { tag: "PCST", text: "Retrieved minimal connected reasoning tree (score: 0.87)" },
    { tag: "LLM", text: "Grounded answer generated" },
  ],
});

// ─── Health ────────────────────────────────────────────────────────────────────

/**
 * GET /api/health
 * @returns {{ status: "connected" | "simulated" }}
 */
export async function healthCheck() {
  try {
    const res = await fetch("/api/health");
    if (res.ok) return { status: "connected" };
    return { status: "simulated" };
  } catch {
    return { status: "simulated" };
  }
}

// ─── Conversations ─────────────────────────────────────────────────────────────

let _convCounter = 1;

/**
 * GET /api/conversations
 * @returns {Promise<Array<{ id: string; title: string; createdAt: string }>>}
 */
export async function getConversations() {
  await delay(80);
  return []; // Will be populated from localStorage in the UI layer
}

/**
 * POST /api/conversations
 * @returns {Promise<{ id: string; title: string; createdAt: string }>}
 */
export async function createConversation() {
  await delay(60);
  return {
    id: `conv-${Date.now()}-${_convCounter++}`,
    title: "New conversation",
    createdAt: new Date().toISOString(),
  };
}

// ─── Query ─────────────────────────────────────────────────────────────────────

/**
 * POST /api/query
 *
 * Mirrors:
 *   JS layer → validates session, checks Redis semantic cache
 *   Python layer → PCST retrieval + LLM answer generation
 *
 * @param {string} text  User query
 * @param {string} sessionId
 * @returns {Promise<{
 *   answer: string;
 *   citations: Array<{ id: string; label: string; kind: string }>;
 *   logEvents: Array<{ tag: string; text: string }>;
 *   cached: boolean;
 * }>}
 */
export async function sendQuery(text, _sessionId) {
  await jitter();
  const matched = matchKB(text) ?? fallbackResponse(text);
  return { ...matched, cached: false };
}

// ─── Simulate edit (webhook ingestion) ────────────────────────────────────────

const EDIT_SOURCES = [
  "Drive: SecurityAudit.md",
  "Notion: Sprint Backlog",
  "Slack: #incident-room",
  "Drive: Architecture.pdf",
  "Notion: Q3 Roadmap",
];

/**
 * POST /api/simulate-edit
 * Simulates a Drive/Notion/Slack webhook arriving at the JS orchestration layer.
 *
 * @returns {Promise<{
 *   source: string;
 *   logEvents: Array<{ tag: string; text: string; time: string }>;
 *   affectedNodes: string[];
 * }>}
 */
export async function triggerEdit() {
  await delay(rand(200, 600));
  const source = EDIT_SOURCES[rand(0, EDIT_SOURCES.length - 1)];
  const now = new Date().toLocaleTimeString();
  return {
    source,
    logEvents: [
      { tag: "WEBHOOK", text: `Inbound edit: ${source}`, time: now },
      { tag: "QUEUE", text: "BullMQ debounce 300 ms quiet window passed", time: now },
      { tag: "PARSER", text: "FastAPI parsed AST: +4 entities, +3 relations", time: now },
      { tag: "NEO4J", text: "Patched 4 nodes, 6 edges in Neo4j GDS", time: now },
      { tag: "GNN-GRU", text: "ROLAND updated hidden states for k=2 neighbourhood", time: now },
      { tag: "CACHE", text: "Semantic cache: 1 dependent query hash evicted", time: now },
    ],
    affectedNodes: ["root", "e1", "e2", "e3"],
  };
}

// ─── Event stream (simulates WebSocket graph-delta-stream) ────────────────────

const STREAM_EVENTS = [
  { tag: "WEBHOOK", text: "Drive push: Onboarding Guide.md (rev 14b)" },
  { tag: "QUEUE", text: "Debounced 3 rapid keystroke saves into job #819" },
  { tag: "PARSER", text: "FastAPI parsed AST: +6 entities, +4 relations" },
  { tag: "NEO4J", text: "Cypher MERGE: Patched 6 nodes, 9 edges in 8 ms" },
  { tag: "GNN-GRU", text: "ROLAND GRU re-embedded 2-hop neighbourhood (142 nodes)" },
  { tag: "CACHE", text: "Semantic cache invalidated 2 dependent query hashes" },
  { tag: "PCST", text: "Subgraph prizes recomputed for 12 query vectors" },
  { tag: "CONNECTED", text: "Heartbeat — gRPC stream healthy (latency: 4 ms)" },
];

let _streamIdx = 0;

/**
 * Simulates the WebSocket `graph-delta-stream` channel.
 * Call `stop()` on the returned object to disconnect.
 *
 * @param {(event: { tag: string; text: string; time: string }) => void} onEvent
 * @param {number} intervalMs
 */
export function streamEvents(onEvent, intervalMs = 3200) {
  const id = setInterval(() => {
    const ev = STREAM_EVENTS[_streamIdx % STREAM_EVENTS.length];
    onEvent({ ...ev, time: new Date().toLocaleTimeString() });
    _streamIdx++;
  }, intervalMs);

  return { stop: () => clearInterval(id) };
}
