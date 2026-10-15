// CSS-only infinite horizontal scroller — used for tech-stack logos
// (Neo4j, PyTorch, Google Drive, Notion, Slack) instead of partner logos.
export default function Marquee({ items = [] }) {
  const doubled = [...items, ...items];
  return (
    <div className="relative w-full overflow-hidden no-scrollbar [mask-image:linear-gradient(to_right,transparent,black_10%,black_90%,transparent)]">
      <div className="flex w-max animate-marquee gap-12 py-2">
        {doubled.map((item, i) => (
          <div
            key={i}
            className="flex items-center gap-2 whitespace-nowrap text-sm font-medium text-body-500"
          >
            {item.icon ? <item.icon size={18} className="text-ink-800" /> : null}
            {item.label}
          </div>
        ))}
      </div>
    </div>
  );
}
