// Production board: batches move PLANNED → … → COMPLETED. Completing a batch adds its good
// pieces to stock automatically (logged as "Production completed") and clears stock flags.
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ChevronLeft, ChevronRight, Plus, Search } from 'lucide-react';
import { useState } from 'react';
import { api, qs } from '../api';
import { useAuth } from '../auth';
import { ALERT_TONE, Badge, Button, Empty, ErrorState, Field, Loading, Modal, day, isoDay, num, useDebounced, useToast } from '../ui';

const FLOW = ['PLANNED', 'RAW_MATERIALS_READY', 'IN_PRODUCTION', 'QC_TESTING', 'PACKAGING', 'COMPLETED'];
const ALERT_LABEL = { OUT_OF_STOCK: 'Out of stock', LOW_STOCK: 'Low stock', EXPIRING_SOON: 'Expiring', PRODUCTION_NEEDED: 'Production needed' };

function useRefresh() {
  const qc = useQueryClient();
  return () => ['batches', 'inventory', 'alerts', 'movements'].forEach((k) => qc.invalidateQueries({ queryKey: ['studio', k] }));
}

function ItemPicker({ value, onChange }) {
  const [q, setQ] = useState('');
  const dq = useDebounced(q);
  const res = useQuery({ queryKey: ['studio', 'inventory', 'pick', dq], queryFn: () => api(`/inventory/items${qs({ q: dq })}`), enabled: !value });
  if (value) {
    return (
      <div className="st-picked">
        <span><strong>{value.title}</strong>{value.variant ? ` · ${value.variant}` : ''} <span className="st-muted">{value.sku} · {num(value.available)} available</span></span>
        <Button size="sm" variant="ghost" onClick={() => onChange(null)}>Change</Button>
      </div>
    );
  }
  return (
    <div className="st-picker">
      <input className="st-input" placeholder="Search product or SKU" value={q} onChange={(e) => setQ(e.target.value)} data-autofocus aria-label="Search product" />
      <ul>
        {(res.data?.items || []).slice(0, 8).map((it) => (
          <li key={it.id}><button type="button" onClick={() => onChange(it)}>
            <strong>{it.title}</strong>{it.variant ? ` · ${it.variant}` : ''} <span className="st-muted">{it.sku} · {num(it.available)} available</span>
            {it.alerts.map((a) => <Badge key={a.kind} tone={ALERT_TONE[a.kind]}>{a.label}</Badge>)}
          </button></li>
        ))}
      </ul>
    </div>
  );
}

export function NewBatchModal({ presetItem = null, onClose }) {
  const toast = useToast();
  const refresh = useRefresh();
  const people = useQuery({ queryKey: ['studio', 'assignees'], queryFn: () => api('/production/assignees') });
  const suggested = presetItem ? Math.max(presetItem.reorder_point * 2 - presetItem.available, 1) : 100;
  const [item, setItem] = useState(presetItem);
  const [form, setForm] = useState({ planned_quantity: String(suggested), assigned_to_id: '', start_date: isoDay(new Date()),
    expected_completion_date: '', expiry_date: '', notes: '' });
  const [state, setState] = useState({ busy: false, error: '' });
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const save = async () => {
    if (!item) return setState({ busy: false, error: 'Choose what to produce.' });
    setState({ busy: true, error: '' });
    try {
      const b = await api('/production/batches', { method: 'POST', body: {
        item_id: item.id, planned_quantity: Number(form.planned_quantity) || 0, assigned_to_id: form.assigned_to_id ? Number(form.assigned_to_id) : null,
        start_date: form.start_date || null, expected_completion_date: form.expected_completion_date || null,
        expiry_date: form.expiry_date || null, notes: form.notes } });
      toast(`Batch ${b.batch_code} planned`); refresh(); onClose();
    } catch (e) { setState({ busy: false, error: e.message }); }
  };
  return (
    <Modal open onClose={onClose} title="Plan a production batch"
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button busy={state.busy} onClick={save}>Create batch</Button></>}>
      <Field label="Product to produce" full><ItemPicker value={item} onChange={setItem} /></Field>
      <div className="st-grid2">
        <Field label="Planned quantity (pieces)"><input className="st-input" inputMode="numeric" value={form.planned_quantity} onChange={(e) => setForm((f) => ({ ...f, planned_quantity: e.target.value.replace(/\D/g, '') }))} /></Field>
        <Field label="Assigned to">
          <select className="st-input" value={form.assigned_to_id} onChange={set('assigned_to_id')}>
            <option value="">Not assigned yet</option>
            {(people.data?.people || []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </Field>
        <Field label="Start date"><input className="st-input" type="date" value={form.start_date} onChange={set('start_date')} /></Field>
        <Field label="Expected completion"><input className="st-input" type="date" value={form.expected_completion_date} onChange={set('expected_completion_date')} /></Field>
        <Field label="Expiry of produced goods" hint="Optional — becomes the shelf batch expiry when completed."><input className="st-input" type="date" value={form.expiry_date} onChange={set('expiry_date')} /></Field>
        <Field label="Notes" full><textarea className="st-input" rows={2} value={form.notes} maxLength={2000} onChange={set('notes')} /></Field>
      </div>
      {state.error && <p className="st-error" role="alert">{state.error}</p>}
    </Modal>
  );
}

function CompleteModal({ batch, onClose }) {
  const toast = useToast();
  const refresh = useRefresh();
  const [good, setGood] = useState(String(batch.planned_quantity));
  const [waste, setWaste] = useState('0');
  const [note, setNote] = useState('');
  const [state, setState] = useState({ busy: false, error: '' });
  const save = async () => {
    setState({ busy: true, error: '' });
    try {
      await api(`/production/batches/${batch.id}/move`, { method: 'POST', body: {
        status: 'COMPLETED', completed_quantity: Number(good) || 0, wastage_quantity: Number(waste) || 0, notes: note || null } });
      toast(`${num(good)} pieces added to stock from ${batch.batch_code}`); refresh(); onClose();
    } catch (e) { setState({ busy: false, error: e.message }); }
  };
  return (
    <Modal open onClose={onClose} title={`Complete ${batch.batch_code}`}
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button busy={state.busy} onClick={save}>Complete & add to stock</Button></>}>
      <p className="st-muted">{batch.item.title} · planned {num(batch.planned_quantity)} pieces. Good pieces are added to stock immediately.</p>
      <div className="st-grid2">
        <Field label="Good pieces produced"><input className="st-input" inputMode="numeric" value={good} data-autofocus onChange={(e) => setGood(e.target.value.replace(/\D/g, ''))} /></Field>
        <Field label="Wastage / rejected"><input className="st-input" inputMode="numeric" value={waste} onChange={(e) => setWaste(e.target.value.replace(/\D/g, ''))} /></Field>
        <Field label="Note (optional)" full><input className="st-input" value={note} maxLength={1000} onChange={(e) => setNote(e.target.value)} /></Field>
      </div>
      {state.error && <p className="st-error" role="alert">{state.error}</p>}
    </Modal>
  );
}

