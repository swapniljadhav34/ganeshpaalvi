// App shell and routes.
//  /           homepage (hero, sections, catalog)
//  /p/:slug    product — opens as a modal over the catalog when clicked inside the site,
//              or as a full page when opened directly / shared (good for SEO & WhatsApp previews).
//  /privacy    privacy policy
//  /track      customer order tracking (/track/<link> from the receipt)
//  /studio/*   Studio for staff (separate, lazily-loaded app — visitors never download it)
//  /__preview  the admin's live preview panel (not for visitors)
import { AnimatePresence, motion } from 'framer-motion';
import { RefreshCw } from 'lucide-react';
import { Suspense, lazy, useEffect } from 'react';
import { Route, Routes, useLocation } from 'react-router-dom';
import AIAssistantWidget from './components/AIAssistantWidget/AIAssistantWidget';
import EnquiryForm from './components/EnquiryForm/EnquiryForm';
import FestivalThemeEngine from './components/FestivalThemeEngine/FestivalThemeEngine';
import Footer from './components/Footer/Footer';
import Header from './components/Header/Header';
import InstantContactDock from './components/InstantContactDock/InstantContactDock';
import ProductDetailModal from './components/ProductDetailModal/ProductDetailModal';
import { useSite } from './context/SiteContext';
import SiteEffects from './fx/SiteEffects';
import HomePage from './pages/HomePage';
import NotFound from './pages/NotFound';
import PrivacyPage from './pages/PrivacyPage';
import TrackPage from './pages/TrackPage';
import ProductPage from './pages/ProductPage';
import { usePageTracking } from './utils/analytics';
import { readStore, writeStore } from './utils/storage';

const PreviewPage = lazy(() => import('./pages/PreviewPage'));
const StudioApp = lazy(() => import('./studio/StudioApp'));

const ease = [0.22, 1, 0.36, 1];

/** Loading screen. Its style is remembered from the last visit (chosen in Site Design Studio). */
function Splash({ kind }) {
  const word = (readStore('site:brand-name', '') || '').toUpperCase();
  const exit = kind === 'curtain' ? { y: '-100%', transition: { duration: 0.9, ease } } : { opacity: 0, transition: { duration: 0.4 } };
  return (
    <motion.div className="pv-splash" exit={exit} aria-busy="true" aria-label="Loading">
      {kind === 'letters' ? (
        <p className="pv-splash-word">
          {word.split('').map((ch, i) => (
            <span key={i} className="pv-mask">
              <motion.span className="pv-letter" initial={{ y: '110%' }} animate={{ y: ['110%', '0%', '0%', '-110%'] }}
                transition={{ duration: 2.2, times: [0, 0.3, 0.75, 1], repeat: Infinity, delay: i * 0.06, ease }}>{ch}</motion.span>
            </span>
          ))}
        </p>
      ) : kind === 'none' ? null : (
        <motion.p className="pv-splash-word" animate={{ opacity: [0.35, 1, 0.35] }} transition={{ duration: 2.2, repeat: Infinity, ease: 'easeInOut' }}>
          {word}
        </motion.p>
      )}
    </motion.div>
  );
}

function Offline({ onRetry }) {
  return (
    <div style={{ minHeight: '100svh', display: 'grid', placeItems: 'center', textAlign: 'center', padding: 24 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14, alignItems: 'center' }}>
        <p style={{ fontFamily: 'var(--font-display)', fontSize: '2rem', letterSpacing: '0.2em' }}>{(readStore('site:brand-name', '') || '').toUpperCase()}</p>
        <p className="t-muted">We couldn't connect just now. Please check your internet and try again.</p>
        <button type="button" className="pv-btn" onClick={onRetry}><RefreshCw size={16} strokeWidth={1.5} /> Try again</button>
      </div>
    </div>
  );
}

export default function App() {
  const { isLoading, isError, refetch, data, design } = useSite();
  const location = useLocation();
  // When a product was opened from inside the site, keep the catalog rendered underneath.
  const background = location.state?.background;
  const loader = readStore('paalvi:loader', 'pulse');

  useEffect(() => {
    if (data?.design?.page_loader) writeStore('paalvi:loader', data.design.page_loader);
    if (data?.brand) writeStore('site:brand-name', data.brand.name || '');
  }, [data]);

  // Scroll to top on real page changes (not when opening the product modal).
  useEffect(() => {
    if (!background && !location.hash) window.scrollTo(0, 0);
  }, [location.pathname]); // eslint-disable-line react-hooks/exhaustive-deps

  usePageTracking();

  if (location.pathname === '/studio' || location.pathname.startsWith('/studio/')) {
    return <Suspense fallback={<Splash kind="pulse" />}><StudioApp /></Suspense>;
  }
  if (isError && !data) return <Offline onRetry={refetch} />;
  const preview = location.pathname === '/__preview';

  return (
    <>
      <AnimatePresence>{isLoading && !data && <Splash key="splash" kind={loader} />}</AnimatePresence>
      {data && preview && (
        <>
          <FestivalThemeEngine />
          <SiteEffects />
          <Suspense fallback={null}><PreviewPage /></Suspense>
        </>
      )}
      {data && !preview && (
        <>
          <FestivalThemeEngine />
          <SiteEffects />
          <a href="#catalog" className="pv-sr">Skip to products</a>
          <Header />
          <Routes location={background || location}>
            <Route path="/" element={<main><HomePage /></main>} />
            <Route path="/p/:slug" element={<ProductPage />} />
            <Route path="/privacy" element={<PrivacyPage />} />
            <Route path="/track" element={<TrackPage />} />
            <Route path="/track/:token" element={<TrackPage />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
          <AnimatePresence>
            {background && (
              <Routes>
                <Route path="/p/:slug" element={<ProductDetailModal />} />
              </Routes>
            )}
          </AnimatePresence>
          <Footer />
          {design.show_contact_dock && <InstantContactDock />}
          <AIAssistantWidget />
          <EnquiryForm />
        </>
      )}
    </>
  );
}
