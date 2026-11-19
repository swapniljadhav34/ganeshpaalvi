// Customer order tracking: /track (order number + phone) or /track/<link> (from the receipt / WhatsApp).
// The status refreshes by itself every 20 seconds while the page is open.
import { useQuery } from '@tanstack/react-query';
import { Check, Printer, X } from 'lucide-react';
import { useState } from 'react';
import { Helmet } from 'react-helmet-async';
import { useNavigate, useParams } from 'react-router-dom';
import { receiptUrl, trackOrder, trackOrderByLink } from '../api/client';
import { useSite } from '../context/SiteContext';
import { useI18n } from '../i18n/I18n';
import { formatINR } from '../utils/format';

const box = { background: 'var(--pv-elevated, #fff)', borderRadius: 20, padding: 'clamp(18px, 4vw, 32px)', border: '1px solid rgba(0,0,0,.08)' };
const input = { width: '100%', padding: '12px 14px', borderRadius: 12, border: '1px solid rgba(0,0,0,.18)', font: 'inherit', background: 'transparent', color: 'inherit' };

function Steps({ order, t }) {
  const cancelled = order.status === 'CANCELLED';
  const at = order.steps.findIndex((s) => s.key === order.status);
  const when = (key) => order.events.filter((e) => e.status === key).at(-1)?.at;
  const fmt = (d) => (d ? new Date(d).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '');
  return (
    <ol style={{ listStyle: 'none', padding: 0, margin: '20px 0', display: 'grid', gap: 0 }} aria-label={t('track.title')}>
      {order.steps.map((s, i) => {
        const done = !cancelled && i <= at;
        return (
          <li key={s.key} style={{ display: 'grid', gridTemplateColumns: '32px 1fr', gap: 12, alignItems: 'start', minHeight: 52 }}
            aria-current={!cancelled && i === at ? 'step' : undefined}>
            <span style={{ width: 28, height: 28, borderRadius: 99, display: 'grid', placeItems: 'center', marginTop: 2,
              background: done ? 'var(--pv-primary, #3a7769)' : 'transparent', color: done ? '#fff' : 'inherit',
              border: done ? '0' : '2px solid rgba(0,0,0,.2)' }}>
              {done ? <Check size={16} aria-hidden="true" /> : null}
            </span>
            <span>
              <strong style={{ opacity: done ? 1 : 0.55 }}>{t(`status.${s.key}`)}</strong>
              {done && when(s.key) && <span className="t-muted" style={{ display: 'block', fontSize: 13 }}>{fmt(when(s.key))}</span>}
            </span>
          </li>
        );
      })}
      {cancelled && (
        <li style={{ display: 'grid', gridTemplateColumns: '32px 1fr', gap: 12 }}>
          <span style={{ width: 28, height: 28, borderRadius: 99, display: 'grid', placeItems: 'center', background: '#b42318', color: '#fff' }}>
            <X size={16} aria-hidden="true" />
          </span>
          <strong>{t('status.CANCELLED')}</strong>
        </li>
      )}
    </ol>
  );
}

function OrderView({ order, t, onAnother }) {
  return (
    <section style={box} aria-live="polite">
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'baseline' }}>
        <h2 className="t-h3" style={{ margin: 0 }}>{order.number}</h2>
        <span className="t-muted" style={{ fontSize: 13 }}>{t('track.live')}</span>
      </div>
      <p className="t-muted" style={{ margin: '4px 0 0' }}>
        {t('track.placed')} {new Date(order.placed_at).toLocaleDateString(undefined, { day: 'numeric', month: 'long', year: 'numeric' })}
      </p>
      <Steps order={order} t={t} />
      {(order.courier || order.tracking_number) && (
        <p><strong>{t('track.courier')}:</strong> {order.courier} {order.tracking_number}</p>
      )}
      {order.expected_delivery && order.status !== 'DELIVERED' && order.status !== 'CANCELLED' && (
        <p><strong>{t('track.expected')}:</strong> {new Date(order.expected_delivery).toLocaleDateString(undefined, { day: 'numeric', month: 'long' })}</p>
      )}
      <h3 className="t-caption" style={{ marginTop: 20 }}>{t('track.items')}</h3>
      <ul style={{ paddingInlineStart: 18 }}>
        {order.lines.map((l, i) => <li key={i}>{l.title} × {l.quantity}</li>)}
      </ul>
      <p><strong>{t('track.total')}:</strong> {formatINR(order.total)}</p>
      {order.customer_note && <p className="t-muted">{order.customer_note}</p>}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 16 }}>
        <a className="pv-btn" href={receiptUrl(order.token)} target="_blank" rel="noopener"><Printer size={16} aria-hidden="true" /> {t('track.receipt')}</a>
        <button type="button" className="pv-btn pv-btn--ghost" onClick={onAnother}>{t('track.another')}</button>
      </div>
    </section>
  );
}

export default function TrackPage() {
  const { token } = useParams();
  const navigate = useNavigate();
  const { brand } = useSite();
  const { t } = useI18n();
  const [form, setForm] = useState({ number: '', phone: '' });
  const [lookup, setLookup] = useState({ busy: false, error: '' });

  const res = useQuery({
    queryKey: ['track', token],
    queryFn: ({ signal }) => trackOrderByLink(token, { signal }),
    enabled: Boolean(token),
    refetchInterval: 20_000,
    retry: false,
  });

  const submit = async (e) => {
    e.preventDefault();
    setLookup({ busy: true, error: '' });
    try {
      const order = await trackOrder(form.number.trim(), form.phone.trim());
      navigate(`/track/${order.token}`, { replace: false });
      setLookup({ busy: false, error: '' });
    } catch (err) {
      setLookup({ busy: false, error: err.message });
    }
  };

  return (
    <main className="pv-container" style={{ position: 'relative', zIndex: 1, maxWidth: 640, paddingBlock: '120px 96px' }}>
      <Helmet>
        <title>{brand?.name ? `${t('track.title')} · ${brand.name}` : t('track.title')}</title>
        <meta name="robots" content="noindex" />
      </Helmet>
      <h1 className="t-h1" style={{ margin: '0 0 24px' }}>{t('track.title')}</h1>
      {token ? (
        res.isLoading ? <p className="t-muted" role="status">…</p>
          : res.isError ? <p role="alert" style={{ color: '#b42318' }}>{res.error.message}</p>
            : <OrderView order={res.data} t={t} onAnother={() => navigate('/track')} />
      ) : (
        <form onSubmit={submit} style={{ ...box, display: 'grid', gap: 16 }}>
          <p className="t-muted" style={{ margin: 0 }}>{t('track.intro')}</p>
          <label style={{ display: 'grid', gap: 6 }}>
            <span>{t('track.number')}</span>
            <input style={input} value={form.number} required placeholder="ORD-…" autoComplete="off"
              onChange={(e) => setForm((f) => ({ ...f, number: e.target.value }))} />
          </label>
          <label style={{ display: 'grid', gap: 6 }}>
            <span>{t('track.phone')}</span>
            <input style={input} value={form.phone} required type="tel" inputMode="tel" autoComplete="tel"
              onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} />
          </label>
          {lookup.error && <p role="alert" style={{ color: '#b42318', margin: 0 }}>{lookup.error}</p>}
          <button type="submit" className="pv-btn" disabled={lookup.busy}>{t('track.submit')}</button>
        </form>
      )}
    </main>
  );
}
