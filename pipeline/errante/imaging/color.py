"""False-color infrared season composites (WS2; contract 0.3.0 ``Field.composites``).

SPHEREx observes 0.75-5.0 um, which the eye cannot see. A composite maps three
infrared wavelength ranges to red, green and blue, the shortest to blue
(chromatic order). It is NOT a true-color picture, and the UI must say so.

One composite per observing season and mode:

- ``detectors`` (full range): blue = D1 0.75-1.11 um (fallback D2),
  green = D3 1.64-2.42 um (fallback D4), red = D6 4.42-5.00 um (fallback D5).
  Each channel coadds the season's FINAL (published) frames of that detector.
- ``jhk`` (2MASS-like): blue / green / red coadd the season's downloaded
  exposures (the whole vetted candidate pool, not only the published frames)
  whose wavelength at the field centre is within ``JHK_TOLERANCE_UM`` of
  J 1.25 / H 1.65 / Ks 2.17 um. If a band has none, the single nearest exposure
  within ``JHK_FALLBACK_UM`` is used. If it has nothing even then, that
  season gets no jhk composite and the reason goes into the provenance note.
  Every SPHEREx exposure sees its own narrow wavelength (linear variable
  filter), so these are narrow samples near the 2MASS bands, not 2MASS filters.

Seasons follow ``build.season_index`` over the final frames. A pool exposure
joins the season of the final frame nearest in time, if it is within
``SEASON_GAP_DAYS``. Composites exist only for seasons where all three
channels exist.

Channels use ``compare.weighted_stack``: one weight per frame, each frame's sky
removed, bad pixels left out. Saturated cores and detector defects that
``reproject_to_grid`` repaired for display only fill the holes of the
displayed image.

Rendering (``color_balance``, ``composite_rgb``): green gets limits like the
grey frames, from 2 sigma below the sky to the bright end of its usable pixels
(``render.field_stretches``). Red and blue are tied to green by the median
flux ratio of the FIELD STARS, so a typical field star comes out white and the
sky neutral grey, and a source much redder than the field stars (a brown dwarf
at 4.5 um) comes out red. The target's halo never sets any limit: on the real
Barnard field a percentile stretch let the target's 4.6 um halo set the red
limit and turned every field star cyan. Limits are shared by every season with
the same three detectors, so blinking seasons does not flicker. The asinh curve
is applied to the mean of the three normalised channels and scales all three
by the same factor (Lupton et al. 2004, PASP 116, 133), so a bright star keeps
its colour instead of clipping to white. Pixels with no colour information are
drawn neutral: saturated cores white, and pixels that only some channels cover
grey. Pixels without data in all three channels are transparent.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from ..detect.difference import StarScale, star_flux_scale
from ..models import Composite, CompositeChannel, Stretch
from .compare import GridFrame, Stack, target_exclusion, weighted_stack
from .render import field_stretches

COLOR_DIR = "color"
COLORS = ("red", "green", "blue")  # contract order
DETECTOR_CHANNELS: dict[str, tuple[int, ...]] = {"red": (6, 5), "green": (3, 4), "blue": (1, 2)}
# 2MASS J / H / Ks central wavelengths, rounded [um].
JHK_BANDS: dict[str, tuple[str, float]] = {"red": ("Ks", 2.17), "green": ("H", 1.65), "blue": ("J", 1.25)}
JHK_TOLERANCE_UM = 0.06
JHK_FALLBACK_UM = 0.12
SOFTENING = 0.1  # asinh softening, the same as the grey frames (render.to_uint8)
_EPS_UM = 1e-9  # float slack on the wavelength windows
MAD_TO_SIGMA = 1.4826
# A channel whose pixel noise exceeds this fraction of its display range gets a "noisy" note: a 2-sigma
# speckle then reaches ~25 % brightness. Measured 2026-11-14 on the real golden fields (pixel-difference
# noise / range): D6 0.015 (Barnard, RW Aur), 0.034-0.049 (eps Indi B, R Dra D5), 0.10-0.11 (WISE 0855);
# every green and blue channel <= 0.01.
NOISY_FRACTION = 0.03

FALSE_COLOR_NOTE = "False color: SPHEREx infrared wavelengths mapped to red, green and blue (infrared, not true color)."
RELATIVE_NOTE = (
    "Colours are relative to the field: typical field stars look roughly white and an object redder than they are "
    "looks red."
)
JHK_NOTE = (
    "2MASS-like: each channel holds narrow SPHEREx samples near J, H or Ks, not the 2MASS filters or 2MASS photometry."
)


@dataclass(frozen=True)
class Channel:
    """One colour of a composite: the coadd of its input frames."""

    color: str
    stack: Stack  # science coadd: bad pixels left out (NaN where no frame has a usable pixel)
    display: np.ndarray  # the coadd, with display-repaired pixels (saturated cores) filling its holes

    @property
    def frame_ids(self) -> list[str]:
        return [f.frame_id for f in self.stack.frames]

    @property
    def detector(self) -> int | None:
        detectors = {f.detector for f in self.stack.frames}
        return detectors.pop() if len(detectors) == 1 else None

    @property
    def wavelengths(self) -> list[float]:
        return [f.wavelength_um for f in self.stack.frames if f.wavelength_um is not None]

    @property
    def wavelength_um(self) -> float | None:
        return float(np.mean(self.wavelengths)) if self.wavelengths else None

    @property
    def wavelength_min_um(self) -> float | None:
        return min(self.wavelengths, default=None)

    @property
    def wavelength_max_um(self) -> float | None:
        return max(self.wavelengths, default=None)

    @property
    def mjds(self) -> list[float]:
        return [f.mjd for f in self.stack.frames]


@dataclass(frozen=True)
class SeasonComposite:
    mode: str
    season: int
    channels: tuple[Channel, Channel, Channel]  # red, green, blue
    notes: tuple[str, ...] = ()

    @property
    def id(self) -> str:
        return f"{self.mode}_S{self.season}"

    @property
    def mjd_min(self) -> float:
        return min(m for ch in self.channels for m in ch.mjds)

    @property
    def mjd_max(self) -> float:
        return max(m for ch in self.channels for m in ch.mjds)


@dataclass(frozen=True)
class ColorPlan:
    composites: list[SeasonComposite]
    skipped: list[str]  # "<mode> S<season>: <reason>"


def _channel(color: str, frames: Sequence[GridFrame]) -> Channel | None:
    """Coadd ``frames`` into one colour; None when no frame has a usable pixel."""
    frames = sorted(frames, key=lambda f: (f.mjd, f.frame_id))
    stack = weighted_stack(frames)
    if not stack.frames:
        return None
    shown = weighted_stack(frames, include_bad=True).data
    return Channel(color, stack, np.where(np.isfinite(stack.data), stack.data, shown).astype(np.float32))


def _describe(ch: Channel) -> str:
    lam = ch.wavelength_um
    where = f"{lam:.2f} um" if lam is not None else "wavelength unknown"
    source = f"D{ch.detector}" if ch.detector is not None else "D" + "+D".join(str(d) for d in _detectors(ch))
    return f"{ch.color} = {source} {where}"


def _detectors(ch: Channel) -> list[int]:
    return sorted({f.detector for f in ch.stack.frames})


def _detector_composite(season: int, frames: Sequence[GridFrame]) -> SeasonComposite | str:
    """Option A: whole detectors over the full range, from the season's final frames."""
    channels: list[Channel] = []
    fallbacks: list[str] = []
    for color in COLORS:
        options = DETECTOR_CHANNELS[color]
        found = None
        for det in options:
            members = [f for f in frames if f.detector == det]
            found = _channel(color, members) if members else None
            if found is not None:
                break
        if found is None:
            wanted = " or ".join(f"D{d}" for d in options)
            return f"detectors S{season}: no usable frame of {wanted} for {color}"
        if found.detector != options[0]:
            fallbacks.append(f"{color} uses D{found.detector}: no usable D{options[0]} frame in this season.")
        channels.append(found)
    mapping = ", ".join(_describe(ch) for ch in channels)
    notes = (FALSE_COLOR_NOTE, f"Full range: {mapping} (mean wavelength at the field centre).", *fallbacks)
    return SeasonComposite("detectors", season, (channels[0], channels[1], channels[2]), (*notes, RELATIVE_NOTE))


