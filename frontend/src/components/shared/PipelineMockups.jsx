import { CheckCircle2, Cpu, GitBranch, RefreshCw, Layers, ShieldCheck, Zap, Terminal } from "lucide-react";

export function StageWebhook() {
  return (
    <div className="flex h-full w-full flex-col justify-between rounded-xl bg-ink-950 p-6 text-left font-mono text-xs">
      <div className="flex items-center justify-between border-b border-white/10 pb-3">
        <div className="flex items-center gap-2 text-emerald-400">
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
          </span>
          POST /api/webhooks/drive
        </div>
        <span className="rounded bg-emerald-500/10 px-2 py-0.5 text-[10px] text-emerald-400">
          200 OK (8ms)
        </span>
      </div>

      <div className="my-4 space-y-2 text-parchment-50">
        <p className="text-body-300">// Inbound Drive change notification</p>
        <div className="rounded-lg bg-white/5 p-3 text-[11px] leading-relaxed">
          <p><span className="text-amber-400">"event"</span>: "sync.document.updated",</p>
          <p><span className="text-amber-400">"documentId"</span>: "1aX9F...Qz8",</p>
          <p><span className="text-amber-400">"title"</span>: "Onboarding Guide.md",</p>
          <p><span className="text-amber-400">"deltaSize"</span>: "+1.4 KB",</p>
          <p><span className="text-amber-400">"idempotencyKey"</span>: "evt_9981a2f4c"</p>
        </div>
      </div>

      <div className="flex items-center justify-between text-[11px] text-body-300">
        <span>Source: Google Drive API v3</span>
        <span className="text-sky-300">Buffer: BullMQ ready</span>
      </div>
    </div>
  );
}

