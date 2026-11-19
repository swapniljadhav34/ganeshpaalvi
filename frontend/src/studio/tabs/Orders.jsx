// Order book: every order — website, phone, WhatsApp, field visit, walk-in — with a live status.
// Marketing & distribution log offline orders here. Moving an order forward keeps stock in step on the
// server (reserve → dispatch → return), and every move is written to the order's timeline.
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Copy, Plus, Printer, Search, Trash2, Users } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { api, fileUrl, qs } from '../api';
import { useAuth } from '../auth';
import { Badge, Button, Empty, ErrorState, Field, Loading, Modal, Pager, money, num, useDebounced, useToast, when } from '../ui';

export const ORDER_TONE = { PENDING: 'warn', CONFIRMED: 'info', PACKED: 'info', IN_TRANSIT: 'serious', DELIVERED: 'good', CANCELLED: 'neutral' };
const PAY = [['UNPAID', 'Not paid'], ['PARTIAL', 'Part paid'], ['PAID', 'Paid'], ['COD', 'Cash on delivery']];

// ---------------------------------------------------------------------------
// New order (offline order book)
// ---------------------------------------------------------------------------
function ProductPicker({ onPick }) {
  const [q, setQ] = useState('');
  const dq = useDebounced(q, 250);
  const res = useQuery({ queryKey: ['studio', 'orders', 'pick', dq], queryFn: () => api(`/orders/pick/products${qs({ q: dq })}`), enabled: dq.length > 0 });
  return (
    <div className="st-picker">
      <label className="st-search"><Search size={16} aria-hidden="true" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Add a product: name or SKU" aria-label="Find a product to add" />
      </label>
      {dq && res.data && (
        <ul className="st-pick-list" role="listbox" aria-label="Matching products">
          {res.data.products.length === 0 && <li className="st-muted">No match.</li>}
          {res.data.products.map((p) => (
            <li key={p.id}>
              <button type="button" onClick={() => { onPick(p); setQ(''); }}>
                <strong>{p.title}</strong> <span className="st-muted">{p.sku} · {money(p.retail_price, true)}{p.available != null && ` · ${num(p.available)} available`}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function NewOrder({ onClose, onCreated, sources, canSetStatus, fromLead }) {
  const toast = useToast();
  const [f, setF] = useState(() => ({
    source: fromLead ? (fromLead.source === 'whatsapp' ? 'WHATSAPP' : 'ONLINE') : 'PHONE',
    channel: fromLead?.tier === 'wholesale' ? 'WHOLESALE' : 'RETAIL', status: 'PENDING',
    customer_name: fromLead?.name || '', phone: fromLead?.phone || '', email: fromLead?.email || '',
    business_name: fromLead?.business_name || '', gstin: '', address: '', city: fromLead?.city || '', state: '', pincode: '',
    discount: '0', shipping: '0', payment_status: 'UNPAID', payment_mode: '', customer_note: '', internal_notes: '',
    lead_id: fromLead?.id || null,
  }));
  const [lines, setLines] = useState([]);
  const [state, setState] = useState({ busy: false, error: '' });
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }));
  const wholesale = f.channel === 'WHOLESALE';
  const add = (p) => setLines((ls) => (ls.some((l) => l.product_id === p.id) ? ls : [...ls, {
    product_id: p.id, title: p.title, sku: p.sku, quantity: 1, available: p.available,
    unit_price: String((wholesale && p.wholesale_price) || p.retail_price),
  }]));
  const setLine = (i, k, v) => setLines((ls) => ls.map((l, j) => (j === i ? { ...l, [k]: v } : l)));
  const subtotal = lines.reduce((s, l) => s + (Number(l.unit_price) || 0) * (Number(l.quantity) || 0), 0);
  const total = Math.max(0, subtotal - (Number(f.discount) || 0) + (Number(f.shipping) || 0));

  const save = async () => {
    if (!lines.length) { setState({ busy: false, error: 'Add at least one product.' }); return; }
    setState({ busy: true, error: '' });
    try {
      const out = await api('/orders', { method: 'POST', body: {
        ...f, discount: f.discount || '0', shipping: f.shipping || '0',
        lines: lines.map((l) => ({ product_id: l.product_id, title: l.title, quantity: Number(l.quantity), unit_price: l.unit_price || '0' })),
      } });
      toast(`Order ${out.number} logged`);
      onCreated(out);
    } catch (e) { setState({ busy: false, error: e.message }); }
  };

  return (
    <Modal open wide onClose={onClose} title="Log an order"
      footer={<><span className="st-muted st-grow">Total <strong>{money(total)}</strong></span>
        <Button variant="ghost" onClick={onClose}>Cancel</Button><Button busy={state.busy} onClick={save}>Save order</Button></>}>
      <div className="st-grid3">
        <Field label="How it came in"><select className="st-input" value={f.source} onChange={set('source')}>{sources.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}</select></Field>
        <Field label="Type"><select className="st-input" value={f.channel} onChange={set('channel')}><option value="RETAIL">Retail</option><option value="WHOLESALE">Wholesale</option></select></Field>
        {canSetStatus && (
          <Field label="Status now" hint="Walk-in sales can be saved as Delivered">
            <select className="st-input" value={f.status} onChange={set('status')}>
              {['PENDING', 'CONFIRMED', 'PACKED', 'IN_TRANSIT', 'DELIVERED'].map((s) => <option key={s} value={s}>{s.replace('_', ' ').toLowerCase().replace(/^./, (c) => c.toUpperCase())}</option>)}
            </select>
          </Field>
        )}
      </div>
      <h3 className="st-h3">Customer</h3>
      <div className="st-grid2">
        <Field label="Name"><input className="st-input" value={f.customer_name} onChange={set('customer_name')} required data-autofocus /></Field>
        <Field label="Phone"><input className="st-input" type="tel" inputMode="tel" value={f.phone} onChange={set('phone')} required /></Field>
        <Field label="Business (optional)"><input className="st-input" value={f.business_name} onChange={set('business_name')} /></Field>
        <Field label="GSTIN (optional)"><input className="st-input" value={f.gstin} maxLength={15} onChange={set('gstin')} /></Field>
        <Field label="Address" full><textarea className="st-input" rows={2} value={f.address} onChange={set('address')} /></Field>
        <Field label="City"><input className="st-input" value={f.city} onChange={set('city')} /></Field>
        <Field label="State"><input className="st-input" value={f.state} onChange={set('state')} /></Field>
        <Field label="PIN code"><input className="st-input" inputMode="numeric" value={f.pincode} maxLength={10} onChange={set('pincode')} /></Field>
        <Field label="Email (optional)"><input className="st-input" type="email" value={f.email} onChange={set('email')} /></Field>
      </div>
      <h3 className="st-h3">Products</h3>
      <ProductPicker onPick={add} />
      {lines.length > 0 && (
        <div className="st-table-wrap">
          <table className="st-table st-table--cards">
            <thead><tr><th>Product</th><th>Qty</th><th>Price / pc (incl. GST)</th><th>Amount</th><th><span className="st-sr">Remove</span></th></tr></thead>
            <tbody>{lines.map((l, i) => (
              <tr key={l.product_id}>
                <td data-label="Product"><strong>{l.title}</strong><br /><span className="st-muted">{l.sku}{l.available != null && ` · ${num(l.available)} available`}</span></td>
                <td data-label="Qty"><input className="st-input st-input--num" type="number" min="1" value={l.quantity} aria-label={`Quantity of ${l.title}`} onChange={(e) => setLine(i, 'quantity', e.target.value)} /></td>
                <td data-label="Price"><input className="st-input st-input--num" type="number" min="0" step="0.01" value={l.unit_price} aria-label={`Price of ${l.title}`} onChange={(e) => setLine(i, 'unit_price', e.target.value)} /></td>
                <td data-label="Amount">{money((Number(l.unit_price) || 0) * (Number(l.quantity) || 0))}</td>
                <td><Button size="sm" variant="ghost" aria-label={`Remove ${l.title}`} onClick={() => setLines((ls) => ls.filter((_, j) => j !== i))}><Trash2 size={15} /></Button></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
      <h3 className="st-h3">Payment & notes</h3>
      <div className="st-grid3">
        <Field label="Discount (₹)"><input className="st-input" type="number" min="0" step="0.01" value={f.discount} onChange={set('discount')} /></Field>
        <Field label="Shipping (₹)"><input className="st-input" type="number" min="0" step="0.01" value={f.shipping} onChange={set('shipping')} /></Field>
        <Field label="Payment"><select className="st-input" value={f.payment_status} onChange={set('payment_status')}>{PAY.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
        <Field label="Paid by (optional)" hint="UPI, cash, bank…"><input className="st-input" value={f.payment_mode} onChange={set('payment_mode')} /></Field>
        <Field label="Note for the customer" hint="Printed on the receipt"><input className="st-input" value={f.customer_note} maxLength={500} onChange={set('customer_note')} /></Field>
        <Field label="Private note"><input className="st-input" value={f.internal_notes} onChange={set('internal_notes')} /></Field>
      </div>
      {state.error && <p className="st-error" role="alert">{state.error}</p>}
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Order detail: status moves, courier details, receipts, tracking link
// ---------------------------------------------------------------------------
const NEXT_LABEL = { CONFIRMED: 'Confirm', PACKED: 'Mark packed', IN_TRANSIT: 'Dispatch', DELIVERED: 'Mark delivered', CANCELLED: 'Cancel order' };

function OrderDetail({ id, onClose }) {
  const { can } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const res = useQuery({ queryKey: ['studio', 'order', id], queryFn: () => api(`/orders/${id}`), refetchInterval: 15_000 });
  const [move, setMove] = useState(null);
  const [extra, setExtra] = useState({ note: '', courier: '', tracking_number: '', expected_delivery: '' });
  const [busy, setBusy] = useState(false);
  const o = res.data;

  const doMove = async () => {
    setBusy(true);
    try {
      const body = { status: move, note: extra.note };
      if (move === 'IN_TRANSIT') Object.assign(body, { courier: extra.courier, tracking_number: extra.tracking_number, expected_delivery: extra.expected_delivery || null });
      const out = await api(`/orders/${id}/status`, { method: 'POST', body });
      qc.setQueryData(['studio', 'order', id], out);
      qc.invalidateQueries({ queryKey: ['studio', 'orders'] });
      toast(`${out.number}: ${out.status_label}`);
      setMove(null);
      setExtra({ note: '', courier: '', tracking_number: '', expected_delivery: '' });
    } catch (e) { toast(e.message, 'critical'); } finally { setBusy(false); }
  };
  const setPayment = async (payment_status) => {
    try {
      const out = await api(`/orders/${id}`, { method: 'PATCH', body: { payment_status } });
      qc.setQueryData(['studio', 'order', id], out);
      qc.invalidateQueries({ queryKey: ['studio', 'orders'] });
      toast('Payment updated');
    } catch (e) { toast(e.message, 'critical'); }
  };
  const remove = async () => {
    if (!window.confirm(`Delete order ${o.number}? Use this only for orders logged by mistake.`)) return;
    try { await api(`/orders/${id}`, { method: 'DELETE' }); qc.invalidateQueries({ queryKey: ['studio', 'orders'] }); toast('Order deleted'); onClose(); } catch (e) { toast(e.message, 'critical'); }
  };
  const copyLink = async () => {
    try { await navigator.clipboard.writeText(o.tracking_url); toast('Tracking link copied — send it to the customer'); } catch { window.prompt('Copy the tracking link:', o.tracking_url); }
  };

  return (
    <Modal open wide onClose={onClose} title={o ? `Order ${o.number}` : 'Order'}>
      {res.isLoading ? <Loading /> : res.isError ? <ErrorState error={res.error} retry={res.refetch} /> : (
        <>
          <div className="st-order-top">
            <Badge tone={ORDER_TONE[o.status]}>{o.status_label}</Badge>
            <span className="st-muted">{when(o.created_at)} · {o.source_label} · {o.channel === 'WHOLESALE' ? 'Wholesale' : 'Retail'}</span>
            <span className="st-muted">Stock: {o.stock_label}</span>
          </div>
          <div className="st-actions st-actions--wrap">
            <a className="st-btn st-btn--ghost st-btn--sm" href={fileUrl(`/orders/${o.id}/receipt?size=a4`)} target="_blank" rel="noopener"><Printer size={15} /> Receipt (A4 / PDF)</a>
            <a className="st-btn st-btn--ghost st-btn--sm" href={fileUrl(`/orders/${o.id}/receipt?size=thermal`)} target="_blank" rel="noopener"><Printer size={15} /> Thermal 80 mm</a>
            <Button size="sm" variant="ghost" onClick={copyLink}><Copy size={15} /> Copy tracking link</Button>
            {can('orders.update') && o.status === 'PENDING' && <Button size="sm" variant="ghost" onClick={remove}><Trash2 size={15} /> Delete</Button>}
          </div>

          {can('orders.update') && o.next.length > 0 && (
            <div className="st-card st-move">
              <p className="st-label">Move this order</p>
              <div className="st-actions st-actions--wrap">
                {o.next.map((s) => (
                  <Button key={s} size="sm" variant={move === s ? 'primary' : s === 'CANCELLED' ? 'ghost' : 'secondary'} onClick={() => setMove(move === s ? null : s)}>{NEXT_LABEL[s]}</Button>
                ))}
              </div>
              {move && (
                <div className="st-grid2" style={{ marginTop: 12 }}>
                  {move === 'IN_TRANSIT' && (
                    <>
                      <Field label="Courier"><input className="st-input" value={extra.courier} onChange={(e) => setExtra((x) => ({ ...x, courier: e.target.value }))} /></Field>
                      <Field label="Tracking / AWB number"><input className="st-input" value={extra.tracking_number} onChange={(e) => setExtra((x) => ({ ...x, tracking_number: e.target.value }))} /></Field>
                      <Field label="Expected delivery"><input className="st-input" type="date" value={extra.expected_delivery} onChange={(e) => setExtra((x) => ({ ...x, expected_delivery: e.target.value }))} /></Field>
                    </>
                  )}
                  <Field label="Note (shown to the customer)" full><input className="st-input" maxLength={300} value={extra.note} onChange={(e) => setExtra((x) => ({ ...x, note: e.target.value }))} /></Field>
                  <div><Button busy={busy} onClick={doMove}>{NEXT_LABEL[move]}</Button></div>
                </div>
              )}
              <p className="st-hint">Confirm reserves stock · Dispatch takes it out · Cancel puts it back. Orders only move forward.</p>
            </div>
          )}

          <div className="st-grid2">
            <div>
              <h3 className="st-h3">Customer</h3>
              <p><strong>{o.customer_name}</strong>{o.business_name && <><br />{o.business_name}</>}<br />
                <a href={`tel:${o.phone}`}>{o.phone}</a>{o.email && <> · <a href={`mailto:${o.email}`}>{o.email}</a></>}</p>
              {(o.address || o.city) && <p className="st-muted" style={{ whiteSpace: 'pre-line' }}>{o.address}{o.address && '\n'}{[o.city, o.state, o.pincode].filter(Boolean).join(', ')}</p>}
              {o.gstin && <p className="st-muted">GSTIN {o.gstin}</p>}
            </div>
            <div>
              <h3 className="st-h3">Payment</h3>
              {can('orders.update') ? (
                <select className="st-input" value={o.payment_status} aria-label="Payment status" onChange={(e) => setPayment(e.target.value)}>
                  {PAY.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                </select>
              ) : <p>{o.payment_label}</p>}
              {(o.courier || o.tracking_number) && <p className="st-muted">Courier: {o.courier} {o.tracking_number}</p>}
              {o.internal_notes && <p className="st-msg">{o.internal_notes}</p>}
            </div>
          </div>

          <div className="st-table-wrap">
            <table className="st-table">
              <thead><tr><th>Item</th><th>Qty</th><th>Price</th><th>Amount</th></tr></thead>
              <tbody>
                {o.lines.map((l) => <tr key={l.id}><td>{l.title} <span className="st-muted">{l.sku}</span></td><td>{num(l.quantity)}</td><td>{money(l.unit_price)}</td><td>{money(l.line_total)}</td></tr>)}
                {Number(o.discount) > 0 && <tr><td colSpan={3}>Discount</td><td>−{money(o.discount)}</td></tr>}
                {Number(o.shipping) > 0 && <tr><td colSpan={3}>Shipping</td><td>{money(o.shipping)}</td></tr>}
                <tr><td colSpan={3}><strong>Total</strong></td><td><strong>{money(o.total)}</strong></td></tr>
              </tbody>
            </table>
          </div>

          <h3 className="st-h3">Timeline</h3>
          <ol className="st-timeline">
            {o.events.map((e, i) => (
              <li key={i}><Badge tone={ORDER_TONE[e.status]}>{e.label}</Badge> <span className="st-muted">{when(e.at)}{e.by && ` · ${e.by.name}`}</span>{e.note && <div>{e.note}</div>}</li>
            ))}
          </ol>
        </>
      )}
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Customer order book: one row per customer
// ---------------------------------------------------------------------------
function Customers({ onOpenPhone }) {
  const [q, setQ] = useState('');
  const dq = useDebounced(q);
  const res = useQuery({ queryKey: ['studio', 'orders', 'customers', dq], queryFn: () => api(`/orders/customers${qs({ q: dq })}`), refetchInterval: 30_000 });
  return (
    <>
      <div className="st-filters">
        <label className="st-search"><Search size={16} aria-hidden="true" /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Customer name, business or phone" aria-label="Search customers" /></label>
      </div>
      {res.isLoading ? <Loading /> : res.isError ? <ErrorState error={res.error} retry={res.refetch} /> : res.data.customers.length === 0 ? <Empty title="No customers yet" /> : (
        <div className="st-table-wrap">
          <table className="st-table st-table--cards">
            <thead><tr><th>Customer</th><th>Orders</th><th>Open</th><th>Spent</th><th>Last order</th><th><span className="st-sr">Open</span></th></tr></thead>
            <tbody>{res.data.customers.map((c) => (
              <tr key={c.phone}>
                <td data-label="Customer"><strong>{c.business_name || c.name}</strong><br /><span className="st-muted">{c.business_name && `${c.name} · `}{c.phone}{c.city && ` · ${c.city}`}</span></td>
                <td data-label="Orders">{num(c.orders)}</td>
                <td data-label="Open">{c.open ? <Badge tone="warn">{c.open}</Badge> : '—'}</td>
                <td data-label="Spent">{money(c.spent || 0, true)}</td>
                <td data-label="Last order">{when(c.last)}</td>
                <td><Button size="sm" variant="ghost" onClick={() => onOpenPhone(c.phone)}>See orders</Button></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
    </>
  );
}

export default function Orders() {
  const location = useLocation();
  const navigate = useNavigate();
  const [view, setView] = useState('orders');
  const [status, setStatus] = useState('');
  const [source, setSource] = useState('');
  const [q, setQ] = useState('');
  const [mine, setMine] = useState(false);
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(null);
  const [creating, setCreating] = useState(false);
  const fromLead = location.state?.fromLead || null;
  const dq = useDebounced(q);
  const qc = useQueryClient();
  const res = useQuery({
    queryKey: ['studio', 'orders', status, source, dq, mine, page],
    queryFn: () => api(`/orders${qs({ status, source, q: dq, mine, page })}`),
    placeholderData: (p) => p,
    refetchInterval: 15_000, // live: other staff's changes appear within seconds
  });

  useEffect(() => { if (fromLead) setCreating(true); }, [fromLead]);
  const counts = res.data?.counts || {};
  const open_total = useMemo(() => ['PENDING', 'CONFIRMED', 'PACKED', 'IN_TRANSIT'].reduce((s, k) => s + (counts[k] || 0), 0), [counts]);

  return (
    <section className="st-section" aria-labelledby="ob-h">
      <div className="st-head">
        <div><h1 id="ob-h">Order book</h1><p className="st-muted">{num(open_total)} open · website, phone, WhatsApp, field and walk-in orders in one place. Updates live.</p></div>
        <div className="st-actions">
          <div className="st-chips" role="radiogroup" aria-label="View">
            <button type="button" role="radio" aria-checked={view === 'orders'} className={view === 'orders' ? 'is-on' : ''} onClick={() => setView('orders')}>Orders</button>
            <button type="button" role="radio" aria-checked={view === 'customers'} className={view === 'customers' ? 'is-on' : ''} onClick={() => setView('customers')}><Users size={14} /> Customers</button>
          </div>
          {res.data?.can_create && <Button onClick={() => setCreating(true)}><Plus size={16} /> Log order</Button>}
        </div>
      </div>

      {view === 'customers' ? <Customers onOpenPhone={(phone) => { setQ(phone); setStatus(''); setPage(1); setView('orders'); }} /> : (
        <>
          <div className="st-filters">
            <label className="st-search"><Search size={16} aria-hidden="true" /><input value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder="Order no., name, phone or city" aria-label="Search orders" /></label>
            <select className="st-input st-input--auto" value={source} onChange={(e) => { setSource(e.target.value); setPage(1); }} aria-label="Source">
              <option value="">All sources</option>
              {(res.data?.sources || []).map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
            </select>
            <label className="st-check"><input type="checkbox" checked={mine} onChange={(e) => { setMine(e.target.checked); setPage(1); }} /> Mine</label>
          </div>
          <div className="st-chips" role="radiogroup" aria-label="Status" style={{ marginBottom: 12 }}>
            {[['', 'All'], ...(res.data?.statuses || []).map((s) => [s.key, s.label])].map(([k, l]) => (
              <button key={k || 'all'} type="button" role="radio" aria-checked={status === k} className={status === k ? 'is-on' : ''} onClick={() => { setStatus(k); setPage(1); }}>
                {l}{k && counts[k] ? ` · ${counts[k]}` : ''}
              </button>
            ))}
          </div>
          {res.isLoading ? <Loading /> : res.isError ? <ErrorState error={res.error} retry={res.refetch} /> : res.data.orders.length === 0 ? <Empty title="No orders here">{res.data.can_create ? 'Use “Log order” for phone, field and walk-in orders.' : ''}</Empty> : (
            <div className="st-table-wrap">
              <table className="st-table st-table--cards">
                <thead><tr><th>Order</th><th>Customer</th><th>Status</th><th>Total</th><th>Payment</th><th>Logged by</th></tr></thead>
                <tbody>{res.data.orders.map((o) => (
                  <tr key={o.id} className="st-row-link" tabIndex={0} onClick={() => setOpen(o.id)} onKeyDown={(e) => e.key === 'Enter' && setOpen(o.id)}>
                    <td data-label="Order"><strong>{o.number}</strong><br /><span className="st-muted">{when(o.created_at)} · {o.source_label}</span></td>
                    <td data-label="Customer">{o.business_name || o.customer_name}<br /><span className="st-muted">{o.phone}{o.city && ` · ${o.city}`}</span></td>
                    <td data-label="Status"><Badge tone={ORDER_TONE[o.status]}>{o.status_label}</Badge></td>
                    <td data-label="Total">{money(o.total)}<br /><span className="st-muted">{num(o.items)} pcs</span></td>
                    <td data-label="Payment">{o.payment_label}</td>
                    <td data-label="Logged by">{o.created_by?.name || '—'}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
          {res.data && <Pager page={page} hasNext={res.data.has_next} onPage={setPage} />}
        </>
      )}

      {creating && (
        <NewOrder sources={res.data?.sources || []} canSetStatus={res.data?.can_update} fromLead={fromLead}
          onClose={() => { setCreating(false); if (fromLead) navigate('.', { replace: true, state: null }); }}
          onCreated={(o) => { setCreating(false); qc.invalidateQueries({ queryKey: ['studio', 'orders'] }); setOpen(o.id); if (fromLead) navigate('.', { replace: true, state: null }); }} />
      )}
      {open && <OrderDetail id={open} onClose={() => setOpen(null)} />}
    </section>
  );
}
