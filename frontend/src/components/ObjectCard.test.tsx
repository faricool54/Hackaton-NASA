import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { ObjectContextResponse } from '../api/types';
import { ObjectCardView } from './ObjectCard';
import { ObjectSummary } from './ObjectSummary';

// Test fixture shaped like a GET /api/object answer for a name lookup (values illustrative, not a recorded answer).
const fact = (label: string, value: string, unit: string | null, verified: boolean) =>
  ({ label, value, unit, verified, source: `${label}: Gaia DR3 (VizieR CfA) | method | Caveat: long text` });
const planet = (name: string) => ({
  name, hostname: "Barnard's star", match: 'gaia_dr3_id' as const, period_days: 3.15, semi_major_axis_au: 0.02,
  radius_earth: 0.7, radius_calculated: true, mass_earth: 0.37, mass_kind: 'Msini', eccentricity: null,
  inclination_deg: null, discovery_year: 2024, discovery_method: 'Radial Velocity', discovery_facility: null,
  reference: null, controversial: false, source: 'NASA Exoplanet Archive pscomppars',
});
const BARNARD: ObjectContextResponse = {
  schema_version: '0.5.0',
  query: { ra: null, dec: null, name: "Barnard's Star", epoch_mjd: 61000, radius_arcsec: 8 },
  position: { ra: 269.45, dec: 4.69, epoch_mjd: 61000, source: 'Gaia DR3 propagated' },
  identity: { display_name: "Barnard's Star", main_id: "NAME Barnard's star", object_type: 'BY*',
    object_type_label: 'BY Dra variable', spectral_type: 'M4V', resolver: 'SIMBAD', gaia_source_id: '4472832130942575872',
    gaia_method: 'simbad_crossid', match: 'name', identity_uncertain: false, separation_arcsec: null, n_gaia_within_radius: 1 },
  facts: [fact('Effective temperature', '3195', 'K', false), fact('Radius', '0.19', 'R_sun', false),
    fact('Luminosity', '0.0035', 'L_sun', false), fact('Mass', 'unknown', null, false), fact('Distance', '1.83', 'pc', true),
    fact('Spectral type', 'M4V', null, true),
    { ...fact('Variability type', 'BY', null, true), source: 'AAVSO VSX V2500 Oph (B/vsx, VizieR CfA)' },
    fact('Variability period', 'unknown', null, false)],
  variability: { name: 'V2500 Oph', var_type: 'BY', period_days: null, mag_max: 9.5, mag_min: 9.6, min_is_amplitude: false,
    passband: 'V', separation_arcsec: 0.3, url: 'https://www.aavso.org/vsx/index.php?view=detail.top&oid=1', source: 'VSX' },
  planets: ['b', 'c', 'd', 'e'].map((x) => planet(`Barnard ${x}`)),
  nearby_planet_hosts: [], photometry: [{ mission: '2MASS', other_mission: true, catalog: '2MASS', designation: 'J1757',
    band: 'J', wavelength_um: 1.235, mag: 5.24, mag_err: 0.02, system: 'Vega', quality: 'A', contamination: null,
    upper_limit: false, epoch_mjd: null, separation_arcsec: 0.3, identity_uncertain: false }],
  warnings: ['First warning text.', 'Second warning text.'],
  provenance: [{ service: 'sesame', catalog: 'SIMBAD', url: null, status: 'ok', retrieved_utc: null, cached: true,
    stale: false, note: null }],
  partial: false, built_at: '2026-11-15T12:00:00Z', synthetic: false,
  note: "Catalog context from other missions/surveys: not SPHEREx measurements. 'unknown' = not measured or not found.",
};

const view = (props: Partial<Parameters<typeof ObjectCardView>[0]> = {}) => renderToStaticMarkup(
  <ObjectCardView lookup={{ name: "Barnard's Star" }} variant="dock" live busy={false} data={BARNARD} error=""
    onRetry={() => {}} {...props} />);
