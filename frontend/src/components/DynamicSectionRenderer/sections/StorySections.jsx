// Editorial-style sections: Video Showcase, Editorial, Promo Banner, Brand Story, Sustainability,
// Testimonials, FAQ, Instagram/UGC strip, plus Hero Banner, Media Gallery and Big Moving Text.
// All words, media, shapes and animations come from the admin.
import { AnimatePresence, motion } from 'framer-motion';
import { ChevronDown, Quote, Star } from 'lucide-react';
import { useState } from 'react';
import { useSite } from '../../../context/SiteContext';
import { useFx, useShapeStyle } from '../../../fx/FxContext';
import HoverFx from '../../../fx/HoverFx';
import MediaGallery from '../../../fx/MediaGallery';
import { HeroView } from '../../HeroSection/HeroSection';
import { InstagramIcon } from '../../ui/BrandIcons';
import Reveal from '../../ui/Reveal';
import SectionShell, { CtaButton, Paragraphs, SectionHeader, SectionMedia, SectionTitle, sectionAnchor } from '../SectionShell';
import styles from '../Sections.module.css';

export function VideoShowcase({ section }) {
  return (
    <SectionShell section={section}>
      <div className="pv-container">
        <SectionHeader section={section} />
        <SectionMedia section={section} className={styles.videoFrame} />
        <div className={styles.ctaRow}><CtaButton section={section} /></div>
      </div>
    </SectionShell>
  );
}

export function Editorial({ section, flip }) {
  const pos = section.media_position;
  const flipped = pos === 'right' ? true : pos === 'left' ? false : flip;
  return (
    <SectionShell section={section}>
      <div className={`pv-container ${styles.split} ${flipped ? styles.flip : ''}`}>
        <SectionMedia section={section} className={styles.splitMedia} />
        <div className={styles.splitText}>
          <SectionHeader section={section} />
          <Reveal delay={0.1}><CtaButton section={section} className="pv-btn pv-btn--ghost" /></Reveal>
        </div>
      </div>
    </SectionShell>
  );
}

function PromoBox({ section, children }) {
  const fx = useFx();
  const shape = useShapeStyle(fx.shape);
  // Only rounded-corner shapes suit a text banner; cut-out shapes would clip the words.
  const safe = shape.clipPath || shape.mask ? {} : { borderRadius: shape.borderRadius };
  return (
    <Reveal className={styles.promo} style={{ ...safe, ...(section.image ? { backgroundImage: `url(${section.image})` } : {}) }}>
      {children}
    </Reveal>
  );
}

export function PromoBanner({ section }) {
  return (
    <SectionShell section={section} tight>
      <div className="pv-container">
        <PromoBox section={section}>
          <div className={styles.promoInner}>
            {section.eyebrow && <p className="t-caption">{section.eyebrow}</p>}
            {section.title && <SectionTitle text={section.title} />}
            <Paragraphs text={section.body} className={styles.promoBody} />
            <CtaButton section={section} />
          </div>
        </PromoBox>
      </div>
    </SectionShell>
  );
}

function Stats({ items }) {
  if (!Array.isArray(items) || !items.length) return null;
  return (
    <div className={styles.stats}>
      {items.map((s, i) => (
        <Reveal key={i} delay={i * 0.08} className={styles.stat}>
          <span className={styles.statValue}>{s.stat}</span>
          <span className={styles.statLabel}>{s.label}</span>
        </Reveal>
      ))}
    </div>
  );
}

export function BrandStory({ section }) {
  return (
    <SectionShell section={section}>
      <div className={`pv-container ${styles.story}`}>
        <div>
          {section.eyebrow && <Reveal><p className="t-caption">{section.eyebrow}</p></Reveal>}
          {section.title && <SectionTitle text={section.title} className={`t-display ${styles.storyTitle}`} />}
        </div>
        <div className={styles.storyBody}>
          <Reveal className={styles.lead}><Paragraphs text={section.body} /></Reveal>
          <Stats items={section.items} />
          <CtaButton section={section} className="pv-btn pv-btn--ghost" />
        </div>
        {section.media?.length > 0 && <SectionMedia section={section} className={styles.storyImage} />}
      </div>
    </SectionShell>
  );
}

export function Sustainability({ section }) {
  const flipped = section.media_position === 'left';
  return (
    <SectionShell section={section}>
      <div className={`pv-container ${styles.split} ${flipped ? '' : styles.flip}`}>
        <SectionMedia section={section} className={styles.splitMedia} />
        <div className={styles.splitText}>
          <SectionHeader section={section} />
          <Stats items={section.items} />
          <CtaButton section={section} className="pv-btn pv-btn--ghost" />
        </div>
      </div>
    </SectionShell>
  );
}

export function Testimonials({ section }) {
  const items = Array.isArray(section.items) ? section.items : [];
  if (!items.length) return null;
  return (
    <SectionShell section={section}>
      <div className="pv-container">
        <SectionHeader section={section} align="center" />
        <div className={styles.quotes}>
          {items.map((t, i) => (
            <Reveal key={i} delay={i * 0.08} hover>
              <figure className={`${styles.quote} ${styles.fillCard}`}>
                <Quote size={22} strokeWidth={1.5} className={styles.quoteMark} aria-hidden="true" />
                {t.rating ? (
                  <div className={styles.stars} aria-label={`${t.rating} out of 5 stars`}>
                    {Array.from({ length: 5 }, (_, s) => <Star key={s} size={14} strokeWidth={1.5} fill={s < t.rating ? 'currentColor' : 'none'} aria-hidden="true" />)}
                  </div>
                ) : null}
                <blockquote className={styles.quoteText}>“{t.quote}”</blockquote>
                <figcaption className={styles.quoteBy}><strong>{t.name}</strong>{t.role && <span> · {t.role}</span>}</figcaption>
              </figure>
            </Reveal>
          ))}
        </div>
      </div>
    </SectionShell>
  );
}

