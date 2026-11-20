// Care education sections: Ingredient Spotlight, Routine Builder (Morning/Night), Bristle & Product Guide.
import { AnimatePresence, motion } from 'framer-motion';
import { ArrowRight, Moon, Sun } from 'lucide-react';
import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useFx, useShapeStyle } from '../../../fx/FxContext';
import HoverFx from '../../../fx/HoverFx';
import ShapedMedia from '../../../fx/ShapedMedia';
import { springs } from '../../../theme/motion';
import { STATIC_SITE } from '../../../staticSite';
import { formatINR } from '../../../utils/format';
import Icon from '../../ui/Icon';
import SectionShell, { SectionHeader } from '../SectionShell';
import styles from '../Sections.module.css';
import { useCalm } from '../../../hooks/useCalm';

function SpotMedia({ current, index, section }) {
  const fx = useFx();
  const shapeCss = useShapeStyle(fx.shape);
  const media = section.media || [];
  const item = current.image ? { type: 'image', src: current.image, alt: current.name } : media.length ? media[index % media.length] : null;
  if (item) return <ShapedMedia media={[item]} shape={fx.shape} motion={fx.motion} hover={fx.hover} speed={fx.speed} />;
  return (
    <HoverFx kind={fx.hover} className="pv-fill">
      <div className="pv-shaped" style={shapeCss}>
        <div className={styles.spotFallback}><Icon name={current.icon || 'leaf'} size={96} /></div>
      </div>
    </HoverFx>
  );
}

function useOpenProduct() {
  const navigate = useNavigate();
  const location = useLocation();
  return (p) => p && navigate(`/p/${p.slug}`, { state: { background: location, preview: p } });
}

export function IngredientSpotlight({ section }) {
  const items = Array.isArray(section.items) ? section.items : [];
  const [active, setActive] = useState(0);
  const reduce = useCalm();
  if (!items.length) return null;
  const current = items[active] || items[0];
  return (
    <SectionShell section={section}>
      <div className={`pv-container ${styles.spot}`}>
        <div>
          <SectionHeader section={section} />
          <div className={styles.spotList} role="tablist" aria-label="Ingredients">
            {items.map((ing, i) => (
              <button key={ing.name} type="button" role="tab" aria-selected={i === active}
                className={`${styles.spotItem} ${i === active ? styles.spotOn : ''}`} onClick={() => setActive(i)} onMouseEnter={() => setActive(i)}>
                <span className={styles.spotNum}>{String(i + 1).padStart(2, '0')}</span>
                <span className={styles.spotName}>{ing.name}</span>
                {i === active && <motion.span layoutId={`spot-${section.id}`} className={styles.spotBar} transition={springs.gentle} />}
              </button>
            ))}
          </div>
        </div>
        <div className={styles.spotVisual}>
          <AnimatePresence mode="wait">
            <motion.div key={current.name} className={styles.spotImage}
              initial={{ opacity: 0, scale: 1.04 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.98 }}
              transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}>
              <SpotMedia current={current} index={active} section={section} />
            </motion.div>
          </AnimatePresence>
          {/* Floating benefit chips */}
          <div className={styles.chipCloud} aria-live="polite">
            {[current.benefit, ...(items.filter((x) => x !== current).slice(0, 2).map((x) => x.name))].filter(Boolean).map((t, i) => (
              <motion.span key={`${current.name}-${t}`} className={`pv-glass ${styles.floatChip} ${styles[`fc${i}`]}`}
                initial={{ opacity: 0, y: 12 }} animate={reduce ? { opacity: 1 } : { opacity: 1, y: [0, -6, 0] }}
                transition={reduce ? undefined : { opacity: { delay: 0.2 + i * 0.1 }, y: { duration: 4 + i, repeat: Infinity, ease: 'easeInOut' } }}>
                {i === 0 ? <><Icon name={current.icon || 'sparkle'} size={14} /> {t}</> : t}
              </motion.span>
            ))}
          </div>
        </div>
      </div>
    </SectionShell>
  );
}

