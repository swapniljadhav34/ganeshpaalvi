// Small shared building blocks for Paalvi Studio (accessible modal, badges, fields, states, toasts).
import { AlertTriangle, Loader2, X } from 'lucide-react';
import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';

const inr = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2, maximumFractionDigits: 2 });
const inr0 = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 });
const int = new Intl.NumberFormat('en-IN');
export const money = (v, whole = false) => (v === null || v === undefined || v === '' ? '—' : (whole ? inr0 : inr).format(Number(v)));
export const num = (v) => (v === null || v === undefined ? '—' : int.format(Number(v)));
export const day = (v) => (v ? new Date(v).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—');
export const when = (v) => (v ? new Date(v).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—');
export const isoDay = (d) => {
  const x = new Date(d);
  return `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, '0')}-${String(x.getDate()).padStart(2, '0')}`;
};

export const ALERT_TONE = { OUT_OF_STOCK: 'critical', PRODUCTION_NEEDED: 'serious', EXPIRING_SOON: 'warn', LOW_STOCK: 'warn' };
export const PAY_TONE = { PAID: 'good', PARTIAL: 'info', UNPAID: 'neutral', OVERDUE: 'critical' };

export function Badge({ tone = 'neutral', children, title }) {
  return <span className={`st-badge st-badge--${tone}`} title={title}>{children}</span>;
}

export function Button({ variant = 'primary', size, busy, children, className = '', ...rest }) {
  return (
    <button type="button" className={`st-btn st-btn--${variant} ${size === 'sm' ? 'st-btn--sm' : ''} ${className}`} disabled={busy || rest.disabled} {...rest}>
      {busy && <Loader2 size={15} className="st-spin" aria-hidden="true" />}
      {children}
    </button>
  );
}

export function Field({ label, hint, error, children, full }) {
  return (
    <label className={`st-field ${full ? 'st-field--full' : ''}`}>
      <span className="st-label">{label}</span>
      {children}
      {hint && !error && <span className="st-hint">{hint}</span>}
      {error && <span className="st-error" role="alert">{error}</span>}
    </label>
  );
}

export function Modal({ open, title, onClose, children, footer, wide = false }) {
  const ref = useRef(null);
  const back = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    back.current = document.activeElement;
    const el = ref.current;
    const focusables = () => [...el.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')]
      .filter((n) => !n.disabled && n.offsetParent !== null);
    (el.querySelector('[data-autofocus]') || focusables()[1] || el).focus();
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
      if (e.key === 'Tab') { // keep keyboard focus inside the dialog
        const f = focusables();
        if (!f.length) return;
        if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
        else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
      }
    };
    document.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
      back.current?.focus?.();
    };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="st-modal-wrap" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={ref} className={`st-modal ${wide ? 'st-modal--wide' : ''}`} role="dialog" aria-modal="true" aria-label={title} tabIndex={-1}>
        <header className="st-modal-head">
          <h2>{title}</h2>
          <button type="button" className="st-icon" onClick={onClose} aria-label="Close"><X size={18} /></button>
        </header>
        <div className="st-modal-body">{children}</div>
        {footer && <footer className="st-modal-foot">{footer}</footer>}
      </div>
    </div>
  );
}

export function Loading({ label = 'Loading…' }) {
  return <div className="st-state" role="status"><Loader2 className="st-spin" size={20} aria-hidden="true" /> {label}</div>;
}

export function ErrorState({ error, retry }) {
  return (
    <div className="st-state st-state--error" role="alert">
      <AlertTriangle size={20} aria-hidden="true" />
      <span>{error?.message || 'Something went wrong.'}</span>
      {retry && <Button variant="ghost" size="sm" onClick={() => retry()}>Try again</Button>}
    </div>
  );
}

export function Empty({ title, children }) {
  return <div className="st-state st-state--empty"><strong>{title}</strong>{children && <span>{children}</span>}</div>;
}

export function Kpi({ label, value, sub, tone }) {
  return (
    <div className={`st-kpi ${tone ? `st-kpi--${tone}` : ''}`}>
      <span className="st-kpi-label">{label}</span>
      <span className="st-kpi-value">{value}</span>
      {sub && <span className="st-kpi-sub">{sub}</span>}
    </div>
  );
}

export function Pager({ page, hasNext, onPage }) {
  if (page === 1 && !hasNext) return null;
  return (
    <div className="st-pager">
      <Button variant="ghost" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>← Previous</Button>
      <span>Page {page}</span>
      <Button variant="ghost" size="sm" disabled={!hasNext} onClick={() => onPage(page + 1)}>Next →</Button>
    </div>
  );
}

/** Debounced value — search boxes don't hit the server on every keystroke. */
export function useDebounced(value, ms = 300) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

const ToastCtx = createContext(() => {});
export function ToastProvider({ children }) {
  const [items, setItems] = useState([]);
  const push = useCallback((text, tone = 'good') => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x.slice(-3), { id, text, tone }]);
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), 4200);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="st-toasts" role="status" aria-live="polite">
        {items.map((t) => <div key={t.id} className={`st-toast st-toast--${t.tone}`}>{t.text}</div>)}
      </div>
    </ToastCtx.Provider>
  );
}
export const useToast = () => useContext(ToastCtx);
