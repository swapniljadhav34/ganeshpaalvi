// Static-website data source: the JSON files written by `manage.py export_static_site`,
// with the catalog's search, filters, sorting and paging done in the browser.
import { ApiError } from './client';

const PAGE_SIZE = 24;

async function load(path, signal) {
  let res;
  try {
    res = await fetch(`/data/${path}`, { signal });
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    throw new ApiError("We couldn't load the shop. Please check your connection.", 0);
  }
  if (!res.ok) throw new ApiError(res.status === 404 ? 'Not found.' : 'Something went wrong. Please try again.', res.status);
  return res.json();
}

let catalog;
const loadCatalog = () => {
  catalog ||= load('products.json').catch((err) => { catalog = undefined; throw err; });
  return catalog;
};

const csv = (v) => String(v || '').split(',').map((x) => x.trim().toLowerCase()).filter(Boolean).slice(0, 5);

function matches(p, f, categories) {
  if (f.category && !(categories[f.category] || []).includes(p.category?.slug)) return false;
  const badges = p.badges.map((b) => b.slug);
  if (!csv(f.badge).every((b) => badges.includes(b))) return false;
  if (!csv(f.suitable_for).every((x) => p._f.suit.includes(x))) return false;
  if (!csv(f.variant).every((x) => p._f.v.includes(x.replace('=', ':')))) return false;
  if (f.featured && !p.is_featured) return false;
  if (f.q) {
    const q = String(f.q).trim().toLowerCase();
    const words = q.split(/\s+/).filter((w) => w.length > 1).slice(0, 6);
    if (!(words.length ? words : [q]).every((w) => p._f.s.includes(w))) return false;
  }
  return true;
}

export const staticBootstrap = ({ signal } = {}) => load('bootstrap.json', signal);

// Some hosts show the share page's real file name (/p/<slug>.html) in the address bar.
export const staticProduct = (slug, { signal } = {}) =>
  load(`products/${encodeURIComponent(slug.replace(/\.html$/, ''))}.json`, signal);

export async function staticProducts(params = {}) {
  const { items, categories } = await loadCatalog();
  let rows = items.filter((p) => matches(p, params, categories));
  if (params.sort === 'newest') rows = [...rows].sort((a, b) => b._f.c.localeCompare(a._f.c));
  if (params.sort === 'bestseller') rows = [...rows].sort((a, b) => b.is_bestseller - a.is_bestseller);
  const page = Number(params.page) || 1;
  const start = (page - 1) * PAGE_SIZE;
  return {
    items: rows.slice(start, start + PAGE_SIZE),
    page,
    has_next: rows.length > start + PAGE_SIZE,
    total: page === 1 ? rows.length : null,
  };
}
