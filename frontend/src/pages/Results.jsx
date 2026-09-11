import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowLeft } from "lucide-react";
import { fadeUp, stagger } from "../lib/motion";
import Tag from "../components/shared/Tag";
import CountUpStat from "../components/shared/CountUpStat";
import CurveChart from "../components/shared/CurveChart";

export default function Results() {
  return (
    <div className="mx-auto max-w-5xl px-6 pb-28 pt-28 md:pt-36">
      <div className="mb-6 flex items-center justify-between text-xs">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 font-medium text-body-500 hover:text-ink-950 transition"
        >
          <ArrowLeft size={14} /> Back to Home
        </Link>
        <span className="text-body-500 font-mono">KONNECT &rsaquo; Evaluation &amp; Results</span>
      </div>
      <motion.div initial="hidden" animate="show" variants={stagger(0.1)} className="text-center">
        <motion.div variants={fadeUp}>
          <Tag color="amber" className="mb-4">Evaluation plan</Tag>
        </motion.div>
        <motion.h1 variants={fadeUp} className="text-4xl font-semibold tracking-tight text-ink-950 md:text-5xl">
          Two axes, two research gaps.
        </motion.h1>
        <motion.p variants={fadeUp} className="mx-auto mt-4 max-w-2xl text-body-500">
          Retrieval quality (PCST-grounded vs. naive vector similarity) and update efficiency
          (incremental vs. full rebuild), across workspaces of increasing size. Numbers below are
          illustrative placeholders — benchmark data drops in once available.
        </motion.p>
      </motion.div>

      <motion.div
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, margin: "-100px" }}
        variants={stagger(0.1)}
        className="mt-16 grid grid-cols-2 gap-8 rounded-3xl border border-black/5 bg-white p-8 md:grid-cols-4"
      >
        <motion.div variants={fadeUp}>
          <CountUpStat target={11} suffix=" ms" label="Median incremental update latency" />
        </motion.div>
        <motion.div variants={fadeUp}>
          <CountUpStat target={230} suffix=" ms" label="Full-rebuild latency at 12k entities" />
        </motion.div>
        <motion.div variants={fadeUp}>
          <CountUpStat target={98} suffix="%" label="Nodes left untouched per edit" />
        </motion.div>
        <motion.div variants={fadeUp}>
          <CountUpStat target={20} label="Entities typically touched per edit" />
        </motion.div>
      </motion.div>

      <motion.div
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, margin: "-100px" }}
        variants={fadeUp}
        className="mt-10 rounded-3xl border border-black/5 bg-white p-8"
      >
        <h2 className="mb-1 text-lg font-medium text-ink-950">
          Update latency vs. corpus size
        </h2>
        <p className="mb-6 text-sm text-body-500">
          Incremental update cost scales with the size of the edit, not the size of the corpus —
          the gap widens as the workspace grows.
        </p>
        <CurveChart />
      </motion.div>

      <motion.div
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, margin: "-100px" }}
        variants={stagger(0.1)}
        className="mt-16 grid gap-6 md:grid-cols-2"
      >
        <motion.div variants={fadeUp} className="rounded-2xl border border-black/5 bg-white p-6">
          <h3 className="text-sm font-medium text-ink-950">Retrieval quality</h3>
          <p className="mt-2 text-sm text-body-500">
            Human-judged answer correctness and citation faithfulness on a held-out question set,
            PCST-grounded answers vs. a naive top-k vector similarity baseline — following the
            GraphQA benchmark methodology used to evaluate G-Retriever.
          </p>
        </motion.div>
        <motion.div variants={fadeUp} className="rounded-2xl border border-black/5 bg-white p-6">
          <h3 className="text-sm font-medium text-ink-950">Update efficiency</h3>
          <p className="mt-2 text-sm text-body-500">
            Wall-clock update latency and nodes/edges re-embedded per edit, KONNECT's incremental
            pipeline vs. a full-rebuild baseline, across workspaces of increasing size.
          </p>
        </motion.div>
      </motion.div>
    </div>
  );
}
