// Filters: category, badges (free-from…), suitable for, bristle/flavour, price and discount.
// Shown inline on desktop and as a bottom sheet on mobile (see ProductCatalog).
import { Check } from 'lucide-react';
import { STATIC_SITE } from '../../staticSite';
import styles from './ProductCatalog.module.css';

const SORTS = [
  { value: '', label: 'Recommended' },
  { value: 'newest', label: 'Newest' },
  { value: 'bestseller', label: 'Bestsellers' },
  ...(STATIC_SITE ? [] : [
    { value: 'price_asc', label: 'Price: low to high' },
    { value: 'price_desc', label: 'Price: high to low' },
    { value: 'discount', label: 'Biggest discount' },
  ]),
];
const PRICE_BANDS = [
  { label: 'Under ₹100', min: '', max: '100' },
  { label: '₹100 – ₹200', min: '100', max: '200' },
  { label: '₹200 – ₹500', min: '200', max: '500' },
  { label: 'Above ₹500', min: '500', max: '' },
];
const DISCOUNTS = [10, 20, 30];

const list = (v) => (v ? v.split(',').filter(Boolean) : []);
const toggleIn = (csv, value) => {
  const items = list(csv);
  return (items.includes(value) ? items.filter((x) => x !== value) : [...items, value]).join(',');
};

function Group({ title, children }) {
  return (
    <fieldset className={styles.group}>
      <legend className="t-caption">{title}</legend>
      <div className={styles.options}>{children}</div>
    </fieldset>
  );
}

function Option({ active, onClick, children, swatch }) {
  return (
    <button type="button" className={`${styles.option} ${active ? styles.optionOn : ''}`} aria-pressed={active} onClick={onClick}>
      {swatch && <span className={styles.optSwatch} style={{ background: swatch }} />}
      {children}
      {active && <Check size={14} strokeWidth={2} aria-hidden="true" />}
    </button>
  );
}

export default function FilterPanel({ filters, setFilter, setMany, badges = [], options, onReset, activeCount }) {
  return (
    <div className={styles.filterPanel}>
      <Group title="Sort by">
        {SORTS.map((s) => (
          <Option key={s.value} active={(filters.sort || '') === s.value} onClick={() => setFilter('sort', s.value)}>{s.label}</Option>
        ))}
      </Group>

      {badges.length > 0 && (
        <Group title="Free-from & values">
          {badges.map((b) => (
            <Option key={b.slug} active={list(filters.badge).includes(b.slug)} onClick={() => setFilter('badge', toggleIn(filters.badge, b.slug))}>
              {b.name}
            </Option>
          ))}
        </Group>
      )}

      {options?.suitable_for?.length > 0 && (
        <Group title="Suitable for">
          {options.suitable_for.map((s) => (
            <Option key={s.value} active={list(filters.suitable_for).includes(s.value)}
              onClick={() => setFilter('suitable_for', toggleIn(filters.suitable_for, s.value))}>
              {s.label}
            </Option>
          ))}
        </Group>
      )}

      {options?.variants?.filter((v) => v.values.length).map((v) => (
        <Group key={v.type} title={v.label}>
          {v.values.map((value) => {
            const token = `${v.type}:${value}`;
            return (
              <Option key={token} active={list(filters.variant).includes(token)} onClick={() => setFilter('variant', toggleIn(filters.variant, token))}>
                {value}
              </Option>
            );
          })}
        </Group>
      ))}

      {!STATIC_SITE && <>
      <Group title="Price (retail)">
        {PRICE_BANDS.map((b) => {
          const on = (filters.min_price || '') === b.min && (filters.max_price || '') === b.max;
          return (
            <Option key={b.label} active={on} onClick={() => setMany(on ? { min_price: '', max_price: '' } : { min_price: b.min, max_price: b.max })}>
              {b.label}
            </Option>
          );
        })}
      </Group>

      <Group title="Discount">
        {DISCOUNTS.map((d) => (
          <Option key={d} active={String(filters.min_discount) === String(d)}
            onClick={() => setFilter('min_discount', String(filters.min_discount) === String(d) ? '' : String(d))}>
            {d}% off or more
          </Option>
        ))}
      </Group>
      </>}

      {activeCount > 0 && (
        <button type="button" className={`pv-btn pv-btn--ghost pv-btn--sm ${styles.reset}`} onClick={onReset}>
          Clear all filters ({activeCount})
        </button>
      )}
    </div>
  );
}
