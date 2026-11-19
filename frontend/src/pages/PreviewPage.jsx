// /__preview — shown inside the admin's "Live preview" panel (never linked publicly).
// Loads the hero slide / section being edited (even if hidden) and applies the admin's
// unsaved field values the moment they change.
import { useEffect, useMemo, useState } from 'react';
import { Helmet } from 'react-helmet-async';
import { useSearchParams } from 'react-router-dom';
import { fetchPreview } from '../api/client';
import DynamicSectionRenderer from '../components/DynamicSectionRenderer/DynamicSectionRenderer';
import Footer from '../components/Footer/Footer';
import Header from '../components/Header/Header';
import { HeroView } from '../components/HeroSection/HeroSection';
import { DEFAULT_DESIGN, useSite } from '../context/SiteContext';
import HomePage from './HomePage';

const NUMBERS = new Set(['overlay_strength', 'gallery_interval', 'header_wordmark_size']);
const SKIP = new Set(['product', 'category', 'show_from', 'show_until', 'is_active', 'order']);

function clean(fields) {
  const out = {};
  Object.entries(fields || {}).forEach(([k, v]) => {
    if (SKIP.has(k)) return;
    out[k] = NUMBERS.has(k) ? Number(v) || 0 : v;
  });
  return out;
}

const EMPTY_HERO = {
  id: 'preview', layout: 'cinematic', headline: 'Your headline', subheadline: '', eyebrow: '', media: [],
  cta_text: 'Explore', cta_link: '#catalog', secondary_cta_text: '', headline_size: 'l', text_tone: 'auto', overlay_strength: 40, height: 'full',
};

export default function PreviewPage() {
  const [params] = useSearchParams();
  const kind = params.get('kind') || 'site';
  const token = params.get('token');
  const { setDesignOverride, data } = useSite();
  const [base, setBase] = useState(null);
  const [fields, setFields] = useState(null);
  const [replay, setReplay] = useState(0);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!token || kind === 'site') return;
    fetchPreview(token).then((r) => setBase(r.item)).catch((e) => setError(e.message));
  }, [token, kind]);

  useEffect(() => {
    const onMessage = (e) => {
      if (e.source !== window.parent) return;
      if (e.data?.type === 'paalvi:preview') setFields(e.data.fields || {});
      if (e.data?.type === 'paalvi:replay') setReplay((r) => r + 1);
    };
    window.addEventListener('message', onMessage);
    window.parent?.postMessage({ type: 'paalvi:ready' }, '*');
    return () => window.removeEventListener('message', onMessage);
  }, []);

  useEffect(() => {
    if (kind !== 'site' || !fields) return;
    const next = {};
    Object.entries(clean(fields)).forEach(([k, v]) => { if (k in DEFAULT_DESIGN) next[k] = v; });
    setDesignOverride(next);
  }, [kind, fields, setDesignOverride]);

  const item = useMemo(() => {
    const live = clean(fields);
    if (kind === 'hero') {
      const merged = { ...EMPTY_HERO, ...(base || {}), ...live };
      if (live.show_product === false) merged.product = null;
      return merged;
    }
    if (kind === 'section') {
      const merged = { id: 'preview', media: [], items: [], ...(base || {}), ...live };
      if (live.section_type) merged.type = live.section_type;
      if (live.background_style) merged.background = live.background_style;
      if (typeof live.items === 'string') {
        try { merged.items = JSON.parse(live.items || '[]'); } catch { merged.items = base?.items || []; }
      }
      return merged;
    }
    return null;
  }, [kind, base, fields]);

  return (
    <>
      <Helmet><meta name="robots" content="noindex, nofollow" /><title>Preview</title></Helmet>
      {error && <p style={{ padding: 24, color: 'var(--color-danger)' }}>{error}</p>}
      {kind === 'hero' && item && (
        <>
          <Header />
          <HeroView key={`${replay}-${item.layout}`} slide={item} />
          <div style={{ padding: '80px 24px 160px', textAlign: 'center' }} className="t-muted">
            Scroll up and down to see scroll effects. Use ↻ Replay in the admin to play the entrance again.
          </div>
        </>
      )}
      {kind === 'section' && item && (
        <div style={{ paddingBlock: '40px 120px' }}>
          <DynamicSectionRenderer key={`${replay}-${item.type}`} sections={[item]} />
        </div>
      )}
      {kind === 'site' && data && (
        <div key={replay}>
          <Header />
          <main><HomePage /></main>
          <Footer />
        </div>
      )}
    </>
  );
}
