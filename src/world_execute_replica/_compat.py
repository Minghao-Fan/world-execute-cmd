# -*- coding: utf-8 -*-
"""Boot-time compatibility shim.

The film's code was written against flat module names (`import engine`,
`import tuikit as tk`, `import s_boot`, ...).  After the src-layout refactor the
files live under `world_execute_replica.*`.  Every entry script imports this
module first: it puts the package roots on ``sys.path`` and registers the flat
names onto their new homes, so the historical layers (loaded by
``importlib``) and any leftover flat import keep resolving.

Importing this module twice is harmless (``sys.modules`` assignments are
idempotent).
"""
import sys
from pathlib import Path

_PKG = Path(__file__).resolve().parent
_SRC = _PKG.parent

# dsh/wave.py shadows the stdlib `wave` while dsh/ is on sys.path (build.py
# puts it in PYTHONPATH); pull dsh/ off the path before resolving the stdlib
# module, then pin it, so `import wave` (g.py's chime writer) stays stdlib.
for _p in list(sys.path):
    if Path(_p).resolve().as_posix().endswith("/world_execute_replica/dsh"):
        sys.path.remove(_p)
import wave as _stdlib_wave
sys.modules["wave"] = _stdlib_wave

for _p in (_SRC, _PKG,
           _PKG / "tui", _PKG / "tui" / "engine", _PKG / "tui" / "engine" / "sections",
           _PKG / "tui" / "continuity", _PKG / "tui" / "continuity" / "shots",
           _PKG / "tui" / "continuity" / "scenes",
           _PKG / "dancer", _PKG / "dsh", _PKG / "_shims",
           _PKG / "dsh" / "batches", _PKG / "dsh" / "patches"):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

# ---- flat names the historical layers import (they are loaded read-only) ----
from world_execute_replica.tui import kit as _tk
sys.modules["tuikit"] = _tk

from world_execute_replica.tui.engine import core as _engine
sys.modules["engine"] = _engine
from world_execute_replica.tui.engine import dancer as _dancer
sys.modules["dancer"] = _dancer
from world_execute_replica.tui.engine import music as _music
sys.modules["music"] = _music
from world_execute_replica.tui.engine import choreo as _choreo
sys.modules["choreo"] = _choreo
from world_execute_replica.tui.engine import rig as _rig
sys.modules["rig"] = _rig
from world_execute_replica.tui.engine import motion as _motion
sys.modules["motion"] = _motion
from world_execute_replica.tui.engine import facts as _facts
sys.modules["facts"] = _facts
from world_execute_replica.tui.engine import direction as _direction
sys.modules["direction"] = _direction
from world_execute_replica.tui.engine import stage as _stage
sys.modules["stage"] = _stage
from world_execute_replica.tui.engine import transitions as _transitions
sys.modules["transitions"] = _transitions

# sections first: engine.builder's register() dynamically imports the sec_* names
from world_execute_replica.tui.engine.sections import (intro, verse1, verse2, chorus1, chorus2, final, outro)
sys.modules["sec_intro"] = intro
sys.modules["sec_verse1"] = verse1
sys.modules["sec_verse2"] = verse2
sys.modules["sec_chorus1"] = chorus1
sys.modules["sec_chorus2"] = chorus2
sys.modules["sec_final"] = final
sys.modules["sec_outro"] = outro

from world_execute_replica.tui.engine import builder as _build
sys.modules["build"] = _build

from world_execute_replica.tui.continuity import kit as _cont_kit
sys.modules["kit"] = _cont_kit
# NOTE: timeline/dancer_playback/rig_tracker are NOT imported here on purpose.
# timeline's module body runs `h3_full.install()` which patches PIL.Image.open
# to forbid whale-*.webp reads — the pages batches read those files directly.
# Every real consumer imports them lazily inside functions (render path only).

from world_execute_replica.tui.continuity.scenes import (base, boot, chorus1, deploy, eval as _eval,
                                                         exec as _exec, reward, sft, userleft)
sys.modules["scenes"] = base
sys.modules["scenes_boot"] = boot
sys.modules["scenes_chorus1"] = chorus1
sys.modules["scenes_deploy"] = deploy
sys.modules["scenes_eval"] = _eval
sys.modules["scenes_exec"] = _exec
sys.modules["scenes_reward"] = reward
sys.modules["scenes_sft"] = sft
sys.modules["scenes_userleft"] = userleft

from world_execute_replica.tui.continuity.shots import (boot, pretrain, sft, chorus1, deploy, userleft,
                                                        reward, exec as _sexec, eval as _seval)
sys.modules["s_boot"] = boot
sys.modules["s_pretrain"] = pretrain
sys.modules["s_sft"] = sft
sys.modules["s_chorus1"] = chorus1
sys.modules["s_deploy"] = deploy
sys.modules["s_userleft"] = userleft
sys.modules["s_reward"] = reward
sys.modules["s_exec"] = _sexec
sys.modules["s_eval"] = _seval

from world_execute_replica.dsh import html_frame as _frame
sys.modules["build_frame"] = _frame
from world_execute_replica.dsh import wave as _wave
sys.modules["dsh_wave"] = _wave
from world_execute_replica.dsh import gpu as _gpu
sys.modules["dsh_gpu"] = _gpu
from world_execute_replica.dsh import closeup as _closeup
sys.modules["f2_closeup"] = _closeup
from world_execute_replica.dsh import css as _css
sys.modules["extract_css"] = _css
from world_execute_replica.dsh import icons as _icons
sys.modules["icons"] = _icons
from world_execute_replica.dsh import sung_words as _sung
sys.modules["sung_words"] = _sung

# patches are loaded dynamically by compose.py (importlib.import_module("dsh_patch_<g>"))
from world_execute_replica.dsh.patches import (fix, mem, r1, reward, execution, eval_love)
# dual registration: new semantic names + the old flat names (drop the old names after regression)
for _new, _old in ((reward, "dsh_patch_e"), (execution, "dsh_patch_f"), (eval_love, "dsh_patch_g"),
                  (reward, "dsh_patch_reward"), (execution, "dsh_patch_execution"), (eval_love, "dsh_patch_eval_love")):
    sys.modules[_old] = _new
sys.modules["dsh_patch_fix"] = fix
sys.modules["dsh_patch_mem"] = mem
sys.modules["dsh_patch_r1"] = r1
