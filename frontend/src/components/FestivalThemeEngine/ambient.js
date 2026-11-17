// Ambient particle effects drawn on ONE <canvas>. Each effect is a tiny "particle recipe".
// Kept deliberately light: max 30 particles on mobile, 100 on desktop.

const rand = (a, b) => a + Math.random() * (b - a);

function hexToRgb(hex = '#8FC9B9') {
  const h = hex.replace('#', '');
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) || 0);
}
const rgba = (hex, a) => `rgba(${hexToRgb(hex).join(',')},${a})`;

/** Recipes: spawn(w,h,colors) → particle, step(p,w,h,t) → keep?, draw(ctx,p,colors). */
const RECIPES = {
  bubbles: {
    density: 1,
    spawn: (w, h, fromBottom) => ({
      x: rand(0, w), y: fromBottom ? h + rand(10, 80) : rand(0, h), r: rand(3, 14),
      vy: rand(0.15, 0.55), wobble: rand(0, Math.PI * 2), ws: rand(0.006, 0.02), a: rand(0.18, 0.45),
    }),
    step: (p) => { p.y -= p.vy; p.wobble += p.ws; p.x += Math.sin(p.wobble) * 0.3; return p.y > -30; },
    draw: (ctx, p, c) => {
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.strokeStyle = rgba(c.primary, p.a);
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(p.x - p.r * 0.35, p.y - p.r * 0.35, p.r * 0.22, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(255,255,255,${p.a + 0.2})`;
      ctx.fill();
    },
  },
  mist: {
    density: 0.25,
    spawn: (w, h, fromBottom) => ({
      x: rand(0, w), y: fromBottom ? h + 60 : rand(0, h), r: rand(60, 160), vy: rand(0.1, 0.3), vx: rand(-0.15, 0.15),
      a: 0, max: rand(0.05, 0.11), life: 0,
    }),
    step: (p) => { p.y -= p.vy; p.x += p.vx; p.life += 1; p.a = Math.min(p.max, p.life / 400); return p.y > -p.r; },
    draw: (ctx, p, c) => {
      const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r);
      g.addColorStop(0, rgba(c.surfaceElevated, p.a * 3));
      g.addColorStop(1, rgba(c.surfaceElevated, 0));
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fill();
    },
  },
  ripple: {
    density: 0.2,
    spawn: (w, h) => ({ x: rand(0, w), y: rand(0, h), r: 0, max: rand(40, 120), a: 0.35 }),
    step: (p) => { p.r += 0.45; p.a = 0.35 * (1 - p.r / p.max); return p.r < p.max; },
    draw: (ctx, p, c) => {
      for (let i = 0; i < 2; i += 1) {
        ctx.beginPath();
        ctx.arc(p.x, p.y, Math.max(0, p.r - i * 10), 0, Math.PI * 2);
        ctx.strokeStyle = rgba(c.primary, Math.max(0, p.a - i * 0.1));
        ctx.lineWidth = 1;
        ctx.stroke();
      }
    },
  },
  diyas: {
    density: 0.8,
    spawn: (w, h, fromBottom) => ({
      x: rand(0, w), y: fromBottom ? h + 10 : rand(0, h), r: rand(1, 2.6), vy: rand(0.2, 0.7), vx: rand(-0.2, 0.2),
      flicker: rand(0, 10), a: rand(0.4, 0.9),
    }),
    step: (p) => { p.y -= p.vy; p.x += p.vx; p.flicker += 0.1; return p.y > -10; },
    draw: (ctx, p, c) => {
      const a = p.a * (0.6 + Math.sin(p.flicker) * 0.4);
      const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 6);
      g.addColorStop(0, rgba(c.accent, a));
      g.addColorStop(1, rgba(c.accent, 0));
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r * 6, 0, Math.PI * 2);
      ctx.fill();
    },
  },
  gulal: {
    density: 0.9,
    spawn: (w, h, fromBottom, c) => ({
      x: rand(0, w), y: fromBottom ? -10 : rand(0, h), s: rand(3, 7), vy: rand(0.4, 1.1), vx: rand(-0.4, 0.4),
      rot: rand(0, 6), vr: rand(-0.04, 0.04), color: [c.primary, c.secondary, c.accent][Math.floor(rand(0, 3))], a: rand(0.35, 0.7),
    }),
    step: (p, w, h) => { p.y += p.vy; p.x += p.vx; p.rot += p.vr; return p.y < h + 20; },
    draw: (ctx, p) => {
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot);
      ctx.fillStyle = rgba(p.color, p.a);
      ctx.fillRect(-p.s / 2, -p.s / 4, p.s, p.s / 2);
      ctx.restore();
    },
  },
  snow: {
    density: 1,
    spawn: (w, h, fromBottom) => ({
      x: rand(0, w), y: fromBottom ? -10 : rand(0, h), r: rand(1, 3.2), vy: rand(0.3, 0.9), sway: rand(0, 6), a: rand(0.4, 0.85),
    }),
    step: (p, w, h) => { p.y += p.vy; p.sway += 0.01; p.x += Math.sin(p.sway) * 0.35; return p.y < h + 10; },
    draw: (ctx, p) => {
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(255,255,255,${p.a})`;
      ctx.fill();
    },
  },
  petals: {
    density: 0.5,
    spawn: (w, h, fromBottom, c) => ({
      x: rand(0, w), y: fromBottom ? -20 : rand(0, h), s: rand(5, 10), vy: rand(0.3, 0.8), sway: rand(0, 6),
      rot: rand(0, 6), vr: rand(-0.02, 0.02), color: Math.random() > 0.5 ? c.secondary : c.primary, a: rand(0.35, 0.65),
    }),
    step: (p, w, h) => { p.y += p.vy; p.sway += 0.012; p.x += Math.sin(p.sway) * 0.6; p.rot += p.vr; return p.y < h + 20; },
    draw: (ctx, p) => {
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot);
      ctx.beginPath();
      ctx.ellipse(0, 0, p.s, p.s / 2.2, 0, 0, Math.PI * 2);
      ctx.fillStyle = rgba(p.color, p.a);
      ctx.fill();
      ctx.restore();
    },
  },
};

