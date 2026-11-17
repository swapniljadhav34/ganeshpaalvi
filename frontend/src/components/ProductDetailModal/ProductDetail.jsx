// Product detail content — used inside the modal AND on the full /p/<slug> page.
import { AnimatePresence, motion } from 'framer-motion';
import { ChevronDown, Mail, MessageSquareText } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Helmet } from 'react-helmet-async';
import { useLocation, useNavigate } from 'react-router-dom';
import { useSite } from '../../context/SiteContext';
import { formatINR, formatQty, STOCK_LABELS, SUITABLE_LABELS } from '../../utils/format';
import { buildWhatsAppMessage } from '../../utils/whatsapp';
import { WhatsAppIcon } from '../ui/BrandIcons';
import Icon from '../ui/Icon';
import Gallery from './Gallery';
import MoqCalculator, { quote } from './MoqCalculator';
import styles from './ProductDetailModal.module.css';

function Accordion({ title, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className={styles.acc}>
      <button type="button" className={styles.accHead} aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <span>{title}</span>
        <motion.span animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.25 }}><ChevronDown size={18} strokeWidth={1.5} /></motion.span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div className={styles.accBody} initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}>
            <div className={styles.accInner}>{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function MiniRow({ title, items, onOpen, label }) {
  if (!items?.length) return null;
  return (
    <section className={styles.row} aria-label={title}>
      <h3 className="t-caption">{title}</h3>
      <div className={styles.rowTrack}>
        {items.map(({ product: p, step }) => (
          <button key={p.slug} type="button" className={styles.mini} onClick={() => onOpen(p)}>
            <span className={styles.miniImg}>{p.images[0]?.thumb && <img src={p.images[0].thumb} alt="" loading="lazy" />}</span>
            {step && <span className={styles.miniStep}>{label?.(step) || step}</span>}
            <span className={styles.miniTitle}>{p.title}</span>
            <span className={styles.miniPrice}>{formatINR(p.retail_price)}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

const STEP_LABELS = { brush: 'Brush', paste: 'Paste', floss: 'Floss', tongue: 'Tongue', rinse: 'Rinse' };

export default function ProductDetail({ product: p, layout = 'modal', headingId }) {
  const { tier, setTier, whatsapp, openEnquiry, brand } = useSite();
  const navigate = useNavigate();
  const location = useLocation();
  const partial = p._partial;

  // Variant selection: one choice per variant type (bristle, flavour, colour…)
  const groups = useMemo(() => {
    const g = {};
    (p.variants || []).forEach((v) => { (g[v.type] ||= { label: v.type_label, items: [] }).items.push(v); });
    return g;
  }, [p.variants]);
  const [picked, setPicked] = useState({});
  const selected = Object.keys(groups).map((t) => groups[t].items.find((v) => v.id === picked[t]) || groups[t].items[0]).filter(Boolean);
  const [pack, setPack] = useState(null);
  const [qty, setQty] = useState(1);

  const variantImage = selected.find((v) => v.image)?.image;
  const images = useMemo(() => {
    const base = p.images || [];
    return variantImage ? [{ thumb: variantImage, medium: variantImage, full: variantImage, alt: p.title }, ...base] : base;
  }, [p.images, variantImage, p.title]);

  const unitRetail = selected.find((v) => v.price_override != null)?.price_override ?? p.retail_price;
  const q = quote({ product: p, pack, qty, tier, unitRetail });
  const hasWholesale = p.wholesale_price != null;
  const savePct = hasWholesale ? Math.round((1 - p.wholesale_price / unitRetail) * 100) : 0;

  const openProduct = (prod) => navigate(`/p/${prod.slug}`, { state: { background: location.state?.background || location, preview: prod }, replace: layout === 'modal' });

  const contact = {
    product: p, variants: selected, pack, quantity: qty, unitPrice: q.unitPrice, total: q.total,
    buyerType: tier === 'wholesale' ? 'retailer' : 'shopper',
  };
  const emailHref = brand?.email
    ? `mailto:${brand.email}?subject=${encodeURIComponent(`Enquiry: ${p.title}`)}&body=${encodeURIComponent(buildWhatsAppMessage({ ...contact, tier, siteUrl: brand.site_url }))}`
    : undefined;

  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'Product',
    name: p.title,
    description: p.seo_description || p.subtitle,
    sku: p.sku,
    gtin13: p.ean || undefined,
    image: (p.images || []).map((i) => i.full || i.medium).filter(Boolean),
    brand: { '@type': 'Brand', name: brand?.name || 'Paalvi' },
    offers: {
      '@type': 'Offer', priceCurrency: 'INR', price: p.retail_price, url: p.url,
      availability: p.stock_status === 'out_of_stock' ? 'https://schema.org/OutOfStock' : 'https://schema.org/InStock',
    },
  };

  return (
    <div className={`${styles.detail} ${layout === 'page' ? styles.detailPage : ''}`}>
      {!partial && (
        <Helmet>
          <title>{`${p.seo_title || p.title} — ${formatINR(p.retail_price)} | ${brand?.name || 'Paalvi'}`}</title>
          <meta name="description" content={p.seo_description || p.subtitle} />
          <meta property="og:title" content={p.seo_title || p.title} />
          <meta property="og:description" content={p.seo_description || p.subtitle} />
          {p.images?.[0] && <meta property="og:image" content={p.images[0].medium} />}
          <link rel="canonical" href={p.url} />
          <script type="application/ld+json">{JSON.stringify(jsonLd)}</script>
        </Helmet>
      )}

      <div className={styles.grid}>
        <div className={styles.left}>
          <Gallery slug={p.slug} images={images} video={p.demo_video} title={p.title} />
        </div>

        <div className={styles.right}>
          {p.category && <p className="t-caption">{p.category.name}</p>}
          <h1 id={headingId} className={`t-h1 ${styles.title}`}>{p.title}</h1>
          {p.subtitle && <p className={styles.subtitle}>{p.subtitle}</p>}

          {p.badges?.length > 0 && (
            <ul className={styles.badgeRow} aria-label="Product qualities">
              {p.badges.map((b) => <li key={b.slug} className="pv-chip pv-chip--primary" title={b.description}>{b.name}</li>)}
            </ul>
          )}

          {/* Retail vs Wholesale, side by side */}
          <div className={styles.tiers}>
            <button type="button" className={`${styles.tierCard} ${tier === 'retail' ? styles.tierOn : ''}`} onClick={() => setTier('retail')} aria-pressed={tier === 'retail'}>
              <span className="t-caption">Retail</span>
              <span className={styles.tierPrice}>{formatINR(unitRetail)}</span>
              {p.mrp > unitRetail ? <span className={styles.tierSub}><s>{formatINR(p.mrp)}</s> · {Math.round((1 - unitRetail / p.mrp) * 100)}% off MRP</span>
                : <span className={styles.tierSub}>MRP {formatINR(p.mrp)}</span>}
            </button>
            {hasWholesale && (
              <button type="button" className={`${styles.tierCard} ${tier === 'wholesale' ? styles.tierOn : ''}`} onClick={() => setTier('wholesale')} aria-pressed={tier === 'wholesale'}>
                <span className="t-caption">Wholesale</span>
                <span className={styles.tierPrice}>{formatINR(p.wholesale_price)}<small>/pc</small></span>
                <span className={styles.tierSub}>Save {formatINR(unitRetail - p.wholesale_price)} ({savePct}%) · MOQ {p.moq}</span>
              </button>
            )}
          </div>
          <p className={styles.taxNote}>MRP incl. of all taxes · {STOCK_LABELS[p.stock_status]}{p.net_quantity ? ` · ${formatQty(p.net_quantity, p.unit)}` : ''}</p>

          {/* Variant selectors */}
          {Object.entries(groups).map(([type, g]) => (
            <div key={type} className={styles.variantGroup}>
              <p className={styles.variantLabel}>{g.label}: <strong>{selected.find((v) => v.type === type)?.value}</strong></p>
              <div className={styles.variantOpts} role="radiogroup" aria-label={g.label}>
                {g.items.map((v) => {
                  const on = selected.some((s) => s.id === v.id);
                  return (
                    <button key={v.id} type="button" role="radio" aria-checked={on} disabled={v.stock_status === 'out_of_stock'}
                      className={`${v.hex ? styles.swatchOpt : styles.variantOpt} ${on ? styles.variantOn : ''}`}
                      style={v.hex ? { '--sw': v.hex } : undefined} onClick={() => setPicked((s) => ({ ...s, [type]: v.id }))}
                      aria-label={v.hex ? v.value : undefined} title={v.value}>
                      {!v.hex && v.value}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}

          {!partial && (
            <MoqCalculator product={p} packs={p.packages?.filter((x) => x.id) || []} pack={pack} setPack={setPack} qty={qty}
              setQty={setQty} tier={tier} unitRetail={unitRetail} />
          )}

          {p.suitable_for?.length > 0 && (
            <p className={styles.suitable}>Suitable for: {p.suitable_for.map((s) => SUITABLE_LABELS[s] || s).join(' · ')}</p>
          )}

          {partial ? (
            <div className={styles.loadingBlock}>
              <div className="pv-skeleton" style={{ height: 56 }} />
              <div className="pv-skeleton" style={{ height: 56 }} />
            </div>
          ) : (
            <div className={styles.accs}>
              {p.key_benefits?.length > 0 && (
                <Accordion title="Benefits" defaultOpen>
                  <ul className={styles.benefits}>{p.key_benefits.map((b) => <li key={b}>{b}</li>)}</ul>
                </Accordion>
              )}
              {p.description && (
                <Accordion title="About this product">
                  {p.description.split(/\n\s*\n/).map((para, i) => <p key={i} className={styles.para}>{para}</p>)}
                </Accordion>
              )}
              {p.how_to_use?.length > 0 && (
                <Accordion title="How to use">
                  <ol className={styles.steps}>{p.how_to_use.map((s, i) => <li key={i}>{s}</li>)}</ol>
                </Accordion>
              )}
              {p.key_ingredients?.length > 0 && (
                <Accordion title="Key ingredients" defaultOpen>
                  <div className={styles.ingredients}>
                    {p.key_ingredients.map((i) => (
                      <div key={i.name} className={styles.ingredient}>
                        <span className={styles.ingIcon}><Icon name={i.icon} size={18} /></span>
                        <span><strong>{i.name}</strong>{i.benefit && <span className="t-muted"> — {i.benefit}</span>}</span>
                      </div>
                    ))}
                  </div>
                </Accordion>
              )}
              {p.ingredients_text && (
                <Accordion title="Full ingredients"><p className={styles.para}>{p.ingredients_text}</p></Accordion>
              )}
              <Accordion title="Product details">
                <dl className={styles.facts}>
                  {p.net_quantity && (<><dt>Net quantity</dt><dd>{formatQty(p.net_quantity, p.unit)}</dd></>)}
                  <dt>MRP</dt><dd>{formatINR(p.mrp)} (incl. of all taxes)</dd>
                  <dt>SKU</dt><dd>{p.sku}</dd>
                  {p.ean && (<><dt>EAN</dt><dd>{p.ean}</dd></>)}
                  <dt>Country of origin</dt><dd>{p.country_of_origin}</dd>
                  {p.shelf_life && (<><dt>Shelf life</dt><dd>{p.shelf_life}</dd></>)}
                  {brand?.manufacturer && (<><dt>Manufacturer</dt><dd>{brand.manufacturer}</dd></>)}
                  {brand?.marketer && (<><dt>Marketed by</dt><dd>{brand.marketer}</dd></>)}
                  {brand?.customer_care && (<><dt>Customer care</dt><dd>{brand.customer_care}</dd></>)}
                </dl>
              </Accordion>
            </div>
          )}

          <MiniRow title="Complete your routine" items={p.routine} onOpen={openProduct} label={(s) => STEP_LABELS[s]} />
          <MiniRow title="You may also like" items={p.related?.map((r) => ({ product: r }))} onOpen={openProduct} />
        </div>
      </div>

      {/* Sticky CTA bar */}
      <div className={`${styles.ctaBar} pv-glass`}>
        <div className={styles.ctaPrice}>
          <span className={styles.ctaTotal}>{formatINR(q.total)}</span>
          <span className={styles.ctaSub}>{q.units} pc{q.units === 1 ? '' : 's'} · {q.useWholesale ? 'wholesale' : 'retail'}</span>
        </div>
        <div className={styles.ctaBtns}>
          {emailHref && (
            <a className="pv-icon-btn" href={emailHref} aria-label="Enquire by email"><Mail size={18} strokeWidth={1.5} /></a>
          )}
          <button type="button" className="pv-icon-btn" aria-label="Send an enquiry"
            onClick={() => openEnquiry({ product: p, variant: selected[0], pack, quantity: q.units, tier, source: tier === 'wholesale' ? 'b2b' : 'email' })}>
            <MessageSquareText size={18} strokeWidth={1.5} />
          </button>
          <button type="button" className="pv-btn pv-btn--whatsapp" onClick={() => whatsapp(contact)}>
            <WhatsAppIcon size={18} /> <span>WhatsApp</span>
          </button>
        </div>
      </div>
    </div>
  );
}
