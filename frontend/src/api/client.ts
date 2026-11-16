// Data access for the UI. Two modes, same functions:
//   static (default): reads JSON/PNG copied into public/data/<dataset>/ (no backend needed,
//                     deployable to GitHub Pages / Vercel / Netlify)
//   api:              talks to the FastAPI backend (VITE_DATA_MODE=api, VITE_API_BASE=...)
// Dataset: 'demo' (synthetic) or 'real'. Override with ?dataset=real in the URL.
import type {
  CandidateList,
  Field,
  Frame,
  KnownObject,
  KnownObjectList,
  Manifest,
  SearchResult,
  SystemModel,
  JobSubmitRequest,
  JobStatusResponse,
  ResolvedRegion,
  SpectrumRequest,
  SpectrumResponse,
  ComparisonRequest,
  ComparisonResponse,
  ObjectContextResponse,
  LightCurveProduct,
} from './types';

export type DataMode = 'static' | 'api';

export interface ClientConfig {
  mode: DataMode;
  apiBase: string;
  staticBase: string; // e.g. '/data/demo/'
}

function envConfig(): ClientConfig {
  const env = import.meta.env;
  const params = new URLSearchParams(globalThis.location?.search ?? '');
  const dataset = params.get('dataset') ?? env.VITE_DATASET ?? 'demo';
  return {
    mode: (params.get('mode') ?? env.VITE_DATA_MODE ?? 'static') as DataMode,
    apiBase: (env.VITE_API_BASE ?? 'http://localhost:8000').replace(/\/$/, ''),
    staticBase: `${env.BASE_URL ?? '/'}data/${dataset}/`,
  };
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

export function createClient(config: ClientConfig = envConfig()) {
  const { mode, apiBase, staticBase } = config;

  async function getJson<T>(url: string, init?: RequestInit): Promise<T> {
    const res = await fetch(url, init);
    if (!res.ok) {
      let detail = `${res.status} ${res.statusText}`;
      try {
        const body = await res.json();
        if (typeof body.detail === 'string') detail = body.detail;
        else if (Array.isArray(body.detail)) {
          detail = body.detail.map((e: { loc?: string[]; msg?: string }) =>
            `${e.loc?.slice(1).join('.') ?? 'Request'}: ${e.msg ?? 'invalid value'}`).join('; ');
        }
      } catch { /* Non-JSON proxy errors still have an HTTP status. */ }
      throw new ApiError(detail, res.status);
    }
    return (await res.json()) as T;
  }

  /** URL of a JSON resource in either mode. */
  function resourceUrl(kind: 'manifest' | 'field' | 'candidates' | 'known', fieldId?: string): string {
    if (mode === 'api') {
      switch (kind) {
        case 'manifest':
          return `${apiBase}/api/manifest`;
        case 'field':
          return `${apiBase}/api/fields/${fieldId}`;
        default:
          return `${apiBase}/api/fields/${fieldId}/${kind}`;
      }
    }
    return kind === 'manifest'
      ? `${staticBase}manifest.json`
      : `${staticBase}fields/${fieldId}/${kind === 'field' ? 'field' : kind}.json`;
  }

  /** URL of a file inside a field directory (frame PNGs, thumbnails). */
  function fieldFileUrl(fieldId: string, relPath: string): string {
    const root = mode === 'api' ? `${apiBase}/data/` : staticBase;
    return `${root}fields/${fieldId}/${relPath}`;
  }

  /** 3D system model (WS7): <root>/systems/<id>.json or /api/systems/<id>. */
  function systemUrl(systemId: string): string {
    return mode === 'api' ? `${apiBase}/api/systems/${systemId}` : `${staticBase}systems/${systemId}.json`;
  }

  /** Precomputed light curve: /api/lightcurves/<id>, or <root>/lightcurves/<id>.json written by
   *  scripts/export_static_science.py for static deploys. */
  function lightCurveUrl(targetId: string): string {
    const id = encodeURIComponent(targetId);
    return mode === 'api' ? `${apiBase}/api/lightcurves/${id}` : `${staticBase}lightcurves/${id}.json`;
  }

  return {
    config,
    resourceUrl,
    fieldFileUrl,
    frameImageUrl: (fieldId: string, frame: Frame) => fieldFileUrl(fieldId, frame.image),
    getManifest: () => getJson<Manifest>(resourceUrl('manifest')),
    getField: (id: string) => getJson<Field>(resourceUrl('field', id)),
    getCandidates: (id: string) => getJson<CandidateList>(resourceUrl('candidates', id)),
    getKnown: (id: string) => getJson<KnownObjectList>(resourceUrl('known', id)),
    systemUrl,
    getSystem: (id: string) => getJson<SystemModel>(systemUrl(id)),

    async resolveName(name: string, signal?: AbortSignal): Promise<ResolvedRegion> {
      if (mode !== 'api') throw new ApiError('Name lookup requires live API mode.', 0);
      return getJson<ResolvedRegion>(`${apiBase}/api/resolve-name?${new URLSearchParams({ name })}`, { signal });
    },
    async submitJob(body: JobSubmitRequest, signal?: AbortSignal): Promise<JobStatusResponse> {
      if (mode !== 'api') throw new ApiError('Arbitrary coordinates require live API mode.', 0);
      return getJson<JobStatusResponse>(`${apiBase}/api/jobs`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal,
      });
    },
    async getJob(id: string, signal?: AbortSignal): Promise<JobStatusResponse> {
      if (mode !== 'api') throw new ApiError('Jobs require live API mode.', 0);
      return getJson<JobStatusResponse>(`${apiBase}/api/jobs/${encodeURIComponent(id)}`, { signal });
    },
    async getSpectrum(body: SpectrumRequest, signal?: AbortSignal): Promise<SpectrumResponse> {
      if (mode !== 'api') throw new ApiError('Spectra require live API mode.', 0);
      return getJson<SpectrumResponse>(`${apiBase}/api/spectra`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal,
      });
    },
    lightCurveUrl,
    async getLightCurve(targetId: string, signal?: AbortSignal): Promise<LightCurveProduct> {
      if (mode === 'api') return getJson<LightCurveProduct>(lightCurveUrl(targetId), { signal });
      const res = await fetch(lightCurveUrl(targetId), { signal });
      // Static hosts with an SPA fallback answer a missing file with the HTML app shell: that is a 404 too.
      if (res.status === 404 || (res.ok && /html/i.test(res.headers.get('content-type') ?? ''))) {
        throw new ApiError('No precomputed light curve is published for this field.', 404);
      }
      if (!res.ok) throw new ApiError(`${res.status} ${res.statusText}`, res.status);
      return (await res.json()) as LightCurveProduct;
    },
    async getComparisons(id: string, body: ComparisonRequest, signal?: AbortSignal): Promise<ComparisonResponse> {
      if (mode !== 'api') throw new ApiError('Comparisons require live API mode.', 0);
      return getJson<ComparisonResponse>(`${apiBase}/api/fields/${encodeURIComponent(id)}/comparisons`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal,
      });
    },
    /** Catalog context for the object card: exactly one of a name or a position (contract 0.5.0). A position may
     *  also give its match radius (arcsec) and epoch (MJD); the API defaults apply when they are absent. */
    async getObjectContext(
      lookup: { name: string } | { ra: number; dec: number; radiusArcsec?: number; epochMjd?: number },
      signal?: AbortSignal): Promise<ObjectContextResponse> {
      if (mode !== 'api') throw new ApiError('Catalog context requires live API mode.', 0);
      const params = 'name' in lookup ? new URLSearchParams({ name: lookup.name })
        : new URLSearchParams({ ra: String(lookup.ra), dec: String(lookup.dec) });
      if (!('name' in lookup)) {
        if (lookup.radiusArcsec !== undefined && Number.isFinite(lookup.radiusArcsec)) params.set('radius_arcsec', String(lookup.radiusArcsec));
        if (lookup.epochMjd !== undefined && Number.isFinite(lookup.epochMjd)) params.set('epoch_mjd', String(lookup.epochMjd));
      }
      return getJson<ObjectContextResponse>(`${apiBase}/api/object?${params}`, { signal });
    },
    analysisImageUrl: (path: string) => `${apiBase}/data/${path}`,

    /** Live archive search — only in api mode (WS1+WS4). */
    async searchArchive(ra: number, dec: number): Promise<SearchResult> {
      if (mode !== 'api') throw new ApiError('Archive search needs the backend (VITE_DATA_MODE=api)', 0);
      return getJson<SearchResult>(`${apiBase}/api/search?ra=${ra}&dec=${dec}`);
    },
    /** Live known-object lookup — only in api mode (WS3+WS4). */
    async knownObjectsAt(ra: number, dec: number, mjd: number, radiusDeg = 0.25): Promise<KnownObject[]> {
      if (mode !== 'api') throw new ApiError('Live lookup needs the backend (VITE_DATA_MODE=api)', 0);
      return getJson<KnownObject[]>(
        `${apiBase}/api/known-objects?ra=${ra}&dec=${dec}&mjd=${mjd}&radius_deg=${radiusDeg}`,
      );
    },
  };
}

export type Client = ReturnType<typeof createClient>;
export const client = createClient();
