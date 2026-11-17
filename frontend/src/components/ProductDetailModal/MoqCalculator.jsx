// Pack picker + quantity stepper with animated totals.
// Wholesale enforces the minimum order (MOQ) and shows savings vs retail.
import { Minus, Plus } from 'lucide-react';
import { useEffect } from 'react';
import { formatINR, formatNumber } from '../../utils/format';
import AnimatedNumber from '../ui/AnimatedNumber';
import styles from './ProductDetailModal.module.css';

/** Work out price per pack/unit for the chosen tier, with sensible fallbacks. */
export function quote({ product, pack, qty, tier, unitRetail }) {
  const units = (pack?.units || 1) * qty;
  const retailPack = pack ? pack.retail_price ?? unitRetail * pack.units : unitRetail;
  const wholesaleUnit = product.wholesale_price;
  const wholesalePack = pack ? pack.wholesale_price ?? (wholesaleUnit != null ? wholesaleUnit * pack.units : null) : wholesaleUnit;
  const useWholesale = tier === 'wholesale' && wholesalePack != null;
  const packPrice = useWholesale ? wholesalePack : retailPack;
  const total = packPrice * qty;
  const retailTotal = retailPack * qty;
  const mrpTotal = (product.mrp || unitRetail) * units;
  const minUnits = useWholesale ? product.moq || 1 : 1;
  const minPacks = useWholesale ? Math.max(pack?.moq || 0, Math.ceil(minUnits / (pack?.units || 1))) : 1;
  return {
    units, packPrice, total, unitPrice: total / units, useWholesale, minPacks, minUnits,
    saveVsRetail: Math.max(0, retailTotal - total), saveVsMrp: Math.max(0, mrpTotal - total),
  };
}

export default function MoqCalculator({ product, packs, pack, setPack, qty, setQty, tier, unitRetail }) {
  const q = quote({ product, pack, qty, tier, unitRetail });

  // Snap quantity up to the minimum when switching to wholesale or a new pack.
  useEffect(() => {
    if (qty < q.minPacks) setQty(q.minPacks);
  }, [q.minPacks]); // eslint-disable-line react-hooks/exhaustive-deps

  const fmt = (v) => formatINR(v);
  return (
    <div className={styles.calc}>
      {packs.length > 0 && (
        <div className={styles.packs} role="radiogroup" aria-label="Pack size">
          {[{ id: null, name: 'Single', units: 1 }, ...packs.filter((p) => !(p.units === 1 && /single/i.test(p.name)))].map((p) => {
            const on = (pack?.id ?? null) === p.id;
            return (
              <button key={p.id ?? 'single'} type="button" role="radio" aria-checked={on} className={`${styles.pack} ${on ? styles.packOn : ''}`}
                onClick={() => setPack(p.id ? p : null)}>
                <span className={styles.packName}>{p.name}</span>
                <span className={styles.packUnits}>{p.units} pc{p.units > 1 ? 's' : ''}</span>
              </button>
            );
          })}
        </div>
      )}

      <div className={styles.calcRow}>
        <div className={styles.stepper} aria-label="Quantity">
          <button type="button" onClick={() => setQty(Math.max(q.minPacks, qty - 1))} disabled={qty <= q.minPacks} aria-label="Decrease quantity">
            <Minus size={16} strokeWidth={1.5} />
          </button>
          <input type="number" inputMode="numeric" min={q.minPacks} value={qty} aria-label={pack ? 'Number of packs' : 'Number of pieces'}
            onChange={(e) => setQty(Math.max(q.minPacks, Math.min(100000, parseInt(e.target.value, 10) || q.minPacks)))} />
          <button type="button" onClick={() => setQty(qty + 1)} aria-label="Increase quantity"><Plus size={16} strokeWidth={1.5} /></button>
        </div>
        <div className={styles.total}>
          <span className={styles.totalLabel}>{formatNumber(q.units)} pcs · {q.useWholesale ? 'Wholesale' : 'Retail'}</span>
          <span className={styles.totalValue}><AnimatedNumber value={q.total} format={fmt} /></span>
          <span className={styles.totalSub}><AnimatedNumber value={q.unitPrice} format={fmt} /> per piece</span>
        </div>
      </div>

      {(q.saveVsMrp > 0 || q.saveVsRetail > 0) && (
        <p className={styles.savings}>
          You save <strong><AnimatedNumber value={q.useWholesale ? q.saveVsRetail : q.saveVsMrp} format={fmt} /></strong>
          {q.useWholesale ? ' vs retail' : ' vs MRP'}
        </p>
      )}
      {q.useWholesale && q.minUnits > 1 && (
        <p className={styles.moqNote}>Minimum wholesale order: {formatNumber(q.minUnits)} pieces{pack?.moq ? ` (${pack.moq} packs)` : ''}.</p>
      )}
    </div>
  );
}
