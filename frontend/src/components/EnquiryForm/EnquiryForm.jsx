// Enquiry / B2B form (opens from product pages, the For Business section and the footer).
// Saves a lead in the admin. Includes a hidden "honeypot" field that only bots fill in.
import { AnimatePresence, motion } from 'framer-motion';
import { CheckCircle2, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import Modal from 'react-bootstrap/Modal';
import { sendInquiry } from '../../api/client';
import { useSite } from '../../context/SiteContext';
import { useSmoothScroll } from '../../hooks/useSmoothScroll';
import { formatNumber } from '../../utils/format';
import { WhatsAppIcon } from '../ui/BrandIcons';
import styles from './EnquiryForm.module.css';

const BUYER_TYPES = [
  ['shopper', 'Shopper'], ['retailer', 'Retailer'], ['chemist', 'Chemist / Pharmacy'], ['hotel', 'Hotel'],
  ['salon', 'Salon / Spa'], ['corporate', 'Corporate Gifting'], ['distributor', 'Distributor'],
];

const empty = { name: '', phone: '', email: '', business_name: '', city: '', message: '', quantity: '', website: '' };

export default function EnquiryForm() {
  const { enquiry, closeEnquiry, whatsapp } = useSite();
  const lenis = useSmoothScroll();
  const [form, setForm] = useState(empty);
  const [buyerType, setBuyerType] = useState('shopper');
  const [status, setStatus] = useState({ state: 'idle', error: '' });
  const open = Boolean(enquiry);
  const product = enquiry?.product;

  useEffect(() => {
    if (!open) return;
    lenis.stop();
    setStatus({ state: 'idle', error: '' });
    setBuyerType(enquiry.buyerType || (enquiry.tier === 'wholesale' ? 'retailer' : 'shopper'));
    setForm({ ...empty, quantity: enquiry.quantity ? String(enquiry.quantity) : '' });
    return () => lenis.start(); // eslint-disable-line consistent-return
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const isBusiness = buyerType !== 'shopper';

  async function submit(e) {
    e.preventDefault();
    if (!form.phone && !form.email) {
      setStatus({ state: 'error', error: 'Please add a phone number or email so we can reply.' });
      return;
    }
    setStatus({ state: 'sending', error: '' });
    try {
      await sendInquiry({
        ...form,
        email: form.email || null,
        quantity: form.quantity ? Number(form.quantity) : null,
        buyer_type: buyerType,
        product: product?.slug,
        variant_id: enquiry?.variant?.id,
        package_id: enquiry?.pack?.id,
        tier: enquiry?.tier || (isBusiness ? 'wholesale' : 'retail'),
        source: enquiry?.source || (isBusiness ? 'b2b' : 'contact'),
        page_url: window.location.href,
      });
      setStatus({ state: 'done', error: '' });
    } catch (err) {
      setStatus({ state: 'error', error: err.message });
    }
  }

  return (
    <Modal show={open} onHide={closeEnquiry} animation={false} fullscreen backdrop={false} dialogClassName={styles.dialog}
      contentClassName={styles.content} aria-labelledby="enquiry-title">
      <motion.div className={styles.scrim} onClick={closeEnquiry} initial={{ opacity: 0 }} animate={{ opacity: 1 }} aria-hidden="true" />
      <motion.div className={styles.card} initial={{ opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }} transition={{ type: 'spring', stiffness: 120, damping: 20 }}
        data-lenis-prevent>
        <button type="button" className={`pv-icon-btn ${styles.close}`} onClick={closeEnquiry} aria-label="Close form"><X size={18} strokeWidth={1.5} /></button>
        <AnimatePresence mode="wait">
          {status.state === 'done' ? (
            <motion.div key="done" className={styles.done} initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }}>
              <CheckCircle2 size={48} strokeWidth={1.25} className={styles.doneIcon} />
              <h2 className="t-h2">Thank you{form.name ? `, ${form.name.split(' ')[0]}` : ''}.</h2>
              <p className="t-muted">We've received your enquiry and will reply within one working day.</p>
              <button type="button" className="pv-btn pv-btn--whatsapp" onClick={() => whatsapp({ product, buyerType, quantity: form.quantity ? Number(form.quantity) : undefined, city: form.city })}>
                <WhatsAppIcon size={18} /> Need it faster? WhatsApp us
              </button>
            </motion.div>
          ) : (
            <motion.form key="form" onSubmit={submit} className={styles.form} noValidate>
              <p className="t-caption">{isBusiness ? 'Business enquiry' : 'Enquiry'}</p>
              <h2 id="enquiry-title" className="t-h2">{product ? product.title : isBusiness ? 'Bulk & wholesale pricing' : 'How can we help?'}</h2>
              {enquiry?.quantity && product && <p className="t-muted">{formatNumber(enquiry.quantity)} pcs{enquiry.pack ? ` · ${enquiry.pack.name}` : ''}</p>}

              <div className={styles.types} role="radiogroup" aria-label="I am a">
                {BUYER_TYPES.map(([v, l]) => (
                  <button key={v} type="button" role="radio" aria-checked={buyerType === v} className={`${styles.type} ${buyerType === v ? styles.typeOn : ''}`} onClick={() => setBuyerType(v)}>
                    {l}
                  </button>
                ))}
              </div>

              <div className={styles.fields}>
                <div className="pv-field"><label htmlFor="eq-name">Your name</label><input id="eq-name" className="pv-input" value={form.name} onChange={set('name')} autoComplete="name" /></div>
                <div className="pv-field"><label htmlFor="eq-phone">Mobile / WhatsApp</label><input id="eq-phone" className="pv-input" value={form.phone} onChange={set('phone')} inputMode="tel" autoComplete="tel" placeholder="98765 43210" /></div>
                <div className="pv-field"><label htmlFor="eq-email">Email (optional)</label><input id="eq-email" type="email" className="pv-input" value={form.email} onChange={set('email')} autoComplete="email" /></div>
                <div className="pv-field"><label htmlFor="eq-city">City</label><input id="eq-city" className="pv-input" value={form.city} onChange={set('city')} autoComplete="address-level2" /></div>
                {isBusiness && (
                  <>
                    <div className="pv-field"><label htmlFor="eq-biz">Business name</label><input id="eq-biz" className="pv-input" value={form.business_name} onChange={set('business_name')} autoComplete="organization" /></div>
                    <div className="pv-field"><label htmlFor="eq-qty">Approx. quantity (pcs)</label><input id="eq-qty" className="pv-input" value={form.quantity} onChange={set('quantity')} inputMode="numeric" /></div>
                  </>
                )}
                <div className={`pv-field ${styles.full}`}><label htmlFor="eq-msg">Message</label><textarea id="eq-msg" className="pv-input" value={form.message} onChange={set('message')} rows={3} placeholder={isBusiness ? 'Private label, delivery city, timelines…' : 'Tell us what you need'} /></div>
                {/* Honeypot: hidden from people, tempting for bots */}
                <div className={styles.hp} aria-hidden="true"><label htmlFor="eq-web">Website</label><input id="eq-web" tabIndex={-1} autoComplete="off" value={form.website} onChange={set('website')} /></div>
              </div>

              {status.error && <p className={styles.error} role="alert">{status.error}</p>}
              <button type="submit" className="pv-btn pv-btn--block" disabled={status.state === 'sending'}>
                {status.state === 'sending' ? 'Sending…' : 'Send enquiry'}
              </button>
              <p className={styles.fine}>We'll only use your details to reply to this enquiry.</p>
            </motion.form>
          )}
        </AnimatePresence>
      </motion.div>
    </Modal>
  );
}
