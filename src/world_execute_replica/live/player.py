"""Live player: render the film into the terminal, audio-synced through ffplay.

    python -m world_execute_replica.live [options]

Controls (while running):
    q / Ctrl-C   quit
    space        pause / resume
    left/right   seek -5 s / +5 s
    [ / ]        seek -1 s / +1 s
    p            save the current 1280x720 frame to output/live/
    h            toggle the key hint

The picture follows the audio clock: if a frame takes longer than 1/24 s to
render, frames are skipped (the time line stays correct). By default the
bloom/scanline/vignette post-pass is skipped so the picture can keep up with
the audio; pass --full-post to restore the full film look (slower).
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PKG = Path(__file__).resolve().parents[1]

FPS = 24
END_DEFAULT = 211.9


def _ff(name: str) -> str:
    """Resolve an ffmpeg-family tool: prefer the portable bin dir from `WEC_FF` (set by live.bat),
    else PATH, else the bare name (lets the error surface naturally)."""
    bindir = os.environ.get("WEC_FF", "")
    if bindir:
        p = Path(bindir) / (name + ".exe")
        if p.exists():
            return str(p)
    return name


# --------------------------------------------------------------------------- bootstrap

def _bootstrap() -> None:
    """Same assembly as every other entry point: flat aliases, then the timeline."""
    sys.path.insert(0, str(PKG))
    import _compat  # noqa: F401  (registers the flat module names)
    import world_execute_replica.tui.continuity.timeline as timeline
    import world_execute_replica.tui.engine.core as engine
    return timeline, engine


def _patch_fast() -> None:
    """Drop the bloom / scanlines / vignette post-pass for a cheaper frame."""
    from PIL import ImageChops
    import world_execute_replica.tui.kit as tk
    import world_execute_replica.tui.engine.core as engine

    def fast_post(img, prev=None, trail=0.42, bloom=0.35):
        if prev is not None and trail > 0:
            img = ImageChops.lighter(img, prev.point(lambda v: int(v * trail)))
        return img.convert("RGB")

    engine.post = fast_post
    tk.post = fast_post


# --------------------------------------------------------------------------- clocks

class AudioClock:
    """Wall-clock synchronised to an ffplay process (pause = kill + relaunch -ss)."""

    START_DELAY = 0.55          # seconds to let ffplay spin up before the clock starts

    def __init__(self, song: Path, start_t: float = 0.0):
        self.song = song
        self._proc: subprocess.Popen | None = None
        self._base = 0.0        # song time the clock currently reports at t0
        self._t0 = 0.0          # monotonic time when the song time was _base
        self._paused = False
        self._paused_t = start_t
        self._start(start_t)

    def _start(self, t: float) -> None:
        self._stop_proc()
        self._proc = subprocess.Popen(
            [_ff("ffplay"), "-nodisp", "-autoexit", "-loglevel", "quiet", "-ss", f"{t:.3f}", str(self.song)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(self.START_DELAY)          # let it decode before the clock runs
        self._base = t
        self._t0 = time.monotonic()
        self._paused = False

    def _stop_proc(self) -> None:
        if self._proc is not None:
            try:
                self._proc.kill()
            except Exception:
                pass
            self._proc = None

    def time(self) -> float:
        if self._paused:
            return self._paused_t
        return self._base + (time.monotonic() - self._t0)

    def set(self, t: float) -> None:
        self._base = t
        self._t0 = time.monotonic()

    def pause(self) -> None:
        if self._paused:
            return
        self._paused_t = self.time()
        self._paused = True
        self._stop_proc()

    def resume(self) -> None:
        if not self._paused:
            return
        self._start(self._paused_t)

    def paused(self) -> bool:
        return self._paused

    def seek(self, dt: float) -> None:
        t = max(0.0, self.time() + dt)
        if self._paused:
            self._paused_t = t
        else:
            self._start(t)

    def finished(self) -> bool:
        return self._proc is not None and self._proc.poll() is not None and not self._paused

    def stop(self) -> None:
        self._stop_proc()


class SimClock:
    """Frame-driven clock for --no-audio (renders as fast as the machine allows)."""

    def __init__(self, fps: float = 24.0, start_t: float = 0.0):
        self.fps = fps
        self._t = start_t
        self._paused = False
        self._last_render = 0.0

    def time(self) -> float:
        return self._t

    def set(self, t: float) -> None:
        self._t = t

    def advance(self, render_s: float) -> None:
        target = 1.0 / self.fps
        self._last_render = render_s
        wait = target - render_s
        if wait > 0:
            time.sleep(wait)
        self._t += target

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def paused(self) -> bool:
        return self._paused

    def seek(self, dt: float) -> None:
        self._t = max(0.0, self._t + dt)

    def finished(self) -> bool:
        return False

    def stop(self) -> None:
        pass


# --------------------------------------------------------------------------- keys

class Keys:
    def __init__(self) -> None:
        self._msvcrt = None
        if os.name == "nt":
            import msvcrt
            self._msvcrt = msvcrt

    def poll(self) -> str | None:
        """Return one key name ('q', 'space', 'left', ...) or None."""
        if self._msvcrt is not None:
            if not self._msvcrt.kbhit():
                return None
            ch = self._msvcrt.getwch()
            if ch in ("\x00", "\xe0"):            # arrow / function keys
                ch2 = self._msvcrt.getwch()
                return {"K": "left", "M": "right", "H": "up", "P": "down"}.get(ch2, ch2)
            return {"\r": "enter", " ": "space", "\x1b": "esc", "\x03": "ctrl_c"}.get(ch, ch)
        try:
            import termios
            import tty
        except ImportError:
            return None
        import select
        if select.select([sys.stdin], [], [], 0)[0]:
            ch = sys.stdin.read(1)
            return {" ": "space", "\x03": "ctrl_c", "\x1b": "esc"}.get(ch, ch)
        return None


# --------------------------------------------------------------------------- main

def _probe_duration(song: Path) -> float:
    try:
        out = subprocess.run([_ff("ffprobe"), "-v", "error", "-show_entries", "format=duration",
                              "-of", "csv=p=0", str(song)], capture_output=True, text=True,
                             timeout=20).stdout.strip()
        return float(out)
    except Exception:
        return END_DEFAULT


def _fmt(sec: float) -> str:
    mm, ss = divmod(max(0.0, sec), 60)
    return f"{int(mm):02d}:{ss:04.1f}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--song", default=str(ROOT / "input" / "song.mp3"), help="audio file to play (any format ffmpeg reads)")
    ap.add_argument("--cols", type=int, default=160, help="terminal columns (default 160)")
    ap.add_argument("--rows", type=int, default=46, help="terminal rows (default 46)")
    ap.add_argument("--chat-rows", type=int, default=10,
                    help="chat overlay rows at the bottom (default 10)")
    ap.add_argument("--left", type=int, default=0, help="chat pane width (default auto)")
    ap.add_argument("--fps", type=float, default=24.0, help="--no-audio target fps (default 24)")
    ap.add_argument("--t0", type=float, default=0.0, help="start at this song time (seconds)")
    ap.add_argument("--seconds", type=float, default=0.0, help="quit after this many seconds of playback (0 = play to the end)")
    ap.add_argument("--full-post", action="store_true", help="keep bloom/scanline/vignette post-pass (slower; off by default so the picture keeps up with the audio)")
    ap.add_argument("--no-audio", action="store_true", help="render without playing the song")
    a = ap.parse_args()

    song = Path(a.song).expanduser()
    if not song.exists():
        print(f"live: song not found: {song}", file=sys.stderr)
        return 2

    timeline, engine = _bootstrap()
    if not a.full_post:
        _patch_fast()
    if not a.no_audio and _ff("ffplay") == "ffplay" and shutil.which("ffplay") is None:
        print("live: ffplay not found on PATH (needed for audio); use --no-audio to render silently", file=sys.stderr)
        return 2

    end = min(END_DEFAULT, _probe_duration(song))
    from world_execute_replica.live.terminal import (ALT_OFF, ALT_ON, CLEAR, HIDE_CURSOR, HOME, RESET,
                                                     SHOW_CURSOR, TermScreen, setup_vt)
    from world_execute_replica.live.chat import ChatView

    setup_vt()
    chat_rows = max(4, min(a.chat_rows or 10, a.rows // 2))
    screen = TermScreen(a.cols, a.rows, 0, chat_rows)
    chat = ChatView(40)
    clock = AudioClock(song, a.t0) if not a.no_audio else SimClock(a.fps, a.t0)

    # terminal entrance
    out = sys.stdout
    out.write(ALT_ON + CLEAR + HIDE_CURSOR + HOME)
    out.flush()
    show_hint = True
    last_n = -1
    t_end = end if not a.no_audio else END_DEFAULT
    try:
        while True:
            keys = Keys()
            while True:
                k = keys.poll()
                if k is None:
                    break
                if k == "q" or k == "ctrl_c":
                    return 0
                if k == "space":
                    if clock.paused():
                        clock.resume()
                    else:
                        clock.pause()
                elif k == "left":
                    clock.seek(-5)
                elif k == "right":
                    clock.seek(5)
                elif k == "[":
                    clock.seek(-1)
                elif k == "]":
                    clock.seek(1)
                elif k == "p":
                    shot_dir = ROOT / "output" / "live"
                    shot_dir.mkdir(parents=True, exist_ok=True)
                    n = round(clock.time() * FPS)
                    timeline.frame(n).save(shot_dir / f"frame_{n:05d}.png")
                elif k == "h":
                    show_hint = not show_hint

            if isinstance(clock, SimClock):
                t = clock.time()
            else:
                t = clock.time()
            if t >= t_end or clock.finished() or (a.seconds and t >= a.t0 + a.seconds):
                break
            n = round(t * FPS)
            if n == last_n:
                time.sleep(0.002)
                continue
            last_n = n
            t_frame = n / FPS
            img = timeline.frame(n)
            t0_ = time.monotonic()

            lines = chat.lines(t)
            overlay = lines[:3] + lines[3:][-(chat_rows - 3):] if len(lines) > 3 else lines
            buf = screen.render(img, overlay)
            out.write(buf)
            out.flush()
            if isinstance(clock, SimClock):
                clock.advance(time.monotonic() - t0_)
    finally:
        clock.stop()
        out.write(RESET + SHOW_CURSOR + ALT_OFF + "\r\n")
        out.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
