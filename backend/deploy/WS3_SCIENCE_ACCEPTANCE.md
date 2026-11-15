# WS3 spectral interpretation and LC24 integration — 2026-11-15

Science implementation: #102 and reviewed safeguards #110, built on faricool54's #93/#94/#97. RW Aur identity is Farid's #101,
preserved unchanged. This record describes local technical acceptance; it is not human R05 approval.

## Scientific products

Both packaged light curves were rebuilt with `errante_api.lightcurve_build`, the original presets,
1000 bootstrap samples and 999 visit permutations. Both products are ready. RW Aur used fresh SIA
with `provenance.partial=false`; R Dra used the explicitly declared archived search after IRSA timed out
and has `partial=true`, `stale_search=true`, `truncated_search=false`. Its completeness is not newly certified. Point values, matched pairs and period are exactly equal
to the previous bundles; the LC24/#106 changes affect only target/control scatter summaries and explanatory notes. The comparison
control uses the same >=3-point rule; the aperture-pair noise-floor advice is absent from wing photometry.

| Product | Measurements / usable | Scatter summary after LC24 |
|---|---|---|
| RW Aur | 56 / 10 | 10 endpoints are five two-exposure bins: summary.n=0, scatter_over_control=null; all points/pairs retained |
| R Dra | 538 / 450 | Per-detector summary n: 64, 51, 74, 56, 80, 91; wing/aperture scatter ratios remain null |

The separate real spectral fixture contains 40 native FITS measurements of epsilon Indi B, 35 usable.
Its search used the declared archived snapshot after IRSA timeouts. No temperature was reported:
quality/coverage/censoring or poor single-blackbody fits rejected each sampled season group.

## API and browser

- Existing contract 0.7.0 and `SpectrumResponse.notes`; no WS5 edit or new public field.
- Model limits, descriptive IR colour and conditional colour-temperature/unknown states are visible.
  The reviewed range includes a declared +/-10% temperature modelling allowance; any saturated season is rejected.
  This is not stellar effective temperature, visible RGB, a radius or a physical 3D reconstruction.
- Cube surface brightness without source/background separation and errors stays unsupported for temperature.
- Transitive science source changes invalidate scientific-response cache keys; image-job keys are unchanged.
- Edge headless, 1360x980, real local API and current frontend: epsilon Indi B cube returned 100/102 usable
  points and visibly stated `colour temperature unknown (unsupported_product)` and the effective-temperature
  caveat. RW Aur's curve displayed the two-exposure scatter warning. No browser page errors.
- Backend tests replay the real L2 fixture through the adapter and verify unknown temperatures reach notes.

## Verification and publication

Full `python scripts/dev.py check`: **1103 Python tests passed, 51 skipped; 376 frontend tests passed**,
lint/schema/product validation/typecheck/build green. Skipped network tests are not claimed as executed.
The real cube/browser extraction and the two real light-curve rebuilds above were separate explicit checks.

Production publication is coordinated with Farid in [issue #100](https://github.com/faricool54/Hackaton-NASA/issues/100).
This local acceptance record does not assert that the API integration is already deployed.
