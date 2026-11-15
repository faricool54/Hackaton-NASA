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
removed, bad pixels left out. The flagged pixels' display values (saturated cores
and detector defects that ``reproject_to_grid`` repaired, ramp-fit errors on a
star kept as recorded) only fill the holes of the displayed image.

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
its colour instead of clipping to white. A noisy channel (pixel noise above
``NOISY_FRACTION`` of its balanced range, e.g. D6 from two frames) gets its black
point raised to its sky + ``NOISY_BLACK_SIGMAS`` x its pixel noise, so its speckle
goes black instead of covering the picture in coloured dots; if the target is not
detected in that channel (aperture S/N below ``TARGET_MIN_SNR``) the composite
says so. Detector composites say when the field's seasons use different detectors
(fallbacks): their colours can then differ for instrumental reasons. Exposures listed
in ``CURATED_FRAME_CAVEATS`` (artifacts checked by eye, not an automatic test) add
their caveat to every composite that uses them. Pixels with no colour information
are drawn neutral: a pixel that is bad in every frame of a channel (a saturated core,
a detector defect, a ramp-fit error) takes the brightest channel's value, so a
saturated core is white, and pixels that only some channels cover are grey.
Pixels without data in all three channels are transparent.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
from PIL import Image

from ..detect.difference import StarScale, star_flux_scale
from ..models import Composite, CompositeChannel, Stretch
from .compare import Coadd, GridFrame, Stack, target_exclusion, weighted_stack
from .render import field_stretches
from .snrcheck import blank_noise, blank_positions, measure

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
# A channel whose pixel noise exceeds this fraction of its colour-balanced range is NOISY: a 2-sigma speckle
# would reach ~25 % brightness, so its black point is raised (``NOISY_BLACK_SIGMAS``) and it gets a note.
# Measured 2026-11-14 on the real golden fields (pixel-difference noise / range): D6 0.015 (Barnard, RW Aur),
# 0.034-0.049 (eps Indi B, R Dra D5), 0.10-0.11 (WISE 0855); every green and blue channel <= 0.01. Rebuilt 2026-11-15:
# only the D6 channels of eps Indi B (0.04-0.05) and WISE 0855 (0.10-0.11) are NOISY.
NOISY_FRACTION = 0.03
# A noisy channel's black point: its sky + this many pixel sigmas, so its noise speckle goes black. Before
# (black point ~0.3 sigma below the sky), WISE 0855's D6 made ~28 % of all pixels red-dominant.
NOISY_BLACK_SIGMAS = 2.0
# In a noisy channel the target counts as not detected below this aperture S/N (5x5 px at the field centre
# over the scatter of the same aperture on blank sky); the composite then says it is not significantly detected
# there, which is not evidence that it is absent (few frames: a marginal signal stays indistinguishable from noise).
TARGET_MIN_SNR = 3.0
TARGET_SEARCH_PX = 1.5  # aperture centres this close to the field centre are tried (pointing and motion slack)
COMPLEMENT = {"red": "cyan", "green": "magenta", "blue": "yellow"}  # what a star missing that colour looks like

# CURATED caveats, checked by eye (NOT an automatic test): exposure id -> note for every composite that uses it.
# eps Indi B, 2026-11-15: both S1 D6 exposures show a band from the target that runs along the detector rows in
# the original cutouts (~35 px toward the lower right on the grid); S0, S2 and S3 (S3 has S1's patch orientation)
# show none, and no FLAGS bit (GHOST*, STREAK) marks it. Cause unknown: an artifact of the target's own light
# (ghost, charge trailing, persistence) is not ruled out, so the note does not claim one. A generic check
# (extended residual present in every frame of one season, absent in the others) also flagged real glows and
# star residuals on the other golden fields, so no automatic test is used.
_EPS_INDI_B_D6_BAND = (
    "Curated caveat (checked by eye on 2026-11-15, not an automatic test): both D6 exposures of this season "
    "(2025W40_1A_0559_1D6, 2025W44_2B_0494_1D6) show a red band about 35 px long from the target toward the lower "
    "right that no other season shows. In the original detector images it runs along the detector rows, and no "
    "SPHEREx ghost or streak flag marks it: an instrumental artifact of unknown cause, not motion of the target."
)
CURATED_FRAME_CAVEATS: dict[str, str] = {
    "2025W40_1A_0559_1D6": _EPS_INDI_B_D6_BAND,
    "2025W44_2B_0494_1D6": _EPS_INDI_B_D6_BAND,
}

