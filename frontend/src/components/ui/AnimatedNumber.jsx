// Smoothly counts between numbers (used for prices and MOQ totals).
import { animate } from 'framer-motion';
import { useEffect, useRef } from 'react';
import { useCalm } from '../../hooks/useCalm';

export default function AnimatedNumber({ value, format = (v) => v }) {
  const ref = useRef(null);
  const prev = useRef(value);
  const reduce = useCalm();

  useEffect(() => {
    const node = ref.current;
    if (!node) return undefined;
    if (reduce || value == null || prev.current == null) {
      node.textContent = format(value);
      prev.current = value;
      return undefined;
    }
    const controls = animate(prev.current, value, {
      duration: 0.45,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (v) => {
        node.textContent = format(v);
      },
    });
    prev.current = value;
    return () => controls.stop();
  }, [value, format, reduce]);

  return <span ref={ref}>{format(value)}</span>;
}
