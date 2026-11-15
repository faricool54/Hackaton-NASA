import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import guion
from guion import find_vigente, frontmatter_value, parse_montage, video_rate

SHEET = """---
version: 2
vigente: true
velocidad: '+5%'
titulo: "Con: dos puntos"
vacio:
---
## {heading}

| # | Locución | Imagen | Entra | Sale | Dur. |
|---|---|---|---|---|---|
| 1 | Hola. 0.5s Esto es **AcmeOS** con `código`. | 🖼️ Slide 1 | | | |
| 2 | Un clic. | 🎬 D3a [0:01.5–0:04] | | | |
| 3 | Zoom lento. | 🖼️ Slide 2 · zoom | | | |

## Otra tabla
| 9 | no es parte | Slide 9 | | | |
"""


def write(tmp_path, text, name="guion-v1.md"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.parametrize("heading", ["Hoja de montaje", "Montage sheet"])
def test_parse_montage_in_both_languages(tmp_path, heading):
    rows = parse_montage(write(tmp_path, SHEET.format(heading=heading)))
    assert [r.num for r in rows] == [1, 2, 3]
    assert rows[0].locucion == "Hola. 0.5s Esto es AcmeOS con código."
    assert rows[0].parts == [("Hola.", 0.5), ("Esto es AcmeOS con código.", 0.0)]
    assert (rows[1].visual.kind, rows[1].visual.ref, rows[1].visual.trim) == ("demo", "D3a", (1.5, 4.0))
    assert rows[2].visual.zoom and not rows[0].visual.zoom


def test_no_sheet_and_empty_row_are_errors(tmp_path):
    with pytest.raises(SystemExit, match="no montage sheet"):
        parse_montage(write(tmp_path, "# nada"))
    with pytest.raises(SystemExit, match="empty"):
        parse_montage(write(tmp_path, "## Hoja de montaje\n| 1 |  | Slide 1 | | | |\n"))


def test_a_row_without_a_visual_is_an_error(tmp_path):
    with pytest.raises(SystemExit, match="no visual"):
        parse_montage(write(tmp_path, "## Hoja de montaje\n| 1 | Hola | nada | | | |\n"))


def test_two_visuals_keeps_the_first(tmp_path, capsys):
    rows = parse_montage(write(tmp_path, "## Hoja de montaje\n| 1 | Hola | D2 o Slide 4 | | | |\n"))
    assert rows[0].visual.ref == "D2" and "more than one visual" in capsys.readouterr().out


def test_find_vigente_accepts_both_names_and_keys(tmp_path):
    write(tmp_path, "---\nvigente: false\n---\n", "guion-v1.md")
    current = write(tmp_path, "---\ncurrent: true\n---\n", "script-v2.md")
    assert find_vigente(tmp_path) == current


@pytest.mark.parametrize("files", [{}, {"guion-v1.md": "vigente: true", "guion-v2.md": "vigente: true"}])
def test_find_vigente_needs_exactly_one(tmp_path, files):
    for name, text in files.items():
        write(tmp_path, f"---\n{text}\n---\n", name)
    with pytest.raises(SystemExit, match="exactly one"):
        find_vigente(tmp_path)


def test_frontmatter_values(tmp_path):
    path = write(tmp_path, SHEET.format(heading="Hoja de montaje"))
    assert frontmatter_value(path, "velocidad") == "+5%"
    assert frontmatter_value(path, "titulo") == "Con: dos puntos"
    assert frontmatter_value(path, "vacio", "x") == "x" and frontmatter_value(path, "falta", "y") == "y"
    assert frontmatter_value(write(tmp_path, "sin frontmatter", "b.md"), "velocidad", "+0%") == "+0%"


def test_video_rate_prefers_the_script_then_the_course(tmp_path):
    assert video_rate(write(tmp_path, "---\nspeed: '+8%'\n---\n", "a.md"), "+0%") == "+8%"
    assert video_rate(write(tmp_path, "---\nversion: 1\n---\n", "b.md"), "+2%") == "+2%"


def test_flag_value():
    assert guion.flag_value(["v", "--out", "x.mp4"], "--out") == "x.mp4"
    assert guion.flag_value(["v", "--out"], "--out", "d") == "d"
    assert guion.flag_value(["v"], "--out") is None


def test_pauses_only_catch_short_markers_and_keep_leading_ones(tmp_path):
    rows = parse_montage(write(tmp_path, "## Hoja de montaje\n"
                                         "| 1 | Los 1990s pasaron. 0.5s Y 10s después. | Slide 1 | | | |\n"
                                         "| 2 | 2s Hola. | Slide 1 | | | |\n"
                                         "| 3 | 3s | Slide 2 | | | |\n"))
    assert rows[0].parts == [("Los 1990s pasaron.", 0.5), ("Y 10s después.", 0.0)]
    assert rows[1].parts == [("", 2.0), ("Hola.", 0.0)]
    assert rows[2].parts == [("", 3.0)]
