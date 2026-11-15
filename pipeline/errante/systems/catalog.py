"""Curated 3D systems for the challenge test targets (WS7).

WS7-2 (2026-11-14): every value below was checked against the NASA Exoplanet
Archive, SIMBAD (CfA mirror), Gaia DR3, VizieR and the cited papers. The
fetchers in ``systems.sources`` reproduce the archive queries and the
``network`` tests in ``tests/test_systems.py`` re-run them. A ``Fact`` is
``verified=True`` only when its value was found in the cited source; model
estimates and derived values say so in their label and source.

Rule (WS7 V13, docs/VISION.md): a value published for this object (measured or
model, labelled as such) is drawn; a value no source gives is not. Such a field
stays ``None`` (the viewer shows it as unknown: grey colour, fixed marker size)
and ``systems.measured`` adds a provenance note saying why. Facts measured by
SPHEREx and the WS3 object-context cross-checks are attached by
``systems.measured`` from ``targets.toml`` and the frozen snapshots in
``inputs/objects/``.

The one fully *synthetic* system (``demo-ecliptic-orbits``) belongs to the
synthetic demo field and is labelled as such.
"""

from __future__ import annotations

from datetime import UTC, datetime

from .. import __version__
from ..models import (
    Appearance,
    Body,
    Fact,
    Orbit,
    Provenance,
    SkyCoord,
    SpaceMotion,
    SystemModel,
    Variability,
)

R_SUN_KM = 695_700.0
R_JUP_KM = 71_492.0
R_EARTH_KM = 6_371.0
M_SUN_KG = 1.989e30
M_JUP_KG = 1.898e27
M_EARTH_KG = 5.972e24
M_JUP_MSUN = M_JUP_KG / M_SUN_KG
AU_KM = 1.495978707e8
DAYS_PER_YEAR = 365.25

PHASE_NOTE = "Orbital and pulsation phases are arbitrary (no epoch): positions are not predictions for a real date."

VERIFIED_NOTE = (
    "Values checked on 2026-11-14 against the NASA Exoplanet Archive, SIMBAD (CfA mirror), Gaia DR3, VizieR and the "
    "cited papers (tasks/WS7-3d-systems.md, WS7-2). Facts still marked 'unverified' are estimates no source states. "
    "The 'seen by SPHEREx' facts were copied from the validation records (docs/validation/; AI analysis with an "
    "independent second analysis, human review pending), not from that catalog cross-check."
)

REAL_REPRESENTATION = (
    "3D model drawn from published catalog and literature values, not measured by SPHEREx unless a fact says "
    "'seen by SPHEREx' (each fact shows its source) - not an image. What no source gives is not drawn: an unknown "
    "temperature is drawn grey and an unknown size at a fixed marker size, not to scale. Sizes and distances may be "
    "exaggerated for visibility."
)

GAIA_DR3 = "Gaia DR3"
EXOPLANET_ARCHIVE = "NASA Exoplanet Archive, pscomppars"


def kepler_period_days(a_au: float, total_mass_msun: float) -> float:
    """Kepler's third law: P[yr]^2 = a[AU]^3 / M[Msun]."""
    return (a_au**3 / total_mass_msun) ** 0.5 * DAYS_PER_YEAR


def kepler_a_au(period_days: float, total_mass_msun: float) -> float:
    return (total_mass_msun * (period_days / DAYS_PER_YEAR) ** 2) ** (1 / 3)


def _demo_field_center(field_id: str) -> SkyCoord:
    from ..synthetic import DEMO_FIELDS

    spec = next(s for s in DEMO_FIELDS if s.id == field_id)
    return SkyCoord(ra=spec.ra, dec=spec.dec)


def _fact(label: str, value: str, unit: str | None = None, source: str | None = None) -> Fact:
    """A value nobody checked (synthetic systems, or an estimate no source states)."""
    return Fact(label=label, value=value, unit=unit, source=source, verified=False)


def _vfact(label: str, value: str, unit: str | None, source: str) -> Fact:
    """A value found in ``source`` during WS7-2 (2026-11-14)."""
    return Fact(label=label, value=value, unit=unit, source=source, verified=True)


def _provenance(*, synthetic: bool, notes: list[str]) -> Provenance:
    return Provenance(
        pipeline_version=__version__,
        built_at=datetime.now(UTC),
        synthetic=synthetic,
        data_releases=["synthetic"] if synthetic else [],
        notes=notes,
    )


# --- Barnard's Star: nearest single star to the Sun, four small planets -------

BJD_MINUS_MJD = 2400000.5  # MJD = JD - 2400000.5; BJD_TDB vs UTC (~69 s) is negligible at this precision

# Mean anomaly at the time of inferior conjunction of a circular orbit drawn with i = Omega = omega = 0
# (M5). The WS7 scene maps the AU frame (x, y, z-up) to three.js (x, z, -y), and the default camera
# looks from scene +z, so AU -y = scene +z is "toward Earth" (the line of sight projected on the orbit
# plane; the inclination is unknown). E = M = 270 deg puts the planet at (0, -a, 0): in front of the star.
CONJUNCTION_MEAN_ANOMALY_DEG = 270.0

