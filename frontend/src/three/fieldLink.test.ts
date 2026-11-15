import { describe, expect, it } from 'vitest';
import { fieldLinkLabel } from './fieldLink';

describe('fieldLinkLabel', () => {
  it('names the field target, so a system page does not imply its primary is in the field', () => {
    // The Epsilon Indi system page shows eps Ind A's coordinates; its field is centred on eps Ind B
    // (~402" away, outside the 0.15° cutout), so the link must say whose images it opens.
    expect(fieldLinkLabel({ name: 'Epsilon Indi B', synthetic: false })).toBe('See Epsilon Indi B in SPHEREx images →');
  });

  it('falls back to the generic wording when the manifest gives no field name', () => {
    expect(fieldLinkLabel({ name: '', synthetic: false })).toBe('See it in SPHEREx images →');
    expect(fieldLinkLabel({ name: '   ', synthetic: false })).toBe('See it in SPHEREx images →');
    expect(fieldLinkLabel(undefined)).toBe('See it in SPHEREx images →');
  });

  it('never calls a synthetic field SPHEREx images', () => {
    expect(fieldLinkLabel({ name: 'Epsilon Indi B', synthetic: true })).toBe(
      'See the synthetic demo field (not SPHEREx) →',
    );
    expect(fieldLinkLabel(undefined, true)).toBe('See the synthetic demo field (not SPHEREx) →');
  });
});
