import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowLeft } from "lucide-react";
import { fadeUp, stagger } from "../lib/motion";
import Tag from "../components/shared/Tag";

const TEAM = [
  { name: "Raghav Rastogi", role: "B.Tech, Mathematics & Computing" },
  { name: "Pranay Mehta", role: "B.Tech, Mathematics & Computing" },
  { name: "Aarav Sharma", role: "B.Tech, Mathematics & Computing" },
  { name: "Manas Ranjan Jena", role: "B.Tech, Mathematics & Computing" },
];

export default function Team() {
  return (
    <div className="mx-auto max-w-4xl px-6 pb-28 pt-28 md:pt-36">
      <div className="mb-6 flex items-center justify-between text-xs">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 font-medium text-body-500 hover:text-ink-950 transition"
        >
          <ArrowLeft size={14} /> Back to Home
        </Link>
        <span className="text-body-500 font-mono">KONNECT &rsaquo; Team</span>
      </div>
      <motion.div initial="hidden" animate="show" variants={stagger(0.1)} className="text-center">
        <motion.div variants={fadeUp}>
          <Tag color="sky" className="mb-4">Team</Tag>
        </motion.div>
        <motion.h1 variants={fadeUp} className="text-4xl font-semibold tracking-tight text-ink-950 md:text-5xl">
          Punjab Engineering College
        </motion.h1>
        <motion.p variants={fadeUp} className="mx-auto mt-4 max-w-xl text-body-500">
          KONNECT is a minor project submitted in partial fulfilment of the requirements for
          B.Tech in Mathematics and Computing, under the mentorship of Sucheta Ma'am, Department of
          Mathematics and Computing.
        </motion.p>
      </motion.div>

      <motion.div
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, margin: "-80px" }}
        variants={stagger(0.1)}
        className="mt-16 grid gap-4 md:grid-cols-2"
      >
        {TEAM.map((m) => (
          <motion.div
            key={m.name}
            variants={fadeUp}
            className="flex items-center gap-4 rounded-2xl border border-black/5 bg-white p-5"
          >
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-amber-400/20 text-sm font-medium text-amber-500">
              {m.name.split(" ").map((p) => p[0]).slice(0, 2).join("")}
            </span>
            <div>
              <p className="text-sm font-medium text-ink-950">{m.name}</p>
              <p className="text-xs text-body-500">{m.role}</p>
            </div>
          </motion.div>
        ))}
      </motion.div>

      <motion.div
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, margin: "-80px" }}
        variants={fadeUp}
        className="mt-8 rounded-2xl border border-dashed border-black/10 p-5 text-center text-sm text-body-500"
      >
        Mentor — Sucheta Ma'am, Department of Mathematics &amp; Computing, PEC Chandigarh
      </motion.div>
    </div>
  );
}
