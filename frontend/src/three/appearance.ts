// Physics-driven look: temperature → color, and display-scale helpers.
// Everything here is an approximation for a MODEL REPRESENTATION, not an image.
import type { Body } from '../api/types';

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

/**
 * Approximate blackbody color (sRGB 0–255) for a temperature in kelvin.
 * Tanner Helland's fit, valid ~1000–40000 K; below 1000 K we fade to a dark red
 * (cold brown dwarfs emit almost nothing visible — their real color is debated).
 */
export function kelvinToRgb(kelvin: number): [number, number, number] {
  const t = clamp(kelvin, 1000, 40000) / 100;
  let r: number, g: number, b: number;
  if (t <= 66) {
    r = 255;
    g = 99.4708025861 * Math.log(t) - 161.1195681661;
    b = t <= 19 ? 0 : 138.5177312231 * Math.log(t - 10) - 305.0447927307;
  } else {
    r = 329.698727446 * Math.pow(t - 60, -0.1332047592);
    g = 288.1221695283 * Math.pow(t - 60, -0.0755148492);
    b = 255;
  }
  let rgb: [number, number, number] = [clamp(r, 0, 255), clamp(g, 0, 255), clamp(b, 0, 255)];
  if (kelvin < 1000) {
    const k = clamp((kelvin - 200) / 800, 0.15, 1); // dim toward black
    rgb = [rgb[0] * k, rgb[1] * k * 0.6, rgb[2] * k * 0.6];
  }
  return rgb.map(Math.round) as [number, number, number];
}

export function rgbToHex([r, g, b]: [number, number, number]): string {
  return '#' + [r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('');
}

/** Base color of a body: explicit override > temperature > per-model default. */
export function bodyColor(body: Body): string {
  if (body.appearance.color_hex) return body.appearance.color_hex;
  if (body.teff_k && (body.kind === 'star' || body.kind === 'brown_dwarf')) return rgbToHex(kelvinToRgb(body.teff_k));
  switch (body.appearance.model) {
    case 'gas_giant':
      return '#c9a27a';
    case 'icy':
      return '#bcd7e8';
    case 'disk':
      return '#d9a066';
    case 'brown_dwarf':
      return '#7a2e3b';
    default:
      return '#9a8f84';
  }
}

/**
 * Compressed distance mapping (AU → scene units) so 0.02 AU and 1500 AU fit in one view.
 * Linear up to the system's smallest orbit (`refAu` → 3 units), logarithmic beyond it:
 * each ×10 in distance adds 10 units. Continuous and monotonic.
 */
export function compressDistance(au: number, refAu: number): number {
  const r = au / refAu;
  return r <= 1 ? 3 * r : 3 + 10 * Math.log10(r);
}

/** Exaggerated, always-visible display radius (scene units) from a physical radius. */
export function displayRadius(body: Body): number {
  if (body.kind === 'disk') return 0;
  const km = body.radius_km ?? (body.kind === 'star' ? 700000 : 3000);
  // Earth (6371 km) → ~0.35, Jupiter → ~0.6, Sun → ~1.2, giant stars capped.
  return clamp(0.12 * Math.pow(km, 0.18), 0.12, 2.2);
}

export const KIND_LABEL: Record<string, string> = {
  star: 'Star',
  brown_dwarf: 'Brown dwarf',
  planet: 'Planet',
  dwarf_planet: 'Dwarf planet',
  moon: 'Moon',
  asteroid: 'Asteroid',
  comet: 'Comet',
  tno: 'Trans-Neptunian object',
  disk: 'Disk',
  unknown: 'Unknown',
};
