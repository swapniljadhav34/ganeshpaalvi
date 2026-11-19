// Reusable 3D product viewer (drag to rotate, pinch/scroll to zoom, auto-rotate toggle).
//  • The poster picture shows instantly in a fixed-ratio box → zero layout shift.
//  • The 3D library loads only when `active` is true (one WebGL canvas on screen at a time).
//  • No WebGL, a load error or reduced motion → a plain 2D picture, never a broken box.
import { Hand, Pause, Play, RotateCcw } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useCalm } from '../hooks/useCalm';
import { loadModelViewer, supportsWebGL } from './modelViewer';
import styles from './Product3DViewer.module.css';

export default function Product3DViewer({
  src, poster, alt = '3D model', active = true, autoRotate: autoRotateInitial = true, className = '', showHint = true, onError,
}) {
  const ref = useRef(null);
  const calm = useCalm();
  const [ready, setReady] = useState(false);     // web component defined
  const [loaded, setLoaded] = useState(false);   // model downloaded & drawn
  const [failed, setFailed] = useState(false);
  const [progress, setProgress] = useState(0);
  const [autoRotate, setAutoRotate] = useState(autoRotateInitial && !calm);
  const [touched, setTouched] = useState(false);

  useEffect(() => {
    if (!active || !src || ready || failed) return;
    if (!supportsWebGL()) { setFailed(true); return; }
    let alive = true;
    loadModelViewer().then(() => alive && setReady(true)).catch(() => alive && setFailed(true));
    return () => { alive = false; };
  }, [active, src, ready, failed]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const onLoad = () => setLoaded(true);
    const onFail = () => { setFailed(true); onError?.(); };
    const onProgress = (e) => setProgress(e.detail?.totalProgress ?? 0);
    const onInteract = () => setTouched(true);
    el.addEventListener('load', onLoad);
    el.addEventListener('error', onFail);
    el.addEventListener('progress', onProgress);
    el.addEventListener('pointerdown', onInteract);
    return () => {
      el.removeEventListener('load', onLoad);
      el.removeEventListener('error', onFail);
      el.removeEventListener('progress', onProgress);
      el.removeEventListener('pointerdown', onInteract);
    };
  }, [ready, active, onError]);

  const reset = () => {
    const el = ref.current;
    if (!el) return;
    el.cameraOrbit = 'auto auto auto';
    el.fieldOfView = 'auto';
    el.resetTurntableRotation?.();
    el.jumpCameraToGoal?.();
  };

  const showModel = active && ready && !failed;
  return (
    <div className={`${styles.viewer} ${className}`} data-loaded={loaded || undefined}>
      {poster && (
        <img src={poster} alt={showModel && loaded ? '' : alt} className={`${styles.poster} ${showModel && loaded ? styles.posterHidden : ''}`}
          decoding="async" draggable="false" />
      )}
      {showModel && (
        <model-viewer
          ref={ref}
          src={src}
          alt={alt}
          camera-controls=""
          touch-action="pan-y"
          interaction-prompt="none"
          shadow-intensity="0.9"
          shadow-softness="0.8"
          exposure="1.05"
          environment-image="neutral"
          auto-rotate={autoRotate && !calm ? '' : undefined}
          auto-rotate-delay="800"
          rotation-per-second="18deg"
          loading="eager"
          reveal="auto"
          style={{ width: '100%', height: '100%', background: 'transparent', '--poster-color': 'transparent', '--progress-bar-height': '0px' }}
        />
      )}
      {showModel && !loaded && (
        <div className={styles.progress} role="progressbar" aria-label="Loading 3D model" aria-valuemin={0} aria-valuemax={100}
          aria-valuenow={Math.round(progress * 100)}>
          <span style={{ transform: `scaleX(${Math.max(0.06, progress)})` }} />
        </div>
      )}
      {showModel && loaded && (
        <div className={styles.controls}>
          {!calm && (
            <button type="button" className={styles.ctrl} onClick={() => setAutoRotate((v) => !v)} aria-pressed={autoRotate}
              aria-label={autoRotate ? 'Stop turning' : 'Turn automatically'}>
              {autoRotate ? <Pause size={15} strokeWidth={1.75} /> : <Play size={15} strokeWidth={1.75} />}
            </button>
          )}
          <button type="button" className={styles.ctrl} onClick={reset} aria-label="Reset view"><RotateCcw size={15} strokeWidth={1.75} /></button>
        </div>
      )}
      {showModel && loaded && showHint && !touched && (
        <span className={styles.hint} aria-hidden="true"><Hand size={14} strokeWidth={1.75} /> Drag to rotate · pinch to zoom</span>
      )}
      <span className={styles.badge} aria-hidden="true">3D</span>
    </div>
  );
}
