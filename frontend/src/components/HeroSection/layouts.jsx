// The 24 hero layouts. Each receives the slide, its resolved effects (fx) and media list,
// and is built from the shared design kit, so shapes / animations / galleries chosen in the
// admin apply everywhere.
import { motion, useMotionTemplate, useMotionValue, useScroll, useTransform } from 'framer-motion';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useSite } from '../../context/SiteContext';
import AnimatedText from '../../fx/AnimatedText';
import { useShapeStyle } from '../../fx/FxContext';
import MediaGallery from '../../fx/MediaGallery';
import MediaItem from '../../fx/MediaItem';
import { useDepth, usePointer } from '../../fx/PointerArea';
import ShapedMedia from '../../fx/ShapedMedia';
import { ease } from '../../theme/motion';
import Hero3DShowcase from '../../three/Hero3DShowcase';
import Price from '../ui/Price';
import { BgMedia, HeroCopy, ProductChip, fill } from './HeroParts';
import s from './Hero.module.css';
import { useCalm } from '../../hooks/useCalm';

const Veil = ({ kind = 'side' }) => <div className={`${s.veil} ${s[`veil_${kind}`]}`} />;

function Droplets() {
  const drops = useMemo(() => Array.from({ length: 14 }, (_, i) => ({
    left: `${(i * 37) % 100}%`, top: `${(i * 53) % 90}%`, size: 6 + ((i * 7) % 22), delay: (i % 5) * 0.6,
  })), []);
  return (
    <div className={s.droplets} aria-hidden="true">
      {drops.map((d, i) => <span key={i} className={s.drop} style={{ left: d.left, top: d.top, width: d.size, height: d.size, animationDelay: `${d.delay}s` }} />)}
    </div>
  );
}

const shaped = (fx, media, extra = {}) => (
  <ShapedMedia media={media} shape={fx.shape} motion={fx.motion} hover={fx.hover} gallery={fx.gallery} interval={fx.interval} speed={fx.speed} sizes="(min-width: 992px) 50vw, 100vw" {...extra} />
);

