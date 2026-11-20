// Tiny fetch wrapper for the Django API. All site content comes from here.
import { STATIC_SITE } from '../staticSite';
import { staticBootstrap, staticProduct, staticProducts } from './staticData';

const BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, { method = 'GET', body, signal, keepalive } = {}) {
  let res;
  try {
    res = await fetch(`${BASE}/api${path}`, {
      method,
      signal,
      keepalive,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    throw new ApiError("We couldn't reach the shop. Please check your connection.", 0);
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(errorMessage(data), res.status);
  return data;
}

/** The API's message in plain words. Validation errors arrive as a list: show the first one. */
export function errorMessage(data) {
  if (typeof data?.detail === 'string') return data.detail;
  if (Array.isArray(data?.detail) && data.detail[0]?.msg) {
    return String(data.detail[0].msg).replace(/^Value error, /, '');
  }
  return 'Something went wrong. Please try again.';
}

/** Turn a filters object into ?a=1&b=2, skipping empty values. */
export function toQuery(params = {}) {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === '' || v === false) return;
    qs.set(k, Array.isArray(v) ? v.join(',') : String(v));
  });
  const s = qs.toString();
  return s ? `?${s}` : '';
}

const noServer = () => Promise.reject(new ApiError('This is not available on this website. Please contact us on WhatsApp.', 0));

export const fetchPreview = (token) => request(`/preview?token=${encodeURIComponent(token)}`);
export const fetchBootstrap = STATIC_SITE ? staticBootstrap : ({ signal } = {}) => request('/bootstrap', { signal });
export const fetchProducts = STATIC_SITE ? staticProducts : (params, { signal } = {}) => request(`/products${toQuery(params)}`, { signal });
export const fetchProduct = STATIC_SITE ? staticProduct : (slug, { signal } = {}) => request(`/products/${encodeURIComponent(slug)}`, { signal });
export const askGuide = (payload) => (STATIC_SITE ? noServer() : request('/ai-guide', { method: 'POST', body: payload }));
export const sendInquiry = (payload) => (STATIC_SITE ? noServer() : request('/inquiry', { method: 'POST', body: payload, keepalive: true }));
export const trackOrder = (number, phone) => request(`/orders/track${toQuery({ number, phone })}`);
export const trackOrderByLink = (token, { signal } = {}) => request(`/orders/track/${encodeURIComponent(token)}`, { signal });
export const receiptUrl = (token, size = 'a4') => `${BASE}/api/orders/track/${encodeURIComponent(token)}/receipt?size=${size}`;
