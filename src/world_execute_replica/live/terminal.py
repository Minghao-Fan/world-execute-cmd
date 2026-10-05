"""ANSI truecolor terminal renderer for the live player.

Layout: full-window picture + a bottom chat overlay. No side pane, no status bar.

Picture modes (selectable via `--render`):
- "half"    half-block chars (U+2580): each cell carries two vertical pixels,
            effective grid = cols x (rows*2)
- "braille" Braille patterns (U+2800): each cell is a 2x4 dot matrix, effective
            grid = (cols*2) x (rows*4), i.e. 320x184 at 160x46 -- nearly the
            film's 16:9 and roughly 4x the pixel density of the old layout.

Colors are always TrueColor (24-bit); per cell the dots use one foreground for
the lit pixels and one background for the unlit pixels.
"""
from __future__ import annotations

import ctypes
import os
import sys
import unicodedata
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFilter

# palette from tuikit (amber), reused for the terminal chrome so the window
# looks like the film's system colour
BG = (8, 6, 4)
UI = (255, 176, 0)
RED = (255, 58, 40)
BLUE = (77, 107, 254)
ME_TEXT = (126, 152, 255)
GREY = (120, 110, 80)
DIM = (70, 62, 40)

# chat role backgrounds (subtle dark tints so the overlay still reads as part
# of the picture)
BG_SYS = (14, 18, 44)
BG_YOU = (8, 32, 17)
BG_DSH = (34, 24, 9)
BG_ERR = (44, 13, 11)
BG_META = (22, 19, 12)

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

