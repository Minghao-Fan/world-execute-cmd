# LIVE：在 cmd 窗口实时渲染播放

`world-execute-cmd` 的核心改动：**不再批量渲染视频文件，而是把整支 PV 逐帧实时渲染进终端窗口**，随音乐同步播放。

## 快速开始

```bat
run.bat                          :: 默认播放 input/song.mp3
run.bat --song path\to\any.mp3   :: 换一首歌（任意 ffmpeg 可读格式）
run.bat --no-audio               :: 静默渲染（画面按帧率走）
run.bat --full-post              :: 保留 bloom/扫描线后期（更接近成片，较慢）
run.bat --clean                   :: 先清除可再生缓存（wav/特征/舞者），再重建并播放
cleaner.bat                       :: 按需清除大型过程文件（音频/舞者/__pycache__/预览图/预渲染）
```

也可直接：

```bat
python -m world_execute_replica.live --t0 118   :: 从 REWARD_HACK 段开始
```

首次运行会自动补齐运行时产物（22 kHz wav、音频特征缓存、替身舞者缓存），之后直接播放。

## 窗口布局

```
┌────────────────────┬─┬───────────────────────────────┐
│ dsh · DeepSeek     │ │  右侧：TUI 引擎整幅画面         │
│ session 4471 · ctx │ │  （1280×720 → 半块字符 ▀ 网格，  │
│ ────────────────── │ │   letterbox 等比不变形）        │
│ [sys] 日志 /       │ │                                │
│ [you] 你好▌        │ │                                │
│ [dsh] token soup…  │ │                                │
│ > 你好             │ │                                │
├────────────────────┴─┴───────────────────────────────┤
│ 00:32.0 / 03:32 · 02 / SFT · song.mp3                │
│ ♪ power · protection · creation       空格 暂停 …    │
└───────────────────────────────────────────────────────┘
```

- **左栏**：用文字流模拟原片的 dsh 网页聊天（无 HTML/Playwright）：系统日志、你的消息、模型回复，时间点对齐原片叙事（BOOT 的“你好”与 token soup、PRETRAIN、DEPLOY、USER_LEFT、REWARD_HACK、EXECUTION、EVAL: LOVE、WHALE_FALL）。
- **右栏**：复用原项目的 TUI 渲染管线（`timeline.frame(n)`），每一帧与成片同一函数、同一时钟。
- **底栏**：当前时间 / 章节 / 歌曲名；当前歌词 + 键位提示。

## 控制键

| 键 | 功能 |
|---|---|
| `q` / `Ctrl-C` | 退出 |
| `space` | 暂停 / 继续（音频模式暂停时停止播放，恢复时从暂停点续播） |
| `←` / `→` | 后退 / 前进 5 秒 |
| `[` / `]` | 后退 / 前进 1 秒 |
| `p` | 保存当前 1280×720 帧到 `output/live/frame_NNNNN.png` |
| `h` | 显示 / 隐藏底栏键位提示 |

## 选项

| 选项 | 默认 | 说明 |
|---|---|---|
| `--song PATH` | `input/song.mp3` | 播放的音频（任意时长；画面时间线按原片 211.9 s，歌曲更短则播完即停，更长则播到原片结束） |
| `--cols N` | 160 | 终端列数（右栏按 `cols/4` 左右分栏） |
| `--rows N` | 46 | 终端行数 |
| `--left N` | 自动 | 左栏宽度 |
| `--t0 S` | 0 | 起始时间（秒） |
| `--seconds S` | 0 | 播放 S 秒后自动退出（0 = 播完） |
| `--full-post` | 关 | 保留 bloom/扫描线/暗角后期（慢） |
| `--no-audio` | 关 | 不播放音频，画面按 `--fps` 匀速推进 |
| `--fps N` | 24 | `--no-audio` 模式的目标帧率 |

## 性能与原理

- **音频同步**：`ffplay` 播放所选歌曲，画面时钟跟随音频（暂停/seek 通过重启 ffplay 并 `-ss` 定位实现）。帧渲染慢于 1/24 s 时自动跳帧，时间轴始终正确。
- **默认跳过后期**（bloom / 扫描线 / 暗角），实测约 40–90 ms/帧（≈ 11–24 fps）；`--full-post` 约 90–200 ms/帧。用 `TUI_DANCE=0` 可关掉舞者字符画换取更高帧率。
- **不依赖 Node / Playwright**：左栏是文字模拟，右栏是引擎直接渲染，全程纯 Python + Pillow/NumPy + ffmpeg。

## 代码位置

| 文件 | 职责 |
|---|---|
| `src/world_execute_replica/live/player.py` | 入口 / 装配 / 音频时钟 / 主循环 / 按键 |
| `src/world_execute_replica/live/terminal.py` | 1280×720 → 半块字符 ANSI truecolor 渲染 |
| `src/world_execute_replica/live/chat.py` | 左栏聊天时间线（对齐原片叙事） |
| `run.bat` | 一键：.venv → 运行时产物 → 播放 |
| `scripts/live_smoke.py` / `live_bench.py` / `live_term_test.py` | 装配、性能与渲染验证 |