/** Starts an effect on a canvas. Returns a stop() function. */
export function startAmbient(canvas, effect, colors, { maxParticles = 60 } = {}) {
  const recipe = RECIPES[effect];
  if (!recipe || !canvas) return () => {};
  const ctx = canvas.getContext('2d');
  const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
  let w = 0;
  let h = 0;
  const resize = () => {
    w = window.innerWidth;
    h = window.innerHeight;
    canvas.width = Math.floor(w * dpr);
    canvas.height = Math.floor(h * dpr);
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  };
  resize();
  const target = Math.max(4, Math.round(maxParticles * recipe.density));
  let particles = Array.from({ length: target }, () => recipe.spawn(w, h, false, colors));
  let frame = 0;
  let running = true;
  let last = 0;

  const loop = (t) => {
    if (!running) return;
    frame = requestAnimationFrame(loop);
    if (t - last < 1000 / 40) return; // ~40fps is plenty for ambience and saves battery
    last = t;
    ctx.clearRect(0, 0, w, h);
    particles = particles.filter((p) => recipe.step(p, w, h, t));
    while (particles.length < target) particles.push(recipe.spawn(w, h, true, colors));
    particles.forEach((p) => recipe.draw(ctx, p, colors));
  };
  frame = requestAnimationFrame(loop);

  const onVisibility = () => {
    if (document.hidden) {
      running = false;
      cancelAnimationFrame(frame);
    } else if (!running) {
      running = true;
      frame = requestAnimationFrame(loop);
    }
  };
  document.addEventListener('visibilitychange', onVisibility);
  window.addEventListener('resize', resize);

  return () => {
    running = false;
    cancelAnimationFrame(frame);
    document.removeEventListener('visibilitychange', onVisibility);
    window.removeEventListener('resize', resize);
    ctx.clearRect(0, 0, w, h);
  };
}
