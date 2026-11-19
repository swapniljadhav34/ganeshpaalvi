// People & vendor directory: employees, warehouse, distribution, marketing and external vendors.
// Read-only contact list — accounts and roles are managed in Team & roles (Admin).
import { useQuery } from '@tanstack/react-query';
import { Search } from 'lucide-react';
import { useState } from 'react';
import { api, qs } from '../api';
import { Empty, ErrorState, Loading, useDebounced } from '../ui';

export default function Directory() {
  const [kind, setKind] = useState('');
  const [q, setQ] = useState('');
  const dq = useDebounced(q);
  const res = useQuery({ queryKey: ['studio', 'directory', kind, dq], queryFn: () => api(`/directory${qs({ kind, q: dq })}`), placeholderData: (p) => p });
  const kinds = res.data?.kinds || [];
  const label = Object.fromEntries(kinds.map((k) => [k.key, k.label]));
  return (
    <section className="st-section" aria-labelledby="dir-h">
      <div className="st-head"><div><h1 id="dir-h">Directory</h1><p className="st-muted">Who's who across the team and supply chain.</p></div></div>
      <div className="st-filters">
        <label className="st-search"><Search size={16} aria-hidden="true" /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name, company or city" aria-label="Search the directory" /></label>
        <div className="st-chips" role="radiogroup" aria-label="Group">
          {[['', 'Everyone'], ...kinds.map((k) => [k.key, k.label])].map(([k, l]) => (
            <button key={k || 'all'} type="button" role="radio" aria-checked={kind === k} className={kind === k ? 'is-on' : ''} onClick={() => setKind(k)}>{l}</button>
          ))}
        </div>
      </div>
      {res.isLoading ? <Loading /> : res.isError ? <ErrorState error={res.error} retry={res.refetch} /> : res.data.people.length === 0 ? <Empty title="Nobody here" /> : (
        <div className="st-cards">
          {res.data.people.map((p) => (
            <article key={p.id} className="st-card">
              <strong>{p.name || p.username}</strong>{p.company && <span className="st-muted"> · {p.company}</span>}
              <p className="st-muted">{label[p.kind]} · {p.role_label}{p.city && ` · ${p.city}`}</p>
              <p className="st-contact">
                {p.phone && <a href={`tel:${p.phone}`}>{p.phone}</a>}
                {p.email && <a href={`mailto:${p.email}`}>{p.email}</a>}
              </p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
