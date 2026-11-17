// Price block: selling price, struck-through MRP when lower, cross-fades when Retail/Wholesale changes.
import { AnimatePresence, motion } from 'framer-motion';
import { useSite } from '../../context/SiteContext';
import { formatINR, tierPrice } from '../../utils/format';
import styles from './Price.module.css';

export default function Price({ product, size = 'md', showNote = false, tierOverride, priceOverride }) {
  const { tier: siteTier } = useSite();
  const tier = tierOverride || siteTier;
  const price = priceOverride ?? tierPrice(product, tier);
  const isWholesale = tier === 'wholesale' && product.wholesale_price != null;
  const showMrp = product.mrp != null && price < product.mrp;

  return (
    <div className={`${styles.price} ${styles[size]}`}>
      <AnimatePresence mode="popLayout" initial={false}>
        <motion.span
          key={`${tier}-${price}`}
          className={styles.amount}
          initial={{ opacity: 0, y: 6, filter: 'blur(4px)' }}
          animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
          exit={{ opacity: 0, y: -6, filter: 'blur(4px)' }}
          transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
        >
          {formatINR(price)}
          {isWholesale && <span className={styles.per}>/pc</span>}
        </motion.span>
      </AnimatePresence>
      {showMrp && (
        <s className={styles.mrp}>
          <span className="pv-sr">MRP </span>
          {formatINR(product.mrp)}
        </s>
      )}
      {isWholesale && product.moq > 1 && <span className={styles.moq}>MOQ {product.moq}</span>}
      {showNote && <span className={styles.note}>MRP incl. of all taxes</span>}
    </div>
  );
}
