// Indian-style formatting helpers.

const inr = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 });
const num = new Intl.NumberFormat('en-IN');

/** ₹1,23,456 — whole rupees, Indian digit grouping. */
export const formatINR = (value) => (value == null || Number.isNaN(Number(value)) ? '—' : inr.format(Math.round(Number(value))));

/** 1,23,456 */
export const formatNumber = (value) => num.format(value ?? 0);

/** "100 g", "250 ml", "10 pcs" */
export const formatQty = (qty, unit) => {
  if (!qty) return '';
  const n = Number(qty);
  const label = unit === 'pcs' && n === 1 ? 'pc' : unit;
  return `${Number.isInteger(n) ? n : n.toFixed(1)} ${label}`;
};

export const STOCK_LABELS = {
  in_stock: 'In stock',
  low: 'Only a few left',
  made_to_order: 'Made to order',
  out_of_stock: 'Out of stock',
};

export const SUITABLE_LABELS = { adults: 'Adults', kids: 'Kids', sensitive: 'Sensitive teeth', braces: 'Braces' };

/** Price shown for a product in the chosen tier (falls back to retail if no wholesale). */
export function tierPrice(product, tier) {
  if (tier === 'wholesale' && product?.wholesale_price != null) return product.wholesale_price;
  return product?.retail_price;
}
