// Accounting (super admin + accountant only — enforced by the server):
// KPIs for a date range, GST invoices with payments, expenses with receipts, GST summary, CSV export.
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, Plus, Search, Trash2 } from 'lucide-react';
import { Fragment, useMemo, useState } from 'react';
import { api, fileUrl, qs } from '../api';
import { useAuth } from '../auth';
import {
  Badge, Button, Empty, ErrorState, Field, Kpi, Loading, Modal, PAY_TONE, Pager, day, isoDay, money, num, useDebounced, useToast,
} from '../ui';

function fyStart(d = new Date()) {
  return new Date(d.getMonth() >= 3 ? d.getFullYear() : d.getFullYear() - 1, 3, 1);
}
const PRESETS = [
  ['month', 'This month', () => [new Date(new Date().getFullYear(), new Date().getMonth(), 1), new Date()]],
  ['30d', 'Last 30 days', () => [new Date(Date.now() - 29 * 864e5), new Date()]],
  ['fy', 'This financial year', () => [fyStart(), new Date()]],
];

function useRefresh() {
  const qc = useQueryClient();
  return () => ['acc-summary', 'invoices', 'invoice', 'expenses'].forEach((k) => qc.invalidateQueries({ queryKey: ['studio', k] }));
}

// Same maths as the server (ops/accounting.py) so the preview matches the saved invoice.
function lineAmounts(qty, price, rate, inclusive) {
  const gross = (Number(qty) || 0) * (Number(price) || 0);
  const r = (Number(rate) || 0) / 100;
  const taxable = Math.round((inclusive ? gross / (1 + r) : gross) * 100) / 100;
  const tax = Math.round((inclusive ? gross - taxable : taxable * r) * 100) / 100;
  return { taxable, tax };
}

const emptyLine = () => ({ description: '', hsn: '', quantity: '1', unit_price: '', gst_rate: 18, product_id: null });

function ProductPick({ onPick }) {
  const [q, setQ] = useState('');
  const dq = useDebounced(q);
  const res = useQuery({ queryKey: ['studio', 'pick-products', dq], queryFn: () => api(`/accounting/pick/products${qs({ q: dq })}`), enabled: dq.length > 1 });
  return (
    <div className="st-picker st-picker--inline">
      <input className="st-input" placeholder="Add a product line…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search product to add" />
      {dq.length > 1 && (
        <ul>{(res.data?.products || []).map((p) => (
          <li key={p.id}><button type="button" onClick={() => { onPick(p); setQ(''); }}>{p.title} <span className="st-muted">{p.sku} · retail {money(p.retail_price, true)}{p.wholesale_price ? ` · wholesale ${money(p.wholesale_price, true)}` : ''}</span></button></li>
        ))}</ul>
      )}
    </div>
  );
}

