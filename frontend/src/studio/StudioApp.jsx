// Studio — the staff app at /studio. Separate from the storefront and lazily loaded.
// Each person sees only the tabs their role allows; the server re-checks every request.
import { useQuery } from '@tanstack/react-query';
import { Bell, Boxes, ClipboardList, Contact, ExternalLink, Factory, IndianRupee, LineChart, LogOut, MessageSquareText, Palette, Server, Shapes, Users } from 'lucide-react';
import { useState } from 'react';
import { Helmet } from 'react-helmet-async';
import { Navigate, NavLink, Route, Routes, useParams } from 'react-router-dom';
import { api } from './api';
import { AuthProvider, useAuth } from './auth';
import AlertsDrawer from './tabs/AlertsDrawer';
import Accounting from './tabs/Accounting';
import Catalog3D from './tabs/Catalog3D';
import Directory from './tabs/Directory';
import Inquiries from './tabs/Inquiries';
import Inventory from './tabs/Inventory';
import Orders from './tabs/Orders';
import Production from './tabs/Production';
import System from './tabs/System';
import Team from './tabs/Team';
import Traffic from './tabs/Traffic';
import { Button, Field, Loading, ToastProvider } from './ui';
import { readStore, writeStore } from '../utils/storage';
import './studio.css';

const TABS = {
  orders: { icon: ClipboardList, Cmp: Orders },
  inventory: { icon: Boxes, Cmp: Inventory },
  production: { icon: Factory, Cmp: Production },
  inquiries: { icon: MessageSquareText, Cmp: Inquiries },
  accounting: { icon: IndianRupee, Cmp: Accounting },
  catalog: { icon: Shapes, Cmp: Catalog3D },
  traffic: { icon: LineChart, Cmp: Traffic },
  directory: { icon: Contact, Cmp: Directory },
  team: { icon: Users, Cmp: Team },
  system: { icon: Server, Cmp: System },
};

// The brand name comes from the server (Brand & contact details); remembered so the sign-in screen can show it.
const rememberedBrand = () => (readStore('site:brand-name', '') || '').toUpperCase();

function Login() {
  const { login } = useAuth();
  const [form, setForm] = useState({ username: '', password: '' });
  const [state, setState] = useState({ busy: false, error: '' });
  const submit = async (e) => {
    e.preventDefault();
    setState({ busy: true, error: '' });
    try {
      await login(form.username, form.password);
    } catch (err) {
      setState({ busy: false, error: err.message });
    }
  };
  return (
    <main className="st-login">
      <form className="st-login-card" onSubmit={submit}>
        {rememberedBrand() && <p className="st-wordmark">{rememberedBrand()}</p>}
        <h1>Studio sign in</h1>
        <p className="st-muted">For the team. Your role decides what you can see.</p>
        <Field label="Username">
          <input className="st-input" autoComplete="username" value={form.username} required data-autofocus
            onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))} />
        </Field>
        <Field label="Password">
          <input className="st-input" type="password" autoComplete="current-password" value={form.password} required
            onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} />
        </Field>
        {state.error && <p className="st-error" role="alert">{state.error}</p>}
        <Button type="submit" busy={state.busy} className="st-btn--block">Sign in</Button>
      </form>
    </main>
  );
}

function TabPage() {
  const { tab } = useParams();
  const { me } = useAuth();
  const allowed = me.tabs.some((t) => t.key === tab);
  if (!TABS[tab]) return <Navigate to="/studio" replace />;
  if (!allowed) return <div className="st-state st-state--error">You don't have access to this area. Ask the owner if you need it.</div>;
  const { Cmp } = TABS[tab];
  return <Cmp />;
}

function Shell() {
  const { me, can, logout } = useAuth();
  const [alertsOpen, setAlertsOpen] = useState(false);
  const alerts = useQuery({
    queryKey: ['studio', 'alerts'],
    queryFn: () => api('/inventory/alerts'),
    enabled: can('inventory.view'),
    refetchInterval: 60_000,
  });
  const alertCount = alerts.data?.alerts?.length || 0;
  const first = me.tabs[0]?.key;
  if (me.brand !== undefined) writeStore('site:brand-name', me.brand || '');

  return (
    <div className="st-app">
      <aside className="st-side" aria-label="Studio sections">
        <p className="st-wordmark">{(me.brand || '').toUpperCase()} <span>Studio</span></p>
        <nav>
          {me.tabs.map(({ key, label }) => {
            const Icon = TABS[key]?.icon || Boxes;
            return (
              <NavLink key={key} to={`/studio/${key}`} className={({ isActive }) => `st-nav ${isActive ? 'is-on' : ''}`}>
                <Icon size={18} strokeWidth={1.75} aria-hidden="true" /> <span>{label}</span>
              </NavLink>
            );
          })}
        </nav>
        <div className="st-side-foot">
          {me.designer_url && <a className="st-nav" href={me.designer_url} target="_blank" rel="noopener"><Palette size={16} /> <span>Designer</span></a>}
          <a className="st-nav" href={me.site_url || '/'} target="_blank" rel="noopener"><ExternalLink size={16} /> <span>View website</span></a>
        </div>
      </aside>

      <div className="st-main">
        <header className="st-top">
          <div>
            <strong>{me.user.name}</strong>
            <span className="st-muted"> · {me.role_label}</span>
          </div>
          <div className="st-top-actions">
            {can('inventory.view') && (
              <button type="button" className="st-icon st-bell" onClick={() => setAlertsOpen(true)}
                aria-label={`Stock alerts: ${alertCount} active`}>
                <Bell size={18} />
                {alertCount > 0 && <span className="st-bell-n" aria-hidden="true">{alertCount > 99 ? '99+' : alertCount}</span>}
              </button>
            )}
            <Button variant="ghost" size="sm" onClick={logout}><LogOut size={15} /> Sign out</Button>
          </div>
        </header>
        <main className="st-content">
          <Routes>
            <Route index element={first ? <Navigate to={`/studio/${first}`} replace /> : <div className="st-state">No areas are assigned to your role yet.</div>} />
            <Route path=":tab" element={<TabPage />} />
          </Routes>
        </main>
      </div>
      <AlertsDrawer open={alertsOpen} onClose={() => setAlertsOpen(false)} alerts={alerts} />
    </div>
  );
}

function Gate() {
  const { me, loading } = useAuth();
  if (loading) return <Loading label="Opening Studio…" />;
  return me ? <Shell /> : <Login />;
}

export default function StudioApp() {
  return (
    <AuthProvider>
      <ToastProvider>
        <Helmet><title>Studio</title><meta name="robots" content="noindex, nofollow" /></Helmet>
        <Routes>
          <Route path="/studio/*" element={<Gate />} />
          <Route path="*" element={<Gate />} />
        </Routes>
      </ToastProvider>
    </AuthProvider>
  );
}
