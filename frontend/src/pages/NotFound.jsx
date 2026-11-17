// Friendly "not found" page.
import { Helmet } from 'react-helmet-async';
import { Link } from 'react-router-dom';

export default function NotFound({ what = 'page', message }) {
  return (
    <main className="pv-container" style={{ position: 'relative', zIndex: 1, minHeight: '70vh', display: 'grid', placeItems: 'center', textAlign: 'center' }}>
      <Helmet><title>Not found · Paalvi</title><meta name="robots" content="noindex" /></Helmet>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, alignItems: 'center', paddingTop: 96 }}>
        <p className="t-caption">404</p>
        <h1 className="t-h1">We couldn't find that {what}.</h1>
        <p className="t-muted">{message || 'It may have moved, or is no longer available.'}</p>
        <Link to="/" className="pv-btn">Back to Paalvi</Link>
      </div>
    </main>
  );
}
