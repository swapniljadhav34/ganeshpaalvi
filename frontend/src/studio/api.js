// Studio API client: same-origin session cookie + Django CSRF token on every change.
import { ApiError, errorMessage } from '../api/client';

const BASE = `${(import.meta.env.VITE_API_URL || '').replace(/\/$/, '')}/api/staff`;

function csrfToken() {
  const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : '';
}

export async function ensureCsrf() {
  if (!csrfToken()) await fetch(`${BASE}/auth/csrf`, { credentials: 'include' });
}

export async function api(path, { method = 'GET', body, form } = {}) {
  const headers = {};
  if (method !== 'GET') {
    await ensureCsrf();
    headers['X-CSRFToken'] = csrfToken();
  }
  let payload;
  if (form) payload = form; // FormData (file uploads) — the browser sets the content type
  else if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(`${BASE}${path}`, { method, headers, body: payload, credentials: 'include' });
  } catch {
    throw new ApiError("Can't reach the server. Check your connection.", 0);
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status === 401 ? 'Please sign in again.' : errorMessage(data), res.status);
  return data;
}

/** Link for file downloads (CSV, receipts) — the session cookie authorises it. */
export const fileUrl = (path) => `${BASE}${path}`;

export function qs(params = {}) {
  const s = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '' && v !== false) s.set(k, v); });
  const out = s.toString();
  return out ? `?${out}` : '';
}
