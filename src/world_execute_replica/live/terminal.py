"""ANSI half-block truecolor terminal renderer for the live player.

Layout (cols x rows, default 160 x 46):

    +------------------------------+--+----------------------------+
    |  left chat pane (text)       |  | right picture pane         |
    |                              |  | (half-block chars '\\u2580',  |
    |                              |  |  letterboxed, never        |
    |                              |  |  distorted)                |
    +------------------------------+--+----------------------------+
    | status line 1: time / chapter / song                            |
    | status line 2: current lyric                                    |
    +-----------------------------------------------------------------+

The picture pane maps 1280x720 into `pw` half-block columns and `ph` half-block
rows: each cell carries two vertical pixels (top = foreground, bottom =
background), so the effective pixel grid is pw x (ph*2). A truecolor ANSI SGR
is emitted per run of identical (fg, bg) cells to keep the byte count low.
"""
from __future__ import annotations

import ctypes
import os
import sys
import unicodedata
from dataclasses import dataclass

import numpy as np
from PIL import Image

# palette from tuikit (amber), reused for the terminal chrome so the window
# looks like the film's system colour
BG = (8, 6, 4)
UI = (255, 176, 0)
RED = (255, 58, 40)
BLUE = (77, 107, 254)
ME_TEXT = (126, 152, 255)
GREY = (120, 110, 80)
DIM = (70, 62, 40)

RESET = "\x1b[0m"
HOME = "\x1b[H"
CLEAR = "\x1b[2J"
ERASE_LINE = "\x1b[K"
HIDE_CURSOR = "\x1b[?25l"
SHOW_CURSOR = "\x1b[?25h"
ALT_ON = "\x1b[?1049h"
ALT_OFF = "\x1b[?1049l"
BEEP = "\x07"

FULL_W, FULL_H = 1280, 720


def setup_vt() -> None:
    """Enable ANSI escape processing on the Windows console (harmless elsewhere)."""
    if os.name != "nt":
        return
    kernel32 = ctypes.windll.kernel32
    for handle_id in (-11, -12):  # stdout, stderr
        h = kernel32.GetStdHandle(handle_id)
        mode = ctypes.c_uint32(0)
        if kernel32.GetConsoleMode(h, ctypes.byref(mode)):
            kernel32.SetConsoleMode(h, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING


def wcwidth(ch: str) -> int:
    """Terminal column width of one character (CJK wide chars take 2 columns)."""
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def pad_text(s: str, width: int, fill: str = " ") -> str:
    """Pad/truncate a string to exactly `width` terminal columns (CJK-aware)."""
    out, w = [], 0
    for ch in s:
        cw = wcwidth(ch)
        if w + cw > width:
            break
        out.append(ch)
        w += cw
    return "".join(out) + fill * (width - w)


@dataclass
class Cell:
    ch: str = " "
    fg: tuple = GREY
    bg: tuple = BG


class TermScreen:
    """Builds one ANSI frame: chat pane text + picture pane half-blocks + status rows."""

    def __init__(self, cols: int = 160, rows: int = 46, left_cols: int = 42):
        self.cols = max(40, cols)
        self.rows = max(12, rows)
        self.left_cols = max(10, min(left_cols, self.cols // 4))
        self.status_rows = 2
        self.pane_rows = self.rows - self.status_rows
        self.sep_col = self.left_cols              # single separator column
        self.pic_cols = self.cols - self.left_cols - 1
        self._prev = None                          # optional diffing (unused in v1)
        # precompute picture geometry: letterboxed 1280x720 -> pic_cols x pic_rows*2 px
        scale = min(self.pic_cols / FULL_W, self.pane_rows * 2 / FULL_H)
        self.pic_w = max(1, int(FULL_W * scale))
        self.pic_h = max(1, int(FULL_H * scale))
        self.pic_x = (self.pic_cols - self.pic_w) // 2
        self.pic_y = (self.pane_rows * 2 - self.pic_h) // 2

    # ------------------------------------------------------------------ picture

    def _picture(self, img: Image.Image) -> np.ndarray:
        """Return (pane_rows, pic_cols) array of cell indices into fg/bg pixel pairs."""
        small = img.convert("RGB").resize((self.pic_w, self.pic_h), Image.BILINEAR)
        canvas = Image.new("RGB", (self.pic_cols, self.pane_rows * 2), BG)
        canvas.paste(small, (self.pic_x, self.pic_y))
        arr = np.asarray(canvas, dtype=np.uint8)            # (H, W, 3)
        top = arr[0::2, :, :]                                # (pane_rows, pic_cols, 3)
        bot = arr[1::2, :, :]
        return top, bot

    # ------------------------------------------------------------------- build

    def render(self, img: Image.Image, chat_lines: list[tuple[str, tuple]],
               status1: str, status2: str) -> str:
        top, bot = self._picture(img)
        buf: list[str] = [HOME]
        for r in range(self.pane_rows):
            # left pane: text (padded to the pane width only, so the row stays
            # left_cols + 1 + pic_cols == cols and never wraps in the terminal)
            if r < len(chat_lines):
                text, fg = chat_lines[r]
                buf.append(self._line_text(text, fg, self.left_cols))
            else:
                buf.append(self._line_text("", GREY, self.left_cols))
            # separator
            buf.append(self._cell_char("│", DIM, BG))
            # right pane: half blocks
            buf.append(self._line_picture(top[r], bot[r]))
            buf.append(ERASE_LINE + "\r\n")
        buf.append(self._line_text(status1, UI))
        buf.append(ERASE_LINE + "\r\n")
        buf.append(self._line_text(status2, ME_TEXT))
        buf.append(RESET)
        return "".join(buf)

    def _line_picture(self, top: np.ndarray, bot: np.ndarray) -> str:
        out: list[str] = []
        prev = None
        run = 0
        for c in range(self.pic_cols):
            key = (tuple(top[c]), tuple(bot[c]))
            if key == prev:
                run += 1
                continue
            if prev is not None:
                out.append(self._sgr(prev[0], prev[1]) + "\u2580" * run)
            prev, run = key, 1
        if prev is not None:
            out.append(self._sgr(prev[0], prev[1]) + "\u2580" * run)
        return "".join(out)

    def _line_text(self, text: str, fg: tuple, width: int | None = None) -> str:
        line = pad_text(text, self.cols if width is None else width)
        return self._sgr(fg, BG) + line

    @staticmethod
    def _cell_char(ch: str, fg: tuple, bg: tuple) -> str:
        return f"\x1b[38;2;{fg[0]};{fg[1]};{fg[2]}m\x1b[48;2;{bg[0]};{bg[1]};{bg[2]}m{ch}"

    @staticmethod
    def _sgr(fg: tuple, bg: tuple) -> str:
        return (f"\x1b[38;2;{fg[0]};{fg[1]};{fg[2]}m"
                f"\x1b[48;2;{bg[0]};{bg[1]};{bg[2]}m")
