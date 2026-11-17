// Shared wrapper for every homepage section: background, anchor id, the section's own
// shape/animation choices (FxProvider), mouse effect, decor, shaped top edge, title and CTA.
import { useReducedMotion } from 'framer-motion';
import { useMemo } from 'react';
import { useSite } from '../../context/SiteContext';
import AnimatedText from '../../fx/AnimatedText';
import Decor from '../../fx/Decor';
import Divider from '../../fx/Divider';
import { FxProvider, resolveFx, useFx } from '../../fx/FxContext';
import PointerArea from '../../fx/PointerArea';
import ShapedMedia from '../../fx/ShapedMedia';
import { linkHref, useLinkAction } from '../../utils/useLinkAction';
import Reveal from '../ui/Reveal';
import styles from './Sections.module.css';

const ANCHORS = { routine_builder: 'ritual', for_business: 'business', faq: 'faq' };
const BG_VAR = {
  surface: 'var(--color-surface)', elevated: 'var(--color-surface-elevated)', primary_tint: 'var(--color-primary-soft)',
  secondary_tint: 'var(--color-secondary-soft)', ink: 'var(--color-ink)',
};

export function sectionAnchor(section) {
  return ANCHORS[section.type] || `section-${section.id}`;
}

/** Kept for older callers: returns a click handler for an admin link. */
export function useCta() {
  return useLinkAction();
}

export function CtaButton({ section, className = 'pv-btn', opts, children }) {
  const act = useLinkAction();
  if (!section.cta_text) return null;
  const link = section.cta_link || '#catalog';
  const external = /^https?:/.test(link);
  return (
    <a href={linkHref(link)} className={className} onClick={act(link, opts)}
      target={external ? '_blank' : undefined} rel={external ? 'noopener' : undefined}>
      {children}{section.cta_text}
    </a>
  );
}

export function Paragraphs({ text, className }) {
  if (!text) return null;
  return text.split(/\n\s*\n/).map((p, i) => <p key={i} className={className}>{p}</p>);
}

/** Section title using the section's chosen text animation. */
export function SectionTitle({ text, className = 't-h1', as = 'h2', delay = 0.05 }) {
  const fx = useFx();
  return <AnimatedText key={`${text}-${fx.text}`} text={text} as={as} kind={fx.text} className={className} speed={fx.speed} delay={delay} />;
}

export function SectionHeader({ section, align = 'left', children }) {
  if (!section.eyebrow && !section.title && !section.body) return null;
  return (
    <div className={`${styles.header} ${align === 'center' ? styles.center : ''}`}>
      {section.eyebrow && <Reveal><p className="t-caption">{section.eyebrow}</p></Reveal>}
      {section.title && <SectionTitle text={section.title} />}
      {section.body && <Reveal delay={0.1} className={styles.lead}><Paragraphs text={section.body} /></Reveal>}
      {children}
    </div>
  );
}

/** The section's photos/videos (main + extras) in its chosen shape, motion, hover and gallery style. */
export function SectionMedia({ section, className = '', items, fallback = true, ...rest }) {
  const fx = useFx();
  const media = items || section.media || [];
  if (!media.length && !fallback) return null;
  return (
    <Reveal className={className}>
      <ShapedMedia media={media} shape={fx.shape} motion={fx.motion} hover={fx.hover} gallery={fx.gallery}
        interval={fx.interval} speed={fx.speed} {...rest} />
    </Reveal>
  );
}

export default function SectionShell({ section, children, className = '', tight = false, ...rest }) {
  const { design } = useSite();
  const reduce = useReducedMotion();
  const fx = useMemo(() => resolveFx(section, design), [section, design]);
  const bg = styles[`bg_${section.background}`] || '';
  return (
    <FxProvider value={fx}>
      <PointerArea
        as="section"
        effect={reduce ? 'none' : fx.pointer}
        id={sectionAnchor(section)}
        className={`${tight ? styles.tight : 'pv-section'} ${styles.section} ${bg} ${section.background === 'ink' ? 'bg-dark-any' : ''} ${className}`}
        style={{ '--sec-bg': BG_VAR[section.background] || BG_VAR.surface }}
        aria-label={section.title || section.type.replace(/_/g, ' ')}
        {...rest}
      >
        <Divider kind={fx.divider} position="top" />
        <Decor kind={fx.decor} />
        <div className={styles.sectionBody}>{children}</div>
      </PointerArea>
    </FxProvider>
  );
}
