// React to CSS media queries, e.g. useMediaQuery('(min-width: 768px)').
import { useEffect, useState } from 'react';

export function useMediaQuery(query) {
  const get = () => typeof window !== 'undefined' && window.matchMedia(query).matches;
  const [matches, setMatches] = useState(get);
  useEffect(() => {
    const mql = window.matchMedia(query);
    const onChange = () => setMatches(mql.matches);
    onChange();
    mql.addEventListener('change', onChange);
    return () => mql.removeEventListener('change', onChange);
  }, [query]);
  return matches;
}

export const useIsDesktop = () => useMediaQuery('(min-width: 992px)');
export const useIsMobile = () => !useMediaQuery('(min-width: 768px)');
