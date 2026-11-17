// AI Care Guide launcher: a small "breathing" glow orb. The chat drawer itself is lazy-loaded
// (only downloaded when someone opens it) to keep the first page load light.
import { AnimatePresence, motion } from 'framer-motion';
import { Sparkles } from 'lucide-react';
import { lazy, Suspense, useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useSite } from '../../context/SiteContext';
import { useScrollDirection } from '../../hooks/useScrollDirection';
import styles from './AIAssistantWidget.module.css';

const AIAssistantPanel = lazy(() => import('./AIAssistantPanel'));

export default function AIAssistantWidget() {
  const { data, guideOpen, openGuide, closeGuide } = useSite();
  const { direction, y } = useScrollDirection();
  const { pathname } = useLocation();
  const [everOpened, setEverOpened] = useState(false);
  const ai = data?.ai;

  useEffect(() => {
    if (guideOpen) setEverOpened(true);
  }, [guideOpen]);

  if (!ai?.active) return null;
  // Tucked away while scrolling down and on product pages (the header ✨ button still opens it).
  const hidden = (direction === 'down' && y > 400) || pathname.startsWith('/p/');

  return (
    <>
      <AnimatePresence>
        {!guideOpen && (
          <motion.button
            type="button"
            className={styles.orb}
            onClick={() => openGuide()}
            aria-label={`Open ${ai.name}`}
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: hidden ? 0.8 : 1, opacity: hidden ? 0 : 1, y: hidden ? 20 : 0 }}
            style={{ pointerEvents: hidden ? 'none' : 'auto' }}
            exit={{ scale: 0, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 260, damping: 22 }}
            whileHover={{ scale: 1.06 }}
            whileTap={{ scale: 0.94 }}
          >
            <span className={styles.glow} aria-hidden="true" />
            <Sparkles size={22} strokeWidth={1.5} />
            <span className={styles.orbLabel}>Ask {ai.name.split(' ')[0]}</span>
          </motion.button>
        )}
      </AnimatePresence>
      {everOpened && (
        <Suspense fallback={null}>
          <AIAssistantPanel open={guideOpen} onClose={closeGuide} config={ai} />
        </Suspense>
      )}
    </>
  );
}