def _jhk_composite(season: int, frames: Sequence[GridFrame]) -> SeasonComposite | str:
    """Option B: exposures near the 2MASS J, H and Ks bands, from the season's downloaded pool."""
    known = [f for f in frames if f.wavelength_um is not None]
    channels: list[Channel] = []
    fallbacks: list[str] = []
    for color in COLORS:
        band, target = JHK_BANDS[color]
        label = f"{color} ({band} {target:g} um)"

        def distance(f: GridFrame, target: float = target) -> float:
            return abs(f.wavelength_um - target)

        near = [f for f in known if distance(f) <= JHK_TOLERANCE_UM + _EPS_UM]
        if not near:
            nearest = min(known, key=lambda f: (distance(f), f.frame_id), default=None)
            if nearest is None or distance(nearest) > JHK_FALLBACK_UM + _EPS_UM:
                closest = f"; nearest {nearest.wavelength_um:.3f} um" if nearest is not None else ""
                return f"jhk S{season}: no exposure within {JHK_FALLBACK_UM:g} um of {label}{closest}"
            near = [nearest]
            fallbacks.append(
                f"{label} uses the nearest exposure, {nearest.wavelength_um:.3f} um "
                f"({distance(nearest):.3f} um away): none within {JHK_TOLERANCE_UM:g} um."
            )
        found = _channel(color, near)
        if found is None:
            return f"jhk S{season}: the exposures near {label} have no usable pixel"
        channels.append(found)
    mapping = ", ".join(_describe(ch) for ch in channels)
    notes = (FALSE_COLOR_NOTE, f"{JHK_NOTE} {mapping} (mean wavelength at the field centre).", *fallbacks)
    return SeasonComposite("jhk", season, (channels[0], channels[1], channels[2]), (*notes, RELATIVE_NOTE))


