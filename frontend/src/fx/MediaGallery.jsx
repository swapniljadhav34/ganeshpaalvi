// Rotating galleries of photos & videos, in 12 styles picked from the admin.
//  Inside one frame: fade, slide, zoom, ken_burns, flip, cube, blinds
//  Many frames:      stack, coverflow, marquee, grid, polaroid
import { AnimatePresence, motion } from 'framer-motion';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ease } from '../theme/motion';
import HoverFx from './HoverFx';
import MediaItem from './MediaItem';
import './fx.css';
import { useCalm } from '../hooks/useCalm';

const SMALL_SCREEN = typeof window !== 'undefined' && window.innerWidth < 768;

export const FRAMED_STYLES = new Set(['fade', 'slide', 'zoom', 'ken_burns', 'flip', 'cube', 'blinds']);

const FRAME_ANIMS = {
  fade: { initial: { opacity: 0 }, animate: { opacity: 1 }, exit: { opacity: 0 } },
  slide: { initial: (d) => ({ x: `${100 * d}%` }), animate: { x: '0%' }, exit: (d) => ({ x: `${-100 * d}%` }) },
  zoom: { initial: { opacity: 0, scale: 1.18 }, animate: { opacity: 1, scale: 1 }, exit: { opacity: 0, scale: 0.94 } },
  ken_burns: { initial: { opacity: 0 }, animate: { opacity: 1 }, exit: { opacity: 0 } },
  flip: { initial: { rotateY: 90, opacity: 0 }, animate: { rotateY: 0, opacity: 1 }, exit: { rotateY: -90, opacity: 0 } },
  cube: {
    initial: (d) => ({ rotateY: 90 * d, x: `${50 * d}%`, opacity: 0.4 }),
    animate: { rotateY: 0, x: '0%', opacity: 1 },
    exit: (d) => ({ rotateY: -90 * d, x: `${-50 * d}%`, opacity: 0.4 }),
  },
  blinds: { initial: { '--blind': '0%' }, animate: { '--blind': '17%' }, exit: { opacity: 0 } },
};

function useAutoplay(count, interval, paused) {
  const [index, setIndex] = useState(0);
  const [dir, setDir] = useState(1);
  const reduce = useCalm();
  const go = useCallback((next, d = 1) => { setDir(d); setIndex(((next % count) + count) % count); }, [count]);
  useEffect(() => {
    if (count < 2 || paused || reduce) return undefined;
    const t = setTimeout(() => go(index + 1, 1), interval * 1000);
    return () => clearTimeout(t);
  }, [index, count, interval, paused, reduce, go]);
  return { index, dir, go };
}

function Wrap({ item, children }) {
  if (!item?.link) return children;
  const external = /^https?:/.test(item.link);
  return (
    <a href={item.link} className="pv-gal-link" target={external ? '_blank' : undefined} rel={external ? 'noopener' : undefined}>
      {children}
    </a>
  );
}

function Dots({ count, index, go }) {
  if (count < 2) return null;
  return (
    <div className="pv-gal-dots" role="tablist" aria-label="Gallery">
      {Array.from({ length: count }, (_, i) => (
        <button key={i} type="button" role="tab" aria-selected={i === index} aria-label={`Show item ${i + 1}`}
          className={i === index ? 'on' : ''} onClick={(e) => { e.stopPropagation(); go(i, i > index ? 1 : -1); }} />
      ))}
    </div>
  );
}

