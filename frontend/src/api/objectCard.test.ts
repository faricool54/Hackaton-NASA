import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, createClient } from './client';
import { parseCoordinate, positionUrl, readPosition } from './jobs';
import {
  coordinateLookup, describeObjectError, factRows, formatArcsec, gaiaMarkerLookup, GAIA_MARKER_RADIUS_ARCSEC,
  identityCaveat, identityNotSecure, isEmptySky, keyRows,
  lookupKey, lookupLabel, magnitudeText, matchBadge, matchSummary, nameLookup, objectTitle, objectTypeLine,
  photometryGroups, planetLine, planetsRow, planetsSummary, positionLookup, serviceRows, servicesSummary, splitCaveat,
  summaryLines, variabilityText,
} from './objectCard';
import { SHOWCASE_TARGETS } from './showcase';
import type { ContextMagnitude, ContextService, ObjectContextResponse, ObjectIdentity, ObjectPlanet } from './types';

afterEach(() => vi.unstubAllGlobals());

const UNKNOWN_FACTS = ['Effective temperature', 'Radius', 'Distance'].map((label) =>
  ({ label, value: 'unknown', unit: null, source: 'No Gaia DR3 counterpart.', verified: false }));

function response(identity: Partial<ObjectIdentity> = {}, extra: Partial<ObjectContextResponse> = {}): ObjectContextResponse {
  return {
    schema_version: '0.5.0',
    query: { ra: 200, dec: 40.1, name: null, epoch_mjd: 61000, radius_arcsec: 8 },
    position: { ra: 200, dec: 40.1, epoch_mjd: 61000, source: 'query position (static)' },
    identity: { display_name: null, main_id: null, object_type: null, object_type_label: null, spectral_type: null,
      resolver: null, gaia_source_id: null, gaia_method: null, match: 'none', identity_uncertain: false,
      separation_arcsec: null, n_gaia_within_radius: 0, ...identity },
    facts: UNKNOWN_FACTS, variability: null, planets: [], nearby_planet_hosts: [], photometry: [], warnings: [],
    provenance: [], partial: false, built_at: '2026-11-15T12:00:00Z',
    note: 'Catalog context from other missions/surveys: not SPHEREx measurements.', synthetic: false, ...extra,
  };
}

const MAG: ContextMagnitude = {
  mission: '2MASS', other_mission: true, catalog: '2MASS All-Sky PSC II/246/out (VizieR CfA)',
  designation: '2MASS J17574849+0441405', band: 'J', wavelength_um: 1.235, mag: 5.244, mag_err: 0.02, system: 'Vega',
  quality: 'A', contamination: null, upper_limit: false, epoch_mjd: 51692.4, separation_arcsec: 0.3,
  identity_uncertain: false,
};

