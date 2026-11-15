import { describe, expect, it } from 'vitest';
import type { SystemModel } from '../api/types';
import { datasetLegend } from './viewerKit';

const SYSTEMS = Object.values(
  import.meta.glob<SystemModel>('../../../data/demo/systems/*.json', { eager: true, import: 'default' }),
);
const system = (id: string): SystemModel => {
  const s = SYSTEMS.find((x) => x.id === id);
  if (!s) throw new Error(`demo system ${id} missing`);
  return s;
};

// Sources of the modules that ship in the main chunk, read as text (nothing is executed).
const SOURCES = import.meta.glob<string>(['../components/SystemViewer.tsx', './datasetGate.ts', './viewerLink.ts'], {
  eager: true,
  query: '?raw',
  import: 'default',
});
const source = (path: string): string => {
  const s = SOURCES[path];
  if (s === undefined) throw new Error(`${path} not found`);
  return s;
};

/** Specifiers of the value (non-type) static imports of a module. */
function staticValueImports(src: string): string[] {
  const out: string[] = [];
  for (const m of src.matchAll(/^import\s+(type\s+)?[^;]*?from\s+'([^']+)';/gms)) if (!m[1]) out.push(m[2]);
  return out;
}

describe('dataset-time legend', () => {
  it('explains an arc, the line-of-sight arrow and no ring for Barnard (all dated)', () => {
    expect(datasetLegend(system('barnards-star'))).toEqual({ arc: true, fittedRing: false, guessedRing: [], lineOfSight: true });
  });

  it("separates Eps Ind's fitted rings (Ab, Bb) from Ba's assumed orbit", () => {
    expect(datasetLegend(system('epsilon-indi'))).toEqual({ arc: false, fittedRing: true, guessedRing: ['assumed'], lineOfSight: false });
  });

  it('has nothing to explain for a system without orbits', () => {
    expect(datasetLegend(system('r-draconis'))).toEqual({ arc: false, fittedRing: false, guessedRing: [], lineOfSight: false });
  });
});

describe('main-chunk weight of the 3D viewer', () => {
  it('imports no WS7 helper module statically except the tiny datasetGate and viewerLink', () => {
    const imports = staticValueImports(source('../components/SystemViewer.tsx'));
    expect(imports.length).toBeGreaterThan(0);
    const three = imports.filter((s) => s.startsWith('../three/'));
    expect(three.sort()).toEqual(['../three/datasetGate', '../three/viewerLink']);
    for (const s of imports) expect(s, s).toMatch(/^(react|\.\.\/api\/[a-z]+|\.\.\/three\/(datasetGate|viewerLink))$/);
    // The helpers and the timeline come through dynamic imports.
    expect(source('../components/SystemViewer.tsx')).toContain("import('../three/viewerKit')");
    expect(source('../components/SystemViewer.tsx')).toContain("import('../three/DatasetTimeline')");
  });

  it('keeps datasetGate and viewerLink free of value imports other than react', () => {
    expect(staticValueImports(source('./datasetGate.ts'))).toEqual([]);
    expect(staticValueImports(source('./viewerLink.ts'))).toEqual(['react']);
  });
});
