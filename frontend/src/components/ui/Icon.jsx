// Thin 1.5px line icons. The admin types icon names (e.g. "leaf"); we map them to Lucide icons.
import {
  Baby, BadgeCheck, Brush, Building2, Droplet, Droplets, Flower2, Gift, Heart, Hotel, Leaf, Moon, Package, Pill,
  Recycle, ShieldCheck, Smile, Sparkle, Sparkles, Sprout, Star, Store, Sun, TreeDeciduous, Truck, Waves, Wind,
} from 'lucide-react';

const MAP = {
  baby: Baby, badge: BadgeCheck, verified: BadgeCheck, brush: Brush, building: Building2, droplet: Droplet,
  droplets: Droplets, flower: Flower2, gift: Gift, hotel: Hotel, leaf: Leaf, package: Package, pill: Pill,
  recycle: Recycle, shield: ShieldCheck, smile: Smile, sparkle: Sparkle, sparkles: Sparkles, sprout: Sprout,
  store: Store, sun: Sun, moon: Moon, tree: TreeDeciduous, truck: Truck, waves: Waves, wind: Wind, star: Star,
  heart: Heart,
};

export default function Icon({ name, size = 20, ...rest }) {
  const Cmp = MAP[String(name || '').toLowerCase()] || Sparkle;
  return <Cmp size={size} strokeWidth={1.5} absoluteStrokeWidth aria-hidden="true" {...rest} />;
}
