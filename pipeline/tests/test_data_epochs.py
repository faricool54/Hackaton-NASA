"""Tests for errante.data.epochs (WS1-6): visits, seasons and per-season selection."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from errante.data import epochs, irsa
from errante.models import FrameRef

FIX = Path(__file__).parent / "fixtures" / "ws1"


def ref(mjd: float, det: int, obs: str | None = None) -> FrameRef:
    return FrameRef(obs_id=obs or f"X_{mjd:.4f}", detector=det, mjd=mjd, release="dr1")


def test_group_visits_and_seasons_on_numbers():
    mjds = [60903.0, 60903.1, 60903.2, 60904.0, 60930.0, 61110.0, 61110.05, 61135.0]
    visits = epochs.group_visits(mjds)  # 6 h = 0.25 d
    assert visits == [[60903.0, 60903.1, 60903.2], [60904.0], [60930.0], [61110.0, 61110.05], [61135.0]]
    seasons = epochs.group_seasons(list(reversed(mjds)))  # input order does not matter
    assert seasons == [[60903.0, 60903.1, 60903.2, 60904.0, 60930.0], [61110.0, 61110.05, 61135.0]]
    assert epochs.group_visits([]) == []
    assert epochs.group_seasons(mjds, gap_days=1000) == [sorted(mjds)]
    with pytest.raises(ValueError):
        epochs.group_by_gap(mjds, 0)


def test_groups_keep_original_objects():
    frames = [ref(61110.0, 1), ref(60903.0, 4), ref(60903.1, 1)]
    seasons = epochs.group_seasons(frames)
    assert [[f.mjd for f in s] for s in seasons] == [[60903.0, 60903.1], [61110.0]]
    assert seasons[0][0] is frames[1]


def test_select_per_season_spreads_over_visits():
    # One detector, one season, 5 visits of 3 frames each: k=2 -> first and last visit.
    frames = [ref(60900 + v * 5 + i * 0.01, 1) for v in range(5) for i in range(3)]
    picked = epochs.select_per_season(frames, per_detector=2)
    assert len(picked) == 2
    visits = epochs.group_visits(frames)
    assert picked[0] in visits[0] and picked[1] in visits[-1]
    picked3 = epochs.select_per_season(frames, per_detector=3)
    assert [next(i for i, v in enumerate(visits) if p in v) for p in picked3] == [0, 2, 4]
    # More slots than visits: every visit is used before any visit gets a second frame.
    picked7 = epochs.select_per_season(frames, per_detector=7)
    per_visit = Counter(next(i for i, v in enumerate(visits) if p in v) for p in picked7)
    assert len(picked7) == 7 and set(per_visit) == {0, 1, 2, 3, 4} and max(per_visit.values()) == 2
    # Fewer frames than slots: all of them.
    assert len(epochs.select_per_season(frames, per_detector=100)) == 15
    with pytest.raises(ValueError):
        epochs.select_per_season(frames, per_detector=0)


def test_select_per_season_on_real_barnard_rows():
    rows, _ = irsa.parse_sia_votable((FIX / "barnard_sia_dr1_qr3.xml").read_bytes())
    frames = [r.ref for r in rows]
    # The fixture keeps only 14 of the 358 frames, so in-season gaps reach ~55 d; the real
    # seasons are > 100 d apart (verified live), hence a 60 d gap here.
    seasons = epochs.group_seasons(frames, gap_days=60)
    assert [len(s) for s in seasons] == [6, 4, 4]
    picked = epochs.select_per_season(frames, per_detector=1, season_gap_days=60)
    # One frame per season x detector present in that season.
    expected = sum(len({f.detector for f in s}) for s in seasons)
    assert len(picked) == expected == 14
    assert [p.mjd for p in picked] == sorted(p.mjd for p in picked)
    # Every season is represented: the first-N cut used by build.py would not do that.
    assert {next(i for i, s in enumerate(seasons) if p in s) for p in picked} == {0, 1, 2}


def test_season_summary():
    frames = [ref(60903.0, 1), ref(60903.1, 4), ref(60930.0, 1), ref(61110.0, 2)]
    assert epochs.season_summary(frames) == [
        {"mjd_min": 60903.0, "mjd_max": 60930.0, "n": 3, "visits": 2},
        {"mjd_min": 61110.0, "mjd_max": 61110.0, "n": 1, "visits": 1},
    ]
