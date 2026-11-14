// Shader materials of the 3D scene (M2/M3). Loaded only with SystemScene (the lazy three.js chunk).
//
// Star material: one ShaderMaterial per star, one draw call, no textures and nothing rebuilt per
// frame (only uniforms change). It draws
//   - limb darkening and limb reddening from a per-channel table I(μ)/I(1) (uLd, 16 × vec3): the
//     grey Eddington atmosphere of astro.limbDarkeningLut in visible mode, or the same model at the
//     IR channel centres in SPHEREx false colour (colorModes.irLimbDarkeningLut). MODEL.
//   - convection cells only where astro.granulationParams says they are resolvable (uGranCells > 0;
//     today only R Draconis, once it has a mass): 3D cellular noise in object space, seeded by the
//     body id, cross-faded to a new pattern every turnover time (uPhase = mjd / τ), so the pattern
//     evolves with model time and scrubbing is deterministic. Cell size MODEL, contrast ILLUSTRATIVE.
//   - base colour (linear) × display brightness, then three's tone mapping and output colour space.
// It is still a Mesh, so raycast selection keeps working.
//
// Rim material: a Fresnel outline that keeps a dark body (a near-black brown dwarf in visible light,
// a planet whose SPHEREx emission is not modelled) findable on the black sky. Dashed for bodies drawn
// only qualitatively (below 2500 K in IR mode). DISPLAY: it is not light the body emits.
import * as THREE from 'three';

/** Entries of the limb-darkening table (μ = i / 15), as in astro.limbDarkeningLut's default. */
export const LD_SAMPLES = 16;

const STAR_VERTEX = /* glsl */ `
varying vec3 vNormalView;
varying vec3 vViewPos;
varying vec3 vObjPos;
void main() {
  vObjPos = position;
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  vViewPos = mv.xyz;
  vNormalView = normalize(normalMatrix * normal);
  gl_Position = projectionMatrix * mv;
}
`;

const STAR_FRAGMENT = /* glsl */ `
uniform vec3 uLd[LD_N];
uniform vec3 uColor;
uniform float uBrightness;
uniform float uGranCells;
uniform float uContrast;
uniform float uPhase;
uniform vec3 uSeed;
varying vec3 vNormalView;
varying vec3 vViewPos;
varying vec3 vObjPos;

vec3 limb(float mu) {
  float x = clamp(mu, 0.0, 1.0) * float(LD_N - 1);
  int i = int(min(floor(x), float(LD_N - 2)));
  return mix(uLd[i], uLd[i + 1], x - float(i));
}

// Sine-free hash (D. Hoskins, "Hash without Sine"): stable in float precision for lattice
// coordinates up to a few thousand.
vec3 hash3(vec3 p3) {
  p3 = fract(p3 * vec3(0.1031, 0.1030, 0.0973));
  p3 += dot(p3, p3.yxz + 33.33);
  return fract((p3.xxy + p3.yxx) * p3.zyx);
}

// Cellular (Worley) noise: distances to the nearest and second-nearest feature points.
vec2 worley(vec3 p) {
  vec3 cell = floor(p);
  vec3 f = fract(p);
  float d1 = 8.0;
  float d2 = 8.0;
  for (int x = -1; x <= 1; x++) {
    for (int y = -1; y <= 1; y++) {
      for (int z = -1; z <= 1; z++) {
        vec3 g = vec3(float(x), float(y), float(z));
        vec3 r = g + hash3(cell + g) - f;
        float d = dot(r, r);
        if (d < d1) { d2 = d1; d1 = d; } else if (d < d2) { d2 = d; }
      }
    }
  }
  return sqrt(vec2(d1, d2));
}

// Bright cell interiors, dark intergranular lanes: 0 on a lane, 1 well inside a cell.
float cells(vec3 p, float layer) {
  vec2 w = worley(p + uSeed + vec3(7.0, 13.0, 19.0) * layer);
  return smoothstep(0.0, 0.35, w.y - w.x);
}

void main() {
  float mu = clamp(dot(normalize(vNormalView), normalize(-vViewPos)), 0.0, 1.0);
  vec3 c = uColor * limb(mu) * uBrightness;
  if (uGranCells > 0.0) {
    // uGranCells cells across the diameter (2 units of the unit sphere): frequency = cells / 2.
    vec3 p = normalize(vObjPos) * (0.5 * uGranCells);
    float k = floor(uPhase);
    float w = smoothstep(0.0, 1.0, uPhase - k);
    float g = mix(cells(p, mod(k, 64.0)), cells(p, mod(k + 1.0, 64.0)), w);
    c *= 1.0 + uContrast * (2.0 * g - 1.0);
  }
  gl_FragColor = vec4(c, 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}
`;