const text = (html: string) => html.replace(/<[^>]+>/g, ' ').replace(/&#x27;/g, "'").replace(/&amp;/g, '&')
  .replace(/\s+/g, ' ');

describe('object card', () => {
  it('keeps the provenance labels visible and folds the details in the dock', () => {
    const html = view();
    expect(html).toContain('Catalog · not SPHEREx');
    expect(html).toContain('Catalog context, not SPHEREx measurements.');
    expect(html).not.toContain('<details open');
    expect(text(html)).toContain('Distance 1.83 pc verified');
    expect(text(html)).toContain('4 confirmed');
    expect(text(html)).toContain('2 catalog warnings');
    expect(text(html)).toContain('All 8 catalog parameters with sources');
    // the dock grid has the key facts only; Radius stays in the folded list of every parameter
    expect(html).not.toContain('<dt>Radius</dt>');
    expect(html).toContain('<strong>Radius:</strong>');
    expect(html).toContain('href="https://www.aavso.org/vsx/');
  });

  it('shows the match badge in the header and marks caveats and unknowns on the value line', () => {
    const html = view();
    const head = text(html.slice(0, html.indexOf('</header>')));
    expect(head).toContain('Name match');
    expect(head).toContain('Catalog · not SPHEREx');
    // the clipped source note would hide "Caveat: …": the value line carries a visible marker, the text in `title`
    expect(text(html)).toContain('Distance 1.83 pc verified caveat');
    expect(html).toContain('title="Caveat: long text"');
    const unknownTeff = { ...BARNARD, facts: BARNARD.facts.map((f) => f.label === 'Effective temperature' ? { ...f, value: 'unknown' } : f) };
    expect(text(view({ data: unknownTeff }))).toContain('Effective temperature unknown not a negative result');
  });

  it('keeps each dock alert to a short line and the full sentence in the full card', () => {
    const shaky = { ...BARNARD, partial: true, identity: { ...BARNARD.identity, identity_uncertain: true } };
    const dock = text(view({ data: shaky }));
    expect(dock).toContain('Partial: some catalogs did not answer (unknown, not negative). Retry');
    expect(dock).toContain('Identity not secure: values may belong to a neighbouring source.');
    const full = text(view({ data: shaky, variant: 'full' }));
    expect(full).toContain('Partial: some catalogs did not answer, so their values are unknown (not negative). Retry');
    expect(full).toContain('Identified by name (SIMBAD).');
  });

  it('shows "Partial" and "Identity not secure" without opening anything', () => {
    const shaky = { ...BARNARD, partial: true, identity: { ...BARNARD.identity, identity_uncertain: true } };
    const html = text(view({ data: shaky }));
    expect(html).toContain('Identity not secure');
    expect(html).toContain('Partial: some catalogs did not answer');
    expect(html.indexOf('Partial')).toBeLessThan(html.indexOf('All 8 catalog parameters'));
  });

  it('lists every parameter, planet and warning in the full variant', () => {
    expect(view({ variant: 'full' })).toContain('<dt>Radius</dt>');
    const html = text(view({ variant: 'full' }));
    expect(html).toContain('Radius 0.19 R☉');
    expect(html).toContain('Barnard e');
    expect(html).toContain('First warning text.');
    expect(html).not.toContain('catalog warnings');
  });

  it('uses the shared skeleton while loading and offers Retry on errors', () => {
    const loading = view({ busy: true, data: null });
    expect(loading).toContain('aria-label="Loading catalog context"');
    expect(loading).toContain('aria-busy="true"');
    expect(text(loading)).toContain('“Barnard\'s Star” Catalog · not SPHEREx');
    expect(text(view({ data: null, error: 'Catalog services did not answer in time; retry shortly.' }))).toContain('Retry');
    expect(text(view({ live: false, data: null }))).toContain('needs the live API');
  });

  it('summarises the same answer in at most six lines for the pinned popup', () => {
    const html = renderToStaticMarkup(<ObjectSummary data={{ ...BARNARD, partial: true }} />);
    expect(html.match(/<p /g)?.length).toBeLessThanOrEqual(6);
    expect(html).toContain('Catalog · not SPHEREx');
    expect(text(html)).toContain('Partial: some catalogs did not answer');
  });
});
