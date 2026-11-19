// Team & roles (Admin only).
//  • People: add employees, warehouse & distribution staff and vendors; change role; give one person extra
//    permissions to cover a colleague; block / restore; reset password; delete permanently.
//  • Roles & permissions: the permission matrix. Tick a box and it applies at once, in Studio AND in the
//    Designer workspace. Create your own roles. The Admin role always has everything.
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Search, Trash2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import { api } from '../api';
import { useAuth } from '../auth';
import { Badge, Button, Empty, ErrorState, Field, Loading, Modal, useDebounced, useToast, when } from '../ui';

function Secret({ password, who, onClose }) {
  return (
    <Modal open onClose={onClose} title={`Temporary password for ${who}`} footer={<Button onClick={onClose}>Done</Button>}>
      <p>Share this privately (not in a group chat). It is shown only once.</p>
      <p className="st-secret"><code>{password}</code></p>
      <p className="st-hint">They sign in at <strong>{window.location.origin}/studio</strong>.</p>
    </Modal>
  );
}

function PersonForm({ data, person, onClose, onSecret }) {
  const qc = useQueryClient();
  const toast = useToast();
  const editing = Boolean(person);
  const [f, setF] = useState(() => ({
    username: person?.username || '', first_name: person?.name || '', email: person?.email || '',
    role: person?.role || 'EMPLOYEE_OPS', kind: person?.kind || 'EMPLOYEE', company: person?.company || '',
    phone: person?.phone || '', city: person?.city || '',
  }));
  const [state, setState] = useState({ busy: false, error: '' });
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }));
  const save = async () => {
    setState({ busy: true, error: '' });
    try {
      if (editing) {
        const { username, ...rest } = f; // eslint-disable-line no-unused-vars
        await api(`/team/${person.id}`, { method: 'PATCH', body: person.self ? { first_name: f.first_name, email: f.email, kind: f.kind, company: f.company, phone: f.phone, city: f.city } : rest });
        toast('Saved');
      } else {
        const res = await api('/team', { method: 'POST', body: f });
        onSecret({ password: res.temporary_password, who: res.person.username });
      }
      qc.invalidateQueries({ queryKey: ['studio', 'team'] });
      onClose();
    } catch (e) { setState({ busy: false, error: e.message }); }
  };
  return (
    <Modal open onClose={onClose} title={editing ? `Edit ${person.username}` : 'Add a person'}
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button busy={state.busy} onClick={save}>{editing ? 'Save' : 'Add'}</Button></>}>
      <div className="st-grid2">
        {!editing && <Field label="Username" hint="Letters, numbers and . _ - only"><input className="st-input" value={f.username} onChange={set('username')} data-autofocus /></Field>}
        <Field label="Name"><input className="st-input" value={f.first_name} onChange={set('first_name')} /></Field>
        <Field label="Group" hint="Where they appear in the directory">
          <select className="st-input" value={f.kind} onChange={set('kind')}>{data.kinds.map((k) => <option key={k.key} value={k.key}>{k.label}</option>)}</select>
        </Field>
        {!person?.self && (
          <Field label="Role" hint="Decides what they can open">
            <select className="st-input" value={f.role} onChange={set('role')}>{data.roles.map((r) => <option key={r.key} value={r.key}>{r.label}</option>)}</select>
          </Field>
        )}
        {f.kind === 'VENDOR' && <Field label="Company"><input className="st-input" value={f.company} onChange={set('company')} /></Field>}
        <Field label="Phone"><input className="st-input" type="tel" value={f.phone} onChange={set('phone')} /></Field>
        <Field label="City"><input className="st-input" value={f.city} onChange={set('city')} /></Field>
        <Field label="Email (optional)"><input className="st-input" type="email" value={f.email} onChange={set('email')} /></Field>
      </div>
      {state.error && <p className="st-error" role="alert">{state.error}</p>}
    </Modal>
  );
}