def _seasons(final: Sequence[GridFrame], pool: Sequence[GridFrame]) -> tuple[dict[int, list], dict[int, list]]:
    """(final frames by season, final + pool frames by season); pool frames join the nearest final frame."""
    from ..build import SEASON_GAP_DAYS, season_index

    final_by: dict[int, list[GridFrame]] = defaultdict(list)
    season_of: dict[str, int] = {}
    for f, s in zip(final, season_index([f.mjd for f in final]), strict=True):
        final_by[s].append(f)
        season_of[f.frame_id] = s
    pool_by: dict[int, list[GridFrame]] = defaultdict(list)
    seen: set[str] = set()
    for f in [*final, *pool]:
        if f.frame_id in seen:
            continue
        seen.add(f.frame_id)
        if f.frame_id in season_of:
            pool_by[season_of[f.frame_id]].append(f)
            continue
        nearest = min(final, key=lambda g: (abs(g.mjd - f.mjd), g.mjd))
        if abs(nearest.mjd - f.mjd) <= SEASON_GAP_DAYS:
            pool_by[season_of[nearest.frame_id]].append(f)
    return final_by, pool_by


def plan_composites(final: Sequence[GridFrame], pool: Sequence[GridFrame]) -> ColorPlan:
    """Composites of both modes for every season of ``final`` that has all three channels."""
    if not final:
        return ColorPlan([], ["no final frames"])
    final_by, pool_by = _seasons(final, pool)
    composites: list[SeasonComposite] = []
    skipped: list[str] = []
    for builder, frames_by in ((_detector_composite, final_by), (_jhk_composite, pool_by)):
        for season in sorted(final_by):
            result = builder(season, frames_by.get(season, []))
            if isinstance(result, str):
                skipped.append(result)
            else:
                composites.append(result)
    return ColorPlan(composites, skipped)


@dataclass(frozen=True)
class Balance:
    """Display limits of every channel and how the three colours were balanced."""

    stretches: dict[tuple[str, str], Stretch]  # (composite id, colour) -> limits in MJy/sr
    ratios: dict[tuple[str, str], float | None]  # (composite id, red|blue) -> field-star flux ratio to green used
    noise: dict[tuple[str, str], float]  # (composite id, colour) -> pixel noise / display range
    notes: dict[str, list[str]]  # composite id -> plain-language colour-balance notes


def _config(comp: SeasonComposite) -> tuple:
    """Seasons that share limits: same mode and, for 'detectors', the same three detectors (fallbacks differ)."""
    if comp.mode == "detectors":
        return (comp.mode, *(ch.detector for ch in comp.channels))
    return (comp.mode,)


