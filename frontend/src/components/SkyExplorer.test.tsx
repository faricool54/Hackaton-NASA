import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { SHOWCASE_TARGETS } from '../api/showcase';
import { EXPLORER_VIEWS, nextTabIndex } from './ExplorerDock';
import { PositionResults } from './PositionResults';
import { buildFailureText, buildsOnSelect, presetNote, resolverNote } from './SkyExplorer';

const text = (html: string) => html.replace(/<[^>]+>/g, ' ').replace(/&amp;/g, '&').replace(/\s+/g, ' ');

describe('FE-2 explorer flow', () => {
  it('starts a job only for a live map click away from a saved sequence, or for the build form (D-1)', () => {
    expect(buildsOnSelect('map', true)).toBe(true);
    expect(buildsOnSelect('map', true, 'barnards-star')).toBe(false);
    expect(buildsOnSelect('map', false)).toBe(false);
    expect(buildsOnSelect('form', true, 'barnards-star')).toBe(true);
    expect(buildsOnSelect('form', false)).toBe(false);
    for (const origin of ['preset', 'search'] as const) {
      expect(buildsOnSelect(origin, true)).toBe(false);
      expect(buildsOnSelect(origin, false)).toBe(false);
    }
  });

  it('keeps the provenance of presets and name lookups', () => {
    const barnard = SHOWCASE_TARGETS[0];
    expect(presetNote(barnard)).toBe("Barnard's Star: ICRS position propagated to mean epoch MJD 61104. "
      + 'Sesame/SIMBAD CfA astrometry, checked 14 Nov 2026. This preset is not a validated detection.');
    expect(resolverNote('M 31', 'Sesame (CfA mirror)')).toMatch(
      /^M 31 · Sesame \(CfA mirror\)\. Catalog position; coverage is checked separately\./);
    expect(resolverNote('M 31')).toContain('M 31 · name resolver.');
  });

  it('turns the disabled-job 503 into a visitor sentence and passes other errors through', () => {
    expect(buildFailureText('Job engine is disabled. Set ERRANTE_ENABLE_JOBS=1 to enable background builds.'))
      .toBe('Generating new sequences is disabled on this server.');
    expect(buildFailureText('No usable archive coverage.')).toBe('No usable archive coverage.');
  });

  it('moves between the dock tabs with arrows, Home and End', () => {
    const last = EXPLORER_VIEWS.length - 1;
    expect(nextTabIndex('ArrowRight', last)).toBe(0);
    expect(nextTabIndex('ArrowLeft', 0)).toBe(last);
    expect(nextTabIndex('Home', 2)).toBe(0);
    expect(nextTabIndex('End', 0)).toBe(last);
    expect(nextTabIndex('Enter', 1)).toBeNull();
  });

  it('shows the provenance note in the dock header', () => {
    const html = renderToStaticMarkup(createElement(PositionResults, {
      position: { ra: 269.44623, dec: 4.7687 }, sequences: [], systems: [], job: null, quickLook: false,
      lookup: null, view: 'Object', onView: () => {}, label: "Barnard's Star", note: presetNote(SHOWCASE_TARGETS[0]),
      synthetic: false, notice: '', onCopyLink: () => {}, object: null, build: null, selectedFieldId: 'barnards-star',
    }));
    expect(text(html)).toContain('This preset is not a validated detection.');
    expect(html).toContain('role="tablist"');
    expect(html).not.toContain('SYNTHETIC DATA');
  });
});
