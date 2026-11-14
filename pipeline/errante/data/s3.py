"""Public S3 mirror of the SPHEREx archive: s3://nasa-irsa-spherex (WS1).

Anonymous HTTPS works with no AWS account (verified 2026-11-14):
  https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/?list-type=2&prefix=...&delimiter=/
Layout:  <release>/level2/<week>/<pipeline-version>/<detector>/<file>.fits
  e.g.   dr1/level2/2025W19_2B/l2b-v27-2026-198/1/
         level2_2025W19_2B_0007_1D1_spx_l2b-v27-2026-198.fits   (~66 MB)
File name = level2_<OBSID>D<detector>_spx_<pipeline-version>.fits
S3 cannot search by sky position: use IRSA TAP/SIA (data/irsa.py) to find
which files cover a position, then download from S3 or IRSA (or cut out).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import requests

from .. import settings

_NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
_FILE_RE = re.compile(
    r"level2_(?P<obsid>(?P<week>\d{4}W\d{2}_\w{2})_(?P<seq>\d{4})_(?P<exp>\d+))D(?P<det>[1-6])"
    r"_spx_(?P<ver>[\w-]+)\.fits$"
)


@dataclass(frozen=True)
class S3Key:
    key: str
    release: str
    week: str
    obs_id: str
    detector: int
    pipeline_version: str

    @property
    def url(self) -> str:
        return f"{settings.S3_HTTPS}/{self.key}"


def parse_key(key: str) -> S3Key:
    m = _FILE_RE.search(key)
    if not m:
        raise ValueError(f"Not a SPHEREx level2 key: {key}")
    return S3Key(
        key=key,
        release=key.split("/", 1)[0],
        week=m["week"],
        obs_id=m["obsid"],
        detector=int(m["det"]),
        pipeline_version=m["ver"],
    )


def list_prefix(prefix: str, delimiter: str | None = "/", max_keys: int = 1000) -> tuple[list[str], list[str]]:
    """One page of an anonymous S3 listing: (sub_prefixes, keys)."""
    params = {"list-type": "2", "prefix": prefix, "max-keys": str(max_keys)}
    if delimiter:
        params["delimiter"] = delimiter
    r = requests.get(settings.S3_HTTPS + "/", params=params, timeout=settings.HTTP_TIMEOUT_S)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    prefixes = [e.text or "" for e in root.findall("s3:CommonPrefixes/s3:Prefix", _NS)]
    keys = [e.text or "" for e in root.findall("s3:Contents/s3:Key", _NS)]
    return prefixes, keys


def list_weeks(release: str = "dr1") -> list[str]:
    """Survey weeks available in a release, e.g. ['2025W17_4B', ...]."""
    prefixes, _ = list_prefix(f"{release}/level2/")
    return [p.rstrip("/").rsplit("/", 1)[-1] for p in prefixes]


def irsa_uri_to_s3_key(irsa_uri: str) -> str:
    """'ibe/data/spherex/qr2/level2/...' -> 'qr2/level2/...' (TODO(WS1): verify for dr1)."""
    return irsa_uri.split("ibe/data/spherex/", 1)[-1]
