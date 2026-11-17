// Retail / Wholesale switch. The sliding pill uses a shared layout animation;
// changing it cross-fades every price on the site and is remembered on this device.
import { motion } from 'framer-motion';
import { useSite } from '../../context/SiteContext';
import { springs } from '../../theme/motion';
import styles from './Header.module.css';

const OPTIONS = [
  { value: 'retail', label: 'Retail' },
  { value: 'wholesale', label: 'Wholesale' },
];

export default function TierToggle({ compact = false, id = 'tier' }) {
  const { tier, setTier } = useSite();
  return (
    <div className={`${styles.tier} ${compact ? styles.tierCompact : ''}`} role="radiogroup" aria-label="Show prices for">
      {OPTIONS.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={tier === o.value}
          className={`${styles.tierBtn} ${tier === o.value ? styles.tierActive : ''}`}
          onClick={() => setTier(o.value)}
        >
          {tier === o.value && <motion.span layoutId={`${id}-pill`} className={styles.tierPill} transition={springs.snappy} />}
          <span className={styles.tierLabel}>{compact && o.value === 'wholesale' ? 'Bulk' : o.label}</span>
        </button>
      ))}
    </div>
  );
}
