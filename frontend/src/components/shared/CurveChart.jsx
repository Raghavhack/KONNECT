import { useEffect, useRef } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);

// SVG line chart with a gray-guide + colored-draw-on-scroll animation.
// Maps onto Section 7 evaluation plan: update latency vs corpus size,
// incremental vs full-rebuild.
export default function CurveChart({
  incremental = [4, 6, 7, 8, 9, 10, 11],
  fullRebuild = [4, 18, 40, 72, 115, 168, 230],
  labels = ["1k", "2k", "4k", "6k", "8k", "10k", "12k"],
  drawOn = "scroll",
}) {
  const pathRef = useRef(null);
  const guideRef = useRef(null);
  const wrapRef = useRef(null);

  const W = 640;
  const H = 260;
  const pad = 24;
  const max = Math.max(...fullRebuild, ...incremental);

  const toPath = (arr) =>
    arr
      .map((v, i) => {
        const x = pad + (i * (W - pad * 2)) / (arr.length - 1);
        const y = H - pad - (v / max) * (H - pad * 2);
        return `${i === 0 ? "M" : "L"} ${x} ${y}`;
      })
      .join(" ");

  useEffect(() => {
    const path = pathRef.current;
    const guide = guideRef.current;
    if (!path || !guide) return;

    [path, guide].forEach((p) => {
      if (typeof p.getTotalLength === "function") {
        const len = p.getTotalLength();
        p.style.strokeDasharray = `${len}`;
        p.style.strokeDashoffset = `${len}`;
      }
    });

    const anim = gsap.timeline({
      scrollTrigger:
        drawOn === "scroll"
          ? { trigger: wrapRef.current, start: "top 75%", once: true }
          : undefined,
    });
    anim
      .to(guide, { strokeDashoffset: 0, duration: 1.1, ease: "power2.out" })
      .to(path, { strokeDashoffset: 0, duration: 1.1, ease: "power2.out" }, "-=0.7");

    return () => anim.scrollTrigger?.kill();
  }, [drawOn]);

  return (
    <div ref={wrapRef} className="w-full">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full overflow-visible">
        <path
          ref={guideRef}
          d={toPath(fullRebuild)}
          fill="none"
          stroke="#A8A8AE"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          ref={pathRef}
          d={toPath(incremental)}
          fill="none"
          stroke="#F2B33D"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {incremental.map((v, i) => {
          const x = pad + (i * (W - pad * 2)) / (incremental.length - 1);
          const y = H - pad - (v / max) * (H - pad * 2);
          return (
            <g key={i} className="group cursor-pointer">
              <circle
                cx={x}
                cy={y}
                r={4}
                fill="#F2B33D"
                className="transition-transform group-hover:scale-150"
              />
              <title>{`${labels[i]}: ${v} ms`}</title>
            </g>
          );
        })}
      </svg>
      <div className="mt-2 flex justify-between text-xs text-body-500">
        {labels.map((l) => (
          <span key={l}>{l}</span>
        ))}
      </div>
      <div className="mt-4 flex gap-6 text-sm">
        <span className="flex items-center gap-2">
          <span className="h-0.5 w-4 bg-amber-400" /> Incremental (KONNECT)
        </span>
        <span className="flex items-center gap-2 text-body-500">
          <span className="h-0.5 w-4 bg-body-300" /> Full rebuild baseline
        </span>
      </div>
    </div>
  );
}
