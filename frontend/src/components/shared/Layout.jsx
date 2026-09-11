import { Outlet, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import Navbar from "./Navbar";
import Footer from "./Footer";
import ScrollToTop from "./ScrollToTop";
import { pageTransition } from "../../lib/motion";

// One Layout component — Navbar + Footer + Outlet + page-transition
// wrapper. Every route renders inside it, so nav/footer/motion-on-route-
// change never has to be reimplemented per page.
export default function Layout() {
  const location = useLocation();

  return (
    <div className="flex min-h-screen flex-col">
      <ScrollToTop />
      <Navbar />
      <AnimatePresence mode="wait">
        <motion.main
          key={location.pathname}
          initial="initial"
          animate="animate"
          exit="exit"
          variants={pageTransition}
          className="flex-1"
        >
          <Outlet />
        </motion.main>
      </AnimatePresence>
      <Footer />
    </div>
  );
}
