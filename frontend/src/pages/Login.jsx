import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowLeft, ArrowRight, Lock, Mail, Sparkles } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import Tag from "../components/shared/Tag";
import { fadeUp, stagger } from "../lib/motion";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [searchParams] = useSearchParams();
  const redirect = searchParams.get("redirect") || "/live-demo";
  const { login, loginAsDemo } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = (e) => {
    e.preventDefault();
    login(email || "researcher@konnect.ai", password || "password");
    navigate(redirect);
  };

  const handleDemoLogin = () => {
    loginAsDemo();
    navigate(redirect);
  };

  return (
    <div className="flex min-h-[85vh] items-center justify-center px-6 py-28">
      <motion.div
        variants={stagger(0.1)}
        initial="hidden"
        animate="show"
        className="w-full max-w-md"
      >
        {/* Back link */}
        <motion.div variants={fadeUp} className="mb-6">
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-xs font-medium text-body-500 hover:text-ink-950"
          >
            <ArrowLeft size={14} /> Back to Home
          </Link>
        </motion.div>

        {/* Card */}
        <motion.div
          variants={fadeUp}
          className="rounded-3xl border border-black/10 bg-white p-8 shadow-[0_20px_60px_-15px_rgba(14,14,16,0.15)] backdrop-blur"
        >
          <div className="text-center">
            <Tag color="amber" className="mb-3">
              <Sparkles size={12} /> Authentication
            </Tag>
            <h1 className="text-2xl font-bold tracking-tight text-ink-950 md:text-3xl">
              Welcome back
            </h1>
            <p className="mt-2 text-xs text-body-500">
              Sign in to access your live knowledge graph &amp; demo workspace
            </p>
          </div>

          {/* Quick Demo Login Button */}
          <div className="mt-6">
            <button
              onClick={handleDemoLogin}
              className="flex w-full items-center justify-center gap-2 rounded-2xl border-2 border-amber-400 bg-amber-400/15 py-3 text-sm font-semibold text-ink-950 transition hover:bg-amber-400/25"
            >
              <Sparkles size={16} className="text-amber-500" />
              1-Click Demo Sign In (Instant Access)
            </button>
            <div className="my-5 flex items-center gap-3">
              <div className="h-px flex-1 bg-black/10" />
              <span className="text-[11px] uppercase tracking-wider text-body-500">or with email</span>
              <div className="h-px flex-1 bg-black/10" />
            </div>
          </div>

          {/* Email form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-ink-950 mb-1.5">Email address</label>
              <div className="relative flex items-center">
                <Mail size={15} className="absolute left-3.5 text-body-500" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@organization.com"
                  className="w-full rounded-xl border border-black/10 bg-parchment-50/50 py-2.5 pl-10 pr-4 text-xs text-ink-950 placeholder:text-body-500 focus:border-amber-400 focus:bg-white focus:outline-none focus:ring-1 focus:ring-amber-400"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-medium text-ink-950">Password</label>
                <span className="text-[11px] text-amber-500 hover:underline cursor-pointer">
                  Forgot password?
                </span>
              </div>
              <div className="relative flex items-center">
                <Lock size={15} className="absolute left-3.5 text-body-500" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full rounded-xl border border-black/10 bg-parchment-50/50 py-2.5 pl-10 pr-4 text-xs text-ink-950 placeholder:text-body-500 focus:border-amber-400 focus:bg-white focus:outline-none focus:ring-1 focus:ring-amber-400"
                />
              </div>
            </div>

            <button
              type="submit"
              className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-full bg-ink-950 py-3 text-sm font-medium text-parchment-50 transition hover:bg-ink-800"
            >
              Sign in <ArrowRight size={15} />
            </button>
          </form>

          <div className="mt-6 text-center text-xs text-body-500">
            Don't have an account?{" "}
            <Link
              to={`/signup${redirect ? `?redirect=${encodeURIComponent(redirect)}` : ""}`}
              className="font-medium text-amber-500 hover:underline"
            >
              Create an account
            </Link>
          </div>
        </motion.div>
      </motion.div>
    </div>
  );
}