# Dates at which the orbit notes quote the 1-sigma phase spread: DR1 start and the last QR3 frame
# (frontend/src/three/spherexCoverage.ts DR1_START_MJD, QR3_LAST_MJD).
PHASE_SPREAD_DATES = ((60789.75, "2025-04-24"), (61318.0, "2026-10-05"))


def phase_sigma_deg(
    t_mjd: float, t0_mjd: float, t0_err_days: float, period_days: float, period_err_days: float
) -> float:
    """First-order 1-sigma orbital phase spread (deg) at ``t_mjd`` from a published t0 and P.

    sigma_phi = sqrt(sigma_t0^2 + N^2 sigma_P^2) / P with N = (t - t0) / P (linear propagation; Taylor
    1997; Zellem et al. 2020, PASP 132, 054401). The t0-P covariance is not published and is ignored.
    """
    n = (t_mjd - t0_mjd) / period_days
    return 360.0 * ((t0_err_days**2 + (n * period_err_days) ** 2) ** 0.5) / period_days


def barnards_star() -> SystemModel:
    star_src = f"{EXOPLANET_ARCHIVE} (González Hernández et al. 2024, A&A 690, A79)"
    planet_src = f"{EXOPLANET_ARCHIVE} (Basant et al. 2025, ApJL 982, L1)"
    basant_t3 = "Basant et al. 2025, ApJL 982, L1, Table 3 (arXiv:2503.08095)"
    gaia = f"{GAIA_DR3} 4472832130942575872"
    planets = [
        # (id, name, period_days, period_err_days, min_mass_earth, a_au, archive radius estimate [R_earth],
        #  t0 [BJD], t0 text as published, t0 1-sigma [d] = the larger side of an asymmetric error)
        # Periods, t0 and their errors: Basant et al. 2025 Table 3 (t0 is listed there as BJD - 2450000).
        ("barnard-d", "Barnard d", 2.3402, 0.0003, 0.263, 0.0188, 0.694, 2460243.70, "+0.08/−0.07", 0.08),
        ("barnard-b", "Barnard b", 3.1542, 0.0004, 0.299, 0.0229, 0.720, 2460243.38, "± 0.09", 0.09),
        ("barnard-c", "Barnard c", 4.1244, 0.0006, 0.335, 0.0274, 0.743, 2460242.92, "± 0.10", 0.10),
        ("barnard-e", "Barnard e", 6.7392, 0.0028, 0.193, 0.0381, 0.637, 2460245.30, "+0.37/−0.36", 0.37),
    ]
    bodies = [
        Body(
            id="barnards-star",
            name="Barnard's Star",
            kind="star",
            description="A small, cool red dwarf. It moves faster across our sky than any other star.",
            radius_km=0.185 * R_SUN_KM,
            mass_kg=0.162 * M_SUN_KG,
            teff_k=3195,
            rotation_period_hours=145 * 24,  # Toledo-Padrón et al. 2019: 145 ± 15 d
            spectral_type="M4V",
            appearance=Appearance(model="star"),
            facts=[
                _vfact("Spectral type", "M4V", None, "SIMBAD (Kirkpatrick et al. 1991)"),
                _vfact("Temperature", "3195 ± 28", "K", star_src),
                _vfact("Mass", "0.162 ± 0.007", "solar masses", star_src),
                _vfact("Radius", "0.185 ± 0.006", "solar radii", star_src),
                _vfact("Distance", "1.828", "pc", f"{gaia} (parallax 546.976 ± 0.040 mas)"),
                _vfact("Proper motion", "10.39", "arcsec/yr", gaia),
                _vfact("Radial velocity", "−110.47 ± 0.13", "km/s", gaia),
                _vfact(
                    "Rotation period",
                    "145 ± 15",
                    "days",
                    "Toledo-Padrón et al. 2019, MNRAS 488, 5145 (activity indices + 15 yr of photometry)",
                ),
            ],
        )
    ]
    for pid, name, period, period_err, mmin, a_au, r_est, t0_bjd, t0_text, t0_err in planets:
        t0_mjd = round(t0_bjd - BJD_MINUS_MJD, 5)
        spread = ", ".join(
            f"±{phase_sigma_deg(t, t0_mjd, t0_err, period, period_err):.0f}° on {iso}" for t, iso in PHASE_SPREAD_DATES
        )
        bodies.append(
            Body(
                id=pid,
                name=name,
                kind="planet",
                description=(
                    "A small planet found by radial velocity (minimum mass well below Earth's); probably rocky. "
                    "Too hot for liquid water."
                ),
                radius_km=r_est * R_EARTH_KM,  # archive estimate from the mass: not transiting, radius not measured
                mass_kg=mmin * M_EARTH_KG,  # minimum mass (M sin i)
                orbit=Orbit(
                    parent="barnards-star",
                    semi_major_axis_au=a_au,
                    period_days=period,
                    mean_anomaly_deg=CONJUNCTION_MEAN_ANOMALY_DEG,
                    epoch_mjd=t0_mjd,
                    note=(
                        "Drawn circular: the fitted eccentricities (d 0.04, b 0.03, c 0.08, e 0.04; Basant et al. "
                        "2025 via the NASA Exoplanet Archive) are consistent with zero within 2σ. A circular drawing "
                        "can misplace the planet along its orbit by up to 2e rad (3–9°); the phase arc does not "
                        "include that. Orbit inclination unknown (radial-velocity detection). "
                        f"Phase: the planet is drawn in front of the star (on the 'toward Earth' arrow) at "
                        f"t0 = BJD {t0_bjd:.2f} {t0_text} (Basant et al. 2025, Table 3), read as the time of "
                        "inferior conjunction as used by juliet/RadVel (tc); the paper text says periastron. "
                        f"1-sigma phase spread from t0 and P ({period} ± {period_err} d): {spread} (linear "
                        "propagation; the t0-P covariance is not published and is ignored). The sense of motion "
                        "on the sky is unknown: drawn counter-clockwise seen from above."
                    ),
                ),
                appearance=Appearance(model="rocky"),
                facts=[
                    _vfact("Orbital period", f"{period} ± {period_err}", "days", basant_t3),
                    _vfact(
                        "Reference time t0",
                        f"{t0_bjd:.2f} {t0_text}",
                        "BJD",
                        f"{basant_t3}, listed as BJD − 2450000. Verified for the value only: the paper calls t0 "
                        "the time of periastron, the fitting code (juliet, RadVel 'tc') the time of conjunction; "
                        "see the orbit note",
                    ),
                    _vfact("Minimum mass", f"{mmin}", "Earth masses", planet_src),
                    _vfact("Orbit size", f"{a_au}", "AU", planet_src),
                    _vfact(
                        "Radius (model estimate)",
                        f"~{r_est:.2f}",
                        "Earth radii",
                        f"{EXOPLANET_ARCHIVE}: calculated from the mass, not measured (no transits)",
                    ),
                ],
            )
        )
    return SystemModel(
        id="barnards-star",
        name="Barnard's Star system",
        description="Challenge test target: the fastest-moving star in our sky, with four small planets.",
        tags=["test-target", "proper-motion", "exoplanets"],
        center=SkyCoord(ra=269.44850252543836, dec=4.739420051112412),
        motion=SpaceMotion(
            distance_pc=1.8282,
            parallax_mas=546.976,
            pm_ra_cosdec_mas_yr=-801.551,
            pm_dec_mas_yr=10362.394,
            radial_velocity_km_s=-110.47,
            epoch="J2016.0",  # Gaia DR3 reference epoch
        ),
        field_id="barnards-star",
        bodies=bodies,
        representation_note=REAL_REPRESENTATION,
        provenance=_provenance(
            synthetic=False,
            notes=[
                VERIFIED_NOTE,
                "Planet phases follow the t0 and periods of Basant et al. 2025 (Table 3), read as times of inferior "
                "conjunction: a position on a real date is a prediction with the 1-sigma spread given in each orbit "
                "note. The star's rotational phase is not known.",
                "Planet masses are minimum masses (M sin i) and planet radii are estimates: radial velocity measures "
                "neither the inclination nor the size.",
            ],
        ),
    )


