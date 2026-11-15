import { afterEach, describe, expect, it, vi } from 'vitest';
import { describeObjectError, type ObjectLookup } from './objectCard';
import { createObjectContextCache, OBJECT_CACHE_SIZE, type ObjectContextFetcher } from './objectCardCache';
import type { ObjectContextResponse } from './types';

afterEach(() => vi.useRealTimers());

function answer(name: string): ObjectContextResponse {
  return { identity: { display_name: name } } as unknown as ObjectContextResponse; // the cache never reads inside
}

/** A fetcher whose requests the test settles by hand; an aborted request rejects with its signal's reason. */
function manualFetcher() {
  const calls: { lookup: ObjectLookup; signal: AbortSignal; resolve: (r: ObjectContextResponse) => void; reject: (e: unknown) => void }[] = [];
  const fetcher: ObjectContextFetcher = (lookup, signal) => new Promise((resolve, reject) => {
    calls.push({ lookup, signal, resolve, reject });
    signal.addEventListener('abort', () => reject(signal.reason), { once: true });
  });
  return { calls, fetcher };
}

const barnard: ObjectLookup = { name: "Barnard's Star" };
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

describe('object context cache', () => {
  it('answers a lookup already fetched without a new request (reselecting the same object)', async () => {
    const { calls, fetcher } = manualFetcher();
    const cache = createObjectContextCache(fetcher, { timeoutMs: 0 });
    expect(cache.peek(barnard)).toBeNull();
    const first = cache.get(barnard);
    calls[0].resolve(answer('Barnard'));
    await expect(first).resolves.toEqual(answer('Barnard'));
    expect(cache.peek(barnard)).toEqual(answer('Barnard'));
    await expect(cache.get({ name: "Barnard's Star" })).resolves.toBe(await first);
    expect(calls).toHaveLength(1);
    // a position lookup that rounds to the same key is the same lookup
    const p = cache.get({ ra: 269.452, dec: 4.6934 });
    calls[1].resolve(answer('pos'));
    await p;
    await cache.get({ ra: 269.45200000001, dec: 4.6934 });
    expect(calls).toHaveLength(2);
  });

  it('shares one request between callers waiting on the same lookup (single-flight)', async () => {
    const { calls, fetcher } = manualFetcher();
    const cache = createObjectContextCache(fetcher, { timeoutMs: 0 });
    const a = cache.get(barnard, new AbortController().signal);
    const b = cache.get(barnard);
    expect(calls).toHaveLength(1);
    expect(cache.inFlight()).toBe(1);
    calls[0].resolve(answer('Barnard'));
    expect(await a).toBe(await b);
    expect(cache.inFlight()).toBe(0);
  });

  it('keeps the request alive when one waiter leaves and another still needs it', async () => {
    const { calls, fetcher } = manualFetcher();
    const cache = createObjectContextCache(fetcher, { timeoutMs: 0 });
    const card = new AbortController();
    const cardWait = cache.get(barnard, card.signal);
    const threeD = cache.get(barnard, new AbortController().signal);
    card.abort(); // the card unmounts (another object was picked)
    await expect(cardWait).rejects.toMatchObject({ name: 'AbortError' });
    expect(calls[0].signal.aborted).toBe(false);
    calls[0].resolve(answer('Barnard'));
    await expect(threeD).resolves.toEqual(answer('Barnard'));
    expect(cache.peek(barnard)).toEqual(answer('Barnard'));
  });

  it('aborts the request when its last waiter leaves, and asks again next time', async () => {
    const { calls, fetcher } = manualFetcher();
    const cache = createObjectContextCache(fetcher, { timeoutMs: 0 });
    const a = new AbortController();
    const b = new AbortController();
    const waits = Promise.allSettled([cache.get(barnard, a.signal), cache.get(barnard, b.signal)]); // handled at once
    a.abort();
    await tick();
    expect(calls[0].signal.aborted).toBe(false);
    b.abort();
    await tick();
    expect(calls[0].signal.aborted).toBe(true);
    expect(cache.inFlight()).toBe(0);
    expect((await waits).map((w) => w.status)).toEqual(['rejected', 'rejected']);
    const again = cache.get(barnard);
    expect(calls).toHaveLength(2);
    calls[1].resolve(answer('Barnard'));
    await expect(again).resolves.toEqual(answer('Barnard'));
  });

  it('lets a caller that comes right back join the request instead of starting another (StrictMode remount)', async () => {
    const { calls, fetcher } = manualFetcher();
    const cache = createObjectContextCache(fetcher, { timeoutMs: 0 });
    const first = new AbortController();
    const firstWait = cache.get(barnard, first.signal);
    first.abort(); // effect cleanup
    const again = cache.get(barnard, new AbortController().signal); // effect re-run, same tick
    await expect(firstWait).rejects.toMatchObject({ name: 'AbortError' });
    await tick();
    expect(calls).toHaveLength(1);
    expect(calls[0].signal.aborted).toBe(false);
    calls[0].resolve(answer('Barnard'));
    await expect(again).resolves.toEqual(answer('Barnard'));
  });

  it('rejects an already aborted caller without a request', async () => {
    const { calls, fetcher } = manualFetcher();
    const cache = createObjectContextCache(fetcher, { timeoutMs: 0 });
    const gone = new AbortController();
    gone.abort();
    await expect(cache.get(barnard, gone.signal)).rejects.toMatchObject({ name: 'AbortError' });
    expect(calls).toHaveLength(0);
  });

  it('never caches an error: every waiter gets it and the next lookup asks again', async () => {
    const { calls, fetcher } = manualFetcher();
    const cache = createObjectContextCache(fetcher, { timeoutMs: 0 });
    const waits = [cache.get(barnard), cache.get(barnard)];
    calls[0].reject(new Error('503'));
    for (const w of waits) await expect(w).rejects.toThrow('503');
    expect(cache.peek(barnard)).toBeNull();
    expect(cache.inFlight()).toBe(0);
    void cache.get(barnard);
    expect(calls).toHaveLength(2);
  });

  it('never keeps a partial answer: every waiter gets it and the next lookup asks again', async () => {
    const { calls, fetcher } = manualFetcher();
    const cache = createObjectContextCache(fetcher, { timeoutMs: 0 });
    const waits = [cache.get(barnard), cache.get(barnard)];
    const partial = { ...answer('Barnard'), partial: true } as ObjectContextResponse;
    calls[0].resolve(partial);
    for (const w of waits) await expect(w).resolves.toBe(partial);
    expect(cache.peek(barnard)).toBeNull();
    expect(cache.inFlight()).toBe(0);
    const again = cache.get(barnard); // reselecting a partially answered object asks the backend, which heals it
    expect(calls).toHaveLength(2);
    const complete = { ...answer('Barnard'), partial: false } as ObjectContextResponse;
    calls[1].resolve(complete);
    await expect(again).resolves.toBe(complete);
    await expect(cache.get(barnard)).resolves.toBe(complete);
    expect(calls).toHaveLength(2); // the complete answer is kept: no request on the next reselection
  });

  it('clears a request whose fetcher throws at once', async () => {
    const cache = createObjectContextCache(() => { throw new Error('offline'); }, { timeoutMs: 0 });
    await expect(cache.get(barnard)).rejects.toThrow('offline');
    expect(cache.inFlight()).toBe(0);
  });

  it('turns a hung request into a timeout the card can explain', async () => {
    vi.useFakeTimers();
    const { calls, fetcher } = manualFetcher();
    const cache = createObjectContextCache(fetcher, { timeoutMs: 1000 });
    const wait = cache.get(barnard);
    const settled = wait.catch((e: unknown) => e);
    await vi.advanceTimersByTimeAsync(1000);
    expect(calls[0].signal.aborted).toBe(true);
    const error = await settled;
    expect(error).toMatchObject({ name: 'TimeoutError' });
    expect(describeObjectError(error)).toBe('Catalog context did not arrive in time; retry.');
    expect(cache.peek(barnard)).toBeNull();
  });

  it(`keeps the ${OBJECT_CACHE_SIZE} most recently used answers`, async () => {
    const cache = createObjectContextCache(async (lookup) => answer('name' in lookup ? lookup.name : '?'), { timeoutMs: 0 });
    for (let i = 0; i < OBJECT_CACHE_SIZE; i += 1) await cache.get({ name: `star ${i}` });
    await cache.get({ name: 'star 0' }); // used again: no longer the oldest
    expect(cache.peek({ name: 'star 1' })).not.toBeNull(); // peek is a pure read: star 1 stays the oldest
    await cache.get({ name: 'star 50' });
    expect(cache.size()).toBe(OBJECT_CACHE_SIZE);
    expect(cache.peek({ name: 'star 0' })).not.toBeNull();
    expect(cache.peek({ name: 'star 1' })).toBeNull();
    expect(cache.peek({ name: 'star 50' })).not.toBeNull();
  });

  it('forgets one answer on request (Retry after a partial answer)', async () => {
    const fetcher = vi.fn(async () => answer('Barnard'));
    const cache = createObjectContextCache(fetcher, { timeoutMs: 0 });
    await cache.get(barnard);
    cache.forget(barnard);
    expect(cache.peek(barnard)).toBeNull();
    await cache.get(barnard);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
