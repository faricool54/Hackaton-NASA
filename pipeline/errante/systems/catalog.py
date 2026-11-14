"""Curated 3D systems for the challenge test targets (WS7).

⚠️ Every number below was typed by hand as a STARTING POINT and is flagged
``verified=False``. WS7-2 replaces them with values fetched by
``systems.sources`` (NASA Exoplanet Archive, SIMBAD/Gaia DR3, JPL SBDB) and
flips ``verified`` to True only for values checked against the cited source.
Where a value is a model estimate (e.g. radius of a non-transiting planet), the
fact label says so.

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
DAYS_PER_YEAR = 365.25

UNVERIFIED_NOTE = (
    "Parameters typed by hand as a starting point; NOT yet verified against catalogs (tasks/WS7-3d-systems.md, WS7-2)."
)


def kepler_period_days(a_au: float, total_mass_msun: float) -> float:
    """Kepler's third law: P[yr]^2 = a[AU]^3 / M[Msun]."""
    return (a_au**3 / total_mass_msun) ** 0.5 * DAYS_PER_YEAR


def kepler_a_au(period_days: float, total_mass_msun: float) -> float:
    return (total_mass_msun * (period_days / DAYS_PER_YEAR) ** 2) ** (1 / 3)


def _fact(label: str, value: str, unit: str | None = None, source: str | None = None) -> Fact:
    return Fact(label=label, value=value, unit=unit, source=source, verified=False)


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
    m_star = 0.16
    src_planets = "Basant et al. 2025 (ApJL) / NASA Exoplanet Archive"
    planets = [
        # (id, name, period_days, min_mass_earth)
        ("barnard-d", "Barnard d", 2.340, 0.26),
        ("barnard-b", "Barnard b", 3.154, 0.30),
        ("barnard-c", "Barnard c", 4.124, 0.34),
        ("barnard-e", "Barnard e", 6.739, 0.19),
    ]
    bodies = [
        Body(
            id="barnards-star",
            name="Barnard's Star",
            kind="star",
            description="A small, cool red dwarf. It moves faster across our sky than any other star.",
            radius_km=0.187 * R_SUN_KM,
            mass_kg=m_star * M_SUN_KG,
            teff_k=3200,
            spectral_type="M4V",
            appearance=Appearance(model="star"),
            facts=[
                _fact("Spectral type", "M4V", source="SIMBAD"),
                _fact("Temperature", "~3200", "K", "SIMBAD / literature"),
                _fact("Distance", "1.83", "pc", "Gaia DR3"),
                _fact("Proper motion", "~10.4", "arcsec/yr", "Gaia DR3"),
            ],
        )
    ]
    for pid, name, period, mmin in planets:
        bodies.append(
            Body(
                id=pid,
                name=name,
                kind="planet",
                description="Rocky sub-Earth found by radial velocity. Too hot for liquid water.",
                radius_km=0.7 * R_EARTH_KM,  # estimate: not transiting, radius unknown
                mass_kg=mmin * M_EARTH_KG,
                orbit=Orbit(
                    parent="barnards-star",
                    semi_major_axis_au=round(kepler_a_au(period, m_star), 5),
                    period_days=period,
                ),
                appearance=Appearance(model="rocky"),
                facts=[
                    _fact("Orbital period", f"{period}", "days", src_planets),
                    _fact("Minimum mass", f"~{mmin}", "Earth masses", src_planets),
                    _fact("Radius (model estimate)", "~0.7", "Earth radii", "mass-radius relation; not measured"),
                ],
            )
        )
    return SystemModel(
        id="barnards-star",
        name="Barnard's Star system",
        description="Challenge test target: the fastest-moving star in our sky, with four small planets.",
        tags=["test-target", "proper-motion", "exoplanets"],
        center=SkyCoord(ra=269.4521, dec=4.6934),
        motion=SpaceMotion(
            distance_pc=1.83,
            parallax_mas=546.98,
            pm_ra_cosdec_mas_yr=-801.6,
            pm_dec_mas_yr=10362.4,
            radial_velocity_km_s=-110.6,
            epoch="J2016.0",
        ),
        field_id="barnards-star",
        bodies=bodies,
        provenance=_provenance(synthetic=False, notes=[UNVERIFIED_NOTE]),
    )


