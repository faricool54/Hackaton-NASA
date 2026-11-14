// Imperative three.js scene for one SystemModel. Loaded lazily (dynamic import) so the
// rest of the site does not pay for three.js. React talks to it through a small API:
//   new SystemScene(container, system, { onSelect, onTick })
//   .setPlaying / .setSpeed / .setTime / .setOptions / .focus / .dispose
//
// What you see is a MODEL REPRESENTATION built from catalog parameters (radius, Teff,
// orbital elements). Sizes are exaggerated and distances optionally compressed.
// How each body is drawn (no invented features on real targets):
//   stars        starMaterial: limb darkening + reddening (grey atmosphere, MODEL), colour from
//                the colour mode, convection cells only where resolvable (R Dra), glow from L_vis
//   planets      uniform 18 % grey sphere lit by the host star's colour (visible); an outline in
//                SPHEREx IR (emission not modelled)
//   brown dwarfs self-luminous at their display brightness (visible: neutral, nearly black for
//                the coldest) or SPHEREx-band brightness (IR), plus a Fresnel rim (DISPLAY)
//   disks        a translucent neutral ring
// Colour modes swap uniforms and material colours only; geometry is never rebuilt. Bodies spin
// only from a rotation period or the tidal-lock rule (sceneLayout.spinModel), in model time.
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { CSS2DObject, CSS2DRenderer } from 'three/examples/jsm/renderers/CSS2DRenderer.js';
import type { Body, SystemModel } from '../api/types';
import {
  bodyColor,
  CLASS_TYPICAL_CONTRAST,
  compressDistance,
  displayRadius,
  NEUTRAL_ALBEDO,
  surfacePattern,
  type SurfacePattern,
} from './appearance';
import { granulationParams } from './astro';
import {
  bodyLook,
  DEFAULT_COLOR_MODE,
  glowOpacity,
  glowPulse,
  IR_SPAN_TEXT,
  srgbDecode,
  starLimbDarkening,
  systemGlowFactors,
  type BodyLook,
  type ColorMode,
} from './colorModes';
import { orbitalPosition, orbitPath, topoOrder, variabilityFactor, type Vec3 } from './orbits';
import {
  advanceModelTime,
  AU_PER_KM,
  capRadii,
  distanceMapper,
  fitDistance,
  focusDistance,
  linearScale,
  ORBIT_COLOR,
  orbitalPhaseAngle,
  pulsationRadiusScale,
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
// Kept here too: SystemViewer reads it from the lazily loaded module.
export { suggestedSpeed };

export interface SceneOptions {
  distanceMode: DistanceMode;
  showOrbits: boolean;
  showLabels: boolean;
  /** 'ir' = SPHEREx false colour (default), 'visible' = CIE 1931 blackbody colours. */
  colorMode: ColorMode;
  /** Show illustrative class-typical surface features on real planets and brown dwarfs (S5). */
  classTypical: boolean;
}

export interface SceneCallbacks {
  onSelect: (bodyId: string | null) => void;
  onTick?: (mjd: number) => void;
}

const DEFAULT_OPTIONS: SceneOptions = {
  distanceMode: 'compressed',
  showOrbits: true,
  showLabels: true,
  colorMode: DEFAULT_COLOR_MODE,
  classTypical: false,
};

/** Rim (outline) strength and colour: a display aid, not emitted light. */
const RIM_HEX = '#9aa4b8';
const RIM_STRENGTH = 0.55;
/** Albedo a planet is drawn with in IR mode: its SPHEREx-band light is not modelled, so a black silhouette with an outline. */
const IR_SILHOUETTE_ALBEDO = 0;

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
 * Class-typical pattern (S5 toggle, ILLUSTRATIVE): a greyscale multiplier in [1 − 2c, 1] (linear,
 * no colour space), seeded per body. Zonal bands, or soft albedo mottling (no craters).
 */
function classTypicalTexture(body: Body, pattern: 'bands' | 'mottling', contrast: number): THREE.Texture | null {
  if (typeof document === 'undefined') return null;
  const rand = seeded(`${body.id}:class-typical`);
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 128;
  const ctx = canvas.getContext('2d');
  if (!ctx) return null;
  const grey = (v: number) => {
    const g = Math.round(255 * Math.min(1, Math.max(0, v)));
    return `rgb(${g},${g},${g})`;
  };
  ctx.fillStyle = grey(1 - contrast);
  ctx.fillRect(0, 0, 256, 128);
  if (pattern === 'bands') {
    let y = 0;
    while (y < 128) {
      const h = 4 + rand() * 14;
      ctx.fillStyle = grey(1 - 2 * contrast * rand());
      ctx.fillRect(0, y, 256, h);
      y += h;
    }
  } else {
    for (let i = 0; i < 140; i++) {
      ctx.globalAlpha = 0.35 + rand() * 0.4;
      ctx.fillStyle = grey(1 - 2 * contrast * rand());
      ctx.beginPath();
      ctx.arc(rand() * 256, rand() * 128, 3 + rand() * 12, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
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
  /** Star: convective turnover time (days) when cells are drawn. */
  turnoverDays?: number;
  /** Glow size in display radii, per colour mode (DISPLAY). */
  glowFactor: Record<ColorMode, number>;
  glow?: THREE.Sprite;
  light?: THREE.PointLight;
  rim?: THREE.Mesh;
  /** Synthetic procedural or class-typical pattern texture of this body (built on first use). */
  patternTex?: THREE.Texture | null;
  label?: CSS2DObject;
  orbitLine?: THREE.Line;
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
    if (this.options.colorMode !== prev.colorMode || this.options.classTypical !== prev.classTypical) {
      this.applyLooks();
      this.updatePositions();
    }
    for (const n of this.nodes.values()) {
      if (n.orbitLine) n.orbitLine.visible = this.options.showOrbits;
      if (n.label) n.label.visible = this.options.showLabels;
    }
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
    const glowFactors = { ir: systemGlowFactors(this.system, 'ir'), visible: systemGlowFactors(this.system, 'visible') };
    for (const body of this.order) {
      const group = new THREE.Group();
      const radius = compressed.get(body.id) ?? displayRadius(body);
      let focusRadius = radius;
      const looks: Record<ColorMode, BodyLook> = {
        ir: bodyLook(body, this.system, 'ir'),
        visible: bodyLook(body, this.system, 'visible'),
      };
      let role: Role;
      let mesh: THREE.Mesh;
      let ld: Record<ColorMode, Float32Array> | undefined;
      let turnoverDays: number | undefined;
      let glow: THREE.Sprite | undefined;
      let light: THREE.PointLight | undefined;
      let rim: THREE.Mesh | undefined;

      if (body.kind === 'disk') {
        role = 'disk';
        const host = body.orbit ? undefined : this.order.find((b) => !b.orbit && b.kind !== 'disk');
        const inner = (host ? displayRadius(host) : 0.5) * 1.4;
        const outerAu = (body.radius_km ?? 1.5e9) * AU_PER_KM;
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
        ld = { ir: starLimbDarkening(body, 'ir'), visible: starLimbDarkening(body, 'visible') };
        // Convection cells only where astro.granulationParams finds them resolvable (< 64 across).
        const g = granulationParams(body);
        const tau = g.turnoverDays.value;
        const gran = g.draw && g.value !== null && tau !== null && tau > 0 ? { cells: g.value, contrast: g.contrast.value, seed: g.seed } : null;
        if (gran) turnoverDays = tau!;
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
        turnoverDays,
        glowFactor: { ir: glowFactors.ir.get(body.id) ?? 2, visible: glowFactors.visible.get(body.id) ?? 2 },
        glow,
        light,
        rim,
      };

      if (typeof document !== 'undefined') {
        const div = document.createElement('button');
        div.type = 'button';
        div.className = 'body-label';
        div.textContent = body.name;
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

  /** The pattern texture of a body, built once on first use (never per frame). */
  private patternTexture(node: BodyNode, pattern: SurfacePattern): THREE.Texture | null {
    if (pattern === 'none') return null;
    if (node.patternTex === undefined) {
      const tex =
        pattern === 'procedural' && node.role === 'lit'
          ? proceduralTexture(node.body, bodyColor(node.body, this.system))
          : classTypicalTexture(node.body, pattern === 'mottling' ? 'mottling' : 'bands', pattern === 'procedural' ? 0.25 : CLASS_TYPICAL_CONTRAST[pattern === 'mottling' ? 'mottling' : 'bands']);
      node.patternTex = tex ? this.track(tex) : null;
    }
    return node.patternTex;
  }

  private static setMap(mat: THREE.MeshBasicMaterial | THREE.MeshStandardMaterial, map: THREE.Texture | null) {
    if (mat.map === map) return;
    if (!!mat.map !== !!map) mat.needsUpdate = true; // the program changes only when a map appears or goes
    mat.map = map;
  }

  /** Colours, maps and outlines for the current colour mode and class-typical toggle (no geometry rebuild). */
  private applyLooks() {
    const mode = this.options.colorMode;
    const synthetic = this.system.provenance.synthetic;
    for (const n of this.nodes.values()) {
      const look = n.looks[mode];
      const pattern = surfacePattern(n.body, this.system, this.options.classTypical);
      switch (n.role) {
        case 'star': {
          if (n.ld) setStarLook(n.mesh.material as THREE.ShaderMaterial, SystemScene.starLook(n.looks, n.ld, mode));
          const hue = new THREE.Color().setRGB(look.hue[0], look.hue[1], look.hue[2], THREE.SRGBColorSpace);
          if (n.glow) (n.glow.material as THREE.SpriteMaterial).color.copy(hue);
          n.light?.color.copy(hue);
          break;
        }
        case 'disk': {
          const mat = n.mesh.material as THREE.MeshBasicMaterial;
          if (synthetic && mode === 'visible') mat.color.set(bodyColor(n.body, this.system));
          else mat.color.setRGB(look.hue[0] * look.level, look.hue[1] * look.level, look.hue[2] * look.level, THREE.SRGBColorSpace);
          mat.opacity = mode === 'ir' ? 0.12 : 0.3; // IR: emission not modelled, a faint outline only
          break;
        }
        case 'emitter': {
          const mat = n.mesh.material as THREE.MeshBasicMaterial;
          const tex = this.patternTexture(n, pattern);
          SystemScene.setMap(mat, tex);
          // A pattern darkens by its contrast on average: compensate so the mean emission is kept.
          const c = pattern === 'bands' ? CLASS_TYPICAL_CONTRAST.bands : pattern === 'procedural' ? 0.25 : 0;
          setDisplayColor(mat.color, look, tex ? 1 / (1 - c) : 1);
          if (n.rim) {
            n.rim.visible = true;
            setRimDashes(n.rim.material as THREE.ShaderMaterial, look.drawnAs === 'qualitative' ? RIM_DASHES : 0);
          }
          break;
        }
        case 'lit': {
          const mat = n.mesh.material as THREE.MeshStandardMaterial;
          if (mode === 'ir') {
            // SPHEREx-band emission and reflection not modelled: a dark body with an outline.
            SystemScene.setMap(mat, null);
            mat.color.setRGB(IR_SILHOUETTE_ALBEDO, IR_SILHOUETTE_ALBEDO, IR_SILHOUETTE_ALBEDO, THREE.LinearSRGBColorSpace);
            if (n.rim) n.rim.visible = true;
          } else {
            const tex = this.patternTexture(n, pattern);
            SystemScene.setMap(mat, tex);
            if (pattern === 'procedural') mat.color.set(tex ? 0xffffff : bodyColor(n.body, this.system));
            else if (synthetic) mat.color.set(bodyColor(n.body, this.system));
            else {
              const c = pattern === 'bands' || pattern === 'mottling' ? CLASS_TYPICAL_CONTRAST[pattern] : 0;
              const a = NEUTRAL_ALBEDO / (tex ? 1 - c : 1);
              mat.color.setRGB(a, a, a, THREE.LinearSRGBColorSpace); // 18 % grey: albedo unknown
            }
            if (n.rim) n.rim.visible = false;
          }
          break;
        }
      }
    }
    this.renderer.domElement.setAttribute(
      'aria-label',
      `3D model of ${this.system.name}, drawn from catalog parameters (not a telescope image); ${
        mode === 'ir'
          ? `false colours: SPHEREx ${IR_SPAN_TEXT} blackbody model`
          : 'visible-light blackbody colours (model)'
      }`,
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
      }
      if (node.role === 'disk') continue;
      // Size: display radius × the class-typical Mira pulsation (1 for every other body).
      node.mesh.scale.setScalar(pulsationRadiusScale(body, this.mjd) * (node.radius / node.baseRadius));
      const spin = node.spin;
      if (spin.kind !== 'none' && !(spin.kind === 'period' && stepDays !== 0 && spinAliased(spin.periodHours, stepDays))) {
        const angle = rotationAngle(spin, this.mjd, rel ? orbitalPhaseAngle(rel) : null);
        if (angle !== undefined) node.mesh.rotation.y = angle;
      }
      if (node.turnoverDays) setStarPhase(node.mesh.material as THREE.ShaderMaterial, this.mjd / node.turnoverDays);
      if (node.glow) {
        const f = variabilityFactor(body, this.mjd); // V-band light curve: carried by the glow only
        node.glow.scale.setScalar(node.radius * node.glowFactor[mode] * glowPulse(f, mode));
        (node.glow.material as THREE.SpriteMaterial).opacity = glowOpacity(node.looks[mode].level, f, mode);
      }
    }
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
      const next = advanceModelTime(this.mjd, this.speed, dt);
      const step = next - this.mjd;
      this.mjd = next;
      this.updatePositions(step);
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
