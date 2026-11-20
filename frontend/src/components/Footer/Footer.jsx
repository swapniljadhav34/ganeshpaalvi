// Footer: brand story, admin-editable columns (own links, automatic categories, automatic
// contact details), legal small print and the big wordmark — its text, size and animation
// are chosen in Site Design Studio.
import { motion, useMotionValue, useScroll, useTransform } from 'framer-motion';
import { Mail, MapPin, Phone } from 'lucide-react';
import { useRef } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useSite } from '../../context/SiteContext';
import Decor from '../../fx/Decor';
import Divider from '../../fx/Divider';
import PointerArea, { usePointer } from '../../fx/PointerArea';
import { useSmoothScroll } from '../../hooks/useSmoothScroll';
import { STATIC_SITE } from '../../staticSite';
import { useLinkProps } from '../../utils/useLinkAction';
import { FacebookIcon, InstagramIcon, WhatsAppIcon, XIcon } from '../ui/BrandIcons';
import Icon from '../ui/Icon';
import styles from './Footer.module.css';
import { useCalm } from '../../hooks/useCalm';
import { useT } from '../../i18n/I18n';

const FOOTER_BG = {
  ink: 'var(--color-ink)', light: 'var(--color-surface)', primary: 'var(--color-primary-soft)',
  gradient: 'var(--color-primary-soft)', glass: 'var(--color-surface-elevated)',
};

function LinkIcon({ name }) {
  if (!name) return null;
  if (name === 'whatsapp') return <WhatsAppIcon size={16} />;
  if (name === 'mail' || name === 'email') return <Mail size={16} strokeWidth={1.5} />;
  if (name === 'phone') return <Phone size={16} strokeWidth={1.5} />;
  if (name === 'map') return <MapPin size={16} strokeWidth={1.5} />;
  return <Icon name={name} size={16} />;
}

function OwnLinks({ links }) {
  const linkProps = useLinkProps();
  return links.map((l) => (
    <li key={`${l.label}-${l.link}`}>
      <a {...linkProps(l.link)}><LinkIcon name={l.icon} />{l.label}</a>
    </li>
  ));
}

function Column({ col }) {
  const { brand, data, whatsapp } = useSite();
  const [, setParams] = useSearchParams();
  const { scrollTo } = useSmoothScroll();
  const goCategory = (slug) => (e) => {
    e.preventDefault();
    setParams((p) => { const n = new URLSearchParams(p); n.set('category', slug); return n; }, { preventScrollReset: true });
    setTimeout(() => scrollTo('#catalog'), 50);
  };
  const cats = (data?.categories || []).flatMap((c) => [c, ...(c.children || [])]).slice(0, 7);
  return (
    <nav aria-label={col.title}>
      <p className="t-caption">{col.title}</p>
      <ul className={col.kind === 'contact' ? styles.contact : styles.links}>
        {col.kind === 'categories' && cats.map((c) => (
          <li key={c.slug}><a href={`/?category=${c.slug}#catalog`} onClick={goCategory(c.slug)}>{c.name}</a></li>
        ))}
        {col.kind === 'contact' && (
          <>
            {brand.whatsapp && <li><button type="button" onClick={() => whatsapp()}><WhatsAppIcon size={16} /> WhatsApp +{brand.whatsapp}</button></li>}
            {brand.email && <li><a href={`mailto:${brand.email}`}><Mail size={16} strokeWidth={1.5} /> {brand.email}</a></li>}
            {brand.phone && <li><a href={`tel:${brand.phone.replace(/\s/g, '')}`}><Phone size={16} strokeWidth={1.5} /> {brand.phone}</a></li>}
            {brand.address && (
              <li>
                {brand.maps ? <a href={brand.maps} target="_blank" rel="noopener"><MapPin size={16} strokeWidth={1.5} /> {brand.address}</a>
                  : <span><MapPin size={16} strokeWidth={1.5} /> {brand.address}</span>}
              </li>
            )}
          </>
        )}
        <OwnLinks links={col.links || []} />
      </ul>
    </nav>
  );
}

function FollowLetter({ ch, i, count }) {
  const { px } = usePointer();
  const zero = useMotionValue(0);
  const center = count > 1 ? i / (count - 1) : 0.5;
  const y = useTransform(px || zero, (v) => -Math.max(0, 1 - Math.abs((v + 1) / 2 - center) * 4) * 26);
  return <motion.span className={styles.letter} style={px ? { y } : undefined}>{ch}</motion.span>;
}

