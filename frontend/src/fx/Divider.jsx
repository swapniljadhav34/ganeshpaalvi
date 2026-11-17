// Shaped edge between two blocks (wave, curve, tilt, zigzag, arch, drips, hills, scallops).
// Drawn in the block's own background colour so it "rises" into the block above it.
import './fx.css';

function zigzag(n = 24, h = 40) {
  let d = 'M0 100 ';
  for (let i = 0; i <= n; i++) d += `L${(1440 / n) * i} ${i % 2 ? 100 - h : 100} `;
  return `${d}L1440 100 Z`;
}

function scallop(n = 18) {
  const w = 1440 / n;
  let d = 'M0 100 L0 60 ';
  for (let i = 0; i < n; i++) d += `A${w / 2} ${w / 2.4} 0 0 1 ${w * (i + 1)} 60 `;
  return `${d}L1440 100 Z`;
}

function drips() {
  const xs = [80, 250, 410, 560, 760, 930, 1080, 1260, 1390];
  let d = 'M0 100 L0 70 ';
  xs.forEach((x, i) => { const h = 24 + ((i * 37) % 40); d += `L${x - 34} 70 C${x - 20} 70 ${x - 16} ${70 - h} ${x} ${70 - h} C${x + 16} ${70 - h} ${x + 20} 70 ${x + 34} 70 `; });
  return `${d}L1440 70 L1440 100 Z`;
}

const PATHS = {
  wave: 'M0 60 C 240 100 480 20 720 55 C 960 90 1200 25 1440 60 L1440 100 L0 100 Z',
  curve: 'M0 100 Q 720 0 1440 100 Z',
  tilt: 'M0 100 L1440 15 L1440 100 Z',
  arch: 'M0 100 C 0 30 360 0 720 0 C 1080 0 1440 30 1440 100 Z',
  zigzag: zigzag(),
  scallop: scallop(),
  drip: drips(),
};

export default function Divider({ kind = 'none', position = 'top', flip = false }) {
  if (!kind || kind === 'none') return null;
  return (
    <div className={`pv-divider pv-divider--${position} ${flip ? 'pv-divider--flip' : ''}`} aria-hidden="true">
      <svg viewBox="0 0 1440 100" preserveAspectRatio="none">
        {kind === 'mountains' ? (
          <>
            <path d="M0 100 L0 70 L240 30 L480 75 L760 20 L1040 70 L1260 35 L1440 60 L1440 100 Z" opacity="0.45" />
            <path d="M0 100 L0 85 L320 50 L620 90 L900 45 L1200 85 L1440 55 L1440 100 Z" />
          </>
        ) : kind === 'wave' ? (
          <g className="pv-divider-wave"><path d={PATHS.wave} /><path d={PATHS.wave} transform="translate(1440 0)" /></g>
        ) : (
          <path d={PATHS[kind] || PATHS.curve} />
        )}
      </svg>
    </div>
  );
}