function ExtraPermissions({ data, person, onClose }) {
  const qc = useQueryClient();
  const toast = useToast();
  const role = data.roles.find((r) => r.key === person.role);
  const fromRole = new Set(role?.permissions || []);
  const [picked, setPicked] = useState(() => new Set(person.extra_permissions));
  const [busy, setBusy] = useState(false);
  const toggle = (k) => setPicked((s) => { const n = new Set(s); if (n.has(k)) n.delete(k); else n.add(k); return n; });
  const save = async () => {
    setBusy(true);
    try {
      await api(`/team/${person.id}`, { method: 'PATCH', body: { extra_permissions: [...picked] } });
      qc.invalidateQueries({ queryKey: ['studio', 'team'] });
      toast('Permissions updated');
      onClose();
    } catch (e) { toast(e.message, 'critical'); setBusy(false); }
  };
  return (
    <Modal open wide onClose={onClose} title={`Extra permissions for ${person.name || person.username}`}
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button busy={busy} onClick={save}>Save</Button></>}>
      <p className="st-muted">Their role (<strong>{role?.label}</strong>) already gives the ticked-and-greyed items. Add more to let them cover someone else's work — e.g. a warehouse worker covering accounts for a week.</p>
      {data.permission_groups.map((g) => (
        <fieldset key={g.group} className="st-permgroup">
          <legend>{g.group}</legend>
          {g.items.map((p) => (
            <label key={p.key} className={`st-check ${!p.grantable ? 'is-locked' : ''}`}>
              <input type="checkbox" disabled={!p.grantable || fromRole.has(p.key)} checked={fromRole.has(p.key) || picked.has(p.key)} onChange={() => toggle(p.key)} />
              {p.label}{!p.grantable && <span className="st-muted"> — Admin only</span>}
            </label>
          ))}
        </fieldset>
      ))}
    </Modal>
  );
}

