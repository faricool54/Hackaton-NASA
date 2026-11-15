// Session cache of GET /api/object answers (FE-5): an LRU of the last 50 lookups plus the requests in flight.
// The backend has 4 workers and needs 6-20 s per lookup, so reselecting an object, or a second view asking for the
// same lookup (the 3D tab, the pinned map popup), must not queue another request. Only complete answers are
// cached: an error, a timeout or a `partial: true` answer is never remembered, so the next try asks again.
import { client } from './client';
import { lookupKey, type ObjectLookup } from './objectCard';
import type { ObjectContextResponse } from './types';

export const OBJECT_CACHE_SIZE = 50;
// The backend answers within its own deadline (< 30 s, partial results after that); this only guards a hung network.
export const OBJECT_CLIENT_TIMEOUT_MS = 45_000;

export type ObjectContextFetcher = (lookup: ObjectLookup, signal: AbortSignal) => Promise<ObjectContextResponse>;

export interface ObjectContextCache {
  /** The cached answer, if any. Pure read: it neither fetches nor changes the LRU order (safe during render). */
  peek(lookup: ObjectLookup | null): ObjectContextResponse | null;
  /** Cached answer, or the shared request for this lookup (single-flight). Aborting `signal` stops only this
   *  caller's wait; the request itself is aborted when its last waiter has left (one tick later). */
  get(lookup: ObjectLookup, signal?: AbortSignal): Promise<ObjectContextResponse>;
  /** Drop a cached answer (Retry). A request in flight is not touched. */
  forget(lookup: ObjectLookup | null): void;
  /** Lookups with a request in flight (tests). */
  inFlight(): number;
  /** Cached answers (tests). */
  size(): number;
}

interface Flight { promise: Promise<ObjectContextResponse>; controller: AbortController; waiters: number }

function abortReason(signal: AbortSignal): unknown {
  return signal.reason ?? new DOMException('The catalog lookup was aborted.', 'AbortError');
}

function isTimeout(reason: unknown): boolean {
  return reason instanceof DOMException && reason.name === 'TimeoutError';
}

export function createObjectContextCache(fetcher: ObjectContextFetcher,
  { max = OBJECT_CACHE_SIZE, timeoutMs = OBJECT_CLIENT_TIMEOUT_MS }: { max?: number; timeoutMs?: number } = {},
): ObjectContextCache {
  const answers = new Map<string, ObjectContextResponse>(); // insertion order = recency, oldest first
  const flights = new Map<string, Flight>();

  const remember = (key: string, data: ObjectContextResponse) => {
    answers.delete(key);
    answers.set(key, data);
    while (answers.size > max) answers.delete(answers.keys().next().value as string);
  };

  const start = (key: string, lookup: ObjectLookup): Flight => {
    const controller = new AbortController();
    const timer = timeoutMs > 0
      ? setTimeout(() => controller.abort(new DOMException('Catalog context timed out', 'TimeoutError')), timeoutMs)
      : undefined;
    const flight: Flight = { controller, waiters: 0, promise: Promise.resolve(null as never) };
    flights.set(key, flight); // before the fetch starts, so a fetcher that fails at once still clears it below
    flight.promise = (async () => {
      try {
        const data = await fetcher(lookup, controller.signal);
        // Like the backend (object_service.py: a partial result is never served from the API cache), a partial
        // answer is not kept: the backend's catalog search goes on after its deadline, so the next lookup heals it.
        if (!data.partial) remember(key, data);
        return data;
      } catch (error) {
        // A hung network surfaces as the timeout (the card says "did not arrive in time"), not as a bare abort.
        throw isTimeout(controller.signal.reason) ? controller.signal.reason : error;
      } finally {
        clearTimeout(timer);
        if (flights.get(key) === flight) flights.delete(key); // errors are not cached: the next get() asks again
      }
    })();
    flight.promise.catch(() => {}); // every waiter handles it; this only keeps an abandoned flight quiet
    return flight;
  };

  return {
    peek(lookup) {
      return answers.get(lookupKey(lookup)) ?? null;
    },
    get(lookup, signal) {
      const key = lookupKey(lookup);
      const hit = answers.get(key);
      if (hit) {
        remember(key, hit); // a use: most recent again
        return Promise.resolve(hit);
      }
      if (signal?.aborted) return Promise.reject(abortReason(signal));
      const flight = flights.get(key) ?? start(key, lookup);
      flight.waiters += 1;
      return new Promise<ObjectContextResponse>((resolve, reject) => {
        let waiting = true;
        const leave = () => {
          if (!waiting) return false;
          waiting = false;
          flight.waiters -= 1;
          signal?.removeEventListener('abort', onAbort);
          return true;
        };
        function onAbort() {
          if (!leave() || !signal) return;
          const reason = abortReason(signal);
          // Nobody needs this answer any more: free the server worker, one tick later so a caller that comes
          // right back (React StrictMode re-runs effects at once) joins this request instead of starting another.
          if (flight.waiters === 0) setTimeout(() => {
            if (flight.waiters > 0) return;
            if (flights.get(key) === flight) flights.delete(key);
            flight.controller.abort(reason);
          }, 0);
          reject(reason);
        }
        signal?.addEventListener('abort', onAbort, { once: true });
        flight.promise.then((data) => { if (leave()) resolve(data); }, (error: unknown) => { if (leave()) reject(error); });
      });
    },
    forget(lookup) {
      answers.delete(lookupKey(lookup));
    },
    inFlight: () => flights.size,
    size: () => answers.size,
  };
}

const shared = createObjectContextCache((lookup, signal) => client.getObjectContext(lookup, signal));

/** Answer already fetched in this session for `lookup` (no request). */
export function peekObjectContext(lookup: ObjectLookup | null): ObjectContextResponse | null {
  return shared.peek(lookup);
}

/** GET /api/object through the session cache: 0 requests for a lookup already answered, 1 shared request for
 *  callers waiting on the same lookup. Rejects with the request's error, or with `signal.reason` when aborted. */
export function getObjectContextCached(lookup: ObjectLookup, signal?: AbortSignal): Promise<ObjectContextResponse> {
  return shared.get(lookup, signal);
}

/** Forget the cached answer of `lookup` so the next request asks the backend again (Retry). */
export function forgetObjectContext(lookup: ObjectLookup | null): void {
  shared.forget(lookup);
}
