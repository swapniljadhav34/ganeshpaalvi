// Loads Google's <model-viewer> web component (and three.js inside it) only when a 3D model
// is actually about to be shown — the rest of the site never downloads it.
let loading = null;

export function loadModelViewer() {
  if (typeof window === 'undefined') return Promise.reject(new Error('no window'));
  if (window.customElements?.get('model-viewer')) return Promise.resolve();
  if (!loading) {
    loading = import('@google/model-viewer').then(() => window.customElements.whenDefined('model-viewer'));
    loading.catch(() => { loading = null; });
  }
  return loading;
}

let webgl;
/** Can this browser draw 3D at all? (Old phones / disabled GPU → show the 2D picture instead.) */
export function supportsWebGL() {
  if (webgl !== undefined) return webgl;
  try {
    const c = document.createElement('canvas');
    webgl = Boolean(window.WebGLRenderingContext && (c.getContext('webgl2') || c.getContext('webgl')));
  } catch {
    webgl = false;
  }
  return webgl;
}
