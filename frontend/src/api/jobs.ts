import type { Client } from './client';
import type { JobStatusResponse, JobSubmitRequest, SkyCoord } from './types';

/** RA sexagesimal is hours; declination sexagesimal is signed degrees. */
export function parseCoordinate(value: string, ra: boolean): number {
  const text = value.trim().replace(/−/g, '-');
  if (!text) throw new Error(`${ra ? 'RA' : 'Declination'} is required.`);
  const parts = text.split(/[:\s]+/);
  let degrees: number;
  if (parts.length === 1 && /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(text)) degrees = Number(text);
  else if (parts.length === 3 && parts.every((p) => /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(p))) {
    const [a, m, s] = parts.map(Number);
    if (!Number.isInteger(a) || m < 0 || m >= 60 || s < 0 || s >= 60 || (ra && text.startsWith('-')))
      throw new Error('Invalid sexagesimal coordinate. Use HH:MM:SS or ±DD:MM:SS.');
    degrees = (Math.abs(a) + m / 60 + s / 3600) * (text.startsWith('-') ? -1 : 1) * (ra ? 15 : 1);
  } else throw new Error('Use decimal degrees or three sexagesimal components.');
  if (!Number.isFinite(degrees) || (ra ? degrees < 0 || degrees >= 360 : degrees < -90 || degrees > 90))
    throw new Error(ra ? 'RA must be ≥ 0 and < 360 degrees.' : 'Declination must be between −90 and +90 degrees.');
  return degrees;
}

export function readPosition(search: string): JobSubmitRequest {
  const p = new URLSearchParams(search);
  const ra = parseCoordinate(p.get('ra') ?? '269.44623', true);
  const dec = parseCoordinate(p.get('dec') ?? '4.76870', false);
  const size_deg = Number(p.get('fov') ?? '0.25');
  const detector = Number(p.get('detector') ?? '2');
  if (!Number.isFinite(size_deg) || size_deg < 0.01 || size_deg > 0.5) throw new Error('FOV must be 0.01–0.5 degrees.');
  if (!Number.isInteger(detector) || detector < 1 || detector > 6) throw new Error('Detector must be 1–6.');
  return { ra, dec, size_deg, detectors: [detector], max_frames: 40 };
}

export function positionUrl(url: string, request: JobSubmitRequest, jobId?: string): string {
  const next = new URL(url);
  for (const [key, value] of Object.entries({ ra: request.ra, dec: request.dec, fov: request.size_deg ?? 0.25,
    detector: request.detectors?.[0] ?? 2 })) next.searchParams.set(key, String(value));
  next.searchParams.delete('job');
  if (jobId) next.searchParams.set('job', jobId);
  next.hash = '/';
  return next.toString();
}

export function isTerminal(job: JobStatusResponse): boolean {
  return job.status !== 'queued' && job.status !== 'running';
}

function pause(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const abort = () => { clearTimeout(timer); reject(new DOMException('Stopped watching', 'AbortError')); };
    const timer = setTimeout(() => { signal.removeEventListener('abort', abort); resolve(); }, ms);
    if (signal.aborted) abort(); else signal.addEventListener('abort', abort, { once: true });
  });
}

/** Stops on every terminal state, abort, network error or bounded watch time. Never resubmits. */
export async function watchJob(api: Pick<Client, 'getJob'>, initial: JobStatusResponse,
  signal: AbortSignal, update: (job: JobStatusResponse) => void, intervalMs = 2000): Promise<JobStatusResponse> {
  let job = initial;
  const deadline = Date.now() + 20 * 60_000;
  signal.throwIfAborted();
  update(job);
  while (!isTerminal(job)) {
    await pause(intervalMs, signal);
    if (Date.now() > deadline) throw new Error('Stopped waiting after 20 minutes. Resume watching this job later.');
    job = await api.getJob(job.id, signal);
    signal.throwIfAborted();
    update(job);
  }
  if (job.status === 'ready' && !job.result_field_id) throw new Error('The server returned ready without a field ID.');
  return job;
}

export function validPosition(value: unknown): value is SkyCoord {
  if (!value || typeof value !== 'object') return false;
  const p = value as SkyCoord;
  return Number.isFinite(p.ra) && p.ra >= 0 && p.ra < 360 && Number.isFinite(p.dec) && p.dec >= -90 && p.dec <= 90;
}