describe('object lookups', () => {
  it('queries names by name and clicks by position, with stable keys', () => {
    expect(nameLookup('  R Dra ')).toEqual({ name: 'R Dra' });
    expect(nameLookup('   ')).toBeNull();
    expect(positionLookup(200, 40.1)).toEqual({ ra: 200, dec: 40.1 });
    expect(positionLookup(360, 0)).toBeNull();
    expect(positionLookup(NaN, 0)).toBeNull();
    expect(lookupKey(null)).toBe('');
    expect(lookupKey({ ra: 200, dec: 40.1 })).toBe(lookupKey({ ra: 200.00000001, dec: 40.1 }));
    expect(lookupKey({ name: 'R Dra' })).not.toBe(lookupKey({ name: 'RW Aur' }));
    expect(lookupLabel({ ra: 331.09665, dec: -56.80066 })).toBe('331.09665°, -56.80066°');
    expect(lookupLabel({ name: 'eps Ind B' })).toBe('“eps Ind B”');
  });

  it('keeps a preset NAME lookup for its untouched position (Build, shared link); edits and clicks go by position', () => {
    // Regression (review 2026-11-15): Build after the WISE 0855 preset looked its position up and showed a G = 16
    // field star 6.9" away; RW Aur became RW Aur B. Build parses the ra/dec text the preset wrote.
    for (const t of SHOWCASE_TARGETS) {
      expect(coordinateLookup(parseCoordinate(String(t.ra), true), parseCoordinate(String(t.dec), false)))
        .toEqual({ name: t.catalogName });
      const shared = readPosition(new URL(positionUrl('http://x/?mode=api', { ra: t.ra, dec: t.dec, size_deg: 0.15,
        detectors: [t.detector] })).search);
      expect(coordinateLookup(shared.ra, shared.dec)).toEqual({ name: t.catalogName });
    }
    const wise = SHOWCASE_TARGETS[2];
    expect(coordinateLookup(wise.ra + 1e-4, wise.dec)).toEqual({ ra: wise.ra + 1e-4, dec: wise.dec }); // edited
    expect(coordinateLookup(200, 40.1)).toEqual({ ra: 200, dec: 40.1 });
    expect(coordinateLookup(360, 0)).toBeNull();
  });

  it('builds the API URL and refuses static mode', async () => {
    const fetch = vi.fn().mockImplementation(async () => new Response(JSON.stringify(response()), { status: 200 }));
    vi.stubGlobal('fetch', fetch);
    const api = createClient({ mode: 'api', apiBase: 'http://api', staticBase: '/data/demo/' });
    await api.getObjectContext({ name: "Barnard's Star" });
    await api.getObjectContext({ ra: 331.09665, dec: -56.80066 });
    expect(fetch.mock.calls[0][0]).toBe("http://api/api/object?name=Barnard%27s+Star");
    expect(fetch.mock.calls[1][0]).toBe('http://api/api/object?ra=331.09665&dec=-56.80066');
    const offline = createClient({ mode: 'static', apiBase: 'http://api', staticBase: '/data/demo/' });
    await expect(offline.getObjectContext({ name: 'x' })).rejects.toThrow('live API');
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it('sends the radius and epoch of a Gaia marker click, and keeps them in the lookup key', async () => {
    const fetch = vi.fn().mockImplementation(async () => new Response(JSON.stringify(response()), { status: 200 }));
    vi.stubGlobal('fetch', fetch);
    const api = createClient({ mode: 'api', apiBase: 'http://api', staticBase: '/data/demo/' });
    const marker = gaiaMarkerLookup(269.4463725391953, 4.768815881735359, 61116.6838019213);
    expect(marker).toEqual({ ra: 269.4463725391953, dec: 4.768815881735359, radiusArcsec: GAIA_MARKER_RADIUS_ARCSEC, epochMjd: 61116.6838019213 });
    await api.getObjectContext(marker!);
    expect(fetch.mock.calls[0][0]).toBe(
      'http://api/api/object?ra=269.4463725391953&dec=4.768815881735359&radius_arcsec=1.5&epoch_mjd=61116.6838019213');
    // A marker lookup is a different card from a plain click at the same position (8″ radius at MJD 61000).
    expect(lookupKey(marker)).not.toBe(lookupKey(positionLookup(269.4463725391953, 4.768815881735359)));
    expect(lookupKey(marker)).not.toBe(lookupKey(gaiaMarkerLookup(269.4463725391953, 4.768815881735359, 61000)));
    expect(lookupKey({ ra: 200, dec: 40.1 })).toBe('pos:200.0000000,40.1000000');
    // An epoch the API refuses (outside MJD 15020–88070) falls back to the plain position lookup.
    expect(gaiaMarkerLookup(200, 40.1, Number.NaN)).toEqual({ ra: 200, dec: 40.1 });
    expect(gaiaMarkerLookup(200, 40.1, 90000)).toEqual({ ra: 200, dec: 40.1 });
  });
});

describe('identity and match status', () => {
  it('distinguishes empty sky from an unreachable catalog', () => {
    const empty = response();
    expect(isEmptySky(empty)).toBe(true);
    expect(matchSummary(empty)).toMatchObject({ label: 'No catalogued source at this position', tone: 'none' });
    const down = response({ match: 'unavailable', identity_uncertain: true }, { partial: true });
    expect(isEmptySky(down)).toBe(false);
    expect(matchSummary(down)).toMatchObject({ label: 'Identity unknown', tone: 'warn' });
    expect(matchSummary(down).detail).toContain('not a negative result');
    const vsxDown: ContextService = { service: 'vsx', catalog: 'AAVSO VSX', url: null, status: 'error',
      retrieved_utc: null, cached: false, stale: false, note: 'ReadTimeout' };
    expect(isEmptySky(response({}, { provenance: [vsxDown], partial: true }))).toBe(false);
  });

  it('warns on ambiguous and loose matches and on names SIMBAD did not identify', () => {
    expect(matchSummary(response({ match: 'ambiguous', identity_uncertain: true }))).toMatchObject({ tone: 'warn', label: 'Ambiguous identification' });
    const loose = matchSummary(response({ match: 'loose', separation_arcsec: 6.93, gaia_source_id: '5756956644387831296' }));
    expect(loose.tone).toBe('warn');
    expect(loose.detail).toContain('6.9″');
    const byName = response({ match: 'none', identity_uncertain: true, resolver: "Sesame resolver 'Vl=VizieR (local)' (CfA)" },
      { query: { ra: null, dec: null, name: 'GJ 699', epoch_mjd: 61000, radius_arcsec: 8 } });
    expect(matchSummary(byName)).toMatchObject({ label: 'Name not identified by SIMBAD', tone: 'warn' });
    expect(isEmptySky(byName)).toBe(false);
  });

  it('keeps the 64-bit Gaia id exact and says how it was matched', () => {
    const named = matchSummary(response({ match: 'name', gaia_source_id: '4472832130942575872', gaia_method: 'simbad_crossid' }));
    expect(named).toMatchObject({ tone: 'ok', label: 'Identified by name (SIMBAD)' });
    expect(named.detail).toContain('Gaia DR3 4472832130942575872 (SIMBAD cross-identification)');
    expect(matchSummary(response({ match: 'name' }))).toMatchObject({ tone: 'ok' });
    expect(matchSummary(response({ match: 'name' })).detail).toContain('No Gaia DR3 counterpart');
    const matched = matchSummary(response({ match: 'matched', gaia_source_id: '6412596012146801152', separation_arcsec: 0.51 }));
    expect(matched.detail).toContain('0.5″ from the requested position');
    // a positional match cannot see an object Gaia lacks (WISE 0855 next to a G = 16 field star)
    expect(matched.detail).toContain('absent from Gaia DR3');
  });

  it('never turns a Gaia outage into "no Gaia DR3 counterpart" for a name', () => {
    // Regression (review 2026-11-15): ESA and VizieR down, or the API deadline, gave match 'name' with no Gaia id.
    const gaiaDown: ContextService[] = ['gaia-esa', 'gaia-vizier'].map((service) => ({ service, catalog: 'Gaia DR3',
      url: null, status: 'error', retrieved_utc: null, cached: false, stale: false, note: 'no answer within the 25 s API deadline' }));
    const name = { ra: null, dec: null, name: 'R Dra', epoch_mjd: 61000, radius_arcsec: 8 };
    const down = matchSummary(response({ match: 'name', n_gaia_within_radius: null, display_name: 'R Dra' },
      { query: name, provenance: gaiaDown, partial: true }));
    expect(down.tone).toBe('warn');
    expect(down.detail).toContain('could not be reached');
    expect(down.detail).toContain('not a negative result');
    expect(down.detail).not.toContain('No Gaia DR3 counterpart');
    // the ESA cone answered nothing, but SIMBAD's Gaia id could not be fetched: not a firm negative either
    const half = matchSummary(response({ match: 'name', n_gaia_within_radius: 0 },
      { query: name, provenance: [{ ...gaiaDown[0], status: 'ok' }, gaiaDown[0]], partial: true }));
    expect(half).toMatchObject({ tone: 'warn' });
    expect(half.detail).toContain('not a firm negative');
    // ESA down, the VizieR CfA copy of Gaia DR3 answered (WISE 0855 by name, live 2026-11-15): an answered negative
    const fallback = matchSummary(response({ match: 'name', n_gaia_within_radius: 0 },
      { query: name, provenance: [gaiaDown[0], { ...gaiaDown[1], status: 'ok' }, { ...gaiaDown[1], status: 'ok' }] }));
    expect(fallback).toMatchObject({ tone: 'ok' });
    expect(fallback.detail).toBe('No Gaia DR3 counterpart: values come from SIMBAD and the other catalogs only.');
    // ...but not when one of the VizieR queries failed too
    expect(matchSummary(response({ match: 'name', n_gaia_within_radius: 0 },
      { query: name, provenance: [gaiaDown[0], { ...gaiaDown[1], status: 'ok' }, gaiaDown[1]] })).tone).toBe('warn');
  });
});

describe('facts, variability, planets and photometry', () => {
  it('shows unknown as unknown and marks verification', () => {
    const rows = factRows([
      { label: 'Radius', value: '0.202 (0.198-0.206)', unit: 'R_sun', source: 'Gaia DR3 FLAME', verified: true },
      { label: 'Distance', value: '185 (175-195)', unit: 'pc', source: 'Ambiguous Gaia match', verified: false },
      { label: 'Mass', value: 'unknown', unit: null, source: null, verified: false },
    ]);
    expect(rows.map((r) => [r.value, r.status])).toEqual([
      ['0.202 (0.198-0.206) R☉', 'verified'], ['185 (175-195) pc', 'not verified'], ['unknown', 'unknown']]);
    expect(rows[2].source).toBe('no source given');
  });

  it('formats VSX ranges, amplitudes and periods', () => {
    const base = { name: 'R Dra', var_type: 'M', period_days: 246.12, mag_max: 6.7, mag_min: 13.2, min_is_amplitude: false,
      passband: 'V', separation_arcsec: 0.1, url: null, source: 'AAVSO VSX' };
    expect(variabilityText(base)).toBe('M · V 6.7–13.2 mag · period 246.12 d');
    expect(variabilityText({ ...base, var_type: 'BY', min_is_amplitude: true, mag_min: 0.02, period_days: null }))
      .toBe('BY · V amplitude 0.02 mag');
  });

  it('counts confirmed planets and labels minimum masses and estimated radii', () => {
    const planet: ObjectPlanet = { name: 'Barnard b', hostname: "Barnard's star", match: 'gaia_dr3_id', period_days: 3.1542,
      semi_major_axis_au: 0.0229, radius_earth: 0.7, radius_calculated: true, mass_earth: 0.299, mass_kind: 'Msini',
      eccentricity: 0.03, inclination_deg: null, discovery_year: 2024, discovery_method: 'Radial Velocity',
      discovery_facility: null, reference: null, controversial: false, source: 'NASA Exoplanet Archive' };
    expect(planetsSummary(response({}, { planets: [planet, { ...planet, name: 'Barnard c' }] }))).toBe('2 confirmed planets (NASA Exoplanet Archive)');
    expect(planetLine(planet)).toBe('Barnard b · P = 3.154 d · M sin i = 0.299 M⊕ (minimum) · R ≈ 0.7 R⊕ (estimated, not measured) · Radial Velocity, 2024');
    expect(planetsSummary(response())).toBe('No confirmed planets listed for this object');
    const down: ContextService = { service: 'exoplanets', catalog: 'NASA Exoplanet Archive', url: null, status: 'error',
      retrieved_utc: null, cached: false, stale: false, note: 'ReadTimeout' };
    expect(planetsSummary(response({}, { provenance: [down] }))).toContain('did not answer');
    // a loose/ambiguous identity: the planets and VSX entry belong to the ADOPTED source, which may be a neighbour
    const loose = response({ match: 'loose', identity_uncertain: true, separation_arcsec: 5 }, { planets: [planet] });
    expect(planetsSummary(loose)).toBe('1 confirmed planet (NASA Exoplanet Archive) · of the adopted source; identity uncertain (may be a neighbour)');
    expect(identityCaveat(loose)).toContain('identity uncertain');
    expect(identityCaveat(response())).toBeNull();
    expect(planetsSummary(response({ match: 'ambiguous', identity_uncertain: true }))).toContain('identity uncertain');
  });

  it('labels 2MASS/AllWISE as other missions and keeps upper limits and flags', () => {
    const groups = photometryGroups([
      MAG, { ...MAG, band: 'H', mag: null },
      { ...MAG, mission: 'WISE', designation: 'AllWISE J175747.94+044323.8', band: 'W4', mag: 9.15, mag_err: null,
        upper_limit: true, quality: 'U', contamination: 'd', identity_uncertain: true },
    ]);
    expect(groups.map((g) => g.label)).toEqual(['2MASS · other mission, not SPHEREx', 'AllWISE · other mission, not SPHEREx']);
    expect(groups[0].rows.map((r) => r.magnitude)).toEqual(['5.24 ± 0.02 (Vega)', 'no measurement (Vega)']);
    expect(groups[1].rows[0]).toMatchObject({ magnitude: '> 9.15 (upper limit) (Vega)', flags: 'quality U, contamination d' });
    expect(groups[1].identityUncertain).toBe(true);
    expect(magnitudeText({ ...MAG, mag_err: null })).toBe('5.24');
  });
});

describe('services and errors', () => {
  it('reports unanswered services as unknown, not negative', () => {
    const rows = serviceRows([
      { service: 'sesame', catalog: 'SIMBAD via Sesame', url: null, status: 'ok', retrieved_utc: '2026-11-15T03:44:16Z', cached: true, stale: false, note: null },
      { service: 'vsx', catalog: 'AAVSO VSX', url: null, status: 'error', retrieved_utc: null, cached: false, stale: false, note: 'no answer within the 25 s API deadline' },
      { service: 'gaia-esa', catalog: 'Gaia DR3', url: null, status: 'ok', retrieved_utc: '2026-11-01T00:00:00Z', cached: true, stale: true, note: null },
    ]);
    expect(rows.map((r) => [r.name, r.status, r.tone])).toEqual([
      ['SIMBAD (Sesame, CfA)', 'answered', 'ok'], ['AAVSO VSX', 'no answer: unknown, not negative', 'warn'],
      ['Gaia DR3 (ESA archive)', 'answered', 'warn']]);
    expect(rows[0].detail).toContain('retrieved 2026-11-15 03:44 UTC');
    expect(rows[2].detail).toContain('STALE');
    expect(servicesSummary([])).toBe('0 catalog calls · all answered');
  });

  it('turns API failures into card messages', () => {
    expect(describeObjectError(new ApiError("Name not found by SIMBAD/Sesame (CfA): 'zz'.", 404))).toContain('Try a SIMBAD name');
    expect(describeObjectError(new ApiError('busy', 503))).toContain('busy');
    expect(describeObjectError(new ApiError('late', 504))).toContain('did not answer in time');
    expect(describeObjectError(new ApiError('down', 502))).toContain('could not be reached');
    expect(describeObjectError(new DOMException('late', 'TimeoutError'))).toContain('did not arrive in time');
    expect(describeObjectError(new TypeError('Failed to fetch'))).toBe('Could not reach the API for catalog context.');
    expect(formatArcsec(null)).toBe('unknown');
    expect(formatArcsec(404.4)).toBe('404″');
  });
});

describe('compact card rows (FE-5)', () => {
  const fact = (label: string, value: string, verified = true, unit: string | null = null) =>
    ({ label, value, unit, source: `${label} source`, verified });
  // Source strings shaped like the backend's (PhysicalParameter.to_fact in pipeline/errante/science/context.py).
  const VSX = 'AAVSO VSX V2500 Oph (B/vsx, VizieR CfA, retrieved 2026-11-15)';
  const facts = [
    fact('Effective temperature', '3195', true, 'K'), fact('Radius', '0.19', true, 'R_sun'), fact('Distance', '1.83', true, 'pc'),
    fact('Spectral type', 'M4V'), { ...fact('Variability type', 'BY'), source: VSX }, fact('Variability period', 'unknown', false),
  ];
  const star = response({ display_name: "Barnard's Star", match: 'name', gaia_source_id: '1', object_type: 'BY*',
    object_type_label: 'BY Dra variable', spectral_type: 'M4V' }, {
    facts, variability: { name: 'V2500 Oph', var_type: 'BY', period_days: null, mag_max: null, mag_min: null,
      min_is_amplitude: false, passband: null, separation_arcsec: 0.2, url: 'https://vsx.aavso.org/x', source: 'VSX' },
  });

  it('shows the key facts in a fixed order in the dock and every fact in the full card', () => {
    expect(keyRows(star).map((r) => r.label)).toEqual(['Distance', 'Effective temperature', 'Spectral type', 'Variability type', 'Planets']);
    expect(keyRows(star, 'full').map((r) => r.label)).toEqual([...facts.map((f) => f.label), 'Planets']);
    expect(keyRows(star)[0]).toMatchObject({ value: '1.83 pc', status: 'verified', source: 'Distance source', href: null,
      caveat: null });
    expect(keyRows(star)[3].href).toBe('https://vsx.aavso.org/x'); // the VSX page backs the variability value
    const known = response({}, { facts: [...facts.slice(0, 5), fact('Variability period', '130.4', true, 'days')] });
    expect(keyRows(known).map((r) => r.label)).toContain('Variability period');
  });

  it('links a variability value to VSX only when VSX is its source', () => {
    // VSX lists the star without a period; the period comes from Gaia DR3's long-period-variable table.
    const lpv = { ...fact('Variability period', '412', true, 'days'),
      source: 'Gaia DR3 123, gaiadr3.vari_long_period_variable (ESA archive) | Caveat: AAVSO VSX could not be reached.' };
    const rows = keyRows({ ...star, facts: [...facts.slice(0, 5), lpv] });
    expect(rows.find((r) => r.label === 'Variability type')?.href).toBe('https://vsx.aavso.org/x');
    expect(rows.find((r) => r.label === 'Variability period')?.href).toBeNull();
  });

  it('splits the backend caveat off a source and marks it on the row', () => {
    expect(splitCaveat('Gaia DR3 1 | GSP-Phot | Caveat: M dwarfs are unreliable: indicative only.')).toEqual({
      source: 'Gaia DR3 1 | GSP-Phot', caveat: 'M dwarfs are unreliable: indicative only.' });
    expect(splitCaveat('Caveat: identity uncertain.')).toEqual({ source: '', caveat: 'identity uncertain.' });
    expect(splitCaveat('SIMBAD via Sesame')).toEqual({ source: 'SIMBAD via Sesame', caveat: null });
    expect(splitCaveat('A note on the Caveat: word')).toEqual({ source: 'A note on the Caveat: word', caveat: null });
    const teff = { ...fact('Effective temperature', '3100 (3099-3102)', true, 'K'),
      source: 'Gaia DR3 1, I/355/gaiadr3 | GSP-Phot | Caveat: GSP-Phot temperatures of M dwarfs are unreliable: indicative only.' };
    const caveated = { ...star, facts: [teff, ...facts.slice(1)] };
    expect(keyRows(caveated).find((r) => r.label === 'Effective temperature')).toMatchObject({
      status: 'verified', caveat: 'GSP-Phot temperatures of M dwarfs are unreliable: indicative only.' });
    // the popup has no room for the caveat on its one clipped line: it leaves that Teff out (the card shows it)
    expect(summaryLines(caveated).map((l) => l.text)).toContain('Distance 1.83 pc (verified)');
    expect(summaryLines(caveated).some((l) => l.text.includes('Teff'))).toBe(false);
  });

  it('labels the match with a short text badge for the header', () => {
    expect(matchBadge(star)).toEqual({ label: 'Name match', tone: 'ok', title: 'Identified by name (SIMBAD)' });
    expect(matchBadge(response({ match: 'ambiguous' }))).toMatchObject({ label: 'Ambiguous', tone: 'warn' });
    expect(matchBadge(response({ match: 'loose', separation_arcsec: 5 }))).toMatchObject({ label: 'Loose match', tone: 'warn' });
    expect(matchBadge(response({ match: 'matched', gaia_source_id: '2' }))).toMatchObject({ label: 'Gaia match', tone: 'ok' });
    expect(matchBadge(response({ match: 'unavailable' }))).toMatchObject({ label: 'Identity unknown', tone: 'warn' });
    expect(matchBadge(response())).toMatchObject({ label: 'No source', tone: 'none' });
    const named = response({}, { query: { ra: null, dec: null, name: 'Foo', epoch_mjd: 61000, radius_arcsec: 8 } });
    expect(matchBadge(named)).toMatchObject({ label: 'Not identified', tone: 'warn' });
  });

  it('counts planets and never turns an archive outage into "none"', () => {
    const planet = { name: 'b' } as ObjectPlanet;
    expect(planetsRow(response({}, { planets: [planet, planet] }))).toMatchObject({ value: '2 confirmed', unknown: false });
    expect(planetsRow(response())).toMatchObject({ value: 'none listed', unknown: false, source: 'NASA Exoplanet Archive' });
    const down = response({}, { provenance: [{ service: 'exoplanets', catalog: 'PS', url: null, status: 'error',
      retrieved_utc: null, cached: false, stale: false, note: null }] });
    expect(planetsRow(down)).toMatchObject({ value: 'unknown', unknown: true, caveat: null });
    expect(planetsRow(response({ identity_uncertain: true, match: 'loose' })).source).toContain('identity uncertain');
    expect(planetsRow(response({ identity_uncertain: true, match: 'loose' })).caveat).toContain('identity uncertain');
    expect(planetsRow(response()).caveat).toBeNull();
  });

  it('titles the card without inventing a name', () => {
    expect(objectTitle(star)).toBe("Barnard's Star");
    expect(objectTitle(response())).toBe('No catalogued source');
    expect(objectTitle(response({ match: 'matched', gaia_source_id: '2' }))).toBe('Unidentified position');
    expect(objectTypeLine(star)).toBe('BY Dra variable (BY*) · spectral type M4V');
    expect(objectTypeLine(response())).toBe('');
    expect(identityNotSecure(response({ identity_uncertain: true, match: 'name' }))).toBe(true);
    expect(identityNotSecure(response({ identity_uncertain: true, match: 'ambiguous' }))).toBe(false);
  });

  it('summarises the card in at most five lines under the title, keeping the caveats', () => {
    expect(summaryLines(star).map((l) => l.text)).toEqual([
      'BY Dra variable (BY*) · spectral type M4V', 'Identified by name (SIMBAD)',
      'Distance 1.83 pc (verified) · Teff 3195 K (verified)', 'Variable: BY · Planets: none listed']);
    const shaky = { ...star, partial: true, identity: { ...star.identity, identity_uncertain: true } };
    const lines = summaryLines(shaky);
    expect(lines.length).toBeLessThanOrEqual(5);
    expect(lines[lines.length - 1]).toEqual({ text: 'Partial: some catalogs did not answer · Identity not secure', tone: 'warn' });
    expect(summaryLines(response()).map((l) => l.text)).toEqual([
      'No catalogued source at this position', 'Nothing catalogued within 8.0″; SPHEREx may still show emission.']);
  });
});