// 1 ─ Cinematic full screen
function Cinematic({ slide, fx, media, product, reduce }) {
  const ref = useRef(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start start', 'end start'] });
  const scale = useTransform(scrollYProgress, [0, 1], [1, 0.92]);
  const radius = useTransform(scrollYProgress, [0, 0.6], [0, 28]);
  const bgY = useTransform(scrollYProgress, [0, 1], ['0%', '18%']);
  const dropY = useTransform(scrollYProgress, [0, 1], ['0%', '-30%']);
  const fgY = useTransform(scrollYProgress, [0, 1], ['0%', '-60%']);
  const fade = useTransform(scrollYProgress, [0, 0.7], [1, 0]);
  return (
    <motion.div ref={ref} className={s.frame} style={reduce ? undefined : { scale, borderRadius: radius }}>
      <motion.div className={s.bg} style={reduce ? undefined : { y: bgY }}><BgMedia media={media} fx={fx} /><Veil /></motion.div>
      <motion.div className={s.layer} style={reduce ? undefined : { y: dropY }}><Droplets /></motion.div>
      <motion.div className={`pv-container ${s.bottomRow}`} style={reduce ? undefined : { y: fgY, opacity: fade }}>
        <HeroCopy slide={slide} fx={fx} />
        <ProductChip product={product} className={s.desktopOnly} />
      </motion.div>
    </motion.div>
  );
}

// 2 ─ Centered statement
function Centered({ slide, fx, media }) {
  return (
    <div className={s.frame}>
      <div className={s.bg}><BgMedia media={media} fx={fx} /><Veil kind="even" /></div>
      <div className={`pv-container ${s.middle}`}><HeroCopy slide={slide} fx={fx} align="center" /></div>
    </div>
  );
}

// 3 ─ Ken Burns slideshow with story-style progress bars
function Slideshow({ slide, fx, media }) {
  const reduce = useCalm();
  const [i, setI] = useState(0);
  const n = Math.max(media.length, 1);
  useEffect(() => {
    if (n < 2 || reduce) return undefined;
    const t = setTimeout(() => setI((x) => (x + 1) % n), fx.interval * 1000);
    return () => clearTimeout(t);
  }, [i, n, fx.interval, reduce]);
  return (
    <div className={s.frame}>
      <div className={s.bg}>
        {media.map((m, k) => (
          <motion.div key={k} className={s.fill} initial={false} animate={{ opacity: k === i ? 1 : 0 }} transition={{ duration: 1.4 * fx.speed, ease }}>
            <MediaItem item={m} priority={k === 0 ? undefined : false} kenBurns={!reduce} />
          </motion.div>
        ))}
        {!media.length && <div className={s.gradient} />}
        <Veil />
      </div>
      <div className={`pv-container ${s.bottomRow}`}>
        <div className={s.stack}>
          <HeroCopy slide={slide} fx={fx} />
          {n > 1 && (
            <div className={s.bars} aria-hidden="true">
              {media.map((_, k) => (
                <button key={k} type="button" className={s.bar} onClick={() => setI(k)} tabIndex={-1}>
                  <motion.span key={`${k}-${i}`} initial={{ scaleX: k < i ? 1 : 0 }} animate={{ scaleX: k <= i ? 1 : 0 }}
                    transition={{ duration: k === i ? fx.interval : 0.2, ease: 'linear' }} />
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// 4 ─ Split screen
function SplitScreen({ slide, fx, media, product }) {
  return (
    <div className={s.splitScreen}>
      <div className={s.splitPanel}>
        <HeroCopy slide={slide} fx={fx} />
        <ProductChip product={product} className={s.desktopOnly} />
      </div>
      <motion.div className={s.splitMedia} initial={{ clipPath: 'inset(0 0 0 100%)' }} animate={{ clipPath: 'inset(0 0 0 0%)' }}
        transition={{ duration: 1.3 * fx.speed, ease, delay: 0.1 }}>
        <BgMedia media={media} fx={fx} />
      </motion.div>
    </div>
  );
}

// 5 ─ Curtain reveal
function Curtain({ slide, fx, media, reduce }) {
  return (
    <div className={s.frame}>
      <div className={s.bg}><BgMedia media={media} fx={fx} /><Veil kind="even" /></div>
      {!reduce && (
        <>
          <motion.div className={`${s.curtain} ${s.curtainL}`} initial={{ scaleX: 1 }} animate={{ scaleX: 0 }} transition={{ duration: 1.5 * fx.speed, ease, delay: 0.25 }} />
          <motion.div className={`${s.curtain} ${s.curtainR}`} initial={{ scaleX: 1 }} animate={{ scaleX: 0 }} transition={{ duration: 1.5 * fx.speed, ease, delay: 0.25 }} />
        </>
      )}
      <div className={`pv-container ${s.middle}`}><HeroCopy slide={slide} fx={fx} align="center" delay={reduce ? 0 : 1} /></div>
    </div>
  );
}

// 6 ─ Zoom on scroll (media grows from your shape to full screen)
function ZoomScroll({ slide, fx, media }) {
  const ref = useRef(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start start', 'end end'] });
  const inset = useTransform(scrollYProgress, [0, 0.65], [22, 0]);
  const side = useTransform(scrollYProgress, [0, 0.65], [26, 0]);
  const round = useTransform(scrollYProgress, [0, 0.65], [48, 0]);
  const clip = useMotionTemplate`inset(${inset}% ${side}% ${inset}% ${side}% round ${round}px)`;
  const introFade = useTransform(scrollYProgress, [0, 0.25], [1, 0]);
  const outroFade = useTransform(scrollYProgress, [0.6, 0.85], [0, 1]);
  return (
    <div ref={ref} className={s.zoomTrack}>
      <div className={s.zoomSticky}>
        <motion.div className={s.bg} style={{ clipPath: clip }}><BgMedia media={media} fx={fx} /><Veil kind="even" /></motion.div>
        <motion.div className={`pv-container ${s.zoomIntro}`} style={{ opacity: introFade }}>
          <HeroCopy slide={{ ...slide, subheadline: '', cta_text: '', secondary_cta_text: '' }} fx={fx} align="center" />
        </motion.div>
        <motion.div className={`pv-container ${s.middle}`} style={{ opacity: outroFade }}>
          <HeroCopy slide={{ ...slide, eyebrow: '-' }} fx={{ ...fx, text: 'none' }} align="center" hideHeadline />
        </motion.div>
      </div>
    </div>
  );
}

// 7 ─ Torch spotlight
function Spotlight({ slide, fx, media }) {
  const { px, py } = usePointer();
  const reduce = useCalm();
  const zero = useMotionValue(0);
  const mx = useTransform(px || zero, (v) => 50 + v * 50);
  const my = useTransform(py || zero, (v) => 50 + v * 50);
  const mask = useMotionTemplate`radial-gradient(circle min(34vw, 300px) at ${mx}% ${my}%, transparent 0%, transparent 35%, rgba(8,10,14,.94) 100%)`;
  return (
    <div className={`${s.frame} ${s.dark}`}>
      <div className={s.bg}><BgMedia media={media} fx={fx} /></div>
      <motion.div className={`${s.torch} ${px ? '' : s.torchAuto}`} style={px && !reduce ? { backgroundImage: mask } : undefined} />
      <div className={`pv-container ${s.middle}`}><HeroCopy slide={slide} fx={fx} align="center" /></div>
    </div>
  );
}

// 8 ─ Video inside the headline
function TextMask({ slide, fx, media }) {
  const { theme } = useSite();
  const surface = theme?.tokens?.surface || '#F8F7F4';
  const dark = (() => {
    const h = surface.replace('#', '');
    const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
    return 0.299 * r + 0.587 * g + 0.114 * b < 128;
  })();
  return (
    <div className={s.maskWrap}>
      <div className={s.maskStage}>
        <div className={s.bg}><BgMedia media={media} fx={fx} /></div>
        <div className={s.maskCover} style={{ background: dark ? '#000' : '#fff', mixBlendMode: dark ? 'multiply' : 'screen' }}>
          <AnimatedText text={slide.headline} as="h1" kind={fx.text} speed={fx.speed} trigger="mount"
            className={s.maskText} style={{ color: dark ? '#fff' : '#000' }} />
        </div>
      </div>
      <div className="pv-container"><HeroCopy slide={slide} fx={fx} align="center" hideHeadline /></div>
    </div>
  );
}

// 9 / 10 ─ Words + shaped media
function SplitShape({ slide, fx, media, product, reverse = false }) {
  const depth = useDepth(-18);
  return (
    <div className={`pv-container ${s.twoCol} ${reverse ? s.reverse : ''}`}>
      <HeroCopy slide={slide} fx={fx} />
      <motion.div className={s.shapeCol} style={depth}>
        <motion.div className={s.shapeBox} initial={{ opacity: 0, scale: 0.92 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 1.2 * fx.speed, ease, delay: 0.2 }}>
          {shaped(fx, media)}
        </motion.div>
        <ProductChip product={product} className={s.chipFloat} />
      </motion.div>
    </div>
  );
}

// 11 ─ Arch window
function ArchWindow({ slide, fx, media }) {
  const shape = slide.media_shape || 'arch_full';
  return (
    <div className={`pv-container ${s.archWrap}`}>
      <HeroCopy slide={{ ...slide, subheadline: '', cta_text: '', secondary_cta_text: '' }} fx={fx} align="center" hideHeadline />
      <div className={s.archStage}>
        <motion.div className={s.archMedia} initial={{ opacity: 0, y: 60 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 1.3 * fx.speed, ease }}>
          {shaped({ ...fx, shape }, media)}
        </motion.div>
        <AnimatedText text={slide.headline} as="h1" kind={fx.text} speed={fx.speed} trigger="mount" delay={0.4}
          className={`${s.headline} ${s.archHeadline} ${s[`hs_${slide.headline_size || 'l'}`]}`} />
      </div>
      <HeroCopy slide={{ ...slide, eyebrow: '-' }} fx={fx} align="center" hideHeadline />
    </div>
  );
}

// 12 ─ Product spotlight with floating chips
function Chip({ children, depth, className }) {
  const d = useDepth(depth);
  return <motion.span className={`${s.floatChip} pv-glass ${className}`} style={d}>{children}</motion.span>;
}
function ProductSpotlight({ slide, fx, media, product }) {
  const img = product?.images?.[0]?.medium;
  const items = img ? [{ type: 'image', src: img, alt: product.title }] : media;
  const shape = slide.media_shape || 'circle';
  const back = useDepth(10);
  const front = useDepth(-26);
  const chips = [
    ...(product?.badges || []).slice(0, 2).map((b) => b.name),
    product?.category?.name,
  ].filter(Boolean);
  return (
    <div className={`pv-container ${s.twoCol}`}>
      <HeroCopy slide={slide} fx={fx} />
      <div className={s.spotStage}>
        <motion.div className={s.spotGlow} style={back} />
        <motion.div className={s.spotMedia} style={front} initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }}
          transition={{ type: 'spring', stiffness: 70, damping: 14, delay: 0.2 }}>
          {shaped({ ...fx, shape, motion: fx.motion === 'none' ? 'float' : fx.motion }, items)}
        </motion.div>
        {chips.map((c, i) => <Chip key={c} depth={[34, -40, 22][i]} className={s[`fc${i}`]}>{c}</Chip>)}
        {product && <Chip depth={-30} className={s.fcPrice}><Price product={product} size="sm" /></Chip>}
      </div>
    </div>
  );
}

// 13 ─ 3D tilt card
function TiltCard({ slide, fx, media, product }) {
  const { px, py } = usePointer();
  const zero = useMotionValue(0);
  const ry = useTransform(px || zero, (v) => v * 14);
  const rx = useTransform(py || zero, (v) => v * -10);
  const gx = useTransform(px || zero, (v) => 50 + v * 40);
  const glare = useMotionTemplate`linear-gradient(115deg, transparent 20%, rgba(255,255,255,.35) ${gx}%, transparent 80%)`;
  return (
    <div className={`pv-container ${s.twoCol}`}>
      <HeroCopy slide={slide} fx={fx} />
      <div className={s.tiltStage}>
        <motion.div className={s.tiltCard} style={{ rotateX: rx, rotateY: ry, transformPerspective: 1200 }}
          initial={{ opacity: 0, rotateY: -30 }} animate={{ opacity: 1 }} transition={{ duration: 1.2 * fx.speed, ease }}>
          {shaped({ ...fx, hover: 'none' }, media)}
          <motion.div className={s.glare} style={{ backgroundImage: glare }} />
          {product && <ProductChip product={product} className={s.tiltChip} />}
        </motion.div>
      </div>
    </div>
  );
}

// 14 ─ Framed inset with a glass panel
function Framed({ slide, fx, media, product }) {
  const shapeCss = useShapeStyle(fx.shape);
  return (
    <div className={s.framedWrap}>
      <motion.div className={s.framedMedia} style={{ ...shapeCss, aspectRatio: undefined }} initial={{ opacity: 0, scale: 1.04 }}
        animate={{ opacity: 1, scale: 1 }} transition={{ duration: 1.4 * fx.speed, ease }}>
        <BgMedia media={media} fx={fx} />
      </motion.div>
      <div className={`${s.framedPanel} pv-glass`}><HeroCopy slide={slide} fx={fx} compact /></div>
      <ProductChip product={product} className={`${s.framedChip} ${s.desktopOnly}`} />
    </div>
  );
}

// 15 ─ Diagonal split
function Diagonal({ slide, fx, media }) {
  return (
    <div className={s.diagWrap}>
      <motion.div className={s.diagMedia} initial={{ clipPath: 'polygon(100% 0, 100% 0, 100% 100%, 100% 100%)' }}
        animate={{ clipPath: 'polygon(24% 0, 100% 0, 100% 100%, 0% 100%)' }} transition={{ duration: 1.4 * fx.speed, ease, delay: 0.15 }}>
        <BgMedia media={media} fx={fx} />
      </motion.div>
      <div className={`pv-container ${s.diagCopy}`}><HeroCopy slide={slide} fx={fx} /></div>
    </div>
  );
}

// 16 ─ Orbit
function Orbit({ slide, fx, media }) {
  const [center, ...rest] = media.length ? media : [null];
  const ring = fill(rest.length ? rest : media, 6).slice(0, 8);
  const reduce = useCalm();
  return (
    <div className={`pv-container ${s.twoCol}`}>
      <HeroCopy slide={slide} fx={fx} />
      <div className={s.orbitStage}>
        <motion.div className={s.orbitRing} animate={reduce ? undefined : { rotate: 360 }} transition={{ duration: 60 * fx.speed, repeat: Infinity, ease: 'linear' }}>
          {ring.map((m, i) => {
            const a = (i / ring.length) * Math.PI * 2;
            return (
              <motion.div key={i} className={s.orbitItem} style={{ left: `${50 + Math.cos(a) * 46}%`, top: `${50 + Math.sin(a) * 46}%` }}
                animate={reduce ? undefined : { rotate: -360 }} transition={{ duration: 60 * fx.speed, repeat: Infinity, ease: 'linear' }}>
                <motion.div className={s.fill} initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring', stiffness: 120, damping: 12, delay: 0.4 + i * 0.08 }}>
                  <ShapedMedia media={[m]} shape="circle" hover={fx.hover} priority={false} sizes="120px" />
                </motion.div>
              </motion.div>
            );
          })}
        </motion.div>
        <motion.div className={s.orbitCenter} initial={{ scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ duration: 1.2 * fx.speed, ease }}>
          {shaped({ ...fx, shape: slide.media_shape || 'circle' }, [center])}
        </motion.div>
      </div>
    </div>
  );
}

// 17 ─ Floating collage (depth parallax)
const COLLAGE = [
  { l: 4, t: 8, w: 46, h: 58, d: 14 }, { l: 54, t: 0, w: 40, h: 44, d: -22 }, { l: 46, t: 50, w: 46, h: 46, d: 30 },
  { l: 0, t: 64, w: 34, h: 34, d: -34 }, { l: 30, t: 30, w: 26, h: 30, d: 44 },
];
function CollageTile({ item, cfg, fx, i }) {
  const d = useDepth(cfg.d);
  return (
    <motion.div className={s.collageTile} style={{ left: `${cfg.l}%`, top: `${cfg.t}%`, width: `${cfg.w}%`, height: `${cfg.h}%`, zIndex: i === 4 ? 3 : 1, ...d }}
      initial={{ opacity: 0, y: 60, rotate: i % 2 ? 4 : -4 }} animate={{ opacity: 1, y: 0, rotate: 0 }}
      transition={{ type: 'spring', stiffness: 70, damping: 15, delay: 0.2 + i * 0.12 }}>
      <ShapedMedia media={[item]} shape={fx.shape} hover={fx.hover} motion={fx.motion} priority={i === 0 ? undefined : false} sizes="(min-width: 992px) 25vw, 50vw" />
    </motion.div>
  );
}
function Collage({ slide, fx, media }) {
  const tiles = fill(media, 5).slice(0, 5);
  return (
    <div className={`pv-container ${s.twoCol}`}>
      <HeroCopy slide={slide} fx={fx} />
      <div className={s.collage}>{tiles.map((m, i) => <CollageTile key={i} item={m} cfg={COLLAGE[i]} fx={fx} i={i} />)}</div>
    </div>
  );
}

// 18 ─ Bento grid
function Bento({ slide, fx, media, product }) {
  const tiles = fill(media, 3).slice(0, 4);
  return (
    <div className={`pv-container ${s.bento}`}>
      <motion.div className={`${s.bentoCopy} ${s.bA}`} initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.9, ease }}>
        <HeroCopy slide={slide} fx={fx} compact />
      </motion.div>
      {tiles.map((m, i) => (
        <motion.div key={i} className={`${s.bentoTile} ${s[`b${i}`]}`} initial={{ opacity: 0, scale: 0.94 }} animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.9 * fx.speed, ease, delay: 0.15 + i * 0.1 }}>
          <ShapedMedia media={[m]} shape={fx.shape} hover={fx.hover} motion={fx.motion} priority={i === 0 ? undefined : false} sizes="(min-width: 992px) 25vw, 50vw" />
        </motion.div>
      ))}
      {product && <div className={`${s.bentoTile} ${s.bP}`}><ProductChip product={product} className={s.bentoChip} delay={0.6} /></div>}
    </div>
  );
}

// 19 ─ Card stack
function StackedCards({ slide, fx, media }) {
  const shapeCss = useShapeStyle(fx.shape);
  return (
    <div className={`pv-container ${s.twoCol}`}>
      <HeroCopy slide={slide} fx={fx} />
      <div className={s.stackStage}>
        <MediaGallery items={fill(media, 3)} style="stack" interval={fx.interval} shapeCss={{ ...shapeCss, aspectRatio: undefined }} speed={fx.speed} />
      </div>
    </div>
  );
}

// 20 ─ Polaroid scatter (drag them around)
function PolaroidLayout({ slide, fx, media }) {
  return (
    <div className={`pv-container ${s.twoCol}`}>
      <HeroCopy slide={slide} fx={fx} />
      <div className={s.polaroidStage}>
        <MediaGallery items={fill(media, 4).slice(0, 6)} style="polaroid" speed={fx.speed} />
        <p className={s.dragHint}>Drag the photos ✦</p>
      </div>
    </div>
  );
}

// 21 ─ Moving photo wall
function MarqueeWall({ slide, fx, media }) {
  const shapeCss = useShapeStyle(fx.shape);
  const rows = [fill(media, 6), fill([...media].reverse(), 6), fill(media.slice(1).concat(media.slice(0, 1)), 6)];
  return (
    <div className={s.frame}>
      <div className={s.wall} aria-hidden="true">
        {rows.map((r, i) => (
          <div key={i} className={`${s.wallRow} ${i === 2 ? s.desktopOnly : ''}`}>
            <MediaGallery items={r} style="marquee" shapeCss={{ ...shapeCss, aspectRatio: undefined }} speed={fx.speed * (1 + i * 0.25)} reverse={i % 2 === 1} />
          </div>
        ))}
      </div>
      <Veil kind="center" />
      <div className={`pv-container ${s.middle}`}><div className={`${s.wallCard} pv-glass`}><HeroCopy slide={slide} fx={fx} align="center" compact /></div></div>
    </div>
  );
}

// 22 ─ Coverflow carousel
function CoverflowLayout({ slide, fx, media }) {
  const shapeCss = useShapeStyle(fx.shape);
  return (
    <div className={`pv-container ${s.coverWrap}`}>
      <HeroCopy slide={{ ...slide, cta_text: '', secondary_cta_text: '' }} fx={fx} align="center" />
      <MediaGallery items={fill(media, 5)} style="coverflow" interval={fx.interval} shapeCss={{ ...shapeCss, aspectRatio: undefined }} speed={fx.speed} />
      <HeroCopy slide={{ ...slide, eyebrow: '-', subheadline: '' }} fx={fx} align="center" hideHeadline />
    </div>
  );
}

// 23 ─ Kinetic typography
function KineticType({ slide, fx, media }) {
  const words = `${slide.headline} · `;
  return (
    <div className={s.kinetic}>
      <h1 className="pv-sr">{slide.headline}</h1>
      <div className={s.kRow} aria-hidden="true"><div className={s.kTrack}>{words.repeat(4)}</div></div>
      <div className={s.kMid} aria-hidden="true">
        <div className={s.kCapsule}>{shaped({ ...fx, shape: slide.media_shape || 'pill' }, media)}</div>
      </div>
      <div className={s.kRow} aria-hidden="true"><div className={`${s.kTrack} ${s.kRev} ${s.kOutline}`}>{words.repeat(4)}</div></div>
      <div className="pv-container"><HeroCopy slide={slide} fx={fx} align="center" hideHeadline /></div>
    </div>
  );
}

// 24 ─ Minimal type over a living gradient
function MinimalType({ slide, fx }) {
  const a = useDepth(60);
  const b = useDepth(-50);
  const c = useDepth(30);
  return (
    <div className={s.frame}>
      <div className={s.mesh} aria-hidden="true">
        <motion.span className={`${s.blob} ${s.blobA}`} style={a} />
        <motion.span className={`${s.blob} ${s.blobB}`} style={b} />
        <motion.span className={`${s.blob} ${s.blobC}`} style={c} />
      </div>
      <div className={`pv-container ${s.middle}`}><HeroCopy slide={slide} fx={fx} align="center" /></div>
    </div>
  );
}

// 25 ─ 3D product showcase (models chosen in the admin; one WebGL canvas at a time)
function Showcase3D({ slide, fx, media, product, reduce, inSection }) {
  const { data } = useSite();
  const products = data?.hero_3d || [];
  if (!products.length) return <SplitShape slide={slide} fx={fx} media={media} product={product} reduce={reduce} inSection={inSection} />;
  return (
    <div className="pv-container">
      <Hero3DShowcase products={products} interval={Math.max(6, fx.interval * 1.5)}
        header={<HeroCopy slide={{ ...slide, cta_text: '', secondary_cta_text: '' }} fx={fx} inSection={inSection} compact />} />
    </div>
  );
}

export const HERO_LAYOUTS = {
  cinematic: Cinematic,
  centered: Centered,
  slideshow: Slideshow,
  split_screen: SplitScreen,
  curtain: Curtain,
  zoom_scroll: ZoomScroll,
  spotlight: Spotlight,
  text_mask: TextMask,
  split_shape: SplitShape,
  split_shape_reverse: (p) => <SplitShape {...p} reverse />,
  arch_window: ArchWindow,
  product_spotlight: ProductSpotlight,
  tilt_card: TiltCard,
  framed: Framed,
  diagonal: Diagonal,
  orbit: Orbit,
  collage: Collage,
  bento: Bento,
  stacked_cards: StackedCards,
  polaroid: PolaroidLayout,
  marquee_wall: MarqueeWall,
  coverflow: CoverflowLayout,
  kinetic_type: KineticType,
  minimal_type: MinimalType,
  showcase_3d: Showcase3D,
};

// Layouts whose media fills the whole hero (the header floats over them).
export const FULL_BLEED = new Set(['cinematic', 'centered', 'slideshow', 'curtain', 'zoom_scroll', 'spotlight', 'marquee_wall', 'minimal_type', 'split_screen', 'diagonal', 'framed']);
