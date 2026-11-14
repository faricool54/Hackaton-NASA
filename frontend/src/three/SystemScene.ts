// Imperative three.js scene for one SystemModel. Loaded lazily (dynamic import) so the
// rest of the site does not pay for three.js. React talks to it through a small API:
//   new SystemScene(container, system, { onSelect, onTick })
//   .setPlaying / .setSpeed / .setTime / .setOptions / .focus / .dispose
//
// What you see is a MODEL REPRESENTATION built from catalog parameters (radius, Teff,
// orbital elements). Sizes are exaggerated and distances optionally compressed.
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { CSS2DObject, CSS2DRenderer } from 'three/examples/jsm/renderers/CSS2DRenderer.js';
import type { Body, SystemModel } from '../api/types';
import { bodyColor, compressDistance, displayRadius } from './appearance';
import { orbitalPosition, orbitPath, topoOrder, variabilityFactor, type Vec3 } from './orbits';

export type DistanceMode = 'compressed' | 'linear';

export interface SceneOptions {
  distanceMode: DistanceMode;
  showOrbits: boolean;
  showLabels: boolean;
}

export interface SceneCallbacks {
  onSelect: (bodyId: string | null) => void;
  onTick?: (mjd: number) => void;
}

const AU_PER_KM = 1 / 1.495978707e8;
const DEFAULT_OPTIONS: SceneOptions = { distanceMode: 'compressed', showOrbits: true, showLabels: true };

export function nowMjd(): number {
  return Date.now() / 86400000 + 40587;
}