# --- Epsilon Indi: K dwarf + imaged giant planet + brown-dwarf binary ---------


def epsilon_indi() -> SystemModel:
    m_a, m_ba, m_bb = 0.76, 66.9 * M_JUP_KG / M_SUN_KG, 53.3 * M_JUP_KG / M_SUN_KG
    return SystemModel(
        id="epsilon-indi",
        name="Epsilon Indi system",
        description="Challenge test target: a Sun-like star, a cold giant planet and a pair of brown dwarfs.",
        tags=["test-target", "brown-dwarf", "binary", "exoplanets"],
        center=SkyCoord(ra=330.8402, dec=-56.7860),
        motion=SpaceMotion(
            distance_pc=3.64,
            parallax_mas=274.8,
            pm_ra_cosdec_mas_yr=3966.7,
            pm_dec_mas_yr=-2536.2,
            radial_velocity_km_s=-40.4,
            epoch="J2016.0",
        ),
        field_id=None,  # TODO(WS3/WS7): add an epsilon-indi field to config/fields.toml
        bodies=[
            Body(
                id="eps-indi-a",
                name="Epsilon Indi A",
                kind="star",
                description="An orange dwarf star, a bit smaller and cooler than the Sun.",
                radius_km=0.71 * R_SUN_KM,
                mass_kg=m_a * M_SUN_KG,
                teff_k=4630,
                spectral_type="K5V",
                appearance=Appearance(model="star"),
                facts=[
                    _fact("Spectral type", "K5V", source="SIMBAD"),
                    _fact("Distance", "3.64", "pc", "Gaia DR3"),
                ],
            ),
            Body(
                id="eps-indi-ab",
                name="Epsilon Indi Ab",
                kind="planet",
                description="A cold giant planet photographed directly by JWST.",
                radius_km=1.0 * R_JUP_KM,  # estimate
                mass_kg=6.0 * M_JUP_KG,
                teff_k=275,
                orbit=Orbit(
                    parent="eps-indi-a",
                    semi_major_axis_au=28.0,
                    period_days=round(kepler_period_days(28.0, m_a), 0),
                ),
                appearance=Appearance(model="gas_giant"),
                facts=[
                    _fact("Mass", "~6", "Jupiter masses", "Matthews et al. 2024 (Nature)"),
                    _fact("Orbit size", "~28", "AU", "Matthews et al. 2024 (Nature)"),
                    _fact("Temperature", "~275", "K", "Matthews et al. 2024 (Nature)"),
                ],
            ),
            Body(
                id="eps-indi-ba",
                name="Epsilon Indi Ba",
                kind="brown_dwarf",
                description="A brown dwarf: too heavy to be a planet, too light to shine like a star.",
                radius_km=0.9 * R_JUP_KM,
                mass_kg=m_ba * M_SUN_KG,
                teff_k=1300,
                spectral_type="T1",
                # Simplification: Ba orbits A directly (the Ba+Bb barycenter does in reality).
                orbit=Orbit(
                    parent="eps-indi-a",
                    semi_major_axis_au=1460.0,
                    period_days=round(kepler_period_days(1460.0, m_a + m_ba + m_bb), 0),
                ),
                appearance=Appearance(model="brown_dwarf"),
                facts=[
                    _fact("Spectral type", "T1", source="SIMBAD"),
                    _fact("Mass", "~67", "Jupiter masses", "Chen et al. 2022"),
                    _fact("Separation from A", "~1460 (projected)", "AU", "literature"),
                ],
            ),
            Body(
                id="eps-indi-bb",
                name="Epsilon Indi Bb",
                kind="brown_dwarf",
                description="The colder twin of Ba; the two orbit each other every ~11 years.",
                radius_km=0.9 * R_JUP_KM,
                mass_kg=m_bb * M_SUN_KG,
                teff_k=900,
                spectral_type="T6",
                orbit=Orbit(
                    parent="eps-indi-ba",
                    semi_major_axis_au=round(kepler_a_au(11.0 * DAYS_PER_YEAR, m_ba + m_bb), 3),
                    period_days=11.0 * DAYS_PER_YEAR,
                    eccentricity=0.54,
                ),
                appearance=Appearance(model="brown_dwarf"),
                facts=[
                    _fact("Spectral type", "T6", source="SIMBAD"),
                    _fact("Mass", "~53", "Jupiter masses", "Chen et al. 2022"),
                    _fact("Orbital period around Ba", "~11", "years", "Chen et al. 2022"),
                ],
            ),
        ],
        provenance=_provenance(
            synthetic=False,
            notes=[UNVERIFIED_NOTE, "Simplified hierarchy: Ba orbits A and Bb orbits Ba (no barycenters)."],
        ),
    )


