"""Turn tracks into scored Candidates with plain-language notes (WS2, P1)."""

from __future__ import annotations

from ..models import Candidate
from .linking import Track


def score_tracks(tracks: list[Track], field_id: str) -> list[Candidate]:
    """Score 0-1 from: number of detections, SNR, linear-fit residual, flags hit,
    distance to bright stars / detector edges. Vet obvious artifacts
    (status='artifact') instead of dropping them, so the UI can show *why*.

    TODO(WS2): build ``Candidate`` objects (detections with sky coords via
    ``imaging.grid.png_xy_to_sky``; motion via ``science.motion.motion_from_detections``).
    Every candidate starts as status='unconfirmed'; WS3 cross-match may turn it
    into 'known'.
    """
    raise NotImplementedError("WS2: score_tracks")
