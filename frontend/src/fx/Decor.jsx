// Decorative animated background shapes (blob, orb, rings, dots, waves, arch, bubbles,
// grid, sparkles, leaves). They drift with the mouse when the block has a pointer effect.
import { motion } from 'framer-motion';
import { useMemo } from 'react';
import { isLowEndDevice } from '../utils/device';
import { useDepth } from './PointerArea';
import './fx.css';
import { useCalm } from '../hooks/useCalm';

function seeded(n, f) {
  return Array.from({ length: n }, (_, i) => f(i, ((i * 9301 + 49297) % 233280) / 233280));
}

function Shapes({ kind }) {
  const bits = useMemo(() => seeded(14, (i, r) => ({ i, r, left: (i * 37 + r * 20) % 100, top: (i * 53) % 95, size: 6 + ((i * 7) % 18) })), []);
  switch (kind) {
    case 'blob':
      return <div className="pv-decor-blob" />;
    case 'orb':
      return <><div className="pv-decor-orb" /><div className="pv-decor-orb pv-decor-orb--2" /></>;
    case 'rings':
      return (
        <svg className="pv-decor-rings" viewBox="0 0 400 400" aria-hidden="true">
          {[60, 100, 140, 180].map((r, i) => (
            <circle key={r} cx="200" cy="200" r={r} fill="none" strokeWidth="1" strokeDasharray={i % 2 ? '2 8' : 'none'} />
          ))}
        </svg>
      );
    case 'dots':
      return <div className="pv-decor-dots" />;
    case 'grid_lines':
      return <div className="pv-decor-grid" />;
    case 'waves':
      return (
        <svg className="pv-decor-waves" viewBox="0 0 1440 320" preserveAspectRatio="none" aria-hidden="true">
          {[0, 1, 2].map((i) => (
            <path key={i} d={`M0 ${160 + i * 40} C 240 ${100 + i * 40}, 480 ${220 + i * 40}, 720 ${160 + i * 40} S 1200 ${100 + i * 40}, 1440 ${160 + i * 40} S 2160 ${220 + i * 40}, 2880 ${160 + i * 40}`}
              fill="none" strokeWidth="1.2" style={{ animationDuration: `${18 + i * 6}s` }} />
          ))}
        </svg>
      );
    case 'arch_outline':
      return (
        <svg className="pv-decor-arch" viewBox="0 0 300 420" aria-hidden="true">
          <motion.path d="M20 420 V150 A130 130 0 0 1 280 150 V420" fill="none" strokeWidth="1.2"
            initial={{ pathLength: 0 }} whileInView={{ pathLength: 1 }} viewport={{ once: true }} transition={{ duration: 2.4, ease: 'easeInOut' }} />
          <motion.path d="M50 420 V160 A100 100 0 0 1 250 160 V420" fill="none" strokeWidth="1"
            initial={{ pathLength: 0 }} whileInView={{ pathLength: 1 }} viewport={{ once: true }} transition={{ duration: 2.4, delay: 0.3, ease: 'easeInOut' }} />
        </svg>
      );
    case 'bubbles':
      return bits.map((b) => (
        <span key={b.i} className="pv-decor-bubble" style={{ left: `${b.left}%`, width: b.size * 1.6, height: b.size * 1.6, animationDelay: `${b.i * 0.9}s`, animationDuration: `${10 + (b.i % 5) * 3}s` }} />
      ));
    case 'sparkles':
      return bits.map((b) => (
        <svg key={b.i} className="pv-decor-sparkle" viewBox="0 0 24 24" style={{ left: `${b.left}%`, top: `${b.top}%`, width: b.size + 6, animationDelay: `${(b.i % 7) * 0.5}s` }} aria-hidden="true">
          <path d="M12 0 C13 8 16 11 24 12 C16 13 13 16 12 24 C11 16 8 13 0 12 C8 11 11 8 12 0Z" />
        </svg>
      ));
    case 'leaves':
      return bits.slice(0, 9).map((b) => (
        <svg key={b.i} className="pv-decor-leaf" viewBox="0 0 24 24" style={{ left: `${b.left}%`, width: b.size + 12, animationDelay: `${b.i * 1.4}s`, animationDuration: `${14 + (b.i % 4) * 4}s` }} aria-hidden="true">
          <path d="M4 20 C4 9 11 3 21 3 C21 13 15 20 4 20Z M4 20 L14 10" />
        </svg>
      ));
    default:
      return null;
  }
}

export default function Decor({ kind = 'none', className = '', depth = 24 }) {
  const reduce = useCalm();
  const { x, y } = useDepth(depth);
  if (!kind || kind === 'none' || (typeof window !== 'undefined' && isLowEndDevice() && ['bubbles', 'sparkles', 'leaves'].includes(kind))) return null;
  return (
    <motion.div className={`pv-decor pv-decor--${kind} ${reduce ? 'pv-still' : ''} ${className}`} style={reduce ? undefined : { x, y }} aria-hidden="true">
      <Shapes kind={kind} />
    </motion.div>
  );
}