FALSE_COLOR_NOTE = "False color: SPHEREx infrared wavelengths mapped to red, green and blue (infrared, not true color)."
RELATIVE_NOTE = (
    "Colours are relative to the field: typical bright field stars look roughly white and an object redder than "
    "they are looks red."
)
JHK_NOTE = (
    "2MASS-like: each channel holds narrow SPHEREx samples near J, H or Ks, not the 2MASS filters or 2MASS photometry."
)


@dataclass(frozen=True)
class Channel:
    """One colour of a composite: the coadd of its input frames."""

    color: str
    stack: Stack  # science coadd: bad pixels left out (NaN where no frame has a usable pixel)
    display: np.ndarray  # the coadd, with the flagged pixels' display values filling its holes

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
        # Clipped to [min, max]: the mean of identical floats can round one step past them, which the contract rejects.
        w = self.wavelengths
        return float(min(max(np.mean(w), min(w)), max(w))) if w else None

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


def _source(ch: Channel) -> str:
    """'D6', or 'D2+D3' for a channel that mixes detectors."""
    return f"D{ch.detector}" if ch.detector is not None else "D" + "+D".join(str(d) for d in _detectors(ch))


def _describe(ch: Channel) -> str:
    lam = ch.wavelength_um
    where = f"{lam:.2f} µm" if lam is not None else "wavelength unknown"
    return f"{ch.color} = {_source(ch)} {where}"


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
        label = f"{color} ({band} {target:g} µm)"

        def distance(f: GridFrame, target: float = target) -> float:
            return abs(f.wavelength_um - target)

        near = [f for f in known if distance(f) <= JHK_TOLERANCE_UM + _EPS_UM]
        if not near:
            nearest = min(known, key=lambda f: (distance(f), f.frame_id), default=None)
            if nearest is None or distance(nearest) > JHK_FALLBACK_UM + _EPS_UM:
                closest = f"; nearest {nearest.wavelength_um:.3f} µm" if nearest is not None else ""
                return f"jhk S{season}: no exposure within {JHK_FALLBACK_UM:g} µm of {label}{closest}"
            near = [nearest]
            fallbacks.append(
                f"{label} uses the nearest exposure, {nearest.wavelength_um:.3f} µm "
                f"({distance(nearest):.3f} µm away): none within {JHK_TOLERANCE_UM:g} µm."
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


def _with_note(comp: SeasonComposite, note: str) -> SeasonComposite:
    """``comp`` with ``note`` added before its last note (the closing 'colours are relative' note)."""
    return replace(comp, notes=(*comp.notes[:-1], note, comp.notes[-1]))


def _mixed_detectors(composites: Sequence[SeasonComposite]) -> list[SeasonComposite]:
    """Detector composites, when the field's seasons use different detectors, say that colour changes between
    them can be instrumental: on the real R Draconis field S0 is D6/D3/D1 and S1, S4 are D5/D4/D1 (fallbacks),
    so the Mira turns from yellow-green to orange between seasons partly or wholly because the wavelengths change
    (a Mira's colour also changes with its pulsation phase, which these composites cannot separate)."""
    assignment = {
        c.season: "/".join(f"D{ch.detector}" for ch in c.channels) for c in composites if c.mode == "detectors"
    }
    if len(set(assignment.values())) < 2:
        return list(composites)
    seasons: dict[str, list[int]] = defaultdict(list)
    for season, detectors in sorted(assignment.items()):
        seasons[detectors].append(season)
    listing = "; ".join(f"{', '.join(f'S{s}' for s in ss)}: {dets}" for dets, ss in seasons.items())
    note = (
        f"Seasons use different detectors (red/green/blue = {listing}): colour differences between them can be "
        "instrumental (other wavelengths), so they are not evidence of a colour change of the object."
    )
    return [_with_note(c, note) if c.mode == "detectors" else c for c in composites]


def _curated(comp: SeasonComposite) -> SeasonComposite:
    """``comp`` with the ``CURATED_FRAME_CAVEATS`` of the exposures it uses (each caveat once)."""
    used = [fid for ch in comp.channels for fid in ch.frame_ids]
    for note in dict.fromkeys(CURATED_FRAME_CAVEATS[fid] for fid in used if fid in CURATED_FRAME_CAVEATS):
        comp = _with_note(comp, note)
    return comp


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
    return ColorPlan([_curated(c) for c in _mixed_detectors(composites)], skipped)


@dataclass(frozen=True)
class Balance:
    """Display limits of every channel and how the three colours were balanced."""

    stretches: dict[tuple[str, str], Stretch]  # (composite id, colour) -> limits in MJy/sr
    ratios: dict[tuple[str, str], float | None]  # (composite id, red|blue) -> field-star flux ratio to green used
    noise: dict[tuple[str, str], float]  # (composite id, colour) -> pixel noise / colour-balanced range
    notes: dict[str, list[str]]  # composite id -> plain-language colour-balance notes
    # (composite id, colour) of a NOISY channel -> target aperture S/N at the field centre (None: not measurable)
    target_snr: dict[tuple[str, str], float | None]


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


def _is_noisy(fraction: float) -> bool:
    return bool(np.isfinite(fraction) and fraction > NOISY_FRACTION)


def _speckle_black_point(stretch: Stretch, sky: float, sigma: float) -> Stretch:
    """``stretch`` with its black point raised to sky + ``NOISY_BLACK_SIGMAS`` x ``sigma``; the white point stays
    (pushed up only if it would not stay ``sigma`` above the new black point)."""
    vmin = sky + NOISY_BLACK_SIGMAS * sigma
    return stretch.model_copy(update={"vmin": vmin, "vmax": max(stretch.vmax, vmin + sigma)})


def _target_snr(ch: Channel, disc: tuple[float, float, float]) -> float | None:
    """Aperture S/N of the target in ``ch``: the brightest 5x5 aperture (above its 4-7 px sky ring) centred within
    ``TARGET_SEARCH_PX`` of the field centre, over the robust scatter of the same aperture on blank sky outside
    ``disc`` (``snrcheck``; that scatter includes correlated noise). None when it cannot be measured: an
    aperture pixel without data (e.g. a saturated core) or too few blank apertures."""
    data = ch.stack.data.astype(np.float64)
    ny, nx = data.shape
    cx, cy = (nx - 1) / 2, (ny - 1) / 2
    r = TARGET_SEARCH_PX
    centres = [
        (x, y)
        for y in range(int(np.floor(cy - r)), int(np.ceil(cy + r)) + 1)
        for x in range(int(np.floor(cx - r)), int(np.ceil(cx + r)) + 1)
        if np.hypot(x - cx, y - cy) <= r
    ]
    found = [measure(data, None, x, y) for x, y in centres]
    if not found or any(m is None for m in found):
        return None
    stack = ch.stack
    as_coadd = Coadd(ch.detector or 0, 0, ch.frame_ids, ch.mjds, stack.data, stack.variance, stack.coverage)
    sigma, _ = blank_noise(data, blank_positions(as_coadd, stack.frames, disc))
    if not (np.isfinite(sigma) and sigma > 0):
        return None
    return max(m.flux for m in found) / sigma


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
       noise is 4-9 % of its balanced span, green's 0.4-0.7 %.) A colour without any fitted season
       (fewer than ``MIN_STARS`` usable stars) keeps step 1's limits.
    3. A channel whose pixel noise exceeds ``NOISY_FRACTION`` of that range gets its black point raised to
       its sky + ``NOISY_BLACK_SIGMAS`` x its pixel noise (white point kept), so its speckle goes black
       (the sky there loses that colour; faint sources too), and a note. Its target S/N is measured: a
       target not detected there (``TARGET_MIN_SNR``) gets a note that it is not significantly detected (not evidence of absence).
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
    target_snr: dict[tuple[str, str], float | None] = {}
    for comp in composites:
        for ch in comp.channels:
            key = (comp.id, ch.color)
            sigma = _pixel_noise(ch.stack.data, skips[key])
            noise[key] = sigma / (stretches[key].vmax - stretches[key].vmin)
            if _is_noisy(noise[key]):
                stretches[key] = _speckle_black_point(stretches[key], _sky_level(ch.stack.data, skips[key]), sigma)
                target_snr[key] = _target_snr(ch, discs[comp.id])
    notes = {c.id: _balance_notes(c, ratios, noise, n_fits, target_snr) for c in composites}
    return Balance(stretches, ratios, noise, notes, target_snr)


def _balance_notes(
    comp: SeasonComposite,
    ratios: Mapping[tuple[str, str], float | None],
    noise: Mapping[tuple[str, str], float],
    n_fits: Mapping[tuple[tuple, str], int],
    target_snr: Mapping[tuple[str, str], float | None],
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
        noisy = [ch.color for ch in comp.channels if _is_noisy(noise[(comp.id, ch.color)])]
        looks = (
            f"so bright field stars look white; fainter ones look {COMPLEMENT[noisy[0]]} because the {noisy[0]} "
            "black point is raised (see below)."
            if noisy
            else "so typical field stars look white."
        )
        text = (
            f"Colour balance: {' and '.join(done)} scaled to green by the median flux ratio of the field stars "
            f"({parts}; median of {seasons} season fit(s)), {looks}"
        )
        missing = [c for c in ("red", "blue") if c not in done]
        if missing:
            text += f" {missing[0].capitalize()} could not be balanced (too few field stars); it uses its own limits."
        notes = [text]
    for ch in comp.channels:
        key = (comp.id, ch.color)
        if _is_noisy(noise[key]):
            notes.extend(_noisy_notes(ch, noise[key], target_snr.get(key)))
    return notes


def _noisy_notes(ch: Channel, fraction: float, snr: float | None) -> list[str]:
    c, source = ch.color, _source(ch)
    notes = [
        f"The {c} channel ({source}, {len(ch.frame_ids)} frame(s)) is noisy here (pixel noise {100 * fraction:.0f}% "
        f"of its colour-balanced range), so its black point is raised to {NOISY_BLACK_SIGMAS:g} sigma of that noise "
        f"above the sky: most noise specks are black, but faint {c} light is hidden too (faint field stars look "
        f"{COMPLEMENT[c]}), and isolated {c} specks that remain are mostly noise, not {c} objects."
    ]
    if snr is not None and snr < TARGET_MIN_SNR:
        notes.append(
            f"The target is not significantly detected in the {c} channel of this {len(ch.frame_ids)}-frame "
            f"{source} coadd (aperture S/N {snr:.1f} at the field centre, below {TARGET_MIN_SNR:g}). This is not "
            f"evidence that it is absent: a {c} speck at its position cannot be told apart from noise here."
        )
    return notes


def _normalised(img: np.ndarray, stretch: Stretch) -> np.ndarray:
    x = (img.astype(np.float64) - stretch.vmin) / (stretch.vmax - stretch.vmin)
    return np.clip(np.nan_to_num(x, nan=0.0), 0.0, None)


def composite_rgb(
    comp: SeasonComposite, stretches: Mapping[tuple[str, str], Stretch], softening: float = SOFTENING
) -> np.ndarray:
    """uint8 RGB image of ``comp`` (RGBA, alpha 0 where no channel has data, if there is such a pixel).

    Pixels without colour information are drawn neutral: a pixel that is bad in every frame of a channel
    (saturated core, detector defect, ramp-fit error; its display value comes from the repaired or recorded
    frames) takes the brightest channel's value, and pixels that only some channels cover are grey from those.
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
        f"the season's downloaded exposures (including unpublished candidates) within {JHK_TOLERANCE_UM:g} µm of "
        f"J 1.25 / H 1.65 / Ks 2.17 µm at the field centre, else the nearest one within {JHK_FALLBACK_UM:g} µm. "
        "Each channel: one weight per frame, sky removed, bad pixels left out; a pixel bad in every frame of a "
        "channel (saturated core, detector defect, ramp-fit error) is drawn neutral at the brightest channel's "
        "level, so saturated cores look white (display only). Green spans 2 sigma below the sky to the bright end of its usable pixels; red and blue are "
        "scaled to green by the median field-star flux ratio (target halo excluded), so typical bright field stars "
        "look white; limits shared by every season with the same detectors, except that a noisy channel (pixel "
        f"noise above {100 * NOISY_FRACTION:g}% of its range) has its black point set per season at its own sky + "
        f"{NOISY_BLACK_SIGMAS:g} sigma, so its speckle goes black (fainter field stars then look the complementary "
        f"colour); colour-preserving asinh (Lupton et al. 2004).{skipped}"
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
