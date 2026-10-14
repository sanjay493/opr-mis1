import { useQuery } from '@tanstack/react-query';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

/**
 * GET a JSON endpoint through React Query, keyed by its URL. Pass a falsy
 * path to hold the request (e.g. until a dependent filter is known).
 *
 * staleTime 0 = stale-while-revalidate: returning to a page shows the cached
 * response at once and refetches in the background, so navigation is instant
 * without hiding fresh uploads behind the provider's 10-minute default.
 */
export function useApi(path, options = {}) {
  return useQuery({
    queryKey: ['api', path],
    queryFn: async ({ signal }) => {
      const r = await fetch(`${API_BASE_URL}${path}`, { signal });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    },
    enabled: !!path,
    staleTime: 0,
    ...options,
  });
}
