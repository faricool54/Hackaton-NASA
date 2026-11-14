"""Curated 3D systems for the challenge test targets (WS7).

WS7-2 (2026-11-14): every value below was checked against the NASA Exoplanet
Archive, SIMBAD (CfA mirror), Gaia DR3, VizieR and the cited papers. The
fetchers in ``systems.sources`` reproduce the archive queries and the
``network`` tests in ``tests/test_systems.py`` re-run them. A ``Fact`` is
``verified=True`` only when its value was found in the cited source; model
estimates and illustrative drawing values say so in their label and source.
Where the drawing needs a number no source gives (e.g. the radius of a brown
dwarf in the Epsilon Indi B pair), it is set on the body without a Fact and the
provenance notes say it is illustrative.

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
    "cited papers (tasks/WS7-3d-systems.md, WS7-2). Facts still marked 'unverified' are estimates no source states."
)

REAL_REPRESENTATION = (
    "3D model drawn from published catalog and literature values (each fact shows its source) - not an image. "
    "Sizes and distances may be exaggerated for visibility."
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


def barnards_star() -> SystemModel:
    star_src = f"{EXOPLANET_ARCHIVE} (González Hernández et al. 2024, A&A 690, A79)"
    planet_src = f"{EXOPLANET_ARCHIVE} (Basant et al. 2025, ApJL 982, L1)"
    gaia = f"{GAIA_DR3} 4472832130942575872"
    planets = [
        # (id, name, period_days, min_mass_earth, a_au, archive radius estimate [R_earth])
        ("barnard-d", "Barnard d", 2.3402, 0.263, 0.0188, 0.694),
        ("barnard-b", "Barnard b", 3.1542, 0.299, 0.0229, 0.720),
        ("barnard-c", "Barnard c", 4.1244, 0.335, 0.0274, 0.743),
        ("barnard-e", "Barnard e", 6.7392, 0.193, 0.0381, 0.637),
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
            ],
        )
    ]
    for pid, name, period, mmin, a_au, r_est in planets:
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
                    note=(
                        "Drawn circular: the fitted eccentricities are consistent with zero (Basant et al. 2025 "
                        "favour e < 0.02). Orbit inclination unknown (radial-velocity detection)."
                    ),
                ),
                appearance=Appearance(model="rocky"),
                facts=[
                    _vfact("Orbital period", f"{period}", "days", planet_src),
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
                PHASE_NOTE,
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
        description="Challenge test target: a Sun-like star, a cold giant planet and a pair of brown dwarfs.",
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
        field_id=None,  # TODO(WS3/WS7): add an epsilon-indi field to config/fields.toml
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
                radius_km=0.9 * R_JUP_KM,  # illustrative: no published radius
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
                    _vfact("Temperature", "~1300", "K", "King et al. 2010, as adopted by Chen et al. 2022"),
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
                radius_km=0.9 * R_JUP_KM,  # illustrative: no published radius
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
                    _vfact("Temperature", "~900", "K", "King et al. 2010, as adopted by Chen et al. 2022"),
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
                "Ba and Bb are drawn with an illustrative radius of 0.9 Jupiter radii (no published radius); the "
                "radius of Ab is the archive's estimate from its mass.",
                "Gaia DR3 measures Ba+Bb as one unresolved source (RUWE 4.3): its parallax is not used for distance.",
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
                mass_kg=5.0 * M_JUP_KG,  # illustrative value inside the 3-10 M_Jup model range
                teff_k=285,
                spectral_type="Y4 (approx.)",
                appearance=Appearance(model="brown_dwarf"),
                facts=[
                    _vfact("Spectral type", "~Y4", None, f"{k21}; {l24}"),
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
                "The model is drawn with 5 Jupiter masses, an illustrative value inside the published 3–10 range.",
            ],
        ),
    )


# --- R Draconis: a pulsating Mira variable --------------------------------------


def r_draconis() -> SystemModel:
    gcvs = "GCVS 5.1 (Samus et al. 2017)"
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
        field_id=None,  # TODO(WS3/WS7): add an r-draconis field to config/fields.toml
        bodies=[
            Body(
                id="r-draconis",
                name="R Draconis",
                kind="star",
                description="A Mira variable: an old red giant whose visible brightness changes by hundreds of times.",
                radius_km=250 * R_SUN_KM,  # illustrative; varies during the cycle
                teff_k=3000,  # representative drawing value inside the published range
                spectral_type="M5e–M9eIII",
                variability=Variability(kind="pulsation", period_days=245.6, amplitude_mag=6.5, band="V"),
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
                    _fact(
                        "Radius (illustrative)",
                        "~250",
                        "solar radii",
                        "drawing value: published sizes depend strongly on the assumed distance and the pulsation phase",
                    ),
                ],
            )
        ],
        representation_note=REAL_REPRESENTATION,
        provenance=_provenance(
            synthetic=False,
            notes=[
                VERIFIED_NOTE,
                PHASE_NOTE,
                "The size/brightness animation is a sine wave spanning the V-band range: real Mira cycles are "
                "asymmetric, change from cycle to cycle and are much smaller in the infrared SPHEREx sees. It is "
                "not a measured or SPHEREx light curve.",
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
        field_id=None,  # TODO(WS3/WS7): add an rw-aurigae field to config/fields.toml
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
                        "Radius (estimate)",
                        "~1.3",
                        "solar radii",
                        "Herczeg & Hillenbrand 2014 (1.20 at 140 pc) rescaled to the Gaia distance; uncertain",
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


def curated_systems() -> list[SystemModel]:
    """Real objects — the challenge test targets (values checked in WS7-2)."""
    return [barnards_star(), epsilon_indi(), wise_0855(), r_draconis(), rw_aurigae()]


def demo_systems() -> list[SystemModel]:
    """Everything written into data/demo."""
    return [demo_ecliptic_orbits(), *curated_systems()]
