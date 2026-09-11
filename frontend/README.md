# KONNECT — Frontend

Built strictly to `konnect-frontend-plan.md`: React 18 + Vite, Tailwind CSS,
Framer Motion + GSAP ScrollTrigger, React Router v6, d3-force for the live
graph, lucide-react icons.

## Run it

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # production build to /dist
```

## What's implemented (per the plan's Build Order)

1. Design tokens (`tailwind.config.js`) + shared motion tokens (`src/lib/motion.js`)
2. `Layout` / `Navbar` (mega-menu) / `Footer`
3. Home hero — full-bleed library image, gradient overlay, frosted-glass nav,
   two-tone headline, AI input box + dual CTAs, tab-switching `AppWindowMock`
4. Shared components: `AppWindowMock`, `Tag`, `Marquee`, `CountUpStat`,
   `ScrollSpySection` (GSAP pin+scrub), `CurveChart` (GSAP stroke-draw),
   `GraphCanvas` (real d3-force simulation, live-looping demo mode)
5. Home's remaining sections: tech marquee, how-it-works teaser, architecture
   teaser, evaluation teaser, team, final CTA
6. All 8 routes: `/`, `/how-it-works`, `/architecture`, `/live-demo`,
   `/research`, `/results`, `/team`, `/docs`

## Notes / next steps

- `/live-demo`'s event log + graph updates are a scripted loop standing in
  for a real WebSocket/SSE feed from the Node/Express orchestration layer —
  swap the `useEffect` interval in `src/pages/LiveDemo.jsx` for a real socket
  connection later; `<GraphCanvas live />` itself doesn't change.
- `/results` stat numbers and the `CurveChart` data are placeholders — swap
  in real benchmark numbers once you have them (`src/pages/Results.jsx`).
- `lucide-react`'s "Github" icon isn't exported in the installed version, so
  `GitFork` is used in its place in `Footer.jsx` / `Docs.jsx`.