function EditModal({ batch, onClose }) {
  const toast = useToast();
  const refresh = useRefresh();
  const people = useQuery({ queryKey: ['studio', 'assignees'], queryFn: () => api('/production/assignees') });
  const [form, setForm] = useState({ assigned_to_id: batch.assigned_to?.id ? String(batch.assigned_to.id) : '', expected_completion_date: batch.expected_completion_date || '',
    planned_quantity: String(batch.planned_quantity), notes: batch.notes || '' });
  const [state, setState] = useState({ busy: false, error: '' });
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const call = async (fn, msg) => {
    setState({ busy: true, error: '' });
    try { await fn(); toast(msg); refresh(); onClose(); } catch (e) { setState({ busy: false, error: e.message }); }
  };
  const save = () => call(() => api(`/production/batches/${batch.id}`, { method: 'PATCH', body: {
    assigned_to_id: form.assigned_to_id ? Number(form.assigned_to_id) : null, expected_completion_date: form.expected_completion_date || null,
    planned_quantity: Number(form.planned_quantity) || 1, notes: form.notes } }), 'Batch updated');
  const cancel = () => call(() => api(`/production/batches/${batch.id}/move`, { method: 'POST', body: { status: 'CANCELLED', notes: 'Cancelled' } }), 'Batch cancelled');
  return (
    <Modal open onClose={onClose} title={`Edit ${batch.batch_code}`}
      footer={<><Button variant="danger" busy={state.busy} onClick={cancel}>Cancel batch</Button><span className="st-grow" /><Button variant="ghost" onClick={onClose}>Close</Button><Button busy={state.busy} onClick={save}>Save</Button></>}>
      <div className="st-grid2">
        <Field label="Assigned to">
          <select className="st-input" value={form.assigned_to_id} onChange={set('assigned_to_id')} data-autofocus>
            <option value="">Not assigned</option>
            {(people.data?.people || []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </Field>
        <Field label="Planned quantity"><input className="st-input" inputMode="numeric" value={form.planned_quantity} onChange={(e) => setForm((f) => ({ ...f, planned_quantity: e.target.value.replace(/\D/g, '') }))} /></Field>
        <Field label="Expected completion"><input className="st-input" type="date" value={form.expected_completion_date} onChange={set('expected_completion_date')} /></Field>
        <Field label="Notes" full><textarea className="st-input" rows={3} value={form.notes} onChange={set('notes')} /></Field>
      </div>
      {state.error && <p className="st-error" role="alert">{state.error}</p>}
    </Modal>
  );
}

function BatchCard({ b, canManage, meId, onMove, onComplete, onEdit, busy }) {
  const i = FLOW.indexOf(b.status);
  const mayMove = canManage || b.assigned_to?.id === meId;
  const done = b.status === 'COMPLETED' || b.status === 'CANCELLED';
  return (
    <article className={`st-card ${b.overdue ? 'st-card--late' : ''}`} aria-label={`${b.batch_code}, ${b.status_label}`}>
      <header><strong>{b.batch_code}</strong>{b.overdue && <Badge tone="critical">Overdue</Badge>}</header>
      <p><strong>{b.item.title}</strong><br /><span className="st-muted">{b.item.sku} · {num(b.item.available)} available</span></p>
      <div className="st-badges">{b.item.alerts.map((k) => <Badge key={k} tone={ALERT_TONE[k]}>{ALERT_LABEL[k]}</Badge>)}</div>
      <dl className="st-facts">
        <dt>Planned</dt><dd>{num(b.planned_quantity)}</dd>
        {b.status === 'COMPLETED' && <><dt>Good</dt><dd>{num(b.completed_quantity)}</dd><dt>Wastage</dt><dd>{num(b.wastage_quantity)}</dd></>}
        <dt>Due</dt><dd>{day(b.expected_completion_date)}</dd>
        <dt>Who</dt><dd>{b.assigned_to?.name || 'Unassigned'}</dd>
      </dl>
      {!done && (
        <div className="st-card-actions">
          {mayMove && i > 0 && <button type="button" className="st-icon" disabled={busy} onClick={() => onMove(b, FLOW[i - 1])} aria-label={`Move ${b.batch_code} back`}><ChevronLeft size={16} /></button>}
          {mayMove && i < FLOW.length - 2 && <Button size="sm" busy={busy} onClick={() => onMove(b, FLOW[i + 1])}>Next stage <ChevronRight size={14} /></Button>}
          {mayMove && i === FLOW.length - 2 && <Button size="sm" onClick={() => onComplete(b)}>Complete</Button>}
          {canManage && <Button size="sm" variant="ghost" onClick={() => onEdit(b)}>Edit</Button>}
        </div>
      )}
    </article>
  );
}

export default function Production() {
  const { can, me } = useAuth();
  const toast = useToast();
  const refresh = useRefresh();
  const canManage = can('production.manage');
  const [mine, setMine] = useState(!canManage);
  const [q, setQ] = useState('');
  const dq = useDebounced(q);
  const [modal, setModal] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const res = useQuery({ queryKey: ['studio', 'batches', mine, dq], queryFn: () => api(`/production/batches${qs({ mine, q: dq })}`), placeholderData: (p) => p });

  const move = async (b, status) => {
    setBusyId(b.id);
    try {
      await api(`/production/batches/${b.id}/move`, { method: 'POST', body: { status } });
      toast(`${b.batch_code} → ${res.data.statuses.find((s) => s.key === status)?.label}`);
      refresh();
    } catch (e) { toast(e.message, 'critical'); } finally { setBusyId(null); }
  };

  const batches = res.data?.batches || [];
  const statuses = (res.data?.statuses || []).filter((s) => s.key !== 'CANCELLED');
  const cancelled = batches.filter((b) => b.status === 'CANCELLED');

  return (
    <section className="st-section" aria-labelledby="prod-h">
      <div className="st-head">
        <div>
          <h1 id="prod-h">Production</h1>
          <p className="st-muted">Move batches through each stage. Completing one adds its output to stock automatically.</p>
        </div>
        {canManage && <div className="st-actions"><Button onClick={() => setModal({ kind: 'new' })}><Plus size={16} /> New batch</Button></div>}
      </div>
      <div className="st-filters">
        <label className="st-search"><Search size={16} aria-hidden="true" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search batch, product or SKU" aria-label="Search batches" /></label>
        <label className="st-check"><input type="checkbox" checked={mine} onChange={(e) => setMine(e.target.checked)} /> Only batches assigned to me</label>
      </div>

      {res.isLoading ? <Loading /> : res.isError ? <ErrorState error={res.error} retry={res.refetch} /> : batches.length === 0 ? (
        <Empty title="No batches here">{canManage ? 'Plan one with “New batch”, or from a flagged item in Inventory.' : 'Nothing is assigned to you right now.'}</Empty>
      ) : (
        <div className="st-board" role="list" aria-label="Production stages">
          {statuses.map((s) => {
            const col = batches.filter((b) => b.status === s.key);
            return (
              <section key={s.key} className="st-col" role="listitem" aria-label={`${s.label}: ${col.length}`}>
                <h2>{s.label} <span className="st-muted">{col.length}</span></h2>
                {col.map((b) => (
                  <BatchCard key={b.id} b={b} canManage={canManage} meId={me.user.id} busy={busyId === b.id}
                    onMove={move} onComplete={(x) => setModal({ kind: 'complete', batch: x })} onEdit={(x) => setModal({ kind: 'edit', batch: x })} />
                ))}
              </section>
            );
          })}
        </div>
      )}
      {cancelled.length > 0 && <p className="st-muted">{cancelled.length} cancelled batch(es) in the last 30 days: {cancelled.map((b) => b.batch_code).join(', ')}</p>}

      {modal?.kind === 'new' && <NewBatchModal onClose={() => setModal(null)} />}
      {modal?.kind === 'complete' && <CompleteModal batch={modal.batch} onClose={() => setModal(null)} />}
      {modal?.kind === 'edit' && <EditModal batch={modal.batch} onClose={() => setModal(null)} />}
    </section>
  );
}
