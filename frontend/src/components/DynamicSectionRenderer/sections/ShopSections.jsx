// Shopping sections: Featured Collection, Category Grid, Free-From strip, For Business.
import { ArrowRight } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { useSite } from '../../../context/SiteContext';
import { useFx, useShapeStyle } from '../../../fx/FxContext';
import { useSmoothScroll } from '../../../hooks/useSmoothScroll';
import { STATIC_SITE } from '../../../staticSite';
import ProductCard from '../../ProductCatalog/ProductCard';
import { WhatsAppIcon } from '../../ui/BrandIcons';
import Icon from '../../ui/Icon';
import Reveal from '../../ui/Reveal';
import SectionShell, { CtaButton, SectionHeader } from '../SectionShell';
import styles from '../Sections.module.css';

export function FeaturedCollection({ section }) {
  const products = section.products || [];
  if (!products.length) return null;
  return (
    <SectionShell section={section}>
      <div className="pv-container">
        <div className={styles.headRow}>
          <SectionHeader section={section} />
          <CtaButton section={section} className="pv-btn pv-btn--ghost pv-btn--sm" />
        </div>
      </div>
      <div className={styles.rail}>
        {products.map((p, i) => (
          <div key={p.id} className={styles.railItem}><ProductCard product={p} index={i} shared={false} /></div>
        ))}
      </div>
    </SectionShell>
  );
}

function CategoryTiles({ tiles, pick }) {
  const fx = useFx();
  const shape = useShapeStyle(fx.shape);
  return (
    <div className={styles.catGrid}>
      {tiles.map((c, i) => (
        <Reveal key={c.slug} delay={(i % 4) * 0.06} hover>
          <button type="button" className={styles.catTile} onClick={() => pick(c.slug)}>
            {c.image ? <img src={c.image} alt="" loading="lazy" className={styles.catImg} style={shape} /> : (
              <span className={styles.catIcon} style={shape}><Icon name={c.icon} size={30} /></span>
            )}
            <span className={styles.catText}>
              <span className={styles.catName}>{c.name}</span>
              {c.description && <span className={styles.catDesc}>{c.description}</span>}
            </span>
            <ArrowRight size={18} strokeWidth={1.5} className={styles.catArrow} aria-hidden="true" />
          </button>
        </Reveal>
      ))}
    </div>
  );
}

export function CategoryGrid({ section }) {
  const { data } = useSite();
  const [, setParams] = useSearchParams();
  const { scrollTo } = useSmoothScroll();
  // Show top-level categories' children if any, otherwise the top-level ones.
  const tops = data?.categories || [];
  const tiles = tops.flatMap((c) => (c.children?.length ? c.children : [c])).slice(0, 8);
  const pick = (slug) => {
    setParams((prev) => { const n = new URLSearchParams(prev); n.set('category', slug); return n; }, { preventScrollReset: true });
    setTimeout(() => scrollTo('#catalog'), 50);
  };
  return (
    <SectionShell section={section}>
      <div className="pv-container">
        <SectionHeader section={section} />
        <CategoryTiles tiles={tiles} pick={pick} />
      </div>
    </SectionShell>
  );
}

export function FreeFromStrip({ section }) {
  const { data } = useSite();
  const custom = Array.isArray(section.items) ? section.items : [];
  const items = custom.length ? custom.map((x) => ({ name: x.name || x.label, icon: x.icon })) : data?.badges || [];
  if (!items.length) return null;
  const loop = [...items, ...items]; // duplicated for a seamless marquee
  return (
    <SectionShell section={section} tight>
      {section.title && <p className={`t-caption ${styles.marqueeTitle}`}>{section.title}</p>}
      <div className={styles.marquee} aria-label={items.map((i) => i.name).join(', ')}>
        <div className={styles.marqueeTrack} aria-hidden="true">
          {loop.map((b, i) => (
            <span key={i} className={styles.marqueeItem}>
              <Icon name={b.icon || 'sparkle'} size={18} /> {b.name}
            </span>
          ))}
        </div>
      </div>
    </SectionShell>
  );
}

const SEGMENT_BUYER = { retailers: 'retailer', chemists: 'chemist', hotels: 'hotel', 'salons & spas': 'salon', salons: 'salon', 'corporate gifting': 'corporate', distributors: 'distributor' };

export function ForBusiness({ section }) {
  const { whatsapp, openEnquiry, setTier } = useSite();
  const items = Array.isArray(section.items) ? section.items : [];
  return (
    <SectionShell section={section}>
      <div className="pv-container">
        <div className={styles.headRow}>
          <SectionHeader section={section} />
        </div>
        <div className={styles.segments}>
          {items.map((s, i) => {
            const buyerType = SEGMENT_BUYER[String(s.title).toLowerCase()] || 'retailer';
            return (
              <Reveal key={i} delay={i * 0.06} hover>
                <button type="button" className={styles.segment} onClick={() => openEnquiry({ source: 'b2b', buyerType, tier: 'wholesale' })}>
                  <span className={styles.segIcon}><Icon name={s.icon} size={22} /></span>
                  <span className={styles.segTitle}>{s.title}</span>
                  <span className={styles.segText}>{s.text}</span>
                  <span className={styles.segLink}>Get a quote <ArrowRight size={14} strokeWidth={1.5} /></span>
                </button>
              </Reveal>
            );
          })}
        </div>
        <Reveal className={styles.bizCtas}>
          <button type="button" className="pv-btn pv-btn--whatsapp" onClick={() => whatsapp({ buyerType: 'retailer', note: 'Please share wholesale pricing & MOQs.' })}>
            <WhatsAppIcon size={18} /> {section.cta_text || 'Bulk enquiry on WhatsApp'}
          </button>
          {!STATIC_SITE && (
            <button type="button" className="pv-btn pv-btn--ghost" onClick={() => { setTier('wholesale'); document.querySelector('#catalog')?.scrollIntoView({ behavior: 'smooth' }); }}>
              See wholesale prices
            </button>
          )}
        </Reveal>
      </div>
    </SectionShell>
  );
}
