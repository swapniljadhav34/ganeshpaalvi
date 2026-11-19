// Hover / mouse effects chosen in the admin: lift, 3D tilt, magnetic, zoom, glow, shine,
// rotate, spotlight, press. Touch devices get a gentle press instead of mouse-only effects.
import { motion, useMotionTemplate, useMotionValue, useSpring } from 'framer-motion';
import { useRef } from 'react';
import { hasFinePointer } from '../utils/device';
import './fx.css';
import { useCalm } from '../hooks/useCalm';

const SPRING = { stiffness: 220, damping: 20 };

export default function HoverFx({ kind = 'lift', className = '', children, strength = 1, style, ...rest }) {
  const ref = useRef(null);
  const reduce = useCalm();
  const fine = useRef(typeof window !== 'undefined' && hasFinePointer());
  const rx = useSpring(useMotionValue(0), SPRING);
  const ry = useSpring(useMotionValue(0), SPRING);
  const mx = useSpring(useMotionValue(0), SPRING);
  const my = useSpring(useMotionValue(0), SPRING);
  const lx = useMotionValue(50);
  const ly = useMotionValue(50);
  const light = useMotionTemplate`radial-gradient(circle at ${lx}% ${ly}%, color-mix(in srgb, var(--color-surface-elevated) 55%, transparent), transparent 55%)`;

  if (!kind || kind === 'none' || reduce) {
    return <div className={className} style={style} {...rest}>{children}</div>;
  }

  const interactive = fine.current && ['tilt_3d', 'magnetic', 'spotlight'].includes(kind);
  const onMove = (e) => {
    if (!interactive || !ref.current) return;
    const r = ref.current.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width;
    const py = (e.clientY - r.top) / r.height;
    if (kind === 'tilt_3d') { ry.set((px - 0.5) * 14 * strength); rx.set((0.5 - py) * 14 * strength); }
    if (kind === 'magnetic') { mx.set((px - 0.5) * r.width * 0.12 * strength); my.set((py - 0.5) * r.height * 0.12 * strength); }
    lx.set(px * 100); ly.set(py * 100);
  };
  const onLeave = () => { rx.set(0); ry.set(0); mx.set(0); my.set(0); };

  const hoverAnim = {
    lift: { y: -8 },
    glow: { y: -2 },
    rotate: { rotate: 2.5, scale: 1.02 },
    press: { scale: 0.97 },
  }[kind];

  const motionStyle = {
    ...style,
    ...(kind === 'tilt_3d' && fine.current ? { rotateX: rx, rotateY: ry, transformPerspective: 900 } : {}),
    ...(kind === 'magnetic' && fine.current ? { x: mx, y: my } : {}),
  };

  return (
    <motion.div
      ref={ref}
      className={`pv-hover pv-hover--${kind} ${className}`}
      style={motionStyle}
      onPointerMove={onMove}
      onPointerLeave={onLeave}
      whileHover={hoverAnim}
      whileTap={{ scale: 0.98 }}
      transition={{ type: 'spring', stiffness: 260, damping: 22 }}
      {...rest}
    >
      {children}
      {(kind === 'spotlight' || kind === 'tilt_3d') && fine.current && (
        <motion.span className="pv-hover-light" style={{ backgroundImage: light }} aria-hidden="true" />
      )}
    </motion.div>
  );
}
