"""Live checks against real services. Run with: ERRANTE_NETWORK_TESTS=1 pytest -m network"""

import os

import pytest

pytestmark = [
    pytest.mark.network,
    pytest.mark.skipif(os.environ.get("ERRANTE_NETWORK_TESTS") != "1", reason="set ERRANTE_NETWORK_TESTS=1"),
]


def test_s3_has_dr1_weeks():
    from errante.data.s3 import list_weeks

    weeks = list_weeks("dr1")
    assert weeks and weeks[0].startswith("2025W")


@pytest.mark.xfail(raises=NotImplementedError, reason="WS1: implement irsa.search_frames")
def test_irsa_finds_frames_for_barnards_star():
    from errante.data.irsa import search_frames

    res = search_frames(269.4463, 4.7665)
    assert len(res.frames) > 10
