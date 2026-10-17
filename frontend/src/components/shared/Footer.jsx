import { Link } from "react-router-dom";
import { GitFork, ExternalLink } from "lucide-react";

const COLUMNS = [
  {
    title: "Product",
    links: [
      { label: "Live demo", to: "/live-demo" },
      { label: "Docs", to: "/docs" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "Sign in", to: "/login" },
      { label: "Get started", to: "/signup" },
    ],
  },
];

export default function Footer() {
  return (
    <footer className="relative mt-auto">
      {/* Gradient fade from page into footer */}
      <div className="h-24 w-full bg-gradient-to-b from-transparent via-[#15161A]/40 to-[#121316] pointer-events-none" />

      <div className="relative bg-[#121316] text-body-300 border-t border-white/5">
        {/* Ambient glow */}
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_60%_50%_at_50%_0%,rgba(242,179,61,0.07),transparent_70%)]" />

        <div className="relative mx-auto max-w-6xl px-6 pb-12 pt-10">
          <div className="grid grid-cols-2 gap-10 md:grid-cols-4">
            {/* Brand */}
            <div className="col-span-2 md:col-span-2">
              <Link to="/" className="flex items-center gap-2 text-lg font-semibold text-amber-400">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-amber-400 text-[11px] font-bold text-ink-950">
                  K
                </span>
                KONNECT
              </Link>
              <p className="mt-3 max-w-xs text-xs leading-relaxed text-body-300/80">
                A live-synced knowledge graph that connects your Drive, Notion, and Slack — reacting to every edit without rebuilding the whole corpus.
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

          <div className="mt-10 flex flex-col items-start justify-between gap-4 border-t border-white/10 pt-6 text-xs text-body-300/50 md:flex-row md:items-center">
            <span>
              &copy; {new Date().getFullYear()} KONNECT. All rights reserved.
            </span>
            <div className="flex items-center gap-4">
              <a
                href="https://github.com"
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1.5 transition hover:text-parchment-50"
              >
                <GitFork size={13} /> GitHub
              </a>
              <Link
                to="/docs"
                className="flex items-center gap-1.5 transition hover:text-parchment-50"
              >
                Docs <ExternalLink size={11} />
              </Link>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}