def _target_disc(comp: SeasonComposite) -> tuple[float, float, float]:
    """(x, y, radius) around the target at the field centre: the widest halo exclusion of the three channels."""
    return max((target_exclusion(ch.stack.data.astype(np.float64)) for ch in comp.channels), key=lambda d: d[2])


def _inside(shape: tuple[int, ...], disc: tuple[float, float, float]) -> np.ndarray:
    yy, xx = np.indices(shape)
    return np.hypot(xx - disc[0], yy - disc[1]) < disc[2]


def _sky_level(img: np.ndarray, skip: np.ndarray) -> float:
    values = img[np.isfinite(img) & ~skip]
    return float(np.median(values)) if values.size else 0.0


def _robust_sigma(values: np.ndarray) -> float:
    return float(MAD_TO_SIGMA * np.median(np.abs(values - np.median(values)))) if values.size else float("nan")


def _noise(ch: Channel) -> float:
    """Per-pixel background noise of a channel: from its propagated VARIANCE, else its robust scatter."""
    var = ch.stack.variance
    sigma = float(np.sqrt(np.nanmedian(var))) if np.isfinite(var).any() else float("nan")
    if not np.isfinite(sigma) or sigma <= 0:
        sigma = _robust_sigma(ch.stack.data[np.isfinite(ch.stack.data)])
    return sigma if np.isfinite(sigma) and sigma > 0 else 1.0


def _pixel_noise(img: np.ndarray, skip: np.ndarray) -> float:
    """Robust pixel-to-pixel noise: horizontal neighbour differences / sqrt(2), blind to smooth glows."""
    diff = img[:, 1:] - img[:, :-1]
    ok = np.isfinite(diff) & ~skip[:, 1:] & ~skip[:, :-1]
    return _robust_sigma(diff[ok]) / np.sqrt(2.0)


def _field_star_ratio(ch: Channel, green: Channel, disc: tuple[float, float, float]) -> StarScale:
    """Median ``ch / green`` aperture-flux ratio of the field stars (local sky, target halo left out)."""
    data, ref = ch.stack.data.astype(np.float64), green.stack.data.astype(np.float64)
    return star_flux_scale(data, ref, _noise(green), exclude=disc)


def _base_limits(
    composites: Sequence[SeasonComposite], discs: Mapping[str, tuple[float, float, float]]
) -> tuple[dict[tuple[str, str], Stretch], dict[tuple[str, str], np.ndarray]]:
    """``render.field_stretches`` limits per channel, shared per (configuration, colour); halo + holes skipped."""
    skips: dict[tuple[str, str], np.ndarray] = {}
    images, groups = [], []
    for comp in composites:
        halo = _inside(comp.channels[0].stack.data.shape, discs[comp.id])
        for ch in comp.channels:
            skips[(comp.id, ch.color)] = ~np.isfinite(ch.stack.data) | halo
            images.append(ch.stack.data)
            groups.append((_config(comp), ch.color))
    return dict(zip(skips, field_stretches(images, groups, list(skips.values())), strict=True)), skips


def _shared_ratios(
    composites: Sequence[SeasonComposite], discs: Mapping[str, tuple[float, float, float]]
) -> tuple[dict[tuple[tuple, str], float], dict[tuple[tuple, str], int]]:
    """Median over seasons of the fitted red/green and blue/green field-star ratios, per configuration."""
    fits: dict[tuple[tuple, str], list[float]] = defaultdict(list)
    for comp in composites:
        red, green, blue = comp.channels
        for ch in (red, blue):
            fit = _field_star_ratio(ch, green, discs[comp.id])
            if fit.fitted:
                fits[(_config(comp), ch.color)].append(fit.scale)
    return {k: float(np.median(v)) for k, v in fits.items()}, {k: len(v) for k, v in fits.items()}


