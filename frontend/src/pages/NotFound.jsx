// Friendly "not found" page.
import { Helmet } from 'react-helmet-async';
import { Link } from 'react-router-dom';
import { useSite } from '../context/SiteContext';
import { useT } from '../i18n/I18n';

export default function NotFound({ what = 'page', message }) {
  const t = useT();
  const { brand } = useSite();
  return (
    <main className="pv-container" style={{ position: 'relative', zIndex: 1, minHeight: '70vh', display: 'grid', placeItems: 'center', textAlign: 'center' }}>
      <Helmet><title>{brand?.name ? `${t('notfound.title')} · ${brand.name}` : t('notfound.title')}</title><meta name="robots" content="noindex" /></Helmet>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, alignItems: 'center', paddingTop: 96 }}>
        <p className="t-caption">404</p>
        <h1 className="t-h1">{what === 'page' ? t('notfound.title') : `We couldn't find that ${what}.`}</h1>
        <p className="t-muted">{message || t('notfound.body')}</p>
        <Link to="/" className="pv-btn">{t('notfound.back')}</Link>
      </div>
    </main>
  );
}
