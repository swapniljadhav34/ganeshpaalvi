// Headlines that animate in one of 14 admin-chosen styles. Screen readers always get the
// plain sentence (aria-label); the animated pieces are hidden from them.
import { motion, useInView } from 'framer-motion';
import { Fragment, useEffect, useRef, useState } from 'react';
import { ease } from '../theme/motion';
import './fx.css';
import { useCalm } from '../hooks/useCalm';

const GLYPHS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';

function useStart(trigger, ref) {
  const inView = useInView(ref, { once: true, margin: '0px 0px -10% 0px' });
  return trigger === 'mount' ? true : inView;
}

function Typewriter({ text, start, speed }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!start) return undefined;
    setN(0);
    let i = 0;
    const t = setInterval(() => { i += 1; setN(i); if (i >= text.length) clearInterval(t); }, 45 * speed);
    return () => clearInterval(t);
  }, [start, text, speed]);
  return <>{text.slice(0, n)}<span className="pv-caret" /></>;
}

function Scramble({ text, start, speed }) {
  const [out, setOut] = useState(text.replace(/\S/g, ' '));
  useEffect(() => {
    if (!start) return undefined;
    let frame = 0;
    const total = Math.round(28 * speed);
    const t = setInterval(() => {
      frame += 1;
      const done = Math.floor((frame / total) * text.length);
      setOut(text.split('').map((ch, i) => (i < done || ch === ' ' ? ch : GLYPHS[(Math.random() * GLYPHS.length) | 0])).join(''));
      if (frame >= total) { clearInterval(t); setOut(text); }
    }, 40);
    return () => clearInterval(t);
  }, [start, text, speed]);
  return out;
}

const WORD_ANIMS = {
  rise_words: { from: { y: '110%' }, to: { y: '0%' }, mask: true },
  blur_words: { from: { opacity: 0, filter: 'blur(14px)', y: 10 }, to: { opacity: 1, filter: 'blur(0px)', y: 0 } },
  scale_words: { from: { opacity: 0, scale: 0.4 }, to: { opacity: 1, scale: 1 }, spring: true },
  slide_words: { from: { opacity: 0, x: -40 }, to: { opacity: 1, x: 0 } },
};
const LETTER_ANIMS = {
  rise_letters: { from: { y: '110%' }, to: { y: '0%' }, mask: true },
  flip_letters: { from: { opacity: 0, rotateX: -90 }, to: { opacity: 1, rotateX: 0 } },
  wave: { from: { opacity: 0, y: 0 }, to: { opacity: 1, y: 0 } },
};

export default function AnimatedText({
  text = '', as: Tag = 'h2', kind = 'rise_words', className = '', delay = 0, speed = 1, trigger = 'view', style,
}) {
  const ref = useRef(null);
  const reduce = useCalm();
  const start = useStart(trigger, ref);
  if (!text) return null;
  const k = reduce ? 'none' : kind;
  const baseDelay = delay * speed;

  if (k === 'none') return <Tag ref={ref} className={className} style={style}>{text}</Tag>;

  if (k === 'fade') {
    const M = motion[Tag] || motion.h2;
    return (
      <M ref={ref} className={className} style={style} initial={{ opacity: 0 }} animate={start ? { opacity: 1 } : {}}
        transition={{ duration: 1 * speed, ease, delay: baseDelay }}>{text}</M>
    );
  }

  if (k === 'typewriter' || k === 'scramble') {
    return (
      <Tag ref={ref} className={`${className} pv-text-${k}`} style={style} aria-label={text}>
        <span aria-hidden="true">{k === 'typewriter' ? <Typewriter text={text} start={start} speed={speed} /> : <Scramble text={text} start={start} speed={speed} />}</span>
      </Tag>
    );
  }

  if (k === 'shimmer' || k === 'gradient_flow' || k === 'highlight') {
    return (
      <Tag ref={ref} className={`${className} pv-text-${k} ${start ? 'is-on' : ''}`} style={{ ...style, '--pv-delay': `${baseDelay}s`, '--pv-speed': speed }}>
        <span className="pv-text-inner">{text}</span>
      </Tag>
    );
  }

  const words = text.split(' ');
  if (WORD_ANIMS[k]) {
    const a = WORD_ANIMS[k];
    return (
      <Tag ref={ref} className={className} style={style} aria-label={text}>
        {words.map((w, i) => (
          <Fragment key={`${w}-${i}`}>
            <span className={a.mask ? 'pv-mask' : 'pv-word'} aria-hidden="true">
              <motion.span
                className="pv-word"
                initial={a.from}
                animate={start ? a.to : a.from}
                transition={a.spring
                  ? { type: 'spring', stiffness: 220, damping: 14, delay: baseDelay + i * 0.07 * speed }
                  : { duration: 0.9 * speed, ease, delay: baseDelay + i * 0.07 * speed }}
              >
                {w}
              </motion.span>
            </span>
            {i < words.length - 1 && ' '}
          </Fragment>
        ))}
      </Tag>
    );
  }

  // Letter-by-letter styles (letters stay grouped per word so lines wrap naturally)
  const a = LETTER_ANIMS[k] || LETTER_ANIMS.rise_letters;
  let count = 0;
  return (
    <Tag ref={ref} className={`${className} ${k === 'flip_letters' ? 'pv-persp' : ''}`} style={style} aria-label={text}>
      {words.map((w, wi) => (
        <Fragment key={`${w}-${wi}`}>
          <span className="pv-word" aria-hidden="true">
            {w.split('').map((ch, ci) => {
              const n = count++;
              const d = baseDelay + n * 0.028 * speed;
              const letter = (
                <motion.span
                  key={ci}
                  className="pv-letter"
                  initial={a.from}
                  animate={start ? (k === 'wave' ? { opacity: 1, y: [0, -9, 0] } : a.to) : a.from}
                  transition={k === 'wave'
                    ? { opacity: { duration: 0.4, delay: d }, y: { duration: 2.6 * speed, delay: d, repeat: Infinity, repeatDelay: 2, ease: 'easeInOut' } }
                    : { duration: 0.7 * speed, ease, delay: d }}
                >
                  {ch}
                </motion.span>
              );
              return a.mask ? <span key={ci} className="pv-mask">{letter}</span> : letter;
            })}
          </span>
          {wi < words.length - 1 && ' '}
        </Fragment>
      ))}
    </Tag>
  );
}
