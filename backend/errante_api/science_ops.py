"""Adapters for WS1/WS2 measurements. Called only in a bounded private child process."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path

from errante.models import (
    ComparisonImage,
    ComparisonResponse,
    MeasurementFailure,
    SkyField,
    SpectralMeasurement,
    SpectrumRequest,
    SpectrumResponse,
)


def finite(value):
    return float(value) if value is not None and math.isfinite(float(value)) else None


def spectrum(request: SpectrumRequest, field: SkyField | None = None) -> SpectrumResponse:
    from errante.science.spectra import interpret_measurements, interpretation_notes

    response = cube_spectrum(request) if request.source == "dr1_cube" else exposure_spectrum(request, field)
    response.notes.extend(
        interpretation_notes(
            interpret_measurements(
                response.points,
                unit=response.unit,
                background_subtracted=response.background_subtracted,
                static_coadd=response.static_coadd,
            )
        )
    )
    return response


def cube_spectrum(request: SpectrumRequest) -> SpectrumResponse:
    from errante.data.cube import cube_spectrum as extract
    from errante.imaging.flags import DEFAULT_BAD, FLAG_BITS, bitmask

    result = extract(request.ra, request.dec, aperture_px=request.aperture_px, with_nhits=True, with_flags=True)
    if result.unit != "MJy/sr":
        raise ValueError("Unexpected cube surface-brightness unit")
    data = result.to_dict()
    points = []
    tile = data["tile"]
    source = tile.get("irsa_url") if data["source"] == "irsa" else tile.get("url")
    bad_bits = bitmask(list(DEFAULT_BAD))
    for k, value in enumerate(data["flux"]):
        detector = data["detector"][k]
        if request.detectors and detector not in request.detectors:
            continue
        flags = []
        if k in data["blank_planes"]:
            flags.append("blank_dichroic_channel")
        if not data["valid"][k]:
            flags.append("invalid_or_missing_core")
        raw_flags = None if data["flags"] is None else data["flags"][k]
        if raw_flags is None:
            flags.append("flags_unavailable")
        else:
            flags.extend(name.lower() for name, bit in FLAG_BITS.items() if raw_flags & (1 << bit))
        clean = raw_flags is not None and raw_flags & bad_bits == 0
        points.append(
            SpectralMeasurement(
                id=f"plane-{k}",
                detector=detector,
                wavelength_um=finite(data["wavelength_um"][k]),
                bandwidth_um=finite(data["bandwidth_um"][k]),
                flux=finite(value),
                flux_err=None,
                usable=bool(data["valid"][k]) and finite(value) is not None and clean,
                flags=flags,
                source_uri=source,
                nhits=None if data["nhits"] is None else data["nhits"][k],
                n_used=data["n_used"][k],
            )
        )
    return SpectrumResponse(
        center={"ra": request.ra, "dec": request.dec},
        source="dr1_cube",
        unit="MJy/sr",
        static_coadd=True,
        points=points,
        built_at=datetime.now(UTC),
        field_id=request.field_id,
        mjd_range=data["mjd_range"],
        pixel_scale_arcsec=data["pixel_scale_arcsec"],
        aperture_px=request.aperture_px,
        background_subtracted=False,
        notes=[
            "Quick-look DR1 static coadd; no time axis or flux-uncertainty extension.",
            "Surface brightness, not background-subtracted source flux. Invalid/saturated cores stay missing.",
            "Planes 50/51 are intentionally blank dichroic channels.",
            "Usable points exclude WS2 DEFAULT_BAD flags; SOURCE alone is informational, not a bad pixel.",
            *data["notes"],
        ],
    )


def exposure_spectrum(request: SpectrumRequest, field: SkyField | None) -> SpectrumResponse:
    from errante.data.point import point_series, to_spherex_image
    from errante.imaging.photometry import APERTURE_PX, SPHEREX_ERA_MJD, measure, propagate
    from errante.models import FrameRef

    refs = None
    if field is not None:
        selected = [
            f
            for f in field.frames
            if (not request.detectors or f.detector in request.detectors)
            and (request.mjd_min is None or f.mjd >= request.mjd_min)
            and (request.mjd_max is None or f.mjd <= request.mjd_max)
        ]
        refs = [
            FrameRef(obs_id=f.obs_id, detector=f.detector, mjd=f.mjd, release=f.release, irsa_uri=f.source_uri)
            for f in selected
        ]
    motion = request.proper_motion
    pm = (motion.ra_cosdec_masyr, motion.dec_masyr, motion.epoch_mjd) if motion else None
    query_ra, query_dec = propagate(request.ra, request.dec, pm, SPHEREX_ERA_MJD)
    series = point_series(
        query_ra,
        query_dec,
        box_px=81 if pm else 25,
        detectors=request.detectors or None,
        mjd_min=request.mjd_min,
        mjd_max=request.mjd_max,
        max_frames=request.max_frames,
        max_workers=8,
        frames=refs,
        deadline_s=70,
    )
    failures = [
        MeasurementFailure(
            frame_id=f"{f.obs_id}D{f.detector}",
            reason="no_overlap" if why.startswith("NoOverlap") else "download_failed",
        )
        for f, why in series.failures
    ]
    points = []
    for sample in series.samples:
        fid = f"{sample.obs_id}D{sample.detector}"
        try:
            image = to_spherex_image(sample)
            ra, dec = propagate(request.ra, request.dec, pm, image.mjd)
            value = measure(image, ra, dec, frame_id=fid, release=sample.release)
            if value is None:
                failures.append(MeasurementFailure(frame_id=fid, reason="no_overlap"))
                continue
            flags = list(value.flags)
            if value.aperture_correction is None:
                flags.append("no_aperture_correction")
            if sample.flags is None:
                flags.append("flags_unavailable")
            if sample.variance is None:
                flags.append("variance_unavailable")
            if sample.zodi is None:
                flags.append("zodi_unavailable")
            points.append(
                SpectralMeasurement(
                    id=fid,
                    frame_id=fid,
                    detector=value.detector,
                    mjd=value.mjd,
                    release=sample.release,
                    wavelength_um=finite(value.wavelength_um),
                    bandwidth_um=finite(value.bandwidth_um),
                    flux=finite(value.flux_mjy),
                    flux_err=finite(value.flux_err_mjy),
                    flags=flags,
                    usable=value.usable and sample.flags is not None and sample.zodi is not None,
                    aperture_correction=finite(value.aperture_correction),
                    source_uri=image.source,
                    position={"ra": ra, "dec": dec},
                )
            )
        except (ValueError, OSError, KeyError, IndexError):
            failures.append(MeasurementFailure(frame_id=fid, reason="measurement_failed"))
    epochs = [p.mjd for p in points if p.mjd is not None]
    return SpectrumResponse(
        center={"ra": request.ra, "dec": request.dec},
        source="l2_exposures",
        unit="mJy",
        static_coadd=False,
        proper_motion=motion,
        points=points,
        field_id=request.field_id,
        built_at=datetime.now(UTC),
        aperture_px=APERTURE_PX,
        background_subtracted=True,
        mjd_range=(min(epochs), max(epochs)) if epochs else (None, None),
        failures=failures,
        truncated=bool(
            series.search.get("truncated")
            or series.search.get("overflow")
            or series.search.get("n_selected", 0) < series.search.get("n_found", 0)
        ),
        stale=bool(series.search.get("stale")),
        notes=[
            "Forced aperture photometry on native IMAGE - ZODI stamps, with a 4–7 pixel local sky annulus.",
            "At most the requested number of exposures, spread in time. Wavelength and epoch remain per point.",
            (
                "Linear catalog proper motion applied per exposure (mu_alpha*cos(dec), mu_delta, mas/year); no parallax or radial velocity. Predicted positions are not measured SPHEREx astrometry."
                if pm
                else "No proper-motion/parallax propagation: this measures the requested fixed sky position."
            ),
            "Coverage searched at MJD 61000; moving-source stamps are 81 pixels across. A trajectory leaving a stamp is reported as no_overlap, not a zero flux.",
            "Aperture correction uses stars in each small stamp when available; otherwise flux is uncorrected aperture flux.",
            "Negative flux is retained. Saturation, missing flags and bad pixels are excluded from usable points.",
            "A multi-epoch spectrum mixes variability and wavelength; filter dates before interpreting a spectral shape.",
        ],
    )


def comparisons(field: SkyField, output: Path, analysis_id: str) -> ComparisonResponse:
    from errante.imaging.compare import compare_field, load_from_cutouts

    meta = compare_field(field, output, load_from_cutouts(field))
    originals = {f.id: f for f in field.frames}
    coadds = {c["id"]: c for c in meta["coadds"]}
    images = []

    def bounds(ids):
        inputs = [originals[fid] for fid in ids]
        waves = [f.wavelength_um for f in inputs if f.wavelength_um is not None]
        return dict(
            frame_ids=ids,
            mjd_min=min(f.mjd for f in inputs),
            mjd_max=max(f.mjd for f in inputs),
            wavelength_range_um=(min(waves), max(waves)) if waves else None,
        )

    failures = []
    for c in meta["coadds"]:
        images.append(
            ComparisonImage(
                id=c["id"],
                kind="weighted_mean",
                detector=c["detector"],
                season=c["season"],
                image=f"analyses/{analysis_id}/{c['image']}",
                valid_fraction=c["valid_fraction"],
                **bounds(c["frame_ids"]),
            )
        )
        failures.extend(MeasurementFailure(frame_id=fid, reason="invalid_pixels") for fid in c["skipped_frame_ids"])
    used = {fid for image in images for fid in image.frame_ids}
    failures.extend(
        MeasurementFailure(frame_id=fid, reason="download_failed")
        for fid in originals.keys() - used
        if fid not in {f.frame_id for f in failures}
    )
    for d in meta["differences"]:
        ids = list(dict.fromkeys(coadds[d["earlier"]]["frame_ids"] + coadds[d["later"]]["frame_ids"]))
        images.append(
            ComparisonImage(
                id=d["id"],
                kind="scaled_difference",
                detector=d["detector"],
                earlier=d["earlier"],
                later=d["later"],
                image=f"analyses/{analysis_id}/{d['image']}",
                flux_scale=d["flux_scale"],
                flux_scale_fitted=d["flux_scale_fitted"],
                flux_scale_stars=d["flux_scale_stars"],
                noise_mjy_sr=finite(d["noise_mjy_sr"]),
                display_limit_mjy_sr=d["limit_mjy_sr"],
                target_exclude_px=d["target_exclude_px"],
                notes=d["notes"],
                **bounds(ids),
            )
        )
    return ComparisonResponse(
        id=analysis_id,
        field_id=field.id,
        field_built_at=field.provenance.built_at,
        built_at=datetime.now(UTC),
        method=meta["method"],
        input_frames=field.frames,
        images=images,
        failures=failures,
        notes=[
            *meta["limitations"],
            "Individual coadd weights are not exported by WS2 (weights=null).",
            *[f"Skipped comparison {x['id']}: {x['reason']}" for x in meta["skipped"]],
        ],
    )
