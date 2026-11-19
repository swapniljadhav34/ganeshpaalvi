// Turns the admin's "Page sections" into homepage blocks.
// The registry maps section_type → component. Unknown types are skipped safely,
// and one broken section never takes down the page (error boundary).
import { Component } from 'react';
import { IngredientSpotlight, ProductGuide, RoutineBuilder } from './sections/CareSections';
import { CategoryGrid, FeaturedCollection, ForBusiness, FreeFromStrip } from './sections/ShopSections';
import {
  BrandStory, Editorial, Faq, Gallery, HeroBanner, MarqueeText, PromoBanner, Sustainability, Testimonials, UgcStrip, VideoShowcase,
} from './sections/StorySections';

export const SECTION_REGISTRY = {
  hero_banner: HeroBanner,
  gallery: Gallery,
  marquee_text: MarqueeText,
  video_showcase: VideoShowcase,
  editorial: Editorial,
  promo_banner: PromoBanner,
  brand_story: BrandStory,
  featured_collection: FeaturedCollection,
  category_grid: CategoryGrid,
  ingredient_spotlight: IngredientSpotlight,
  routine_builder: RoutineBuilder,
  product_guide: ProductGuide,
  free_from: FreeFromStrip,
  sustainability: Sustainability,
  testimonials: Testimonials,
  for_business: ForBusiness,
  faq: Faq,
  ugc_strip: UgcStrip,
};

class SectionBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error) {
    // eslint-disable-next-line no-console
    console.warn('A homepage section failed to render and was skipped.', error);
  }

  render() {
    return this.state.failed ? null : this.props.children;
  }
}

/** Render a slice of sections (so the catalog can sit between them). */
export default function DynamicSectionRenderer({ sections = [] }) {
  let editorialCount = 0;
  return sections.map((section) => {
    const Cmp = SECTION_REGISTRY[section.type];
    if (!Cmp) return null; // unknown type → skip
    const extra = section.type === 'editorial' ? { flip: editorialCount++ % 2 === 1 } : {};
    return (
      <SectionBoundary key={section.id}>
        <Cmp section={section} {...extra} />
      </SectionBoundary>
    );
  });
}
