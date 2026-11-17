// TanStack Query hooks — caching, retries and infinite scrolling for the API.
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchBootstrap, fetchProduct, fetchProducts } from './client';

export function useBootstrap() {
  return useQuery({
    queryKey: ['bootstrap'],
    queryFn: ({ signal }) => fetchBootstrap({ signal }),
    staleTime: 5 * 60 * 1000,
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
