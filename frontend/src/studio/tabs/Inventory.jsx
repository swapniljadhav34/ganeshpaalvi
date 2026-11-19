// Inventory Manager: stock per SKU with automatic flags, quick +/− adjustments (reason required),
// batch & expiry, and (admin only) thresholds, the movement audit log, settings and CSV export.
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, History, Minus, Plus, Search, Settings2 } from 'lucide-react';
import { useState } from 'react';
import { api, fileUrl, qs } from '../api';
import { useAuth } from '../auth';
import {
  ALERT_TONE, Badge, Button, Empty, ErrorState, Field, Loading, Modal, Pager, day, num, useDebounced, useToast, when,
} from '../ui';
import { NewBatchModal } from './Production';

const FLAGS = [
  { key: '', label: 'All' }, { key: 'ANY', label: 'Needs attention' }, { key: 'OUT_OF_STOCK', label: 'Out of stock' },
  { key: 'LOW_STOCK', label: 'Low stock' }, { key: 'EXPIRING_SOON', label: 'Expiring' },
  { key: 'PRODUCTION_NEEDED', label: 'Production needed' }, { key: 'OK', label: 'Healthy' },
];

const KINDS = {
  add: [['IN', 'Delivery, purchase or customer return'], ['ADJUSTMENT', 'Stock count correction']],
  remove: [['OUT', 'Sold (retail)'], ['WHOLESALE_DISPATCH', 'Wholesale dispatch'], ['DAMAGED', 'Damaged / expired write-off'],
    ['ADJUSTMENT', 'Stock count correction']],
  reserve: [['RESERVE', 'Reserve for a pending order'], ['RELEASE', 'Release a reservation (order cancelled)']],
};

function useRefreshStock() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ['studio', 'inventory'] });
    qc.invalidateQueries({ queryKey: ['studio', 'alerts'] });
    qc.invalidateQueries({ queryKey: ['studio', 'movements'] });
    qc.invalidateQueries({ queryKey: ['studio', 'batches'] });
  };
}

function AdjustModal({ item, onClose }) {
  const toast = useToast();
  const refresh = useRefreshStock();
  const [mode, setMode] = useState('add');
  const [kind, setKind] = useState('IN');
  const [qty, setQty] = useState(1);
  const [reason, setReason] = useState('');
  const [release, setRelease] = useState(0);
  const [state, setState] = useState({ busy: false, error: '' });
  if (!item) return null;

  const n = Math.max(0, Number(qty) || 0);
  const after = mode === 'add' ? item.available + n : mode === 'remove' ? item.available - n + Number(release || 0)
    : kind === 'RESERVE' ? item.available - n : item.available + n;
  const pick = (m) => { setMode(m); setKind(KINDS[m][0][0]); setRelease(0); };

  const submit = async () => {
    if (n < 1) return setState({ busy: false, error: 'Enter a quantity of at least 1.' });
    if (reason.trim().length < 3) return setState({ busy: false, error: 'Please write a short reason (it goes in the audit log).' });
    setState({ busy: true, error: '' });
    try {
      await api(`/inventory/items/${item.id}/adjust`, {
        method: 'POST',
        body: { kind, quantity: mode === 'remove' && kind === 'ADJUSTMENT' ? -n : n, reason: reason.trim(), release_reserved: Number(release) || 0 },
      });
      toast(`${item.sku}: stock updated`);
      refresh();
      onClose();
    } catch (e) {
      setState({ busy: false, error: e.message });
    }
  };

  return (
    <Modal open onClose={onClose} title={`Adjust stock · ${item.title}${item.variant ? ` (${item.variant})` : ''}`}
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button busy={state.busy} onClick={submit}>Save change</Button></>}>
      <div className="st-seg" role="radiogroup" aria-label="Type of change">
        {[['add', 'Add stock', Plus], ['remove', 'Remove stock', Minus], ['reserve', 'Reserve']].map(([k, l, I]) => (
          <button key={k} type="button" role="radio" aria-checked={mode === k} className={mode === k ? 'is-on' : ''} onClick={() => pick(k)}>
            {I && <I size={15} />} {l}
          </button>
        ))}
      </div>
      <div className="st-grid2">
        <Field label="What happened?">
          <select className="st-input" value={kind} onChange={(e) => setKind(e.target.value)}>
            {KINDS[mode].map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
        </Field>
        <Field label="Quantity (pieces)">
          <div className="st-stepper">
            <button type="button" onClick={() => setQty((v) => Math.max(1, (Number(v) || 1) - 1))} aria-label="Decrease"><Minus size={16} /></button>
            <input className="st-input" inputMode="numeric" value={qty} onChange={(e) => setQty(e.target.value.replace(/\D/g, ''))} data-autofocus />
            <button type="button" onClick={() => setQty((v) => (Number(v) || 0) + 1)} aria-label="Increase"><Plus size={16} /></button>
          </div>
        </Field>
        {mode === 'remove' && ['OUT', 'WHOLESALE_DISPATCH'].includes(kind) && item.reserved > 0 && (
          <Field label="Also release reserved pieces" hint={`${item.reserved} are reserved for orders. Release them if this fulfils an order.`}>
            <input className="st-input" inputMode="numeric" value={release} onChange={(e) => setRelease(e.target.value.replace(/\D/g, ''))} />
          </Field>
        )}
        <Field label="Reason (required)" hint="e.g. 'Invoice PAL/2026-27/0012' or 'Monthly count'" full>
          <input className="st-input" value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} />
        </Field>
      </div>
      <p className="st-preview">Available now <strong>{num(item.available)}</strong> → after this change <strong className={after < 0 ? 'st-neg' : ''}>{num(after)}</strong></p>
      {state.error && <p className="st-error" role="alert">{state.error}</p>}
    </Modal>
  );
}

