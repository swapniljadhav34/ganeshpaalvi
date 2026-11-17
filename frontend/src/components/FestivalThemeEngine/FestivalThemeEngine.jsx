// Applies the admin's active theme (everyday or festival) to the whole site:
//   1. writes colour + font tokens onto :root (600ms cross-fade via CSS transitions)
//   2. runs the ambient effect (bubbles, diyas, snow…) on a single fixed <canvas>
// Ambient effects switch off for reduced-motion, low-end phones and hidden tabs.
import { useEffect, useRef } from 'react';
import { useSite } from '../../context/SiteContext';
import { isLowEndDevice, isMobileViewport, prefersReducedMotion } from '../../utils/device';
import { startAmbient } from './ambient';
import styles from './FestivalThemeEngine.module.css';

const FONT_STACKS = {
  instrument: "'Instrument Serif', Georgia, serif",
  fraunces: "'Fraunces', 'Instrument Serif', Georgia, serif",
  tiro: "'Tiro Devanagari Hindi', 'Instrument Serif', Georgia, serif",
};
const FONT_URLS = {
  fraunces: 'https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300;9..144,400&display=swap',
  tiro: 'https://fonts.googleapis.com/css2?family=Tiro+Devanagari+Hindi&display=swap',
};

/** Load a display font only when a theme actually needs it. */
function ensureFont(key) {
  const href = FONT_URLS[key];
  if (!href || document.querySelector(`link[data-font="${key}"]`)) return;
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = href;
  link.dataset.font = key;
  document.head.appendChild(link);
}

/** Relative luminance — tells us whether the theme is light or dark. */
function isDark(hex = '#ffffff') {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b < 0.4;
}

export default function FestivalThemeEngine() {
  const { theme } = useSite();
  const canvasRef = useRef(null);
  const tokens = theme?.tokens;

  // 1. Colour + font tokens
  useEffect(() => {
    if (!tokens) return;
    const root = document.documentElement;
    const set = (k, v) => v && root.style.setProperty(k, v);
    set('--color-primary', tokens.primary);
    set('--color-secondary', tokens.secondary);
    set('--color-accent', tokens.accent);
    set('--color-surface', tokens.surface);
    set('--color-surface-elevated', tokens.surface_elevated);
    set('--color-text', tokens.text);
    set('--color-text-muted', tokens.text_muted);
    set('--font-display', FONT_STACKS[tokens.display_font] || FONT_STACKS.instrument);
    ensureFont(tokens.display_font);
    const dark = isDark(tokens.surface);
    root.dataset.themeMode = dark ? 'dark' : 'light';
    root.dataset.theme = tokens.slug;
    root.style.colorScheme = dark ? 'dark' : 'light';
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', tokens.surface);
    if (isLowEndDevice()) root.classList.add('pv-lowend');
  }, [tokens]);

  // 2. Ambient canvas
  const effect = tokens?.ambient_effect;
  const enabled = theme?.ambient_enabled !== false;
  useEffect(() => {
    if (!tokens || !enabled || !effect || effect === 'none') return undefined;
    if (prefersReducedMotion() || isLowEndDevice()) return undefined;
    const colors = {
      primary: tokens.primary,
      secondary: tokens.secondary,
      accent: tokens.accent,
      surfaceElevated: tokens.surface_elevated,
    };
    return startAmbient(canvasRef.current, effect, colors, { maxParticles: isMobileViewport() ? 30 : 100 });
  }, [tokens, effect, enabled]);

  return <canvas ref={canvasRef} className={styles.canvas} aria-hidden="true" />;
}
