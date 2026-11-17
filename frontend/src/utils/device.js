// Device capability checks so we can keep mid-range Android phones fast.

export const prefersReducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

/** True on phones/laptops that would struggle with heavy effects (or when the user asked to save data). */
export function isLowEndDevice() {
  if (typeof navigator === 'undefined') return false;
  const cores = navigator.hardwareConcurrency || 8;
  const memory = navigator.deviceMemory || 8;
  const saveData = navigator.connection?.saveData;
  const slowNet = /(^|-)2g$/.test(navigator.connection?.effectiveType || '');
  return cores <= 4 || memory <= 4 || Boolean(saveData) || slowNet;
}

export const hasFinePointer = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(hover: hover) and (pointer: fine)').matches;

export const isMobileViewport = () => typeof window !== 'undefined' && window.innerWidth < 768;
