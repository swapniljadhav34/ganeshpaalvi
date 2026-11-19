// Orders & enquiries: every WhatsApp tap, form and B2B request, moved through New → Won/Lost.
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Search } from 'lucide-react';
import { useState } from 'react';
import { api, qs } from '../api';
import { useAuth } from '../auth';
import { Badge, Button, Empty, ErrorState, Loading, Pager, num, useDebounced, useToast, when } from '../ui';

const TONE = { new: 'info', contacted: 'warn', quoted: 'serious', won: 'good', lost: 'neutral' };

function LeadCard({ lead, canEdit }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [notes, setNotes] = useState(lead.notes || '');
  const [busy, setBusy] = useState(false);
  const save = async (body, msg) => {
    setBusy(true);
    try {
      await api(`/inquiries/${lead.id}`, { method: 'PATCH', body });
      toast(msg);
      qc.invalidateQueries({ queryKey: ['studio', 'inquiries'] });
    } catch (e) { toast(e.message, 'critical'); } finally { setBusy(false); }
  };
  const digits = (lead.phone || '').replace(/\D/g, '');
  const wa = digits ? `https://wa.me/${digits.length === 10 ? `91${digits}` : digits}` : null;
  return (
    <article className="st-card st-lead">
      <header>
        <div><strong>{lead.business_name || lead.name || lead.phone || 'Visitor'}</strong>
          <span className="st-muted"> · {lead.buyer_type}{lead.city && ` · ${lead.city}`}</span></div>
        <Badge tone={TONE[lead.status]}>{lead.status_label}</Badge>
      </header>
      <p className="st-muted">{when(lead.created_at)} · {lead.source_label} · {lead.tier}</p>
      {lead.product && <p><strong>{lead.product}</strong>{lead.variant && ` · ${lead.variant}`}{lead.package && ` · ${lead.package}`}{lead.quantity && ` · ${num(lead.quantity)} pcs`}</p>}
      {lead.message && <p className="st-msg">{lead.message}</p>}
      <p className="st-contact">
        {lead.phone && <a href={`tel:${lead.phone}`}>{lead.phone}</a>}
        {wa && <a href={wa} target="_blank" rel="noopener">WhatsApp ↗</a>}
        {lead.email && <a href={`mailto:${lead.email}`}>{lead.email}</a>}
      </p>
      {canEdit && (
        <div className="st-lead-edit">
          <select className="st-input" value={lead.status} disabled={busy} aria-label="Stage"
            onChange={(e) => save({ status: e.target.value }, 'Stage updated')}>
            {['new', 'contacted', 'quoted', 'won', 'lost'].map((s) => <option key={s} value={s}>{s[0].toUpperCase() + s.slice(1)}</option>)}
          </select>
          <input className="st-input" value={notes} maxLength={4000} placeholder="Private note" aria-label="Private note" onChange={(e) => setNotes(e.target.value)} />
          <Button size="sm" variant="ghost" busy={busy} disabled={notes === (lead.notes || '')} onClick={() => save({ notes }, 'Note saved')}>Save note</Button>
        </div>
      )}
    </article>
  );
}

export default function Inquiries() {
  const { can } = useAuth();
  const [status, setStatus] = useState('');
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  const dq = useDebounced(q);
  const res = useQuery({ queryKey: ['studio', 'inquiries', status, dq, page], queryFn: () => api(`/inquiries${qs({ status, q: dq, page })}`), placeholderData: (p) => p });
  const counts = res.data?.counts || {};
  return (
    <section className="st-section" aria-labelledby="iq-h">
      <div className="st-head"><div><h1 id="iq-h">Orders & enquiries</h1><p className="st-muted">WhatsApp taps, enquiry forms and B2B requests from the website.</p></div></div>
      <div className="st-filters">
        <label className="st-search"><Search size={16} aria-hidden="true" /><input value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder="Name, phone, city or message" aria-label="Search enquiries" /></label>
        <div className="st-chips" role="radiogroup" aria-label="Stage">
          {[['', 'All'], ...(res.data?.statuses || []).map((s) => [s.key, s.label])].map(([k, l]) => (
            <button key={k || 'all'} type="button" role="radio" aria-checked={status === k} className={status === k ? 'is-on' : ''} onClick={() => { setStatus(k); setPage(1); }}>
              {l}{k && counts[k] ? ` · ${counts[k]}` : ''}
            </button>
          ))}
        </div>
      </div>
      {res.isLoading ? <Loading /> : res.isError ? <ErrorState error={res.error} retry={res.refetch} /> : res.data.leads.length === 0 ? <Empty title="No enquiries here" /> : (
        <div className="st-cards">{res.data.leads.map((l) => <LeadCard key={`${l.id}-${l.status}`} lead={l} canEdit={can('leads.update')} />)}</div>
      )}
      {res.data && <Pager page={page} hasNext={res.data.has_next} onPage={setPage} />}
    </section>
  );
}
