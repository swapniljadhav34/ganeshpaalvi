// First-party, cookie-free page-view counting (see backend ops/analytics.py).
// Sends a tiny beacon on every route change; never blocks the page; honours "Do Not Track".
import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useSite } from '../context/SiteContext';

const BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');

function tabId() {
  try {
    let id = sessionStorage.getItem('paalvi:sid');
    if (!id) {
      id = crypto.getRandomValues(new Uint32Array(4)).join('-');
      sessionStorage.setItem('paalvi:sid', id);
    }
    return id;
  } catch {
    return '';
  }
}

function send(payload) {
  const url = `${BASE}/api/analytics/track`;
  const body = JSON.stringify(payload);
  try {
    if (navigator.sendBeacon && navigator.sendBeacon(url, new Blob([body], { type: 'application/json' }))) return;
  } catch { /* fall through */ }
  fetch(url, { method: 'POST', body, headers: { 'Content-Type': 'application/json' }, keepalive: true }).catch(() => {});
}

export function usePageTracking() {
  const location = useLocation();
  const { tier } = useSite();
  useEffect(() => {
    if (navigator.doNotTrack === '1' || window.doNotTrack === '1') return;
    const { pathname, search } = location;
    if (pathname.startsWith('/studio') || pathname.startsWith('/__preview')) return;
    const params = new URLSearchParams(search);
    const t = setTimeout(() => send({
      path: pathname,
      referrer: document.referrer || '',
      tier,
      sid: tabId(),
      category: params.get('category') || '',
    }), 400);
    return () => clearTimeout(t);
  }, [location.pathname, location.search]); // eslint-disable-line react-hooks/exhaustive-deps
}
