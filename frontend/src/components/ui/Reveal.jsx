// Scroll-reveal wrapper. Uses the entrance animation chosen in the admin for the current
// section (or the site default). `hover` adds the section's hover effect to the block.
import { motion } from 'framer-motion';
import { useEntrance, useFx } from '../../fx/FxContext';
import HoverFx from '../../fx/HoverFx';
import { useCalm } from '../../hooks/useCalm';

export default function Reveal({ as = 'div', children, delay = 0, className, entrance, hover = false, style, ...rest }) {
  const reduce = useCalm();
  const fx = useFx();
  const motionProps = useEntrance(entrance || fx.entrance, { delay: delay * fx.speed, speed: fx.speed });
  const Cmp = motion[as] || motion.div;
  const content = hover && fx.hover !== 'none'
    ? <HoverFx kind={fx.hover} className="pv-fill">{children}</HoverFx>
    : children;
  return (
    <Cmp className={className} style={style} {...(reduce ? {} : motionProps)} {...rest}>
      {content}
    </Cmp>
  );
}