# --- WISE 0855-0714: the coldest known brown dwarf, alone ---------------------


def wise_0855() -> SystemModel:
    return SystemModel(
        id="wise-0855",
        name="WISE 0855−0714",
        description="Challenge test target: the coldest known brown dwarf, about as cold as the North Pole.",
        tags=["test-target", "brown-dwarf", "proper-motion"],
        center=SkyCoord(ra=133.79513, dec=-7.24515),  # coordinates given in the challenge (older epoch)
        motion=SpaceMotion(
            distance_pc=2.28,
            parallax_mas=439.0,
            pm_ra_cosdec_mas_yr=-8118.0,
            pm_dec_mas_yr=680.0,
            epoch="J2014 (approx.)",
        ),
        field_id="wise-0855",
        bodies=[
            Body(
                id="wise-0855",
                name="WISE 0855−0714",
                kind="brown_dwarf",
                description="A free-floating ultra-cool brown dwarf with water clouds predicted in its atmosphere.",
                radius_km=1.0 * R_JUP_KM,
                mass_kg=5.0 * M_JUP_KG,
                teff_k=285,
                spectral_type="Y4 (approx.)",
                appearance=Appearance(model="brown_dwarf"),
                facts=[
                    _fact("Temperature", "~285", "K", "Luhman 2014; JWST spectra"),
                    _fact("Distance", "~2.28", "pc", "Luhman & Esplin 2016"),
                    _fact("Mass", "3–10", "Jupiter masses", "literature (model dependent)"),
                    _fact("Proper motion", "~8.1", "arcsec/yr", "literature"),
                ],
            )
        ],
        provenance=_provenance(synthetic=False, notes=[UNVERIFIED_NOTE]),
    )


# --- R Draconis: a pulsating Mira variable --------------------------------------


def r_draconis() -> SystemModel:
    return SystemModel(
        id="r-draconis",
        name="R Draconis",
        description="Challenge test target: a giant star that swells and fades every ~8 months.",
        tags=["test-target", "variable"],
        center=SkyCoord(ra=248.1675, dec=66.7550),
        field_id=None,  # TODO(WS3/WS7): add an r-draconis field to config/fields.toml
        bodies=[
            Body(
                id="r-draconis",
                name="R Draconis",
                kind="star",
                description="A Mira variable: an old red giant whose brightness changes by hundreds of times.",
                radius_km=250 * R_SUN_KM,  # rough estimate; varies during the cycle
                teff_k=3000,
                spectral_type="M5e–M9e",
                variability=Variability(kind="pulsation", period_days=245.6, amplitude_mag=6.5, band="V"),
                appearance=Appearance(model="star"),
                facts=[
                    _fact("Variable type", "Mira", source="GCVS / AAVSO VSX"),
                    _fact("Period", "~245.6", "days", "GCVS / AAVSO VSX"),
                    _fact("Visual range", "6.7–13.2", "mag", "GCVS / AAVSO VSX"),
                    _fact("Radius (rough estimate)", "~250", "solar radii", "typical Mira; not measured"),
                ],
            )
        ],
        provenance=_provenance(synthetic=False, notes=[UNVERIFIED_NOTE]),
    )


# --- RW Aurigae: young binary with a disk ----------------------------------------


