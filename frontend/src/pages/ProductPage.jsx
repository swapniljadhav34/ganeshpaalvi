// Full product page — used when a /p/<slug> link is opened directly or shared on WhatsApp.
// (When clicked inside the catalog, the same content opens as a modal instead.)
import { ArrowLeft } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { useProduct } from '../api/hooks';
import ProductDetail from '../components/ProductDetailModal/ProductDetail';
import NotFound from './NotFound';

export default function ProductPage() {
  const { slug } = useParams();
  const { data, isLoading, isError, error } = useProduct(slug);

  if (isError) return error?.status === 404 ? <NotFound what="product" /> : <NotFound what="product" message={error?.message} />;
  return (
    <main className="pv-container" style={{ position: 'relative', zIndex: 1 }}>
      <div style={{ paddingTop: 96 }}>
        <Link to="/#catalog" className="pv-btn pv-btn--ghost pv-btn--sm"><ArrowLeft size={16} strokeWidth={1.5} /> All essentials</Link>
      </div>
      {isLoading || !data ? (
        <div style={{ display: 'grid', gap: 24, paddingBlock: 40 }}>
          <div className="pv-skeleton" style={{ aspectRatio: '4/5', maxWidth: 560 }} />
        </div>
      ) : (
        <ProductDetail key={slug} product={data} layout="page" headingId="product-title" />
      )}
    </main>
  );
}