/** Suggested animation speed (days per real second) so the fastest motion is easy to follow. */
export function suggestedSpeed(system: SystemModel): number {
  const periods = system.bodies.flatMap((b) => [b.orbit?.period_days, b.variability?.period_days]);
  const valid = periods.filter((p): p is number => typeof p === 'number' && p > 0);
  return valid.length ? Math.min(...valid) / 8 : 1;
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

interface BodyNode {
  body: Body;
  group: THREE.Group; // positioned each frame
  mesh: THREE.Object3D;
  radius: number;
  glow?: THREE.Sprite;
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
  private speed: number; // days per second
  private playing = true;
  private focusId: string | null = null;
  private zoomTarget: number | null = null;
  private lastFocusPos = new THREE.Vector3();
  private raf = 0;
  private lastFrame = 0;
  private lastTick = 0;
  private resizeObserver: ResizeObserver;
  private disposables: { dispose: () => void }[] = [];
  private pointerDown: { x: number; y: number } | null = null;

  constructor(
    private container: HTMLElement,
    private system: SystemModel,
    private callbacks: SceneCallbacks,
  ) {
    this.order = topoOrder(system.bodies);
    const scales = system.bodies.flatMap((b) => [
      b.orbit?.semi_major_axis_au,
      b.kind === 'disk' && b.radius_km ? b.radius_km * AU_PER_KM : undefined,
    ]);
    const valid = scales.filter((v): v is number => typeof v === 'number' && v > 0);
    this.refAu = valid.length ? Math.min(...valid) : 1;
    const maxExtent = system.bodies.reduce(
      (s, b) => s + (b.orbit ? b.orbit.semi_major_axis_au * (1 + b.orbit.eccentricity) : 0),
      0,
    );
    this.linearScale = maxExtent > 0 ? 30 / maxExtent : 1;
    this.speed = suggestedSpeed(system);

    this.renderer = new THREE.WebGLRenderer({ antialias: true }); // throws if WebGL is unavailable
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(this.renderer.domElement);

    this.labelRenderer = new CSS2DRenderer();
    this.labelRenderer.domElement.className = 'scene-labels';
    container.appendChild(this.labelRenderer.domElement);

    this.camera = new THREE.PerspectiveCamera(50, 1, 0.01, 5000);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;

    this.scene.background = new THREE.Color('#03050a');
    this.scene.add(new THREE.AmbientLight(0xffffff, 0.25));
    this.addStarfield();
    this.buildBodies();
    this.rebuildOrbits();
    this.updatePositions();
    this.fitCamera();

    const el = this.renderer.domElement;
    el.addEventListener('pointerdown', this.onPointerDown);
    el.addEventListener('pointerup', this.onPointerUp);
    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(container);
    this.resize();
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
    this.updatePositions();
    this.callbacks.onTick?.(mjd);
  }
  getTime() {
    return this.mjd;
  }
  setOptions(partial: Partial<SceneOptions>) {
    const modeChanged = partial.distanceMode && partial.distanceMode !== this.options.distanceMode;
    this.options = { ...this.options, ...partial };
    if (modeChanged) {
      this.rebuildOrbits();
      this.updatePositions();
      if (!this.focusId) this.fitCamera();
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
      this.zoomTarget = Math.max(node.radius * 6, 2.5);
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
    this.controls.dispose();
    this.scene.traverse((obj) => {
      if (obj instanceof CSS2DObject) obj.element.remove();
    });
    this.disposables.forEach((d) => d.dispose());
    this.renderer.dispose();
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

  /** Cap child radii so siblings on neighbouring orbits don't overlap in compressed mode. */
  private radiusCaps(): Map<string, number> {
    const caps = new Map<string, number>();
    const byParent = new Map<string, Body[]>();
    for (const b of this.system.bodies) {
      if (b.orbit && b.kind !== 'disk') byParent.set(b.orbit.parent, [...(byParent.get(b.orbit.parent) ?? []), b]);
    }
    for (const [parentId, kids] of byParent) {
      const parent = this.system.bodies.find((b) => b.id === parentId);
      const dists = kids.map((k) => compressDistance(k.orbit!.semi_major_axis_au, this.refAu)).sort((a, b) => a - b);
      const gaps = [dists[0] - (parent ? displayRadius(parent) : 0), ...dists.slice(1).map((d, i) => d - dists[i])];
      const cap = Math.max(0.12, 0.4 * Math.min(...gaps));
      kids.forEach((k) => caps.set(k.id, cap));
    }
    return caps;
  }

  private buildBodies() {
    const glowTex = glowTexture();
    if (glowTex) this.track(glowTex);
    const caps = this.radiusCaps();
    for (const body of this.order) {
      const group = new THREE.Group();
      const radius = Math.min(displayRadius(body), caps.get(body.id) ?? Infinity);
      const color = bodyColor(body);
      let mesh: THREE.Object3D;
      let glow: THREE.Sprite | undefined;

      if (body.kind === 'disk') {
        const host = body.orbit ? undefined : this.order.find((b) => !b.orbit && b.kind !== 'disk');
        const inner = (host ? displayRadius(host) : 0.5) * 1.4;
        const outerAu = (body.radius_km ?? 1.5e9) * AU_PER_KM;
        const outer = Math.max(compressDistance(outerAu, this.refAu), inner * 2.5);
        const geo = this.track(new THREE.RingGeometry(inner, outer, 96, 4));
        const mat = this.track(
          new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.35, side: THREE.DoubleSide }),
        );
        mesh = new THREE.Mesh(geo, mat);
        mesh.rotation.x = -Math.PI / 2;
        mesh.userData.labelOffset = new THREE.Vector3(outer, 0.15, 0);
      } else if (body.appearance.model === 'star') {
        const geo = this.track(new THREE.SphereGeometry(radius, 48, 24));
        const mat = this.track(new THREE.MeshBasicMaterial({ color }));
        mesh = new THREE.Mesh(geo, mat);
        if (glowTex) {
          const gmat = this.track(
            new THREE.SpriteMaterial({
              map: glowTex,
              color,
              transparent: true,
              blending: THREE.AdditiveBlending,
              depthWrite: false,
            }),
          );
          glow = new THREE.Sprite(gmat);
          glow.scale.setScalar(radius * 5);
          group.add(glow);
        }
        const light = new THREE.PointLight(color, 2.5, 0, 0);
        group.add(light);
      } else {
        // TODO(WS7-6): load appearance.mesh_url (glTF) for real asteroid shape models.
        const geo = this.track(new THREE.SphereGeometry(radius, 40, 20));
        const tex = proceduralTexture(body, color);
        if (tex) this.track(tex);
        const warm = body.kind === 'brown_dwarf' && body.teff_k ? Math.min(Math.max((body.teff_k - 300) / 1500, 0.08), 0.7) : 0;
        const mat = this.track(
          new THREE.MeshStandardMaterial({
            color: tex ? 0xffffff : color,
            map: tex,
            roughness: 0.9,
            metalness: 0,
            emissive: new THREE.Color(color),
            emissiveIntensity: warm,
          }),
        );
        mesh = new THREE.Mesh(geo, mat);
      }
      mesh.userData.bodyId = body.id;
      group.add(mesh);

      let label: CSS2DObject | undefined;
      if (typeof document !== 'undefined') {
        const div = document.createElement('button');
        div.type = 'button';
        div.className = 'body-label';
        div.textContent = body.name;
        div.addEventListener('click', () => this.callbacks.onSelect(body.id));
        label = new CSS2DObject(div);
        const offset = mesh.userData.labelOffset as THREE.Vector3 | undefined;
        if (offset) label.position.copy(offset);
        else label.position.set(0, radius * 1.25 + 0.15, 0);
        group.add(label);
      }

      this.scene.add(group);
      this.nodes.set(body.id, { body, group, mesh, radius, glow, label });
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
      const unknownOrbit = node.body.facts.some((f) => /not fitted|assumed/i.test(f.value));
      const mat = new THREE.LineBasicMaterial({
        color: unknownOrbit ? 0xfbbf24 : 0x3a4a6b,
        transparent: true,
        opacity: unknownOrbit ? 0.5 : 0.8,
      });
      const line = new THREE.Line(geo, mat);
      line.visible = this.options.showOrbits;
      this.scene.add(line);
      node.orbitLine = line;
    }
  }

  // --- per frame --------------------------------------------------------------------
  private updatePositions() {
    for (const body of this.order) {
      const node = this.nodes.get(body.id)!;
      if (!body.orbit) {
        node.group.position.set(0, 0, 0);
      } else {
        const parent = this.nodes.get(body.orbit.parent);
        const base = parent ? parent.group.position : new THREE.Vector3();
        node.group.position.copy(base).add(this.displayOffset(orbitalPosition(body.orbit, this.mjd)));
        node.orbitLine?.position.copy(base);
      }
      if (body.variability) {
        const f = variabilityFactor(body, this.mjd);
        const s = Math.pow(f, 0.08); // pulsating stars change size a little, brightness a lot
        node.mesh.scale.setScalar(s);
        if (node.glow) {
          node.glow.scale.setScalar(node.radius * 5 * Math.pow(f, 0.3));
          (node.glow.material as THREE.SpriteMaterial).opacity = Math.min(1, 0.35 + 0.4 * Math.log10(1 + f * 3));
        }
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
    const dist = Math.max(extent * 1.9, maxRadius * 4.5, 6);
    this.controls.target.set(0, 0, 0);
    this.camera.position.set(0, dist * 0.55, dist);
    this.camera.near = Math.max(dist / 5000, 0.005);
    this.camera.updateProjectionMatrix();
  }

  private resize() {
    const w = this.container.clientWidth || 1;
    const h = this.container.clientHeight || 1;
    this.renderer.setSize(w, h);
    this.labelRenderer.setSize(w, h);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
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
    if (this.playing && dt > 0) {
      this.mjd += this.speed * dt;
      this.updatePositions();
    }
    for (const n of this.nodes.values()) if (n.body.kind !== 'disk') n.mesh.rotation.y += dt * 0.25;

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
        if (Math.abs(next - this.zoomTarget) < 0.05) this.zoomTarget = null;
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
