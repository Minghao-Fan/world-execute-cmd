"""Section 01 PRETRAIN (cuts 8-20): the approved sample. Scenes in scenes.py, cuts in cuts.py."""
import world_execute_replica.tui.continuity.cuts as C
import world_execute_replica.tui.continuity.scenes.base as S
import world_execute_replica.tui.engine.sections.intro as sec_intro
import world_execute_replica.tui.engine.sections.verse1 as sec_verse1
STUB = [sec_intro, sec_verse1]
REPLACE = S.REPLACE
SPLIT = S.SPLIT
SHELL = {"shot_limit": "ulimit -a"}
CUTS = C.CUTS


def setup(v1):
    C.SHOT_HOOKS["shot_losscurve"]["xlabel"] = S.counter_text(v1.BYNAME["shot_losscurve"].start)

