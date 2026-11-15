// Display names of Body.kind values. Kept apart from appearance.ts (which imports astro.ts) so that
// the pages and panels of the main chunk (SystemsPage, BodyPanel) can label a body without pulling
// the astrophysics module into it. appearance.ts re-exports KIND_LABEL for the 3D modules.
export const KIND_LABEL: Readonly<Record<string, string>> = {
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