function BatchModal({ item, onClose }) {
  const toast = useToast();
  const refresh = useRefreshStock();
  const [form, setForm] = useState({ batch_number: item?.batch_number || '', expiry_date: item?.expiry_date || '' });
  const [state, setState] = useState({ busy: false, error: '' });
  if (!item) return null;
  const save = async () => {
    setState({ busy: true, error: '' });
    try {
      await api(`/inventory/items/${item.id}/batch`, { method: 'PATCH', body: { batch_number: form.batch_number, expiry_date: form.expiry_date || null } });
      toast('Batch details saved'); refresh(); onClose();
    } catch (e) { setState({ busy: false, error: e.message }); }
  };
  return (
    <Modal open onClose={onClose} title={`Batch & expiry · ${item.sku}`}
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button busy={state.busy} onClick={save}>Save</Button></>}>
      <div className="st-grid2">
        <Field label="Batch / lot number"><input className="st-input" value={form.batch_number} maxLength={40} data-autofocus
          onChange={(e) => setForm((f) => ({ ...f, batch_number: e.target.value }))} /></Field>
        <Field label="Expiry date" hint="Leave empty if it doesn't expire."><input className="st-input" type="date" value={form.expiry_date || ''}
          onChange={(e) => setForm((f) => ({ ...f, expiry_date: e.target.value }))} /></Field>
      </div>
      {state.error && <p className="st-error" role="alert">{state.error}</p>}
    </Modal>
  );
}

function ThresholdModal({ item, onClose }) {
  const toast = useToast();
  const refresh = useRefreshStock();
  const [form, setForm] = useState({ low_stock_threshold: item?.low_stock_threshold ?? 0, reorder_point: item?.reorder_point ?? 0 });
  const [state, setState] = useState({ busy: false, error: '' });
  if (!item) return null;
  const save = async () => {
    setState({ busy: true, error: '' });
    try {
      await api(`/inventory/items/${item.id}/thresholds`, { method: 'PATCH', body: { low_stock_threshold: Number(form.low_stock_threshold) || 0, reorder_point: Number(form.reorder_point) || 0 } });
      toast('Thresholds saved'); refresh(); onClose();
    } catch (e) { setState({ busy: false, error: e.message }); }
  };
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value.replace(/\D/g, '') }));
  return (
    <Modal open onClose={onClose} title={`Alert levels · ${item.sku}`}
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button busy={state.busy} onClick={save}>Save</Button></>}>
      <div className="st-grid2">
        <Field label="Low-stock alert at" hint="'Low stock' when available pieces fall to this number."><input className="st-input" inputMode="numeric" data-autofocus value={form.low_stock_threshold} onChange={set('low_stock_threshold')} /></Field>
        <Field label="Reorder point" hint="'Production needed' below this, unless a batch is already planned."><input className="st-input" inputMode="numeric" value={form.reorder_point} onChange={set('reorder_point')} /></Field>
      </div>
      {state.error && <p className="st-error" role="alert">{state.error}</p>}
    </Modal>
  );
}