def rw_aurigae() -> SystemModel:
    return SystemModel(
        id="rw-aurigae",
        name="RW Aurigae",
        description="Challenge test target: a young binary star whose dusty disk causes deep dimming events.",
        tags=["test-target", "variable", "binary", "young-star"],
        center=SkyCoord(ra=76.9563, dec=30.4014),
        field_id=None,  # TODO(WS3/WS7): add an rw-aurigae field to config/fields.toml
        bodies=[
            Body(
                id="rw-aur-a",
                name="RW Aurigae A",
                kind="star",
                description="A T Tauri star: a newborn star still feeding from its disk.",
                radius_km=1.7 * R_SUN_KM,
                mass_kg=1.4 * M_SUN_KG,
                teff_k=4900,
                spectral_type="K1–K4 (T Tauri)",
                variability=Variability(kind="irregular", amplitude_mag=2.0, band="V"),
                appearance=Appearance(model="star"),
                facts=[
                    _fact("Type", "Classical T Tauri star", source="SIMBAD"),
                    _fact("Dimming events", "~2 mag since 2010", source="literature (e.g. Rodriguez et al.)"),
                ],
            ),
            Body(
                id="rw-aur-a-disk",
                name="Disk around A",
                kind="disk",
                description="Gas and dust left over from the star's birth, truncated by companion B.",
                radius_km=40 * 1.496e8,  # ~40 AU outer radius (rough)
                orbit=None,
                appearance=Appearance(model="disk"),
                facts=[_fact("Outer radius (rough)", "~40", "AU", "literature")],
            ),
            Body(
                id="rw-aur-b",
                name="RW Aurigae B",
                kind="star",
                description="The companion star, about 1.4 arcsec away on the sky.",
                radius_km=1.2 * R_SUN_KM,
                mass_kg=0.9 * M_SUN_KG,
                teff_k=4400,
                orbit=Orbit(
                    parent="rw-aur-a",
                    semi_major_axis_au=200.0,
                    period_days=round(kepler_period_days(200.0, 2.3), 0),
                ),
                appearance=Appearance(model="star"),
                facts=[_fact("Projected separation", "~1.4 (~200 AU)", "arcsec", "literature")],
            ),
        ],
        provenance=_provenance(
            synthetic=False,
            notes=[UNVERIFIED_NOTE, "The disk body has no orbit: the UI draws it centred on its host (rw-aur-a)."],
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
        center=SkyCoord(ra=180.0, dec=0.0),
        field_id="demo-ecliptic",
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
                description="Synthetic main-belt asteroid matching candidate SYN-AST-1.",
                radius_km=5.0,
                orbit=Orbit(
                    parent="sun",
                    semi_major_axis_au=2.9,
                    period_days=round(kepler_period_days(2.9, 1.0), 1),
                    eccentricity=0.12,
                    inclination_deg=8.0,
                    ascending_node_deg=40.0,
                    arg_periapsis_deg=110.0,
                ),
                appearance=Appearance(model="rocky"),
                candidate_id="SYN-AST-1",
                facts=[_fact("Candidate", "SYN-AST-1 (known, synthetic)")],
            ),
            Body(
                id="syn-tno-1",
                name="SYN-TNO-1 (unconfirmed, synthetic)",
                kind="tno",
                description="Unconfirmed candidate. Its orbit is NOT known: drawn as a circle at the estimated distance.",
                radius_km=150.0,
                orbit=Orbit(
                    parent="sun",
                    semi_major_axis_au=42.2,
                    period_days=round(kepler_period_days(42.2, 1.0), 1),
                ),
                appearance=Appearance(model="icy"),
                candidate_id="SYN-TNO-1",
                facts=[
                    _fact("Distance estimate", "~42", "AU", "pipeline (synthetic)"),
                    _fact("Orbit", "assumed circular — not fitted", source="placeholder"),
                ],
            ),
        ],
        provenance=_provenance(
            synthetic=True,
            notes=["SYNTHETIC system for the synthetic demo field — NOT real objects."],
        ),
    )


def curated_systems() -> list[SystemModel]:
    """Real objects (hand-typed, unverified) — the challenge test targets."""
    return [barnards_star(), epsilon_indi(), wise_0855(), r_draconis(), rw_aurigae()]


def demo_systems() -> list[SystemModel]:
    """Everything written into data/demo."""
    return [demo_ecliptic_orbits(), *curated_systems()]
