// The design kit's brain: resolves a hero/section's shape & animation choices against the
// Site Design Studio defaults, and turns the admin's registry into styles and motion props.
import { createContext, useContext, useMemo } from 'react';
import { useSite } from '../context/SiteContext';
import { ease } from '../theme/motion';

const FALLBACK_SHAPES = {
  rounded: { css: { borderRadius: '28px' } },
  soft: { css: { borderRadius: '16px' } },
  arch: { css: { borderRadius: '999px 999px 28px 28px' } },
  circle: { css: { borderRadius: '50%' }, square: true },
};
const FALLBACK_ENTRANCES = { fade_up: { from: { opacity: 0, y: 48 }, to: { opacity: 1, y: 0 } } };
export const SPEED = { slow: 1.5, normal: 1, fast: 0.6 };

const FxCtx = createContext(null);

/** Merge an item's own choices with the site-wide defaults. Empty value = use the default. */
export function resolveFx(item = {}, design = {}) {
  const pick = (own, def) => (own && own !== '' ? own : def);
  const speedKey = pick(item.animation_speed, design.animation_speed || 'normal');
  return {
    shape: pick(item.media_shape, design.default_media_shape || 'rounded'),
    entrance: pick(item.entrance_animation, design.default_entrance || 'fade_up'),
    text: pick(item.text_animation, design.default_text_animation || 'rise_words'),
    hover: pick(item.hover_effect, design.default_hover || 'lift'),
    motion: pick(item.media_motion, design.default_media_motion || 'none'),
    gallery: pick(item.gallery_style, design.default_gallery_style || 'fade'),
    interval: Math.max(2, Number(item.gallery_interval) || 5),
    pointer: pick(item.pointer_effect, design.default_pointer || 'none'),
    decor: pick(item.decor_shape, design.default_decor || 'none'),
    divider: pick(item.divider_shape, design.default_divider || 'none'),
    speed: SPEED[speedKey] || 1,
  };
}

export function FxProvider({ item, value, children }) {
  const { design } = useSite();
  const fx = useMemo(() => value || resolveFx(item, design), [value, item, design]);
  return <FxCtx.Provider value={fx}>{children}</FxCtx.Provider>;
}

/** The current block's resolved effects (or the site defaults outside any block). */
export function useFx() {
  const ctx = useContext(FxCtx);
  const { design } = useSite();
  return useMemo(() => ctx || resolveFx({}, design), [ctx, design]);
}

export function useRegistry() {
  const { data } = useSite();
  return {
    shapes: data?.fx?.shapes || FALLBACK_SHAPES,
    entrances: data?.fx?.entrances || FALLBACK_ENTRANCES,
  };
}

/** CSS for a named shape (border-radius / clip-path / mask). */
export function useShapeStyle(key) {
  const { shapes } = useRegistry();
  return useMemo(() => {
    const def = shapes[key] || shapes.rounded || FALLBACK_SHAPES.rounded;
    return { ...def.css, ...(def.square ? { aspectRatio: '1 / 1' } : {}) };
  }, [shapes, key]);
}

export function isSquareShape(shapes, key) {
  return Boolean(shapes[key]?.square);
}

/** Motion props for an entrance animation, played once when scrolled into view (or on mount). */
export function useEntrance(key, { delay = 0, speed = 1, onMount = false, amount } = {}) {
  const { entrances } = useRegistry();
  return useMemo(() => {
    const def = entrances[key];
    if (!def || key === 'none' || !Object.keys(def.from || {}).length) return {};
    const transition = def.spring
      ? { type: 'spring', stiffness: 120 / speed, damping: 13, delay }
      : { duration: 0.9 * speed, ease, delay };
    const base = { initial: def.from, transition };
    return onMount
      ? { ...base, animate: def.to }
      : { ...base, whileInView: def.to, viewport: { once: true, margin: '0px 0px -10% 0px', amount } };
  }, [entrances, key, delay, speed, onMount, amount]);
}
