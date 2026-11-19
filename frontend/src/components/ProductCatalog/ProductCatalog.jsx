// The catalog: sticky category chips, filters (inline on desktop, bottom sheet on mobile),
// 2/3/4-column grid, infinite scroll with a "Load more" fallback, shimmer skeletons,
// and windowed rendering once more than 200 cards are loaded (keeps 50,000-product catalogs smooth).
import { useWindowVirtualizer } from '@tanstack/react-virtual';
import { motion } from 'framer-motion';
import { RefreshCw, SlidersHorizontal, X } from 'lucide-react';
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import Offcanvas from 'react-bootstrap/Offcanvas';
import { useSearchParams } from 'react-router-dom';
import { useProducts } from '../../api/hooks';
import { useSite } from '../../context/SiteContext';
import { useMediaQuery } from '../../hooks/useMediaQuery';
import { useSmoothScroll } from '../../hooks/useSmoothScroll';
import { springs } from '../../theme/motion';
import { formatNumber } from '../../utils/format';
import { useT } from '../../i18n/I18n';
import FilterPanel from './FilterPanel';
import ProductCard from './ProductCard';
import styles from './ProductCatalog.module.css';

const FILTER_KEYS = ['q', 'category', 'badge', 'suitable_for', 'variant', 'sort', 'min_discount', 'min_price', 'max_price'];
const VIRTUALIZE_AFTER = 200;

function flattenCategories(nodes, depth = 0, out = []) {
  nodes.forEach((n) => {
    out.push({ ...n, depth });
    if (n.children?.length) flattenCategories(n.children, depth + 1, out);
  });
  return out;
}

function SkeletonCard() {
  return (
    <div className={styles.card} aria-hidden="true">
      <div className={`${styles.media} pv-skeleton`} />
      <div className={styles.body}>
        <div className="pv-skeleton" style={{ height: 10, width: '40%' }} />
        <div className="pv-skeleton" style={{ height: 16, width: '85%', marginTop: 8 }} />
        <div className="pv-skeleton" style={{ height: 14, width: '30%', marginTop: 10 }} />
      </div>
    </div>
  );
}

function useColumns() {
  const md = useMediaQuery('(min-width: 768px)');
  const lg = useMediaQuery('(min-width: 1200px)');
  return lg ? 4 : md ? 3 : 2;
}

/** Plain grid for normal catalogs, windowed rows for very long lists. */
function Grid({ items, columns, virtual }) {
  const listRef = useRef(null);
  const [margin, setMargin] = useState(0);
  const rows = Math.ceil(items.length / columns);
  // Distance from the top of the PAGE (not the nearest positioned parent) — measured after layout.
  useLayoutEffect(() => {
    if (!virtual || !listRef.current) return;
    setMargin(listRef.current.getBoundingClientRect().top + window.scrollY);
  }, [virtual, columns]);
  const virtualizer = useWindowVirtualizer({
    count: virtual ? rows : 0,
    estimateSize: () => 460,
    overscan: 3,
    scrollMargin: margin,
  });

  if (!virtual) {
    return (
      <div className={styles.grid}>
        {items.map((p, i) => <ProductCard key={p.id} product={p} index={i} />)}
      </div>
    );
  }
  return (
    <div ref={listRef} style={{ position: 'relative', height: virtualizer.getTotalSize() }}>
      {virtualizer.getVirtualItems().map((row) => (
        <div
          key={row.key}
          ref={virtualizer.measureElement}
          data-index={row.index}
          className={styles.grid}
          style={{ position: 'absolute', top: 0, left: 0, right: 0, transform: `translateY(${row.start - virtualizer.options.scrollMargin}px)`, paddingBottom: 'var(--grid-gap)' }}
        >
          {items.slice(row.index * columns, row.index * columns + columns).map((p, i) => (
            <ProductCard key={p.id} product={p} index={row.index * columns + i} />
          ))}
        </div>
      ))}
    </div>
  );
}

