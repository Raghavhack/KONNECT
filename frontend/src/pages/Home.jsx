import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight, Sparkles, Network, MessageSquare, GitBranch } from "lucide-react";
import heroImg from "../assets/hero-library.png";
import { fadeUp, stagger } from "../lib/motion";
import Tag from "../components/shared/Tag";
import AppWindowMock from "../components/shared/AppWindowMock";
import Marquee from "../components/shared/Marquee";
import ScrollSpySection from "../components/shared/ScrollSpySection";
import GraphCanvas from "../components/shared/GraphCanvas";
import CurveChart from "../components/shared/CurveChart";
import { howItWorksSteps } from "../data/howItWorks";

const TABS = [
  { id: "graph", label: "Graph" },
  { id: "chat", label: "Chat" },
  { id: "architecture", label: "Architecture" },
];

const TECH = [
  { label: "Neo4j" },
  { label: "PyTorch" },
  { label: "Google Drive" },
  { label: "Notion" },
  { label: "Slack" },
  { label: "FastAPI" },
  { label: "BullMQ / Redis" },
];

function HeroMock({ tab }) {
  if (tab === "graph") {
    return (
      <div className="h-72 w-full md:h-96">
        <GraphCanvas
          live
          initialNodes={[
            { id: "root", kind: "Doc", label: "Onboarding.md", x: 320, y: 210 },
            { id: "e1", kind: "Entity", label: "AuthService", x: 260, y: 160 },
            { id: "e2", kind: "Person", label: "Raghav", x: 380, y: 260 },
          ]}
          initialLinks={[
            { source: "root", target: "e1" },
            { source: "root", target: "e2" },
          ]}
        />
      </div>
    );
  }
  if (tab === "chat") {
    return (
      <div className="flex h-72 w-full flex-col justify-end gap-3 p-6 text-sm md:h-96">
        <div className="ml-auto max-w-[75%] rounded-2xl rounded-tr-sm bg-sky-500/20 px-4 py-2.5 text-parchment-50">
          What changed in the onboarding doc this week?
        </div>
        <div className="mr-auto max-w-[80%] rounded-2xl rounded-tl-sm bg-white/5 px-4 py-2.5 text-parchment-50">
          Two sections were revised 40 minutes ago —{" "}
          <span className="text-amber-400">Access &amp; Permissions</span> and{" "}
          <span className="text-amber-400">Rollout Checklist</span>. Citing 3 nodes.
        </div>
      </div>
    );
  }
  return (
    <div className="grid h-72 w-full grid-cols-2 gap-3 p-6 text-xs md:h-96">
      <div className="flex flex-col justify-center gap-2 rounded-xl border border-white/10 bg-white/5 p-3 text-parchment-50">
        <span className="font-medium text-amber-400">Node.js / Express</span>
        Auth, webhooks, BullMQ queue, gRPC client
      </div>
      <div className="flex flex-col justify-center gap-2 rounded-xl border border-white/10 bg-white/5 p-3 text-parchment-50">
        <span className="font-medium text-amber-400">Python / FastAPI</span>
        Parsing, GNN update, PCST retrieval, LLM answers
      </div>
      <div className="col-span-2 flex items-center justify-center gap-2 rounded-xl border border-dashed border-white/15 p-3 text-body-300">
        <GitBranch size={14} /> Protobuf over gRPC, streaming graph-delta events
      </div>
    </div>
  );
}

