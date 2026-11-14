// SPHEREx detector bands for the physics core (astro.ts). Pure data, no three.js.
//
// Source: docs/RECON_SPHEREX.md §2.2 (2026-11-14), which records
//   - band edges = IRSA SIA em_min–em_max per detector (live queries of spherex_dr1 / spherex_qr3),
//   - resolving power R, PSF FWHM, the 6.15″ pixel (6.152″ measured as sqrt|det PC|) and the
//     non-linearity onsets (AB, Explanatory Supplement Table 25, a PRE-LAUNCH model),
//   - 17 spectral channels per detector (Explanatory Supplement v2.1, Tables 29–34).
// Only the D1 channel centres are transcribed in the recon; the full tables live in the Supplement.
// The channel centres below are therefore a MODEL: 17 equal steps in log(λ) between the band edges
// (bin centres), which reproduces the published D1 centres within 0.4 % (about an eighth of a
// channel width, λ/R ≈ 2.6 %).

export type SpherexDetectorId = 'D1' | 'D2' | 'D3' | 'D4' | 'D5' | 'D6';

export interface SpherexDetector {
  readonly id: SpherexDetectorId;
  /** Detector number as in Frame.detector (1-6). */
  readonly index: 1 | 2 | 3 | 4 | 5 | 6;
  /** Band edges (µm), IRSA SIA em_min–em_max. */
  readonly lambdaMinUm: number;
  readonly lambdaMaxUm: number;
  /** Spectral resolving power λ/Δλ. */
  readonly resolvingPower: number;
  /** PSF full width at half maximum (arcsec). */
  readonly psfFwhmArcsec: number;
  /** AB magnitude brighter than which the response becomes non-linear (pre-launch model). */
  readonly nonLinearityOnsetAB: number;
  /** Detector array: SWIR = H2RG 2.6 µm cutoff at 62 K, MWIR = 5.3 µm cutoff at 45 K. */
  readonly array: 'SWIR' | 'MWIR';
  /** Detector that sees the same sky at the same instant through the dichroic. */
  readonly dichroicPair: SpherexDetectorId;
  /** 17 channel centres (µm): log-uniform bin centres between the edges (a MODEL, see header). */
  readonly channelCentersUm: readonly number[];
}

/** SPHEREx pixel scale (arcsec). */
export const SPHEREX_PIXEL_ARCSEC = 6.15;

/** Spectral channels per detector (102 in total). */
export const SPHEREX_CHANNELS_PER_DETECTOR = 17;

export const SPHEREX_BANDS_CITATION =
  'docs/RECON_SPHEREX.md §2.2 (2026-11-14): IRSA SIA em_min–em_max per detector; SPHEREx Explanatory Supplement v2.1 (R, PSF, channels; non-linearity onsets from its Table 25, pre-launch model)';

/** Published D1 channel centres (µm), RECON §2.2 — used only to check the log-uniform model. */
export const SPHEREX_D1_PUBLISHED_CENTERS_UM: readonly number[] = [
  0.753, 0.771, 0.79, 0.809, 0.828, 0.848, 0.868, 0.889, 0.91, 0.932, 0.955, 0.978, 1.001, 1.025, 1.05, 1.075, 1.102,
];

/** Centres of n equal bins in log(λ) between lo and hi. */
function logUniformCenters(lo: number, hi: number, n: number): number[] {
  const step = Math.log(hi / lo) / n;
  return Array.from({ length: n }, (_, i) => lo * Math.exp((i + 0.5) * step));
}

type DetectorRow = Omit<SpherexDetector, 'channelCentersUm'>;

const ROWS: readonly DetectorRow[] = [
  { id: 'D1', index: 1, lambdaMinUm: 0.746, lambdaMaxUm: 1.117, resolvingPower: 39, psfFwhmArcsec: 7.1, nonLinearityOnsetAB: 11.5, array: 'SWIR', dichroicPair: 'D4' },
  { id: 'D2', index: 2, lambdaMinUm: 1.103, lambdaMaxUm: 1.65, resolvingPower: 41, psfFwhmArcsec: 6.9, nonLinearityOnsetAB: 11.5, array: 'SWIR', dichroicPair: 'D5' },
  { id: 'D3', index: 3, lambdaMinUm: 1.63, lambdaMaxUm: 2.435, resolvingPower: 41, psfFwhmArcsec: 6.9, nonLinearityOnsetAB: 11.3, array: 'SWIR', dichroicPair: 'D6' },
  { id: 'D4', index: 4, lambdaMinUm: 2.403, lambdaMaxUm: 3.847, resolvingPower: 35, psfFwhmArcsec: 7.7, nonLinearityOnsetAB: 11.71, array: 'MWIR', dichroicPair: 'D1' },
  { id: 'D5', index: 5, lambdaMinUm: 3.811, lambdaMaxUm: 4.43, resolvingPower: 112, psfFwhmArcsec: 8.0, nonLinearityOnsetAB: 10.19, array: 'MWIR', dichroicPair: 'D2' },
  { id: 'D6', index: 6, lambdaMinUm: 4.412, lambdaMaxUm: 5.01, resolvingPower: 128, psfFwhmArcsec: 8.3, nonLinearityOnsetAB: 9.75, array: 'MWIR', dichroicPair: 'D3' },
];

/** The six SPHEREx detectors, D1 (bluest) to D6. */
export const SPHEREX_DETECTORS: readonly SpherexDetector[] = ROWS.map((r) => ({
  ...r,
  channelCentersUm: logUniformCenters(r.lambdaMinUm, r.lambdaMaxUm, SPHEREX_CHANNELS_PER_DETECTOR),
}));
