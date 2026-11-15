// Imperative three.js scene for one SystemModel. Loaded lazily (dynamic import) so the
// rest of the site does not pay for three.js. React talks to it through a small API:
//   new SystemScene(container, system, { onSelect, onTick })
//   .setPlaying / .setSpeed / .setTime / .setOptions / .focus / .dispose
//
// What you see is a MODEL REPRESENTATION built from catalog parameters (radius, Teff,
// orbital elements). Sizes are exaggerated and distances optionally compressed.
// How each body is drawn (no invented features on real targets):
//   stars        starMaterial: limb darkening + reddening (grey atmosphere, MODEL), colour from
//                the colour mode, a smooth sphere (convection cells on the synthetic demo only), glow
//                from L in the mode's band; without a measured Teff: neutral grey (colour unknown)
//   planets      uniform 18 % grey sphere lit by the host star's colour (visible); an outline in
//                the SPHEREx modes (emission not modelled)
//   brown dwarfs self-luminous at their display brightness (visible: neutral, nearly black for
//                the coldest) or SPHEREx-band brightness (IR), plus a rim outline (DISPLAY): a thin
//                dashed line on the silhouette while the IR level is only qualitative
//   disks        a translucent neutral ring
//   synthetic    the demo system keeps its palette and procedural textures in EVERY colour mode;
//                only its stars follow the mode
//   size unknown a body without a radius is a fixed marker (appearance.UNKNOWN_SIZE_DISPLAY_RADIUS),
//                labelled 'size unknown · not to scale' (factOrigin.bodyLabelText)
// Colour modes (colorModes.COLOR_MODES: false colour, visible, one SPHEREx detector in grey) swap
// uniforms and material colours only; geometry is never rebuilt. Real bodies get no surface pattern
// (no surface map is measured). Bodies spin only from a rotation period or the tidal-lock rule
// (sceneLayout.spinModel), in model time. No body changes size: a pulsating star keeps a constant
// radius (its size change is not measured) and only its glow follows the catalog V light curve.
// Dataset time (setDatasetMode, M4/M5/S2/S3): the clock runs on real SPHEREx dates inside the window.
//   - orbits with a published epoch are drawn at their predicted phase, with an arc of 64 points over
//     ±2σ of phase (ephemerides.ts); a dated circle in the reference plane gets a 'toward Earth' arrow;
//   - orbits without an epoch: the body is dimmed (0.35), labelled '(phase unknown)', and a ring of
//     64 points uniform in mean anomaly is drawn: on a fitted orbit it shows where the body could be;
//     on an assumed or hypothetical orbit neither the orbit nor the phase is known;
//   - variability follows ephemerides.variabilityPhase: a periodic variable with a catalogue ephemeris
//     (R Dra, VSX) follows the predicted phase; 'unknown' ones are frozen at mean brightness and
//     labelled; irregular variables never get a curve.
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { CSS2DObject, CSS2DRenderer } from 'three/examples/jsm/renderers/CSS2DRenderer.js';
import type { Body, SystemModel } from '../api/types';
import {
  bodyColor,
  compressDistance,
  displayRadius,
  NEUTRAL_ALBEDO,
  surfacePattern,
  type SurfacePattern,
} from './appearance';
import { granulationParams } from './astro';
import {
  bodyLook,
  COLOR_MODES,
  DEFAULT_COLOR_MODE,
  glowOpacity,
  glowPulse,
  IR_SPAN_TEXT,
  isInfraredMode,
  srgbDecode,
  starLimbDarkening,
  systemGlowFactors,
  type BodyLook,
  type ColorMode,
} from './colorModes';
import {
  ARC_ALPHA,
  CLOUD_POINTS,
  isLineOfSightOrbit,
  LINE_OF_SIGHT_LABEL,
  miraEphemerisFor,
  orbitEphemerisFor,
  phaseCloud,
  phaseUnknownLabel,
  predictedPulsation,
  RING_ALPHA,
  UNCERTAINTY_COLOR,
  undatedOrbitTitle,
  variabilityPhase,
  type MiraEphemeris,
  type OrbitEphemeris,
} from './ephemerides';
import {
  meanAnomalyAt,
  orbitalPosition,
  orbitPath,
  positionAtMeanAnomaly,
  topoOrder,
  variabilityFactor,
  type Vec3,
} from './orbits';
import { bodyLabelText, isSizeKnown, UNKNOWN_SIZE_TEXT } from './factOrigin';
import { PHASE_UNKNOWN_SUFFIX } from './spherexCoverage';
import {
  advanceModelTime,
  AU_PER_KM,
  capRadii,
  distanceMapper,
  drawsPulsation,
  fitDistance,
  focusDistance,
  linearScale,
  ORBIT_COLOR,
  orbitalPhaseAngle,
  referenceAu,
  rotationAngle,
  spinAliased,
  spinModel,
  suggestedSpeed,
  type DistanceMode,
  type SpinModel,
} from './sceneLayout';
import { createRimMaterial, createStarMaterial, RIM_DASHES, setRimDashes, setStarLook, setStarPhase, type StarLook } from './starMaterial';

export type { DistanceMode } from './sceneLayout';
export type { ColorMode } from './colorModes';

export interface SceneOptions {
  distanceMode: DistanceMode;
  showOrbits: boolean;
  showLabels: boolean;
  /** 'ir' = SPHEREx false colour (default), 'visible' = CIE 1931 blackbody colours, 'D1'…'D6' = one detector in grey. */
  colorMode: ColorMode;
}

export interface SceneCallbacks {
  onSelect: (bodyId: string | null) => void;
  onTick?: (mjd: number) => void;
  /** The dataset clock reached the end of its window and paused itself. */
  onClockStop?: () => void;
}

/** Opacity (or brightness factor, for stars) of a body without a published epoch on a real date. */
const DIM_FACTOR = 0.35;
/** 'toward Earth' arrow colour (DISPLAY). */
const LOS_HEX = '#7dd3fc';
/** Pixel size of the phase-cloud points. */
const CLOUD_POINT_PX = 4;

const DEFAULT_OPTIONS: SceneOptions = {
  distanceMode: 'compressed',
  showOrbits: true,
  showLabels: true,
  colorMode: DEFAULT_COLOR_MODE,
};

