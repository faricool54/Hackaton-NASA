import { afterEach, describe, expect, it, vi } from 'vitest';
import { createClient } from './client';
import { parseCoordinate, positionUrl, readPosition, watchJob } from './jobs';
import type { JobStatusResponse } from './types';

const api = createClient({ mode: 'api', apiBase: 'http://api', staticBase: '/data/demo/' });
const queued: JobStatusResponse = { id: 'one', status: 'queued', stage: 'queued',
  created_at: '2026-11-14T00:00:00Z', updated_at: '2026-11-14T00:00:00Z', result_field_id: null, error_detail: null };
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

describe('coordinate input and sharing', () => {
  it('normalizes decimal and signed sexagesimal coordinates', () => {
    expect(parseCoordinate('17:57:48', true)).toBeCloseTo(269.45);
    expect(parseCoordinate('−00 30 00', false)).toBe(-0.5);
    expect(parseCoordinate('359.9999999', true)).toBe(359.9999999);
    expect(parseCoordinate('+90', false)).toBe(90);
  });
  it.each(['', 'NaN', 'Infinity', '360', '-1', '24:00:00', '17:60:00', '17:-1:00', '1:2', '-0:30:00'])
    ('rejects invalid RA %s', (text) => expect(() => parseCoordinate(text, true)).toThrow());
  it('preserves deployment path, mode and dataset in position links', () => {
    const request = readPosition('?ra=133.7598387&dec=-7.2421674&fov=0.2&detector=6');
    const url = positionUrl('https://example.org/Hackaton-NASA/?mode=api&dataset=real&job=old#/field/old', request, 'new');
    expect(new URL(url).pathname).toBe('/Hackaton-NASA/');
    expect(new URL(url).searchParams.get('mode')).toBe('api');
    expect(new URL(url).searchParams.get('job')).toBe('new');
    expect(readPosition(new URL(url).search)).toEqual(request);
    expect(new URL(positionUrl(url, request)).searchParams.has('job')).toBe(false);
  });
  it.each(['?ra=oops', '?dec=91', '?fov=0', '?detector=2.5', '?fov=Infinity'])
    ('rejects invalid shared input %s', (search) => expect(() => readPosition(search)).toThrow());
});

describe('job client and polling', () => {
  it('posts the bounded request and encodes names and job IDs', async () => {
    const fetch = vi.fn().mockImplementation(async () => new Response(JSON.stringify(queued), { status: 202 }));
    vi.stubGlobal('fetch', fetch);
    const request = readPosition('');
    await api.submitJob(request);
    expect(fetch.mock.calls[0][0]).toBe('http://api/api/jobs');
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual(request);
    expect(fetch.mock.calls[0][1].method).toBe('POST');
    await api.resolveName('a&b?');
    expect(fetch.mock.calls[1][0]).toBe('http://api/api/resolve-name?name=a%26b%3F');
    await api.getJob('a/b');
    expect(fetch.mock.calls[2][0]).toBe('http://api/api/jobs/a%2Fb');
  });
  it('exposes server validation and queue/disabled errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ detail: [
      { loc: ['body', 'ra'], msg: 'must be < 360' }] }), { status: 422 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'Job engine is disabled.' }), { status: 503 })));
    await expect(api.submitJob({ ra: 360, dec: 0 })).rejects.toThrow('ra: must be < 360');
    await expect(api.getJob('one')).rejects.toThrow('Job engine is disabled.');
  });
  it('never submits jobs in static mode', async () => {
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
    const staticApi = createClient({ mode: 'static', apiBase: '', staticBase: '/data/demo/' });
    await expect(staticApi.submitJob({ ra: 0, dec: 0 })).rejects.toThrow('live API');
    expect(fetch).not.toHaveBeenCalled();
  });
  it.each(['ready', 'failed', 'no_coverage', 'pipeline_not_ready'] as const)
    ('stops at %s without another request', async (status) => {
      const getJob = vi.fn();
      const terminal = { ...queued, status, result_field_id: status === 'ready' ? 'real' : null };
      expect(await watchJob({ getJob }, terminal, new AbortController().signal, vi.fn(), 1)).toEqual(terminal);
      expect(getJob).not.toHaveBeenCalled();
    });
  it('polls queued → running → ready and reports each transition', async () => {
    const ready = { ...queued, status: 'ready' as const, result_field_id: 'real' };
    const getJob = vi.fn().mockResolvedValueOnce({ ...queued, status: 'running' }).mockResolvedValueOnce(ready);
    const update = vi.fn();
    expect(await watchJob({ getJob }, queued, new AbortController().signal, update, 1)).toEqual(ready);
    expect(update.mock.calls.map(([job]) => job.status)).toEqual(['queued', 'running', 'ready']);
  });
  it('aborts pending observation without a request', async () => {
    const abort = new AbortController(); const getJob = vi.fn();
    const watching = watchJob({ getJob }, queued, abort.signal, vi.fn(), 1000);
    abort.abort(); await expect(watching).rejects.toMatchObject({ name: 'AbortError' });
    expect(getJob).not.toHaveBeenCalled();
  });
  it('does not report stale data when an aborted fetch resolves', async () => {
    const abort = new AbortController(); const update = vi.fn();
    const getJob = vi.fn(async () => { abort.abort(); return { ...queued, status: 'ready' as const, result_field_id: 'stale' }; });
    await expect(watchJob({ getJob }, queued, abort.signal, update, 1)).rejects.toMatchObject({ name: 'AbortError' });
    expect(update).toHaveBeenCalledTimes(1);
  });
  it('rejects a ready response that cannot open a field', async () => {
    await expect(watchJob({ getJob: vi.fn() }, { ...queued, status: 'ready' }, new AbortController().signal,
      vi.fn(), 1)).rejects.toThrow('without a field ID');
  });
});
