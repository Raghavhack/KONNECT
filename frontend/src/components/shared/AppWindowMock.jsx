// Sleek "app window" chrome frame — reused to frame every
// product preview: graph viz preview, chat preview, architecture diagram.
export default function AppWindowMock({ children, title = "konnect-orchestration — live", className = "" }) {
  return (
    <div
      className={`overflow-hidden rounded-2xl border border-black/10 bg-[#141519] shadow-[0_20px_60px_-15px_rgba(14,14,16,0.25)] ring-1 ring-white/5 ${className}`}
    >
      <div className="flex items-center justify-between border-b border-white/10 bg-[#1B1C22] px-4 py-2.5">
        <div className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-[#FF5F57]/90" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#FEBC2E]/90" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#28C840]/90" />
        </div>
        <span className="truncate text-[11px] font-mono font-medium text-body-300/70">
          {title}
        </span>
        <div className="w-8" />
      </div>
      <div className="bg-[#121316] text-parchment-50">{children}</div>
    </div>
  );
}
