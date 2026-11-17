// Paalvi Studio — live preview + visual pickers for shapes, animations and hero layouts.
// Sends the form's current (unsaved) values to the website preview frame on every change.
(function () {
  const panel = document.getElementById('pv-preview');
  const regEl = document.getElementById('pv-registry');
  if (!panel || !regEl) return;
  const REG = JSON.parse(regEl.textContent);
  const frame = panel.querySelector('iframe');
  const stage = panel.querySelector('.pv-preview-stage');
  const scaler = panel.querySelector('.pv-preview-scale');
  const openBtn = document.getElementById('pv-preview-open');
  const origin = new URL(panel.dataset.origin, location.href).origin;
  const kind = panel.dataset.kind;
  const form = document.querySelector('form[id$="_form"]') || panel.closest('form');
  const store = { get: (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } },
                  set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* private mode */ } } };

  // ---- Device sizes (the frame is scaled down to fit the panel) ----
  const DEVICES = { phone: [390, 760], tablet: [820, 1000], desktop: [1366, 820] };
  let device = store.get('pv-device', 'phone');
  function layout() {
    const [w, h] = DEVICES[device];
    const avail = stage.clientWidth || 360;
    const s = Math.min(1, avail / w);
    frame.style.width = w + 'px';
    frame.style.height = h + 'px';
    scaler.style.transform = `scale(${s})`;
    scaler.style.width = w + 'px';
    stage.style.height = Math.round(h * s) + 'px';
    panel.querySelectorAll('[data-device]').forEach((b) => b.classList.toggle('on', b.dataset.device === device));
  }
  panel.querySelectorAll('[data-device]').forEach((b) => b.addEventListener('click', () => {
    device = b.dataset.device; store.set('pv-device', device); layout();
  }));
  window.addEventListener('resize', layout);

  // ---- Hide / show ----
  function setHidden(h) {
    panel.hidden = h; openBtn.hidden = !h; store.set('pv-hidden', h ? '1' : '0');
    document.body.classList.toggle('pv-has-preview', !h);
    if (!h) layout();
  }
  panel.querySelector('[data-action=toggle]').addEventListener('click', () => setHidden(true));
  openBtn.addEventListener('click', () => setHidden(false));
  setHidden(store.get('pv-hidden', '0') === '1');

  // ---- Collect form values ----
  function collect() {
    const out = {};
    if (!form) return out;
    for (const el of form.elements) {
      const n = el.name;
      if (!n || n.includes('-') || n === 'csrfmiddlewaretoken' || el.type === 'file' || el.type === 'hidden' || el.type === 'submit') continue;
      if (el.type === 'checkbox') out[n] = el.checked;
      else if (el.type === 'radio') { if (el.checked) out[n] = el.value; }
      else if (el.multiple) continue;
      else out[n] = el.value;
    }
    return out;
  }
  const send = (msg) => frame.contentWindow && frame.contentWindow.postMessage(msg, origin);
  const push = () => send({ type: 'paalvi:preview', kind, fields: collect() });
  let t;
  const schedule = () => { clearTimeout(t); t = setTimeout(push, 180); };
  if (form) { form.addEventListener('input', schedule); form.addEventListener('change', schedule); }
  window.addEventListener('message', (e) => {
    if (e.origin === origin && e.data && e.data.type === 'paalvi:ready') push();
  });
  frame.addEventListener('load', () => setTimeout(push, 300));
  panel.querySelector('[data-action=replay]').addEventListener('click', () => send({ type: 'paalvi:replay' }));

  // ---- Visual pickers ----
  const kebab = (k) => k.replace(/^Webkit/, '-webkit-').replace(/[A-Z]/g, (m) => '-' + m.toLowerCase());
  const applyCss = (el, css) => Object.entries(css || {}).forEach(([k, v]) => el.style.setProperty(kebab(k), v));

  function addShapePicker(select) {
    const box = document.createElement('div');
    box.className = 'pv-shapes';
    [...select.options].forEach((opt) => {
      const tile = document.createElement('button');
      tile.type = 'button';
      tile.className = 'pv-shape';
      tile.title = opt.text;
      const swatch = document.createElement('span');
      swatch.className = 'pv-shape-swatch';
      const def = REG.shapes[opt.value];
      if (def) { applyCss(swatch, def.css); if (def.square) swatch.style.aspectRatio = '1'; } else swatch.textContent = 'Site';
      const label = document.createElement('span');
      label.textContent = opt.value ? opt.text : 'Site default';
      tile.append(swatch, label);
      tile.addEventListener('click', () => { select.value = opt.value; select.dispatchEvent(new Event('change', { bubbles: true })); mark(); });
      box.appendChild(tile);
    });
    const mark = () => [...box.children].forEach((c, i) => c.classList.toggle('on', select.options[i].value === select.value));
    select.addEventListener('change', mark);
    mark();
    select.insertAdjacentElement('afterend', box);
  }

  function keyframe(o) {
    const t = [];
    if (o.transformPerspective) t.push(`perspective(${o.transformPerspective}px)`);
    if (o.x != null) t.push(`translateX(${o.x}px)`);
    if (o.y != null) t.push(`translateY(${o.y}px)`);
    if (o.scale != null) t.push(`scale(${o.scale})`);
    if (o.rotate != null) t.push(`rotate(${o.rotate}deg)`);
    if (o.rotateX != null) t.push(`rotateX(${o.rotateX}deg)`);
    if (o.rotateY != null) t.push(`rotateY(${o.rotateY}deg)`);
    if (o.skewY != null) t.push(`skewY(${o.skewY}deg)`);
    const k = { transform: t.join(' ') || 'none' };
    ['opacity', 'filter', 'clipPath'].forEach((p) => { if (o[p] != null) k[p] = o[p]; });
    return k;
  }

  function addEntranceDemo(select) {
    const wrap = document.createElement('div');
    wrap.className = 'pv-anim-demo';
    const tile = document.createElement('div');
    tile.className = 'pv-anim-tile';
    tile.textContent = 'Aa';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = '▶ Play';
    const play = () => {
      const def = REG.entrances[select.value];
      if (!def || !Object.keys(def.from).length) return;
      tile.animate([keyframe(def.from), keyframe(def.to)], { duration: 900, easing: 'cubic-bezier(0.22, 1, 0.36, 1)' });
    };
    btn.addEventListener('click', play);
    select.addEventListener('change', play);
    wrap.append(tile, btn);
    select.insertAdjacentElement('afterend', wrap);
  }

  function addLayoutPicker(select) {
    const box = document.createElement('div');
    box.className = 'pv-layouts';
    const help = document.createElement('p');
    help.className = 'pv-layout-help';
    [...select.options].forEach((opt) => {
      const def = REG.layouts[opt.value];
      if (!def) return;
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'pv-layout';
      b.dataset.value = opt.value;
      b.innerHTML = `<i class="pv-thumb pv-thumb-${opt.value}"></i><span></span>`;
      b.querySelector('span').textContent = def.label;
      b.title = def.help;
      b.addEventListener('click', () => { select.value = opt.value; select.dispatchEvent(new Event('change', { bubbles: true })); mark(); });
      box.appendChild(b);
    });
    const mark = () => {
      [...box.children].forEach((c) => c.classList.toggle('on', c.dataset.value === select.value));
      const def = REG.layouts[select.value];
      help.textContent = def ? `${def.help} Best with: ${def.media}.` : '';
    };
    select.addEventListener('change', mark);
    mark();
    select.insertAdjacentElement('afterend', box);
    box.insertAdjacentElement('afterend', help);
  }

  if (form) {
    form.querySelectorAll('select').forEach((s) => {
      if (!s.name || s.name.includes('-')) return;
      if (/shape$/.test(s.name) && !/decor|divider/.test(s.name)) addShapePicker(s);
      else if (/entrance/.test(s.name)) addEntranceDemo(s);
      else if (s.name === 'layout' || s.name === 'hero_layout') addLayoutPicker(s);
    });
  }
  layout();
})();
