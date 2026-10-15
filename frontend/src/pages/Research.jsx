import { useState } from "react";
import { Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, ArrowLeft } from "lucide-react";
import { fadeUp, stagger } from "../lib/motion";
import Tag from "../components/shared/Tag";
import { researchCards } from "../data/research";

function AccordionCard({ card, isOpen, onToggle }) {
  return (
    <motion.div variants={fadeUp} className="overflow-hidden rounded-2xl border border-black/5 bg-white">
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between gap-4 px-6 py-5 text-left"
      >
        <div>
          <Tag color="amber">{card.tag}</Tag>
          <p className="mt-2 text-xs text-body-500">{card.source}</p>
        </div>
        <ChevronDown
          size={18}
          className={`shrink-0 text-body-500 transition-transform ${isOpen ? "rotate-180" : ""}`}
        />
      </button>
      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
            className="px-6 pb-6"
          >
            <p className="text-sm text-body-500">{card.problem}</p>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-emerald-600">Reused as-is</p>
                <p className="mt-1 text-sm text-ink-950">{card.reused}</p>
              </div>
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-amber-500">Reused, adapted</p>
                <p className="mt-1 text-sm text-ink-950">{card.adapted}</p>
              </div>
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-body-500">Not reused</p>
                <p className="mt-1 text-sm text-ink-950">{card.notReused}</p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default function Research() {
  const [open, setOpen] = useState(0);

  return (
    <div className="mx-auto max-w-4xl px-6 pb-28 pt-28 md:pt-36">
      <div className="mb-6 flex items-center justify-between text-xs">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 font-medium text-body-500 hover:text-ink-950 transition"
        >
          <ArrowLeft size={14} /> Back to Home
        </Link>
        <span className="text-body-500 font-mono">KONNECT &rsaquo; Research</span>
      </div>
      <motion.div initial="hidden" animate="show" variants={stagger(0.1)} className="text-center">
        <motion.div variants={fadeUp}>
          <Tag color="sky" className="mb-4">Research</Tag>
        </motion.div>
        <motion.h1 variants={fadeUp} className="text-4xl font-semibold tracking-tight text-ink-950 md:text-5xl">
          Three papers. One coherent update rule.
        </motion.h1>
        <motion.p variants={fadeUp} className="mx-auto mt-4 max-w-2xl text-body-500">
          None of GraphRAG, G-Retriever or ROLAND were designed to operate together, or for a
          webhook-driven, continuously mutating corpus. KONNECT fuses them.
        </motion.p>
      </motion.div>

      <motion.div
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, margin: "-80px" }}
        variants={stagger(0.12)}
        className="mt-16 flex flex-col gap-4"
      >
        {researchCards.map((card, i) => (
          <AccordionCard
            key={card.tag}
            card={card}
            isOpen={open === i}
            onToggle={() => setOpen(open === i ? -1 : i)}
          />
        ))}
      </motion.div>
    </div>
  );
}
