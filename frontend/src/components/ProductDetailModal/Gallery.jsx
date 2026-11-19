// Swipeable gallery (native scroll-snap = smooth on any phone) with optional demo video.
// The first image shares a layoutId with the catalog card for the "lift-off" open animation.
import { AnimatePresence, motion } from 'framer-motion';
import { Box, Play, ZoomIn } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useSite } from '../../context/SiteContext';
import { useShapeStyle } from '../../fx/FxContext';
import Product3DViewer from '../../three/Product3DViewer';
import ZoomViewer from './ZoomViewer';
import styles from './ProductDetailModal.module.css';

export default function Gallery({ slug, images, video, title, model, modelPoster }) {
  const track = useRef(null);
  const [active, setActive] = useState(0);
  const [zoomAt, setZoomAt] = useState(null);
  const { design } = useSite();
  const shape = useShapeStyle(design.product_gallery_shape);
  // Photos first, then the 3D model (if any), then the demo video.
  const slides = [
    ...images.slice(0, 1).map((im) => ({ kind: 'image', ...im, idx: 0 })),
    ...(model ? [{ kind: 'model', src: model, poster: modelPoster || images[0]?.medium }] : []),
    ...images.slice(1).map((im, j) => ({ kind: 'image', ...im, idx: j + 1 })),
    ...(video ? [{ kind: 'video', src: video }] : []),
  ];

  // Reset to the first slide when the image set changes (e.g. a variant with its own photo).
  useEffect(() => {
    track.current?.scrollTo({ left: 0 });
    setActive(0);
  }, [images]);

  const onScroll = () => {
    const el = track.current;
    if (!el) return;
    setActive(Math.round(el.scrollLeft / el.clientWidth));
  };
  const goTo = (i) => track.current?.scrollTo({ left: i * track.current.clientWidth, behavior: 'smooth' });

  return (
    <div className={styles.gallery}>
      <motion.div layoutId={`media-${slug}`} className={styles.galleryFrame} style={{ ...shape, aspectRatio: undefined }}>
        <div ref={track} className={styles.track} onScroll={onScroll} aria-roledescription="carousel" aria-label={`${title} photos`}>
          {slides.length === 0 && <div className={styles.slide}><div className={styles.noImg}>{title.slice(0, 1)}</div></div>}
          {slides.map((s, i) => (
            <div key={i} className={styles.slide} role="group" aria-roledescription="slide" aria-label={`${i + 1} of ${slides.length}`}>
              {s.kind === 'model' ? (
                <Product3DViewer src={s.src} poster={s.poster} alt={`${title} — 3D model`} active={active === i} />
              ) : s.kind === 'image' ? (
                <button type="button" className={styles.slideBtn} onClick={() => setZoomAt(i)} aria-label="Zoom image">
                  <img src={s.medium || s.thumb} srcSet={s.full ? `${s.medium} 960w, ${s.full} 2000w` : undefined}
                    sizes="(min-width: 992px) 50vw, 100vw" alt={s.alt} loading={i === 0 ? 'eager' : 'lazy'} decoding="async" />
                  <span className={styles.zoomBadge} aria-hidden="true"><ZoomIn size={16} strokeWidth={1.5} /></span>
                </button>
              ) : (
                <video src={s.src} controls playsInline preload="metadata" className={styles.video} aria-label={`${title} demo video`} />
              )}
            </div>
          ))}
        </div>
      </motion.div>

      {slides.length > 1 && (
        <div className={styles.thumbs} role="tablist" aria-label="Choose photo">
          {slides.map((s, i) => (
            <button key={i} type="button" role="tab" aria-selected={i === active} className={`${styles.thumb} ${i === active ? styles.thumbOn : ''}`}
              onClick={() => goTo(i)} aria-label={s.kind === 'video' ? 'Play video' : s.kind === 'model' ? 'View in 3D' : `Photo ${i + 1}`}>
              {s.kind === 'image' ? <img src={s.thumb} alt="" loading="lazy" />
                : s.kind === 'model' ? <span className={styles.thumbVideo}><Box size={16} strokeWidth={1.5} /> 3D</span>
                  : <span className={styles.thumbVideo}><Play size={16} strokeWidth={1.5} /></span>}
            </button>
          ))}
        </div>
      )}

      <AnimatePresence>
        {zoomAt != null && <ZoomViewer images={images} start={slides[zoomAt]?.idx ?? 0} onClose={() => setZoomAt(null)} />}
      </AnimatePresence>
    </div>
  );
}
