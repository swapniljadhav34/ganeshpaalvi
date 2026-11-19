// True when motion should stop: the visitor's OS asks for reduced motion, OR they pressed
// "Pause animations" in the footer (WCAG 2.2.2 — moving content must be pausable).
import { useReducedMotion } from 'framer-motion';
import { useContext } from 'react';
import { MotionPauseContext } from '../context/SiteContext';

export function useCalm() {
  const reduce = useReducedMotion();
  const paused = useContext(MotionPauseContext);
  return Boolean(reduce || paused);
}
