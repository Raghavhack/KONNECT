import { useState, useEffect, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronLeft, ChevronRight, Play, Pause } from "lucide-react";
import {
  StageWebhook,
  StageDebounce,
  StageReparse,
  StageNeo4j,
  StageROLAND,
  StagePCST,
  StageCitedAnswer,
} from "./PipelineMockups";

const STAGE_COMPONENTS = {
  webhook: <StageWebhook />,
  debounce: <StageDebounce />,
  reparse: <StageReparse />,
  neo4j: <StageNeo4j />,
  roland: <StageROLAND />,
  pcst: <StagePCST />,
  "cited-answer": <StageCitedAnswer />,
};

export default function ScrollSpySection({ steps = [], eyebrow, title }) {
  const [active, setActive] = useState(0);
  const [isAutoPlay, setIsAutoPlay] = useState(true);
  const timerRef = useRef(null);

  // Auto-advance walkthrough unless user paused or interacted
  useEffect(() => {
    if (!isAutoPlay || steps.length === 0) return;
    timerRef.current = setInterval(() => {
      setActive((prev) => (prev + 1) % steps.length);
    }, 4500);
    return () => clearInterval(timerRef.current);
  }, [isAutoPlay, steps.length, active]);

  const handleStepClick = (index) => {
    setActive(index);
    setIsAutoPlay(false);
  };

  const handlePrev = () => {
    setActive((prev) => (prev > 0 ? prev - 1 : steps.length - 1));
    setIsAutoPlay(false);
  };

  const handleNext = () => {
    setActive((prev) => (prev < steps.length - 1 ? prev + 1 : 0));
    setIsAutoPlay(false);
  };

  const currentStep = steps[active];
  const renderedContent =
    currentStep?.mockContent ||
    (currentStep?.id && STAGE_COMPONENTS[currentStep.id]) || (
      <div className="text-center font-mono text-sm text-body-300">
        <p className="font-semibold text-amber-400">{currentStep?.title}</p>
        <p className="mt-2 text-xs">{currentStep?.description}</p>
      </div>
    );

  return (
    <section className="relative mx-auto max-w-6xl px-6 py-16">
      {/* Outer Studio Container - softly rounded, integrated dark canvas with smooth ambient fade */}
      <div className="relative overflow-hidden rounded-4xl border border-black/10 bg-gradient-to-b from-[#181A20] via-[#14151A] to-[#101114] p-8 text-parchment-50 shadow-2xl md:p-14">
        {/* Soft radial ambient glow */}
        <div className="pointer-events-none absolute -top-24 left-1/2 h-96 w-96 -translate-x-1/2 rounded-full bg-amber-400/10 blur-3xl" />

        {/* Section Header */}
        <div className="relative z-10 mb-10 flex flex-col items-start justify-between gap-4 md:flex-row md:items-end">
          <div>
            {eyebrow ? (
              <span className="mb-2 inline-block rounded-full bg-amber-400/15 px-3 py-1 text-xs font-semibold text-amber-400 ring-1 ring-amber-400/30">
                {eyebrow}
              </span>
            ) : null}
            {title ? (
              <h2 className="text-2xl font-bold tracking-tight text-white md:text-4xl">{title}</h2>
            ) : null}
          </div>

          {/* Stepper Controls & Autoplay Toggle */}
          <div className="flex items-center gap-2 text-xs text-body-300">
            <button
              onClick={() => setIsAutoPlay((p) => !p)}
              className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-parchment-50 transition hover:bg-white/10"
              title={isAutoPlay ? "Pause auto-advance" : "Play auto-advance"}
            >
              {isAutoPlay ? <Pause size={12} className="text-amber-400" /> : <Play size={12} />}
              <span>{isAutoPlay ? "Auto-playing" : "Paused"}</span>
            </button>
            <div className="flex items-center gap-1">
              <button
                onClick={handlePrev}
                aria-label="Previous step"
                className="flex h-8 w-8 items-center justify-center rounded-full border border-white/10 bg-white/5 hover:bg-white/15 transition"
              >
                <ChevronLeft size={16} />
              </button>
              <button
                onClick={handleNext}
                aria-label="Next step"
                className="flex h-8 w-8 items-center justify-center rounded-full border border-white/10 bg-white/5 hover:bg-white/15 transition"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        </div>

        {/* Two-column layout: Interactive Steps list on Left, Live Stage View on Right */}
        <div className="relative z-10 grid gap-8 lg:grid-cols-12 lg:items-center">
          {/* Steps List (Left) */}
          <div className="flex flex-col gap-2 lg:col-span-5">
            {steps.map((step, i) => {
              const isActive = i === active;
              return (
                <button
                  key={step.title}
                  onClick={() => handleStepClick(i)}
                  className={`group relative flex items-start gap-3.5 rounded-2xl p-3.5 text-left transition-all ${
                    isActive
                      ? "bg-white/10 shadow-lg ring-1 ring-white/15"
                      : "opacity-50 hover:bg-white/5 hover:opacity-90"
                  }`}
                >
                  {/* Step index badge */}
                  <span
                    className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-mono font-bold transition-all ${
                      isActive
                        ? "bg-amber-400 text-ink-950 shadow-[0_0_12px_rgba(242,179,61,0.6)]"
                        : "bg-white/10 text-body-300 group-hover:bg-white/20"
                    }`}
                  >
                    {i + 1}
                  </span>

                  <div className="flex-1">
                    <span className="block text-sm font-semibold tracking-tight text-white">
                      {step.title}
                    </span>
                    <span className="mt-1 block text-xs leading-relaxed text-body-300/80">
                      {step.description}
                    </span>

                    {/* Active progress indicator bar */}
                    {isActive && isAutoPlay && (
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: "100%" }}
                        transition={{ duration: 4.5, ease: "linear" }}
                        className="mt-2.5 h-0.5 rounded-full bg-amber-400/80"
                      />
                    )}
                  </div>
                </button>
              );
            })}
          </div>

          {/* Interactive Preview Viewport (Right) */}
          <div className="lg:col-span-7">
            <div className="overflow-hidden rounded-2xl border border-white/15 bg-[#121316] shadow-2xl ring-1 ring-black/40">
              {/* Preview Window Header */}
              <div className="flex items-center justify-between border-b border-white/10 bg-[#1A1B22] px-4 py-2.5">
                <div className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-[#FF5F57]/80" />
                  <span className="h-2.5 w-2.5 rounded-full bg-[#FEBC2E]/80" />
                  <span className="h-2.5 w-2.5 rounded-full bg-[#28C840]/80" />
                </div>
                <span className="font-mono text-[11px] text-body-300/70">
                  pipeline-stage-{active + 1}: {currentStep?.title}
                </span>
                <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-mono text-emerald-400">
                  Live
                </span>
              </div>

              {/* Stage Content */}
              <div className="min-h-[360px] p-6 md:p-8 flex items-center justify-center">
                <AnimatePresence mode="wait">
                  <motion.div
                    key={active}
                    initial={{ opacity: 0, y: 10, scale: 0.98 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -10, scale: 0.98 }}
                    transition={{ duration: 0.25, ease: "easeOut" }}
                    className="w-full"
                  >
                    {renderedContent}
                  </motion.div>
                </AnimatePresence>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