function GiantWordmark({ text, size, anim }) {
  const ref = useRef(null);
  const reduce = useCalm();
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start end', 'end end'] });
  const y = useTransform(scrollYProgress, [0, 1], ['40%', '0%']);
  if (!text || size === 'hidden') return null;
  const a = reduce ? 'none' : anim;
  const cls = `${styles.giant} ${styles[`gs_${size}`]} ${styles[`ga_${a}`] || ''}`;
  const letters = text.split('');

  if (a === 'marquee') {
    return (
      <div className={`${cls} ${styles.giantMarquee}`} aria-hidden="true">
        <div className={styles.giantTrack}>{`${text} ✦ `.repeat(6)}</div>
      </div>
    );
  }
  if (a === 'letters' || a === 'wave' || a === 'follow') {
    return (
      <p ref={ref} className={cls} aria-hidden="true">
        {letters.map((ch, i) => (a === 'follow' ? <FollowLetter key={i} ch={ch} i={i} count={letters.length} /> : (
          <motion.span key={i} className={styles.letter}
            initial={{ y: '100%', opacity: 0 }}
            whileInView={a === 'wave' ? { opacity: 1, y: ['0%', '-10%', '0%'] } : { y: '0%', opacity: 1 }}
            viewport={{ once: a !== 'wave' }}
            transition={a === 'wave'
              ? { opacity: { duration: 0.4, delay: i * 0.05 }, y: { duration: 2.4, repeat: Infinity, delay: i * 0.12, ease: 'easeInOut' } }
              : { duration: 0.9, ease: [0.22, 1, 0.36, 1], delay: i * 0.06 }}>
            {ch === ' ' ? ' ' : ch}
          </motion.span>
        )))}
      </p>
    );
  }
  if (a === 'rise') {
    return (
      <motion.p ref={ref} className={cls} aria-hidden="true" initial={{ y: 80, opacity: 0 }} whileInView={{ y: 0, opacity: 1 }}
        viewport={{ once: true }} transition={{ duration: 1.2, ease: [0.22, 1, 0.36, 1] }}>{text}</motion.p>
    );
  }
  if (a === 'parallax') return <motion.p ref={ref} className={cls} style={{ y }} aria-hidden="true">{text}</motion.p>;
  return <p ref={ref} className={cls} aria-hidden="true">{text}</p>;
}

export default function Footer() {
  const { brand, data, design, motionPaused, setMotionPaused } = useSite();
  const t = useT();
  if (!brand) return null;
  const year = new Date().getFullYear();
  const columns = data?.footer?.length ? data.footer : [{ title: 'Shop', kind: 'categories', links: [] }, { title: 'Talk to us', kind: 'contact', links: [] }];
  const style = design.footer_style || 'ink';
  const word = design.footer_wordmark_text || brand.name;

  return (
    <PointerArea as="footer" alwaysTrack className={`${styles.footer} ${styles[`f_${style}`]}`} style={{ '--sec-bg': FOOTER_BG[style] }}>
      <Divider kind={design.footer_divider} position="top" />
      <Decor kind={design.footer_decor} />
      <div className={`pv-container ${styles.inner}`}>
        <div className={styles.top} style={{ '--cols': columns.length }}>
          <div className={styles.brandCol}>
            <p className={styles.wordmark} style={{ letterSpacing: design.wordmark_spacing }}>{brand.name.toUpperCase()}</p>
            {brand.tagline && <p className={styles.tagline}>{brand.tagline}</p>}
            {brand.footer_story && <p className={styles.story}>{brand.footer_story}</p>}
            {design.footer_show_socials && (
              <div className={styles.socials}>
                {brand.instagram && <a href={brand.instagram} target="_blank" rel="noopener" aria-label="Instagram"><InstagramIcon size={18} /></a>}
                {brand.facebook && <a href={brand.facebook} target="_blank" rel="noopener" aria-label="Facebook"><FacebookIcon size={18} /></a>}
                {brand.x && <a href={brand.x} target="_blank" rel="noopener" aria-label="X (Twitter)"><XIcon size={16} /></a>}
              </div>
            )}
          </div>
          {columns.map((col) => <Column key={col.title} col={col} />)}
        </div>

        <div className={styles.legal}>
          <p>© {year} {brand.name}. {design.footer_legal_text}</p>
          <p className={styles.legalLinks}>
            <Link to="/privacy">{t('footer.privacy')}</Link>
            {!STATIC_SITE && <Link to="/track">{t('footer.track')}</Link>}
            <button type="button" aria-pressed={motionPaused} onClick={() => setMotionPaused(!motionPaused)}>
              {motionPaused ? t('footer.play') : t('footer.pause')}
            </button>
          </p>
          <p className={styles.legalMeta}>
            {brand.gstin && <span>GSTIN {brand.gstin}</span>}
            {brand.manufacturer && <span>{brand.manufacturer}</span>}
            {brand.marketer && <span>{brand.marketer}</span>}
            {brand.customer_care && <span>{brand.customer_care}</span>}
          </p>
        </div>
      </div>
      <GiantWordmark text={word} size={design.footer_wordmark_size} anim={design.footer_wordmark_animation} />
    </PointerArea>
  );
}
