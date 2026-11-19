// A photo, video or rotating gallery inside any admin-chosen shape, with optional
// ongoing motion (float, Ken Burns, morph…) and hover effect.
import { motion, useScroll, useTransform } from 'framer-motion';
import { useRef } from 'react';
import { isLowEndDevice } from '../utils/device';
import { useRegistry, useShapeStyle } from './FxContext';
import HoverFx from './HoverFx';
import MediaGallery, { FRAMED_STYLES } from './MediaGallery';
import MediaItem from './MediaItem';
import './fx.css';
import { useCalm } from '../hooks/useCalm';

export { MediaItem };

const lowEnd = typeof window !== 'undefined' && isLowEndDevice();

const MOTION = {
  float: { animate: { y: [0, -14, 0] }, transition: { duration: 6, repeat: Infinity, ease: 'easeInOut' } },
  breathe: { animate: { scale: [1, 1.035, 1] }, transition: { duration: 7, repeat: Infinity, ease: 'easeInOut' } },
  sway: { animate: { rotate: [-2, 2, -2] }, transition: { duration: 8, repeat: Infinity, ease: 'easeInOut' } },
  slow_spin: { animate: { rotate: 360 }, transition: { duration: 70, repeat: Infinity, ease: 'linear' } },
  drift: { animate: { x: [0, 10, 0, -10, 0], y: [0, -8, -14, -8, 0] }, transition: { duration: 12, repeat: Infinity, ease: 'easeInOut' } },
};

/**
 * media: list of {type, src, poster, caption, link, alt}
 * shape / motion / hover / gallery / interval: admin choices (already resolved)
 */
export default function ShapedMedia({
  media = [], shape = 'rounded', motion: motionKind = 'none', hover = 'none', gallery = 'fade', interval = 5,
  className = '', style, priority, speed = 1, sizes, children,
}) {
  const reduce = useCalm();
  const { shapes } = useRegistry();
  const shapeCss = useShapeStyle(shape);
  const ref = useRef(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start end', 'end start'] });
  const parY = useTransform(scrollYProgress, [0, 1], ['-8%', '8%']);
  const items = media.filter(Boolean);
  const multi = items.length > 1;

  // Multi-frame gallery styles (stack, coverflow, marquee…) shape each photo separately.
  if (multi && !FRAMED_STYLES.has(gallery)) {
    return (
      <div className={`pv-shaped-multi ${className}`} style={style}>
        <MediaGallery items={items} style={gallery} interval={interval} shapeCss={shapeCss} hover={hover} speed={speed} />
        {children}
      </div>
    );
  }

  const live = !reduce && !lowEnd;
  const morph = live && motionKind === 'morph' && !shapeCss.clipPath;
  const loop = live && MOTION[motionKind];
  const kenBurns = live && motionKind === 'ken_burns';
  const inner = multi ? (
    <MediaGallery items={items} style={gallery} interval={interval} priority={priority} speed={speed} kenBurns={kenBurns} />
  ) : (
    <MediaItem item={items[0]} priority={priority} kenBurns={kenBurns} sizes={sizes} />
  );

  const box = (
    <motion.div
      ref={ref}
      className={`pv-shaped ${morph ? 'pv-morph' : ''} ${shapes[shape]?.square ? 'pv-square' : ''}`}
      style={shapeCss}
      {...(loop || {})}
    >
      {motionKind === 'scroll_parallax' && live ? (
        <motion.div className="pv-parallax-inner" style={{ y: parY }}>{inner}</motion.div>
      ) : inner}
      {items[0]?.caption && !multi && <span className="pv-caption">{items[0].caption}</span>}
    </motion.div>
  );

  return (
    <div className={`pv-shaped-wrap ${className}`} style={style}>
      {hover && hover !== 'none' ? <HoverFx kind={hover} className="pv-fill">{box}</HoverFx> : box}
      {children}
    </div>
  );
}
