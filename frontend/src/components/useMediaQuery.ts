import { useCallback, useSyncExternalStore } from 'react';

/** Whether a CSS media query matches now. Server rendering (and any place without matchMedia) gets false. */
export function matchesMediaQuery(query: string): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false;
  return window.matchMedia(query).matches;
}

/**
 * Live value of a media query, e.g. useMediaQuery('(max-width: 900px)'). It is read during the first client render,
 * so a phone never renders the desktop layout first; on the server it is always false.
 */
export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback((onChange: () => void) => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return () => {};
    const list = window.matchMedia(query);
    // Safari < 14 only has the deprecated addListener.
    if (typeof list.addEventListener === 'function') {
      list.addEventListener('change', onChange);
      return () => list.removeEventListener('change', onChange);
    }
    list.addListener(onChange);
    return () => list.removeListener(onChange);
  }, [query]);
  return useSyncExternalStore(subscribe, () => matchesMediaQuery(query), () => false);
}
