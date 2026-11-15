// Everything SystemViewer builds its controls, legends and dataset-time HUD from, gathered in one module
// that the viewer loads on demand (dynamic import, in parallel with the three.js scene). None of it, nor
// the coverage and ephemeris tables behind it, ships in the main chunk. Pure: no React, no three.js.
import type { Body, OrbitQuality, SystemModel } from '../api/types';
import { isLineOfSightOrbit } from './ephemerides';

export {
  COLOR_MODE_LABEL,
  COLOR_MODES,
  colorLegend,
  colourModeChip,
  DEFAULT_COLOR_MODE,
  isInfraredMode,
  surfaceLegend,
} from './colorModes';
export { nonFittedOrbits, ORBIT_COLOR, spinLegend, suggestedSpeed } from './sceneLayout';
export {
  ARC_HALF_WIDTH_SIGMA,
  CLOUD_POINTS,
  LINE_OF_SIGHT_LABEL,
  onThisDate,
  UNCERTAINTY_COLOR,
  variabilityTracks,
} from './ephemerides';
export {
  datasetBounds,
  datasetSpeed,
  datasetWindow,
  freeRunningArbitraryPhase,
  mjdToIsoDate,
  phaseStatusLine,
} from './spherexCoverage';

export interface DatasetLegend {
  /** Some dated orbit gets an arc of phase uncertainty. */
  arc: boolean;
  /** Fitted orbits without an epoch: the ring shows where the body could be. */
  fittedRing: boolean;
  /** Assumed or hypothetical orbits without an epoch: neither the orbit nor the phase is known. */
  guessedRing: OrbitQuality[];
  /** Some dated circle in the reference plane gets the 'toward Earth' arrow. */
  lineOfSight: boolean;
}

/** What the dataset-time legend has to explain for this system (disks have no phase). */
export function datasetLegend(system: Pick<SystemModel, 'bodies'>): DatasetLegend {
  const orbiting = system.bodies.filter((b): b is Body & { orbit: NonNullable<Body['orbit']> } => !!b.orbit && b.kind !== 'disk');
  const undated = orbiting.filter((b) => b.orbit.epoch_mjd == null).map((b) => b.orbit.quality ?? 'fitted');
  return {
    arc: orbiting.some((b) => b.orbit.epoch_mjd != null),
    fittedRing: undated.includes('fitted'),
    guessedRing: [...new Set(undated.filter((q) => q !== 'fitted'))],
    lineOfSight: orbiting.some((b) => isLineOfSightOrbit(b.orbit)),
  };
}
