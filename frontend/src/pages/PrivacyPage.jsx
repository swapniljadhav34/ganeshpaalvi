// /privacy — the owner's privacy policy (edited in Brand & Contact), with a sensible default.
import { Helmet } from 'react-helmet-async';
import { useSite } from '../context/SiteContext';

const DEFAULT = (name, email) => `${name} respects your privacy.

What we collect: when you send an enquiry or tap WhatsApp, we keep the details you give us (name, phone, email, city, business and your message) and the product you asked about.

Why: only to reply to your enquiry, prepare quotes and process orders. We never sell your details or use them for unrelated marketing.

Website statistics: we count page views without cookies and without storing your IP address, so we can't identify you.

How long: enquiry details are kept for as long as needed to serve you and meet tax/accounting rules, then deleted.

Your choices: you can ask us to show, correct or delete your details at any time${email ? ` by writing to ${email}` : ''}.`;

export default function PrivacyPage() {
  const { brand } = useSite();
  const name = brand?.name || 'This shop';
  const text = brand?.privacy_policy || DEFAULT(name, brand?.email);
  return (
    <main className="pv-container" style={{ position: 'relative', zIndex: 1, maxWidth: 760, paddingBlock: '120px 96px' }}>
      <Helmet><title>{`Privacy policy · ${name}`}</title><link rel="canonical" href={`${brand?.site_url || ''}/privacy`} /></Helmet>
      <p className="t-caption">Privacy</p>
      <h1 className="t-h1" style={{ margin: '8px 0 32px' }}>Privacy policy</h1>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {text.split(/\n\s*\n/).map((para, i) => <p key={i} className="t-measure">{para}</p>)}
      </div>
    </main>
  );
}
