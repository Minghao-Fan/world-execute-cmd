"""Crop-compare: source region vs terminal region, side by side, enlarged.

Usage:
    python crop_compare.py --t0 6 --box "520,120,780,520" --out output/live/crop_globe.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "world_execute_replica"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--t0", type=float, default=6.0)
    ap.add_argument("--box", type=str, required=True)          # x0,y0,x1,y1 source px
    ap.add_argument("--out", type=str, required=True)
    ap.add_argument("--cols", type=int, default=160)
    ap.add_argument("--rows", type=int, default=46)
    ap.add_argument("--chat", type=int, default=0)
    ap.add_argument("--dot-offset", type=float, default=16.0)
    ap.add_argument("--dot-cap", type=float, default=170.0)
    ap.add_argument("--gamma", type=float, default=0.62)
    a = ap.parse_args()
    x0, y0, x1, y1 = (int(v) for v in a.box.split(","))

    sys.path.insert(0, str(PKG))
    import _compat  # noqa: F401
    from world_execute_replica.live.player import _patch_fast
    from world_execute_replica.live.terminal import (TermScreen, _TEXTS, install_text_capture,
                                                     pad_text)
    import world_execute_replica.tui.continuity.timeline as tlm
    import world_execute_replica.tui.engine.core as engine

    _patch_fast()
    install_text_capture()
    n = round(a.t0 * 24)
    img = tlm.frame(n)
    texts = _TEXTS[:]
    _TEXTS.clear()

    scr = TermScreen(a.cols, a.rows, 0, a.chat, mode="braille",
                     dot_offset=a.dot_offset, dot_cap=a.dot_cap, gamma=a.gamma)
    img_dark = scr._strip_texts(img, texts) if texts else img
    ct = engine.chrome_texts(t=a.t0, chapter=engine.chapter_at(a.t0), alert="")
    chrome = ct["title"].ljust(42) + ct["mid"].ljust(60) + ct["right"].ljust(58)
    chrome_top = pad_text(chrome, a.cols) if chrome else ""
    lines = scr.render_lines(img, [], chrome_top=chrome_top, texts=texts)

    from PIL import Image, ImageDraw, ImageFont
    CW, CH, S = 8, 16, 2
    term_w = a.cols * CW * S
    total = Image.new("RGB", (1280 + 24 + term_w, 720 + 24), (14, 12, 8))
    total.paste(img_dark.convert("RGB"), (0, 0))
    d = ImageDraw.Draw(total)
    fchar = None
    try:
        fchar = ImageFont.truetype(r"C:\Windows\Fonts\seguisym.ttf", CH * S)
    except Exception:
        pass
    fg, bg = (255, 176, 0), (8, 6, 4)
    for r, line in enumerate(lines):
        xp = 1280 + 24
        yp = r * CH * S
        d.rectangle([xp, yp, xp + term_w, yp + CH * S - 1], fill=bg)
        body = line.split("\x1b[K")[0]
        i = 0
        while i < len(body):
            if body[i] == "\x1b":
                j = body.find("m", i)
                if j < 0:
                    break
                parts = body[i + 2:j].split(";")
                if parts[0] == "38" and len(parts) >= 5:
                    fg = tuple(int(x) for x in parts[2:5])
                if parts[0] == "48" and len(parts) >= 5:
                    bg = tuple(int(x) for x in parts[2:5])
                i = j + 1
                continue
            ch = body[i]
            i += 1
            col = 0
            k = 0
            while k < i - 1:
                if body[k] == "\x1b":
                    jj = body.find("m", k)
                    k = jj + 1 if jj >= 0 else len(body)
                    continue
                col += 1
                k += 1
            if fchar is not None:
                try:
                    d.text((xp + col * CW * S, yp), ch, font=fchar, fill=fg)
                except Exception:
                    pass

    src_crop = img_dark.convert("RGB").crop((x0, y0, x1, y1))
    c0, c1 = x0 * a.cols // 1280, x1 * a.cols // 1280
    r0, r1 = y0 * a.rows // 720, y1 * a.rows // 720
    tx0 = 1280 + 24 + c0 * CW * S
    ty0 = r0 * CH * S
    tx1 = 1280 + 24 + c1 * CW * S
    ty1 = r1 * CH * S
    term_crop = total.crop((tx0, ty0, tx1, ty1))

    H = 620
    s1 = src_crop.resize((int(src_crop.width * H / max(1, src_crop.height)), H), Image.LANCZOS)
    t1 = term_crop.resize((int(term_crop.width * H / max(1, term_crop.height)), H), Image.LANCZOS)
    pad = 18
    out = Image.new("RGB", (s1.width + pad + t1.width, H), (12, 10, 7))
    out.paste(s1, (0, 0))
    out.paste(t1, (s1.width + pad, 0))
    dst = ROOT / a.out if a.out.startswith("output") else ROOT / "output" / "live" / Path(a.out).name
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst)
    print(f"saved {dst}  src={src_crop.size} term={term_crop.size} texts={len(texts)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
