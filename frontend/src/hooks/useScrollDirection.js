// Tells you whether the visitor is scrolling up or down, and how far they've scrolled.
import { useEffect, useState } from 'react';

export function useScrollDirection(threshold = 8) {
  const [state, setState] = useState({ direction: 'up', y: 0 });
  useEffect(() => {
    let lastY = window.scrollY;
    let ticking = false;
    const onScroll = () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => {
        const y = window.scrollY;
        if (Math.abs(y - lastY) >= threshold) {
          setState({ direction: y > lastY ? 'down' : 'up', y });
          lastY = y;
        }
        ticking = false;
      });
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, [threshold]);
  return state;
}
