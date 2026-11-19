// One image or video filling its box.
//  • Pictures come with a srcset so phones download a phone-sized file.
//  • Videos fall back to their cover photo on slow phones, and `still` shows only the cover
//    (used where many items are on screen at once, e.g. moving strips and grids).
import { createContext, useContext } from 'react';
import { isLowEndDevice } from '../utils/device';

/** True only inside the real top-of-page hero: its first picture loads first (fast LCP). */
export const MediaPriorityContext = createContext(false);

const lowEnd = typeof window !== 'undefined' && isLowEndDevice();

export default function MediaItem({ item, priority: priorityProp, className = 'pv-media-fill', kenBurns = false, still = false, sizes = '100vw' }) {
  const inheritedPriority = useContext(MediaPriorityContext);
  const priority = priorityProp ?? inheritedPriority;
  if (!item) return <div className={`${className} pv-media-empty`} aria-hidden="true" />;
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 768;
  const asVideo = item.type === 'video' && !lowEnd && !still;
  const imgSrc = item.type === 'video' ? item.poster : item.src;
  const content = asVideo ? (
    <video
      className={className}
      src={(isMobile && item.src_mobile) || item.src}
      poster={item.poster || undefined}
      autoPlay muted loop playsInline preload={priority ? 'auto' : 'metadata'}
      aria-label={item.alt || undefined}
      aria-hidden={item.alt ? undefined : 'true'}
    />
  ) : imgSrc ? (
    <img
      className={className}
      src={imgSrc}
      srcSet={item.type === 'image' && item.srcset ? item.srcset : undefined}
      sizes={item.type === 'image' && item.srcset ? sizes : undefined}
      alt={item.alt || ''}
      loading={priority ? 'eager' : 'lazy'}
      fetchpriority={priority ? 'high' : undefined}
      decoding="async"
      draggable="false"
    />
  ) : (
    <div className={`${className} pv-media-empty`} aria-hidden="true" />
  );
  if (!kenBurns) return content;
  return <div className="pv-media-fill pv-kenburns">{content}</div>;
}
