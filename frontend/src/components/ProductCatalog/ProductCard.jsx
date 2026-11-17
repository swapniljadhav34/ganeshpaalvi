// Product card: 4:5 image on a soft tint, second-image cross-fade on hover, desktop-only tilt (max 5°)
// with a soft light sweep, badges, variant swatches, pack chips and one-tap WhatsApp.
import { motion, useMotionTemplate, useMotionValue, useReducedMotion, useSpring } from 'framer-motion';
import { memo, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { usePrefetchProduct } from '../../api/hooks';
import { useSite } from '../../context/SiteContext';
import { useEntrance, useShapeStyle } from '../../fx/FxContext';
import HoverFx from '../../fx/HoverFx';
import { hasFinePointer } from '../../utils/device';
import { STOCK_LABELS, tierPrice } from '../../utils/format';
import { WhatsAppIcon } from '../ui/BrandIcons';
import Price from '../ui/Price';
import styles from './ProductCatalog.module.css';

function CardBadges({ p }) {
  const items = [];
  if (p.is_new_arrival) items.push({ label: 'New', cls: 'pv-chip--ink' });
  if (p.is_bestseller) items.push({ label: 'Bestseller', cls: 'pv-chip--accent' });
  if (p.discount_percent > 0) items.push({ label: `${p.discount_percent}% off`, cls: 'pv-chip--primary' });
  p.badges.slice(0, 2).forEach((b) => items.push({ label: b.name, cls: '' }));
  return (
    <div className={styles.badges}>
      {items.slice(0, 2).map((b) => (
        <span key={b.label} className={`pv-chip ${b.cls}`}>{b.label}</span>
      ))}
    </div>
  );
}

function ProductCard({ product: p, index = 0, shared = true }) {
  const navigate = useNavigate();
  const location = useLocation();
  const prefetch = usePrefetchProduct();
  const { whatsapp, tier, design } = useSite();
  const reduce = useReducedMotion();
  const ref = useRef(null);
  const tilt = design.card_hover === 'tilt_3d';
  const fine = { current: hasFinePointer() && tilt };
  const shape = useShapeStyle(design.card_image_shape);
  const entrance = useEntrance(design.card_entrance, { delay: (index % 4) * 0.05 });

  // Tilt + light sweep (desktop only)
  const rx = useSpring(useMotionValue(0), { stiffness: 200, damping: 20 });
  const ry = useSpring(useMotionValue(0), { stiffness: 200, damping: 20 });
  const lx = useMotionValue(50);
  const ly = useMotionValue(50);
  const sweep = useMotionTemplate`radial-gradient(circle at ${lx}% ${ly}%, rgba(255,255,255,.35), transparent 55%)`;

  const onMove = (e) => {
    if (!fine.current) return;
    const r = ref.current.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width;
    const py = (e.clientY - r.top) / r.height;
    ry.set((px - 0.5) * 10); // ±5°
    rx.set((0.5 - py) * 10);
    lx.set(px * 100);
    ly.set(py * 100);
  };
  const onLeave = () => { rx.set(0); ry.set(0); };

  const open = () => navigate(`/p/${p.slug}`, { state: { background: location, preview: p } });
  const [img1, img2] = p.images;
  const out = p.stock_status === 'out_of_stock';
  const colours = p.swatches.filter((s) => s.hex);
  const others = p.swatches.filter((s) => !s.hex);

  const card = (
    <motion.article
      ref={ref}
      className={styles.card}
      data-style={design.card_style}
      data-imghover={design.card_image_hover}
      style={fine.current ? { rotateX: rx, rotateY: ry, transformPerspective: 900 } : undefined}
      onPointerMove={onMove}
      onPointerLeave={onLeave}
      onPointerEnter={() => prefetch(p.slug)}
      onTouchStart={() => prefetch(p.slug)}
      {...(reduce ? {} : entrance)}
    >
      <button type="button" className={styles.cardHit} onClick={open} aria-label={`${p.title}, view details`} />
      <div className={styles.media} style={{ aspectRatio: design.card_aspect, ...shape }}>
        <motion.div layoutId={shared ? `media-${p.slug}` : undefined} className={styles.mediaInner}>
          {img1?.thumb ? (
            <img src={img1.thumb} srcSet={img1.medium ? `${img1.thumb} 480w, ${img1.medium} 960w` : undefined}
              sizes="(min-width: 1200px) 22vw, (min-width: 768px) 30vw, 48vw" alt={img1.alt} loading={index < 4 ? 'eager' : 'lazy'}
              decoding="async" className={styles.img} width="480" height="600" />
          ) : <div className={styles.noImg} aria-hidden="true">{p.title.slice(0, 1)}</div>}
          {img2?.thumb && <img src={img2.thumb} alt="" loading="lazy" decoding="async" className={`${styles.img} ${styles.img2}`} width="480" height="600" />}
        </motion.div>
        {fine.current && <motion.div className={styles.sweep} style={{ backgroundImage: sweep }} aria-hidden="true" />}
        <CardBadges p={p} />
        {out && <span className={styles.stockOverlay}>{STOCK_LABELS.out_of_stock}</span>}
        {design.card_show_whatsapp && <button
          type="button"
          className={styles.waBtn}
          onClick={(e) => {
            e.stopPropagation();
            whatsapp({ product: p, unitPrice: tierPrice(p, tier) });
          }}
          aria-label={`Enquire about ${p.title} on WhatsApp`}
        >
          <WhatsAppIcon size={18} />
        </button>}
      </div>

      <div className={styles.body}>
        {p.category && <span className="t-caption">{p.category.name}</span>}
        <h3 className={styles.title}>{p.title}</h3>
        {p.subtitle && <p className={styles.subtitle}>{p.subtitle}</p>}
        <div className={styles.metaRow}>
          <Price product={p} size="sm" />
        </div>
        {(colours.length > 0 || others.length > 0 || p.packages.length > 0) && (
          <div className={styles.extras}>
            {colours.length > 0 && (
              <span className={styles.swatches} aria-label={`Colours: ${colours.map((c) => c.value).join(', ')}`}>
                {colours.slice(0, 4).map((c) => <span key={c.value} className={styles.swatch} style={{ background: c.hex }} title={c.value} />)}
              </span>
            )}
            {others.slice(0, 2).map((s) => <span key={s.value} className={styles.mini}>{s.value}</span>)}
            {p.packages.length > 1 && <span className={styles.mini}>{p.packages.length} pack sizes</span>}
          </div>
        )}
      </div>
    </motion.article>
  );
  if (tilt || !design.card_hover || design.card_hover === 'none') return card;
  return <HoverFx kind={design.card_hover} className="pv-fill">{card}</HoverFx>;
}

export default memo(ProductCard);
