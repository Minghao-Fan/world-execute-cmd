"""Terminal preview renderer: source frame <-> terminal grid, side by side.

Usage:
    python preview_term.py [--t0 6] [--out output/live/term_t006.png]
                           [--cols 160] [--rows 46] [--chat 0]
                           [--dot-offset 16.0] [--dot-cap 170.0]

Produces one PNG with the source frame on the left and the terminal rendering
(one 8x16 cell per grid char, scaled 2x) on the right, so every graphic can be
judged intent-vs-result at a glance.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PKG = SRC / "world_execute_replica"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--t0", type=float, default=6.0)
    ap.add_argument("--out", type=str, default="")
    ap.add_argument("--cols", type=int, default=160)
    ap.add_argument("--rows", type=int, default=46)
    ap.add_argument("--chat", type=int, default=0)
    ap.add_argument("--dot-offset", type=float, default=16.0)
    ap.add_argument("--dot-cap", type=float, default=170.0)
    ap.add_argument("--gamma", type=float, default=0.62)
    a = ap.parse_args()

    sys.path.insert(0, str(PKG))
    import _compat  # noqa: F401
    from world_execute_replica.live.player import _patch_fast
    from world_execute_replica.live.terminal import (TermScreen, _TEXTS, install_text_capture,
                                                     pad_text)
    import world_execute_replica.tui.continuity.timeline as tlm

    _patch_fast()
    install_text_capture()

    n = round(a.t0 * 24)
    img = tlm.frame(n)
    texts = _TEXTS[:]
    _TEXTS.clear()

    # source frame (captured texts darkened -> what the player actually sees)
    from world_execute_replica.live.terminal import TermScreen as TS
    scr = TS(a.cols, a.rows, 0, a.chat, mode="braille",
             dot_offset=a.dot_offset, dot_cap=a.dot_cap, gamma=a.gamma)
    img_dark = scr._strip_texts(img, texts) if texts else img

    import world_execute_replica.tui.engine.core as engine
    ct = engine.chrome_texts(t=a.t0, chapter=engine.chapter_at(a.t0), alert="")
    chrome = ct["title"].ljust(42) + ct["mid"].ljust(60) + ct["right"].ljust(58)
    chrome_top = pad_text(chrome, a.cols) if chrome else ""

    chat_lines = []
    lines = scr.render_lines(img, chat_lines, chrome_top=chrome_top, texts=texts)

    out = ROOT / "output" / "live"
    out.mkdir(parents=True, exist_ok=True)
    name = a.out or f"term_t{int(a.t0 * 10):04d}.png"
    dst = Path(a.out) if a.out else out / name
    _compose(dst, img_dark, lines, a.cols, a.rows)
    print(f"saved {dst}  (n={n}, texts={len(texts)})")
    return 0


def _compose(dst: Path, src_img, lines: list[str], cols: int, rows: int) -> None:
    """Source frame left, terminal render right (2x cell = 16x32 px)."""
    from PIL import Image, ImageDraw, ImageFont

    CW, CH = 8, 16
    scale = 2
    term_w, term_h = cols * CW * scale, rows * CH * scale
    src_w, src_h = src_img.size
    padx, pady = 24, 24
    total = Image.new("RGB", (src_w + padx + term_w, src_h + pady), (14, 12, 8))
    total.paste(src_img.convert("RGB"), (0, 0))
    d = ImageDraw.Draw(total)

    segui = r"C:\Windows\Fonts\seguisym.ttf"
    fchar = None
    try:
        fchar = ImageFont.truetype(segui, CH * scale)
    except Exception:
        pass

    fg = (255, 176, 0)
    bg = (8, 6, 4)
    for r, line in enumerate(lines):
        x0 = src_w + padx
        y0 = r * CH * scale
        d.rectangle([x0, y0, x0 + term_w, y0 + CH * scale - 1], fill=bg)
        i = 0
        # strip the trailing ESC[K and \r\n / \r
        body = line
        if "\x1b[K" in body:
            body = body.split("\x1b[K")[0]
        while i < len(body):
            if body[i] == "\x1b":
                j = body.find("m", i)
                if j < 0:
                    break
                seq = body[i + 2:j]
                parts = seq.split(";")
                if parts[0] == "38" and len(parts) >= 5:
                    fg = tuple(int(x) for x in parts[2:5])
                if parts[0] == "48" and len(parts) >= 5:
                    bg = tuple(int(x) for x in parts[2:5])
                i = j + 1
                continue
            ch = body[i]
            i += 1
            c = body[:i].count("\x1b")  # unused, keep simple
            col = _col_of(body, i - 1)
            cx = x0 + col * CW * scale
            if fchar is not None:
                try:
                    d.text((cx, y0), ch, font=fchar, fill=fg)
                except Exception:
                    pass
    total.save(dst)


def _col_of(body: str, idx: int) -> int:
    """Column index of the character at body[idx] (skips escape sequences)."""
    col = 0
    i = 0
    while i < idx:
        if body[i] == "\x1b":
            j = body.find("m", i)
            if j < 0:
                break
            i = j + 1
            continue
        col += 1
        i += 1
    return col


if __name__ == "__main__":
    sys.exit(main())
