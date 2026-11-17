// Lenis smooth scrolling (off for reduced-motion & low-end devices).
// Exposes stop()/start() so modals can freeze the page behind them.
import { createContext, useContext, useEffect, useMemo, useRef } from 'react';
import Lenis from 'lenis';
import { useSite } from '../context/SiteContext';
import { isLowEndDevice, prefersReducedMotion } from '../utils/device';

const fallback = {
  stop() {},
  start() {},
  scrollTo(target) {
    const el = typeof target === 'string' ? document.querySelector(target) : target;
    el?.scrollIntoView({ block: 'start' });
  },
};
const LenisContext = createContext(fallback);

export function SmoothScrollProvider({ children }) {
  const lenisRef = useRef(null);
  const { design } = useSite();
  const enabled = design.smooth_scroll !== false;

  useEffect(() => {
    if (!enabled || prefersReducedMotion() || isLowEndDevice()) return undefined;
    const lenis = new Lenis({ lerp: 0.11, smoothWheel: true, syncTouch: false });
    lenisRef.current = lenis;
    let frame;
    const raf = (time) => {
      lenis.raf(time);
      frame = requestAnimationFrame(raf);
    };
    frame = requestAnimationFrame(raf);
    return () => {
      cancelAnimationFrame(frame);
      lenis.destroy();
      lenisRef.current = null;
    };
  }, [enabled]);

  const api = useMemo(
    () => ({
      stop: () => lenisRef.current?.stop(),
      start: () => lenisRef.current?.start(),
      scrollTo: (target, opts = {}) => {
        if (lenisRef.current) {
          lenisRef.current.scrollTo(target, { offset: -90, ...opts });
          return;
        }
        const el = typeof target === 'string' ? document.querySelector(target) : target;
        el?.scrollIntoView({ behavior: prefersReducedMotion() ? 'auto' : 'smooth', block: 'start' });
      },
    }),
    [],
  );

  return <LenisContext.Provider value={api}>{children}</LenisContext.Provider>;
}

export const useSmoothScroll = () => useContext(LenisContext);
