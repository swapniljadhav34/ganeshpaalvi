// One image or video filling its box. Videos fall back to their cover photo on slow phones.
import { isLowEndDevice } from '../utils/device';

const lowEnd = typeof window !== 'undefined' && isLowEndDevice();

export default function MediaItem({ item, priority = false, className = 'pv-media-fill', kenBurns = false }) {
  if (!item) return <div className={`${className} pv-media-empty`} aria-hidden="true" />;
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 768;
  const content = item.type === 'video' && !lowEnd ? (
    <video
      className={className}
      src={(isMobile && item.src_mobile) || item.src}
      poster={item.poster || undefined}
      autoPlay muted loop playsInline preload="metadata"
      aria-label={item.alt || undefined}
      aria-hidden={item.alt ? undefined : 'true'}
    />
  ) : (
    <img
      className={className}
      src={item.type === 'video' ? item.poster || '' : item.src}
      alt={item.alt || ''}
      loading={priority ? 'eager' : 'lazy'}
      fetchpriority={priority ? 'high' : undefined}
      decoding="async"
      draggable="false"
    />
  );
  if (!kenBurns) return content;
  return <div className="pv-media-fill pv-kenburns">{content}</div>;
}