export function RoutineBuilder({ section }) {
  const routine = section.items && !Array.isArray(section.items) ? section.items : { morning: [], night: [] };
  const tabs = [
    { key: 'morning', label: 'Morning', icon: Sun },
    { key: 'night', label: 'Night', icon: Moon },
  ].filter((t) => routine[t.key]?.length);
  const [tab, setTab] = useState(tabs[0]?.key);
  const openProduct = useOpenProduct();
  const fx = useFx();
  if (!tabs.length) return null;
  const steps = routine[tab] || [];
  const linked = section.linked_products || {};

  return (
    <SectionShell section={section}>
      <div className="pv-container">
        <div className={styles.headRow}>
          <SectionHeader section={section} />
          <div className={styles.tabs} role="tablist" aria-label="Routine time">
            {tabs.map(({ key, label, icon: I }) => (
              <button key={key} type="button" role="tab" aria-selected={tab === key} className={`${styles.tab} ${tab === key ? styles.tabOn : ''}`} onClick={() => setTab(key)}>
                {tab === key && <motion.span layoutId={`routine-${section.id}`} className={styles.tabPill} transition={springs.snappy} />}
                <span className={styles.tabLabel}><I size={16} strokeWidth={1.5} /> {label}</span>
              </button>
            ))}
          </div>
        </div>
        <AnimatePresence mode="wait">
          <motion.ol key={tab} className={styles.steps} initial="hidden" animate="show" exit="hidden"
            variants={{ hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.08 } } }}>
            {steps.map((s, i) => {
              const p = linked[s.product];
              return (
                <motion.li key={`${tab}-${i}`} variants={{ hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }}>
                  <HoverFx kind={fx.hover} className={`${styles.step} pv-fill`}>
                  <span className={styles.stepNum}>{i + 1}</span>
                  <div className={styles.stepBody}>
                    <h3 className="t-h3">{s.title}</h3>
                    {s.text && <p className="t-muted">{s.text}</p>}
                  </div>
                  {p && (
                    <button type="button" className={styles.stepProduct} onClick={() => openProduct(p)}>
                      {p.images[0]?.thumb && <img src={p.images[0].thumb} alt="" loading="lazy" />}
                      <span>
                        <span className={styles.stepPName}>{p.title}</span>
                        <span className={styles.stepPPrice}>{STATIC_SITE ? 'View' : formatINR(p.retail_price)} <ArrowRight size={12} strokeWidth={1.5} /></span>
                      </span>
                    </button>
                  )}
                  {i < steps.length - 1 && <span className={styles.stepLine} aria-hidden="true" />}
                  </HoverFx>
                </motion.li>
              );
            })}
          </motion.ol>
        </AnimatePresence>
      </div>
    </SectionShell>
  );
}

export function ProductGuide({ section }) {
  const rows = Array.isArray(section.items) ? section.items : [];
  const [active, setActive] = useState(Math.min(1, rows.length - 1));
  const openProduct = useOpenProduct();
  const fx = useFx();
  if (!rows.length) return null;
  const linked = section.linked_products || {};
  const max = Math.max(...rows.map((r) => r.level || 1), 3);
  const sel = rows[active];

  return (
    <SectionShell section={section}>
      <div className="pv-container">
        <SectionHeader section={section} />
        <div className={styles.guide}>
          <div className={styles.guideOptions} role="radiogroup" aria-label="Compare">
            {rows.map((r, i) => (
              <HoverFx key={r.name} kind={fx.hover} className="pv-fill">
                <button type="button" role="radio" aria-checked={i === active}
                  className={`${styles.guideCard} ${styles.fillCard} ${i === active ? styles.guideOn : ''}`} onClick={() => setActive(i)}>
                  <span className={styles.guideName}>{r.name}</span>
                  <span className={styles.meter} aria-label={`Firmness ${r.level || 1} of ${max}`}>
                    {Array.from({ length: max }, (_, k) => <span key={k} className={k < (r.level || 1) ? styles.meterOn : ''} />)}
                  </span>
                  <span className={styles.guideBest}>Best for: {r.best_for}</span>
                </button>
              </HoverFx>
            ))}
          </div>
          <AnimatePresence mode="wait">
            <motion.div key={sel.name} className={styles.guideDetail} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}>
              <p className="t-caption">{sel.best_for}</p>
              <h3 className="t-h2">{sel.name}</h3>
              {sel.text && <p className="t-muted">{sel.text}</p>}
              {linked[sel.product] && (
                <button type="button" className="pv-btn pv-btn--sm" onClick={() => openProduct(linked[sel.product])}>
                  Shop {linked[sel.product].title} <ArrowRight size={14} strokeWidth={1.5} />
                </button>
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </SectionShell>
  );
}

