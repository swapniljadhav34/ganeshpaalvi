// Product modal over the catalog (route /p/<slug> with a "background" location).
// Mobile: full-screen sheet you can swipe down to close. Desktop: large centred sheet.
// react-bootstrap's Modal gives us focus-trapping, Escape-to-close and screen-reader semantics.
import { motion, useDragControls, useReducedMotion } from 'framer-motion';
import { X } from 'lucide-react';
import { useEffect, useState } from 'react';
import Modal from 'react-bootstrap/Modal';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { useProduct } from '../../api/hooks';
import { useMediaQuery } from '../../hooks/useMediaQuery';
import { useSmoothScroll } from '../../hooks/useSmoothScroll';
import { springs } from '../../theme/motion';
import ProductDetail from './ProductDetail';
import styles from './ProductDetailModal.module.css';

export default function ProductDetailModal() {
  const { slug } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const isDesktop = useMediaQuery('(min-width: 992px)');
  const reduce = useReducedMotion();
  const dragControls = useDragControls();
  const lenis = useSmoothScroll();
  const [closing, setClosing] = useState(false);
  const { data: product, isError, error } = useProduct(slug, { initial: location.state?.preview });

  useEffect(() => {
    lenis.stop();
    return () => lenis.start();
  }, [lenis]);

  // Animate the sheet away first, then leave the route.
  const close = () => setClosing(true);
  const afterClose = () => {
    if (location.state?.background) navigate(-1);
    else navigate('/', { replace: true });
  };

  return (
    <Modal show onHide={close} animation={false} fullscreen backdrop={false}
      dialogClassName={styles.dialog} contentClassName={styles.content} aria-labelledby="product-title" restoreFocus>
      {/* Our own backdrop so it fades in sync with the sheet */}
      <motion.div className={styles.backdrop} onClick={close} aria-hidden="true"
        initial={{ opacity: 0 }} animate={{ opacity: closing ? 0 : 1 }} transition={{ duration: 0.35 }} />
      <motion.div
        className={styles.sheet}
        initial={reduce ? { opacity: 0 } : isDesktop ? { opacity: 0, y: 40, scale: 0.98 } : { y: '100%' }}
        animate={!closing ? { opacity: 1, y: 0, scale: 1 } : isDesktop ? { opacity: 0, y: 40, scale: 0.98 } : { y: '100%' }}
        transition={springs.float}
        onAnimationComplete={() => closing && afterClose()}
        drag={isDesktop ? false : 'y'}
        dragControls={dragControls}
        dragListener={false}
        dragConstraints={{ top: 0, bottom: 0 }}
        dragElastic={{ top: 0, bottom: 0.6 }}
        onDragEnd={(_, info) => { if (info.offset.y > 120 || info.velocity.y > 600) close(); }}
      >
        <div className={styles.sheetTop} onPointerDown={(e) => !isDesktop && dragControls.start(e)}>
          {!isDesktop && <span className={styles.handle} aria-hidden="true" />}
          <button type="button" className={styles.close} onClick={close} aria-label="Close product">
            <X size={20} strokeWidth={1.5} />
          </button>
        </div>
        <div className={styles.scroll} data-lenis-prevent>
          {isError ? (
            <div className={styles.error}>
              <p className="t-h2">This product isn't available.</p>
              <p className="t-muted">{error?.message}</p>
              <button type="button" className="pv-btn" onClick={close}>Back to the catalog</button>
            </div>
          ) : product ? (
            <ProductDetail key={slug} product={product} headingId="product-title" />
          ) : (
            <div className={styles.loadingBlock} style={{ padding: 32 }}>
              <div className="pv-skeleton" style={{ aspectRatio: '4/5', maxWidth: 480 }} />
            </div>
          )}
        </div>
      </motion.div>
    </Modal>
  );
}
