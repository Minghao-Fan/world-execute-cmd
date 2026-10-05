"""Render a mockup PNG of what the live terminal looks like (for preview only).

Full-window picture + bottom chat overlay; mode = braille (2x4 dots per cell)
or half (2 vertical pixels per cell).
"""
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "src" / "world_execute_replica"
sys.path.insert(0, str(PKG))
import _compat  # noqa: F401
import world_execute_replica.tui.continuity.timeline as timeline
import world_execute_replica.tui.engine.core as engine
from PIL import Image, ImageDraw, ImageFont

from world_execute_replica.live.terminal import TermScreen, BG, GREY
from world_execute_replica.live.chat import ChatView

FONT = "C:/Windows/Fonts/consola.ttf"
FONT_CJK = "C:/Windows/Fonts/msyh.ttc"
CELL_W, CELL_H = 8, 16
CHAT_ROWS = 10


def draw_terminal(img: Image.Image, chat_lines, out_path: Path, mode: str = "braille") -> None:
    cols, rows = 160, 46
    screen = TermScreen(cols, rows, 0, CHAT_ROWS, mode=mode)
    canvas = Image.new("RGB", (cols * CELL_W, rows * CELL_H), BG)
    d = ImageDraw.Draw(canvas)
    f = ImageFont.truetype(FONT, 14)
    fcjk = ImageFont.truetype(FONT_CJK, 14)

    def put_text(col, row, text, fg):
        x = col * CELL_W
        for ch in text:
            w = 2 if ord(ch) > 0x2E80 else 1
            d.text((x, row * CELL_H + 1), ch, font=fcjk if w == 2 else f, fill=fg)
            x += w * CELL_W

    if mode == "braille":
        fg, bg, mask = screen._picture_braille(img)
        dot_w, dot_h = CELL_W // 2, CELL_H // 4     # 4x4 px per dot
        for r in range(rows):
            for c in range(cols):
                x0 = (c * 2) * dot_w
                y0 = (r * 4) * dot_h
                m = int(mask[r, c])
                cf, cb = tuple(fg[r, c]), tuple(bg[r, c])
                for dr in range(4):
                    for dc in range(2):
                        bit = [1, 8, 2, 16, 4, 32, 64, 128][dr * 2 + dc]
                        color = cf if (m & bit) else cb
                        d.rectangle([x0 + dc * dot_w, y0 + dr * dot_h,
                                     x0 + dc * dot_w + dot_w - 1, y0 + dr * dot_h + dot_h - 1],
                                    fill=color)
    else:
        top, bot = screen._picture_half(img)
        for r in range(rows):
            for c in range(cols):
                x0, y0 = c * CELL_W, r * CELL_H
                d.rectangle([x0, y0, x0 + CELL_W - 1, y0 + CELL_H // 2 - 1], fill=tuple(top[r, c]))
                d.rectangle([x0, y0 + CELL_H // 2, x0 + CELL_W - 1, y0 + CELL_H - 1], fill=tuple(bot[r, c]))

    # chat overlay: bottom CHAT_ROWS lines, role-tinted background + text
    start = rows - CHAT_ROWS
    for r in range(start, rows):
        idx = r - start
        if idx < len(chat_lines):
            text, fg_c, bg_c = chat_lines[idx]
            d.rectangle([0, r * CELL_H, cols * CELL_W - 1, (r + 1) * CELL_H - 1], fill=bg_c)
            put_text(0, r, text, fg_c)
        else:
            d.rectangle([0, r * CELL_H, cols * CELL_W - 1, (r + 1) * CELL_H - 1], fill=BG)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)
    print(out_path)


if __name__ == "__main__":
    t = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
    mode = sys.argv[2] if len(sys.argv) > 2 else "braille"
    n = round(t * engine.FPS)
    img = timeline.frame(n)
    chat = ChatView(40)
    lines = chat.lines(t)
    overlay = lines[:3] + lines[3:][-(CHAT_ROWS - 3):] if len(lines) > 3 else lines
    draw_terminal(img, overlay,
                  Path(__file__).resolve().parents[1] / "output" / "live" / f"preview_{mode}_{t:05.1f}.png",
                  mode=mode)