/** Rim (outline) strength and colour: a display aid, not emitted light. */
const RIM_HEX = '#9aa4b8';
const RIM_STRENGTH = 0.55;
/** Albedo a planet is drawn with in the SPHEREx modes: its SPHEREx-band light is not modelled, so a black silhouette with an outline. */
const IR_SILHOUETTE_ALBEDO = 0;
/** Pattern contrast of the synthetic demo's brown dwarfs (decoration). */
const SYNTHETIC_PATTERN_CONTRAST = 0.25;

/** One value per colour mode. */
function perMode<T>(f: (mode: ColorMode) => T): Record<ColorMode, T> {
  return Object.fromEntries(COLOR_MODES.map((m) => [m, f(m)])) as Record<ColorMode, T>;
}

/** Contrast c of a pattern texture (the drawn intensity is the mean × (1 ± c)): synthetic demo only. */
function patternContrast(pattern: SurfacePattern): number {
  return pattern === 'procedural' ? SYNTHETIC_PATTERN_CONTRAST : 0;
}

export function nowMjd(): number {
  return Date.now() / 86400000 + 40587;
}

// --- tiny seeded PRNG so procedural textures are stable per body ---------------------
function seeded(str: string): () => number {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) h = Math.imul(h ^ str.charCodeAt(i), 16777619);
  return () => {
    h += 0x6d2b79f5;
    let t = h;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function shade(hex: string, factor: number): string {
  const c = new THREE.Color(hex);
  c.multiplyScalar(factor);
  return `#${c.getHexString()}`;
}

/** Synthetic demo system only (hasSurfacePattern gate): seeded bands or blotches and craters. */
function proceduralTexture(body: Body, base: string): THREE.Texture | null {
  if (typeof document === 'undefined') return null;
  const rand = seeded(body.id);
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 128;
  const ctx = canvas.getContext('2d');
  if (!ctx) return null;
  ctx.fillStyle = base;
  ctx.fillRect(0, 0, 256, 128);
  const model = body.appearance.model;
  if (model === 'gas_giant' || model === 'brown_dwarf') {
    // Horizontal cloud bands.
    let y = 0;
    while (y < 128) {
      const h = 3 + rand() * 12;
      ctx.fillStyle = shade(base, 0.7 + rand() * 0.6);
      ctx.globalAlpha = 0.55;
      ctx.fillRect(0, y, 256, h);
      y += h;
    }
  } else {
    // Rocky / icy: blotches and craters.
    for (let i = 0; i < 160; i++) {
      ctx.globalAlpha = 0.15 + rand() * 0.3;
      ctx.fillStyle = shade(base, 0.55 + rand() * 0.8);
      ctx.beginPath();
      ctx.arc(rand() * 256, rand() * 128, 1 + rand() * 9, 0, Math.PI * 2);
      ctx.fill();
    }
  }
  ctx.globalAlpha = 1;
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

/**
 * Zonal-band pattern of the synthetic demo's self-luminous bodies (brown dwarfs; decoration, never a
 * real body): a greyscale multiplier (linear, no colour space), seeded per body. Each band has the value
 * (1 + c·u) / (1 + c) with u uniform in [−1, 1], so material colour × (1 + c) × texture is the mean
 * brightness × (1 ± c): the ±c of the legend is exactly what is drawn.
 */
function bandTexture(body: Body, contrast: number): THREE.Texture | null {
  if (typeof document === 'undefined') return null;
  const rand = seeded(`${body.id}:class-typical`);
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 128;
  const ctx = canvas.getContext('2d');
  if (!ctx) return null;
  const grey = (u: number) => {
    const g = Math.round(255 * Math.min(1, Math.max(0, (1 + contrast * u) / (1 + contrast))));
    return `rgb(${g},${g},${g})`;
  };
  ctx.fillStyle = grey(0);
  ctx.fillRect(0, 0, 256, 128);
  let y = 0;
  while (y < 128) {
    const h = 4 + rand() * 14;
    ctx.fillStyle = grey(2 * rand() - 1);
    ctx.fillRect(0, y, 256, h);
    y += h;
  }
  return new THREE.CanvasTexture(canvas); // NoColorSpace: a linear multiplier
}

function glowTexture(): THREE.Texture | null {
  if (typeof document === 'undefined') return null;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 128;
  const ctx = canvas.getContext('2d');
  if (!ctx) return null;
  const g = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
  g.addColorStop(0, 'rgba(255,255,255,1)');
  g.addColorStop(0.25, 'rgba(255,255,255,0.45)');
  g.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(canvas);
}

/** AU frame (x, y, z-up) → three.js frame (y-up). */
function toScene([x, y, z]: Vec3): THREE.Vector3 {
  return new THREE.Vector3(x, z, -y);
}

/** Display colour (sRGB-encoded hue × level) → a three.js colour in the linear working space. */
function setDisplayColor(target: THREE.Color, look: BodyLook, scale = 1): THREE.Color {
  const l = look.level;
  target.setRGB(look.hue[0] * l, look.hue[1] * l, look.hue[2] * l, THREE.SRGBColorSpace);
  return target.multiplyScalar(scale);
}

/** How the body's mesh is drawn. */
type Role = 'star' | 'disk' | 'emitter' | 'lit';

interface BodyNode {
  body: Body;
  role: Role;
  group: THREE.Group; // positioned each frame
  mesh: THREE.Mesh;
  baseRadius: number; // radius the geometry was built with (compressed mode)
  radiusByMode: Record<DistanceMode, number>;
  radius: number; // current display radius
  focusRadius: number; // what the camera frames when entering this body
  looks: Record<ColorMode, BodyLook>;
  spin: SpinModel;
  /** Star: limb-darkening tables per colour mode. */
  ld?: Record<ColorMode, Float32Array>;
  /**
   * Star: convection cells across the disc when astro.granulationParams finds them resolvable. Not
   * observed on any real target, so they are drawn on the synthetic demo only (VISION.md).
   */
  granCells?: number;
  /** Star: convective turnover time (days) when cells are drawn. */
  turnoverDays?: number;
  /** Glow size in display radii, per colour mode (DISPLAY). */
  glowFactor: Record<ColorMode, number>;
  glow?: THREE.Sprite;
  light?: THREE.PointLight;
  rim?: THREE.Mesh;
  /** Synthetic procedural pattern texture of this body (built on first use). */
  patternTex?: THREE.Texture | null;
  /** The pattern that texture was built for. */
  patternKind?: SurfacePattern;
  label?: CSS2DObject;
  orbitLine?: THREE.Line;
  /** Orbit ephemeris with 1-sigma (WS7 table), when the orbit is dated and tabulated. */
  orbitEph: OrbitEphemeris | null;
  /** Catalogue pulsation ephemeris (WS7 table), when the body has one. */
  mira: MiraEphemeris | null;
  /** Dataset time: 64 points of phase uncertainty (arc) or of unknown phase (ring). */
  cloud?: THREE.Points;
  cloudKind?: 'arc' | 'ring' | null;
  /** Distance mode the ring positions were computed for (rings do not move along the orbit). */
  ringMode?: DistanceMode | null;
  /** Dataset time: drawn dimmed (orbit without a published epoch). */
  dim: boolean;
  /** Dataset time: variability 'unknown' (ephemerides.variabilityPhase), frozen at mean brightness. */
  frozen: boolean;
}

/** A 'toward Earth' arrow from a parent whose dated circular orbits use the line-of-sight convention (M5). */
interface LosArrow {
  parentId: string;
  group: THREE.Group;
  arrow: THREE.ArrowHelper;
  label?: CSS2DObject;
}

export class SystemScene {
  private renderer: THREE.WebGLRenderer;
  private labelRenderer: CSS2DRenderer;
  private scene = new THREE.Scene();
  private camera: THREE.PerspectiveCamera;
  private controls: OrbitControls;
  private nodes = new Map<string, BodyNode>();
  private order: Body[];
  private refAu: number;
  private linearScale: number;
  private options: SceneOptions = { ...DEFAULT_OPTIONS };
  private mjd = nowMjd();
  private startMjd = this.mjd;
  private speed: number; // days per second
  private playing = true;
  private focusId: string | null = null;
  private zoomTarget: number | null = null;
  private lastFocusPos = new THREE.Vector3();
  private raf = 0;
  private lastFrame = 0;
  private lastTick = 0;
  private fitNear = 0.005;
  private pixelRatio = 0;
  private resizeObserver: ResizeObserver;
  private disposables: { dispose: () => void }[] = [];
  private pointerDown: { x: number; y: number } | null = null;
  private userMovedCamera = false;
  private datasetMode = false;
  private timeBounds: [number, number] | null = null;
  private losArrows: LosArrow[] = [];

  constructor(
    private container: HTMLElement,
    private system: SystemModel,
    private callbacks: SceneCallbacks,
  ) {
    this.order = topoOrder(system.bodies);
    this.refAu = referenceAu(system.bodies);
    this.linearScale = linearScale(system.bodies);
    this.speed = suggestedSpeed(system);

    this.renderer = new THREE.WebGLRenderer({ antialias: true }); // throws if WebGL is unavailable
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    const canvas = this.renderer.domElement;
    canvas.setAttribute('role', 'img');
    container.appendChild(canvas);

    this.labelRenderer = new CSS2DRenderer();
    this.labelRenderer.domElement.className = 'scene-labels';
    container.appendChild(this.labelRenderer.domElement);

    this.camera = new THREE.PerspectiveCamera(50, 1, 0.01, 5000);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    // A view the user rotated or zoomed by hand is kept when the window resizes (see resize()).
    this.controls.addEventListener('start', this.onControlsStart);

    this.scene.background = new THREE.Color('#03050a');
    // Faint fill light so night sides are not pure black (DISPLAY).
    this.scene.add(new THREE.AmbientLight(0xffffff, 0.25));
    this.addStarfield();
    this.buildBodies();
    this.applyLooks();
    this.rebuildOrbits();
    this.updatePositions();
    this.resize(); // real aspect ratio first, then frame the whole system for it
    this.fitCamera();

    const el = this.renderer.domElement;
    el.addEventListener('pointerdown', this.onPointerDown);
    el.addEventListener('pointerup', this.onPointerUp);
    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(container);
    this.raf = requestAnimationFrame(this.loop);
  }

  // --- public API -------------------------------------------------------------------
  setPlaying(playing: boolean) {
    this.playing = playing;
  }
  setSpeed(daysPerSecond: number) {
    this.speed = daysPerSecond;
  }
  setTime(mjd: number) {
    this.mjd = mjd;
    this.startMjd = mjd;
    this.updatePositions();
    this.callbacks.onTick?.(mjd);
  }
  getTime() {
    return this.mjd;
  }
  /** Model time when the animation started (orbit phases are arbitrary, so show elapsed time). */
  getStartTime() {
    return this.startMjd;
  }
  /**
   * Dataset time on or off. On: the clock stays inside `bounds` (MJD; playing stops at the end),
   * undated bodies are dimmed and labelled, phase clouds are drawn and variability follows a
   * catalogue ephemeris or is frozen. Off: the free-running animation, as before.
   */
  setDatasetMode(on: boolean, bounds: readonly [number, number] | null = null) {
    const changed = on !== this.datasetMode;
    this.datasetMode = on;
    this.timeBounds = on && bounds ? [bounds[0], bounds[1]] : null;
    if (!changed) return;
    this.applyDatasetLook();
    this.updatePositions();
  }
  isDatasetMode() {
    return this.datasetMode;
  }
  setOptions(partial: Partial<SceneOptions>) {
    const prev = this.options;
    this.options = { ...prev, ...partial };
    if (this.options.distanceMode !== prev.distanceMode) {
      this.applyModeRadii();
      this.rebuildOrbits();
      this.updatePositions();
      // Reframe for the new sizes: the entered body (it may have shrunk a lot), or the whole system.
      if (this.focusId) this.focus(this.focusId);
      else this.fitCamera();
    }
    if (this.options.colorMode !== prev.colorMode) {
      this.applyLooks();
      this.updatePositions();
    }
    for (const n of this.nodes.values()) {
      if (n.orbitLine) n.orbitLine.visible = this.options.showOrbits;
      if (n.label) n.label.visible = this.options.showLabels;
    }
    for (const a of this.losArrows) a.group.visible = this.options.showOrbits;
    if (this.options.showOrbits !== prev.showOrbits) this.updatePositions(); // phase clouds follow the orbits toggle
  }
  /** Fly to a body and follow it (null = back to the whole system). */
  focus(bodyId: string | null) {
    const node = bodyId ? this.nodes.get(bodyId) : undefined;
    this.focusId = node ? node.body.id : null;
    if (node) {
      this.lastFocusPos.copy(node.group.position);
      const isDisk = node.body.kind === 'disk';
      this.zoomTarget = focusDistance(
        isDisk ? 'disk' : 'body',
        isDisk ? node.focusRadius : node.radius,
        this.options.distanceMode,
        this.camera.fov,
        this.camera.aspect,
      );
      // Tiny bodies (true proportions) are framed from very close: keep them clear of the near plane.
      this.camera.near = Math.max(Math.min(this.fitNear, this.zoomTarget / 50), 1e-4);
      this.camera.updateProjectionMatrix();
    } else {
      this.zoomTarget = null;
      this.fitCamera();
    }
  }
  dispose() {
    cancelAnimationFrame(this.raf);
    this.resizeObserver.disconnect();
    const el = this.renderer.domElement;
    el.removeEventListener('pointerdown', this.onPointerDown);
    el.removeEventListener('pointerup', this.onPointerUp);
    this.controls.removeEventListener('start', this.onControlsStart);
    this.controls.dispose();
    this.scene.traverse((obj) => {
      if (obj instanceof CSS2DObject) obj.element.remove();
    });
    for (const n of this.nodes.values()) {
      if (n.orbitLine) {
        n.orbitLine.geometry.dispose();
        (n.orbitLine.material as THREE.Material).dispose();
        n.orbitLine = undefined;
      }
    }
    this.clearArrows();
    this.disposables.forEach((d) => d.dispose());
    this.renderer.dispose();
    this.renderer.forceContextLoss(); // free the WebGL context now, not at garbage collection
    el.remove();
    this.labelRenderer.domElement.remove();
  }

  // --- construction -----------------------------------------------------------------
  private track<T extends { dispose: () => void }>(d: T): T {
    this.disposables.push(d);
    return d;
  }

  private addStarfield() {
    const rand = seeded(this.system.id + ':stars');
    const n = 1500;
    const pos = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      const u = rand() * 2 - 1;
      const phi = rand() * Math.PI * 2;
      const r = Math.sqrt(1 - u * u) * 1500;
      pos.set([r * Math.cos(phi), u * 1500, r * Math.sin(phi)], i * 3);
    }
    const geo = this.track(new THREE.BufferGeometry());
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    const mat = this.track(new THREE.PointsMaterial({ color: 0x8890a8, size: 1.5, sizeAttenuation: false }));
    this.scene.add(new THREE.Points(geo, mat));
  }

  private static starLook(looks: Record<ColorMode, BodyLook>, ld: Record<ColorMode, Float32Array>, mode: ColorMode): StarLook {
    const look = looks[mode];
    return { ld: ld[mode], hue: look.hue, brightness: srgbDecode(look.level) };
  }

  /** A Fresnel outline drawn over the body (shares its geometry; not raycast). */
  private addRim(mesh: THREE.Mesh): THREE.Mesh {
    const rim = new THREE.Mesh(mesh.geometry, this.track(createRimMaterial(RIM_HEX, RIM_STRENGTH)));
    rim.raycast = () => {};
    rim.renderOrder = 1;
    mesh.add(rim);
    return rim;
  }

  private buildBodies() {
    const glowTex = glowTexture();
    if (glowTex) this.track(glowTex);
    const base = new Map(this.order.map((b) => [b.id, displayRadius(b)]));
    const bodies = this.system.bodies;
    const toUnits = (mode: DistanceMode) => distanceMapper(mode, this.refAu, this.linearScale);
    const compressed = capRadii(bodies, 'compressed', base, toUnits('compressed'));
    const linear = capRadii(bodies, 'linear', compressed, toUnits('linear'));
    const glowFactors = perMode((m) => systemGlowFactors(this.system, m));
    for (const body of this.order) {
      const group = new THREE.Group();
      const radius = compressed.get(body.id) ?? displayRadius(body);
      let focusRadius = radius;
      const looks = perMode((m) => bodyLook(body, this.system, m));
      let role: Role;
      let mesh: THREE.Mesh;
      let ld: Record<ColorMode, Float32Array> | undefined;
      let turnoverDays: number | undefined;
      let granCells: number | undefined;
      let glow: THREE.Sprite | undefined;
      let light: THREE.PointLight | undefined;
      let rim: THREE.Mesh | undefined;

      if (body.kind === 'disk') {
        role = 'disk';
        const host = body.orbit ? undefined : this.order.find((b) => !b.orbit && b.kind !== 'disk');
        const inner = (host ? displayRadius(host) : 0.5) * 1.4;
        // No disk radius: a fixed marker ring (2.5 × inner, below), never a default physical size.
        const outerAu = isSizeKnown(body) ? (body.radius_km as number) * AU_PER_KM : 0;
        const outer = Math.max(compressDistance(outerAu, this.refAu), inner * 2.5);
        const geo = this.track(new THREE.RingGeometry(inner, outer, 96, 4));
        const mat = this.track(new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.3, side: THREE.DoubleSide, depthWrite: false }));
        mesh = new THREE.Mesh(geo, mat);
        mesh.rotation.x = -Math.PI / 2;
        mesh.userData.labelOffset = new THREE.Vector3(outer, 0.15, 0);
        mesh.userData.diskOuter = { compressed: outer, linear: Math.max(outerAu * this.linearScale, inner * 1.2) };
        focusRadius = outer;
      } else if (body.kind === 'star' || body.appearance.model === 'star') {
        role = 'star';
        ld = perMode((m) => starLimbDarkening(body, m)); // one table per mode, copied into the uniform
        // Convection cells: synthetic demo only, where astro.granulationParams finds them resolvable
        // (< 64 across). No cell is observed on any real star, so real stars are smooth spheres.
        const g = granulationParams(body);
        const tau = g.turnoverDays.value;
        const gran =
          this.system.provenance.synthetic && g.draw && g.value !== null && tau !== null && tau > 0
            ? { cells: g.value, contrast: g.contrast.value, seed: g.seed }
            : null;
        if (gran) {
          turnoverDays = tau!;
          granCells = gran.cells;
        }
        const geo = this.track(new THREE.SphereGeometry(radius, 64, 32));
        const mat = this.track(createStarMaterial(SystemScene.starLook(looks, ld, this.options.colorMode), gran));
        mesh = new THREE.Mesh(geo, mat);
        if (glowTex) {
          const gmat = this.track(
            new THREE.SpriteMaterial({ map: glowTex, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }),
          );
          glow = new THREE.Sprite(gmat);
          group.add(glow);
        }
        light = new THREE.PointLight(0xffffff, 2.5, 0, 0); // display-normalised: no 1/r² fall-off
        group.add(light);
      } else if (body.kind === 'brown_dwarf') {
        role = 'emitter';
        const geo = this.track(new THREE.SphereGeometry(radius, 40, 20));
        mesh = new THREE.Mesh(geo, this.track(new THREE.MeshBasicMaterial()));
        rim = this.addRim(mesh);
      } else {
        // TODO(WS7-6): load appearance.mesh_url (glTF) for real asteroid shape models.
        role = 'lit';
        const geo = this.track(new THREE.SphereGeometry(radius, 40, 20));
        const roughness = this.system.provenance.synthetic ? 0.9 : 1;
        mesh = new THREE.Mesh(geo, this.track(new THREE.MeshStandardMaterial({ roughness, metalness: 0 })));
        rim = this.addRim(mesh);
      }
      mesh.userData.bodyId = body.id;
      group.add(mesh);
      const node: BodyNode = {
        body,
        role,
        group,
        mesh,
        baseRadius: radius,
        radiusByMode: { compressed: radius, linear: linear.get(body.id) ?? radius },
        radius,
        focusRadius,
        looks,
        spin: spinModel(body, bodies),
        ld,
        granCells,
        turnoverDays,
        glowFactor: perMode((m) => glowFactors[m].get(body.id) ?? 2),
        glow,
        light,
        rim,
        orbitEph: body.orbit && body.orbit.epoch_mjd != null ? orbitEphemerisFor(this.system.id, body.id) : null,
        mira: miraEphemerisFor(this.system.id, body.id),
        dim: false,
        frozen: false,
      };
      if (body.orbit && role !== 'disk') node.cloud = this.makeCloud(body);

      if (typeof document !== 'undefined') {
        const div = document.createElement('button');
        div.type = 'button';
        div.className = 'body-label';
        div.textContent = bodyLabelText(body);
        if (!isSizeKnown(body)) div.title = `${UNKNOWN_SIZE_TEXT}: no single radius is adopted, so it is drawn at a fixed marker size`;
        div.addEventListener('click', () => this.callbacks.onSelect(body.id));
        const label = new CSS2DObject(div);
        const offset = node.mesh.userData.labelOffset as THREE.Vector3 | undefined;
        if (offset) label.position.copy(offset);
        else label.position.set(0, radius * 1.25 + 0.15, 0);
        group.add(label);
        node.label = label;
      }

      this.scene.add(group);
      this.nodes.set(body.id, node);
    }
  }

  /** 64 points for the dataset-time phase cloud of an orbit, in the orbit-legend colour (hidden until used). */
  private makeCloud(body: Body): THREE.Points {
    const geo = this.track(new THREE.BufferGeometry());
    geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(CLOUD_POINTS * 3), 3));
    const col = new THREE.BufferAttribute(new Float32Array(CLOUD_POINTS * 4), 4);
    const c = new THREE.Color(UNCERTAINTY_COLOR[body.orbit?.quality ?? 'fitted']);
    for (let k = 0; k < CLOUD_POINTS; k++) col.setXYZW(k, c.r, c.g, c.b, RING_ALPHA);
    geo.setAttribute('color', col);
    const mat = this.track(
      new THREE.PointsMaterial({ size: CLOUD_POINT_PX, sizeAttenuation: false, vertexColors: true, transparent: true, depthWrite: false }),
    );
    const points = new THREE.Points(geo, mat);
    points.frustumCulled = false; // positions change every frame; the bounding sphere would go stale
    points.visible = false;
    points.raycast = () => {};
    this.scene.add(points);
    return points;
  }

  /** Arc (opacity follows the Gaussian density) or ring (uniform opacity): the per-point alpha. */
  private setCloudKind(node: BodyNode, kind: 'arc' | 'ring') {
    if (!node.cloud || node.cloudKind === kind) return;
    node.cloudKind = kind;
    node.ringMode = null;
    const col = node.cloud.geometry.getAttribute('color') as THREE.BufferAttribute;
    for (let k = 0; k < CLOUD_POINTS; k++) col.setW(k, kind === 'arc' ? ARC_ALPHA[k] : RING_ALPHA);
    col.needsUpdate = true;
  }

  /**
   * Dataset-time looks: dim the bodies whose orbit has no published epoch (opacity, or the brightness
   * of a star's shader and of its glow), and label them; freeze the periodic variables without an
   * ephemeris. Applied after every colour-mode change (applyLooks), so it never compounds.
   */
  private applyDatasetLook() {
    const mode = this.options.colorMode;
    for (const n of this.nodes.values()) {
      const b = n.body;
      const v = b.variability;
      n.dim = this.datasetMode && !!b.orbit && b.orbit.epoch_mjd == null && n.role !== 'disk';
      n.frozen = this.datasetMode && variabilityPhase(this.system.id, b) === 'unknown';
      const k = n.dim ? DIM_FACTOR : 1;
      if (n.role === 'star') {
        (n.mesh.material as THREE.ShaderMaterial).uniforms.uBrightness.value = srgbDecode(n.looks[mode].level) * k;
      } else if (n.role !== 'disk') {
        const mat = n.mesh.material as THREE.MeshBasicMaterial | THREE.MeshStandardMaterial;
        if (mat.transparent !== n.dim) {
          mat.transparent = n.dim;
          mat.needsUpdate = true;
        }
        mat.opacity = k;
      }
      if (n.rim) (n.rim.material as THREE.ShaderMaterial).uniforms.uStrength.value = RIM_STRENGTH * k;
      if (n.label) {
        const el = n.label.element;
        const unknownLabel = v ? phaseUnknownLabel(v.kind) : '';
        const suffix = n.dim ? ` ${PHASE_UNKNOWN_SUFFIX}` : n.frozen ? ` (${unknownLabel})` : '';
        el.textContent = `${bodyLabelText(b)}${suffix}`;
        el.style.opacity = n.dim ? '0.7' : '';
        el.title = n.dim
          ? undatedOrbitTitle(b.orbit?.quality ?? 'fitted')
          : n.frozen
            ? `${unknownLabel[0].toUpperCase()}${unknownLabel.slice(1)} (no epoch or no period): drawn at mean brightness on real dates.`
            : isSizeKnown(b)
              ? ''
              : `${UNKNOWN_SIZE_TEXT}: no single radius is adopted, so it is drawn at a fixed marker size`;
      }
    }
  }

  /**
   * The pattern texture of a body, built once on first use (never per frame): synthetic demo only.
   * Its lit bodies get the legacy procedural texture, its self-luminous ones zonal bands (bandTexture).
   */
  private patternTexture(node: BodyNode, pattern: SurfacePattern): THREE.Texture | null {
    if (pattern === 'none') return null;
    if (node.patternTex === undefined || node.patternKind !== pattern) {
      const tex =
        pattern === 'procedural' && node.role === 'lit'
          ? proceduralTexture(node.body, bodyColor(node.body, this.system))
          : bandTexture(node.body, patternContrast(pattern));
      node.patternTex = tex ? this.track(tex) : null;
      node.patternKind = pattern;
    }
    return node.patternTex;
  }

  private static setMap(mat: THREE.MeshBasicMaterial | THREE.MeshStandardMaterial, map: THREE.Texture | null) {
    if (mat.map === map) return;
    if (!!mat.map !== !!map) mat.needsUpdate = true; // the program changes only when a map appears or goes
    mat.map = map;
  }

  /** Colours, maps and outlines for the current colour mode (no geometry rebuild). */
  private applyLooks() {
    const mode = this.options.colorMode;
    const infrared = isInfraredMode(mode);
    const synthetic = this.system.provenance.synthetic;
    for (const n of this.nodes.values()) {
      const look = n.looks[mode];
      const pattern = surfacePattern(n.body, this.system);
      switch (n.role) {
        case 'star': {
          if (n.ld) setStarLook(n.mesh.material as THREE.ShaderMaterial, SystemScene.starLook(n.looks, n.ld, mode));
          const hue = new THREE.Color().setRGB(look.hue[0], look.hue[1], look.hue[2], THREE.SRGBColorSpace);
          if (n.glow) (n.glow.material as THREE.SpriteMaterial).color.copy(hue);
          // The synthetic demo's planets keep their visible look in every mode, so their light does too.
          const lit = synthetic ? n.looks.visible : look;
          n.light?.color.setRGB(lit.hue[0], lit.hue[1], lit.hue[2], THREE.SRGBColorSpace);
          break;
        }
        case 'disk': {
          const mat = n.mesh.material as THREE.MeshBasicMaterial;
          if (synthetic) mat.color.set(bodyColor(n.body, this.system)); // demo palette in every mode
          else mat.color.setRGB(look.hue[0] * look.level, look.hue[1] * look.level, look.hue[2] * look.level, THREE.SRGBColorSpace);
          mat.opacity = infrared && !synthetic ? 0.12 : 0.3; // SPHEREx modes: emission not modelled, a faint outline only
          break;
        }
        case 'emitter': {
          const mat = n.mesh.material as THREE.MeshBasicMaterial;
          const tex = this.patternTexture(n, pattern);
          SystemScene.setMap(mat, tex);
          // Texture × (1 + c) = mean × (1 ± c): the mean emission is kept (the brightest bands may clip at 1).
          setDisplayColor(mat.color, look, tex ? 1 + patternContrast(pattern) : 1);
          if (n.rim) {
            n.rim.visible = true;
            setRimDashes(n.rim.material as THREE.ShaderMaterial, look.drawnAs === 'qualitative' ? RIM_DASHES : 0);
          }
          break;
        }
        case 'lit': {
          const mat = n.mesh.material as THREE.MeshStandardMaterial;
          if (infrared && !synthetic) {
            // SPHEREx-band emission and reflection not modelled: a dark body with an outline.
            SystemScene.setMap(mat, null);
            mat.color.setRGB(IR_SILHOUETTE_ALBEDO, IR_SILHOUETTE_ALBEDO, IR_SILHOUETTE_ALBEDO, THREE.LinearSRGBColorSpace);
            if (n.rim) n.rim.visible = true;
          } else {
            // Visible light, or the synthetic demo in any mode (its textures are kept everywhere).
            const tex = this.patternTexture(n, pattern);
            SystemScene.setMap(mat, tex);
            if (pattern === 'procedural') mat.color.set(tex ? 0xffffff : bodyColor(n.body, this.system));
            else if (synthetic) mat.color.set(bodyColor(n.body, this.system));
            else mat.color.setRGB(NEUTRAL_ALBEDO, NEUTRAL_ALBEDO, NEUTRAL_ALBEDO, THREE.LinearSRGBColorSpace); // 18 % grey: albedo unknown
            if (n.rim) n.rim.visible = false;
          }
          break;
        }
      }
    }
    this.applyDatasetLook(); // dimming on top of the new colours (dataset time only)
    this.renderer.domElement.setAttribute(
      'aria-label',
      `3D model of ${this.system.name}, drawn from catalog parameters (not a telescope image); ${
        mode === 'ir'
          ? `false colours: SPHEREx ${IR_SPAN_TEXT} blackbody model`
          : mode === 'visible'
            ? 'visible-light blackbody colours (model)'
            : `grey levels: SPHEREx ${mode} only, blackbody model`
      }${synthetic ? '; the synthetic demo bodies keep their decorative colours in every mode' : ''}`,
    );
  }

  /** Resize bodies (by scaling, no geometry rebuild) for the current distance mode. */
  private applyModeRadii() {
    const mode = this.options.distanceMode;
    for (const n of this.nodes.values()) {
      const disk = n.mesh.userData.diskOuter as { compressed: number; linear: number } | undefined;
      if (disk) {
        const k = disk[mode] / disk.compressed;
        n.mesh.scale.setScalar(k);
        n.focusRadius = disk[mode];
        n.label?.position.set(disk[mode], 0.15, 0);
        continue;
      }
      n.radius = n.radiusByMode[mode];
      n.focusRadius = n.radius;
      n.label?.position.set(0, n.radius * 1.25 + 0.15, 0);
    }
  }

  private displayOffset(rel: Vec3): THREE.Vector3 {
    const r = Math.hypot(...rel);
    if (r === 0) return new THREE.Vector3();
    const d = this.options.distanceMode === 'compressed' ? compressDistance(r, this.refAu) : r * this.linearScale;
    return toScene(rel).multiplyScalar(d / r);
  }

  private rebuildOrbits() {
    for (const node of this.nodes.values()) {
      if (node.orbitLine) {
        node.orbitLine.removeFromParent();
        node.orbitLine.geometry.dispose();
        (node.orbitLine.material as THREE.Material).dispose();
        node.orbitLine = undefined;
      }
      const orbit = node.body.orbit;
      if (!orbit) continue;
      const pts = orbitPath(orbit).map((p) => this.displayOffset(p));
      const geo = new THREE.BufferGeometry().setFromPoints(pts);
      const quality = orbit.quality ?? 'fitted';
      const mat = new THREE.LineBasicMaterial({
        color: new THREE.Color(ORBIT_COLOR[quality] ?? ORBIT_COLOR.fitted),
        transparent: true,
        opacity: quality === 'fitted' ? 0.8 : 0.55,
      });
      const line = new THREE.Line(geo, mat);
      line.visible = this.options.showOrbits;
      this.scene.add(line);
      node.orbitLine = line;
      node.ringMode = null; // ring positions depend on the distance mode
    }
    this.rebuildArrows();
  }

  private clearArrows() {
    for (const a of this.losArrows) {
      a.group.removeFromParent();
      a.arrow.dispose();
      a.label?.element.remove();
    }
    this.losArrows = [];
  }

  /**
   * One 'toward Earth' arrow per parent of dated circles drawn with i = Ω = ω = 0 (Barnard b-e, M5):
   * the conjunction convention puts the line of sight, projected on the orbit plane, along AU −y =
   * scene +z. It passes through each planet's position at its t0. The inclination is unknown.
   */
  private rebuildArrows() {
    this.clearArrows();
    const reach = new Map<string, number>();
    for (const n of this.nodes.values()) {
      const o = n.body.orbit;
      if (!o || n.role === 'disk' || !isLineOfSightOrbit(o) || !this.nodes.has(o.parent)) continue;
      const r = this.displayOffset([o.semi_major_axis_au * (1 + o.eccentricity), 0, 0]).length();
      reach.set(o.parent, Math.max(reach.get(o.parent) ?? 0, r));
    }
    for (const [parentId, r] of reach) {
      const length = r * 1.35;
      const dir = toScene([0, -1, 0]);
      const head = Math.min(0.12 * length, 0.6);
      const arrow = new THREE.ArrowHelper(dir, new THREE.Vector3(), length, new THREE.Color(LOS_HEX), head, head * 0.5);
      arrow.traverse((o) => {
        o.raycast = () => {};
      });
      const group = new THREE.Group();
      group.add(arrow);
      let label: CSS2DObject | undefined;
      if (typeof document !== 'undefined') {
        const el = document.createElement('div');
        el.style.cssText =
          'pointer-events:none;max-width:200px;text-align:center;font-size:11px;line-height:1.3;color:' +
          `${LOS_HEX};text-shadow:0 0 3px #03050a,0 0 3px #03050a;white-space:normal`;
        const [head1, ...rest] = LINE_OF_SIGHT_LABEL.split(' (');
        const strong = document.createElement('strong');
        strong.textContent = head1;
        el.append(strong, document.createElement('br'), `(${rest.join(' (')}`);
        label = new CSS2DObject(el);
        label.position.copy(dir.clone().multiplyScalar(length * 1.08));
        group.add(label);
      }
      group.visible = this.options.showOrbits;
      this.scene.add(group);
      this.losArrows.push({ parentId, group, arrow, label });
    }
  }

  // --- per frame --------------------------------------------------------------------
  /**
   * Positions, sizes, spins and glows at the current model time. `stepDays` is the model time this
   * frame advanced (0 for a jump such as setTime): a spin that would turn more than 90° in one
   * frame is held still instead of aliasing.
   */
  private updatePositions(stepDays = 0) {
    const mode = this.options.colorMode;
    for (const body of this.order) {
      const node = this.nodes.get(body.id)!;
      let rel: Vec3 | null = null;
      if (!body.orbit) {
        node.group.position.set(0, 0, 0);
      } else {
        const parent = this.nodes.get(body.orbit.parent);
        const base = parent ? parent.group.position : new THREE.Vector3();
        rel = orbitalPosition(body.orbit, this.mjd);
        node.group.position.copy(base).add(this.displayOffset(rel));
        node.orbitLine?.position.copy(base);
        this.updateCloud(node, body.orbit, base);
      }
      if (node.role === 'disk') continue;
      const puls = this.pulsationAt(node);
      // Size: the display radius of the distance mode, constant in time (no size change is measured).
      node.mesh.scale.setScalar(node.radius / node.baseRadius);
      const spin = node.spin;
      if (spin.kind !== 'none' && !(spin.kind === 'period' && stepDays !== 0 && spinAliased(spin.periodHours, stepDays))) {
        const angle = rotationAngle(spin, this.mjd, rel ? orbitalPhaseAngle(rel) : null);
        if (angle !== undefined) node.mesh.rotation.y = angle;
      }
      if (node.turnoverDays) setStarPhase(node.mesh.material as THREE.ShaderMaterial, this.mjd / node.turnoverDays);
      if (node.glow) {
        const f = puls.factor; // V-band light curve: carried by the glow only
        node.glow.scale.setScalar(node.radius * node.glowFactor[mode] * glowPulse(f, mode));
        (node.glow.material as THREE.SpriteMaterial).opacity =
          glowOpacity(node.looks[mode].level, f, mode) * (node.dim ? DIM_FACTOR : 1);
      }
    }
    for (const a of this.losArrows) {
      const parent = this.nodes.get(a.parentId);
      if (parent) a.group.position.copy(parent.group.position);
    }
  }

  /**
   * V brightness factor of a body now (it drives the glow only; the radius is constant). Free-running:
   * the catalog sinusoid (arbitrary phase). Dataset time: the catalogue ephemeris when there is one
   * (R Dra, VSX), otherwise frozen at the mean (1); irregular variables are 1 in both modes.
   */
  private pulsationAt(node: BodyNode): { factor: number } {
    const body = node.body;
    if (!this.datasetMode) return { factor: variabilityFactor(body, this.mjd) };
    if (node.mira && drawsPulsation(body)) return { factor: predictedPulsation(node.mira, body, this.mjd).factor };
    return { factor: 1 };
  }

  /** Dataset time: the arc (dated, ±2σ about the predicted position) or ring (phase unknown) of an orbit. */
  private updateCloud(node: BodyNode, orbit: NonNullable<Body['orbit']>, base: THREE.Vector3) {
    const points = node.cloud;
    if (!points) return;
    const cloud = this.datasetMode && this.options.showOrbits ? phaseCloud(orbit, node.orbitEph, this.mjd, meanAnomalyAt(orbit, this.mjd)) : null;
    points.visible = cloud !== null;
    if (!cloud) return;
    this.setCloudKind(node, cloud.kind);
    points.position.copy(base);
    // A ring does not move along the orbit: recompute it only for a new distance mode.
    if (cloud.kind === 'ring' && node.ringMode === this.options.distanceMode) return;
    const pos = points.geometry.getAttribute('position') as THREE.BufferAttribute;
    cloud.meanAnomalies.forEach((M, k) => {
      const p = this.displayOffset(positionAtMeanAnomaly(orbit, M));
      pos.setXYZ(k, p.x, p.y, p.z);
    });
    pos.needsUpdate = true;
    node.ringMode = cloud.kind === 'ring' ? this.options.distanceMode : null;
  }

  private fitCamera() {
    let extent = 0;
    let maxRadius = 0;
    for (const n of this.nodes.values()) {
      maxRadius = Math.max(maxRadius, n.radius);
      extent = Math.max(extent, n.group.position.length() + n.radius);
      if (n.orbitLine) {
        n.orbitLine.geometry.computeBoundingSphere();
        const bs = n.orbitLine.geometry.boundingSphere;
        if (bs) extent = Math.max(extent, n.orbitLine.position.length() + bs.center.length() + bs.radius);
      }
    }
    // Frame for the tighter of the vertical and horizontal FOV, so portrait screens see it all too.
    const dist = fitDistance(extent, maxRadius, this.camera.fov, this.camera.aspect);
    this.controls.target.set(0, 0, 0);
    this.camera.position.set(0, dist * 0.55, dist);
    this.fitNear = Math.max(dist / 5000, 0.005);
    this.camera.near = this.fitNear;
    this.camera.updateProjectionMatrix();
    this.userMovedCamera = false;
  }

  private onControlsStart = () => {
    this.userMovedCamera = true;
  };

  private resize() {
    const w = this.container.clientWidth || 1;
    const h = this.container.clientHeight || 1;
    // Re-read the pixel ratio every time: browser zoom or another monitor changes it.
    this.pixelRatio = window.devicePixelRatio || 1;
    this.renderer.setPixelRatio(Math.min(this.pixelRatio, 2));
    this.renderer.setSize(w, h);
    this.labelRenderer.setSize(w, h);
    const aspect = w / h;
    const aspectChanged = Math.abs(aspect - this.camera.aspect) > 1e-3;
    this.camera.aspect = aspect;
    this.camera.updateProjectionMatrix();
    // The whole-system view depends on the aspect ratio (portrait is limited by the horizontal FOV),
    // but a view the user set by hand is theirs: keep it.
    if (aspectChanged && !this.focusId && !this.userMovedCamera) this.fitCamera();
  }

  private onPointerDown = (e: PointerEvent) => {
    this.pointerDown = { x: e.clientX, y: e.clientY };
  };

  private onPointerUp = (e: PointerEvent) => {
    const start = this.pointerDown;
    this.pointerDown = null;
    if (!start || Math.hypot(e.clientX - start.x, e.clientY - start.y) > 5) return; // it was a drag
    const rect = this.renderer.domElement.getBoundingClientRect();
    const ndc = new THREE.Vector2(
      ((e.clientX - rect.left) / rect.width) * 2 - 1,
      -((e.clientY - rect.top) / rect.height) * 2 + 1,
    );
    const ray = new THREE.Raycaster();
    ray.setFromCamera(ndc, this.camera);
    const meshes = [...this.nodes.values()].map((n) => n.mesh);
    const hit = ray.intersectObjects(meshes, false)[0];
    if (hit) this.callbacks.onSelect(hit.object.userData.bodyId as string);
  };

  private loop = (t: number) => {
    const dt = this.lastFrame ? Math.min((t - this.lastFrame) / 1000, 0.1) : 0;
    this.lastFrame = t;
    // Moving to a monitor with another pixel density does not resize the container: check here.
    if ((window.devicePixelRatio || 1) !== this.pixelRatio) this.resize();
    if (this.playing && dt > 0) {
      // Model time runs on continuously (no wrap), so no body or pulsation ever jumps.
      let next = advanceModelTime(this.mjd, this.speed, dt);
      // Dataset time plays inside its window and stops at the end (no data after it).
      const stop = this.timeBounds !== null && next >= this.timeBounds[1];
      if (stop) next = this.timeBounds![1];
      const step = next - this.mjd;
      this.mjd = next;
      this.updatePositions(step);
      if (stop) {
        this.playing = false;
        this.callbacks.onTick?.(this.mjd);
        this.callbacks.onClockStop?.();
      }
    }
    // No global spin: bodies turn only in updatePositions, from a period or the tidal-lock rule.

    // Follow the focused body; ease the camera in on first focus.
    const focus = this.focusId ? this.nodes.get(this.focusId) : undefined;
    if (focus) {
      const delta = focus.group.position.clone().sub(this.lastFocusPos);
      this.camera.position.add(delta);
      this.controls.target.add(delta);
      this.lastFocusPos.copy(focus.group.position);
      this.controls.target.lerp(focus.group.position, 0.12);
      if (this.zoomTarget !== null) {
        const off = this.camera.position.clone().sub(this.controls.target);
        const d = off.length();
        const next = d + (this.zoomTarget - d) * 0.08;
        this.camera.position.copy(this.controls.target).add(off.setLength(next));
        // Relative stop threshold: true-proportions targets can be a few hundredths of a unit.
        if (Math.abs(next - this.zoomTarget) < Math.min(0.05, 0.02 * this.zoomTarget)) this.zoomTarget = null;
      }
      // Keep the near plane proportional to the viewing distance: very small near values (needed to
      // frame tiny bodies) would ruin depth precision once the user zooms back out by hand.
      const near = Math.min(Math.max(this.camera.position.distanceTo(this.controls.target) / 200, 1e-4), this.fitNear);
      if (Math.abs(near - this.camera.near) > 0.1 * near) {
        this.camera.near = near;
        this.camera.updateProjectionMatrix();
      }
    }

    this.controls.update();
    this.renderer.render(this.scene, this.camera);
    this.labelRenderer.render(this.scene, this.camera);
    if (this.callbacks.onTick && t - this.lastTick > 100) {
      this.lastTick = t;
      this.callbacks.onTick(this.mjd);
    }
    this.raf = requestAnimationFrame(this.loop);
  };
}
