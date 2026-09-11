import { Link } from "react-router-dom";
import { GitFork, ExternalLink, Heart } from "lucide-react";

const COLUMNS = [
  {
    title: "Product",
    links: [
      { label: "How it works", to: "/how-it-works" },
      { label: "Architecture", to: "/architecture" },
      { label: "Live demo", to: "/live-demo" },
    ],
  },
  {
    title: "Research",
    links: [
      { label: "Literature survey", to: "/research" },
      { label: "Evaluation & results", to: "/results" },
    ],
  },
  {
    title: "Project",
    links: [
      { label: "Team & mentor", to: "/team" },
      { label: "Docs & repo", to: "/docs" },
    ],
  },
  {
    title: "Built with",
    links: [
      { label: "GraphRAG (Microsoft)", to: "/research" },
      { label: "G-Retriever", to: "/research" },
      { label: "ROLAND (KDD 2022)", to: "/research" },
    ],
  },
];

export default function Footer() {
  return (
    <footer className="relative mt-auto">
      {/* Seamless gradient fade from page parchment into footer */}
      <div className="h-24 w-full bg-gradient-to-b from-transparent via-[#15161A]/40 to-[#121316] pointer-events-none" />

      <div className="relative bg-[#121316] text-body-300 border-t border-white/5">
        {/* Subtle warm ambient glow */}
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_60%_50%_at_50%_0%,rgba(242,179,61,0.08),transparent_70%)]" />

        <div className="relative mx-auto max-w-6xl px-6 pb-16 pt-10">
          <div className="grid grid-cols-2 gap-10 md:grid-cols-5">
            <div className="col-span-2 md:col-span-1">
              <Link to="/" className="flex items-center gap-2 text-lg font-semibold text-amber-400">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-amber-400 text-[11px] font-bold text-ink-950">
                  K
                </span>
                KONNECT
              </Link>
              <p className="mt-3 text-xs leading-relaxed text-body-300/80">
                A live-synced knowledge graph second brain over Google Drive, Notion and Slack.
              </p>
              <p className="mt-4 text-[11px] text-body-300/60 leading-relaxed">
                Minor Project · Mathematics &amp; Computing
                <br />
                Punjab Engineering College, Chandigarh
              </p>
            </div>

            {COLUMNS.map((col) => (
              <div key={col.title}>
                <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-parchment-50">
                  {col.title}
                </h4>
                <ul className="flex flex-col gap-2">
                  {col.links.map((l) => (
                    <li key={l.label}>
                      <Link
                        to={l.to}
                        className="text-xs text-body-300/70 transition hover:text-amber-400"
                      >
                        {l.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <div className="mt-12 flex flex-col items-start justify-between gap-4 border-t border-white/10 pt-6 text-xs text-body-300/60 md:flex-row md:items-center">
            <span className="flex items-center gap-1">
              &copy; {new Date().getFullYear()} KONNECT. Crafted with{" "}
              <Heart size={12} className="text-amber-400 fill-amber-400" /> by Raghav, Pranay, Aarav &amp; Manas.
            </span>
            <div className="flex items-center gap-4">
              <a
                href="https://github.com"
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1.5 hover:text-parchment-50 transition"
              >
                <GitFork size={14} /> Repository
              </a>
              <Link
                to="/docs"
                className="flex items-center gap-1.5 hover:text-parchment-50 transition"
              >
                Project Docs <ExternalLink size={12} />
              </Link>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}
