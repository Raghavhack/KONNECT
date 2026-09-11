import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowLeft } from "lucide-react";
import { fadeUp, stagger } from "../lib/motion";
import Tag from "../components/shared/Tag";
import AppWindowMock from "../components/shared/AppWindowMock";
import ScrollSpySection from "../components/shared/ScrollSpySection";

import {
  ReliabilityBackoff,
  ReliabilityIdempotency,
  ReliabilityDebounce,
  ReliabilityCache,
} from "../components/shared/PipelineMockups";

const SERVICE_SPLIT = [
  { lang: "JavaScript (Node.js)", role: "Auth, user DB access, client-facing REST API, webhook receipt, job queueing, caching, retry/backoff, billing" },
  { lang: "Python (FastAPI)", role: "Parsing, embeddings, incremental knowledge graph updates, incremental GNN re-embedding, PCST retrieval, LLM answer generation" },
  { lang: "Protobuf over gRPC", role: "Typed contracts between JS and Python; supports streaming for incremental graph-update events" },
];

const DATA_STORES = [
  { store: "PostgreSQL", data: "User accounts, auth, billing/plan state" },
  { store: "Neo4j", data: "Knowledge graph — entities, relationships, communities; native k-hop traversal + GDS Leiden" },
  { store: "Neo4j vector index", data: "Node/edge embeddings for similarity search, colocated with the graph" },
  { store: "Redis", data: "Query→answer semantic cache" },
  { store: "Redis (via BullMQ)", data: "Job queue / webhook event buffer — debouncing, retries, idempotency" },
];

const RELIABILITY = [
  {
    title: "Exponential backoff, max 5 retries",
    desc: "Applied to webhook content fetches and any transient gRPC call, with jitter to avoid thundering-herd retries.",
    mockContent: <ReliabilityBackoff />,
  },
  {
    title: "Idempotency keys",
    desc: "Derived from each webhook's change event ID, checked before enqueueing, so retried deliveries don't double-process.",
    mockContent: <ReliabilityIdempotency />,
  },
  {
    title: "Per-document debouncing",
    desc: "Rapid successive edits to the same file collapse into one job after a short quiet window.",
    mockContent: <ReliabilityDebounce />,
  },
  {
    title: "Cache invalidation",
    desc: "When a cached answer's cited subgraph nodes get updated, the cache entry is evicted or flagged — not left to TTL alone.",
    mockContent: <ReliabilityCache />,
  },
];

export default function Architecture() {
  return (
    <div>
      <section className="mx-auto max-w-4xl px-6 pb-16 pt-28 md:pt-36 text-center">
        <div className="mb-6 flex items-center justify-between text-xs">
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 font-medium text-body-500 hover:text-ink-950 transition"
          >
            <ArrowLeft size={14} /> Back to Home
          </Link>
          <span className="text-body-500 font-mono">KONNECT &rsaquo; Architecture</span>
        </div>
        <motion.div initial="hidden" animate="show" variants={stagger(0.1)}>
          <motion.div variants={fadeUp}>
            <Tag color="sky" className="mb-4">Architecture</Tag>
          </motion.div>
          <motion.h1 variants={fadeUp} className="text-4xl font-semibold tracking-tight text-ink-950 md:text-5xl">
            Two services, one typed contract.
          </motion.h1>
          <motion.p variants={fadeUp} className="mx-auto mt-4 max-w-2xl text-body-500">
            The Python service owns essentially all output the frontend renders. JS is a thin, fast
            layer in front of it.
          </motion.p>
        </motion.div>
      </section>

      {/* service split diagram */}
      <section className="mx-auto max-w-5xl px-6 pb-24">
        <AppWindowMock>
          <motion.div
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, margin: "-80px" }}
            variants={stagger(0.12)}
            className="grid gap-4 p-8 md:grid-cols-3"
          >
            {SERVICE_SPLIT.map((s) => (
              <motion.div
                key={s.lang}
                variants={fadeUp}
                className="rounded-xl border border-white/10 bg-white/5 p-5 text-parchment-50"
              >
                <p className="text-sm font-medium text-amber-400">{s.lang}</p>
                <p className="mt-2 text-xs leading-relaxed text-body-300">{s.role}</p>
              </motion.div>
            ))}
          </motion.div>
        </AppWindowMock>
      </section>

      <ScrollSpySection
        eyebrow="Ingestion → retrieval"
        title="Reliability & data flow."
        steps={RELIABILITY}
      />

      {/* data store table */}
      <section className="mx-auto max-w-4xl px-6 py-24">
        <motion.div
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: "-100px" }}
          variants={stagger(0.08)}
        >
          <motion.h2 variants={fadeUp} className="mb-8 text-2xl font-semibold tracking-tight text-ink-950">
            Data store mapping
          </motion.h2>
          <div className="overflow-hidden rounded-2xl border border-black/5">
            {DATA_STORES.map((row, i) => (
              <motion.div
                key={row.store}
                variants={fadeUp}
                className={`flex flex-col gap-1 px-6 py-4 md:flex-row md:items-center md:gap-6 ${
                  i % 2 === 0 ? "bg-white" : "bg-parchment-50"
                }`}
              >
                <span className="w-full shrink-0 text-sm font-medium text-ink-950 md:w-48">{row.store}</span>
                <span className="text-sm text-body-500">{row.data}</span>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </section>
    </div>
  );
}