function SettingsModal({ onClose }) {
  const toast = useToast();
  const refresh = useRefreshStock();
  const s = useQuery({ queryKey: ['studio', 'inv-settings'], queryFn: () => api('/inventory/settings') });
  const [form, setForm] = useState(null);
  const [state, setState] = useState({ busy: false, error: '' });
  const v = form || s.data;
  const save = async () => {
    setState({ busy: true, error: '' });
    try {
      await api('/inventory/settings', { method: 'PUT', body: {
        expiry_warning_days: Number(v.expiry_warning_days), default_low_stock_threshold: Number(v.default_low_stock_threshold),
        default_reorder_point: Number(v.default_reorder_point), sync_storefront_status: Boolean(v.sync_storefront_status) } });
      toast('Inventory settings saved'); refresh(); onClose();
    } catch (e) { setState({ busy: false, error: e.message }); }
  };
  const set = (k, bool) => (e) => setForm({ ...v, [k]: bool ? e.target.checked : e.target.value.replace(/\D/g, '') });
  return (
    <Modal open onClose={onClose} title="Inventory settings"
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button busy={state.busy} disabled={!v} onClick={save}>Save</Button></>}>
      {!v ? <Loading /> : (
        <div className="st-grid2">
          <Field label="'Expiring soon' warning (days)"><input className="st-input" inputMode="numeric" value={v.expiry_warning_days} onChange={set('expiry_warning_days')} /></Field>
          <Field label="Default low-stock alert (new items)"><input className="st-input" inputMode="numeric" value={v.default_low_stock_threshold} onChange={set('default_low_stock_threshold')} /></Field>
          <Field label="Default reorder point (new items)"><input className="st-input" inputMode="numeric" value={v.default_reorder_point} onChange={set('default_reorder_point')} /></Field>
          <label className="st-check st-field--full">
            <input type="checkbox" checked={Boolean(v.sync_storefront_status)} onChange={set('sync_storefront_status', true)} />
            Update the website's In stock / Low stock / Out of stock labels automatically
          </label>
        </div>
      )}
      {state.error && <p className="st-error" role="alert">{state.error}</p>}
    </Modal>
  );
}

