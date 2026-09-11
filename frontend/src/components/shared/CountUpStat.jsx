import { useEffect, useRef, useState } from "react";
import { motion, useInView } from "framer-motion";

// Count-up number, used on /results.
export default function CountUpStat({ target = 0, suffix = "", label, duration = 1.4 }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });
  const [value, setValue] = useState(0);

  useEffect(() => {
    if (!inView) return;
    let raf;
    const start = performance.now();
    const tick = (now) => {
      const t = Math.min(1, (now - start) / (duration * 1000));
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(target * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inView, target, duration]);

  const display =
    target % 1 === 0 ? Math.round(value).toLocaleString() : value.toFixed(1);

  return (
    <motion.div
      ref={ref}
      variants={{ hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0 } }}
      initial="hidden"
      animate={inView ? "show" : "hidden"}
      transition={{ duration: 0.45, ease: "easeOut" }}
      className="flex flex-col gap-1"
    >
      <span className="text-4xl md:text-5xl font-semibold tracking-tight text-ink-950">
        {display}
        {suffix}
      </span>
      {label ? <span className="text-sm text-body-500">{label}</span> : null}
    </motion.div>
  );
}
