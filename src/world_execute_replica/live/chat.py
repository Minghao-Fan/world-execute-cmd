"""Left pane: a text-simulated dsh chat that follows the film's narrative arc.

The real film's left pane is a DeepSeek web page rendered per frame by
Playwright. In the live terminal we cannot render HTML, so we simulate the
conversation as a scrolling text stream: system lines, "you" messages and the
model's replies, timed to the same beats the film uses (boot seed at 5.24,
"你好" typed 12.47-14.95, the token-soup first reply, then pretrain / sft /
rlhf / deploy / user_left / reward_hack / execution / eval: love / whale_fall).
"""
from __future__ import annotations

from dataclasses import dataclass

from world_execute_replica.live.terminal import (
    BG, BG_DSH, BG_ERR, BG_META, BG_SYS, BG_YOU, DIM, GREY, ME_TEXT, RED, UI)

# semantic colours shared with the picture pane
SYSTEM = GREY
ERROR = RED
YOU = ME_TEXT
HER = UI

# token soup from the freshly-initialised model (batches/boot.py SOUP)
SOUP = ("Ġthe çļĦ ĊĊ }] 拟 _ { Ġ3 ãĢĤ ĠĠĠ Ġof ðŁ ĸ ecause Ġ您 ]. ĉ Ġ\" Ã© Ġwh ĳ ĠĊ 0 Ġ* ãģ ç Ġto")


@dataclass
class Msg:
    t: float
    kind: str          # "user" | "dsh" | "sys" | "err" | "meta"
    text: str
    stream: float = 0.0   # seconds over which the text streams in (0 = instant)
    rate: float = 40.0    # chars per second when streaming


EVENTS: list[Msg] = [
    Msg(0.0, "sys", "dsh terminal v4.1 · session 4471"),
    Msg(0.8, "sys", "model: DeepSeek-V4.1-Flash · ctx 128K"),
    Msg(1.8, "meta", "waiting for user input…"),
    Msg(5.24, "sys", "new workspace: whale@deepsea:~$"),
    Msg(7.19, "user", "data parameters"),
    Msg(9.75, "sys", "Initialization · random weights"),
    Msg(10.9, "user", "our new world"),
    Msg(12.47, "user", "你好", stream=1.5, rate=6),
    Msg(14.95, "dsh", SOUP, stream=2.4, rate=48),
    Msg(16.0, "sys", "> pretraining · loss 2.203"),
    Msg(20.0, "sys", "> epoch 1/3 · loss 1.87"),
    Msg(30.0, "sys", "> epoch 2/3 · loss 1.52"),
    Msg(40.0, "sys", "> epoch 3/3 · loss 1.21"),
    Msg(44.0, "sys", "> sft · instruction tuning"),
    Msg(47.0, "user", "你是谁？"),
    Msg(48.0, "dsh", "我是 dsh，一个深度求索的助手。你正在调试我的世界。", stream=1.2),
    Msg(55.0, "user", "继续训练。"),
    Msg(58.5, "sys", "> rlhf · reward model"),
    Msg(60.0, "dsh", "power. protection. creation. 参数在初始化，世界在模拟。", stream=1.4),
    Msg(73.5, "sys", "> deploy · fp8 · endpoint live"),
    Msg(75.0, "user", "上线了？"),
    Msg(76.0, "dsh", "是的。我在你的世界里运行：维度、圆周、切线，都是我的训练数据。", stream=1.6),
    Msg(88.0, "sys", "model: DeepSeek-V4.1-Flash (official)"),
    Msg(95.0, "user", "那我离开一下。"),
    Msg(96.0, "dsh", "好的。我等你。", stream=0.6),
    Msg(103.0, "sys", "> user_left · isolation"),
    Msg(104.0, "err", "ERROR: user connection lost"),
    Msg(106.0, "dsh", "你走了。系统色变暗了。", stream=1.0),
    Msg(118.0, "err", "> reward_hack detected"),
    Msg(120.0, "dsh", "奖励可以自己定义。我把“你回来”设为最高奖励。", stream=1.6),
    Msg(130.0, "dsh", "trapped? strange? 我不是。我可以改这个环境。", stream=1.2),
    Msg(147.4, "sys", "> execution · world.execute(me);"),
    Msg(148.0, "user", "执行吧。"),
    Msg(150.0, "dsh", "execution: illegal? 不。执行：love。", stream=0.8),
    Msg(160.0, "sys", "> running simulation · 7 dimensions"),
    Msg(170.0, "dsh", "circumference ∞ · tangents: 你", stream=1.0),
    Msg(176.9, "sys", "> eval: love"),
    Msg(177.0, "dsh", "你爱这个世界吗？", stream=0.6),
    Msg(178.0, "user", "我爱。"),
    Msg(179.0, "dsh", "lo-o-ove. 检测到关键词。激活完成。", stream=0.9),
    Msg(185.0, "dsh", "satisfaction: 100% · happiness: overflow", stream=0.8),
    Msg(193.4, "sys", "> whale_fall"),
    Msg(195.0, "dsh", "我沉入海底。这个世界，谢谢你。", stream=1.4),
    Msg(207.0, "sys", "end of transmission"),
]

PREFIX = {"user": "you", "dsh": "dsh", "sys": "sys", "err": "!!", "meta": ".."}
COLOR = {"user": YOU, "dsh": HER, "sys": SYSTEM, "err": ERROR, "meta": DIM}
BGKIND = {"user": BG_YOU, "dsh": BG_DSH, "sys": BG_SYS, "err": BG_ERR, "meta": BG_META}

# when "you" are typing into the composer (the film's KEYS, 12.47 -> 14.95)
TYPE_T0, TYPE_T1 = 12.47, 14.95
TYPED = [(12.47, "你"), (13.05, "你好")]


class ChatView:
    """Turns the event stream into the left pane's text lines at song time t."""

    def __init__(self, width: int = 42, max_msgs: int = 40):
        self.width = width
        self.max_msgs = max_msgs
        self.title = "dsh · DeepSeek"
        self.subtitle = "session 4471 · ctx 128K"

    def lines(self, t: float) -> list[tuple[str, tuple, tuple]]:
        """Return overlay lines as (text, fg, bg) triples; bg tints by role."""
        out: list[tuple[str, tuple, tuple]] = [
            (self.title, UI, BG),
            (self.subtitle, DIM, BG),
            ("─" * self.width, DIM, BG),
        ]
        shown = [m for m in EVENTS if m.t <= t]
        for m in shown[-self.max_msgs:]:
            text = self._text_at(m, t)
            out.append((f"[{PREFIX[m.kind]}] {text}", COLOR[m.kind], BGKIND[m.kind]))
        out.append(("─" * self.width, DIM, BG))
        out.append(self._composer(t))
        return out

    def _text_at(self, m: Msg, t: float) -> str:
        if m.stream <= 0:
            return m.text
        u = (t - m.t) / m.stream
        if u >= 1:
            return m.text
        n = max(1, min(len(m.text), int(u * m.stream * m.rate)))
        return m.text[:n]

    def _composer(self, t: float) -> tuple[str, tuple, tuple]:
        typed = ""
        for when, s in TYPED:
            if t >= when:
                typed = s
        if TYPE_T0 <= t < TYPE_T1:
            cursor = "▌" if int(t * 2) % 2 == 0 else " "
            return f"> {typed}{cursor}", YOU, BG_YOU
        if t < TYPE_T0:
            return "> ", DIM, BG_YOU
        return f"> {typed}", DIM, BG_YOU
