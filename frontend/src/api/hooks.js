// TanStack Query hooks — caching, retries and infinite scrolling for the API.
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchBootstrap, fetchProduct, fetchProducts } from './client';

/** Homepage data the server already put in the HTML (saves a round trip before the hero paints). */
function inlinedBootstrap() {
  if (typeof document === 'undefined') return undefined;
  const el = document.getElementById('__BOOT__');
  if (!el) return undefined;
  try {
    const data = JSON.parse(el.textContent);
    el.remove();
    return data;
  } catch {
    return undefined;
  }
}
const BOOT = inlinedBootstrap();
const BOOT_AT = Date.now();

export function useBootstrap() {
  return useQuery({
    queryKey: ['bootstrap'],
    queryFn: ({ signal }) => fetchBootstrap({ signal }),
    staleTime: 5 * 60 * 1000,
    initialData: BOOT,
    initialDataUpdatedAt: BOOT ? BOOT_AT : undefined,
  });
}

export function useProducts(filters) {
  return useInfiniteQuery({
    queryKey: ['products', filters],
    queryFn: ({ pageParam, signal }) => fetchProducts({ ...filters, page: pageParam }, { signal }),
    initialPageParam: 1,
    getNextPageParam: (last) => (last.has_next ? last.page + 1 : undefined),
    staleTime: 60 * 1000,
    placeholderData: (prev) => prev, // keep showing old cards while new filters load
  });
}

export function useProduct(slug, { initial } = {}) {
  return useQuery({
    queryKey: ['product', slug],
    queryFn: ({ signal }) => fetchProduct(slug, { signal }),
    enabled: Boolean(slug),
    staleTime: 2 * 60 * 1000,
    // Show the card's data instantly while the full detail loads.
    placeholderData: initial ? { ...initial, _partial: true } : undefined,
  });
}

/** Preload product detail on hover/touch so the modal opens instantly. */
export function usePrefetchProduct() {
  const qc = useQueryClient();
  return (slug) =>
    qc.prefetchQuery({ queryKey: ['product', slug], queryFn: ({ signal }) => fetchProduct(slug, { signal }), staleTime: 2 * 60 * 1000 });
}