function FaqItem({ q, a }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={styles.faqItem}>
      <button type="button" className={styles.faqQ} aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <span>{q}</span>
        <motion.span animate={{ rotate: open ? 180 : 0 }}><ChevronDown size={20} strokeWidth={1.5} /></motion.span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }} style={{ overflow: 'hidden' }}>
            <p className={styles.faqA}>{a}</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function Faq({ section }) {
  const items = Array.isArray(section.items) ? section.items : [];
  const faqLd = {
    '@context': 'https://schema.org', '@type': 'FAQPage',
    mainEntity: items.map((f) => ({ '@type': 'Question', name: f.q, acceptedAnswer: { '@type': 'Answer', text: f.a } })),
  };
  return (
    <SectionShell section={section}>
      <div className={`pv-container ${styles.faqWrap}`}>
        <SectionHeader section={section} />
        <Reveal className={styles.faq}>
          {items.map((f, i) => <FaqItem key={i} q={f.q} a={f.a} />)}
        </Reveal>
        {items.length > 0 && <script type="application/ld+json">{JSON.stringify(faqLd)}</script>}
      </div>
    </SectionShell>
  );
}

function UgcItem({ u, brand }) {
  const fx = useFx();
  const shape = useShapeStyle(fx.shape);
  return (
    <HoverFx kind={fx.hover} className={styles.ugcItem} style={{ ...shape, aspectRatio: '1' }}>
      <a href={u.link || brand?.instagram || '#'} target="_blank" rel="noopener" className="pv-fill" style={{ display: 'block' }}>
        <img src={u.image} alt={u.caption || 'Paalvi on Instagram'} loading="lazy" />
        {u.caption && <span className={styles.ugcCap}>{u.caption}</span>}
      </a>
    </HoverFx>
  );
}

export function UgcStrip({ section }) {
  const { brand } = useSite();
  const fromItems = Array.isArray(section.items) ? section.items.filter((u) => u?.image) : [];
  const fromMedia = (section.media || []).map((m) => ({ image: m.type === 'video' ? m.poster : m.src, caption: m.caption, link: m.link }));
  const items = [...fromItems, ...fromMedia].filter((u) => u.image);
  if (!items.length) return null;
  return (
    <SectionShell section={section}>
      <div className="pv-container">
        <SectionHeader section={section}>
          {brand?.instagram && (
            <a href={brand.instagram} target="_blank" rel="noopener" className="pv-btn pv-btn--ghost pv-btn--sm" style={{ alignSelf: 'flex-start' }}>
              <InstagramIcon size={16} /> Follow us
            </a>
          )}
        </SectionHeader>
      </div>
      <div className={styles.ugc}>
        {items.map((u, i) => <Reveal key={i} delay={(i % 5) * 0.06}><UgcItem u={u} brand={brand} /></Reveal>)}
      </div>
    </SectionShell>
  );
}

// --- New: Animated Hero Banner (any of the 24 hero layouts, anywhere on the page) ---
export function HeroBanner({ section }) {
  const slide = {
    ...section,
    layout: section.hero_layout || 'split_shape',
    headline: section.title || '',
    subheadline: section.body || '',
    eyebrow: section.eyebrow || '-',
    secondary_cta_text: '',
    height: 'large',
    headline_size: 'm',
    overlay_strength: 40,
    show_product: Boolean(section.product),
  };
  return <HeroView slide={slide} inSection id={sectionAnchor(section)} />;
}

// --- New: Media Gallery (rotating photos & videos in any gallery style) ---
function GalleryBody({ section }) {
  const fx = useFx();
  const shape = useShapeStyle(fx.shape);
  const media = section.media || [];
  if (!media.length) return null;
  const framed = ['fade', 'slide', 'zoom', 'ken_burns', 'flip', 'cube', 'blinds'].includes(fx.gallery);
  if (framed) return <SectionMedia section={section} className={styles.galleryFrame} />;
  return (
    <Reveal>
      <MediaGallery items={media} style={fx.gallery} interval={fx.interval} shapeCss={{ ...shape, aspectRatio: undefined }} hover={fx.hover} speed={fx.speed} />
    </Reveal>
  );
}

export function Gallery({ section }) {
  return (
    <SectionShell section={section}>
      <div className="pv-container">
        <SectionHeader section={section} align="center" />
        <GalleryBody section={section} />
        <div className={styles.ctaRow}><CtaButton section={section} /></div>
      </div>
    </SectionShell>
  );
}

// --- New: Big Moving Text ---
export function MarqueeText({ section }) {
  const fx = useFx();
  const words = (Array.isArray(section.items) && section.items.length
    ? section.items.map((w) => (typeof w === 'string' ? w : w?.text || w?.name)).filter(Boolean)
    : [section.title || 'Paalvi']);
  const row = (key, rev) => (
    <div className={styles.bigMarquee} aria-hidden="true" key={key}>
      <div className={`${styles.bigTrack} ${rev ? styles.bigTrackRev : ''}`} style={{ animationDuration: `${45 * fx.speed}s` }}>
        {[...words, ...words, ...words, ...words].map((w, i) => (
          <span key={i}>{w} <span className={styles.bigSep}>✦</span></span>
        ))}
      </div>
    </div>
  );
  return (
    <SectionShell section={section} tight>
      <p className="pv-sr">{words.join(' · ')}</p>
      {row('a', false)}
      {words.length > 1 && row('b', true)}
    </SectionShell>
  );
}