function People({ data }) {
  const { me } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const [edit, setEdit] = useState(null);
  const [extra, setExtra] = useState(null);
  const [secret, setSecret] = useState(null);
  const [q, setQ] = useState('');
  const [kind, setKind] = useState('');
  const dq = useDebounced(q, 150).toLowerCase();
  const roleLabel = Object.fromEntries(data.roles.map((r) => [r.key, r.label]));
  const kindLabel = Object.fromEntries(data.kinds.map((k) => [k.key, k.label]));
  const people = data.people.filter((p) => (!kind || p.kind === kind) && (!dq || `${p.username} ${p.name} ${p.company} ${p.city}`.toLowerCase().includes(dq)));
  const call = async (fn, msg) => {
    try { const out = await fn(); toast(msg); qc.invalidateQueries({ queryKey: ['studio', 'team'] }); return out; } catch (e) { toast(e.message, 'critical'); return null; }
  };
  const remove = (p) => {
    const typed = window.prompt(`Permanently delete ${p.username}? Their past work (orders, stock log, invoices) is kept and shows "deleted user".\n\nType the username to confirm:`);
    if (typed === null) return;
    if (typed.trim() !== p.username) { toast("The username didn't match — nothing was deleted.", 'critical'); return; }
    call(() => api(`/team/${p.id}`, { method: 'DELETE' }), `${p.username} deleted`);
  };
  return (
    <>
      <div className="st-filters">
        <label className="st-search"><Search size={16} aria-hidden="true" /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name, username, company or city" aria-label="Search people" /></label>
        <select className="st-input st-input--auto" value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Group">
          <option value="">Everyone</option>{data.kinds.map((k) => <option key={k.key} value={k.key}>{k.label}</option>)}
        </select>
        <Button onClick={() => setEdit('new')}><Plus size={16} /> Add person</Button>
      </div>
      {people.length === 0 ? <Empty title="Nobody here yet" /> : (
        <div className="st-table-wrap">
          <table className="st-table st-table--cards">
            <thead><tr><th>Person</th><th>Role</th><th>Access</th><th>Last sign-in</th><th><span className="st-sr">Actions</span></th></tr></thead>
            <tbody>{people.map((p) => {
              const self = p.id === me.user.id;
              return (
                <tr key={p.id}>
                  <td data-label="Person"><strong>{p.name || p.username}</strong>{p.company && ` · ${p.company}`}<br />
                    <span className="st-muted">{p.username} · {kindLabel[p.kind]}{p.city && ` · ${p.city}`}</span></td>
                  <td data-label="Role">
                    {self ? <>{p.role_label} <span className="st-muted">(you)</span></> : (
                      <select className="st-input" value={p.role || ''} aria-label={`Role for ${p.username}`}
                        onChange={(e) => call(() => api(`/team/${p.id}`, { method: 'PATCH', body: { role: e.target.value } }), `${p.username} is now ${roleLabel[e.target.value]}`)}>
                        {data.roles.map((r) => <option key={r.key} value={r.key}>{r.label}</option>)}
                      </select>
                    )}
                    {p.extra_permissions.length > 0 && <div className="st-muted">+ {p.extra_permissions.length} extra permission{p.extra_permissions.length > 1 ? 's' : ''}</div>}
                    {p.designer_access && <div><Badge tone="info">Designer workspace</Badge></div>}
                  </td>
                  <td data-label="Access">{p.active ? <Badge tone="good">Active</Badge> : <Badge tone="critical">Blocked</Badge>}</td>
                  <td data-label="Last sign-in">{p.last_login ? when(p.last_login) : 'Never'}</td>
                  <td data-label="Actions">
                    <div className="st-row-actions">
                      <Button size="sm" variant="ghost" onClick={() => setEdit({ ...p, self })}>Edit</Button>
                      {!self && (
                        <>
                          {p.role !== 'SUPER_ADMIN' && <Button size="sm" variant="ghost" onClick={() => setExtra(p)}>Permissions</Button>}
                          <Button size="sm" variant="ghost" onClick={() => call(() => api(`/team/${p.id}`, { method: 'PATCH', body: { active: !p.active } }), p.active ? 'Account disabled' : 'Account enabled')}>
                            {p.active ? 'Disable' : 'Enable'}
                          </Button>
                          <Button size="sm" variant="ghost" onClick={async () => {
                            const out = await call(() => api(`/team/${p.id}/reset-password`, { method: 'POST' }), 'Password reset');
                            if (out) setSecret({ password: out.temporary_password, who: p.username });
                          }}>Reset password</Button>
                          <Button size="sm" variant="ghost" aria-label={`Delete ${p.username}`} onClick={() => remove(p)}><Trash2 size={15} /></Button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}</tbody>
          </table>
        </div>
      )}
      {edit && <PersonForm data={data} person={edit === 'new' ? null : edit} onClose={() => setEdit(null)} onSecret={setSecret} />}
      {extra && <ExtraPermissions data={data} person={extra} onClose={() => setExtra(null)} />}
      {secret && <Secret {...secret} onClose={() => setSecret(null)} />}
    </>
  );
}

function NewRole({ roles, onClose }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [f, setF] = useState({ label: '', description: '', copy_from: '' });
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    try {
      await api('/roles', { method: 'POST', body: { ...f, copy_from: f.copy_from || null, permissions: [] } });
      qc.invalidateQueries({ queryKey: ['studio', 'team'] });
      toast(`Role “${f.label}” created — tick its permissions in the matrix`);
      onClose();
    } catch (e) { toast(e.message, 'critical'); setBusy(false); }
  };
  return (
    <Modal open onClose={onClose} title="New role" footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button busy={busy} onClick={save}>Create</Button></>}>
      <Field label="Name" hint="e.g. Field sales, Packing team"><input className="st-input" value={f.label} onChange={(e) => setF((x) => ({ ...x, label: e.target.value }))} data-autofocus /></Field>
      <Field label="What they do (optional)"><input className="st-input" value={f.description} onChange={(e) => setF((x) => ({ ...x, description: e.target.value }))} /></Field>
      <Field label="Start with the permissions of">
        <select className="st-input" value={f.copy_from} onChange={(e) => setF((x) => ({ ...x, copy_from: e.target.value }))}>
          <option value="">Nothing (start empty)</option>
          {roles.filter((r) => !r.locked).map((r) => <option key={r.key} value={r.key}>{r.label}</option>)}
        </select>
      </Field>
    </Modal>
  );
}

function Matrix({ data }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [busyKey, setBusyKey] = useState('');
  const [adding, setAdding] = useState(false);
  const roles = data.roles;
  const toggle = async (role, perm) => {
    const has = role.permissions.includes(perm);
    const permissions = has ? role.permissions.filter((p) => p !== perm) : [...role.permissions, perm];
    setBusyKey(`${role.key}:${perm}`);
    // Optimistic: tick immediately, roll back on error.
    qc.setQueryData(['studio', 'team'], (old) => old && { ...old, roles: old.roles.map((r) => (r.key === role.key ? { ...r, permissions } : r)) });
    try {
      await api(`/roles/${role.key}`, { method: 'PATCH', body: { permissions } });
      qc.invalidateQueries({ queryKey: ['studio', 'team'] });
    } catch (e) {
      toast(e.message, 'critical');
      qc.invalidateQueries({ queryKey: ['studio', 'team'] });
    } finally { setBusyKey(''); }
  };
  const removeRole = async (r) => {
    if (!window.confirm(`Delete the role “${r.label}”?`)) return;
    try { await api(`/roles/${r.key}`, { method: 'DELETE' }); qc.invalidateQueries({ queryKey: ['studio', 'team'] }); toast('Role deleted'); } catch (e) { toast(e.message, 'critical'); }
  };
  return (
    <>
      <div className="st-filters">
        <p className="st-muted st-grow">Tick a box to give a permission to everyone in that role. Changes apply immediately — in Studio and in the Designer workspace.</p>
        <Button onClick={() => setAdding(true)}><Plus size={16} /> New role</Button>
      </div>
      <div className="st-matrix-wrap" tabIndex={0} aria-label="Permission matrix (scrolls sideways)">
        <table className="st-matrix">
          <thead>
            <tr>
              <th scope="col">Permission</th>
              {roles.map((r) => (
                <th key={r.key} scope="col" title={r.description}>
                  <span>{r.label}</span>
                  <small className="st-muted">{r.people} {r.people === 1 ? 'person' : 'people'}</small>
                  {!r.builtin && !r.locked && <button type="button" className="st-icon st-icon--sm" aria-label={`Delete role ${r.label}`} onClick={() => removeRole(r)}><Trash2 size={13} /></button>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.permission_groups.map((g) => [
              <tr key={g.group} className="st-matrix-group"><th colSpan={roles.length + 1} scope="colgroup">{g.group}</th></tr>,
              ...g.items.map((p) => (
                <tr key={p.key}>
                  <th scope="row">{p.label}</th>
                  {roles.map((r) => {
                    const on = r.locked || r.permissions.includes(p.key);
                    const locked = r.locked || !p.grantable;
                    return (
                      <td key={r.key}>
                        <input type="checkbox" checked={on} disabled={locked || busyKey === `${r.key}:${p.key}`}
                          aria-label={`${r.label}: ${p.label}`} title={r.locked ? 'The Admin always has every permission' : !p.grantable ? 'Admin only' : ''}
                          onChange={() => toggle(r, p.key)} />
                      </td>
                    );
                  })}
                </tr>
              )),
            ])}
          </tbody>
        </table>
      </div>
      {adding && <NewRole roles={roles} onClose={() => setAdding(false)} />}
    </>
  );
}

export default function Team() {
  const { me } = useAuth();
  const [view, setView] = useState('people');
  const res = useQuery({ queryKey: ['studio', 'team'], queryFn: () => api('/team') });
  const counts = useMemo(() => {
    const c = { active: 0, blocked: 0 };
    (res.data?.people || []).forEach((p) => { c[p.active ? 'active' : 'blocked'] += 1; });
    return c;
  }, [res.data]);
  return (
    <section className="st-section" aria-labelledby="tm-h">
      <div className="st-head">
        <div><h1 id="tm-h">Team & roles</h1><p className="st-muted">{counts.active} active · {counts.blocked} disabled. One permission system for Studio and the Designer workspace.</p></div>
        <div className="st-actions">
          <div className="st-chips" role="radiogroup" aria-label="View">
            <button type="button" role="radio" aria-checked={view === 'people'} className={view === 'people' ? 'is-on' : ''} onClick={() => setView('people')}>People</button>
            <button type="button" role="radio" aria-checked={view === 'roles'} className={view === 'roles' ? 'is-on' : ''} onClick={() => setView('roles')}>Roles & permissions</button>
          </div>
          {me.designer_url && <a className="st-btn st-btn--ghost" href={me.designer_url} target="_blank" rel="noopener">Designer ↗</a>}
        </div>
      </div>
      {res.isLoading ? <Loading /> : res.isError ? <ErrorState error={res.error} retry={res.refetch} />
        : view === 'people' ? <People data={res.data} /> : <Matrix data={res.data} />}
    </section>
  );
}