/** One frame, items take turns (used inside a shaped box). */
function FramedGallery({ items, style, interval, priority, speed, kenBurns }) {
  const [paused, setPaused] = useState(false);
  const { index, dir, go } = useAutoplay(items.length, interval, paused);
  const anim = FRAME_ANIMS[style] || FRAME_ANIMS.fade;
  const item = items[index];
  return (
    <div className={`pv-gal-frame pv-gal-${style}`} onPointerEnter={() => setPaused(true)} onPointerLeave={() => setPaused(false)}>
      <AnimatePresence initial={false} custom={dir} mode={style === 'cube' || style === 'flip' ? 'sync' : 'sync'}>
        <motion.div
          key={index}
          className="pv-gal-slide"
          custom={dir}
          variants={{ initial: anim.initial, animate: anim.animate, exit: anim.exit }}
          initial="initial" animate="animate" exit="exit"
          transition={{ duration: (style === 'slide' || style === 'cube' ? 0.9 : 1.1) * speed, ease }}
          drag={items.length > 1 ? 'x' : false}
          dragConstraints={{ left: 0, right: 0 }}
          dragElastic={0.2}
          onDragEnd={(_, info) => { if (Math.abs(info.offset.x) > 60) go(index + (info.offset.x < 0 ? 1 : -1), info.offset.x < 0 ? 1 : -1); }}
        >
          <Wrap item={item}>
            <MediaItem item={item} priority={index === 0 ? priority : false} kenBurns={kenBurns || style === 'ken_burns'} />
          </Wrap>
          {item?.caption && <span className="pv-caption">{item.caption}</span>}
        </motion.div>
      </AnimatePresence>
      <Dots count={items.length} index={index} go={go} />
    </div>
  );
}

function Stack({ items, interval, shapeCss, speed }) {
  const [paused, setPaused] = useState(false);
  const { index, go } = useAutoplay(items.length, interval, paused);
  const order = items.map((_, i) => (i - index + items.length) % items.length); // 0 = top card
  return (
    <div className="pv-gal-stack" onPointerEnter={() => setPaused(true)} onPointerLeave={() => setPaused(false)}>
      {items.map((item, i) => {
        const pos = order[i];
        const visible = pos < 4;
        return (
          <motion.div
            key={i}
            className="pv-gal-card"
            style={{ ...shapeCss, zIndex: items.length - pos, pointerEvents: pos === 0 ? 'auto' : 'none' }}
            animate={{ rotate: pos === 0 ? 0 : (pos % 2 ? 1 : -1) * (3 + pos * 2), y: pos * 14, scale: 1 - pos * 0.05, opacity: visible ? 1 : 0 }}
            transition={{ type: 'spring', stiffness: 160 / speed, damping: 20 }}
            drag={pos === 0 ? 'x' : false}
            dragSnapToOrigin
            onDragEnd={(_, info) => { if (Math.abs(info.offset.x) > 70) go(index + 1); }}
          >
            <MediaItem item={item} priority={i === 0 ? undefined : false} still={pos > 0} />
            {item.caption && <span className="pv-caption">{item.caption}</span>}
          </motion.div>
        );
      })}
    </div>
  );
}

function Coverflow({ items, interval, shapeCss, speed }) {
  const [paused, setPaused] = useState(false);
  const { index, go } = useAutoplay(items.length, interval, paused);
  return (
    <div className="pv-gal-coverflow" onPointerEnter={() => setPaused(true)} onPointerLeave={() => setPaused(false)}>
      <motion.div className="pv-gal-cf-track" drag="x" dragConstraints={{ left: 0, right: 0 }} dragElastic={0.15}
        onDragEnd={(_, info) => { if (Math.abs(info.offset.x) > 50) go(index + (info.offset.x < 0 ? 1 : -1)); }}>
        {items.map((item, i) => {
          let off = i - index;
          if (off > items.length / 2) off -= items.length;
          if (off < -items.length / 2) off += items.length;
          const abs = Math.abs(off);
          return (
            <motion.button
              type="button"
              key={i}
              className="pv-gal-cf-item"
              style={{ ...shapeCss, zIndex: 10 - abs }}
              animate={{ x: `${off * 62}%`, rotateY: off * -38, scale: 1 - Math.min(abs, 3) * 0.14, opacity: abs > 2 ? 0 : 1 - abs * 0.18 }}
              transition={{ type: 'spring', stiffness: 140 / speed, damping: 22 }}
              onClick={() => go(i)}
              aria-label={item.caption || item.alt || `Item ${i + 1}`}
            >
              <MediaItem item={item} still={off !== 0} priority={false} />
              {item.caption && off === 0 && <span className="pv-caption">{item.caption}</span>}
            </motion.button>
          );
        })}
      </motion.div>
      <Dots count={items.length} index={index} go={go} />
    </div>
  );
}

