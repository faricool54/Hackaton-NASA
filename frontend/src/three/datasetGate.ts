// The two facts the 3D viewer needs before its dataset-time helpers load: which systems have SPHEREx
// archive coverage, and whether a set of frames gives a dataset window. Kept tiny and dependency-free
// (types only) because SystemViewer imports it statically, i.e. it ships in the main chunk; the
// coverage tables themselves (spherexCoverage.ts) load on demand with the 3D view.
import type { Frame } from '../api/types';

/** Systems with a row in spherexCoverage.SPHEREX_COVERAGE (its Record type keeps the two in step). */
export const SPHEREX_TARGET_IDS = ['barnards-star', 'epsilon-indi', 'wise-0855', 'r-draconis', 'rw-aurigae'] as const;

export type SpherexTargetId = (typeof SPHEREX_TARGET_IDS)[number];

export function isSpherexTarget(id: string): id is SpherexTargetId {
  return (SPHEREX_TARGET_IDS as readonly string[]).includes(id);
}

/**
 * True exactly when spherexCoverage.datasetWindow(system, frames) is not null (tested there): the
 * target has archive coverage, or the field's frames include at least one finite time.
 */
export function hasDatasetWindow(systemId: string, frames?: readonly Pick<Frame, 'mjd'>[] | null): boolean {
  return isSpherexTarget(systemId) || (frames ?? []).some((f) => Number.isFinite(f.mjd));
}
