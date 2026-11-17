// Site-wide state: API bootstrap data, Retail/Wholesale tier, and shared UI controls
// (enquiry form, AI guide). Any component can read these with useSite().
import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { useBootstrap } from '../api/hooks';
import { readStore, writeStore } from '../utils/storage';
import { buildWhatsAppMessage, openWhatsApp } from '../utils/whatsapp';

const SiteContext = createContext(null);

// Used until the API answers (and for any setting an older backend doesn't send).
export const DEFAULT_DESIGN = {
  default_media_shape: 'rounded', default_entrance: 'fade_up', default_text_animation: 'rise_words', default_hover: 'lift',
  default_media_motion: 'none', default_gallery_style: 'fade', default_pointer: 'none', default_decor: 'none',
  default_divider: 'none', animation_speed: 'normal', cursor_style: 'default', scroll_progress: false, smooth_scroll: true,
  page_loader: 'pulse', button_shape: '999px', button_hover: 'lift', header_style: 'floating_pill', header_scroll: 'shrink',
  header_entrance: 'fade_down', header_wordmark_size: 22, wordmark_spacing: '0.2em', nav_hover: 'pill', show_search: true,
  show_tier_toggle: true, show_ai_button: true, announcement_style: 'static', footer_style: 'ink', footer_wordmark_text: '',
  footer_wordmark_size: 'l', footer_wordmark_animation: 'rise', footer_decor: 'none', footer_divider: 'none',
  footer_legal_text: 'All prices are MRP / selling prices in ₹, inclusive of all taxes.', footer_show_socials: true,
  card_style: 'minimal', card_image_shape: 'soft', card_aspect: '4 / 5', card_hover: 'tilt_3d', card_image_hover: 'both',
  card_entrance: 'fade_up', card_show_whatsapp: true, product_gallery_shape: 'rounded', show_contact_dock: true, dock_position: 'right',
};

export function SiteProvider({ children }) {
  const { data, isLoading, isError, refetch } = useBootstrap();
  const [designOverride, setDesignOverride] = useState(null); // admin live preview only
  const [tier, setTierState] = useState(() => (readStore('paalvi:tier', 'retail') === 'wholesale' ? 'wholesale' : 'retail'));
  const [enquiry, setEnquiry] = useState(null); // { product, source, buyerType, ... } when the form is open
  const [guideOpen, setGuideOpen] = useState(false);
  const [guidePrompt, setGuidePrompt] = useState('');

  const setTier = useCallback((next) => {
    setTierState(next);
    writeStore('paalvi:tier', next);
  }, []);

  const brand = data?.brand;

  /** One-tap WhatsApp from anywhere. Pass product/variant/pack details for a rich message. */
  const whatsapp = useCallback(
    (opts = {}) => {
      if (!brand?.whatsapp) return;
      const message = buildWhatsAppMessage({ tier, siteUrl: brand.site_url, ...opts });
      openWhatsApp(brand.whatsapp, message, {
        product: opts.product?.slug,
        variant_id: opts.variants?.[0]?.id,
        package_id: opts.pack?.id,
        quantity: opts.quantity,
        tier,
        buyer_type: opts.buyerType || (tier === 'wholesale' ? 'retailer' : 'shopper'),
      });
    },
    [brand, tier],
  );

  const openGuide = useCallback((prompt = '') => {
    setGuidePrompt(prompt);
    setGuideOpen(true);
  }, []);

  const design = useMemo(() => ({ ...DEFAULT_DESIGN, ...(data?.design || {}), ...(designOverride || {}) }), [data, designOverride]);

  const value = useMemo(
    () => ({
      data,
      brand,
      design,
      setDesignOverride,
      theme: data?.theme,
      isLoading,
      isError,
      refetch,
      tier,
      setTier,
      whatsapp,
      enquiry,
      openEnquiry: (opts = {}) => setEnquiry(opts),
      closeEnquiry: () => setEnquiry(null),
      guideOpen,
      guidePrompt,
      openGuide,
      closeGuide: () => setGuideOpen(false),
    }),
    [data, brand, design, isLoading, isError, refetch, tier, setTier, whatsapp, enquiry, guideOpen, guidePrompt, openGuide],
  );

  return <SiteContext.Provider value={value}>{children}</SiteContext.Provider>;
}

export function useSite() {
  const ctx = useContext(SiteContext);
  if (!ctx) throw new Error('useSite must be used inside <SiteProvider>');
  return ctx;
}