def color_balance(composites: Sequence[SeasonComposite]) -> Balance:
    """Per-channel limits, shared by every season of the same configuration, balanced on the field stars.

    1. Every channel gets limits like ``render.field_stretches``: 2 sigma below its sky to the bright end of
       its usable pixels, shared across seasons. The target's halo (``compare.target_exclusion``, widest of
       the three channels) and display-filled pixels never set them.
    2. Red and blue are then tied to green: their span above the sky is green's span times the median
       field-star flux ratio (red / green, blue / green; one aperture ratio per star above its local sky,
       ``detect.difference.star_flux_scale``), the median of the per-season fits, and their black point
       sits the same fraction of that span below their sky as green's 2 sigma. A typical field star and
       the mean sky then have the same normalised value in all three channels, i.e. look white / neutral
       grey. (A per-channel 2 sigma black point tinted the real eps Indi B and WISE 0855 skies purple: D6
       noise is 4-9 % of its balanced span, green's 0.4-0.7 %.) The noisier channel still shows as
       coloured speckle, and gets a note above ``NOISY_FRACTION``. A colour without any fitted season
       (fewer than ``MIN_STARS`` usable stars) keeps step 1's limits.
    """
    discs = {c.id: _target_disc(c) for c in composites}
    base, skips = _base_limits(composites, discs)
    shared, n_fits = _shared_ratios(composites, discs)
    stretches = dict(base)
    ratios: dict[tuple[str, str], float | None] = {}
    for comp in composites:
        green, green_limits = comp.channels[1], base[(comp.id, "green")]
        green_sky = _sky_level(green.stack.data, skips[(comp.id, "green")])
        green_span = green_limits.vmax - green_sky
        below = (green_sky - green_limits.vmin) / green_span  # green's 2 sigma below the sky, as a span fraction
        for ch in (comp.channels[0], comp.channels[2]):
            key = (comp.id, ch.color)
            ratios[key] = ratio = shared.get((_config(comp), ch.color))
            if ratio is not None:
                sky, span = _sky_level(ch.stack.data, skips[key]), ratio * green_span
                stretches[key] = Stretch(vmin=sky - below * span, vmax=sky + span, method="asinh")
    noise: dict[tuple[str, str], float] = {}
    for comp in composites:
        for ch in comp.channels:
            key = (comp.id, ch.color)
            noise[key] = _pixel_noise(ch.stack.data, skips[key]) / (stretches[key].vmax - stretches[key].vmin)
    notes = {c.id: _balance_notes(c, ratios, noise, n_fits) for c in composites}
    return Balance(stretches, ratios, noise, notes)


def _balance_notes(
    comp: SeasonComposite,
    ratios: Mapping[tuple[str, str], float | None],
    noise: Mapping[tuple[str, str], float],
    n_fits: Mapping[tuple[tuple, str], int],
) -> list[str]:
    done = [c for c in ("red", "blue") if ratios[(comp.id, c)] is not None]
    if not done:
        notes = [
            "Colour balance: not fitted (fewer than 5 usable field stars outside the target halo); each channel "
            "is scaled on its own brightest usable pixels, so field-star colours are only indicative."
        ]
    else:
        parts = ", ".join(f"{c} x{ratios[(comp.id, c)]:.3g}" for c in done)
        seasons = max(n_fits.get((_config(comp), c), 0) for c in done)
        text = (
            f"Colour balance: {' and '.join(done)} scaled to green by the median flux ratio of the field stars "
            f"({parts}; median of {seasons} season fit(s)), so typical field stars look white."
        )
        missing = [c for c in ("red", "blue") if c not in done]
        if missing:
            text += f" {missing[0].capitalize()} could not be balanced (too few field stars); it uses its own limits."
        notes = [text]
    for ch in comp.channels:
        fraction = noise[(comp.id, ch.color)]
        if np.isfinite(fraction) and fraction > NOISY_FRACTION:
            source = f"D{ch.detector}" if ch.detector is not None else "mixed detectors"
            notes.append(
                f"The {ch.color} channel ({source}) is noisy here (pixel noise {100 * fraction:.0f}% of its range): "
                f"isolated {ch.color} specks are mostly noise, not {ch.color} objects."
            )
    return notes


def _normalised(img: np.ndarray, stretch: Stretch) -> np.ndarray:
    x = (img.astype(np.float64) - stretch.vmin) / (stretch.vmax - stretch.vmin)
    return np.clip(np.nan_to_num(x, nan=0.0), 0.0, None)