function Marquee({ items, shapeCss, hover, speed, reverse = false }) {
  const loop = [...items, ...items];
  return (
    <div className="pv-gal-marquee">
      <div className={`pv-gal-marquee-track ${reverse ? 'rev' : ''}`} style={{ animationDuration: `${Math.max(20, items.length * 7) * speed}s` }}>
        {loop.map((item, i) => (
          <div key={i} className="pv-gal-marquee-item" aria-hidden={i >= items.length ? 'true' : undefined}>
            <HoverFx kind={hover} className="pv-fill">
              <div className="pv-shaped" style={shapeCss}><Wrap item={item}><MediaItem item={item} still priority={false} sizes="280px" /></Wrap></div>
            </HoverFx>
          </div>
        ))}
      </div>
    </div>
  );
}

function Grid({ items, shapeCss, hover, speed }) {
  return (
    <div className={`pv-gal-grid pv-gal-grid-${Math.min(items.length, 6)}`}>
      {items.map((item, i) => (
        <motion.div key={i} className="pv-gal-grid-item" initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }} transition={{ duration: 0.8 * speed, ease, delay: i * 0.08 }}>
          <HoverFx kind={hover} className="pv-fill">
            <div className="pv-shaped" style={shapeCss}>
              <Wrap item={item}><MediaItem item={item} still={SMALL_SCREEN} priority={false} sizes="(min-width: 768px) 33vw, 50vw" /></Wrap>
              {item.caption && <span className="pv-caption">{item.caption}</span>}
            </div>
          </HoverFx>
        </motion.div>
      ))}
    </div>
  );
}

const SCATTER = [[-30, 8, -7], [6, -4, 5], [38, 12, -3], [-14, 52, 6], [24, 50, -6], [52, 40, 4], [-44, 40, 3], [60, 0, -5]];

function Polaroid({ items, speed }) {
  const area = useRef(null);
  const [top, setTop] = useState(items.length - 1);
  return (
    <div className="pv-gal-polaroid" ref={area}>
      {items.slice(0, 8).map((item, i) => {
        const [x, y, r] = SCATTER[i % SCATTER.length];
        return (
          <motion.figure
            key={i}
            className="pv-polaroid"
            style={{ left: `calc(50% + ${x}% - 22%)`, top: `${y}%`, zIndex: top === i ? 20 : i }}
            initial={{ opacity: 0, y: 60, rotate: r * 2 }}
            whileInView={{ opacity: 1, y: 0, rotate: r }}
            viewport={{ once: true }}
            transition={{ type: 'spring', stiffness: 90 / speed, damping: 14, delay: i * 0.08 }}
            drag dragConstraints={area} dragElastic={0.1}
            whileDrag={{ scale: 1.06, rotate: 0 }}
            onPointerDown={() => setTop(i)}
          >
            <div className="pv-polaroid-img"><MediaItem item={item} still priority={false} sizes="240px" /></div>
            <figcaption>{item.caption || ' '}</figcaption>
          </motion.figure>
        );
      })}
    </div>
  );
}

export default function MediaGallery({ items = [], style = 'fade', interval = 5, shapeCss = {}, hover = 'none', priority, speed = 1, kenBurns, reverse }) {
  if (!items.length) return null;
  if (FRAMED_STYLES.has(style)) return <FramedGallery items={items} style={style} interval={interval} priority={priority} speed={speed} kenBurns={kenBurns} />;
  if (style === 'stack') return <Stack items={items} interval={interval} shapeCss={shapeCss} speed={speed} />;
  if (style === 'coverflow') return <Coverflow items={items} interval={interval} shapeCss={shapeCss} speed={speed} />;
  if (style === 'marquee') return <Marquee items={items} shapeCss={shapeCss} hover={hover} speed={speed} reverse={reverse} />;
  if (style === 'polaroid') return <Polaroid items={items} speed={speed} />;
  return <Grid items={items} shapeCss={shapeCss} hover={hover} speed={speed} />;
}
