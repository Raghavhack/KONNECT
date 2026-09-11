import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Home, Search } from "lucide-react";
import Tag from "../components/shared/Tag";
import { fadeUp, stagger } from "../lib/motion";

export default function NotFound() {
  return (
    <div className="flex min-h-[80vh] items-center justify-center px-6 py-28 text-center">
      <motion.div
        variants={stagger(0.1)}
        initial="hidden"
        animate="show"
        className="max-w-md"
      >
        <motion.div variants={fadeUp}>
          <Tag color="amber" className="mb-4">
            Error 404
          </Tag>
        </motion.div>

        <motion.h1
          variants={fadeUp}
          className="text-5xl font-bold tracking-tight text-ink-950 md:text-6xl"
        >
          Node not found
        </motion.h1>

        <motion.p variants={fadeUp} className="mt-4 text-body-500">
          The requested path doesn't exist in the knowledge graph. It may have been pruned or moved during an incremental update.
        </motion.p>

        <motion.div variants={fadeUp} className="mt-8 flex items-center justify-center gap-3">
          <Link
            to="/"
            className="flex items-center gap-2 rounded-full bg-ink-950 px-5 py-2.5 text-sm font-medium text-parchment-50 transition-colors hover:bg-ink-800"
          >
            <Home size={16} />
            Back to Home
          </Link>
          <Link
            to="/live-demo"
            className="flex items-center gap-2 rounded-full border border-black/10 bg-white px-5 py-2.5 text-sm font-medium text-ink-950 transition-colors hover:bg-parchment-50"
          >
            <Search size={16} />
            Try Live Demo
          </Link>
        </motion.div>
      </motion.div>
    </div>
  );
}
