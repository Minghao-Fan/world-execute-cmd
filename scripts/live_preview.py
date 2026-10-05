"""Render a mockup PNG of what the live terminal looks like (for preview only)."""
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "src" / "world_execute_replica"
sys.path.insert(0, str(PKG))
import _compat  # noqa: F401
import world_execute_replica.tui.continuity.timeline as timeline
import world_execute_replica.tui.engine.core as engine
from PIL import Image, ImageDraw, ImageFont

from world_execute_replica.live.terminal import TermScreen, BG, UI, DIM, ME_TEXT, GREY, RED
from world_execute_replica.live.chat import ChatView

FONT = "C:/Windows/Fonts/consola.ttf"
CELL_W, CELL_H = 8, 16

def draw_terminal(img: Image.Image, chat_lines, st1, st2, out_path: Path) -> None:
    cols, rows = 160, 46
    screen = TermScreen(cols, rows)
    top, bot = screen._picture(img)
    canvas = Image.new("RGB", (cols * CELL_W, rows * CELL_H), BG)
    d = ImageDraw.Draw(canvas)
    f = ImageFont.truetype(FONT, 14)
    fcjk = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 14)

    def put_text(col, row, text, fg):
        x = col * CELL_W
        for ch in text:
            w = 2 if ord(ch) > 0x2E80 else 1
            d.text((x, row * CELL_H + 1), ch, font=fcjk if w == 2 else f, fill=fg)
            x += w * CELL_W

    for r in range(screen.pane_rows):
        if r < len(chat_lines):
            text, fg = chat_lines[r]
            put_text(0, r, text[:screen.left_cols], fg)
        # separator
        d.rectangle([screen.left_cols * CELL_W, r * CELL_H,
                     screen.left_cols * CELL_W + 1, (r + 1) * CELL_H], fill=DIM)
        for c in range(screen.pic_cols):
            x0 = (screen.left_cols + 1 + c) * CELL_W
            y0 = r * CELL_H
            d.rectangle([x0, y0, x0 + CELL_W - 1, y0 + CELL_H // 2 - 1], fill=tuple(top[r][c]))
            d.rectangle([x0, y0 + CELL_H // 2, x0 + CELL_W - 1, y0 + CELL_H - 1], fill=tuple(bot[r][c]))
    # status rows
    put_text(0, rows - 2, st1[:cols], UI)
    put_text(0, rows - 1, st2[:cols], ME_TEXT)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)
    print(out_path)


if __name__ == "__main__":
    t = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
    n = round(t * engine.FPS)
    img = timeline.frame(n)
    chat = ChatView(42)
    st1 = f"00:{int(t):02d}.0 / 03:32 · {engine.chapter_at(n / engine.FPS)} · song.mp3"
    st2 = "♪ power · protection · creation            space 暂停  ←→ ±5s  q 退出  p 截图"
    draw_terminal(img, chat.lines(t), st1, st2,
                  Path(__file__).resolve().parents[1] / "output" / "live" / f"preview_{t:05.1f}.png")