# Braille dot bitmasks, Unicode order: cols x rows layout inside one cell.
#   dot1=1  dot4=8
#   dot2=2  dot5=16
#   dot3=4  dot6=32
#   dot7=64 dot8=128
BRAILLE_BITS = np.array([
    [1, 8],
    [2, 16],
    [4, 32],
    [64, 128],
], dtype=np.uint16)


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
    """Full-window picture + a bottom chat overlay (no panes, no status bar)."""

    def __init__(self, cols: int = 160, rows: int = 46, left_cols: int = 0,
                 chat_rows: int = 10, mode: str = "braille",
                 dot_offset: float = 16.0, dot_cap: float = 170.0):
        # adaptive threshold: a dot lights when clearly brighter than its cell
        # mean; dot_cap keeps uniform bright areas lit (absolute fallback).
        self.cols = max(40, cols)
        self.rows = max(12, rows)
        self.left_cols = 0                         # no side pane anymore
        self.chat_rows = max(4, min(chat_rows, self.rows // 2))
        self.status_rows = 0                       # status bar removed
        self.pane_rows = self.rows                 # picture takes the whole window
        self.sep_col = 0
        self.pic_cols = self.cols
        self.mode = mode if mode in ("braille", "half") else "braille"
        self.dot_offset = float(dot_offset)
        self.dot_cap = float(dot_cap)
        self._prev = None

        if self.mode == "braille":
            # dot grid = (cols*2) x (rows*4); 320x184 at 160x46 ~= 16:9
            self.pic_w_px = self.pic_cols * 2
            self.pic_h_px = self.pane_rows * 4
            scale = min(self.pic_w_px / FULL_W, self.pic_h_px / FULL_H)
            self.pic_w = max(1, int(FULL_W * scale))
            self.pic_h = max(1, int(FULL_H * scale))
            self.pic_x = (self.pic_w_px - self.pic_w) // 2
            self.pic_y = (self.pic_h_px - self.pic_h) // 2
        else:
            self.pic_w_px = self.pic_cols
            self.pic_h_px = self.pane_rows * 2
            scale = min(self.pic_w_px / FULL_W, self.pic_h_px / FULL_H)
            self.pic_w = max(1, int(FULL_W * scale))
            self.pic_h = max(1, int(FULL_H * scale))
            self.pic_x = (self.pic_w_px - self.pic_w) // 2
            self.pic_y = (self.pic_h_px - self.pic_h) // 2

    # ------------------------------------------------------------- picture

    def _downscaled(self, img: Image.Image, w_px: int, h_px: int) -> np.ndarray:
        """LANCZOS downscale + light unsharp -> letterboxed RGB ndarray."""
        small = img.convert("RGB").resize((self.pic_w, self.pic_h), Image.LANCZOS)
        small = small.filter(ImageFilter.UnsharpMask(radius=2, percent=90, threshold=2))
        canvas = Image.new("RGB", (w_px, h_px), BG)
        canvas.paste(small, (self.pic_x, self.pic_y))
        return np.asarray(canvas, dtype=np.uint8)      # (h_px, w_px, 3)

    def _picture_half(self, img: Image.Image):
        """Half-block mode: return (top, bot) pixel arrays, (rows, cols, 3) each."""
        arr = self._downscaled(img, self.pic_w_px, self.pic_h_px)
        return arr[0::2, :, :], arr[1::2, :, :]

    def _picture_braille(self, img: Image.Image):
        """Braille mode: return (fg, bg, mask) arrays, (rows, cols, ...) each.

        mask bit i is set when the i-th dot is lit; fg is the mean color of the
        lit dots, bg the mean of the unlit dots (per cell, TrueColor).
        """
        arr = self._downscaled(img, self.pic_w_px, self.pic_h_px)
        luma = arr @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
        cells = arr.reshape(self.pane_rows, 4, self.pic_cols, 2, 3)
        lum = luma.reshape(self.pane_rows, 4, self.pic_cols, 2)
        mean = lum.mean(axis=(1, 3), keepdims=True)             # per-cell mean
        thr = np.minimum(mean + self.dot_offset, self.dot_cap)   # local contrast + abs fallback
        on = lum >= thr

        mask = (on * BRAILLE_BITS[None, :, None, :]).sum(axis=(1, 3)).astype(np.uint16)   # (rows, cols)

        f32 = cells.astype(np.float32)
        lit = (f32 * on[..., None]).sum(axis=(1, 3))
        n_lit = on.sum(axis=(1, 3))[..., None].clip(min=1)
        fg = np.rint(lit / n_lit).astype(np.uint8)          # mean of lit dots

        off = (f32 * (~on[..., None])).sum(axis=(1, 3))
        n_off = (~on).sum(axis=(1, 3))[..., None].clip(min=1)
        bg = np.rint(off / n_off).astype(np.uint8)          # mean of unlit dots
        return fg, bg, mask

    # ------------------------------------------------------------- build

    def render_lines(self, img: Image.Image,
                     chat_lines: list[tuple[str, tuple, tuple]]) -> list[str]:
        """Return the frame as a list of full ANSI lines (each ends with \\r\\n).

        The player diffs consecutive frames and only re-emits changed lines.
        """
        lines: list[str] = []
        if self.mode == "braille":
            fg, bg, mask = self._picture_braille(img)
            for r in range(self.pane_rows):
                lines.append(self._line_braille(fg[r], bg[r], mask[r]) + ERASE_LINE + "\r\n")
        else:
            top, bot = self._picture_half(img)
            for r in range(self.pane_rows):
                lines.append(self._line_half(top[r], bot[r]) + ERASE_LINE + "\r\n")

        start = self.rows - self.chat_rows
        for r in range(start, self.rows):
            idx = r - start
            if idx < len(chat_lines):
                text, fg_c, bg_c = chat_lines[idx]
                lines.append(self._sgr(fg_c, bg_c) + pad_text(text, self.cols) + ERASE_LINE + "\r\n")
            else:
                lines.append(self._sgr(GREY, BG) + " " * self.cols + ERASE_LINE + "\r\n")
        return lines

    def render(self, img: Image.Image, chat_lines: list[tuple[str, tuple, tuple]],
               status1: str = "", status2: str = "") -> str:
        """Convenience: full frame as one ANSI string (HOME + all lines + RESET)."""
        return HOME + "".join(self.render_lines(img, chat_lines)) + RESET

    def _line_half(self, top: np.ndarray, bot: np.ndarray) -> str:
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

    def _line_braille(self, fg: np.ndarray, bg: np.ndarray, mask: np.ndarray) -> str:
        out: list[str] = []
        prev = None
        run = 0
        for c in range(self.pic_cols):
            key = (tuple(fg[c]), tuple(bg[c]), int(mask[c]))
            if key == prev:
                run += 1
                continue
            if prev is not None:
                out.append(self._sgr(prev[0], prev[1]) + chr(0x2800 + prev[2]) * run)
            prev, run = key, 1
        if prev is not None:
            out.append(self._sgr(prev[0], prev[1]) + chr(0x2800 + prev[2]) * run)
        return "".join(out)

    @staticmethod
    def _sgr(fg: tuple, bg: tuple) -> str:
        return (f"\x1b[38;2;{fg[0]};{fg[1]};{fg[2]}m"
                f"\x1b[48;2;{bg[0]};{bg[1]};{bg[2]}m")
