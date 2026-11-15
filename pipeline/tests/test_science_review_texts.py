"""Guards for the paste-ready texts of the WS3 scientific review in ``docs/SCIENCE.md``.

Other workstreams paste these texts into the app, the README and the submission. The validation numbers
of the five challenge targets were measured offline on the SPHEREx FITS files, and the published product
does not show them yet, so every paste-ready text that quotes one must say "offline" (``docs/SCIENCE.md``
§4). The tests skip once the review section is removed from the document.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

SCIENCE_MD = Path(__file__).resolve().parents[2] / "docs" / "SCIENCE.md"
REVIEW_HEADING = "## Revisión científica de textos"
BLOCKS_HEADING = "### Textos listos para pegar"
LIVE_CHECKS_HEADING = "### Comprobaciones en vivo"

# Numbers from the five validation records (docs/SCIENCE.md §0.0), as the English paste-ready texts write them.
MEASURED = re.compile(
    r"1\.66|10\.2″|1\.03 p|8\.4–8\.5″|~?260[- ]d|~260|0\.5–1\.3|(about|~) ?1(\.0)? mag|ten arcseconds"
)
SEVERITIES = ("bloquea", "importante", "menor")


def _review() -> str:
    text = SCIENCE_MD.read_text(encoding="utf-8")
    if REVIEW_HEADING not in text:
        pytest.skip("docs/SCIENCE.md has no scientific review section")
    return text[text.index(REVIEW_HEADING) :]


def _table_rows(review: str) -> list[list[str]]:
    """Cells of the findings table: file:line, current text, problem, suggested text, severity, owner."""
    lines = review.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("| archivo:línea |"))
    rows = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        assert len(cells) == 6, f"table row with {len(cells)} cells: {line[:80]}"
        rows.append(cells)
    return rows


def _blocks(review: str) -> dict[str, str]:
    """Fenced paste-ready blocks keyed by their label (A1, A2, A2b, ...)."""
    section = review[review.index(BLOCKS_HEADING) : review.index(LIVE_CHECKS_HEADING)]
    blocks: dict[str, str] = {}
    label = None
    fence: list[str] | None = None
    for line in section.splitlines():
        if fence is not None:
            if line.startswith("```"):
                assert label is not None
                blocks[label] = "\n".join(fence)
                fence = None
            else:
                fence.append(line)
        elif line.startswith("```"):
            fence = []
        elif m := re.match(r"\*\*(A\d+b?)\.", line):
            label = m.group(1)
    return blocks


def test_review_has_its_tables_and_blocks() -> None:
    review = _review()
    assert len(_table_rows(review)) > 30
    assert {"A1", "A2", "A2b", "A3", "A4", "A5", "A6"} <= set(_blocks(review))


def test_paste_ready_blocks_that_quote_a_validation_number_say_offline() -> None:
    blocks = _blocks(_review())
    quoting = {k: v for k, v in blocks.items() if MEASURED.search(v)}
    assert {"A2", "A2b", "A4", "A5"} <= set(quoting)
    missing = [k for k, v in quoting.items() if "offline" not in v]
    assert not missing, f"blocks quote validation numbers without saying 'offline': {missing}"


def test_suggested_texts_that_quote_a_validation_number_say_offline() -> None:
    missing = [row[0] for row in _table_rows(_review()) if MEASURED.search(row[3]) and "offline" not in row[3]]
    assert not missing, f"suggested texts quote validation numbers without saying 'offline': {missing}"


def test_summary_does_not_claim_the_app_shows_the_validation() -> None:
    a4 = _blocks(_review())["A4"]
    assert "We tested it" not in a4
    assert "not yet visible in the app" in a4


def _vfacts(block: str) -> list[tuple[str, str, str | None, str]]:
    facts = []
    for node in ast.walk(ast.parse(block)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_vfact":
            label, value, unit, source = (ast.literal_eval(a) for a in node.args)
            facts.append((label, value, unit, source))
    return facts


def test_spherex_facts_render_their_unit_after_a_bare_number() -> None:
    # BodyPanel.tsx shows a fact as f"{value} {unit}": with a unit, the value must be the number alone.
    facts = _vfacts(_blocks(_review())["A5"])
    assert len(facts) >= 5
    for label, value, unit, source in facts:
        assert "offline" in source, label
        if unit is not None:
            assert not re.search(r"[A-Za-zµ]", value), f"{label}: '{value} {unit}' puts the unit after text"


def test_severity_counts_match_the_table() -> None:
    review = _review()
    rows = _table_rows(review)
    counts = {s: sum(1 for r in rows if r[4] == s) for s in SEVERITIES}
    assert sum(counts.values()) == len(rows), "a row has an unknown severity"
    m = re.search(r"(\d+)\s+filas:\s+(\d+)\s+bloquean,\s+(\d+)\s+son\s+importantes\s+y\s+(\d+)\s+menores", review)
    assert m, "the review must state its row and severity counts"
    assert [int(g) for g in m.groups()] == [len(rows), *counts.values()]