function InvoiceForm({ onClose }) {
  const toast = useToast();
  const refresh = useRefresh();
  const today = isoDay(new Date());
  const [f, setF] = useState({ channel: 'wholesale', customer_name: '', customer_phone: '', customer_email: '', customer_gstin: '', billing_address: '',
    place_of_supply: '', tax_mode: 'intra', prices_include_tax: false, issue_date: today, due_date: isoDay(Date.now() + 30 * 864e5), notes: '' });
  const [lines, setLines] = useState([emptyLine()]);
  const [state, setState] = useState({ busy: false, error: '' });
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }));
  const setLine = (i, k, v) => setLines((ls) => ls.map((l, j) => (j === i ? { ...l, [k]: v } : l)));

  const totals = useMemo(() => lines.reduce((t, l) => {
    const { taxable, tax } = lineAmounts(l.quantity, l.unit_price, l.gst_rate, f.prices_include_tax);
    return { taxable: t.taxable + taxable, tax: t.tax + tax };
  }, { taxable: 0, tax: 0 }), [lines, f.prices_include_tax]);

  const save = async () => {
    const good = lines.filter((l) => l.description.trim() && Number(l.quantity) > 0 && l.unit_price !== '');
    if (!f.customer_name.trim()) return setState({ busy: false, error: 'Enter the customer name.' });
    if (!good.length) return setState({ busy: false, error: 'Add at least one line with a description, quantity and price.' });
    setState({ busy: true, error: '' });
    try {
      const inv = await api('/accounting/invoices', { method: 'POST', body: {
        ...f, customer_gstin: f.customer_gstin.trim().toUpperCase(), due_date: f.due_date || null, issue_date: f.issue_date || null,
        lines: good.map((l) => ({ description: l.description.trim(), hsn: l.hsn, quantity: Number(l.quantity), unit_price: Number(l.unit_price),
          gst_rate: Number(l.gst_rate), product_id: l.product_id })) } });
      toast(`Invoice ${inv.number} created`); refresh(); onClose();
    } catch (e) { setState({ busy: false, error: e.message }); }
  };

  return (
    <Modal open onClose={onClose} wide title="New invoice"
      footer={<><span className="st-total">Total {money(totals.taxable + totals.tax)} <span className="st-muted">({money(totals.taxable)} + GST {money(totals.tax)})</span></span>
        <span className="st-grow" /><Button variant="ghost" onClick={onClose}>Cancel</Button><Button busy={state.busy} onClick={save}>Create invoice</Button></>}>
      <div className="st-grid3">
        <Field label="Customer name"><input className="st-input" value={f.customer_name} onChange={set('customer_name')} data-autofocus /></Field>
        <Field label="Customer GSTIN" hint="15 characters, optional"><input className="st-input" value={f.customer_gstin} maxLength={15} onChange={set('customer_gstin')} /></Field>
        <Field label="Channel">
          <select className="st-input" value={f.channel} onChange={set('channel')}><option value="wholesale">Wholesale</option><option value="retail">Retail</option></select>
        </Field>
        <Field label="Phone"><input className="st-input" value={f.customer_phone} onChange={set('customer_phone')} /></Field>
        <Field label="Email"><input className="st-input" type="email" value={f.customer_email} onChange={set('customer_email')} /></Field>
        <Field label="Place of supply (state)"><input className="st-input" value={f.place_of_supply} onChange={set('place_of_supply')} /></Field>
        <Field label="GST type">
          <select className="st-input" value={f.tax_mode} onChange={set('tax_mode')}><option value="intra">Within state — CGST + SGST</option><option value="inter">Other state — IGST</option></select>
        </Field>
        <Field label="Invoice date"><input className="st-input" type="date" value={f.issue_date} onChange={set('issue_date')} /></Field>
        <Field label="Due date"><input className="st-input" type="date" value={f.due_date} onChange={set('due_date')} /></Field>
        <Field label="Billing address" full><textarea className="st-input" rows={2} value={f.billing_address} onChange={set('billing_address')} /></Field>
      </div>
      <label className="st-check"><input type="checkbox" checked={f.prices_include_tax} onChange={set('prices_include_tax')} /> Line prices already include GST (typical for retail)</label>

      <div className="st-table-wrap">
        <table className="st-table st-lines">
          <thead><tr><th>Description</th><th>HSN</th><th className="st-num">Qty</th><th className="st-num">Rate ₹</th><th>GST</th><th className="st-num">Amount</th><th><span className="st-sr">Remove</span></th></tr></thead>
          <tbody>
            {lines.map((l, i) => {
              const { taxable, tax } = lineAmounts(l.quantity, l.unit_price, l.gst_rate, f.prices_include_tax);
              return (
                <tr key={i}>
                  <td data-label="Description"><input className="st-input" value={l.description} aria-label={`Line ${i + 1} description`} onChange={(e) => setLine(i, 'description', e.target.value)} /></td>
                  <td data-label="HSN"><input className="st-input st-w6" value={l.hsn} maxLength={10} aria-label={`Line ${i + 1} HSN`} onChange={(e) => setLine(i, 'hsn', e.target.value)} /></td>
                  <td data-label="Qty"><input className="st-input st-w6" inputMode="decimal" value={l.quantity} aria-label={`Line ${i + 1} quantity`} onChange={(e) => setLine(i, 'quantity', e.target.value.replace(/[^\d.]/g, ''))} /></td>
                  <td data-label="Rate ₹"><input className="st-input st-w8" inputMode="decimal" value={l.unit_price} aria-label={`Line ${i + 1} rate`} onChange={(e) => setLine(i, 'unit_price', e.target.value.replace(/[^\d.]/g, ''))} /></td>
                  <td data-label="GST"><select className="st-input" value={l.gst_rate} aria-label={`Line ${i + 1} GST rate`} onChange={(e) => setLine(i, 'gst_rate', Number(e.target.value))}>
                    {[0, 5, 12, 18, 28].map((r) => <option key={r} value={r}>{r}%</option>)}</select></td>
                  <td data-label="Amount" className="st-num">{money(taxable + tax)}</td>
                  <td><button type="button" className="st-icon" onClick={() => setLines((ls) => (ls.length > 1 ? ls.filter((_, j) => j !== i) : ls))} aria-label={`Remove line ${i + 1}`}><Trash2 size={15} /></button></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="st-actions">
        <ProductPick onPick={(p) => setLines((ls) => [...ls.filter((l) => l.description || l.unit_price), {
          ...emptyLine(), description: p.title, product_id: p.id,
          unit_price: String((f.channel === 'wholesale' && p.wholesale_price) || p.retail_price) }])} />
        <Button variant="ghost" size="sm" onClick={() => setLines((ls) => [...ls, emptyLine()])}><Plus size={14} /> Blank line</Button>
      </div>
      {state.error && <p className="st-error" role="alert">{state.error}</p>}
    </Modal>
  );
}

function InvoiceModal({ id, canEdit, onClose }) {
  const toast = useToast();
  const refresh = useRefresh();
  const inv = useQuery({ queryKey: ['studio', 'invoice', id], queryFn: () => api(`/accounting/invoices/${id}`) });
  const [pay, setPay] = useState({ amount: '', mode: 'UPI', reference_id: '', paid_on: isoDay(new Date()) });
  const [state, setState] = useState({ busy: false, error: '' });
  const d = inv.data;
  const record = async () => {
    setState({ busy: true, error: '' });
    try {
      await api(`/accounting/invoices/${id}/payments`, { method: 'POST', body: { ...pay, amount: Number(pay.amount) || 0 } });
      toast('Payment recorded'); refresh(); setPay((p) => ({ ...p, amount: '', reference_id: '' })); setState({ busy: false, error: '' });
    } catch (e) { setState({ busy: false, error: e.message }); }
  };
  const remove = async () => {
    setState({ busy: true, error: '' });
    try { await api(`/accounting/invoices/${id}`, { method: 'DELETE' }); toast('Invoice deleted'); refresh(); onClose(); } catch (e) { setState({ busy: false, error: e.message }); }
  };
  return (
    <Modal open onClose={onClose} wide title={d ? `Invoice ${d.number}` : 'Invoice'}>
      {inv.isLoading ? <Loading /> : inv.isError ? <ErrorState error={inv.error} retry={inv.refetch} /> : (
        <>
          <div className="st-inv-head">
            <div><strong>{d.customer_name}</strong>{d.customer_gstin && <> · GSTIN {d.customer_gstin}</>}<br />
              <span className="st-muted">{d.billing_address}</span></div>
            <div className="st-right"><Badge tone={PAY_TONE[d.payment_status]}>{d.payment_status_label}</Badge><br />
              <span className="st-muted">Issued {day(d.issue_date)} · due {day(d.due_date)}</span></div>
          </div>
          <div className="st-table-wrap">
            <table className="st-table">
              <thead><tr><th>Item</th><th>HSN</th><th className="st-num">Qty</th><th className="st-num">Rate</th><th className="st-num">GST</th><th className="st-num">Taxable</th><th className="st-num">Tax</th></tr></thead>
              <tbody>{d.lines.map((l, i) => (
                <tr key={i}><td data-label="Item">{l.description}</td><td data-label="HSN">{l.hsn || '—'}</td><td data-label="Qty" className="st-num">{num(l.quantity)}</td>
                  <td data-label="Rate" className="st-num">{money(l.unit_price)}</td><td data-label="GST" className="st-num">{Number(l.gst_rate)}%</td>
                  <td data-label="Taxable" className="st-num">{money(l.taxable_value)}</td><td data-label="Tax" className="st-num">{money(l.tax_amount)}</td></tr>
              ))}</tbody>
            </table>
          </div>
          <dl className="st-sum">
            <dt>Taxable value</dt><dd>{money(d.subtotal)}</dd>
            {Number(d.igst) > 0 ? <><dt>IGST</dt><dd>{money(d.igst)}</dd></> : <><dt>CGST</dt><dd>{money(d.cgst)}</dd><dt>SGST</dt><dd>{money(d.sgst)}</dd></>}
            <dt><strong>Total</strong></dt><dd><strong>{money(d.total)}</strong></dd>
            <dt>Paid</dt><dd>{money(d.amount_paid)}</dd><dt><strong>Balance due</strong></dt><dd><strong>{money(d.balance)}</strong></dd>
          </dl>
          <h3>Payments</h3>
          {d.payments.length === 0 ? <p className="st-muted">No payments yet.</p> : (
            <ul className="st-list">{d.payments.map((p) => (
              <li key={p.id}>{day(p.paid_on)} · <strong>{money(p.amount)}</strong> · {p.mode_label}{p.reference_id && ` · ${p.reference_id}`} <span className="st-muted">· {p.by?.name}</span></li>
            ))}</ul>
          )}
          {canEdit && Number(d.balance) > 0 && (
            <div className="st-pay">
              <Field label="Amount ₹"><input className="st-input" inputMode="decimal" value={pay.amount} placeholder={String(d.balance)} onChange={(e) => setPay((p) => ({ ...p, amount: e.target.value.replace(/[^\d.]/g, '') }))} /></Field>
              <Field label="Mode"><select className="st-input" value={pay.mode} onChange={(e) => setPay((p) => ({ ...p, mode: e.target.value }))}>
                <option value="UPI">UPI</option><option value="BANK">Bank transfer</option><option value="CASH">Cash</option><option value="CARD">Card</option></select></Field>
              <Field label="Reference"><input className="st-input" value={pay.reference_id} maxLength={80} onChange={(e) => setPay((p) => ({ ...p, reference_id: e.target.value }))} /></Field>
              <Field label="Date"><input className="st-input" type="date" value={pay.paid_on} onChange={(e) => setPay((p) => ({ ...p, paid_on: e.target.value }))} /></Field>
              <Button busy={state.busy} onClick={record}>Record payment</Button>
            </div>
          )}
          {state.error && <p className="st-error" role="alert">{state.error}</p>}
          {canEdit && d.payments.length === 0 && <p><Button variant="danger" size="sm" busy={state.busy} onClick={remove}><Trash2 size={14} /> Delete invoice</Button></p>}
        </>
      )}
    </Modal>
  );
}

function ExpenseForm({ categories, onClose }) {
  const toast = useToast();
  const refresh = useRefresh();
  const [f, setF] = useState({ category: categories[0]?.key || 'OTHER', amount: '', gst_amount: '', vendor: '', vendor_gstin: '', spent_on: isoDay(new Date()), description: '' });
  const [file, setFile] = useState(null);
  const [state, setState] = useState({ busy: false, error: '' });
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }));
  const save = async () => {
    if (!f.vendor.trim() || !(Number(f.amount) > 0)) return setState({ busy: false, error: 'Enter the vendor and an amount.' });
    if (file && file.size > 5 * 1048576) return setState({ busy: false, error: 'Receipts must be under 5 MB.' });
    setState({ busy: true, error: '' });
    const form = new FormData();
    Object.entries({ ...f, gst_amount: f.gst_amount || '0', vendor_gstin: f.vendor_gstin.trim().toUpperCase() }).forEach(([k, v]) => form.append(k, v));
    if (file) form.append('receipt', file);
    try {
      await api('/accounting/expenses', { method: 'POST', form });
      toast('Expense saved'); refresh(); onClose();
    } catch (e) { setState({ busy: false, error: e.message }); }
  };
  return (
    <Modal open onClose={onClose} title="Log an expense"
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button busy={state.busy} onClick={save}>Save expense</Button></>}>
      <div className="st-grid2">
        <Field label="Category"><select className="st-input" value={f.category} onChange={set('category')} data-autofocus>{categories.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}</select></Field>
        <Field label="Date"><input className="st-input" type="date" value={f.spent_on} onChange={set('spent_on')} /></Field>
        <Field label="Vendor"><input className="st-input" value={f.vendor} maxLength={140} onChange={set('vendor')} /></Field>
        <Field label="Vendor GSTIN (optional)"><input className="st-input" value={f.vendor_gstin} maxLength={15} onChange={set('vendor_gstin')} /></Field>
        <Field label="Total paid ₹ (incl. GST)"><input className="st-input" inputMode="decimal" value={f.amount} onChange={(e) => setF((x) => ({ ...x, amount: e.target.value.replace(/[^\d.]/g, '') }))} /></Field>
        <Field label="GST included ₹" hint="Input tax credit, if any"><input className="st-input" inputMode="decimal" value={f.gst_amount} onChange={(e) => setF((x) => ({ ...x, gst_amount: e.target.value.replace(/[^\d.]/g, '') }))} /></Field>
        <Field label="Description" full><input className="st-input" value={f.description} maxLength={240} onChange={set('description')} /></Field>
        <Field label="Receipt (PDF or photo, max 5 MB)" full hint="Stored privately — only accounting staff can open it.">
          <input className="st-input" type="file" accept=".pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/*" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        </Field>
      </div>
      {state.error && <p className="st-error" role="alert">{state.error}</p>}
    </Modal>
  );
}

