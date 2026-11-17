// Makes a whole block react to the mouse (or finger): parallax depth, 3D tilt,
// a soft following spotlight, or ripples where you tap. Children can read the
// pointer position with usePointer() to move at their own depth.
import { motion, useMotionTemplate, useMotionValue, useReducedMotion, useSpring, useTransform } from 'framer-motion';
import { createContext, useContext, useRef, useState } from 'react';
import { hasFinePointer } from '../utils/device';
import './fx.css';

const PointerCtx = createContext({ px: null, py: null });

/** Pointer position from -1 to 1 inside the nearest PointerArea (springy). */
export function usePointer() {
  return useContext(PointerCtx);
}

/** Offset (px) for a layer at a given depth, following the pointer. */
export function useDepth(depth = 20) {
  const { px, py } = usePointer();
  const fallback = useMotionValue(0);
  const x = useTransform(px || fallback, (v) => v * depth);
  const y = useTransform(py || fallback, (v) => v * depth);
  return { x, y };
}

export default function PointerArea({ effect = 'none', className = '', style, children, as = 'div', alwaysTrack = false, ...rest }) {
  const ref = useRef(null);
  const reduce = useReducedMotion();
  const rawX = useMotionValue(0);
  const rawY = useMotionValue(0);
  const px = useSpring(rawX, { stiffness: 80, damping: 18 });
  const py = useSpring(rawY, { stiffness: 80, damping: 18 });
  const lx = useMotionValue(50);
  const ly = useMotionValue(40);
  const rx = useTransform(py, (v) => v * -4);
  const ry = useTransform(px, (v) => v * 4);
  const light = useMotionTemplate`radial-gradient(520px circle at ${lx}% ${ly}%, color-mix(in srgb, var(--color-primary) 22%, transparent), transparent 60%)`;
  const [ripples, setRipples] = useState([]);
  const fine = typeof window !== 'undefined' && hasFinePointer();
  const track = !reduce && (effect !== 'none' || alwaysTrack);

  const onMove = (e) => {
    if (!track || !ref.current) return;
    const r = ref.current.getBoundingClientRect();
    const nx = (e.clientX - r.left) / r.width;
    const ny = (e.clientY - r.top) / r.height;
    rawX.set(nx * 2 - 1);
    rawY.set(ny * 2 - 1);
    lx.set(nx * 100);
    ly.set(ny * 100);
  };
  const onLeave = () => { rawX.set(0); rawY.set(0); };
  const onDown = (e) => {
    if (effect !== 'ripple' || reduce || !ref.current) return;
    const r = ref.current.getBoundingClientRect();
    const id = Date.now() + Math.random();
    setRipples((list) => [...list.slice(-4), { id, x: e.clientX - r.left, y: e.clientY - r.top }]);
    setTimeout(() => setRipples((list) => list.filter((it) => it.id !== id)), 1400);
  };

  const Cmp = motion[as] || motion.div;
  const tilt = track && effect === 'tilt' && fine;
  return (
    <PointerCtx.Provider value={track ? { px, py } : { px: null, py: null }}>
      <Cmp
        ref={ref}
        className={`pv-pointer ${className}`}
        style={{ ...style, ...(tilt ? { rotateX: rx, rotateY: ry, transformPerspective: 1400 } : {}) }}
        onPointerMove={onMove}
        onPointerLeave={onLeave}
        onPointerDown={onDown}
        {...rest}
      >
        {children}
        {track && effect === 'spotlight' && <motion.div className="pv-spotlight" style={{ backgroundImage: light }} aria-hidden="true" />}
        {ripples.map((r) => (
          <span key={r.id} className="pv-ripple" style={{ left: r.x, top: r.y }} aria-hidden="true" />
        ))}
      </Cmp>
    </PointerCtx.Provider>
  );
}
