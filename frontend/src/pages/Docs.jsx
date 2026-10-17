import { motion } from "framer-motion";
import { GitFork, FileText, BookOpen, ArrowLeft } from "lucide-react";
import { fadeUp, stagger } from "../lib/motion";
import Tag from "../components/shared/Tag";
import { Link } from "react-router-dom";

const LINKS = [
  { icon: GitFork, title: "Repository", desc: "Source code for the orchestration + intelligence services", href: "https://github.com", external: true },
  { icon: FileText, title: "Live Demo", desc: "Interactive knowledge graph with real-time chat and event stream", href: "/live-demo", external: false },
  { icon: BookOpen, title: "API Reference", desc: "REST and gRPC contracts between the JS and Python services", href: "https://github.com", external: true },
];

const STACK = [
  "Node.js, Express, BullMQ, Redis",
  "Python, FastAPI",
  "PyTorch, PyTorch Geometric, GRU update module (ROLAND)",
  "Prize Collecting Steiner Tree solver (G-Retriever formulation)",
  "Neo4j",
  "Google Drive API, Notion API, Slack API, OAuth 2.0",
  "React + force-directed graph visualisation",
  "Docker",
];

export default function Docs() {
  return (
    <div className="mx-auto max-w-4xl px-6 pb-28 pt-28 md:pt-36">
      <div className="mb-6 flex items-center justify-between text-xs">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 font-medium text-body-500 hover:text-ink-950 transition"
        >
          <ArrowLeft size={14} /> Back to Home
        </Link>
        <span className="text-body-500 font-mono">KONNECT &rsaquo; Documentation</span>
      </div>
      <motion.div initial="hidden" animate="show" variants={stagger(0.1)} className="text-center">
        <motion.div variants={fadeUp}>
          <Tag color="amber" className="mb-4">Docs</Tag>
        </motion.div>
        <motion.h1 variants={fadeUp} className="text-4xl font-semibold tracking-tight text-ink-950 md:text-5xl">
          Resources
        </motion.h1>
      </motion.div>

      <motion.div
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, margin: "-80px" }}
        variants={stagger(0.1)}
        className="mt-14 grid gap-4 md:grid-cols-3"
      >
        {LINKS.map((l) =>
          l.external ? (
            <motion.a
              key={l.title}
              href={l.href}
              target="_blank"
              rel="noreferrer"
              variants={fadeUp}
              className="rounded-2xl border border-black/5 bg-white p-6 transition-all hover:border-amber-400 hover:shadow-md"
            >
              <l.icon size={18} className="mb-4 text-amber-500" />
              <p className="text-sm font-medium text-ink-950">{l.title}</p>
              <p className="mt-1 text-xs text-body-500">{l.desc}</p>
            </motion.a>
          ) : (
            <motion.div key={l.title} variants={fadeUp}>
              <Link
                to={l.href}
                className="block h-full rounded-2xl border border-black/5 bg-white p-6 transition-all hover:border-amber-400 hover:shadow-md"
              >
                <l.icon size={18} className="mb-4 text-amber-500" />
                <p className="text-sm font-medium text-ink-950">{l.title}</p>
                <p className="mt-1 text-xs text-body-500">{l.desc}</p>
              </Link>
            </motion.div>
          )
        )}
      </motion.div>

      <motion.div
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, margin: "-80px" }}
        variants={fadeUp}
        className="mt-16"
      >
        <h2 className="mb-4 text-lg font-medium text-ink-950">Tools &amp; technologies</h2>
        <ul className="grid gap-2 rounded-2xl border border-black/5 bg-white p-6 text-sm text-body-500 md:grid-cols-2">
          {STACK.map((s) => (
            <li key={s} className="flex items-start gap-2">
              <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-amber-400" />
              {s}
            </li>
          ))}
        </ul>
      </motion.div>
    </div>
  );
}
