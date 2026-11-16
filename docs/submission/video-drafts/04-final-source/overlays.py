"""Section headlines and on-screen captions over a verified montage (team request: reference promo style).

Usage: python overlays.py "internal/04 - Errante final" OUT.mp4
Reads the video's locucion/timings.json and the OVERLAYS table below, renders one transparent 1920x1080 PNG
per row with Pillow (kicker + headline card top-left, caption pill bottom-center, accent words in **bold**),
and composites them with ffmpeg (fade + slide-up). Audio and container metadata are copied unchanged.
"""
import json
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
FONTS = Path("C:/Windows/Fonts")
BOLD = str(FONTS / "segoeuib.ttf")
SEMI = str(FONTS / "seguisb.ttf")
WHITE = (241, 245, 249, 255)
ACCENT = (103, 232, 249, 255)       # cyan, matches the hook gradient start
KICKER = (165, 180, 252, 255)       # indigo, matches the hook subline
PANEL = (6, 10, 26, 214)
BORDER = (125, 211, 252, 96)

# row -> (kicker, headline lines, caption). None = no overlay for that row.
OVERLAYS = {
    1: None,  # the hook already carries its animated title
    2: ("ANY POINT IN THE SKY", ["Pick a point.", "Build it **live**."],
        "Pick any point, and Errante builds its sequence **from the archive**."),
    3: ("TIME · REAL SPHEREx FRAMES", ["Real frames.", "**Real** change."],
        "After a cut for the build, its real frames blink **in false color**."),
    4: ("OBJECT · CATALOG CONTEXT", ["Every star,", "**with its sources**."],
        "Hover a Gaia star, click it, and read its **catalog facts**."),
    5: ("3D · CATALOG MODEL", ["From catalog", "to **3D**."],
        "Then explore it in 3D, **from catalog values**."),
    6: (None, None, "Errante. **Explore the changing sky.**"),
}


def segments(text):
    """'a **b** c' -> [('a ', False), ('b', True), (' c', False)]"""
    parts = text.split("**")
    return [(p, i % 2 == 1) for i, p in enumerate(parts) if p]


def draw_rich(draw, xy, text, font, color=WHITE, accent=ACCENT):
    x, y = xy
    for seg, hot in segments(text):
        draw.text((x, y), seg, font=font, fill=accent if hot else color)
        x += draw.textlength(seg, font=font)
    return x


def rich_width(draw, text, font):
    return sum(draw.textlength(seg, font=font) for seg, _ in segments(text))


def render(row, spec, out):
    kicker, lines, caption = spec
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if lines:
        kf = ImageFont.truetype(SEMI, 21)
        hf = ImageFont.truetype(BOLD, 58)
        pad, gap = 30, 8
        kw = d.textlength("●  " + kicker, font=kf) * 1.08
        hw = max(rich_width(d, ln, hf) for ln in lines)
        bw = int(max(kw, hw) + 2 * pad)
        bh = int(pad + 28 + 14 + len(lines) * (66 + gap) + pad - gap)
        x0, y0 = 24, 62
        d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), radius=24, fill=PANEL, outline=BORDER, width=2)
        cx = x0 + pad
        for ch in "●  " + kicker:  # letter-spaced kicker
            d.text((cx, y0 + pad), ch, font=kf, fill=ACCENT if ch == "●" else KICKER)
            cx += d.textlength(ch, font=kf) * 1.08
        ty = y0 + pad + 28 + 14
        for ln in lines:
            draw_rich(d, (x0 + pad, ty), ln, hf)
            ty += 66 + gap
    if caption:
        cf = ImageFont.truetype(SEMI, 40)
        tw = rich_width(d, caption, cf)
        px, py = 34, 18
        bw, bh = int(tw + 2 * px), 40 + 2 * py + 8
        x0 = (W - bw) // 2
        y0 = H - 70 - bh
        d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), radius=bh // 2, fill=PANEL, outline=BORDER, width=2)
        draw_rich(d, (x0 + px, y0 + py - 2), caption, cf)
    img.save(out)


def main(video_dir, out_mp4):
    video_dir = Path(video_dir)
    course = video_dir.parent.parent
    base = course / "export" / video_dir.name / f"{video_dir.name}.mp4"
    rows = json.loads((video_dir / "locucion/timings.json").read_text(encoding="utf-8"))["rows"]
    work = video_dir / "overlays"
    work.mkdir(exist_ok=True)
    inputs, chains, last, n_png = [], [], "0:v", 0
    for r in rows:
        spec = OVERLAYS.get(r["row"])
        if not spec:
            continue
        png = work / f"row-{r['row']:02d}.png"
        render(r["row"], spec, png)
        a = r["visual_start"] + 0.12
        b = r["visual_start"] + r["visual_dur"] - 0.05
        n_png += 1
        idx = n_png
        inputs +=["-loop", "1", "-t", f"{b + 0.1:.3f}", "-i", str(png)]
        lab = f"o{idx}"
        chains.append(f"[{idx}:v]format=rgba,fade=in:st={a:.3f}:d=0.35:alpha=1,"
                      f"fade=out:st={b - 0.25:.3f}:d=0.25:alpha=1[{lab}]")
        nxt = f"v{idx}"
        y = f"'if(lt(t,{a:.3f}+0.35),18*(1-max(0,t-{a:.3f})/0.35),0)'"
        chains.append(f"[{last}][{lab}]overlay=x=0:y={y}:eval=frame:"
                      f"enable='between(t,{a:.3f},{b:.3f})'[{nxt}]")
        last = nxt
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ff, "-v", "error", "-y", "-i", str(base), *inputs, "-filter_complex", ";".join(chains),
           "-map", f"[{last}]", "-map", "0:a", "-map_metadata", "0", "-c:v", "libx264", "-preset", "medium",
           "-crf", "17", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "copy", "-movflags", "+faststart",
           "-metadata:s:a:0", "language=eng", str(out_mp4)]
    subprocess.run(cmd, check=True)
    print(f"OK {out_mp4}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
