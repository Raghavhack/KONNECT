import { useState, useEffect } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Menu, X, LogIn, LogOut, User, Zap, BookOpen } from "lucide-react";
import { useAuth } from "../../context/AuthContext";

const NAV_LINKS = [
  { to: "/docs", label: "Docs", icon: BookOpen },
];

export default function Navbar() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { user, isAuthenticated, logout } = useAuth();
  const location = useLocation();

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  return (
    <div className="fixed inset-x-0 top-4 z-50 flex justify-center px-4">
      <nav className="relative flex w-full max-w-5xl items-center justify-between rounded-full bg-white/80 px-4 py-2.5 shadow-[0_8px_30px_-10px_rgba(14,14,16,0.25)] backdrop-blur-md ring-1 ring-black/5">
        {/* Brand */}
        <Link
          to="/"
          className="group flex items-center gap-2 pl-1 text-sm font-semibold tracking-tight text-ink-950 transition-opacity hover:opacity-80"
          aria-label="KONNECT Home"
        >
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-amber-400 text-[11px] font-bold text-ink-950 shadow-sm transition-transform group-hover:scale-105">
            K
          </span>
          KONNECT
        </Link>

        {/* Desktop links */}
        <div className="hidden items-center gap-1 md:flex">
          {NAV_LINKS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-1 rounded-full px-3 py-1.5 text-xs transition-colors ${
                  isActive
                    ? "bg-black/5 font-semibold text-ink-950"
                    : "text-ink-950/70 hover:bg-black/5"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}

          <Link
            to="/live-demo"
            className="flex items-center gap-1.5 rounded-full bg-ink-950 px-3.5 py-1.5 text-xs font-medium text-parchment-50 transition hover:bg-ink-800"
          >
            <Zap size={11} className="text-amber-400" />
            Live demo
          </Link>
        </div>

        {/* Auth */}
        <div className="flex items-center gap-2">
          {isAuthenticated ? (
            <div className="hidden items-center gap-2 sm:flex">
              <span className="flex items-center gap-1.5 rounded-full bg-amber-400/20 px-3 py-1 text-xs font-semibold text-amber-700 ring-1 ring-amber-400/30">
                <User size={12} />
                {user?.name?.split(" ")[0] || "Demo"}
              </span>
              <button
                onClick={logout}
                title="Sign out"
                className="flex h-8 w-8 items-center justify-center rounded-full text-body-500 transition hover:bg-black/5 hover:text-ink-950"
              >
                <LogOut size={14} />
              </button>
            </div>
          ) : (
            <div className="hidden items-center gap-1 sm:flex">
              <Link
                to="/login"
                className="flex items-center gap-1 rounded-full px-3 py-1.5 text-xs font-medium text-ink-950 transition hover:bg-black/5"
              >
                <LogIn size={13} /> Sign in
              </Link>
              <Link
                to="/signup"
                className="flex items-center gap-1 rounded-full bg-ink-950 px-3.5 py-1.5 text-xs font-medium text-parchment-50 transition hover:bg-ink-800"
              >
                Get started
              </Link>
            </div>
          )}

          {/* Mobile menu toggle */}
          <button
            onClick={() => setMobileMenuOpen((v) => !v)}
            className="flex h-8 w-8 items-center justify-center rounded-full text-ink-950 hover:bg-black/5 md:hidden"
            aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
            aria-expanded={mobileMenuOpen}
          >
            {mobileMenuOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>
      </nav>

      {/* Mobile drawer */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, y: -10, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.96 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="absolute inset-x-4 top-16 z-50 rounded-3xl border border-black/10 bg-white/95 p-5 shadow-2xl backdrop-blur-xl md:hidden"
          >
            <div className="flex flex-col gap-1">
              <Link
                to="/live-demo"
                className="flex items-center gap-2 rounded-xl bg-ink-950 px-4 py-3 text-sm font-medium text-parchment-50"
              >
                <Zap size={14} className="text-amber-400" /> Live demo
              </Link>
              <Link
                to="/docs"
                className="flex items-center gap-2 rounded-xl px-4 py-3 text-sm font-medium text-ink-950 hover:bg-parchment-50"
              >
                <BookOpen size={14} /> Docs
              </Link>
            </div>

            <div className="mt-4 border-t border-black/5 pt-4">
              {isAuthenticated ? (
                <div className="flex items-center justify-between rounded-2xl bg-amber-400/15 p-3">
                  <span className="flex items-center gap-2 text-xs font-semibold text-ink-950">
                    <User size={14} className="text-amber-600" />
                    {user?.name}
                  </span>
                  <button
                    onClick={logout}
                    className="flex items-center gap-1 rounded-full bg-ink-950 px-3 py-1 text-xs font-medium text-parchment-50"
                  >
                    <LogOut size={12} /> Sign out
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-2">
                  <Link
                    to="/login"
                    className="flex items-center justify-center gap-1.5 rounded-full border border-black/10 py-2.5 text-xs font-medium text-ink-950 hover:bg-black/5"
                  >
                    <LogIn size={14} /> Sign in
                  </Link>
                  <Link
                    to="/signup"
                    className="flex items-center justify-center gap-1.5 rounded-full bg-ink-950 py-2.5 text-xs font-medium text-parchment-50 hover:bg-ink-800"
                  >
                    Get started
                  </Link>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
