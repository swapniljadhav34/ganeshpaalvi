// Catalog & 3D: upload .glb models and posters per product, preview them, and choose which
// ones appear in the homepage 3D hero (and in what order).
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Box, Search, Trash2, Upload } from 'lucide-react';
import { useState } from 'react';
import Product3DViewer from '../../three/Product3DViewer';
import { api, qs } from '../api';
import { Badge, Button, Empty, ErrorState, Field, Loading, Modal, Pager, useDebounced, useToast } from '../ui';

/** Quick checks in the browser (the server checks again): extension, size and the 'glTF' file header. */
async function checkGlb(file, maxMb) {
  if (!/\.glb$/i.test(file.name)) return 'Please choose a .glb file (binary glTF). Export it from Blender as “glTF Binary (.glb)”.';
  if (file.size > maxMb * 1048576) return `This model is ${(file.size / 1048576).toFixed(1)} MB. The limit is ${maxMb} MB — compress it (e.g. gltf.report).`;
  const head = new Uint8Array(await file.slice(0, 4).arrayBuffer());
  if (String.fromCharCode(...head) !== 'glTF') return 'This file is not a valid .glb model.';
  return '';
}

function UploadModal({ product, maxMb, onClose }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [model, setModel] = useState(null);
  const [poster, setPoster] = useState(null);
  const [preview, setPreview] = useState(null);
  const [state, setState] = useState({ busy: false, error: '' });
  const pickModel = async (f) => {
    setModel(null);
    setPreview(null);
    if (!f) return;
    const err = await checkGlb(f, maxMb);
    if (err) return setState({ busy: false, error: err });
    setState({ busy: false, error: '' });
    setModel(f);
    setPreview(URL.createObjectURL(f));
  };
  const save = async () => {
    if (!model && !poster) return setState({ busy: false, error: 'Choose a model and/or a poster image.' });
    if (poster && poster.size > 15 * 1048576) return setState({ busy: false, error: 'The poster must be under 15 MB.' });
    setState({ busy: true, error: '' });
    const form = new FormData();
    if (model) form.append('model', model);
    if (poster) form.append('poster', poster);
    try {
      await api(`/catalog/products/${product.id}/model3d`, { method: 'POST', form });
      toast(`3D media saved for ${product.title}`);
      qc.invalidateQueries({ queryKey: ['studio', 'catalog'] });
      onClose();
    } catch (e) { setState({ busy: false, error: e.message }); }
  };
  return (
    <Modal open onClose={onClose} wide title={`3D model · ${product.title}`}
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button busy={state.busy} onClick={save}><Upload size={15} /> Upload</Button></>}>
      <div className="st-grid2">
        <div>
          <Field label={`3D model (.glb, max ${maxMb} MB)`} hint="Aim for under 5 MB so phones load it quickly.">
            <input className="st-input" type="file" accept=".glb,model/gltf-binary" onChange={(e) => pickModel(e.target.files?.[0])} data-autofocus />
          </Field>
          <Field label="Poster image (optional)" hint="Shown instantly while the model loads. Same angle as the model works best.">
            <input className="st-input" type="file" accept="image/*" onChange={(e) => setPoster(e.target.files?.[0] || null)} />
          </Field>
          {state.error && <p className="st-error" role="alert">{state.error}</p>}
        </div>
        <div className="st-3d-preview">
          {preview || product.model_3d ? (
            <Product3DViewer src={preview || product.model_3d} poster={product.model_poster || product.thumb} alt={`${product.title} preview`} />
          ) : <Empty title="Preview">Choose a .glb file to see it here.</Empty>}
        </div>
      </div>
    </Modal>
  );
}

