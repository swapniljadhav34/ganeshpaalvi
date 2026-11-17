// Homepage: hero → admin sections → catalog → remaining admin sections.
// The catalog slots in right after the "Featured Collection" section (else the first "Category Grid")
// (or after the second section if neither exists), so the owner controls the flow from the admin.
import { Helmet } from 'react-helmet-async';
import DynamicSectionRenderer from '../components/DynamicSectionRenderer/DynamicSectionRenderer';
import HeroSection from '../components/HeroSection/HeroSection';
import ProductCatalog from '../components/ProductCatalog/ProductCatalog';
import { useSite } from '../context/SiteContext';

export default function HomePage() {
  const { data, brand } = useSite();
  const sections = data?.sections || [];
  const featured = sections.findIndex((s) => s.type === 'featured_collection');
  const anchor = featured >= 0 ? featured : sections.findIndex((s) => s.type === 'category_grid');
  const split = anchor >= 0 ? anchor + 1 : Math.min(2, sections.length);

  const orgLd = brand && {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: brand.name,
    url: brand.site_url,
    logo: brand.logo_dark || undefined,
    email: brand.email || undefined,
    sameAs: [brand.instagram, brand.facebook, brand.x].filter(Boolean),
    contactPoint: brand.whatsapp ? [{ '@type': 'ContactPoint', telephone: `+${brand.whatsapp}`, contactType: 'customer service', areaServed: 'IN' }] : undefined,
  };

  return (
    <>
      {brand && (
        <Helmet>
          <title>{brand.seo.title}</title>
          <meta name="description" content={brand.seo.description} />
          <meta property="og:title" content={brand.seo.title} />
          <meta property="og:description" content={brand.seo.description} />
          {brand.seo.image && <meta property="og:image" content={brand.seo.image} />}
          <link rel="canonical" href={`${brand.site_url}/`} />
          <script type="application/ld+json">{JSON.stringify(orgLd)}</script>
        </Helmet>
      )}
      <HeroSection />
      <DynamicSectionRenderer sections={sections.slice(0, split)} />
      <ProductCatalog />
      <DynamicSectionRenderer sections={sections.slice(split)} />
    </>
  );
}