# --- Epsilon Indi: K dwarf + imaged giant planet + brown-dwarf binary ---------


def epsilon_indi() -> SystemModel:
    m_a = 0.80  # Sanghi et al. 2026 via the NASA Exoplanet Archive
    m_ba, m_bb = 66.92 * M_JUP_MSUN, 53.25 * M_JUP_MSUN  # Chen et al. 2022, Table 4
    host_src = f"{EXOPLANET_ARCHIVE} (Sanghi et al. 2026, AJ 172, 115)"
    chen = "Chen et al. 2022, AJ 163, 288 (Table 4)"
    gaia = f"{GAIA_DR3} 6412595290592307840"
    return SystemModel(
        id="epsilon-indi",
        name="Epsilon Indi system",
        description="Challenge test target: an orange dwarf star, a cold giant planet and a pair of brown dwarfs.",
        tags=["test-target", "brown-dwarf", "binary", "exoplanets"],
        center=SkyCoord(ra=330.8724078795965, dec=-56.79725466122902),  # Eps Ind A
        motion=SpaceMotion(
            distance_pc=3.638,
            parallax_mas=274.843,
            pm_ra_cosdec_mas_yr=3966.661,
            pm_dec_mas_yr=-2536.192,
            radial_velocity_km_s=-40.43,
            epoch="J2016.0",  # Gaia DR3 reference epoch
        ),
        field_id="eps-indi-b",  # WS3 field centred on the unresolved Ba+Bb pair (A is ~402 arcsec west)
        bodies=[
            Body(
                id="eps-indi-a",
                name="Epsilon Indi A",
                kind="star",
                description="An orange dwarf star, a bit smaller and cooler than the Sun.",
                radius_km=0.713 * R_SUN_KM,
                mass_kg=m_a * M_SUN_KG,
                teff_k=4700,
                spectral_type="K5V",
                appearance=Appearance(model="star"),
                facts=[
                    _vfact("Spectral type", "K5V", None, "SIMBAD"),
                    _vfact("Temperature", "4700 ± 65", "K", host_src),
                    _vfact("Mass", "0.80 ± 0.02", "solar masses", host_src),
                    _vfact("Radius", "0.713", "solar radii", host_src),
                    _vfact("Distance", "3.638", "pc", f"{gaia} (parallax 274.84 mas)"),
                ],
            ),
            Body(
                id="eps-indi-ab",
                name="Epsilon Indi Ab",
                kind="planet",
                description="A cold giant planet photographed directly by JWST.",
                radius_km=1.13 * R_JUP_KM,  # archive estimate from the mass, not measured
                mass_kg=6.5 * M_JUP_KG,
                teff_k=275,
                orbit=Orbit(
                    parent="eps-indi-a",
                    semi_major_axis_au=15.76,
                    period_days=25450.0,
                    eccentricity=0.25,
                    note=(
                        "Fit by Sanghi et al. 2026 (JWST imaging + radial velocity + Hipparcos-Gaia). The measured "
                        "orientation (inclination ~102°) and the orbital phase are not modelled. The first JWST fit "
                        "(Matthews et al. 2024) gave a wider orbit (~28 AU, e ~0.4)."
                    ),
                ),
                appearance=Appearance(model="gas_giant"),
                facts=[
                    _vfact("Mass", "6.5 (+0.7/−0.6)", "Jupiter masses", host_src),
                    _vfact("Orbit size", "15.8 (+1.7/−1.4)", "AU", host_src),
                    _vfact("Orbital period", "~70 (+12/−9)", "years", f"{host_src}: 25450 (+4387/−3302) days"),
                    _vfact("Eccentricity", "0.25 ± 0.09", None, host_src),
                    _vfact("Temperature", "~275", "K", "Matthews et al. 2024, Nature 633, 789 (JWST)"),
                    _vfact(
                        "Radius (model estimate)",
                        "~1.1",
                        "Jupiter radii",
                        f"{EXOPLANET_ARCHIVE}: calculated from the mass, not measured",
                    ),
                ],
            ),
            Body(
                id="eps-indi-ba",
                name="Epsilon Indi Ba",
                kind="brown_dwarf",
                description="A brown dwarf: too heavy to be a planet, too light to shine like a star.",
                radius_km=None,  # no published radius: size unknown, not drawn to scale
                mass_kg=m_ba * M_SUN_KG,
                teff_k=1300,
                spectral_type="T1",
                # Simplification: Ba orbits A directly (the Ba+Bb barycenter does in reality).
                orbit=Orbit(
                    parent="eps-indi-a",
                    semi_major_axis_au=1460.0,
                    period_days=round(kepler_period_days(1460.0, m_a + m_ba + m_bb), 0),
                    quality="assumed",
                    note="Circle at the projected separation; period from Kepler's law. The A–B orbit is not known.",
                ),
                appearance=Appearance(model="brown_dwarf"),
                facts=[
                    _vfact("Spectral type", "T1", None, f"SIMBAD; {chen}"),
                    _vfact("Mass", "66.92 ± 0.36", "Jupiter masses", chen),
                    _vfact(
                        "Temperature (model-dependent)",
                        "~1300",
                        "K",
                        "King et al. 2010 (evolutionary models), adopted by Chen et al. 2022",
                    ),
                    _vfact(
                        "Separation from A",
                        "~1460 (projected)",
                        "AU",
                        "Scholz et al. 2003, A&A 398, L29; Gaia DR3 positions",
                    ),
                ],
            ),
            Body(
                id="eps-indi-bb",
                name="Epsilon Indi Bb",
                kind="brown_dwarf",
                description="The colder twin of Ba; the two orbit each other every ~11 years.",
                radius_km=None,  # no published radius: size unknown, not drawn to scale
                mass_kg=m_bb * M_SUN_KG,
                teff_k=900,
                spectral_type="T6",
                orbit=Orbit(
                    parent="eps-indi-ba",
                    semi_major_axis_au=2.4058,
                    period_days=round(11.0197 * DAYS_PER_YEAR, 2),
                    eccentricity=0.5404,
                    note="Fitted orbit (Chen et al. 2022); its orientation on the sky (i ≈ 77°) is not modelled.",
                ),
                appearance=Appearance(model="brown_dwarf"),
                facts=[
                    _vfact("Spectral type", "T6", None, f"SIMBAD; {chen}"),
                    _vfact("Mass", "53.25 ± 0.29", "Jupiter masses", chen),
                    _vfact(
                        "Temperature (model-dependent)",
                        "~900",
                        "K",
                        "King et al. 2010 (evolutionary models), adopted by Chen et al. 2022",
                    ),
                    _vfact("Orbital period around Ba", "11.0197 ± 0.0076", "years", chen),
                    _vfact("Orbit size", "2.406", "AU", chen),
                    _vfact("Eccentricity", "0.540", None, chen),
                ],
            ),
        ],
        representation_note=REAL_REPRESENTATION,
        provenance=_provenance(
            synthetic=False,
            notes=[
                VERIFIED_NOTE,
                PHASE_NOTE,
                "Simplified hierarchy: Ba orbits A and Bb orbits Ba (no barycenters).",
                "Ba and Bb have no published radius: their size is unknown and they are drawn at a fixed marker "
                "size, not to scale. The radius of Ab is the archive's estimate from its mass.",
                "Gaia DR3 measures Ba+Bb as one unresolved source (RUWE 4.3): its parallax is not used for distance. "
                "SPHEREx also sees Ba+Bb as one source: they are never more than about 1″ apart (orbit semi-major "
                "axis 2.4 AU, 0.66″ at 3.64 pc; eccentricity 0.54), and a SPHEREx pixel is 6.15″.",
            ],
        ),
    )


