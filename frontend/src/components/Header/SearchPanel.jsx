// Expanding live search: 300ms debounce, thumbnails, prices and badge chips.
import { AnimatePresence, motion } from 'framer-motion';
import { ArrowRight, LoaderCircle, Search, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { fetchProducts } from '../../api/client';
import { useSmoothScroll } from '../../hooks/useSmoothScroll';
import { springs } from '../../theme/motion';
import Price from '../ui/Price';
import { useSite } from '../../context/SiteContext';
import { useT } from '../../i18n/I18n';
import styles from './Header.module.css';

export default function SearchPanel({ open, onClose }) {
  const t = useT();
  const { brand } = useSite();
  const [q, setQ] = useState('');
  const [state, setState] = useState({ loading: false, items: [], total: 0, error: '' });
  const inputRef = useRef(null);
  const navigate = useNavigate();
  const location = useLocation();
  const { scrollTo } = useSmoothScroll();

  const returnTo = useRef(null);

  // Focus the input on open; give focus back to whatever opened the search on close.
  useEffect(() => {
    if (open) {
      returnTo.current = document.activeElement;
      setTimeout(() => inputRef.current?.focus(), 60);
    } else {
      setQ('');
      if (returnTo.current?.focus) returnTo.current.focus();
    }
  }, [open]);

  // Debounced search: waits 300ms after the last keystroke, cancels stale requests.
  useEffect(() => {
    const term = q.trim();
    if (term.length < 2) {
      setState({ loading: false, items: [], total: 0, error: '' });
      return undefined;
    }
    const ctrl = new AbortController();
    setState((s) => ({ ...s, loading: true }));
    const t = setTimeout(() => {
      fetchProducts({ q: term }, { signal: ctrl.signal })
        .then((d) => setState({ loading: false, items: d.items.slice(0, 6), total: d.total ?? d.items.length, error: '' }))
        .catch((e) => e.name !== 'AbortError' && setState({ loading: false, items: [], total: 0, error: e.message }));
    }, 300);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [q]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  const openProduct = (p) => {
    onClose();
    navigate(`/p/${p.slug}`, { state: { background: location, preview: p } });
  };

  const seeAll = (e) => {
    e?.preventDefault();
    const term = q.trim();
    if (!term) return;
    onClose();
    const params = new URLSearchParams(location.search);
    params.set('q', term);
    navigate({ pathname: '/', search: params.toString() });
    setTimeout(() => scrollTo('#catalog'), 80);
  };

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className={styles.searchScrim}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            className={`${styles.searchPanel} pv-glass`}
            role="dialog"
            aria-modal="true"
            aria-label="Search products"
            initial={{ opacity: 0, y: -12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -12, scale: 0.98 }}
            transition={springs.gentle}
            data-lenis-prevent
          >
            <form className={styles.searchForm} onSubmit={seeAll} role="search">
              <Search size={20} strokeWidth={1.5} aria-hidden="true" />
              <input
                ref={inputRef}
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder={brand?.search_placeholder || t('search.placeholder')}
                aria-label={t('search.open')}
                className={styles.searchInput}
                enterKeyHint="search"
              />
              {state.loading && <LoaderCircle className={styles.spin} size={18} strokeWidth={1.5} aria-label="Searching" />}
              <button type="button" className={styles.iconGhost} onClick={onClose} aria-label={t('search.close')}>
                <X size={20} strokeWidth={1.5} />
              </button>
            </form>

            <div className={styles.searchResults} aria-live="polite">
              {q.trim().length >= 2 && !state.loading && state.items.length === 0 && !state.error && (
                <p className={styles.searchEmpty}>
                  No matches for “{q.trim()}”. Try “soft brush”, “neem” or ask the Care Guide.
                </p>
              )}
              {state.error && <p className={styles.searchEmpty}>{state.error}</p>}
              <ul>
                {state.items.map((p, i) => (
                  <motion.li key={p.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}>
                    <button type="button" className={styles.result} onClick={() => openProduct(p)}>
                      <span className={styles.resultImg}>
                        {p.images[0]?.thumb && <img src={p.images[0].thumb} alt="" loading="lazy" width="48" height="60" />}
                      </span>
                      <span className={styles.resultBody}>
                        <span className={styles.resultTitle}>{p.title}</span>
                        <span className={styles.resultChips}>
                          {p.badges.slice(0, 2).map((b) => (
                            <span key={b.slug} className="pv-chip pv-chip--primary">{b.name}</span>
                          ))}
                        </span>
                      </span>
                      <Price product={p} size="sm" />
                    </button>
                  </motion.li>
                ))}
              </ul>
              {state.items.length > 0 && (
                <button type="button" className={styles.seeAll} onClick={seeAll}>
                  See all {state.total > 6 ? state.total : ''} results <ArrowRight size={16} strokeWidth={1.5} />
                </button>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
