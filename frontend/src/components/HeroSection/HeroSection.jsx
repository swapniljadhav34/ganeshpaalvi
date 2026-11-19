// Homepage hero: one or more admin "Hero slides", each in any of 24 layouts with its own
// shapes, galleries, text animation, mouse effects, decor and divider. Slides rotate.
// HeroView is also used by the "Animated Hero Banner" section and the admin live preview.
import { AnimatePresence, motion } from 'framer-motion';
import { ArrowDown } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useSite } from '../../context/SiteContext';
import Decor from '../../fx/Decor';
import Divider from '../../fx/Divider';
import { FxProvider, resolveFx } from '../../fx/FxContext';
import PointerArea from '../../fx/PointerArea';
import { useSmoothScroll } from '../../hooks/useSmoothScroll';
import { MediaPriorityContext } from '../../fx/MediaItem';
import { FULL_BLEED, HERO_LAYOUTS } from './layouts';
import s from './Hero.module.css';
import { useCalm } from '../../hooks/useCalm';

export function HeroView({ slide, inSection = false, controls = null, id }) {
  const { design } = useSite();
  const reduce = useCalm();
  const fx = useMemo(() => resolveFx(slide, design), [slide, design]);
  const layout = HERO_LAYOUTS[slide.layout] ? slide.layout : 'cinematic';
  const Layout = HERO_LAYOUTS[layout];
  const media = slide.media || [];
  const product = slide.show_product === false ? null : slide.product;
  const cls = [
    s.hero, s[`h_${slide.height || (inSection ? 'large' : 'full')}`], s[`l_${layout}`],
    FULL_BLEED.has(layout) ? s.bleed : s.padded, inSection ? s.inSection : '',
    slide.text_tone === 'light' || layout === 'spotlight' ? s.light : '', slide.text_tone === 'dark' ? s.darkText : '',
  ].join(' ');
  return (
    <FxProvider value={fx}>
      <PointerArea as="section" id={id} effect={fx.pointer} alwaysTrack className={cls}
        style={{ '--veil-a': `${slide.overlay_strength ?? 40}%` }} aria-label={slide.headline || 'Welcome'}>
        <Decor kind={fx.decor} />
        <MediaPriorityContext.Provider value={!inSection}>
          <Layout slide={slide} fx={fx} media={media} product={product} reduce={reduce} inSection={inSection} />
        </MediaPriorityContext.Provider>
        {controls}
        <Divider kind={fx.divider} position="inside" />
      </PointerArea>
    </FxProvider>
  );
}

export default function HeroSection() {
  const { data } = useSite();
  const slides = data?.hero || [];
  const [index, setIndex] = useState(0);
  const reduce = useCalm();
  const { scrollTo } = useSmoothScroll();

  useEffect(() => {
    if (slides.length < 2 || reduce) return undefined;
    const t = setTimeout(() => setIndex((i) => (i + 1) % slides.length), 9000);
    return () => clearTimeout(t);
  }, [index, slides.length, reduce]);

  const slide = slides[index % Math.max(slides.length, 1)];
  if (!slide) return <section className={s.placeholder} aria-hidden="true" />;

  const controls = (
    <>
      {slides.length > 1 && (
        <div className={s.dots} role="tablist" aria-label="Hero slides">
          {slides.map((sl, i) => (
            <button key={sl.id} type="button" role="tab" aria-selected={i === index} aria-label={`Slide ${i + 1}`}
              className={`${s.dot} ${i === index ? s.dotOn : ''}`} onClick={() => setIndex(i)} />
          ))}
        </div>
      )}
      {(slide.height || 'full') === 'full' && slide.layout !== 'zoom_scroll' && (
        <button type="button" className={s.scrollCue} onClick={() => scrollTo('#catalog')} aria-label="Scroll to products">
          <ArrowDown size={18} strokeWidth={1.5} />
        </button>
      )}
    </>
  );

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div key={slide.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.6 }}>
        <HeroView slide={slide} controls={controls} />
      </motion.div>
    </AnimatePresence>
  );
}