export interface StarLook {
  /** Limb-darkening table, LD_SAMPLES × [r, g, b] (μ = i / (LD_SAMPLES − 1)). */
  readonly ld: Float32Array;
  /** Base colour, sRGB-encoded channel values in [0, 1]. */
  readonly hue: readonly [number, number, number];
  /** Display brightness, linear-light multiplier in [0, 1]. */
  readonly brightness: number;
}

export interface Granulation {
  /** Cells across the diameter (0 = not drawn). */
  readonly cells: number;
  /** Intensity contrast (± fraction). */
  readonly contrast: number;
  /** Noise seed (32-bit integer, e.g. astro.granulationParams(body).seed). */
  readonly seed: number;
}

/** A 32-bit seed → a small object-space offset (keeps the noise arguments small for float precision). */
function seedOffset(seed: number): THREE.Vector3 {
  const s = seed >>> 0;
  return new THREE.Vector3((s & 1023) / 10.24, ((s >>> 10) & 1023) / 10.24, ((s >>> 20) & 1023) / 10.24);
}

function ldArray(ld: Float32Array): Float32Array {
  if (ld.length === LD_SAMPLES * 3) return ld;
  // Resample any other table length (linear in μ) so the uniform array size is fixed.
  const n = ld.length / 3;
  const out = new Float32Array(LD_SAMPLES * 3);
  for (let i = 0; i < LD_SAMPLES; i++) {
    const x = (i / (LD_SAMPLES - 1)) * (n - 1);
    const j = Math.min(Math.floor(x), n - 2);
    const t = x - j;
    for (let ch = 0; ch < 3; ch++) out[i * 3 + ch] = ld[j * 3 + ch] * (1 - t) + ld[(j + 1) * 3 + ch] * t;
  }
  return out;
}

export function createStarMaterial(look: StarLook, granulation: Granulation | null): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    defines: { LD_N: LD_SAMPLES },
    uniforms: {
      uLd: { value: ldArray(look.ld) },
      uColor: { value: new THREE.Color().setRGB(look.hue[0], look.hue[1], look.hue[2], THREE.SRGBColorSpace) },
      uBrightness: { value: look.brightness },
      uGranCells: { value: granulation && granulation.cells > 0 ? granulation.cells : 0 },
      uContrast: { value: granulation?.contrast ?? 0 },
      uPhase: { value: 0 },
      uSeed: { value: seedOffset(granulation?.seed ?? 0) },
    },
    vertexShader: STAR_VERTEX,
    fragmentShader: STAR_FRAGMENT,
  });
}

/** Swap the colour-mode inputs of a star (no geometry or program rebuild). */
export function setStarLook(mat: THREE.ShaderMaterial, look: StarLook): void {
  (mat.uniforms.uLd.value as Float32Array).set(ldArray(look.ld));
  (mat.uniforms.uColor.value as THREE.Color).setRGB(look.hue[0], look.hue[1], look.hue[2], THREE.SRGBColorSpace);
  mat.uniforms.uBrightness.value = look.brightness;
}

/** Granulation phase: model time in units of the convective turnover time (mjd / τ). */
export function setStarPhase(mat: THREE.ShaderMaterial, phase: number): void {
  mat.uniforms.uPhase.value = phase;
}

const RIM_VERTEX = /* glsl */ `
varying vec3 vN;
varying vec3 vV;
void main() {
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  vV = mv.xyz;
  vN = normalize(normalMatrix * normal);
  gl_Position = projectionMatrix * mv;
}
`;

const RIM_FRAGMENT = /* glsl */ `
uniform vec3 uColor;
uniform float uStrength;
uniform float uDashes;
varying vec3 vN;
varying vec3 vV;
void main() {
  vec3 n = normalize(vN);
  float mu = clamp(dot(n, normalize(-vV)), 0.0, 1.0);
  float f = pow(1.0 - mu, 3.0) * uStrength;
  if (uDashes > 0.0) f *= step(0.5, fract(atan(n.y, n.x) / 6.28318530718 * uDashes));
  gl_FragColor = vec4(uColor, f);
  #include <colorspace_fragment>
}
`;

/** Number of dashes around a dashed (qualitative) outline. */
export const RIM_DASHES = 24;

/** Fresnel outline (additive, drawn over the body with the same geometry). DISPLAY. */
export function createRimMaterial(hex: string, strength: number): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    uniforms: {
      uColor: { value: new THREE.Color(hex) },
      uStrength: { value: strength },
      uDashes: { value: 0 },
    },
    vertexShader: RIM_VERTEX,
    fragmentShader: RIM_FRAGMENT,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
}

/** Solid (0) or dashed outline. */
export function setRimDashes(mat: THREE.ShaderMaterial, dashes: number): void {
  mat.uniforms.uDashes.value = dashes;
}
