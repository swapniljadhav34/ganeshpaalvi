// WhatsApp-first conversion: builds pre-filled messages and logs each tap as a lead.
import { formatINR, formatNumber } from './format';
import { sendInquiry } from '../api/client';

const BUYER_LABELS = {
  shopper: 'Shopper',
  retailer: 'Retailer',
  chemist: 'Chemist / Pharmacy',
  hotel: 'Hotel',
  salon: 'Salon / Spa',
  corporate: 'Corporate Gifting',
  distributor: 'Distributor',
};

/**
 * Paalvi WhatsApp message format (kept short so it reads well in the chat):
 *
 *   Hi Paalvi 👋 I'd like to enquire about:
 *   🪥 Bamboo Charcoal Toothbrush
 *   SKU: PAL-001 · Bristle: Soft · Colour: Mint
 *   Pack: Carton of 144 × 2
 *   Price seen: ₹72/pc (Wholesale) · MOQ 144
 *   Est. total: ₹20,736
 *   I'm a: Hotel · Pune
 *   🔗 https://paalvi.in/p/bamboo-charcoal-toothbrush
 */
export function buildWhatsAppMessage({
  product,
  variants = [],
  pack,
  quantity,
  tier = 'retail',
  unitPrice,
  total,
  buyerType,
  city,
  note,
  siteUrl = typeof window !== 'undefined' ? window.location.origin : 'https://paalvi.in',
} = {}) {
  const lines = [];
  if (!product) {
    lines.push(
      tier === 'wholesale' || (buyerType && buyerType !== 'shopper')
        ? "Hi Paalvi 👋 I'd like bulk / wholesale pricing."
        : "Hi Paalvi 👋 I'd love some help choosing my essentials.",
    );
  } else {
    lines.push("Hi Paalvi 👋 I'd like to enquire about:");
    lines.push(`🪥 ${product.title}`);
    const meta = [`SKU: ${product.sku}`, ...variants.filter(Boolean).map((v) => `${v.type_label || v.type}: ${v.value}`)];
    lines.push(meta.join(' · '));
    if (pack || quantity) {
      lines.push(`Pack: ${pack ? pack.name : 'Single'}${quantity ? ` × ${formatNumber(quantity)}` : ''}`);
    }
    if (unitPrice != null) {
      const moq = tier === 'wholesale' && product.moq > 1 ? ` · MOQ ${formatNumber(product.moq)}` : '';
      lines.push(`Price seen: ${formatINR(unitPrice)}/pc (${tier === 'wholesale' ? 'Wholesale' : 'Retail'})${moq}`);
    }
    if (total) lines.push(`Est. total: ${formatINR(total)}`);
  }
  if (buyerType && buyerType !== 'shopper') lines.push(`I'm a: ${BUYER_LABELS[buyerType] || buyerType}${city ? ` · ${city}` : ''}`);
  if (note) lines.push(note);
  if (product?.slug) lines.push(`🔗 ${siteUrl}/p/${product.slug}`);
  return lines.join('\n');
}

export function whatsappUrl(number, message) {
  const digits = String(number || '').replace(/\D/g, '');
  return `https://wa.me/${digits}?text=${encodeURIComponent(message)}`;
}

/** Open WhatsApp and quietly log the tap as a lead in the admin (never blocks the user). */
export function openWhatsApp(number, message, lead = {}) {
  const url = whatsappUrl(number, message);
  sendInquiry({ source: 'whatsapp', message, page_url: window.location.href, ...lead }).catch(() => {});
  window.open(url, '_blank', 'noopener');
}
