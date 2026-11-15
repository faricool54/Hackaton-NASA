// Snapshot of pipeline/errante/config/fields.toml, checked 2026-11-14.
// Sesame/SIMBAD CfA astrometry propagated to each mean SPHEREx epoch.
// These are search presets, not completed R05 validations or detected sources.
// catalogName: the SIMBAD name the object card looks up (recorded in pipeline/tests/fixtures/ws3/context/).
export const SHOWCASE_TARGETS = [
  { name: "Barnard's Star", catalogName: "Barnard's Star", ra: 269.44623, dec: 4.76870, mjd: 61104, detector: 2,
    fieldId: 'barnards-star', testCase: 'Motion test' },
  { name: 'Epsilon Indi B', catalogName: 'eps Ind B', ra: 331.09665, dec: -56.80066, mjd: 61042, detector: 2,
    fieldId: 'eps-indi-b', testCase: 'Motion test' },
  { name: 'WISE 0855−0714', catalogName: 'WISE J085510.83-071442.5', ra: 133.75980, dec: -7.24219, mjd: 61035, detector: 6,
    fieldId: 'wise-0855', testCase: 'Motion test' },
  { name: 'RW Aurigae', catalogName: 'RW Aur', ra: 76.95659, dec: 30.40129, mjd: 61107, detector: 2,
    fieldId: 'rw-aurigae', testCase: 'Brightness test' },
  { name: 'R Draconis', catalogName: 'R Dra', ra: 248.16723, dec: 66.75502, mjd: 61115, detector: 2,
    fieldId: 'r-draconis', testCase: 'Brightness test' },
];

export type ShowcaseTarget = typeof SHOWCASE_TARGETS[number];
