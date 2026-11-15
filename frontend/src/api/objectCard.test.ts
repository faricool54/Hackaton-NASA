import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, createClient } from './client';
import { parseCoordinate, positionUrl, readPosition } from './jobs';
import {
  coordinateLookup, describeObjectError, factRows, formatArcsec, identityCaveat, isEmptySky, lookupKey, lookupLabel,
  magnitudeText, matchSummary, nameLookup, photometryGroups, planetLine, planetsSummary, positionLookup, serviceRows,
  servicesSummary, variabilityText,
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
