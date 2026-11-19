// Header with announcement bar, admin-editable menu, live search and Retail/Wholesale toggle.
// Style (floating pill, full bar, minimal, centered, split), scroll behaviour, wordmark size,
// entrance animation and which buttons show are all chosen in Site Design Studio.
import { AnimatePresence, motion } from 'framer-motion';
import { Search, Sparkles, X } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useSite } from '../../context/SiteContext';
import { useEntrance } from '../../fx/FxContext';
import { useScrollDirection } from '../../hooks/useScrollDirection';
import { readStore, writeStore } from '../../utils/storage';
import { useLinkProps } from '../../utils/useLinkAction';
import SearchPanel from './SearchPanel';
import TierToggle from './TierToggle';
import styles from './Header.module.css';
import { useCalm } from '../../hooks/useCalm';

const SECTION_ANCHORS = { '#ritual': 'routine_builder', '#business': 'for_business', '#faq': 'faq' };

function AnnouncementBar({ announcement, style }) {
  const messages = announcement?.messages?.length ? announcement.messages : [announcement?.text].filter(Boolean);
  const key = `paalvi:announce:${messages.join('|')}`;
  const [hidden, setHidden] = useState(() => readStore(key, false));
  const [i, setI] = useState(0);
  const reduce = useCalm();
  const ref = useRef(null);
  const linkProps = useLinkProps();
  const visible = announcement?.active && !hidden;

  // Publish the bar's height as --announce-h so the hero can fit exactly one screen.
  useEffect(() => {
    const root = document.documentElement;
    if (!visible || !ref.current) {
      root.style.setProperty('--announce-h', '0px');
      return undefined;
    }
    const ro = new ResizeObserver(([entry]) => root.style.setProperty('--announce-h', `${entry.target.offsetHeight}px`));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, [visible]);

  useEffect(() => {
    if (style !== 'rotate' || messages.length < 2 || reduce) return undefined;
    const t = setTimeout(() => setI((x) => (x + 1) % messages.length), 4000);
    return () => clearTimeout(t);
  }, [i, style, messages.length, reduce]);

  if (!visible) return null;

  let content;
  if (style === 'marquee' && !reduce) {
    const loop = [...messages, ...messages, ...messages, ...messages];
    content = (
      <div className={styles.announceMarquee}>
        <div className={styles.announceTrack}>
          {loop.map((m, k) => <span key={k} aria-hidden={k >= messages.length ? 'true' : undefined}>{m}<span className={styles.announceSep}>✦</span></span>)}
        </div>
      </div>
    );
  } else if (style === 'rotate' && messages.length > 1) {
    content = (
      <span className={styles.announceRotate}>
        <AnimatePresence mode="wait" initial={false}>
          <motion.span key={i} initial={{ y: 14, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: -14, opacity: 0 }} transition={{ duration: 0.4 }}>
            {messages[i]}
          </motion.span>
        </AnimatePresence>
      </span>
    );
  } else {
    content = <span>{messages[0]}</span>;
  }

  return (
    <div ref={ref} className={styles.announce} role="region" aria-label="Announcement">
      {announcement.link ? <a {...linkProps(announcement.link)} className={styles.announceLink}>{content}</a> : content}
      <button type="button" className={styles.announceClose} onClick={() => { setHidden(true); writeStore(key, true); }} aria-label="Dismiss announcement">
        <X size={14} strokeWidth={1.5} />
      </button>
    </div>
  );
}

export function Wordmark({ brand, onDark = false, size, spacing }) {
  const logo = onDark ? brand?.logo_light : brand?.logo_dark;
  const px = Number(size) || 22;
  if (logo) return <img src={logo} alt={brand?.name || 'Paalvi'} className={styles.logoImg} style={{ height: Math.round(px * 1.3) }} />;
  return (
    <span className={styles.wordmark} style={{ fontSize: `${px}px`, letterSpacing: spacing }}>
      {(brand?.name || 'Paalvi').toUpperCase()}
    </span>
  );
}

function NavLinks({ links, className }) {
  const linkProps = useLinkProps();
  return (
    <ul className={`${styles.links} ${className || ''}`}>
      {links.map((l) => (
        <li key={`${l.label}-${l.link}`}>
          <a {...linkProps(l.link)} className={l.highlight ? styles.navHighlight : undefined}>{l.label}</a>
        </li>
      ))}
    </ul>
  );
}

export default function Header() {
  const { brand, openGuide, data, design } = useSite();
  const { y, direction } = useScrollDirection(4);
  const [searchOpen, setSearchOpen] = useState(false);
  const closeSearch = useCallback(() => setSearchOpen(false), []);
  const entrance = useEntrance(design.header_entrance, { onMount: true, delay: 0.1 });
  const scrolled = y > 80;
  const themeDark = typeof document !== 'undefined' && document.documentElement.dataset.themeMode === 'dark';

  // Press "/" anywhere to search (desktop nicety).
  useEffect(() => {
    if (!design.show_search) return undefined;
    const onKey = (e) => {
      if (e.key === '/' && !/input|textarea/i.test(document.activeElement?.tagName)) {
        e.preventDefault();
        setSearchOpen(true);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [design.show_search]);

  // Hide menu links that point at a section that isn't on the page.
  const types = new Set((data?.sections || []).map((s) => s.type));
  const ids = new Set((data?.sections || []).map((s) => `#section-${s.id}`));
  const links = (data?.nav || [{ label: 'Shop', link: '#catalog' }]).filter((l) => {
    if (SECTION_ANCHORS[l.link]) return types.has(SECTION_ANCHORS[l.link]);
    if (l.link.startsWith('#section-')) return ids.has(l.link);
    return true;
  });

  const style = design.header_style || 'floating_pill';
  const hidden = design.header_scroll === 'hide' && direction === 'down' && y > 160 && !searchOpen;
  const solid = design.header_scroll === 'solid' && scrolled;
  const shrink = design.header_scroll === 'shrink' && scrolled;
  const wordmark = (
    <Link to="/" className={styles.brand} aria-label={`${brand?.name || 'Paalvi'} home`}>
      <Wordmark brand={brand} onDark={themeDark} size={design.header_wordmark_size} spacing={design.wordmark_spacing} />
    </Link>
  );
  const actions = (
    <div className={styles.actions}>
      {design.show_tier_toggle && (
        <>
          <div className="d-none d-md-block"><TierToggle id="tier-desktop" /></div>
          <div className="d-md-none"><TierToggle compact id="tier-mobile" /></div>
        </>
      )}
      {design.show_ai_button && data?.ai?.active && (
        <button type="button" className={`${styles.iconBtn} d-none d-sm-inline-grid`} onClick={() => openGuide()} aria-label="Ask the Care Guide">
          <Sparkles size={19} strokeWidth={1.5} />
        </button>
      )}
      {design.show_search && (
        <button type="button" className={styles.iconBtn} onClick={() => setSearchOpen(true)} aria-label="Search products (press /)">
          <Search size={19} strokeWidth={1.5} />
        </button>
      )}
    </div>
  );

  return (
    <>
      <AnnouncementBar announcement={brand?.announcement} style={design.announcement_style} />
      <header className={`${styles.wrap} ${styles[`s_${style}`]} ${shrink ? styles.scrolled : ''} ${solid ? styles.solid : ''} ${hidden ? styles.hidden : ''}`}>
        <motion.nav className={`${styles.pill} ${style === 'minimal' && !solid ? '' : 'pv-glass'}`} aria-label="Main" {...entrance}>
          {style === 'split' ? (
            <>
              <NavLinks links={links} className={styles.linksLeft} />
              <div className={styles.centerBrand}>{wordmark}</div>
              {actions}
            </>
          ) : style === 'centered' ? (
            <div className={styles.centeredInner}>
              <div className={styles.centeredTop}>
                <span className={styles.spacer} />
                {wordmark}
                {actions}
              </div>
              <NavLinks links={links} className={styles.linksCentered} />
            </div>
          ) : (
            <>
              {wordmark}
              <NavLinks links={links} />
              {actions}
            </>
          )}
        </motion.nav>
      </header>
      <SearchPanel open={searchOpen} onClose={closeSearch} />
    </>
  );
}