function Row({ p, onUpload }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [order, setOrder] = useState(String(p.hero_3d_order));
  const [busy, setBusy] = useState(false);
  const call = async (fn, msg) => {
    setBusy(true);
    try { await fn(); toast(msg); qc.invalidateQueries({ queryKey: ['studio', 'catalog'] }); } catch (e) { toast(e.message, 'critical'); } finally { setBusy(false); }
  };
  return (
    <tr>
      <td data-label="Product">
        <div className="st-prod">{p.thumb ? <img src={p.thumb} alt="" width="40" height="50" loading="lazy" /> : <span className="st-prod-ph" />}
          <span><strong>{p.title}</strong><br /><span className="st-muted">{p.sku}{!p.is_active && ' · hidden'}</span></span></div>
      </td>
      <td data-label="3D model">{p.model_3d ? <Badge tone="good"><Box size={12} /> {p.model_size_mb} MB</Badge> : <Badge>None</Badge>}</td>
      <td data-label="3D hero">
        <label className="st-check">
          <input type="checkbox" checked={p.is_hero_3d_featured} disabled={!p.model_3d || busy}
            onChange={(e) => call(() => api(`/catalog/products/${p.id}/hero3d`, { method: 'PATCH', body: { featured: e.target.checked, order: Number(order) || 0 } }),
              e.target.checked ? 'Added to the 3D hero' : 'Removed from the 3D hero')} />
          Show in 3D hero
        </label>
      </td>
      <td data-label="Order">
        <input className="st-input st-w6" inputMode="numeric" value={order} aria-label={`Order for ${p.title}`} disabled={!p.is_hero_3d_featured}
          onChange={(e) => setOrder(e.target.value.replace(/\D/g, ''))}
          onBlur={() => Number(order) !== p.hero_3d_order && call(() => api(`/catalog/products/${p.id}/hero3d`, { method: 'PATCH', body: { featured: true, order: Number(order) || 0 } }), 'Order saved')} />
      </td>
      <td data-label="Actions">
        <div className="st-row-actions">
          <Button size="sm" onClick={() => onUpload(p)}><Upload size={14} /> {p.model_3d ? 'Replace' : 'Upload'}</Button>
          {p.model_3d && <button type="button" className="st-icon" disabled={busy} aria-label={`Remove 3D model from ${p.title}`}
            onClick={() => call(() => api(`/catalog/products/${p.id}/model3d`, { method: 'DELETE' }), '3D model removed')}><Trash2 size={15} /></button>}
        </div>
      </td>
    </tr>
  );
}

export default function Catalog3D() {
  const [q, setQ] = useState('');
  const [has3d, setHas3d] = useState('');
  const [page, setPage] = useState(1);
  const [upload, setUpload] = useState(null);
  const dq = useDebounced(q);
  const res = useQuery({ queryKey: ['studio', 'catalog', dq, has3d, page], queryFn: () => api(`/catalog/products${qs({ q: dq, has3d, page })}`), placeholderData: (p) => p });
  return (
    <section className="st-section" aria-labelledby="c3-h">
      <div className="st-head"><div><h1 id="c3-h">Catalog & 3D</h1>
        <p className="st-muted">Upload 3D models for product pages and pick which ones spin in the homepage 3D hero (lowest order first).</p></div></div>
      <div className="st-filters">
        <label className="st-search"><Search size={16} aria-hidden="true" /><input value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder="Search products" aria-label="Search products" /></label>
        <div className="st-chips" role="radiogroup" aria-label="3D filter">
          {[['', 'All'], ['true', 'With 3D'], ['false', 'Without 3D']].map(([k, l]) => (
            <button key={k || 'all'} type="button" role="radio" aria-checked={has3d === k} className={has3d === k ? 'is-on' : ''} onClick={() => { setHas3d(k); setPage(1); }}>{l}</button>
          ))}
        </div>
      </div>
      {res.isLoading ? <Loading /> : res.isError ? <ErrorState error={res.error} retry={res.refetch} /> : res.data.products.length === 0 ? <Empty title="No products match" /> : (
        <div className="st-table-wrap">
          <table className="st-table st-table--cards">
            <thead><tr><th>Product</th><th>3D model</th><th>3D hero</th><th>Order</th><th><span className="st-sr">Actions</span></th></tr></thead>
            <tbody>{res.data.products.map((p) => <Row key={`${p.id}-${p.model_3d}-${p.hero_3d_order}`} p={p} onUpload={setUpload} />)}</tbody>
          </table>
        </div>
      )}
      {res.data && <Pager page={page} hasNext={res.data.has_next} onPage={setPage} />}
      {upload && <UploadModal product={upload} maxMb={res.data?.max_mb || 20} onClose={() => setUpload(null)} />}
    </section>
  );
}
