// Full-screen image viewer with pinch-zoom (touch), double-tap / double-click zoom,
// mouse-wheel zoom and drag-to-pan. Lightweight — no extra library.
import { motion } from 'framer-motion';
import { ChevronLeft, ChevronRight, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import styles from './ProductDetailModal.module.css';

const clamp = (v, a, b) => Math.min(b, Math.max(a, v));

export default function ZoomViewer({ images, start = 0, onClose }) {
  const [index, setIndex] = useState(start);
  const [t, setT] = useState({ scale: 1, x: 0, y: 0 });
  const pointers = useRef(new Map());
  const pinch = useRef(null);
  const lastTap = useRef(0);
  const img = images[index];

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
      if (e.key === 'ArrowRight') go(1);
      if (e.key === 'ArrowLeft') go(-1);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const go = (d) => {
    setIndex((i) => (i + d + images.length) % images.length);
    setT({ scale: 1, x: 0, y: 0 });
  };

  const onPointerDown = (e) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.current.size === 2) {
      const [a, b] = [...pointers.current.values()];
      pinch.current = { dist: Math.hypot(a.x - b.x, a.y - b.y), scale: t.scale };
    }
    const now = Date.now();
    if (now - lastTap.current < 280 && pointers.current.size === 1) {
      setT((s) => (s.scale > 1 ? { scale: 1, x: 0, y: 0 } : { scale: 2.5, x: 0, y: 0 }));
    }
    lastTap.current = now;
  };

  const onPointerMove = (e) => {
    const prev = pointers.current.get(e.pointerId);
    if (!prev) return;
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.current.size === 2 && pinch.current) {
      const [a, b] = [...pointers.current.values()];
      const dist = Math.hypot(a.x - b.x, a.y - b.y);
      setT((s) => ({ ...s, scale: clamp((pinch.current.scale * dist) / pinch.current.dist, 1, 4) }));
    } else if (t.scale > 1) {
      setT((s) => ({ ...s, x: s.x + (e.clientX - prev.x), y: s.y + (e.clientY - prev.y) }));
    }
  };

  const onPointerUp = (e) => {
    pointers.current.delete(e.pointerId);
    if (pointers.current.size < 2) pinch.current = null;
    if (t.scale <= 1.02) setT({ scale: 1, x: 0, y: 0 });
  };

  const onWheel = (e) => {
    setT((s) => {
      const scale = clamp(s.scale * (e.deltaY < 0 ? 1.12 : 0.89), 1, 4);
      return scale === 1 ? { scale: 1, x: 0, y: 0 } : { ...s, scale };
    });
  };

  return (
    <motion.div className={styles.zoom} role="dialog" aria-modal="true" aria-label="Zoomed product image"
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} data-lenis-prevent>
      <button type="button" className={styles.zoomClose} onClick={onClose} aria-label="Close zoom"><X size={22} strokeWidth={1.5} /></button>
      <div className={styles.zoomStage} onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp} onWheel={onWheel}>
        <img src={img.full || img.medium} alt={img.alt} draggable="false"
          style={{ transform: `translate(${t.x}px, ${t.y}px) scale(${t.scale})` }} className={styles.zoomImg} />
      </div>
      {images.length > 1 && (
        <>
          <button type="button" className={`${styles.zoomNav} ${styles.zoomPrev}`} onClick={() => go(-1)} aria-label="Previous image"><ChevronLeft size={22} strokeWidth={1.5} /></button>
          <button type="button" className={`${styles.zoomNav} ${styles.zoomNext}`} onClick={() => go(1)} aria-label="Next image"><ChevronRight size={22} strokeWidth={1.5} /></button>
        </>
      )}
      <p className={styles.zoomHint}>Pinch or double-tap to zoom · {index + 1} / {images.length}</p>
    </motion.div>
  );
}