# --- WISE 0855-0714: the coldest known brown dwarf, alone ---------------------


def wise_0855() -> SystemModel:
    k21 = "Kirkpatrick et al. 2021, ApJS 253, 7"
    l24 = "Luhman et al. 2024, AJ 167, 5 (JWST)"
    return SystemModel(
        id="wise-0855",
        name="WISE 0855−0714",
        description="Challenge test target: the coldest known brown dwarf, near the freezing point of water.",
        tags=["test-target", "brown-dwarf", "proper-motion"],
        # Kirkpatrick et al. 2021 position at its astrometric epoch (not in Gaia: too faint).
        center=SkyCoord(ra=133.780984, dec=-7.243932),
        motion=SpaceMotion(
            distance_pc=2.28,
            parallax_mas=439.0,
            pm_ra_cosdec_mas_yr=-8123.7,
            pm_dec_mas_yr=673.2,
            epoch="J2016.67",  # Kirkpatrick et al. 2021 astrometric epoch, MJD 57633.39
        ),
        field_id="wise-0855",
        bodies=[
            Body(
                id="wise-0855",
                name="WISE 0855−0714",
                kind="brown_dwarf",
                description="A free-floating brown dwarf so cold that water could condense in its atmosphere.",
                radius_km=1.0 * R_JUP_KM,
                mass_kg=None,  # only a 3-10 M_Jup model range is published: no single value is drawn
                teff_k=285,
                spectral_type="Y4 (approx.)",
                appearance=Appearance(model="brown_dwarf"),
                facts=[
                    _vfact("Spectral type", "~Y4 (Kirkpatrick et al. 2021); SIMBAD lists Y2", None, f"{k21}; {l24}"),
                    _vfact("Temperature", "~250–300 (best fit 285)", "K", f"{l24}; model dependent"),
                    _vfact("Distance", "~2.28", "pc", f"{k21} (parallax 439.0 ± 2.4 mas)"),
                    _vfact("Proper motion", "~8.15", "arcsec/yr", k21),
                    _vfact("Mass (evolutionary models)", "3–10", "Jupiter masses", f"{l24}; for ages of 1–10 Gyr"),
                    _vfact("Radius (evolutionary models)", "~1", "Jupiter radii", f"{l24} (0.10–0.11 solar radii)"),
                ],
            )
        ],
        representation_note=REAL_REPRESENTATION,
        provenance=_provenance(
            synthetic=False,
            notes=[
                VERIFIED_NOTE,
                "The challenge gives 133.79513, −7.24515: the WISE All-Sky position at epoch 2010.34 (MJD 55320.4). "
                "The object moves ~8.2 arcsec per year, so positions must be propagated to the date of each image.",
            ],
        ),
    )


