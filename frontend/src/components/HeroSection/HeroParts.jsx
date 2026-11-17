// Building blocks shared by all 24 hero layouts: the words + buttons, the floating
// product chip, and full-bleed background media.
import { motion, useReducedMotion } from 'framer-motion';
import { useLocation, useNavigate } from 'react-router-dom';
import { useSite } from '../../context/SiteContext';
import AnimatedText from '../../fx/AnimatedText';
import MediaGallery, { FRAMED_STYLES } from '../../fx/MediaGallery';
import MediaItem from '../../fx/MediaItem';
import { ease } from '../../theme/motion';
import { linkHref, useLinkAction } from '../../utils/useLinkAction';
import { WhatsAppIcon } from '../ui/BrandIcons';
import Price from '../ui/Price';
import s from './Hero.module.css';

export function HeroCopy({ slide, fx, align = 'left', inSection = false, className = '', compact = false, hideHeadline = false, delay = 0 }) {
  const { brand } = useSite();
  const act = useLinkAction();
  const eyebrow = slide.eyebrow === '-' ? '' : slide.eyebrow || [brand?.name, brand?.tagline].filter(Boolean).join(' · ');
  const d = (x) => (delay + x) * fx.speed;
  const secondaryIsWa = slide.secondary_cta_link === 'whatsapp';
  return (
    <div className={`${s.copy} ${align === 'center' ? s.center : ''} ${compact ? s.compact : ''} ${className}`}>
      {eyebrow && (
        <motion.p className="t-caption" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: d(0.1), duration: 0.6, ease }}>
          {eyebrow}
        </motion.p>
      )}
      {!hideHeadline && (
        <AnimatedText
          key={`${slide.id}-${fx.text}`}
          text={slide.headline}
          as={inSection ? 'h2' : 'h1'}
          kind={fx.text}
          className={`${s.headline} ${s[`hs_${slide.headline_size || 'l'}`]}`}
          delay={0.2 + delay}
          speed={fx.speed}
          trigger={inSection ? 'view' : 'mount'}
        />
      )}
      {slide.subheadline && (
        <motion.p className={s.sub} initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}
          transition={{ delay: d(0.6), duration: 0.8, ease }}>
          {slide.subheadline}
        </motion.p>
      )}
      {(slide.cta_text || slide.secondary_cta_text) && (
        <motion.div className={s.ctas} initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}
          transition={{ delay: d(0.75), duration: 0.8, ease }}>
          {slide.cta_text && (
            <a href={linkHref(slide.cta_link)} className="pv-btn" onClick={act(slide.cta_link || '#catalog')}
              {...(/^https?:/.test(slide.cta_link || '') ? { target: '_blank', rel: 'noopener' } : {})}>
              {slide.cta_text}
            </a>
          )}
          {slide.secondary_cta_text && (
            <a href={linkHref(slide.secondary_cta_link)} className="pv-btn pv-btn--glass"
              onClick={act(slide.secondary_cta_link || 'whatsapp', { buyerType: 'retailer', note: 'Please share your wholesale catalogue.' })}>
              {secondaryIsWa && <WhatsAppIcon size={18} />} {slide.secondary_cta_text}
            </a>
          )}
        </motion.div>
      )}
    </div>
  );
}

export function ProductChip({ product, className = '', delay = 1, style }) {
  const navigate = useNavigate();
  const location = useLocation();
  if (!product) return null;
  const img = product.images?.[0]?.medium || product.images?.[0]?.thumb;
  return (
    <motion.button
      type="button"
      className={`${s.product} pv-glass ${className}`}
      style={style}
      initial={{ opacity: 0, y: 40, rotate: -2 }}
      animate={{ opacity: 1, y: 0, rotate: 0 }}
      transition={{ type: 'spring', stiffness: 90, damping: 18, delay }}
      whileHover={{ y: -6 }}
      onClick={() => navigate(`/p/${product.slug}`, { state: { background: location, preview: product } })}
      aria-label={`View ${product.title}`}
    >
      {img && <img src={img} alt="" className={s.productImg} />}
      <span className={s.productMeta}>
        <span className="t-caption">Featured</span>
        <span className={s.productTitle}>{product.title}</span>
        <Price product={product} size="sm" />
      </span>
    </motion.button>
  );
}

/** Full-bleed background: one photo/video, or a rotating gallery when several are added. */
export function BgMedia({ media, fx, priority = true, forceStyle }) {
  const reduce = useReducedMotion();
  if (!media?.length) return <div className={s.gradient} />;
  if (media.length === 1) {
    return <MediaItem item={media[0]} priority={priority} kenBurns={!reduce && fx.motion === 'ken_burns'} />;
  }
  const style = forceStyle || (FRAMED_STYLES.has(fx.gallery) ? fx.gallery : 'fade');
  return <MediaGallery items={media} style={style} interval={fx.interval} priority={priority} speed={fx.speed} kenBurns={fx.motion === 'ken_burns'} />;
}

/** Repeat the list until it has at least `n` items (so layouts never look empty). */
export function fill(media, n) {
  if (!media.length) return Array.from({ length: n }, () => null);
  const out = [];
  while (out.length < n) out.push(...media);
  return out.slice(0, Math.max(n, media.length));
}
