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

  async function getJson<T>(url: string): Promise<T> {
    const res = await fetch(url);
    if (!res.ok) throw new ApiError(`${res.status} ${res.statusText} — ${url}`, res.status);
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

  return {
    config,
    resourceUrl,
    fieldFileUrl,
    frameImageUrl: (fieldId: string, frame: Frame) => fieldFileUrl(fieldId, frame.image),
    getManifest: () => getJson<Manifest>(resourceUrl('manifest')),
    getField: (id: string) => getJson<Field>(resourceUrl('field', id)),
    getCandidates: (id: string) => getJson<CandidateList>(resourceUrl('candidates', id)),
    getKnown: (id: string) => getJson<KnownObjectList>(resourceUrl('known', id)),

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