# --- R Draconis: a pulsating Mira variable --------------------------------------

# The viewer draws R Dra's pulsation on two clocks. Free-running: a sine at the catalog (GCVS) period
# with an arbitrary phase. Dataset time: the AAVSO VSX ephemeris of maximum light, held with its
# timing band in the WS7 table frontend/src/three/ephemerides.ts (MIRA_EPHEMERIDES); the contract has
# no field for a Variability epoch. tests/test_systems.py checks that these values match that table.
RDRA_GCVS_PERIOD_DAYS = 245.6
RDRA_VSX_EPOCH_HJD = 2457370.00  # epoch of maximum light (V)
RDRA_VSX_PERIOD_DAYS = 246.12
RDRA_VSX_RISE_PERCENT = 45  # rise from minimum to maximum, % of the period
RDRA_PULSATION_NOTE = (
    "The pulsation is drawn as a brightness change only: the radius is drawn constant, because its size change "
    "is not measured. It runs on two clocks. Free-running: the brightness animation is a sine wave at the GCVS "
    f"period ({RDRA_GCVS_PERIOD_DAYS} d) spanning the V-band range, with an arbitrary phase (no epoch): it is not "
    "a prediction for a real date. Dataset time: inside the SPHEREx window R Dra's phase is dated by the V "
    "maxima measured by AAVSO in 2025–2026 (MJD 60811.4, 61046.5 and 61304.3; linear phase between them, "
    "±3 d band; docs/validation/r-draconis.md), and outside it by the AAVSO VSX ephemeris (epoch of maximum "
    f"HJD {RDRA_VSX_EPOCH_HJD:.2f}, P = {RDRA_VSX_PERIOD_DAYS} d; ±9.0 d band, the RMS of the O−C of those "
    f"maxima), on an asymmetric curve that rises in {RDRA_VSX_RISE_PERCENT} % of the cycle (WS7 table "
    "frontend/src/three/ephemerides.ts). Both are "
    "catalog V-band drawings, not measured by SPHEREx: real Mira cycles change from cycle to cycle, and the "
    "amplitude is much smaller in the infrared: offline measurements on the SPHEREx FITS files give 0.5–1.3 mag "
    "peak-to-peak at 0.74–5.0 µm and a ~260-day cycle in 2025–2026 (docs/validation/r-draconis.md). The "
    "animation is not that light curve, and the SPHEREx images in this app do not show it. The R Draconis field "
    "page shows the precomputed SPHEREx light curve (WS3/WS4 product) in live API mode."
)


