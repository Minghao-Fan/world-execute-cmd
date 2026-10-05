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

Brightness pipeline: the mean map (LANCZOS) provides the per-cell colours; a
parallel max map (BOX to 2x then 2x2 max-pool) feeds the dot decision so sparse
bright dots (globe dot-clouds, particles, scatter) survive downscaling. The dot
decision is per-cell min/max normalised: a dot lights when it reaches the top
~30% of its cell's range (norm >= 0.7), uniform areas stay off, and dot_cap
still lights uniform bright fills.

Simulated text -> real terminal text: every ImageDraw.text call during frame
rendering is intercepted (see install_text_capture); mid-size informational
text is darkened in the source frame and re-rendered by the player as native
terminal text at the same grid position, instead of smearing into braille dots.
"""
from __future__ import annotations

import ctypes
import os
import unicodedata

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# palette from tuikit (amber), reused for the terminal chrome so the window
# looks like the film's system colour
BG = (8, 6, 4)
UI = (255, 176, 0)
RED = (255, 58, 40)
BLUE = (77, 107, 254)
ME_TEXT = (126, 152, 255)
GREY = (120, 110, 80)
DIM = (70, 62, 40)
# solid frame colour for the ops ticker border (amber, clearly visible)
FRAME = (170, 145, 80)

RESET = "\x1b[0m"
HOME = "\x1b[H"
CLEAR = "\x1b[2J"
ERASE_LINE = "\x1b[K"
HIDE_CURSOR = "\x1b[?25l"
SHOW_CURSOR = "\x1b[?25h"
ALT_ON = "\x1b[?1049h"
ALT_OFF = "\x1b[?1049l"

FULL_W, FULL_H = 1280, 720

# source px of the right ops ticker frame (core.py TICK); text captured inside
# this band is right-aligned to the frame right edge so the column hugs the
# window border at the same distance the left pane border keeps from the left.
OPS_LEFT_X, OPS_RIGHT_X = 1150, 1256

# persistent terminal chrome in the source frame (tui/engine/core.py header):
# title / step-loss-tps / right status. Darkened so the braille picture shows a
# clean base; the player overlays real terminal text there instead.
CHROME_BOXES = ((24, 6, 430, 36), (330, 6, 692, 36), (960, 6, 1256, 36))

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


# ---------------------------------------------------------------- text capture
# Every ImageDraw.text during the frame render is routed here. Mid-size text
# (the "simulated text" that smears into braille dots) is darkened in the frame
# and recorded; the player overlays it as real terminal text. Tiny captions and
# huge effect titles stay pixel-rendered on purpose.

_TEXTS: list[tuple[int, int, int, int, str, int, tuple]] = []  # x, y, w, h, s, size, fg
_ORIG_TEXT = ImageDraw.ImageDraw.text


def install_text_capture() -> None:
    """Patch ImageDraw.text so source text becomes native terminal text."""
    ImageDraw.ImageDraw.text = _capture_text


def _capture_text(self, xy, text, font=None, fill=None, *a, **k):
    size = getattr(font, "size", 0)
    if not (size and text):
        return _ORIG_TEXT(self, xy, text, font=font, fill=fill, *a, **k)
    # Grayscale canvases ("L") are internal glyph/bitmap builders (banner_bits,
    # dot charts, ...) that paint text on tiny throwaway images and read the
    # pixels back. Capturing them would blank the glyphs (and their coordinates
    # collide with the chrome boxes), so always let them draw untouched.
    if getattr(getattr(self, "_image", None), "mode", "") == "L":
        return _ORIG_TEXT(self, xy, text, font=font, fill=fill, *a, **k)
    x0, y0 = int(xy[0]), int(xy[1])
    # persistent header boxes are handled by chrome_top (and _strip_chrome);
    # never double-overlay them.
    for bx0, by0, bx1, by1 in CHROME_BOXES:
        if bx0 - 6 <= x0 <= bx1 and by0 - 6 <= y0 <= by1:
            return None
    if 10 <= size <= 34:
        try:
            bb = font.getbbox(text)
            w, h = bb[2] - bb[0], bb[3] - bb[1]
        except Exception:
            w, h = int(size * 0.6) * len(text), int(size * 1.2)
        fill_c = tuple(fill) if isinstance(fill, (tuple, list)) and len(fill) == 3 else (255, 176, 0)
        _TEXTS.append((x0, y0, max(1, w), max(1, h), str(text), size, fill_c))
        # Draw the original text: some shots read pixels back from their canvas
        # (e.g. the countdown '3' cells). Darkening happens later in
        # _strip_texts, right before the braille pass, so the dots stay clean.
        return _ORIG_TEXT(self, xy, text, font=font, fill=fill, *a, **k)
    return _ORIG_TEXT(self, xy, text, font=font, fill=fill, *a, **k)


class TermScreen:
    """Full-window picture + bottom chat overlay (no panes, no status bar)."""

    def __init__(self, cols: int = 160, rows: int = 46, left_cols: int = 0,
                 chat_rows: int = 10, mode: str = "braille",
                 dot_offset: float = 16.0, dot_cap: float = 170.0,
                 gamma: float = 1.0):
        # adaptive threshold: a dot lights when clearly brighter than its cell
        # mean; dot_cap keeps uniform bright areas lit (absolute fallback).
        # gamma is an optional tone map on the max-map luminance (kept for
        # experimentation; default 1.0 = off).
        self.cols = max(40, cols)
        self.rows = max(12, rows)
        self.left_cols = 0                         # no side pane anymore
        self.chat_rows = max(4, min(chat_rows, self.rows // 2))
        self.status_rows = 0                       # status bar removed
        self.pane_rows = self.rows                 # picture takes the whole window
        self.sep_col = 0
        self.pic_cols = self.cols
        self.mode = mode if mode in ("braille", "half") else "braille"
        self.strip_chrome = True
        self.dot_offset = float(dot_offset)
        self.dot_cap = float(dot_cap)
        self.gamma = float(gamma)
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

    def _strip_chrome(self, img: Image.Image) -> Image.Image:
        """Darken the persistent header boxes so source text does not smear into
        the braille dots; the player overlays real terminal text there instead."""
        d = ImageDraw.Draw(img)
        for x0, y0, x1, y1 in CHROME_BOXES:
            d.rectangle([x0, y0, x1, y1], fill=(6, 5, 3))
        return img

    def _strip_texts(self, img: Image.Image,
                     texts: list[tuple[int, int, int, int, str, int, tuple]]) -> Image.Image:
        """Darken every captured text box so it cannot smear into the dots."""
        d = ImageDraw.Draw(img)
        for (x, y, w, h, s, size, fg) in texts:
            d.rectangle([x, y, x + w, y + h], fill=(6, 5, 3))
        return img

    def _downscaled(self, img: Image.Image, w_px: int, h_px: int) -> np.ndarray:
        """LANCZOS downscale + light unsharp -> letterboxed RGB ndarray."""
        if self.strip_chrome:
            img = self._strip_chrome(img)
        small = img.convert("RGB").resize((self.pic_w, self.pic_h), Image.LANCZOS)
        small = small.filter(ImageFilter.UnsharpMask(radius=2, percent=90, threshold=2))
        canvas = Image.new("RGB", (w_px, h_px), BG)
        canvas.paste(small, (self.pic_x, self.pic_y))
        return np.asarray(canvas, dtype=np.uint8)      # (h_px, w_px, 3)

    def _downscaled_max(self, img: Image.Image, w_px: int, h_px: int) -> np.ndarray:
        """Max-pooled luminance map: BOX to 2x then 2x2 max.

        The mean downscale (LANCZOS) smears sparse bright dots (globe dot-clouds,
        particles) into their dark surroundings and they vanish from the braille
        pass. Keeping the brightest pixel per cell preserves those dots while
        uniform areas stay identical to the mean map.
        """
        mid = img.convert("RGB").resize((self.pic_w * 2, self.pic_h * 2), Image.BOX)
        a = np.asarray(mid, dtype=np.float32)
        a = a.reshape(self.pic_h, 2, self.pic_w, 2, 3).max(axis=(1, 3))
        canvas = np.full((h_px, w_px, 3), BG, dtype=np.float32)
        canvas[self.pic_y:self.pic_y + self.pic_h, self.pic_x:self.pic_x + self.pic_w] = a
        return canvas

    def _picture_half(self, img: Image.Image):
        """Half-block mode: return (top, bot) pixel arrays, (rows, cols, 3) each."""
        arr = self._downscaled(img, self.pic_w_px, self.pic_h_px)
        return arr[0::2, :, :], arr[1::2, :, :]

    def _picture_braille(self, img: Image.Image):
        """Braille mode: return (fg, bg, mask) arrays, (rows, cols, ...) each.

        mask bit i is set when the i-th dot is lit; fg is the mean color of the
        lit dots, bg the mean of the unlit dots (per cell, TrueColor).
        """
        arr = self._downscaled(img, self.pic_w_px, self.pic_h_px)     # mean map (colours)
        arr_h = self._downscaled_max(img, self.pic_w_px, self.pic_h_px)  # max map (dots)
        luma = arr_h @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
        if self.gamma != 1.0:
            luma = 255.0 * np.power(luma / 255.0, self.gamma)
        cells = arr.reshape(self.pane_rows, 4, self.pic_cols, 2, 3)
        lum = luma.reshape(self.pane_rows, 4, self.pic_cols, 2)
        # Per-cell contrast stretch: the globe's dot-cloud and particle fields
        # are drawn far too dark to clear any absolute bar after downscaling
        # (peak ~10 vs BG 6). Normalising each cell to its own min/max range
        # makes the relative bright dot light up while uniform areas stay off;
        # dot_cap still lights uniform bright fills.
        mn = lum.min(axis=(1, 3), keepdims=True)
        mx = lum.max(axis=(1, 3), keepdims=True)
        norm = (lum - mn) / (mx - mn + 1.0)
        on = (norm >= 0.7) | (lum >= self.dot_cap)

        mask = (on * BRAILLE_BITS[None, :, None, :]).sum(axis=(1, 3)).astype(np.uint16)   # (rows, cols)

        f32 = cells.astype(np.float32)
        lit = (f32 * on[..., None]).sum(axis=(1, 3))
        n_lit = on.sum(axis=(1, 3))[..., None].clip(min=1)
        fg = np.rint(lit / n_lit).astype(np.uint8)          # mean of lit dots
        # Lift the foreground: lit dots (e.g. the globe's dark-brown points) are
        # often as dark as the background after mean-colouring, so they vanish
        # visually even when the mask says lit. A soft gamma keeps hue, lifts
        # dark fills into visibility and barely touches bright curves.
        fg = np.rint(255.0 * np.power(fg.astype(np.float32) / 255.0, 0.6)).astype(np.uint8)

        off = (f32 * (~on[..., None])).sum(axis=(1, 3))
        n_off = (~on).sum(axis=(1, 3))[..., None].clip(min=1)
        bg = np.rint(off / n_off).astype(np.uint8)          # mean of unlit dots
        return fg, bg, mask

    # ------------------------------------------------------------- build

    def render_lines(self, img: Image.Image,
                     chat_lines: list[tuple[str, tuple, tuple]],
                     chrome_top: str = "",
                     texts: list[tuple[int, int, int, int, str, int, tuple]] | None = None) -> list[str]:
        """Return the frame as a fixed-length list of ANSI lines (rows total;
        the last line ends with \\r so the console never scrolls).

        Pipeline: dot picture -> char grid -> overlay chrome/texts/chat on the
        grid -> per-line run-length ANSI. The player diffs consecutive frames.
        """
        if texts:
            img = self._strip_texts(img, texts)
        if self.mode == "braille":
            fg, bg, mask = self._picture_braille(img)
            grid = [[(chr(0x2800 + int(mask[r, c])), tuple(fg[r, c]), tuple(bg[r, c]))
                     for c in range(self.pic_cols)] for r in range(self.pane_rows)]
        else:
            top, bot = self._picture_half(img)
            grid = [[("\u2580", tuple(top[r, c]), tuple(bot[r, c]))
                     for c in range(self.pic_cols)] for r in range(self.pane_rows)]

        if chrome_top:
            self._fill_row(grid, 0, pad_text(chrome_top, self.cols), UI, BG)

        if texts:
            self._overlay_texts(grid, texts)

        self._draw_ops_frame(grid)

        start = self.rows - self.chat_rows
        for r in range(start, self.rows):
            idx = r - start
            if idx < len(chat_lines):
                text, fg_c, bg_c = chat_lines[idx]
                self._fill_row(grid, r, pad_text(text, self.cols), fg_c, bg_c)
            else:
                self._fill_row(grid, r, " " * self.cols, GREY, BG)

        lines = [self._grid_line(grid[r]) + ERASE_LINE
                 + ("\r\n" if r < self.rows - 1 else "\r") for r in range(self.rows)]
        return lines

    def _draw_ops_frame(self, grid: list) -> None:
        """Solid frame around the right ops ticker: its right edge mirrors the
        left pane border (source x=24 -> 3 cols from the edge). Drawn after the
        text overlay so the border always wins; the bottom stops above the chat
        overlay so the line is never swallowed by the chat background."""
        if self.cols < 120:
            return
        ol = self.cols * OPS_LEFT_X // FULL_W
        or_ = self.cols * OPS_RIGHT_X // FULL_W
        rt = 3                       # source y=56
        rb = min(self.rows - self.chat_rows - 1, self.rows - 2)
        if rb < rt:
            return
        for rr in range(rt, rb + 1):
            grid[rr][ol] = ("┃", FRAME, BG)
            grid[rr][or_] = ("┃", FRAME, BG)
        for cc in range(ol, or_ + 1):
            grid[rt][cc] = ("━", FRAME, BG)
            grid[rb][cc] = ("━", FRAME, BG)
        grid[rt][ol] = ("┏", FRAME, BG)
        grid[rt][or_] = ("┓", FRAME, BG)
        grid[rb][ol] = ("┗", FRAME, BG)
        grid[rb][or_] = ("┛", FRAME, BG)

    def _overlay_texts(self, grid: list, texts: list[tuple[int, int, int, int, str, int, tuple]]) -> None:
        """Blit captured source texts onto the grid as native terminal text."""
        ops_right_col = self.cols * OPS_RIGHT_X // FULL_W   # ticker frame right edge
        for (x, y, w, h, s, size, fg_c) in texts:
            if x >= OPS_LEFT_X and y >= 56 and y < 610:
                # right ops ticker zone: right-align so its right edge hugs the
                # window edge at the same distance as the left pane border does
                # on the left (source x=24 -> col 3). Short ops labels then line
                # up flush against the right margin instead of dangling.
                n = sum(wcwidth(ch) for ch in s)
                col = ops_right_col - 1 - n   # keep 1 column clear for the frame
                if col < 0:
                    col = 0
            else:
                col = x * self.cols // FULL_W
            row = y * self.rows // FULL_H
            rows_take = max(1, min(3, (int(size * 1.1 * self.rows * 4 / FULL_H) + 3) // 4))
            if not (0 <= row < self.pane_rows and 0 <= col < self.cols):
                continue
            avail = self.cols - col
            chars: list[str] = []
            for ch in s:
                cw = wcwidth(ch)
                if cw > avail:
                    break
                chars.append(ch)
                avail -= cw
            if not chars:
                continue
            for rr in range(row, min(row + rows_take, self.rows)):
                if rr >= self.pane_rows:
                    break
                self._fill_row(grid, rr, "".join(chars), fg_c, BG, col)

    @staticmethod
    def _fill_row(grid: list, r: int, text: str, fg: tuple, bg: tuple, col0: int = 0) -> None:
        """Write one grid row at col0; CJK wide chars occupy 2 columns, with a
        bg-coloured placeholder cell after them so nothing overlaps."""
        c = col0
        for ch in text:
            cw = wcwidth(ch)
            if c + cw > len(grid[r]):
                break
            grid[r][c] = (ch, fg, bg)
            if cw == 2 and c + 1 < len(grid[r]):
                grid[r][c + 1] = (" ", bg, bg)
            c += cw

    @staticmethod
    def _grid_line(row: list[tuple[str, tuple, tuple]]) -> str:
        out: list[str] = []
        prev = None
        run: list[str] = []
        for (ch, fg, bg) in row:
            key = (fg, bg)
            if key == prev:
                run.append(ch)
            else:
                if prev is not None:
                    out.append(TermScreen._sgr(prev[0], prev[1]) + "".join(run))
                prev, run = key, [ch]
        if prev is not None:
            out.append(TermScreen._sgr(prev[0], prev[1]) + "".join(run))
        return "".join(out)

    def render(self, img: Image.Image, chat_lines: list[tuple[str, tuple, tuple]],
               status1: str = "", status2: str = "") -> str:
        """Convenience: full frame as one ANSI string (HOME + all lines + RESET)."""
        return HOME + "".join(self.render_lines(img, chat_lines)) + RESET

    @staticmethod
    def _sgr(fg: tuple, bg: tuple) -> str:
        return (f"\x1b[38;2;{fg[0]};{fg[1]};{fg[2]}m"
                f"\x1b[48;2;{bg[0]};{bg[1]};{bg[2]}m")
