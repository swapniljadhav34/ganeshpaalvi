// Site-wide touches from the Site Design Studio: button shape & hover, custom cursor,
// scroll progress bar. Mouse-only effects never appear on phones.
import { motion, useMotionValue, useScroll, useSpring } from 'framer-motion';
import { useEffect, useState } from 'react';
import { useSite } from '../context/SiteContext';
import { hasFinePointer } from '../utils/device';
import './fx.css';
import { useCalm } from '../hooks/useCalm';

function Cursor({ kind }) {
  const x = useMotionValue(-100);
  const y = useMotionValue(-100);
  const sx = useSpring(x, { stiffness: 500, damping: 40 });
  const sy = useSpring(y, { stiffness: 500, damping: 40 });
  const lx = useSpring(x, { stiffness: 140, damping: 22 });
  const ly = useSpring(y, { stiffness: 140, damping: 22 });
  const [hot, setHot] = useState(false);
  const [trail, setTrail] = useState([]);

  useEffect(() => {
    let last = 0;
    const move = (e) => {
      x.set(e.clientX); y.set(e.clientY);
      setHot(Boolean(e.target.closest?.('a, button, [role="button"], input, select, textarea, label')));
      if (kind === 'trail' && e.timeStamp - last > 45) {
        last = e.timeStamp;
        const id = e.timeStamp;
        setTrail((t) => [...t.slice(-10), { id, x: e.clientX, y: e.clientY }]);
        setTimeout(() => setTrail((t) => t.filter((p) => p.id !== id)), 700);
      }
    };
    window.addEventListener('pointermove', move, { passive: true });
    document.documentElement.classList.add(`pv-cursor-${kind}`);
    return () => {
      window.removeEventListener('pointermove', move);
      document.documentElement.classList.remove(`pv-cursor-${kind}`);
    };
  }, [kind, x, y]);

  return (
    <div className={`pv-cursor pv-cursor--${kind} ${hot ? 'is-hot' : ''}`} aria-hidden="true">
      {(kind === 'ring' || kind === 'dot' || kind === 'glow' || kind === 'blend') && (
        <motion.span className="pv-cursor-lag" style={{ x: lx, y: ly }} />
      )}
      {kind === 'ring' && <motion.span className="pv-cursor-dot" style={{ x: sx, y: sy }} />}
      {trail.map((p) => <span key={p.id} className="pv-cursor-trail" style={{ left: p.x, top: p.y }} />)}
    </div>
  );
}

function ScrollProgress() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 120, damping: 24 });
  return <motion.div className="pv-progress" style={{ scaleX }} aria-hidden="true" />;
}

export default function SiteEffects() {
  const { design } = useSite();
  const reduce = useCalm();
  const fine = typeof window !== 'undefined' && hasFinePointer();

  useEffect(() => {
    const root = document.documentElement;
    root.style.setProperty('--btn-radius', design.button_shape || '999px');
    root.dataset.btnHover = design.button_hover || 'lift';
    root.dataset.navHover = design.nav_hover || 'pill';
    root.dataset.dock = design.dock_position || 'right';
  }, [design.button_shape, design.button_hover, design.nav_hover, design.dock_position]);

  return (
    <>
      {design.scroll_progress && <ScrollProgress />}
      {fine && !reduce && design.cursor_style && design.cursor_style !== 'default' && <Cursor kind={design.cursor_style} />}
    </>
  );
}