def r_draconis() -> SystemModel:
    gcvs = "GCVS 5.1 (Samus et al. 2017)"
    # Not drawn (V13): no dynamical mass and no single radius are published for R Dra, and its temperature
    # changes with the pulsation (a single value would be a pick inside ~2000-3300 K). The fields stay None;
    # systems.measured explains them in a provenance note.
    return SystemModel(
        id="r-draconis",
        name="R Draconis",
        description="Challenge test target: a giant star that swells and fades every ~8 months.",
        tags=["test-target", "variable"],
        center=SkyCoord(ra=248.1673783672889, dec=66.75500674547219),
        motion=SpaceMotion(
            distance_pc=792.0,
            parallax_mas=1.2509,
            pm_ra_cosdec_mas_yr=-20.643,
            pm_dec_mas_yr=6.149,
            radial_velocity_km_s=-132.8,
            epoch="J2016.0",  # Gaia DR3 reference epoch
        ),
        field_id="r-draconis",  # WS3 field (config/fields.toml)
        bodies=[
            Body(
                id="r-draconis",
                name="R Draconis",
                kind="star",
                description="A Mira variable: an old red giant whose visible brightness changes by hundreds of times.",
                radius_km=None,  # not measured: size unknown, not drawn to scale
                mass_kg=None,  # no dynamical mass
                teff_k=None,  # changes with the pulsation: colour unknown
                spectral_type="M5e–M9eIII",
                variability=Variability(
                    kind="pulsation", period_days=RDRA_GCVS_PERIOD_DAYS, amplitude_mag=6.5, band="V"
                ),
                appearance=Appearance(model="star"),
                facts=[
                    _vfact("Variable type", "Mira", None, f"{gcvs}; AAVSO VSX"),
                    _vfact("Spectral type", "M5e–M9eIII", None, gcvs),
                    _vfact("Period", "~245.6", "days", f"{gcvs} (AAVSO VSX: 246.1 days)"),
                    _vfact("Visual range", "6.7–13.2", "mag (V)", f"{gcvs}; AAVSO VSX"),
                    _vfact(
                        "Temperature (changes with the pulsation)",
                        "~2000–3300",
                        "K",
                        "van Belle et al. 2002, AJ 124, 1706 (2034 ± 139 K at phase 0.83); "
                        "McDonald et al. 2012, MNRAS 427, 343 (3336 K, SED fit)",
                    ),
                    _vfact("Distance", "~790", "pc", "Bailer-Jones et al. 2021 (Gaia EDR3)"),
                ],
            )
        ],
        representation_note=REAL_REPRESENTATION,
        provenance=_provenance(
            synthetic=False,
            notes=[
                VERIFIED_NOTE,
                RDRA_PULSATION_NOTE,  # replaces PHASE_NOTE: R Dra has no orbit, and its phase is dated in Dataset time
                "Radial velocity −132.8 km/s from SIMBAD (Wilson 1953); optical lines of a Mira move with the pulsation.",
            ],
        ),
    )


# --- RW Aurigae: young binary with a disk ----------------------------------------


