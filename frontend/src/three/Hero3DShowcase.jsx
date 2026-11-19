// Homepage 3D showcase: cycles through the products the owner ticked "Show in the 3D hero"
// (Products → 3D model, or Studio → Catalog & 3D), in their chosen order.
//  • Exactly ONE 3D model is mounted at a time, and only while the showcase is on screen.
//  • Everyone sees the poster instantly; the model fades in when ready.
//  • Next / previous / dots, keyboard arrows, and a CTA overlay (view product, WhatsApp).
import { AnimatePresence, motion } from 'framer-motion';
import { ArrowRight, ChevronLeft, ChevronRight } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import Price from '../components/ui/Price';
import { WhatsAppIcon } from '../components/ui/BrandIcons';
import { useSite } from '../context/SiteContext';
import { useCalm } from '../hooks/useCalm';
import { ease } from '../theme/motion';
import { tierPrice } from '../utils/format';
import Product3DViewer from './Product3DViewer';
import styles from './Hero3DShowcase.module.css';

export default function Hero3DShowcase({ products = [], interval = 9, header = null }) {
  const root = useRef(null);
  const [index, setIndex] = useState(0);
  const [inView, setInView] = useState(false);
  const [held, setHeld] = useState(false); // the visitor is playing with the model → stop auto-advancing
  const calm = useCalm();
  const { whatsapp, tier } = useSite();
  const navigate = useNavigate();
  const location = useLocation();
  const count = products.length;
  const p = products[index % Math.max(count, 1)];

  useEffect(() => {
    const el = root.current;
    if (!el || typeof IntersectionObserver === 'undefined') { setInView(true); return undefined; }
    const io = new IntersectionObserver(([e]) => setInView(e.isIntersecting), { rootMargin: '100px 0px' });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    if (count < 2 || calm || held || !inView) return undefined;
    const t = setTimeout(() => setIndex((i) => (i + 1) % count), interval * 1000);
    return () => clearTimeout(t);
  }, [index, count, calm, held, inView, interval]);

  if (!p) return null;
  const go = (d) => { setHeld(true); setIndex((i) => (i + d + count) % count); };
  const open = () => navigate(`/p/${p.slug}`, { state: { background: location, preview: p } });

  return (
    <div ref={root} className={styles.wrap} aria-roledescription="carousel" aria-label="3D product showcase"
      onKeyDown={(e) => { if (e.key === 'ArrowRight') go(1); if (e.key === 'ArrowLeft') go(-1); }}>
      <div className={styles.copy}>
        {header}
        <AnimatePresence mode="wait" initial={false}>
          <motion.div key={p.slug} className={styles.product} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.45, ease }} aria-live="polite">
            {p.category && <p className="t-caption">{p.category.name}</p>}
            <h2 className={styles.title}>{p.title}</h2>
            {p.subtitle && <p className={styles.sub}>{p.subtitle}</p>}
            <Price product={p} />
            <div className={styles.ctas}>
              <button type="button" className="pv-btn" onClick={open}>View product <ArrowRight size={16} strokeWidth={1.75} /></button>
              <button type="button" className="pv-btn pv-btn--glass" onClick={() => whatsapp({ product: p, unitPrice: tierPrice(p, tier) })}>
                <WhatsAppIcon size={18} /> WhatsApp
              </button>
            </div>
          </motion.div>
        </AnimatePresence>
      </div>

      <div className={styles.stage} onPointerDown={() => setHeld(true)}>
        {/* key = slug → the previous model is fully unmounted before the next one mounts (one WebGL context). */}
        <Product3DViewer key={p.slug} src={p.model_3d} poster={p.model_poster} alt={`${p.title} — 3D model`} active={inView}
          className={styles.viewer} />
        {count > 1 && (
          <div className={styles.nav}>
            <button type="button" className={styles.arrow} onClick={() => go(-1)} aria-label="Previous product"><ChevronLeft size={20} strokeWidth={1.75} /></button>
            <div className={styles.dots} role="tablist" aria-label="Choose product">
              {products.map((x, i) => (
                <button key={x.slug} type="button" role="tab" aria-selected={i === index} aria-label={x.title}
                  className={`${styles.dot} ${i === index ? styles.dotOn : ''}`} onClick={() => { setHeld(true); setIndex(i); }} />
              ))}
            </div>
            <button type="button" className={styles.arrow} onClick={() => go(1)} aria-label="Next product"><ChevronRight size={20} strokeWidth={1.75} /></button>
          </div>
        )}
      </div>
    </div>
  );
}
