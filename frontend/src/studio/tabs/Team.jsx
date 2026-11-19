// Team (super admin only): add staff with a role, change roles, block access, reset passwords.
// Temporary passwords are shown once — share them privately and ask the person to change it.
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
import { useState } from 'react';
import { api } from '../api';
import { useAuth } from '../auth';
import { Badge, Button, Empty, ErrorState, Field, Loading, Modal, useToast, when } from '../ui';

function Secret({ password, who, onClose }) {
  return (
    <Modal open onClose={onClose} title={`Temporary password for ${who}`} footer={<Button onClick={onClose}>Done</Button>}>
      <p>Share this privately (not in a group chat). It is shown only once.</p>
      <p className="st-secret"><code>{password}</code></p>
      <p className="st-hint">They sign in at <strong>{window.location.origin}/studio</strong>.</p>
    </Modal>
  );
}

function AddPerson({ roles, onClose, onSecret }) {
  const qc = useQueryClient();
  const [f, setF] = useState({ username: '', first_name: '', email: '', role: 'EMPLOYEE_OPS' });
  const [state, setState] = useState({ busy: false, error: '' });
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }));
  const save = async () => {
    setState({ busy: true, error: '' });
    try {
      const res = await api('/team', { method: 'POST', body: f });
      qc.invalidateQueries({ queryKey: ['studio', 'team'] });
      onSecret({ password: res.temporary_password, who: res.person.username });
      onClose();
    } catch (e) { setState({ busy: false, error: e.message }); }
  };
  return (
    <Modal open onClose={onClose} title="Add a team member"
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button busy={state.busy} onClick={save}>Add</Button></>}>
      <div className="st-grid2">
        <Field label="Username" hint="Letters, numbers and . _ - only"><input className="st-input" value={f.username} onChange={set('username')} data-autofocus /></Field>
        <Field label="Name"><input className="st-input" value={f.first_name} onChange={set('first_name')} /></Field>
        <Field label="Email (optional)"><input className="st-input" type="email" value={f.email} onChange={set('email')} /></Field>
        <Field label="Role"><select className="st-input" value={f.role} onChange={set('role')}>{roles.map((r) => <option key={r.key} value={r.key}>{r.label}</option>)}</select></Field>
      </div>
      {state.error && <p className="st-error" role="alert">{state.error}</p>}
    </Modal>
  );
}

export default function Team() {
  const { me } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const res = useQuery({ queryKey: ['studio', 'team'], queryFn: () => api('/team') });
  const [adding, setAdding] = useState(false);
  const [secret, setSecret] = useState(null);
  const call = async (fn, msg) => {
    try { const out = await fn(); toast(msg); qc.invalidateQueries({ queryKey: ['studio', 'team'] }); return out; } catch (e) { toast(e.message, 'critical'); return null; }
  };
  return (
    <section className="st-section" aria-labelledby="tm-h">
      <div className="st-head">
        <div><h1 id="tm-h">Team & settings</h1><p className="st-muted">Each role only sees its own tabs. Only super admins can open site settings.</p></div>
        <div className="st-actions">
          {me.admin_url && <a className="st-btn st-btn--ghost" href={me.admin_url} target="_blank" rel="noopener">Open site admin ↗</a>}
          <Button onClick={() => setAdding(true)}><Plus size={16} /> Add person</Button>
        </div>
      </div>
      {res.isLoading ? <Loading /> : res.isError ? <ErrorState error={res.error} retry={res.refetch} /> : res.data.people.length === 0 ? <Empty title="No staff yet" /> : (
        <div className="st-table-wrap">
          <table className="st-table st-table--cards">
            <thead><tr><th>Person</th><th>Role</th><th>Access</th><th>Last sign-in</th><th><span className="st-sr">Actions</span></th></tr></thead>
            <tbody>{res.data.people.map((p) => {
              const self = p.id === me.user.id;
              return (
                <tr key={p.id}>
                  <td data-label="Person"><strong>{p.name || p.username}</strong><br /><span className="st-muted">{p.username}{p.email && ` · ${p.email}`}</span></td>
                  <td data-label="Role">
                    {self ? p.role_label : (
                      <select className="st-input" value={p.role || ''} aria-label={`Role for ${p.username}`}
                        onChange={(e) => call(() => api(`/team/${p.id}`, { method: 'PATCH', body: { role: e.target.value } }), 'Role updated')}>
                        {res.data.roles.map((r) => <option key={r.key} value={r.key}>{r.label}</option>)}
                      </select>
                    )}
                  </td>
                  <td data-label="Access">{p.active ? <Badge tone="good">Active</Badge> : <Badge tone="critical">Blocked</Badge>}</td>
                  <td data-label="Last sign-in">{p.last_login ? when(p.last_login) : 'Never'}</td>
                  <td data-label="Actions">
                    {!self && (
                      <div className="st-row-actions">
                        <Button size="sm" variant="ghost" onClick={() => call(() => api(`/team/${p.id}`, { method: 'PATCH', body: { active: !p.active } }), p.active ? 'Access blocked' : 'Access restored')}>
                          {p.active ? 'Block' : 'Restore'}
                        </Button>
                        <Button size="sm" variant="ghost" onClick={async () => {
                          const out = await call(() => api(`/team/${p.id}/reset-password`, { method: 'POST' }), 'Password reset');
                          if (out) setSecret({ password: out.temporary_password, who: p.username });
                        }}>Reset password</Button>
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}</tbody>
          </table>
        </div>
      )}
      {adding && <AddPerson roles={res.data?.roles || []} onClose={() => setAdding(false)} onSecret={setSecret} />}
      {secret && <Secret {...secret} onClose={() => setSecret(null)} />}
    </section>
  );
}