def rw_aurigae() -> SystemModel:
    kurtovic = "Kurtovic et al. 2024, A&A (arXiv:2407.18828)"
    dodin20 = "Dodin et al. 2020, MNRAS 497, 4527"
    m_a, m_b = 1.238, 0.995  # dynamical masses, Kurtovic et al. 2024
    return SystemModel(
        id="rw-aurigae",
        name="RW Aurigae",
        description="Challenge test target: a young binary star whose dusty disk causes deep dimming events.",
        tags=["test-target", "variable", "binary", "young-star"],
        center=SkyCoord(ra=76.9565443110343, dec=30.401316149887936),  # RW Aur A, Gaia DR3 156430817820015232
        motion=SpaceMotion(
            distance_pc=156.1,
            parallax_mas=6.406,
            pm_ra_cosdec_mas_yr=2.641,
            pm_dec_mas_yr=-27.398,
            radial_velocity_km_s=15.0,
            epoch="J2016.0",  # Gaia DR3 reference epoch
        ),
        field_id="rw-aurigae",  # WS3 field (config/fields.toml)
        bodies=[
            Body(
                id="rw-aur-a",
                name="RW Aurigae A",
                kind="star",
                description="A T Tauri star: a newborn star still feeding from its disk.",
                radius_km=1.3 * R_SUN_KM,
                mass_kg=m_a * M_SUN_KG,
                teff_k=4900,
                spectral_type="K1–K4 (T Tauri)",
                variability=Variability(kind="irregular", amplitude_mag=4.4, band="V"),
                appearance=Appearance(model="star"),
                facts=[
                    _vfact("Type", "Classical T Tauri star", None, "SIMBAD; AAVSO VSX"),
                    _vfact(
                        "Distance",
                        "156.1",
                        "pc",
                        "Gaia DR3 parallax of B (6.406 ± 0.044 mas), adopted for the system by Kurtovic et al. 2024",
                    ),
                    _vfact("Mass (dynamical)", "1.24", "solar masses", f"{kurtovic}, gas disk rotation"),
                    _vfact("Temperature", "4900", "K", "Testi et al. 2022, A&A 663, A98"),
                    _vfact("Visual range (A+B)", "9.2–13.6", "mag (V)", "AAVSO VSX"),
                    _vfact(
                        "Dimming events",
                        "~2 mag since 2010; A alone up to ~5 mag in 2014–2018",
                        None,
                        "Rodriguez et al. 2013, AJ 146, 112; 2016, AJ 151, 29; Dodin et al. 2019, MNRAS 482, 5524",
                    ),
                    _fact(
                        "Radius (derived from the catalog luminosity)",
                        "~1.3",
                        "solar radii",
                        "derived by WS7: Herczeg & Hillenbrand 2014, ApJ 786, 97 list 1.20 solar radii at their "
                        "assumed 140 pc; a radius from the luminosity at a fixed temperature scales with the distance "
                        "(L scales as d², and by Stefan–Boltzmann R as the square root of L), so at the Gaia DR3 "
                        "distance of 156.1 pc it is "
                        "1.20 × 156.1 / 140 = 1.34. Catalog, not measured by SPHEREx; uncertain",
                    ),
                ],
            ),
            Body(
                id="rw-aur-a-disk",
                name="Disk around A",
                kind="disk",
                description="Gas and dust left over from the star's birth; small, possibly trimmed by a past close pass of companion B.",
                radius_km=19 * AU_KM,  # dust disk (R90%)
                orbit=None,
                appearance=Appearance(model="disk"),
                facts=[
                    _vfact("Dust disk radius", "~19", "AU", f"{kurtovic} (ALMA, 90% of the flux)"),
                    _vfact("Gas (CO) disk radius", "~58", "AU", "Rodriguez et al. 2018, ApJ 859, 150"),
                ],
            ),
            Body(
                id="rw-aur-b",
                name="RW Aurigae B",
                kind="star",
                description="The companion star, about 1.5 arcsec away on the sky. It also has irregular dips.",
                radius_km=1.5 * R_SUN_KM,
                mass_kg=m_b * M_SUN_KG,
                teff_k=4150,
                spectral_type="K6.5 (T Tauri)",
                variability=Variability(kind="irregular", amplitude_mag=1.3, band="V"),
                orbit=Orbit(
                    parent="rw-aur-a",
                    semi_major_axis_au=258.0,
                    period_days=round(2773 * DAYS_PER_YEAR, 0),
                    eccentricity=0.787,
                    inclination_deg=129.8,
                    ascending_node_deg=73.8,
                    arg_periapsis_deg=42.3,
                    note=(
                        "Best-fit orbit of Kurtovic et al. 2024 (a derived from their periastron 55 AU and e). Very "
                        "uncertain: period 2773 (+27100/−366) years and an unbound orbit is not ruled out."
                    ),
                ),
                appearance=Appearance(model="star"),
                facts=[
                    _vfact("Mass (dynamical)", "1.00", "solar masses", f"{kurtovic}, gas disk rotation"),
                    _vfact("Temperature", "4100–4200", "K", dodin20),
                    _vfact("Radius", "~1.5", "solar radii", dodin20),
                    _vfact("Spectral type", "K6.5", None, "Herczeg & Hillenbrand 2014, ApJ 786, 97"),
                    _vfact("Projected separation", "~1.5", "arcsec", f"{kurtovic} (1.494″, ALMA 2017)"),
                    _vfact("Projected distance from A", "~233", "AU", kurtovic),
                    _vfact("Orbital period", "~2800 (+27100/−370)", "years", kurtovic),
                    _vfact("Eccentricity", "~0.79", None, kurtovic),
                    _vfact("Dips", "up to 1.3 mag, about a day long", None, dodin20),
                ],
            ),
        ],
        representation_note=REAL_REPRESENTATION,
        provenance=_provenance(
            synthetic=False,
            notes=[
                VERIFIED_NOTE,
                PHASE_NOTE,
                "The disk body has no orbit: the UI draws it centred on its host (rw-aur-a).",
                "SIMBAD swaps the Gaia DR3 identifiers of the two stars: A is Gaia DR3 156430817820015232 and B is "
                "156430822114424576 (WDS position angle; Kurtovic et al. 2024).",
                "Parallax and proper motion come from B's Gaia DR3 solution (A's is unreliable, RUWE 16), as adopted "
                "by Kurtovic et al. 2024. Radial velocity 15 km/s from SIMBAD (Nguyen et al. 2012).",
            ],
        ),
    )


