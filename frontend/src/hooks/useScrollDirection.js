// Tells you whether the visitor is scrolling up or down, and roughly how far.
// To keep scrolling smooth on phones, it only re-renders when the direction flips or the page
// crosses one of the `marks` (e.g. 80px, 160px, 300px) — never on every scroll frame.
import { useEffect, useState } from 'react';

const MARKS = [80, 160, 300];

export function useScrollDirection(threshold = 8, marks = MARKS) {
  const [state, setState] = useState({ direction: 'up', y: 0 });
  useEffect(() => {
    let lastY = window.scrollY;
    let ticking = false;
    const bucket = (y) => marks.filter((m) => y > m).length;
    const onScroll = () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => {
        const y = window.scrollY;
        if (Math.abs(y - lastY) >= threshold) {
          const direction = y > lastY ? 'down' : 'up';
          setState((prev) => (prev.direction === direction && bucket(prev.y) === bucket(y) ? prev : { direction, y }));
          lastY = y;
        }
        ticking = false;
      });
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, [threshold, marks]);
  return state;
}
