// The Care Guide chat drawer: bottom sheet on mobile, side panel on desktop.
// Greeting + suggestion chips from the admin, typing indicator, tappable product cards,
// gentle dentist-referral notes, and friendly handling of rate limits / outages.
import { AnimatePresence, motion } from 'framer-motion';
import { ArrowUp, RotateCcw, Sparkles, Stethoscope, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import Offcanvas from 'react-bootstrap/Offcanvas';
import { useLocation, useNavigate } from 'react-router-dom';
import { askGuide } from '../../api/client';
import { useSite } from '../../context/SiteContext';
import { useMediaQuery } from '../../hooks/useMediaQuery';
import { useSmoothScroll } from '../../hooks/useSmoothScroll';
import { formatINR, tierPrice } from '../../utils/format';
import { WhatsAppIcon } from '../ui/BrandIcons';
import styles from './AIAssistantWidget.module.css';

const STORE_KEY = 'paalvi:guide:chat';

function loadChat() {
  try {
    return JSON.parse(sessionStorage.getItem(STORE_KEY)) || [];
  } catch {
    return [];
  }
}

export default function AIAssistantPanel({ open, onClose, config }) {
  const { tier, whatsapp, guidePrompt } = useSite();
  const isDesktop = useMediaQuery('(min-width: 768px)');
  const [messages, setMessages] = useState(loadChat);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const listRef = useRef(null);
  const inputRef = useRef(null);
  const navigate = useNavigate();
  const location = useLocation();
  const lenis = useSmoothScroll();

  useEffect(() => {
    try { sessionStorage.setItem(STORE_KEY, JSON.stringify(messages.slice(-20))); } catch { /* ignore */ }
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, busy]);

  useEffect(() => {
    if (open) { lenis.stop(); setTimeout(() => inputRef.current?.focus(), 300); } else lenis.start();
  }, [open, lenis]);

  // Opened with a ready-made question (e.g. from a "Ask the guide" button)
  useEffect(() => {
    if (open && guidePrompt) send(guidePrompt);
  }, [open, guidePrompt]); // eslint-disable-line react-hooks/exhaustive-deps

  async function send(text) {
    const message = text.trim();
    if (!message || busy) return;
    setInput('');
    const history = messages.filter((m) => m.role !== 'error').map(({ role, content, sig }) => ({ role, content, sig: sig || '' })).slice(-8);
    setMessages((m) => [...m, { role: 'user', content: message }]);
    setBusy(true);
    try {
      const res = await askGuide({ message, history, tier });
      setMessages((m) => [...m, { role: 'assistant', content: res.reply, sig: res.sig, products: res.products, dentist: res.suggest_dentist, buyer: res.buyer_type }]);
    } catch (err) {
      const text429 = err.status === 429 ? "You're asking quickly — give me a few seconds and try again." : null;
      setMessages((m) => [...m, { role: 'error', content: text429 || err.message || 'Something went wrong. Our team is happy to help on WhatsApp.' }]);
    } finally {
      setBusy(false);
    }
  }

  const openProduct = (p) => {
    onClose();
    navigate(`/p/${p.slug}`, { state: { background: location.state?.background || location, preview: p } });
  };

  return (
    <Offcanvas show={open} onHide={onClose} placement={isDesktop ? 'end' : 'bottom'} className={`${styles.panel} ${isDesktop ? '' : styles.sheet}`}
      aria-labelledby="guide-title" scroll={false}>
      <header className={styles.head}>
        <span className={styles.avatar} aria-hidden="true"><Sparkles size={18} strokeWidth={1.5} /></span>
        <div className={styles.headText}>
          <h2 id="guide-title" className={styles.title}>{config.name}</h2>
          <p className={styles.status}>Product suggestions from our catalogue · not medical advice</p>
        </div>
        {messages.length > 0 && (
          <button type="button" className="pv-icon-btn" onClick={() => setMessages([])} aria-label="Start a new chat"><RotateCcw size={16} strokeWidth={1.5} /></button>
        )}
        <button type="button" className="pv-icon-btn" onClick={onClose} aria-label="Close Care Guide"><X size={18} strokeWidth={1.5} /></button>
      </header>

      <div ref={listRef} className={styles.list} data-lenis-prevent aria-live="polite">
        <div className={`${styles.bubble} ${styles.bot}`}>{config.greeting}</div>
        {messages.length === 0 && config.prompts?.length > 0 && (
          <div className={styles.chips}>
            {config.prompts.map((p) => (
              <button key={p} type="button" className={styles.chip} onClick={() => send(p)}>{p}</button>
            ))}
          </div>
        )}

        <AnimatePresence initial={false}>
          {messages.map((m, i) => (
            <motion.div key={i} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }} className={styles.msg}>
              <div className={`${styles.bubble} ${m.role === 'user' ? styles.me : m.role === 'error' ? styles.err : styles.bot}`}>{m.content}</div>
              {m.dentist && (
                <p className={styles.dentist}><Stethoscope size={14} strokeWidth={1.5} /> If you have pain, bleeding or swelling, please see a dentist.</p>
              )}
              {m.products?.length > 0 && (
                <div className={styles.cards}>
                  {m.products.map((p) => (
                    <button key={p.slug} type="button" className={styles.card} onClick={() => openProduct(p)}>
                      {p.images[0]?.thumb && <img src={p.images[0].thumb} alt="" loading="lazy" />}
                      <span className={styles.cardTitle}>{p.title}</span>
                      <span className={styles.cardPrice}>{formatINR(tierPrice(p, tier))}{tier === 'wholesale' && p.wholesale_price ? '/pc' : ''}</span>
                      {p.badges[0] && <span className="pv-chip pv-chip--primary">{p.badges[0].name}</span>}
                    </button>
                  ))}
                </div>
              )}
              {(m.role === 'error' || (m.buyer && m.role === 'assistant')) && (
                <button type="button" className={`pv-btn pv-btn--whatsapp pv-btn--sm ${styles.wa}`}
                  onClick={() => whatsapp({ buyerType: m.buyer || 'shopper', note: messages.filter((x) => x.role === 'user').slice(-1)[0]?.content })}>
                  <WhatsAppIcon size={16} /> Continue on WhatsApp
                </button>
              )}
            </motion.div>
          ))}
        </AnimatePresence>

        {busy && (
          <div className={`${styles.bubble} ${styles.bot} ${styles.typing}`} aria-label="Care Guide is typing">
            <span /><span /><span />
          </div>
        )}
      </div>

      <form className={styles.composer} onSubmit={(e) => { e.preventDefault(); send(input); }}>
        <input ref={inputRef} value={input} onChange={(e) => setInput(e.target.value)} maxLength={1000}
          placeholder="Ask about sensitivity, kids, bulk orders…" aria-label="Message the Care Guide" className={styles.input} enterKeyHint="send" />
        <button type="submit" className={styles.send} disabled={!input.trim() || busy} aria-label="Send"><ArrowUp size={18} strokeWidth={1.75} /></button>
      </form>
    </Offcanvas>
  );
}
