// Optional page-level inputs of the 3D viewer, as a React context. SystemViewer also takes them as
// props (props win); the context exists so SystemPage can supply them while keeping its existing
// <SystemViewer ... /> line verbatim (that line is shared with other workstreams). Tiny: main chunk.
import { createContext } from 'react';

export interface SystemViewerLink {
  /**
   * Whether the manifest lists the system's field (the page has fetched it already). When given, the
   * viewer does not fetch the manifest again; when absent it fetches it itself.
   */
  fieldExists?: boolean;
  /** Dataset-time date (MJD) each time the calendar day changes; null in free-running and on unmount. */
  onDatasetMjd?: (mjd: number | null) => void;
}

export const SystemViewerContext = createContext<SystemViewerLink>({});