function Invoices({ canEdit }) {
  const [status, setStatus] = useState('');
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(null);
  const [creating, setCreating] = useState(false);
  const dq = useDebounced(q);
  const res = useQuery({ queryKey: ['studio', 'invoices', status, dq, page], queryFn: () => api(`/accounting/invoices${qs({ status, q: dq, page })}`), placeholderData: (p) => p });
  return (
    <>
      <div className="st-filters">
        <label className="st-search"><Search size={16} aria-hidden="true" /><input value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder="Invoice number, customer or GSTIN" aria-label="Search invoices" /></label>
        <div className="st-chips" role="radiogroup" aria-label="Payment status">
          {[['', 'All'], ['OPEN', 'Not fully paid'], ['OVERDUE', 'Overdue'], ['UNPAID', 'Unpaid'], ['PARTIAL', 'Partly paid'], ['PAID', 'Paid']].map(([k, l]) => (
            <button key={k || 'all'} type="button" role="radio" aria-checked={status === k} className={status === k ? 'is-on' : ''} onClick={() => { setStatus(k); setPage(1); }}>{l}</button>
          ))}
        </div>
        {canEdit && <Button onClick={() => setCreating(true)}><Plus size={16} /> New invoice</Button>}
      </div>
      {res.isLoading ? <Loading /> : res.isError ? <ErrorState error={res.error} retry={res.refetch} /> : res.data.invoices.length === 0 ? <Empty title="No invoices here" /> : (
        <div className="st-table-wrap">
          <table className="st-table st-table--cards st-clickable">
            <thead><tr><th>Number</th><th>Date</th><th>Customer</th><th>Channel</th><th className="st-num">Total</th><th className="st-num">Balance</th><th>Status</th></tr></thead>
            <tbody>{res.data.invoices.map((i) => (
              <tr key={i.id} onClick={() => setOpen(i.id)} onKeyDown={(e) => e.key === 'Enter' && setOpen(i.id)} tabIndex={0} aria-label={`Open invoice ${i.number}`}>
                <td data-label="Number"><strong>{i.number}</strong></td><td data-label="Date">{day(i.issue_date)}</td>
                <td data-label="Customer">{i.customer_name}</td><td data-label="Channel">{i.channel === 'wholesale' ? 'Wholesale' : 'Retail'}</td>
                <td data-label="Total" className="st-num">{money(i.total)}</td><td data-label="Balance" className="st-num">{money(i.balance)}</td>
                <td data-label="Status"><Badge tone={PAY_TONE[i.payment_status]}>{i.payment_status_label}</Badge></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
      {res.data && <Pager page={page} hasNext={res.data.has_next} onPage={setPage} />}
      {open && <InvoiceModal id={open} canEdit={canEdit} onClose={() => setOpen(null)} />}
      {creating && <InvoiceForm onClose={() => setCreating(false)} />}
    </>
  );
}

function Expenses({ range, canEdit }) {
  const toast = useToast();
  const refresh = useRefresh();
  const [page, setPage] = useState(1);
  const [adding, setAdding] = useState(false);
  const res = useQuery({ queryKey: ['studio', 'expenses', range, page], queryFn: () => api(`/accounting/expenses${qs({ ...range, page })}`), placeholderData: (p) => p });
  const del = async (e) => {
    try { await api(`/accounting/expenses/${e.id}`, { method: 'DELETE' }); toast('Expense deleted'); refresh(); } catch (err) { toast(err.message, 'critical'); }
  };
  return (
    <>
      {canEdit && <div className="st-filters"><Button onClick={() => setAdding(true)}><Plus size={16} /> Log expense</Button></div>}
      {res.isLoading ? <Loading /> : res.isError ? <ErrorState error={res.error} retry={res.refetch} /> : res.data.expenses.length === 0 ? <Empty title="No expenses in this period" /> : (
        <div className="st-table-wrap">
          <table className="st-table st-table--cards">
            <thead><tr><th>Date</th><th>Category</th><th>Vendor</th><th className="st-num">Amount</th><th className="st-num">GST</th><th>Receipt</th><th><span className="st-sr">Actions</span></th></tr></thead>
            <tbody>{res.data.expenses.map((e) => (
              <tr key={e.id}>
                <td data-label="Date">{day(e.spent_on)}</td><td data-label="Category">{e.category_label}</td>
                <td data-label="Vendor">{e.vendor}{e.description && <><br /><span className="st-muted">{e.description}</span></>}</td>
                <td data-label="Amount" className="st-num">{money(e.amount)}</td><td data-label="GST" className="st-num">{money(e.gst_amount)}</td>
                <td data-label="Receipt">{e.has_receipt ? <a href={fileUrl(`/accounting/expenses/${e.id}/receipt`)}>Download</a> : '—'}</td>
                <td>{canEdit && <button type="button" className="st-icon" onClick={() => del(e)} aria-label={`Delete expense from ${e.vendor}`}><Trash2 size={15} /></button>}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
      {res.data && <Pager page={page} hasNext={res.data.has_next} onPage={setPage} />}
      {adding && <ExpenseForm categories={res.data?.categories || []} onClose={() => setAdding(false)} />}
    </>
  );
}

function Gst({ s }) {
  return (
    <div className="st-grid2">
      <div className="st-panel">
        <h3>GST for this period</h3>
        <dl className="st-sum">
          <dt>CGST collected</dt><dd>{money(s.gst.cgst)}</dd><dt>SGST collected</dt><dd>{money(s.gst.sgst)}</dd><dt>IGST collected</dt><dd>{money(s.gst.igst)}</dd>
          <dt><strong>Output GST</strong></dt><dd><strong>{money(s.gst.output)}</strong></dd>
          <dt>Input GST (from expenses)</dt><dd>− {money(s.gst.input)}</dd>
          <dt><strong>Estimated GST payable</strong></dt><dd><strong>{money(s.gst.net_payable)}</strong></dd>
        </dl>
        <p className="st-hint">An estimate for planning. File returns with your CA using your GST portal data.</p>
      </div>
      <div className="st-panel">
        <h3>Expenses by category</h3>
        {s.expenses_by_category.length === 0 ? <p className="st-muted">No expenses yet.</p> : (
          <dl className="st-sum">{s.expenses_by_category.map((c) => <Fragment key={c.category}><dt>{c.label}</dt><dd>{money(c.amount)}</dd></Fragment>)}</dl>
        )}
      </div>
    </div>
  );
}

export default function Accounting() {
  const { can } = useAuth();
  const [preset, setPreset] = useState('month');
  const [custom, setCustom] = useState({ start: isoDay(fyStart()), end: isoDay(new Date()) });
  const [view, setView] = useState('invoices');
  const range = useMemo(() => {
    if (preset === 'custom') return custom;
    const [a, b] = PRESETS.find((p) => p[0] === preset)[2]();
    return { start: isoDay(a), end: isoDay(b) };
  }, [preset, custom]);
  const sum = useQuery({ queryKey: ['studio', 'acc-summary', range], queryFn: () => api(`/accounting/summary${qs(range)}`) });
  const s = sum.data;

  return (
    <section className="st-section" aria-labelledby="acc-h">
      <div className="st-head">
        <div><h1 id="acc-h">Accounting</h1><p className="st-muted">Only the owner and accounting staff can see this page.</p></div>
        {can('accounting.export') && (
          <div className="st-actions">
            {['invoices', 'payments', 'expenses'].map((k) => (
              <a key={k} className="st-btn st-btn--ghost st-btn--sm" href={fileUrl(`/accounting/export/${k}${qs(range)}`)}><Download size={14} /> {k} CSV</a>
            ))}
          </div>
        )}
      </div>

      <div className="st-filters">
        <div className="st-chips" role="radiogroup" aria-label="Period">
          {[...PRESETS.map(([k, l]) => [k, l]), ['custom', 'Custom']].map(([k, l]) => (
            <button key={k} type="button" role="radio" aria-checked={preset === k} className={preset === k ? 'is-on' : ''} onClick={() => setPreset(k)}>{l}</button>
          ))}
        </div>
        {preset === 'custom' && (
          <div className="st-range">
            <input className="st-input" type="date" value={custom.start} onChange={(e) => setCustom((c) => ({ ...c, start: e.target.value }))} aria-label="From" />
            <span>to</span>
            <input className="st-input" type="date" value={custom.end} onChange={(e) => setCustom((c) => ({ ...c, end: e.target.value }))} aria-label="To" />
          </div>
        )}
      </div>

      {sum.isLoading ? <Loading /> : sum.isError ? <ErrorState error={sum.error} retry={sum.refetch} /> : (
        <div className="st-kpis">
          <Kpi label="Total revenue" value={money(s.revenue, true)} sub={`${money(s.invoiced_total, true)} invoiced incl. GST`} />
          <Kpi label="Pending receivables" value={money(s.receivables.total, true)} tone={Number(s.receivables.overdue) > 0 ? 'critical' : undefined}
            sub={`${money(s.receivables.overdue, true)} overdue · ${s.receivables.count} open invoice(s)`} />
          <Kpi label="Total expenses" value={money(s.expenses, true)} sub={`Net profit estimate ${money(s.net_profit_estimate, true)}`} />
          <Kpi label="Net cashflow" value={money(s.net_cashflow, true)} tone={Number(s.net_cashflow) < 0 ? 'critical' : 'good'}
            sub={`${money(s.cash_received, true)} received − expenses`} />
        </div>
      )}

      <div className="st-tabs" role="tablist" aria-label="Accounting views">
        {[['invoices', 'Invoices & payments'], ['expenses', 'Expenses'], ['gst', 'GST & categories']].map(([k, l]) => (
          <button key={k} type="button" role="tab" aria-selected={view === k} className={view === k ? 'is-on' : ''} onClick={() => setView(k)}>{l}</button>
        ))}
      </div>
      {view === 'invoices' && <Invoices canEdit={can('accounting.edit')} />}
      {view === 'expenses' && <Expenses range={range} canEdit={can('accounting.edit')} />}
      {view === 'gst' && s && <Gst s={s} />}
    </section>
  );
}