export default function ProductCatalog() {
  const { data, brand } = useSite();
  const t = useT();
  const [params, setParams] = useSearchParams();
  const [sheetOpen, setSheetOpen] = useState(false);
  const isDesktop = useMediaQuery('(min-width: 992px)');
  const columns = useColumns();
  const sentinel = useRef(null);
  const { scrollTo } = useSmoothScroll();

  const filters = useMemo(() => Object.fromEntries(FILTER_KEYS.map((k) => [k, params.get(k) || ''])), [params]);
  const apiFilters = useMemo(() => Object.fromEntries(Object.entries(filters).filter(([, v]) => v)), [filters]);
  const activeCount = FILTER_KEYS.filter((k) => !['q', 'category', 'sort'].includes(k) && filters[k]).length + (filters.sort ? 1 : 0);

  const setMany = useCallback(
    (changes) => {
      const next = new URLSearchParams(params);
      Object.entries(changes).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)));
      setParams(next, { replace: true, preventScrollReset: true });
    },
    [params, setParams],
  );
  const setFilter = useCallback((k, v) => setMany({ [k]: v }), [setMany]);
  const reset = () => setMany(Object.fromEntries(FILTER_KEYS.filter((k) => k !== 'category' && k !== 'q').map((k) => [k, ''])));

  const { data: pages, isLoading, isError, error, fetchNextPage, hasNextPage, isFetchingNextPage, isFetching, refetch } = useProducts(apiFilters);
  const items = useMemo(() => pages?.pages.flatMap((p) => p.items) ?? [], [pages]);
  const total = pages?.pages[0]?.total;

  // Infinite scroll: load the next page when the sentinel comes into view.
  useEffect(() => {
    const el = sentinel.current;
    if (!el || !hasNextPage) return undefined;
    const io = new IntersectionObserver(([entry]) => entry.isIntersecting && !isFetchingNextPage && fetchNextPage(), { rootMargin: '800px 0px' });
    io.observe(el);
    return () => io.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  const cats = useMemo(() => flattenCategories(data?.categories || []), [data]);
  const pickCategory = (slug) => {
    setFilter('category', slug);
    scrollTo('#catalog', { duration: 0.8 });
  };

  // Arrow keys move between category tabs (standard tablist keyboard behaviour).
  const chipKeys = (e) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
    const tabs = [...e.currentTarget.querySelectorAll('[role="tab"]')];
    const at = tabs.indexOf(document.activeElement);
    const next = e.key === 'Home' ? 0 : e.key === 'End' ? tabs.length - 1
      : (at + (e.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
    e.preventDefault();
    tabs[next]?.focus();
  };

  const panel = (
    <FilterPanel filters={filters} setFilter={setFilter} setMany={setMany} badges={data?.badges} options={data?.filters}
      onReset={reset} activeCount={activeCount} />
  );

  return (
    <section id="catalog" className={`pv-section ${styles.catalog}`} aria-labelledby="catalog-title">
      <div className="pv-container">
        <header className={styles.head}>
          <div>
            <p className="t-caption">{t('shop.eyebrow')}</p>
            {/* The core store: always rendered on the homepage — no setting or role can switch it off. */}
            <h2 id="catalog-title" className="t-h1">{filters.q ? t('shop.results', { q: filters.q }) : (brand?.shop_title || t('shop.title'))}</h2>
            {!filters.q && brand?.shop_intro && <p className="t-muted">{brand.shop_intro}</p>}
          </div>
          <p className={`t-muted ${styles.count}`} aria-live="polite">
            {total != null ? t('shop.count', { n: formatNumber(total) }) : ''}
            {isFetching && !isFetchingNextPage && !isLoading ? ' · updating…' : ''}
          </p>
        </header>

        {/* Sticky category chips with an animated underline */}
        <div className={styles.chipsBar}>
          <div className={styles.chips} role="tablist" aria-label="Categories" onKeyDown={chipKeys}>
            {[{ slug: '', name: t('shop.all'), depth: 0 }, ...cats].map((c) => {
              const on = (filters.category || '') === c.slug;
              return (
                <button key={c.slug || 'all'} type="button" role="tab" aria-selected={on} tabIndex={on ? 0 : -1}
                  className={`${styles.chip} ${on ? styles.chipOn : ''} ${c.depth > 0 ? styles.chipSub : ''}`} onClick={() => pickCategory(c.slug)}>
                  {c.name}
                  {on && <motion.span layoutId="cat-underline" className={styles.underline} transition={springs.snappy} />}
                </button>
              );
            })}
          </div>
          {!isDesktop && (
            <button type="button" className={`pv-btn pv-btn--ghost pv-btn--sm ${styles.filterBtn}`} onClick={() => setSheetOpen(true)}>
              <SlidersHorizontal size={16} strokeWidth={1.5} /> Filters{activeCount ? ` · ${activeCount}` : ''}
            </button>
          )}
        </div>

        {filters.q && (
          <div className={styles.activeQ}>
            <span className="pv-chip pv-chip--primary">
              Search: {filters.q}
              <button type="button" onClick={() => setFilter('q', '')} aria-label="Clear search" className={styles.chipX}><X size={12} /></button>
            </span>
          </div>
        )}

        <div className={styles.layout}>
          {isDesktop && <aside className={styles.sidebar} aria-label="Filters">{panel}</aside>}

          <div className={styles.results}>
            {isLoading && (
              <div className={styles.grid}>{Array.from({ length: columns * 2 }, (_, i) => <SkeletonCard key={i} />)}</div>
            )}

            {isError && (
              <div className={styles.state}>
                <p className="t-h3">We couldn't load products just now.</p>
                <p className="t-muted">{error?.message}</p>
                <button type="button" className="pv-btn pv-btn--sm" onClick={() => refetch()}><RefreshCw size={16} strokeWidth={1.5} /> Try again</button>
              </div>
            )}

            {!isLoading && !isError && items.length === 0 && (
              <div className={styles.state}>
                <p className="t-h2">Nothing here — yet.</p>
                <p className="t-muted">Try removing a filter, or ask our Care Guide to find the right essential for you.</p>
                {activeCount > 0 && <button type="button" className="pv-btn pv-btn--sm" onClick={reset}>Clear filters</button>}
              </div>
            )}

            {items.length > 0 && <Grid items={items} columns={columns} virtual={items.length > VIRTUALIZE_AFTER} />}

            {isFetchingNextPage && (
              <div className={styles.grid} style={{ marginTop: 'var(--grid-gap)' }}>
                {Array.from({ length: columns }, (_, i) => <SkeletonCard key={i} />)}
              </div>
            )}
            <div ref={sentinel} aria-hidden="true" />
            {hasNextPage && !isFetchingNextPage && (
              <div className={styles.more}>
                <button type="button" className="pv-btn pv-btn--ghost" onClick={() => fetchNextPage()}>Load more</button>
              </div>
            )}
          </div>
        </div>
      </div>

      {!isDesktop && (
        <Offcanvas show={sheetOpen} onHide={() => setSheetOpen(false)} placement="bottom" className={styles.sheet} aria-labelledby="filters-title">
          <div className={styles.sheetHandle} aria-hidden="true" />
          <div className={styles.sheetHead}>
            <h2 id="filters-title" className="t-h3">Filters</h2>
            <button type="button" className="pv-icon-btn" onClick={() => setSheetOpen(false)} aria-label="Close filters"><X size={18} strokeWidth={1.5} /></button>
          </div>
          <div className={styles.sheetBody} data-lenis-prevent>{panel}</div>
          <div className={styles.sheetFoot}>
            <button type="button" className="pv-btn pv-btn--block" onClick={() => setSheetOpen(false)}>
              Show {total != null ? formatNumber(total) : ''} products
            </button>
          </div>
        </Offcanvas>
      )}
    </section>
  );
}