export default function Home() {
  const [tab, setTab] = useState("graph");
  const [query, setQuery] = useState("");
  const navigate = useNavigate();

  const handleAsk = (e) => {
    e.preventDefault();
    if (query.trim()) {
      navigate(`/live-demo?q=${encodeURIComponent(query.trim())}`);
    } else {
      navigate("/live-demo");
    }
  };

  return (
    <div>
      {/* ---------------- HERO ---------------- */}
      <section className="relative overflow-hidden pt-32 pb-20 md:pt-40 md:pb-28">
        <img
          src={heroImg}
          alt="Sunlit library with arched windows"
          className="absolute inset-0 h-full w-full object-cover object-[center_30%]"
        />
        <div className="absolute inset-0 bg-hero-overlay" />

        <div className="relative z-10 mx-auto max-w-5xl px-6 text-center">
          <motion.div
            variants={stagger(0.12)}
            initial="hidden"
            animate="show"
            className="flex flex-col items-center"
          >
            <motion.div variants={fadeUp}>
              <Tag color="amber" className="mb-6 bg-white/75 backdrop-blur-md">
                <Sparkles size={12} /> Live-synced knowledge graph
              </Tag>
            </motion.div>

            <motion.h1
              variants={fadeUp}
              className="max-w-3xl text-4xl font-semibold leading-tight tracking-tight text-ink-950 md:text-6xl"
            >
              Your knowledge, <span className="text-amber-400">always synced</span>.
            </motion.h1>

            <motion.p variants={fadeUp} className="mt-5 max-w-xl text-base text-ink-950/70 md:text-lg">
              KONNECT builds a live knowledge graph over Drive, Notion and Slack — reacting to every
              edit in near real time, without ever rebuilding the whole corpus.
            </motion.p>

            {/* Interactive Search Query Input */}
            <motion.form
              variants={fadeUp}
              onSubmit={handleAsk}
              className="mt-8 flex w-full max-w-md items-center gap-2 rounded-full bg-white/85 p-1.5 pl-5 shadow-lg ring-1 ring-black/5 backdrop-blur-md transition-all focus-within:ring-2 focus-within:ring-amber-400"
            >
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ask your knowledge graph anything…"
                className="flex-1 bg-transparent text-sm text-ink-950 placeholder:text-ink-950/50 focus:outline-none"
              />
              <button
                type="submit"
                className="flex items-center gap-1.5 rounded-full bg-amber-400 px-4 py-2 text-sm font-medium text-ink-950 transition-colors hover:bg-amber-500"
              >
                Ask <ArrowRight size={14} />
              </button>
            </motion.form>

            <motion.div variants={fadeUp} className="mt-4 flex items-center gap-3">
              <Link
                to="/live-demo"
                className="rounded-full bg-ink-950 px-5 py-2.5 text-sm font-medium text-parchment-50 transition-colors hover:bg-ink-800"
              >
                See it live
              </Link>
              <Link
                to="/research"
                className="rounded-full border border-ink-950/15 bg-white/60 px-5 py-2.5 text-sm font-medium text-ink-950 backdrop-blur-sm transition-colors hover:bg-white"
              >
                Read the research
              </Link>
            </motion.div>
          </motion.div>

          {/* Floating showcase window mock */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.45, duration: 0.55, ease: "easeOut" }}
            className="mt-12 md:mt-16"
          >
            <div className="mb-3 flex justify-center gap-2">
              {TABS.map((t) => (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id)}
                  className={`rounded-full px-4 py-1.5 text-xs font-medium transition-all ${
                    tab === t.id
                      ? "bg-ink-950 text-parchment-50 shadow"
                      : "bg-white/80 text-ink-950/70 backdrop-blur hover:bg-white"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
            <AppWindowMock className="mx-auto max-w-3xl shadow-[0_25px_70px_-15px_rgba(14,14,16,0.35)]">
              <HeroMock tab={tab} />
            </AppWindowMock>
          </motion.div>
        </div>
      </section>

      {/* ---------------- TECH MARQUEE ---------------- */}
      <section className="bg-parchment-50 pb-20 pt-4">
        <div className="mx-auto max-w-4xl px-6">
          <p className="mb-6 text-center text-xs uppercase tracking-wide text-body-500">
            Synced across your stack
          </p>
          <Marquee items={TECH} />
        </div>
      </section>

      {/* ---------------- HOW IT WORKS TEASER (ScrollSpySection) ---------------- */}
      <ScrollSpySection
        eyebrow="How KONNECT works"
        title="One edit, one bounded update."
        steps={howItWorksSteps}
      />

      <div className="bg-parchment-50 py-12 text-center">
        <Link
          to="/how-it-works"
          className="inline-flex items-center gap-1.5 rounded-full border border-black/10 bg-white px-5 py-2.5 text-sm font-medium text-ink-950 shadow-sm transition-colors hover:border-amber-400 hover:text-amber-500"
        >
          See the full pipeline walkthrough <ArrowRight size={14} />
        </Link>
      </div>

      {/* ---------------- ARCHITECTURE TEASER ---------------- */}
      <section className="mx-auto max-w-6xl px-6 py-24">
        <motion.div
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: "-100px" }}
          variants={stagger(0.1)}
          className="grid gap-10 md:grid-cols-2 md:items-center"
        >
          <motion.div variants={fadeUp}>
            <Tag color="sky" className="mb-4">
              Architecture
            </Tag>
            <h2 className="text-3xl font-semibold tracking-tight text-ink-950 md:text-4xl">
              A thin JS orchestration layer, in front of a Python intelligence layer.
            </h2>
            <p className="mt-4 text-body-500">
              Node/Express owns auth, webhooks, the BullMQ job queue and billing. FastAPI owns
              parsing, incremental graph updates, GRU re-embedding and PCST retrieval — talking
              over typed Protobuf/gRPC contracts.
            </p>
            <Link
              to="/architecture"
              className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-ink-950 hover:text-amber-500"
            >
              View full architecture <ArrowRight size={14} />
            </Link>
          </motion.div>

          <motion.div variants={fadeUp} className="grid grid-cols-2 gap-3">
            {[
              { icon: Network, label: "Neo4j graph store", desc: "k-hop traversal, GDS Leiden" },
              { icon: MessageSquare, label: "Cited chat answers", desc: "PCST-grounded generation" },
              { icon: GitBranch, label: "gRPC contracts", desc: "Typed JS ↔ Python transport" },
              { icon: Sparkles, label: "Semantic cache", desc: "Redis, query→answer pairs" },
            ].map((item) => (
              <div
                key={item.label}
                className="rounded-2xl border border-black/5 bg-white p-5 shadow-sm transition-all hover:shadow-md"
              >
                <item.icon size={18} className="mb-3 text-amber-500" />
                <p className="text-sm font-medium text-ink-950">{item.label}</p>
                <p className="mt-1 text-xs text-body-500">{item.desc}</p>
              </div>
            ))}
          </motion.div>
        </motion.div>
      </section>

      {/* ---------------- EVALUATION TEASER ---------------- */}
      <section className="mx-auto max-w-6xl px-6 py-16">
        <div className="relative overflow-hidden rounded-4xl border border-black/10 bg-gradient-to-b from-[#181A20] via-[#14151A] to-[#101114] p-8 md:p-14 text-parchment-50 shadow-2xl">
          <div className="pointer-events-none absolute -top-24 right-1/4 h-80 w-80 rounded-full bg-amber-400/10 blur-3xl" />
          <motion.div
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, margin: "-100px" }}
            variants={stagger(0.1)}
            className="relative z-10"
          >
            <motion.div variants={fadeUp}>
              <Tag color="amber" className="mb-4">
                Evaluation
              </Tag>
              <h2 className="max-w-xl text-2xl font-bold tracking-tight md:text-4xl text-white">
                Update cost scales with the edit, not the corpus.
              </h2>
              <p className="mt-2 text-xs md:text-sm text-body-300/80">
                Incremental update latency stays constant as workspace size multiplies.
              </p>
            </motion.div>
            <motion.div variants={fadeUp} className="mt-8 rounded-2xl border border-white/10 bg-[#121316] p-6 shadow-xl">
              <CurveChart />
            </motion.div>
            <motion.div variants={fadeUp} className="mt-6">
              <Link
                to="/results"
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-amber-400 hover:text-amber-300 transition"
              >
                See the full evaluation plan &amp; methodology <ArrowRight size={14} />
              </Link>
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* ---------------- TEAM ---------------- */}
      <section className="mx-auto max-w-6xl px-6 py-24">
        <motion.div
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: "-100px" }}
          variants={stagger(0.1)}
        >
          <motion.div variants={fadeUp}>
            <Tag color="sky" className="mb-4">
              Team
            </Tag>
            <h2 className="text-3xl font-semibold tracking-tight text-ink-950 md:text-4xl">
              Built at Punjab Engineering College.
            </h2>
          </motion.div>
          <motion.div variants={fadeUp} className="mt-8 flex flex-wrap gap-3">
            {["Raghav Rastogi", "Pranay Mehta", "Aarav Sharma", "Manas Ranjan Jena"].map((name) => (
              <span
                key={name}
                className="rounded-full border border-black/10 bg-white px-4 py-2 text-sm text-ink-950 shadow-sm"
              >
                {name}
              </span>
            ))}
          </motion.div>
          <motion.p variants={fadeUp} className="mt-4 text-sm text-body-500">
            Under the mentorship of Dr. Sucheta, Department of Mathematics &amp; Computing.
          </motion.p>
        </motion.div>
      </section>

      {/* ---------------- FINAL CTA ---------------- */}
      <section className="mx-auto max-w-6xl px-6 pb-28">
        <motion.div
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: "-100px" }}
          variants={fadeUp}
          className="flex flex-col items-center gap-6 rounded-4xl bg-ink-950 px-8 py-16 text-center text-parchment-50 shadow-2xl"
        >
          <h2 className="max-w-xl text-3xl font-semibold tracking-tight md:text-4xl">
            Watch an edit become an answer.
          </h2>
          <p className="max-w-md text-body-300">
            Try the live demo — edit a document and watch the graph, then the chat, update within
            seconds.
          </p>
          <Link
            to="/live-demo"
            className="flex items-center gap-1.5 rounded-full bg-amber-400 px-6 py-3 text-sm font-medium text-ink-950 transition-colors hover:bg-amber-500"
          >
            Open the live demo <ArrowRight size={14} />
          </Link>
        </motion.div>
      </section>
    </div>
  );
}
