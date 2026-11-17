// Motion tokens — "water and air". Import these instead of inventing new timings.

// Springs: stiffness / damping
export const springs = {
  float: { type: 'spring', stiffness: 90, damping: 18 },   // buoyant, for big surfaces
  gentle: { type: 'spring', stiffness: 120, damping: 20 }, // default UI movement
  snappy: { type: 'spring', stiffness: 400, damping: 30 }, // toggles, small chips
};

export const durations = { fast: 0.15, base: 0.25, slow: 0.45, slower: 0.8 };
export const ease = [0.22, 1, 0.36, 1];

// Scroll reveal: fade + 32px rise, plays once.
export const reveal = {
  hidden: { opacity: 0, y: 32 },
  show: { opacity: 1, y: 0, transition: { duration: durations.slower, ease } },
};

export const stagger = (step = 0.08, delay = 0) => ({
  hidden: {},
  show: { transition: { staggerChildren: step, delayChildren: delay } },
});
