// System (Admin only): health, clear cache, one-click recovery and a guarded factory reset.
// Nothing here needs a server restart.
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, CheckCircle2, RefreshCw, Trash2, Wrench, XCircle } from 'lucide-react';
import { useState } from 'react';
import { api } from '../api';
import { Badge, Button, ErrorState, Field, Kpi, Loading, Modal, num, useToast } from '../ui';

function ResetModal({ onClose }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [f, setF] = useState({ confirm: '', password: '', load_sample: false });
  const [state, setState] = useState({ busy: false, error: '' });
  const ready = f.confirm === 'RESET' && f.password.length > 0;
  const go = async () => {
    setState({ busy: true, error: '' });
    try {
      const out = await api('/system/reset', { method: 'POST', body: f });
      toast(`Site reset. Backup saved as ${out.backup}`);
      qc.invalidateQueries();
      onClose();
    } catch (e) { setState({ busy: false, error: e.message }); }
  };
  return (
    <Modal open onClose={onClose} title="Reset the site to factory defaults"
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="danger" busy={state.busy} disabled={!ready} onClick={go}>Reset site</Button></>}>
      <div className="st-warn" role="note">
        <AlertTriangle size={18} aria-hidden="true" />
        <div>
          <p><strong>This removes:</strong> all products, categories and photos; homepage sections, hero, menus and footer; translations;
            orders, enquiries, stock and the stock log; production batches; invoices, payments and expenses; traffic data.
            Brand name, contact details and announcement text are emptied.</p>
          <p><strong>This keeps:</strong> every account, password, role and the permission matrix; theme presets; AI assistant settings.</p>
          <p>A full backup file is saved on the server first (<code>backend/backups/</code>), so it can be restored.</p>
        </div>
      </div>
      <Field label="Type RESET to confirm"><input className="st-input" value={f.confirm} autoComplete="off" onChange={(e) => setF((x) => ({ ...x, confirm: e.target.value }))} data-autofocus /></Field>
      <Field label="Your password"><input className="st-input" type="password" autoComplete="current-password" value={f.password} onChange={(e) => setF((x) => ({ ...x, password: e.target.value }))} /></Field>
      <label className="st-check"><input type="checkbox" checked={f.load_sample} onChange={(e) => setF((x) => ({ ...x, load_sample: e.target.checked }))} /> Load the sample products and homepage afterwards (for a demo)</label>
      {state.error && <p className="st-error" role="alert">{state.error}</p>}
    </Modal>
  );
}

export default function System() {
  const toast = useToast();
  const qc = useQueryClient();
  const health = useQuery({ queryKey: ['studio', 'system', 'health'], queryFn: () => api('/system/health'), refetchInterval: 30_000 });
  const [busy, setBusy] = useState('');
  const [steps, setSteps] = useState(null);
  const [resetting, setResetting] = useState(false);
  const h = health.data;

  const clear = async () => {
    setBusy('clear');
    try { await api('/system/clear-cache', { method: 'POST' }); toast('Cache cleared — visitors get fresh pages now'); qc.invalidateQueries(); } catch (e) { toast(e.message, 'critical'); } finally { setBusy(''); }
  };
  const recover = async () => {
    setBusy('recover');
    try {
      const out = await api('/system/recover', { method: 'POST' });
      setSteps(out.steps);
      toast(out.ok ? 'Recovery finished — everything is back in order' : 'Recovery finished with a problem — see below', out.ok ? 'good' : 'critical');
      qc.invalidateQueries();
    } catch (e) { toast(e.message, 'critical'); } finally { setBusy(''); }
  };

  return (
    <section className="st-section" aria-labelledby="sys-h">
      <div className="st-head"><div><h1 id="sys-h">System</h1><p className="st-muted">Maintenance tools. None of them restart the server or log anyone out.</p></div></div>

      {health.isLoading ? <Loading /> : health.isError ? <ErrorState error={health.error} retry={health.refetch} /> : (
        <div className="st-kpis">
          <Kpi label="Database" value={h.database ? 'OK' : 'Problem'} sub={h.database_engine} tone={h.database ? 'good' : 'critical'} />
          <Kpi label="Cache" value={h.cache ? 'OK' : 'Problem'} sub={h.cache_backend} tone={h.cache ? 'good' : 'critical'} />
          <Kpi label="Website build" value={h.frontend_built ? 'OK' : 'Missing'} tone={h.frontend_built ? 'good' : 'critical'} sub={h.debug ? 'Debug mode ON' : 'Production mode'} />
          <Kpi label="Products" value={num(h.counts.Product)} sub={`${num(h.counts.Category)} categories`} />
          <Kpi label="Orders" value={num(h.counts.Order)} sub={`${num(h.counts.LeadInquiry)} enquiries`} />
          <Kpi label="Accounts" value={num(h.counts.User)} />
        </div>
      )}

      <div className="st-cards st-cards--3">
        <article className="st-card">
          <h2 className="st-h3"><RefreshCw size={17} aria-hidden="true" /> Clear cache</h2>
          <p className="st-muted">Use when a change in the Designer doesn't show on the website yet.</p>
          <Button busy={busy === 'clear'} onClick={clear}>Clear cache</Button>
        </article>
        <article className="st-card">
          <h2 className="st-h3"><Wrench size={17} aria-hidden="true" /> One-click recovery</h2>
          <p className="st-muted">Clears caches, re-checks every stock alert and website stock label, marks overdue invoices, removes expired sessions, lifts login lockouts and checks the database.</p>
          <Button busy={busy === 'recover'} onClick={recover}>Run recovery</Button>
        </article>
        <article className="st-card st-card--danger">
          <h2 className="st-h3"><Trash2 size={17} aria-hidden="true" /> Reset site</h2>
          <p className="st-muted">Factory reset of content and settings. Accounts are always kept. Needs RESET + your password.</p>
          <Button variant="danger" onClick={() => setResetting(true)}>Reset site…</Button>
        </article>
      </div>

      {steps && (
        <div className="st-card">
          <h2 className="st-h3">Last recovery</h2>
          <ul className="st-steps">
            {steps.map((s) => (
              <li key={s.label}>
                {s.ok ? <CheckCircle2 size={16} className="st-ok" aria-label="Done" /> : <XCircle size={16} className="st-bad" aria-label="Failed" />}
                {' '}{s.label} <span className="st-muted">· {s.detail} · {s.ms} ms</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {h?.backups?.length > 0 && (
        <div className="st-card">
          <h2 className="st-h3">Recent backups on the server</h2>
          <ul>{h.backups.map((b) => <li key={b.name}><code>{b.name}</code> <Badge>{num(b.size_kb)} KB</Badge></li>)}</ul>
          <p className="st-hint">Restore with: <code>python manage.py loaddata backups/&lt;file&gt;</code> (ask your developer).</p>
        </div>
      )}
      {resetting && <ResetModal onClose={() => setResetting(false)} />}
    </section>
  );
}