export function StageDebounce() {
  return (
    <div className="flex h-full w-full flex-col justify-between rounded-xl bg-ink-950 p-6 text-left text-xs">
      <div className="flex items-center justify-between border-b border-white/10 pb-3">
        <span className="flex items-center gap-2 font-mono text-amber-400">
          <RefreshCw size={14} className="animate-spin" /> BullMQ Job Debouncer
        </span>
        <span className="rounded bg-amber-400/10 px-2 py-0.5 text-[10px] text-amber-400">
          Quiet Window: 300ms
        </span>
      </div>

      <div className="my-3 space-y-3">
        <p className="text-body-300">Successive edits collapsed into single atomic job:</p>
        <div className="space-y-2">
          {[
            { id: "e1", time: "12:04:12.100", status: "Collapsed" },
            { id: "e2", time: "12:04:12.240", status: "Collapsed" },
            { id: "e3", time: "12:04:12.380", status: "Dispatched to FastAPI" },
          ].map((row, i) => (
            <div
              key={row.id}
              className={`flex items-center justify-between rounded-lg p-2.5 font-mono text-[11px] ${
                i === 2 ? "border border-amber-400/40 bg-amber-400/10 text-parchment-50" : "bg-white/5 text-body-300"
              }`}
            >
              <span>{row.time} · event_{row.id}</span>
              <span className={i === 2 ? "text-amber-400 font-medium" : "text-body-500"}>
                {row.status}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-2 text-[11px] text-emerald-400 font-mono">
        <CheckCircle2 size={13} /> Idempotency check verified · 0 duplicate executions
      </div>
    </div>
  );
}

export function StageReparse() {
  return (
    <div className="flex h-full w-full flex-col justify-between rounded-xl bg-ink-950 p-6 text-left font-mono text-xs">
      <div className="flex items-center justify-between border-b border-white/10 pb-3">
        <span className="flex items-center gap-2 text-sky-400">
          <Terminal size={14} /> FastAPI Document Parser
        </span>
        <span className="text-[10px] text-body-300">AST Diff Extraction</span>
      </div>

      <div className="my-3 space-y-2">
        <div className="rounded-lg bg-emerald-500/10 p-2.5 text-[11px] text-emerald-300">
          + [Section: "Permissions & Access"] Added 6 entities, 4 relationships
        </div>
        <div className="rounded-lg bg-red-500/10 p-2.5 text-[11px] text-red-300">
          - [Section: "Legacy Auth"] Pruned 2 deprecated edges
        </div>
        <div className="rounded-lg bg-white/5 p-2.5 text-[11px] text-body-300">
          = [14 Remaining Sections] Preserved as-is (0 re-parsing cost)
        </div>
      </div>

      <div className="flex items-center justify-between text-[11px] text-amber-400">
        <span>FastAPI Latency: 14ms</span>
        <span>Scope: 1 changed doc</span>
      </div>
    </div>
  );
}

export function StageNeo4j() {
  return (
    <div className="flex h-full w-full flex-col justify-between rounded-xl bg-ink-950 p-6 text-left text-xs">
      <div className="flex items-center justify-between border-b border-white/10 pb-3">
        <span className="flex items-center gap-2 font-mono text-sky-400">
          <GitBranch size={14} /> Neo4j Partial Invalidation
        </span>
        <span className="rounded bg-sky-500/10 px-2 py-0.5 font-mono text-[10px] text-sky-300">
          MATCH &amp; MERGE
        </span>
      </div>

      <div className="my-3 grid grid-cols-2 gap-2 text-center font-mono">
        <div className="rounded-lg border border-amber-400/30 bg-amber-400/10 p-3">
          <p className="text-2xl font-semibold text-amber-400">6</p>
          <p className="text-[11px] text-body-300">Nodes Patched</p>
        </div>
        <div className="rounded-lg border border-white/10 bg-white/5 p-3">
          <p className="text-2xl font-semibold text-parchment-50">11,994</p>
          <p className="text-[11px] text-body-300">Nodes Untouched (99.9%)</p>
        </div>
      </div>

      <div className="rounded-lg bg-white/5 p-2 font-mono text-[10px] text-body-300">
        Cypher: MATCH (d:Doc &#123;id: $docId&#125;)-[r]-&gt;(e) MERGE ...
      </div>
    </div>
  );
}

export function StageROLAND() {
  return (
    <div className="flex h-full w-full flex-col justify-between rounded-xl bg-ink-950 p-6 text-left text-xs">
      <div className="flex items-center justify-between border-b border-white/10 pb-3 font-mono">
        <span className="flex items-center gap-2 text-amber-400">
          <Cpu size={14} /> ROLAND GRU Re-Embedding
        </span>
        <span className="text-[10px] text-body-300">k-hop: 2 hops</span>
      </div>

      <div className="my-3 space-y-2 font-mono">
        <div className="rounded-lg bg-white/5 p-3 text-center">
          <p className="text-sm font-semibold text-amber-400">
            h<sub>v</sub><sup>(t)</sup> = GRU( h<sub>v</sub><sup>(t-1)</sup> , m<sub>v</sub><sup>(t)</sup> )
          </p>
          <p className="mt-1 text-[10px] text-body-300">
            Incremental hidden state update rule
          </p>
        </div>
        <div className="flex justify-between text-[11px] text-body-300">
          <span>Target: 142 affected nodes</span>
          <span className="text-emerald-400 font-medium">Recomputed in 11ms</span>
        </div>
      </div>

      <div className="text-[11px] text-body-300">
        Full graph re-embedding skipped · Zero global loss of structure
      </div>
    </div>
  );
}

export function StagePCST() {
  return (
    <div className="flex h-full w-full flex-col justify-between rounded-xl bg-ink-950 p-6 text-left text-xs">
      <div className="flex items-center justify-between border-b border-white/10 pb-3 font-mono">
        <span className="flex items-center gap-2 text-sky-400">
          <Layers size={14} /> G-Retriever PCST Solver
        </span>
        <span className="text-[10px] text-body-300">Prize Collecting Steiner Tree</span>
      </div>

      <div className="my-3 space-y-2">
        <p className="text-body-300">Formulation maximizes relevance while penalizing edge travel:</p>
        <div className="rounded-lg bg-white/5 p-2.5 font-mono text-[11px] text-parchment-50">
          max &#931;<sub>v &isin; T</sub> &pi;<sub>v</sub> &minus; &#931;<sub>e &isin; T</sub> c<sub>e</sub>
        </div>
        <div className="flex items-center justify-between font-mono text-[11px] text-amber-400">
          <span>Connected Subgraph: 1</span>
          <span>Relevant Nodes: 8</span>
        </div>
      </div>

      <div className="flex items-center gap-1.5 text-[11px] text-emerald-400">
        <CheckCircle2 size={13} /> Yields 1 unified, explainable reasoning subgraph
      </div>
    </div>
  );
}

export function StageCitedAnswer() {
  return (
    <div className="flex h-full w-full flex-col justify-between rounded-xl bg-ink-950 p-6 text-left text-xs">
      <div className="flex items-center justify-between border-b border-white/10 pb-3">
        <span className="flex items-center gap-2 font-medium text-parchment-50">
          <Zap size={14} className="text-amber-400" /> Grounded Answer Generation
        </span>
        <span className="rounded bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-400">
          Faithfulness: 99.4%
        </span>
      </div>

      <div className="my-3 rounded-xl border border-white/10 bg-white/5 p-3.5 leading-relaxed text-parchment-50">
        <p className="text-xs">
          "The Access &amp; Permissions section was updated{" "}
          <span className="inline-flex items-center rounded bg-amber-400/20 px-1.5 py-0.5 text-[10px] font-mono text-amber-400">
            [Doc: #12 &sect;3]
          </span>{" "}
          granting read-only scopes to the analytics service{" "}
          <span className="inline-flex items-center rounded bg-sky-400/20 px-1.5 py-0.5 text-[10px] font-mono text-sky-300">
            [Entity: AnalyticsCluster]
          </span>
          ."
        </p>
      </div>

      <div className="flex items-center justify-between text-[11px] text-body-300">
        <span>Citing 3 verified graph nodes</span>
        <span className="text-amber-400">End-to-end sync: 420ms</span>
      </div>
    </div>
  );
}

// Reliability Visual Mockups for Architecture.jsx
export function ReliabilityBackoff() {
  return (
    <div className="flex h-full w-full flex-col justify-between rounded-xl bg-ink-950 p-6 text-left font-mono text-xs">
      <div className="flex items-center justify-between border-b border-white/10 pb-3">
        <span className="text-amber-400">Exponential Backoff &amp; Jitter</span>
        <span className="rounded bg-white/10 px-2 py-0.5 text-[10px] text-parchment-50">Max 5 Retries</span>
      </div>
      <div className="my-3 space-y-2 text-[11px]">
        <div className="flex justify-between rounded bg-white/5 p-2 text-body-300">
          <span>Attempt #1: Immediate</span>
          <span className="text-amber-400">429 Rate Limit</span>
        </div>
        <div className="flex justify-between rounded bg-white/5 p-2 text-body-300">
          <span>Attempt #2: +200ms &plusmn; jitter</span>
          <span className="text-amber-400">503 Unavailable</span>
        </div>
        <div className="flex justify-between rounded bg-emerald-500/10 p-2 text-emerald-300">
          <span>Attempt #3: +480ms</span>
          <span>200 Success</span>
        </div>
      </div>
      <p className="text-[10px] text-body-300">Decorrelated full-jitter prevents thundering herds</p>
    </div>
  );
}

export function ReliabilityIdempotency() {
  return (
    <div className="flex h-full w-full flex-col justify-between rounded-xl bg-ink-950 p-6 text-left font-mono text-xs">
      <div className="flex items-center justify-between border-b border-white/10 pb-3">
        <span className="text-sky-400 flex items-center gap-1.5"><ShieldCheck size={14} /> Idempotency Keys</span>
        <span className="text-[10px] text-emerald-400">Redis Lock TTL: 60s</span>
      </div>
      <div className="my-3 space-y-2">
        <p className="text-[11px] text-body-300">Key = SHA256(source + docId + revTimestamp)</p>
        <div className="rounded bg-white/5 p-3 text-[11px] text-parchment-50">
          SET key "processing" NX EX 60
        </div>
        <p className="text-[11px] text-emerald-400">&check; Duplicate webhook deliver returned 200 without re-running</p>
      </div>
      <p className="text-[10px] text-body-300">Zero double-processing on network retries</p>
    </div>
  );
}

export function ReliabilityDebounce() {
  return (
    <div className="flex h-full w-full flex-col justify-between rounded-xl bg-ink-950 p-6 text-left font-mono text-xs">
      <div className="flex items-center justify-between border-b border-white/10 pb-3">
        <span className="text-amber-400">Per-Document Debouncing</span>
        <span className="text-[10px] text-sky-300">Sliding Window</span>
      </div>
      <div className="my-3 space-y-2">
        <p className="text-body-300">When user types continuously in Notion or Drive:</p>
        <div className="rounded bg-white/5 p-3 space-y-1 text-[11px] text-body-300">
          <p>&bull; 12:00:01.00 - Keystroke 1 (Timer started)</p>
          <p>&bull; 12:00:01.12 - Keystroke 2 (Timer reset)</p>
          <p>&bull; 12:00:01.28 - Keystroke 3 (Timer reset)</p>
          <p className="text-emerald-400 font-medium">&bull; 12:00:01.58 - Window quiet &rarr; Job Dispatched</p>
        </div>
      </div>
      <p className="text-[10px] text-body-300">Reduces compute calls by up to 92%</p>
    </div>
  );
}

export function ReliabilityCache() {
  return (
    <div className="flex h-full w-full flex-col justify-between rounded-xl bg-ink-950 p-6 text-left font-mono text-xs">
      <div className="flex items-center justify-between border-b border-white/10 pb-3">
        <span className="text-emerald-400">Selective Cache Invalidation</span>
        <span className="text-[10px] text-amber-400">Redis Eviction</span>
      </div>
      <div className="my-3 space-y-2 text-[11px]">
        <p className="text-body-300">Query answers record cited node IDs as reverse tags:</p>
        <div className="rounded bg-white/5 p-2.5 text-parchment-50">
          TAG:node_n12 &rarr; [query_hash_a, query_hash_b]
        </div>
        <div className="rounded bg-amber-400/10 p-2.5 text-amber-300">
          Node n12 patched &rarr; Targeted eviction of 2 entries only
        </div>
      </div>
      <p className="text-[10px] text-body-300">Unrelated cached answers stay warm at 100%</p>
    </div>
  );
}