# --- Synthetic: orbits for the candidates of the synthetic demo field ------------


def demo_ecliptic_orbits() -> SystemModel:
    """Solar-system view of the synthetic `demo-ecliptic` candidates (SYNTHETIC)."""

    def planet(pid: str, name: str, a: float, e: float, inc: float, model: str, radius_km: float) -> Body:
        return Body(
            id=pid,
            name=name,
            kind="planet",
            radius_km=radius_km,
            orbit=Orbit(
                parent="sun",
                semi_major_axis_au=a,
                period_days=round(kepler_period_days(a, 1.0), 1),
                eccentricity=e,
                inclination_deg=inc,
            ),
            appearance=Appearance(model=model),  # type: ignore[arg-type]
            facts=[_fact("Orbit size", f"{a}", "AU")],
        )

    return SystemModel(
        id="demo-ecliptic-orbits",
        name="Demo: where the moving dots are",
        description="SYNTHETIC. 3D orbits for the candidates of the synthetic 'demo-ecliptic' field.",
        tags=["synthetic", "solar-system"],
        center=_demo_field_center("demo-ecliptic"),
        field_id="demo-ecliptic",
        representation_note=(
            "Illustrative model of a SYNTHETIC system (synthetic candidates, approximate planet orbits) - not an "
            "image. Sizes and distances may be exaggerated for visibility."
        ),
        bodies=[
            Body(
                id="sun",
                name="Sun",
                kind="star",
                radius_km=R_SUN_KM,
                mass_kg=M_SUN_KG,
                teff_k=5772,
                spectral_type="G2V",
                appearance=Appearance(model="star"),
            ),
            planet("earth", "Earth", 1.0, 0.017, 0.0, "rocky", R_EARTH_KM),
            planet("jupiter", "Jupiter", 5.2, 0.049, 1.3, "gas_giant", R_JUP_KM),
            planet("neptune", "Neptune", 30.07, 0.009, 1.8, "icy", 24_622.0),
            Body(
                id="syn-2026-aa",
                name="SYN 2026 AA (synthetic asteroid)",
                kind="asteroid",
                description="Synthetic outer-belt asteroid matching candidate SYN-AST-1.",
                radius_km=5.0,
                orbit=Orbit(
                    parent="sun",
                    semi_major_axis_au=3.8,
                    period_days=round(kepler_period_days(3.8, 1.0), 1),
                    eccentricity=0.05,
                    inclination_deg=8.0,
                    ascending_node_deg=40.0,
                    arg_periapsis_deg=110.0,
                ),
                appearance=Appearance(model="rocky"),
                candidate_id="SYN-AST-1",
                facts=[
                    _fact("Candidate", "SYN-AST-1 (known, synthetic)"),
                    _fact("Distance estimate", "~3.8", "AU", "pipeline (synthetic, opposition rate)"),
                ],
            ),
            Body(
                id="syn-tno-1",
                name="SYN-TNO-1 (unconfirmed, synthetic)",
                kind="unknown",
                description=(
                    "Unconfirmed (synthetic) candidate: it could be an artifact, a measurement error or an "
                    "uncatalogued slow mover. Its orbit is NOT known: drawn as a circle at the estimated distance."
                ),
                radius_km=150.0,  # arbitrary drawing size: nothing constrains it
                orbit=Orbit(
                    parent="sun",
                    semi_major_axis_au=42.2,
                    period_days=round(kepler_period_days(42.2, 1.0), 1),
                    quality="assumed",
                    note="Unconfirmed candidate: circle at the estimated distance, not a fitted orbit.",
                ),
                appearance=Appearance(model="icy"),
                candidate_id="SYN-TNO-1",
                facts=[
                    _fact("Distance estimate", "~42", "AU", "pipeline (synthetic)"),
                    _fact("Orbit", "assumed circular — not fitted", source="placeholder"),
                    _fact("Size", "unknown (drawn at an arbitrary size)"),
                ],
            ),
        ],
        provenance=_provenance(
            synthetic=True,
            notes=[
                "SYNTHETIC system for the synthetic demo field — NOT real objects.",
                "Orbital phases are arbitrary (no epoch): positions are not predictions for the shown date.",
            ],
        ),
    )


def literature_systems() -> list[SystemModel]:
    """The literature layer of the challenge test targets (values checked in WS7-2), before ``measured``."""
    return [barnards_star(), epsilon_indi(), wise_0855(), r_draconis(), rw_aurigae()]


def curated_systems() -> list[SystemModel]:
    """Real objects — the challenge test targets: literature layer + measurement layer (``targets.toml``)."""
    from .measured import apply_registry  # lazy: measured imports nothing from here, but keep the layers apart

    return apply_registry(literature_systems())


def demo_systems() -> list[SystemModel]:
    """Everything written into data/demo."""
    return [demo_ecliptic_orbits(), *curated_systems()]
