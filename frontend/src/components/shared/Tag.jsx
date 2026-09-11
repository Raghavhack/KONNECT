const COLOR_MAP = {
  amber: "bg-amber-400/15 text-amber-500 ring-amber-400/30",
  sky: "bg-sky-500/10 text-sky-500 ring-sky-500/30",
  green: "bg-emerald-500/10 text-emerald-600 ring-emerald-500/30",
};

export default function Tag({ children, color = "amber", className = "" }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset ${COLOR_MAP[color] || COLOR_MAP.amber} ${className}`}
    >
      {children}
    </span>
  );
}
