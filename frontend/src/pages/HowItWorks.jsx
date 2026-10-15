import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowLeft } from "lucide-react";
import { fadeUp, stagger } from "../lib/motion";
import Tag from "../components/shared/Tag";
import ScrollSpySection from "../components/shared/ScrollSpySection";
import { howItWorksSteps } from "../data/howItWorks";

export default function HowItWorks() {
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
          <span className="text-body-500 font-mono">KONNECT &rsaquo; How It Works</span>
        </div>

        <motion.div initial="hidden" animate="show" variants={stagger(0.1)}>
          <motion.div variants={fadeUp}>
            <Tag color="sky" className="mb-4">
              How it works
            </Tag>
          </motion.div>
          <motion.h1 variants={fadeUp} className="text-4xl font-semibold tracking-tight text-ink-950 md:text-5xl">
            From a source edit to a cited answer.
          </motion.h1>
          <motion.p variants={fadeUp} className="mx-auto mt-4 max-w-2xl text-body-500">
            The full pipeline fusing GraphRAG's indexing, G-Retriever's PCST retrieval and ROLAND's
            incremental GRU update — walk through each stage.
          </motion.p>
        </motion.div>
      </section>

      <ScrollSpySection eyebrow="Pipeline" title="Seven stages, one bounded update." steps={howItWorksSteps} />

      <section className="mx-auto max-w-4xl px-6 py-20 text-center text-body-500 text-xs md:text-sm">
        <p>
          Every stage above touches only the entities extracted from the edited document, plus a
          bounded k-hop neighbourhood — never the full corpus.
        </p>
      </section>
    </div>
  );
}
