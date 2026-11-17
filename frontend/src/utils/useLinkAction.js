// One place that understands every link the owner can type in the admin:
//   #catalog / #section-12   smooth scroll (from any page)
//   /p/slug                  in-site navigation
//   https://…, mailto:, tel: normal links
//   whatsapp                 WhatsApp chat
//   enquire / enquire:hotel  enquiry form (optionally for a business type)
import { useLocation, useNavigate } from 'react-router-dom';
import { useSite } from '../context/SiteContext';
import { useSmoothScroll } from '../hooks/useSmoothScroll';

const BUYERS = ['shopper', 'retailer', 'chemist', 'hotel', 'salon', 'corporate', 'distributor'];

export function linkHref(link) {
  if (!link) return '#';
  if (link === 'whatsapp' || link.startsWith('enquire')) return '#';
  return link;
}

export function isExternal(link) {
  return /^(https?:|mailto:|tel:)/.test(link || '');
}

export function useLinkAction() {
  const { whatsapp, openEnquiry } = useSite();
  const navigate = useNavigate();
  const location = useLocation();
  const { scrollTo } = useSmoothScroll();

  return (link, opts = {}) => (e) => {
    if (!link) return;
    if (link === 'whatsapp') { e?.preventDefault(); whatsapp(opts); return; }
    if (link.startsWith('enquire')) {
      e?.preventDefault();
      const type = link.split(':')[1];
      const buyerType = BUYERS.includes(type) ? type : undefined;
      openEnquiry(buyerType ? { source: 'b2b', buyerType, tier: 'wholesale' } : { source: 'contact' });
      return;
    }
    if (link.startsWith('#')) {
      e?.preventDefault();
      if (location.pathname !== '/') { navigate('/'); setTimeout(() => scrollTo(link), 160); } else scrollTo(link);
      return;
    }
    if (link.startsWith('/')) { e?.preventDefault(); navigate(link); }
  };
}

/** Props for an <a> that follows an admin link. */
export function useLinkProps() {
  const act = useLinkAction();
  return (link, opts) => ({
    href: linkHref(link),
    onClick: act(link, opts),
    ...(/^https?:/.test(link || '') ? { target: '_blank', rel: 'noopener' } : {}),
  });
}
