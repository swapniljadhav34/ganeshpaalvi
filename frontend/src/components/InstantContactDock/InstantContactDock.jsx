// Floating contact dock: WhatsApp (primary, larger), Email, Instagram, Facebook, X.
// Magnetic hover on desktop; hides while scrolling down, returns when scrolling up.
import { motion, useMotionValue, useSpring } from 'framer-motion';
import { Mail } from 'lucide-react';
import { useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { useSite } from '../../context/SiteContext';
import { useScrollDirection } from '../../hooks/useScrollDirection';
import { hasFinePointer } from '../../utils/device';
import { FacebookIcon, InstagramIcon, WhatsAppIcon, XIcon } from '../ui/BrandIcons';
import styles from './InstantContactDock.module.css';

function Magnetic({ children, className, strength = 0.35, ...rest }) {
  const ref = useRef(null);
  const x = useSpring(useMotionValue(0), { stiffness: 300, damping: 20 });
  const y = useSpring(useMotionValue(0), { stiffness: 300, damping: 20 });
  const fine = useRef(hasFinePointer());
  const Tag = rest.href ? motion.a : motion.button;
  return (
    <Tag
      ref={ref}
      className={className}
      style={{ x, y }}
      onPointerMove={(e) => {
        if (!fine.current) return;
        const r = ref.current.getBoundingClientRect();
        x.set((e.clientX - (r.left + r.width / 2)) * strength);
        y.set((e.clientY - (r.top + r.height / 2)) * strength);
      }}
      onPointerLeave={() => { x.set(0); y.set(0); }}
      whileTap={{ scale: 0.92 }}
      {...rest}
    >
      {children}
    </Tag>
  );
}

export default function InstantContactDock() {
  const { brand, whatsapp, tier, design } = useSite();
  const { direction, y } = useScrollDirection();
  const { pathname } = useLocation();
  if (!brand || !design.show_contact_dock) return null;
  // On product pages the sticky "WhatsApp · Email · Enquire" bar takes over.
  const hidden = (direction === 'down' && y > 300) || pathname.startsWith('/p/');
  const socials = [
    brand.email && { key: 'email', href: `mailto:${brand.email}`, label: `Email ${brand.email}`, icon: <Mail size={18} strokeWidth={1.5} /> },
    brand.instagram && { key: 'ig', href: brand.instagram, label: 'Instagram', icon: <InstagramIcon size={18} /> },
    brand.facebook && { key: 'fb', href: brand.facebook, label: 'Facebook', icon: <FacebookIcon size={18} /> },
    brand.x && { key: 'x', href: brand.x, label: 'X (Twitter)', icon: <XIcon size={16} /> },
  ].filter(Boolean);

  return (
    <motion.nav
      className={styles.dock}
      aria-label="Contact Paalvi"
      initial={{ y: 80, opacity: 0 }}
      animate={{ y: hidden ? 100 : 0, opacity: hidden ? 0 : 1 }}
      transition={{ type: 'spring', stiffness: 220, damping: 26 }}
      style={{ pointerEvents: hidden ? 'none' : 'auto' }}
    >
      <div className={`${styles.socials} pv-glass`}>
        {socials.map((s) => (
          <Magnetic key={s.key} href={s.href} target={s.key === 'email' ? undefined : '_blank'} rel="noopener" aria-label={s.label} className={styles.icon}>
            {s.icon}
          </Magnetic>
        ))}
      </div>
      {brand.whatsapp && (
        <Magnetic className={styles.wa} strength={0.25} onClick={() => whatsapp({ buyerType: tier === 'wholesale' ? 'retailer' : 'shopper' })}
          aria-label="Chat with Paalvi on WhatsApp">
          <WhatsAppIcon size={26} />
          <span className={styles.waLabel}>Chat with us</span>
        </Magnetic>
      )}
    </motion.nav>
  );
}