def composite_rgb(
    comp: SeasonComposite, stretches: Mapping[tuple[str, str], Stretch], softening: float = SOFTENING
) -> np.ndarray:
    """uint8 RGB image of ``comp`` (RGBA, alpha 0 where no channel has data, if there is such a pixel).

    Pixels without colour information are drawn neutral: saturated cores (display-repaired in a channel)
    white at the brightest channel, and pixels that only some channels cover grey from those channels.
    """
    x = np.stack([_normalised(ch.display, stretches[(comp.id, ch.color)]) for ch in comp.channels])
    has = np.stack([np.isfinite(ch.display) for ch in comp.channels])
    repaired = np.stack([np.isfinite(ch.display) & ~np.isfinite(ch.stack.data) for ch in comp.channels]).any(axis=0)
    x = np.where(repaired, x.max(axis=0), x)
    partial = has.any(axis=0) & ~has.all(axis=0)
    grey = np.where(has, x, 0.0).sum(axis=0) / np.maximum(has.sum(axis=0), 1)
    x = np.where(partial, grey, x)
    intensity = x.mean(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        gain = np.where(intensity > 0, np.arcsinh(intensity / softening) / np.arcsinh(1.0 / softening) / intensity, 0)
    rgb = x * gain
    rgb /= np.maximum(rgb.max(axis=0), 1.0)  # keep the hue of pixels brighter than the limits
    out = (rgb * 255).round().astype(np.uint8).transpose(1, 2, 0)
    nodata = np.logical_and.reduce([~np.isfinite(ch.display) for ch in comp.channels])
    if not nodata.any():
        return out
    return np.dstack([out, np.where(nodata, 0, 255).astype(np.uint8)])


def _to_contract(comp: SeasonComposite, balance_notes: list[str]) -> Composite:
    return Composite(
        id=comp.id,
        mode=comp.mode,
        season=comp.season,
        mjd_min=comp.mjd_min,
        mjd_max=comp.mjd_max,
        image=f"{COLOR_DIR}/{comp.id}.png",
        channels=[
            CompositeChannel(
                color=ch.color,
                detector=ch.detector,
                wavelength_um=ch.wavelength_um,
                wavelength_min_um=ch.wavelength_min_um,
                wavelength_max_um=ch.wavelength_max_um,
                frame_ids=ch.frame_ids,
            )
            for ch in comp.channels
        ],
        notes=[*comp.notes[:-1], *balance_notes, comp.notes[-1]],
    )


def provenance_note(plan: ColorPlan) -> str:
    """The ``False-color composites: ...`` provenance note of a field."""
    skipped = f" Skipped: {'; '.join(plan.skipped)}." if plan.skipped else ""
    if not plan.composites:
        return f"False-color composites: none built (infrared, not true color).{skipped}"
    count = {m: sum(c.mode == m for c in plan.composites) for m in ("detectors", "jhk")}
    return (
        f"False-color composites: {count['detectors']} 'detectors' and {count['jhk']} 'jhk' season composite(s) "
        "(infrared, not true color). detectors = full range: blue = D1 (fallback D2), green = D3 (D4), "
        "red = D6 (D5), coadds of the season's published frames. jhk = 2MASS-like: blue / green / red = coadd of "
        f"the season's downloaded exposures (including unpublished candidates) within {JHK_TOLERANCE_UM:g} um of "
        f"J 1.25 / H 1.65 / Ks 2.17 um at the field centre, else the nearest one within {JHK_FALLBACK_UM:g} um. "
        "Each channel: one weight per frame, sky removed, bad pixels left out (saturated cores drawn white, for "
        "display only). Green spans 2 sigma below the sky to the bright end of its usable pixels; red and blue are "
        "scaled to green by the median field-star flux ratio (target halo excluded), so typical field stars look "
        "white; limits shared by every season with the same detectors; colour-preserving asinh (Lupton et al. "
        f"2004).{skipped}"
    )


def write_composites(
    field_dir: Path, final: Sequence[GridFrame], pool: Sequence[GridFrame]
) -> tuple[list[Composite], str]:
    """Write ``color/<mode>_S<season>.png`` under ``field_dir``; return the contract objects and the note.

    Old composite PNGs are removed first, so a rebuild never leaves stale images.
    """
    plan = plan_composites(final, pool)
    out = field_dir / COLOR_DIR
    for old in out.glob("*.png") if out.is_dir() else ():
        old.unlink()
    if plan.composites:
        out.mkdir(parents=True, exist_ok=True)
    balance = color_balance(plan.composites)
    for comp in plan.composites:
        Image.fromarray(composite_rgb(comp, balance.stretches)).save(out / f"{comp.id}.png", optimize=True)
    return [_to_contract(c, balance.notes[c.id]) for c in plan.composites], provenance_note(plan)