function MovementsModal({ item, onClose }) {
  const [page, setPage] = useState(1);
  const [q, setQ] = useState('');
  const dq = useDebounced(q);
  const m = useQuery({
    queryKey: ['studio', 'movements', item?.id, dq, page],
    queryFn: () => api(`/inventory/movements${qs({ item: item?.id, q: dq, page })}`),
    placeholderData: (prev) => prev,
  });
  return (
    <Modal open onClose={onClose} wide title={item ? `Stock history · ${item.sku}` : 'Stock movement log (all items)'}>
      {!item && <input className="st-input" placeholder="Search SKU, product or reason" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} aria-label="Search movements" />}
      {m.isLoading ? <Loading /> : m.isError ? <ErrorState error={m.error} retry={m.refetch} /> : m.data.movements.length === 0 ? <Empty title="No stock changes yet" /> : (
        <div className="st-table-wrap">
          <table className="st-table">
            <thead><tr><th>When</th>{!item && <th>Item</th>}<th>Change</th><th>Qty</th><th>Stock after</th><th>Reason</th><th>By</th></tr></thead>
            <tbody>
              {m.data.movements.map((x) => (
                <tr key={x.id}>
                  <td data-label="When">{when(x.at)}</td>
                  {!item && <td data-label="Item">{x.item.sku}<br /><span className="st-muted">{x.item.title}</span></td>}
                  <td data-label="Change">{x.label}{x.production_batch && <><br /><span className="st-muted">{x.production_batch}</span></>}</td>
                  <td data-label="Qty" className={x.quantity < 0 ? 'st-neg' : 'st-pos'}>{x.quantity > 0 ? '+' : ''}{num(x.quantity)}</td>
                  <td data-label="Stock after">{num(x.stock_after)}{x.reserved_after ? <span className="st-muted"> ({num(x.reserved_after)} reserved)</span> : null}</td>
                  <td data-label="Reason">{x.reason}</td>
                  <td data-label="By">{x.by?.name || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {m.data && <Pager page={page} hasNext={m.data.has_next} onPage={setPage} />}
    </Modal>
  );
}

export default function Inventory() {
  const { can } = useAuth();
  const qcZero = useQueryClient();
  const toastZero = useToast();
  const zero = async (it) => {
    if (!window.confirm(`Reset ${it.title} (${it.sku}) to 0 in stock? It's logged as a stock correction of −${it.stock}.`)) return;
    try {
      await api(`/inventory/items/${it.id}/zero`, { method: 'POST' });
      toastZero(`${it.sku} reset to 0`);
      qcZero.invalidateQueries({ queryKey: ['studio'] });
    } catch (e) { toastZero(e.message, 'critical'); }
  };
  const [q, setQ] = useState('');
  const [flag, setFlag] = useState('');
  const [page, setPage] = useState(1);
  const [modal, setModal] = useState(null); // { kind, item }
  const dq = useDebounced(q);
  const inv = useQuery({
    queryKey: ['studio', 'inventory', dq, flag, page],
    queryFn: () => api(`/inventory/items${qs({ q: dq, flag, page })}`),
    placeholderData: (prev) => prev,
  });
  const counts = inv.data?.alert_counts || {};
  const close = () => setModal(null);

  return (
    <section className="st-section" aria-labelledby="inv-h">
      <div className="st-head">
        <div>
          <h1 id="inv-h">Inventory</h1>
          <p className="st-muted">Every change is logged with who, when and why. Flags update automatically.</p>
        </div>
        <div className="st-actions">
          {can('inventory.audit') && <Button variant="ghost" onClick={() => setModal({ kind: 'log' })}><History size={16} /> Movement log</Button>}
          {can('inventory.configure') && <Button variant="ghost" onClick={() => setModal({ kind: 'settings' })}><Settings2 size={16} /> Settings</Button>}
          {can('inventory.export') && <a className="st-btn st-btn--ghost" href={fileUrl('/inventory/export.csv')}><Download size={16} /> Export CSV</a>}
        </div>
      </div>

      {Object.keys(counts).length > 0 && (
        <div className="st-banner" role="status">
          <strong>Needs attention:</strong>
          {['OUT_OF_STOCK', 'PRODUCTION_NEEDED', 'EXPIRING_SOON', 'LOW_STOCK'].filter((k) => counts[k]).map((k) => (
            <button key={k} type="button" className="st-chip-btn" onClick={() => { setFlag(k); setPage(1); }}>
              <Badge tone={ALERT_TONE[k]}>{FLAGS.find((f) => f.key === k)?.label}: {counts[k]}</Badge>
            </button>
          ))}
        </div>
      )}

      <div className="st-filters">
        <label className="st-search">
          <Search size={16} aria-hidden="true" />
          <input value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder="Search SKU, product or batch" aria-label="Search stock" />
        </label>
        <div className="st-chips" role="radiogroup" aria-label="Filter by flag">
          {FLAGS.map((f) => (
            <button key={f.key || 'all'} type="button" role="radio" aria-checked={flag === f.key} className={flag === f.key ? 'is-on' : ''}
              onClick={() => { setFlag(f.key); setPage(1); }}>{f.label}</button>
          ))}
        </div>
      </div>

      {inv.isLoading ? <Loading /> : inv.isError ? <ErrorState error={inv.error} retry={inv.refetch} /> : inv.data.items.length === 0 ? (
        <Empty title={q || flag ? 'Nothing matches' : 'No stock items yet'}>{q || flag ? 'Try another search or filter.' : 'Every new product gets a stock item automatically.'}</Empty>
      ) : (
        <div className="st-table-wrap">
          <table className="st-table st-table--cards">
            <thead><tr><th>Product</th><th className="st-num">Available</th><th className="st-num">In stock</th><th className="st-num">Reserved</th><th>Batch · expiry</th><th>Flags</th><th><span className="st-sr">Actions</span></th></tr></thead>
            <tbody>
              {inv.data.items.map((it) => (
                <tr key={it.id}>
                  <td data-label="Product">
                    <div className="st-prod">
                      {it.thumb ? <img src={it.thumb} alt="" loading="lazy" width="40" height="50" /> : <span className="st-prod-ph" />}
                      <span><strong>{it.title}</strong>{it.variant && <> · {it.variant}</>}<br /><span className="st-muted">{it.sku}</span></span>
                    </div>
                  </td>
                  <td data-label="Available" className={`st-num st-big ${it.available <= 0 ? 'st-neg' : ''}`}>{num(it.available)}</td>
                  <td data-label="In stock" className="st-num">{num(it.stock)}</td>
                  <td data-label="Reserved" className="st-num">{num(it.reserved)}</td>
                  <td data-label="Batch · expiry">{it.batch_number || '—'}<br /><span className="st-muted">{it.expiry_date ? `exp. ${day(it.expiry_date)}` : 'no expiry'}</span></td>
                  <td data-label="Flags">
                    <div className="st-badges">
                      {it.alerts.length === 0 ? <Badge tone="good">OK</Badge> : it.alerts.map((a) => <Badge key={a.kind} tone={ALERT_TONE[a.kind]} title={a.message}>{a.label}</Badge>)}
                      {it.active_batches > 0 && <Badge tone="info">{it.active_batches} in production</Badge>}
                    </div>
                  </td>
                  <td data-label="Actions">
                    <div className="st-row-actions">
                      {can('inventory.adjust') && <Button size="sm" onClick={() => setModal({ kind: 'adjust', item: it })}>± Stock</Button>}
                      {can('inventory.reset') && it.stock > 0 && (
                        <Button size="sm" variant="ghost" onClick={() => zero(it)}>Reset to 0</Button>
                      )}
                      {can('inventory.batches') && <Button size="sm" variant="ghost" onClick={() => setModal({ kind: 'batch', item: it })}>Batch</Button>}
                      {can('inventory.configure') && <Button size="sm" variant="ghost" onClick={() => setModal({ kind: 'thresholds', item: it })}>Alert levels</Button>}
                      {can('production.manage') && it.alerts.some((a) => ['PRODUCTION_NEEDED', 'LOW_STOCK', 'OUT_OF_STOCK'].includes(a.kind)) && (
                        <Button size="sm" variant="ghost" onClick={() => setModal({ kind: 'plan', item: it })}>Plan batch</Button>
                      )}
                      {can('inventory.audit') && <Button size="sm" variant="ghost" onClick={() => setModal({ kind: 'log', item: it })}>History</Button>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {inv.data && <Pager page={page} hasNext={inv.data.has_next} onPage={setPage} />}

      {modal?.kind === 'adjust' && <AdjustModal item={modal.item} onClose={close} />}
      {modal?.kind === 'batch' && <BatchModal item={modal.item} onClose={close} />}
      {modal?.kind === 'thresholds' && <ThresholdModal item={modal.item} onClose={close} />}
      {modal?.kind === 'settings' && <SettingsModal onClose={close} />}
      {modal?.kind === 'log' && <MovementsModal item={modal.item} onClose={close} />}
      {modal?.kind === 'plan' && <NewBatchModal presetItem={modal.item} onClose={close} />}
    </section>
  );
}
