# world-execute-replica · 技术规格与 1:1 复刻指南

> **本文档读者**：需要近乎 1:1 复刻本项目的 AI / 工程师。
> **本文档性质**：规格说明（蓝图）。它精确到模块、函数、常量、契约与路径；正文不重复源码，需要细节时按路径读源文件。
> **配合材料**：上游原仓库 `world-execute-me-dsh-pv-main`（作者 MisakaZentai，成片 [BV1xCai6aE9g](https://www.bilibili.com/video/BV1xCai6aE9g/)）；本仓库 `docs/original/` 存有上游 README/NOTICE/LICENSE 备份。
> **不可分发项**：歌曲 `input/song.mp3`（Mili 版权）、歌词原文、上游舞者帧。详见 §14。

---

## 1. 项目速览

一支用代码逐帧渲染的 TUI 风格 PV（Mili《world.execute(me);》的非官方同人作品）：

- **左边**：DeepSeek Harness（dsh）聊天窗口——每一帧是一张静态 HTML 页面（用 dsh 自有 CSS 拼成），由 Playwright 无头 Chromium 截成 PNG；
- **右边**：TUI 模型可视化引擎——Transformer/卷积/RLHF 等概念镜头，全部用 PIL 逐字符画。

**核心原则**：每一帧都是歌曲时间 `t` 的纯函数。24 fps，画布 1280×720，全长 `END = 211.9` 秒。无视频剪辑软件、无手工关键帧、无 dsh 进程、无服务器、不调用任何模型。

**架构形态**：标准 src-layout。唯一顶层包 `src/world_execute_replica/`；数据/代码/资源/历史四分离；历史层保留原始扁平 import，运行时由 `_compat.py` 注册到新路径。

---

## 2. 环境与工具链契约

| 依赖 | 版本 | 说明 |
|---|---|---|
| Python | ≥ 3.12（3.13 兼容） | Pillow + NumPy；3.13 无标准库 `audioop`，由 `_shims/audioop.py` 替代 |
| Node | ≥ 20 | 仅用于 Playwright 截图 |
| ffmpeg / ffprobe | PATH 内 | 音频预处理与最终 mux |
| Playwright Chromium | `npx playwright install chromium` | 无头截图 |
| Windows 字体 | Consolas / Consolab / 微软雅黑 / Segoe UI Symbol | 可经 `PV_F_MONO` / `PV_F_MONO_B` / `PV_F_CJK` / `PV_F_SYM` 环境变量替换（见 `docs/FONTS.md`） |

依赖清单三处：`pyproject.toml`（Pillow/NumPy、console_scripts `world-execute`、package-data）、`requirements.txt`（pip -r 兼容）、`package.json`（playwright 1.63.0）。`pyproject.toml` 的 `package-data` 必须覆盖 `assets/**`、`dsh/assets/**`、`dsh/vendor/**`、**`dsh/templates/**`（seg.html/dsh_components.css/disclosure_map.json）与 `dsh/tools/*.mjs`（screenshot/mem_shot）**，否则打包会丢文件。

---

## 3. 完整目录树（含职责）

```
world-execute-replica/
├── pyproject.toml / requirements.txt / package.json / package-lock.json   # 三份依赖清单
├── run.bat                         # 一键：环境检测 → 出片（GBK/CRLF，自动提权）
├── clear.bat                       # 一键：清理全部过程文件（保留原始文件与 output/）
├── README.md / NOTICE.md / LICENSE # 文档与许可（复刻版；原版备份在 docs/original/）
├── .gitignore                      # 运行产物忽略规则（见 §10）
│
├── src/world_execute_replica/      # ★ 唯一顶层包
│   ├── __init__.py
│   ├── __main__.py                 # python -m world_execute_replica → cli.build.main
│   ├── _compat.py                  # ★ 兼容层：46 个扁平别名 → 新包路径（§5.1）
│   ├── _shims/audioop.py           # Python 3.13 audioop 替代实现（消费方 engine/music.py）
│   │
│   ├── cli/build.py                # 出片流水线入口：check/lyrics/prep/dancer/pages/render/archive
│   ├── lyrics/fetch.py             # 歌词：fetch（LRCLIB 36914646）+ merge（sha256 校验重建）
│   ├── dancer/
│   │   ├── placeholder.py          # 替身舞者：用 maid-left.webp 生成全部 take（44 帧 loop 摆动）
│   │   └── schedule.py             # pv_full：MMD 舞蹈时间线（T0/TIMELINE），install() 返回 v2/h3
│   │
│   ├── dsh/                        # ★ 左侧 dsh 窗口
│   │   ├── compose.py              # dsh_her：最终合成入口（render 子命令 + install() 补丁链）
│   │   ├── html_frame.py           # build_frame：单帧 HTML 构建
│   │   ├── wave.py                 # dsh_wave：顶栏实时波形（ECG）
│   │   ├── gpu.py                  # dsh_gpu：可选 CUDA 后期（torch）
│   │   ├── closeup.py              # f2_closeup：特写镜头
│   │   ├── icons.py / sung_words.py / css.py   # 图标 SVG / 逐词歌词 / CSS 提取
│   │   ├── batches/                # 段落页面脚本（按时间序）：boot→pretrain→verse1→alignment→
│   │   │   │                       #   deploy→separator→reward→execution→eval_love
│   │   │   └── separator.py        # seg_page：分隔页；运行时重写 dsh/seg.html（§6.4）
│   │   ├── patches/                # 运行时内存补丁：fix/r1/mem/reward/execution/eval_love
│   │   ├── templates/              # seg.html / dsh_components.css / disclosure_map.json（提交模板）
│   │   ├── tools/                  # screenshot.mjs / mem_shot.mjs（Playwright 截图）
│   │   ├── assets/mem_sprites/     # mem 补丁的记忆卡 sprite
│   │   └── vendor/                 # dsh-client-ui-cordis / dsh-web-frontend（均带 LICENSE）
│   │
│   ├── tui/                        # ★ 右侧 TUI 引擎
│   │   ├── kit.py                  # tuikit：字符画原语（画布/字体/配色/后期）
│   │   ├── engine/                 # 引擎本体：core.py(画布/时钟) choreo.py music.py rig.py
│   │   │   │                       #   dancer.py direction.py facts.py motion.py stage.py
│   │   │   │                       #   transitions.py builder.py
│   │   │   └── sections/           # sec_*：intro verse1 verse2 chorus1 chorus2 final outro
│   │   ├── continuity/             # 成片编排：timeline.py(v2) kit.py cuts.py words.py
│   │   │   │                       #   dancer_playback.py(h3_full) rig_tracker.py(grok_rig)
│   │   │   ├── shots/              # s_*：boot pretrain sft chorus1 deploy userleft reward exec eval
│   │   │   └── scenes/             # scenes_*：base boot chorus1 deploy eval exec reward sft userleft
│   │   └── history/                # ★ 历史层（运行时加载，不能删/改名）：v1/ chorus/ sidebar/ ascii/
│   │
│   └── assets/                     # 包内共享资源
│       ├── fonts/                  # Anton-Regular.ttf / SpaceMono-Bold.ttf（OFL 1.1）
│       ├── mascot/whale_maid_expanded_20260926/   # maid-left.webp + expressions/ + sources/（CC BY-NC-SA 4.0）
│       └── audio/                  # 运行时生成 song_mono22k.wav（gitignore）
│
├── data/
│   ├── song.json                   # 歌曲指纹（sha256/时长/格式），check 步骤校验
│   ├── h3_takes.json               # 舞者 take 清单（帧数/图像索引）
│   ├── timing/                     # 无歌词文本的逐词时间（三件套，§7）
│   └── lyrics/lyrics_synced.lrc    # 运行时由 merge 重建的同步歌词（target）
├── input/                          # song.mp3 + lyrics.lrc（自备，gitignore 白名单靠 README.md）
├── build/                          # 渲染临时产物（gitignore）：film.mp4 / film_master.mp4 / film_4k.mp4
├── output/YYYY-MM-DD-NN/           # 归档成片：film.mp4(+4k) + RESULT.md（.gitkeep 保留目录）
├── docs/                           # ASSET_SOURCES / FONTS / HOW_IT_WORKS / pipeline / original/ 备份
├── scripts/e2e_smoke.py            # 跨语言冒烟（歌词 + 一个批次 + 截图计数）
├── tests/                          # conftest.py + test_lyrics/test_tui_engine/test_continuity
└── LICENSES/                       # CC-BY-NC-SA-4.0.txt / React-MIT.txt / README.md
```

---

## 4. 出片流水线（cli/build.py）

入口命令：`python -m world_execute_replica <all|check|lyrics|prep|dancer|pages|render>`（`run.bat` 内部等价于 `all`）。

| 步骤 | 函数 | 做什么 | 关键输入 → 产物 |
|---|---|---|---|
| check | `check()` | 工具/字体/Playwright/song 指纹校验 | `data/song.json` vs `input/song.mp3`（sha256，不匹配仅告警不失败） |
| lyrics | `lyrics()` | 缺 `input/lyrics.lrc` 则 `fetch`（LRCLIB 36914646）；`merge` 重建两文件 | `data/timing/*_notext.json` → `data/lyrics/lyrics_synced.lrc` + `data/timing/word_timeline.json`（sha256 必须命中，否则**什么都不写**并退出） |
| prep | `prep()` | ffmpeg 转 22 kHz 单声道 wav | `input/song.mp3` → `assets/audio/song_mono22k.wav`（存在则跳过） |
| dancer | `dancer()` | 替身舞者 | `assets/mascot/.../maid-left.webp` + `data/h3_takes.json` → `dancer/pv_cache/` + `tui/continuity/cache/h3_full_v1/`（已存在则跳过） |
| pages | `pages()` | 逐段落生成 HTML 帧并截图 | 9 个 `batches/*.py` → `batches/*_frames.json`；`node tools/screenshot.mjs batches/*_frames.json` → `dsh/dsh_frames/NNNNN.png` |
| render | `render(a)` | compose 并行渲染无损母版 → mux 成片 | `dsh/compose.py render 0 211.9 film_master.mp4 N` → `build/film_master.mp4`；ffmpeg mux → `build/film.mp4`（--4k 另有 `film_4k.mp4`） |
| archive | `archive()` | 成功出片后归档 | `build/film.mp4` → `output/YYYY-MM-DD-NN/film.mp4` + `RESULT.md`（序号 = 当日已有归档数 + 1） |

**关键常量**（build.py）：

```python
END = 211.9          # 歌曲时长，向下取整到帧
CHIME_MS = 207873    # 结尾提示音插入时刻（ms），来自 batches/eval_love.py CHIME_T
FPS = 24
PAGES = ["boot", "pretrain", "verse1", "alignment", "deploy", "separator", "reward", "execution", "eval_love"]
FRAMES = {**同键**, "separator": "seg"}   # 截图用的 frames json 名
```

**环境变量契约 `env()`**：`PYTHONUTF8=1`、`PV_PACKAGE_JSON=<root>/package.json`（供 `createRequire`）；`PYTHONPATH` 按序注入 `[PKG.parent, _shims, tui, tui/engine, tui/engine/sections, tui/continuity, tui/continuity/shots, tui/continuity/scenes, dancer]`。**DSH 目录刻意不在 PYTHONPATH**——`dsh/wave.py` 会遮蔽标准库 `wave`（batches 的 chime 写入依赖它）。

**mux 参数（render）**：`-filter_complex "[1:a]atrim=0:211.9,asetpts=PTS-STARTPTS[s];[2:a]adelay=207873|207873[c];[s][c]amix=inputs=2:duration=first:normalize=0[a]"`（1=歌曲、2=chime）；`-vf scale=out_color_matrix=bt709:out_range=tv,format=yuv420p`；x264 `-crf 16 -preset slow`；--4k 为 `scale=3840:2160:flags=neighbor` + x265。

---

## 5. 运行时装配机制（最高风险区）

### 5.1 `_compat.py`：54 个别名

历史层代码保留原始扁平 import（`import engine`、`import tuikit as tk`、`import sec_*`、`import s_*`…）。`_compat.py` 在**每个入口点**（`__main__`、compose、schedule、placeholder、conftest）最先被 import，用 `sys.modules[扁平名] = 新模块` 注册。全文件共 **49 行注册、54 个别名**（另有 1 行把标准库 `wave` 固定回 stdlib——防 `dsh/wave.py` 遮蔽；patches 的新旧双名在一行循环里展开）：

| 扁平名 | 目标 | 扁平名 | 目标 |
|---|---|---|---|
| `tuikit` | `tui.kit` | `sec_intro..sec_outro`(7) | `tui.engine.sections.*` |
| `engine` `dancer` `music` `choreo` `rig` `motion` `facts` `direction` `stage` `transitions`(10) | `tui.engine.*` | `scenes` `scenes_boot..userleft`(9) | `tui.continuity.scenes.*` |
| `build` | `tui.engine.builder` | `s_boot..s_eval`(9) | `tui.continuity.shots.*` |
| `kit` | `tui.continuity.kit` | `build_frame` `dsh_wave` `dsh_gpu` `f2_closeup` `extract_css` `icons` `sung_words` | `dsh.{html_frame,wave,gpu,closeup,css,icons,sung_words}` |
| `dsh_patch_fix/mem/r1` | `dsh.patches.{fix,mem,r1}` | `dsh_patch_{e,f,g}` 与 `dsh_patch_{reward,execution,eval_love}` | `dsh.patches.{reward,execution,eval_love}`（新旧双注册） |

**禁令**：`timeline` / `dancer_playback` / `rig_tracker` **不得**在 `_compat.py` 中被 import——`timeline.py` 模块体会调用 `h3_full.install()`，其 patch 会改写 `PIL.Image.open`（禁读 whale webp）；pages 批次需要直读立绘，被提前 import 会静默破坏头像。

### 5.2 `compose.install()` 补丁链

`dsh/compose.py` 是左侧窗口的合成核心。补丁以**内存 patch** 方式注入右侧引擎，签名统一为 `install(D, v2)`（`D` = compose 模块自身，`v2` = 编排对象）：

```python
PATCHES = ["mem", "reward", "execution", "eval_love"]          # compose.py:57
for g in ["fix", "r1"] + PATCHES:                               # compose.py:301
    importlib.import_module(f"world_execute_replica.dsh.patches.{g}").install(sys.modules[__name__], v2)
```

**加载顺序（固定）**：`fix → r1 → mem → reward → execution → eval_love`。各补丁通过三个注册表接管画面：`COVER`（时段接管表）、`LEAD`（主角表，另一方亮度 42%）、`FINISH`（帧级收尾钩子，先到先得）。

### 5.3 history 四层装配链

```
tui/continuity/timeline.py        ← 入口（MODS 表 + CUTS）
  └─ kit.py                       ← 通用绘制积木
       └─ history/v1/full_continuity.py      ← spec_from_file_location 加载
            └─ history/chorus/continuity.py  ← 副歌 OWN 镜头
                 └─ history/sidebar/sidebar.py ← 挂 sys.path、patch dancer.render
                      └─ ascii/convert.py
```

链式加载用 `importlib.util.spec_from_file_location + module_from_spec + exec_module`，路径基于 `PROJECT = tui/` 相对解析。**历史层目录不能删、不能改名、不能改内部扁平 import**。

### 5.4 timeline（v2）装配

- `SECTIONS = ["s_boot","s_pretrain","s_sft","s_chorus1","s_deploy","s_userleft","s_reward","s_exec","s_eval"]`（9 个，可用 `V2_SECTIONS` 环境变量裁剪）；
- 每个 section 模块可声明：`STUB/REPLACE/SPLIT/FULL_ART/SHELL/CUTS/HIDE_HER/OVERLAY/OWN/setup(v1)`（语义见 timeline.py 文档字符串）；
- `MODS` 按名动态加载（`importlib.import_module("...shots." + name[2:])`）→ **改名必须同步**；
- `CUTS = [CUT_CLASSES[i](ALL[i-1], ALL[i]) for i in sorted(CUT_CLASSES)]`；
- `HER = os.environ.get("V2_HER", "h3")`；`"h3"` 时 `h3_full.install()`（生产模式）；
- `HARD_CUT = 4970 / FPS = 207.083`（歌曲 207.08 s 死停，黑场开始）。

---

## 6. 跨语言契约（Python ↔ Node，全部接口）

### 6.1 frames JSON（Python 写 → screenshot.mjs 读）

- 位置：`dsh/batches/{name}_frames.json`（name ∈ FRAMES 映射值，separator → `seg`）；
- 每帧对象字段：`{body, t, sheets, ids, n, measure?}`；
  - `body`：注入 `#app` 的 HTML 字符串（可能含 `src="avatars/..."` 相对路径）；
  - `t`：歌曲时间（秒），动画 pin 用：`getAnimations().forEach(a => a.currentTime = (t*1000) % duration)`；
  - `sheets`：本轮启用的样式 id 子集（全集 7 个：`s-vendor s-index s-components s-palette s-bare s-code s-pv`）；`ids` 为全部 7 个 id，截图前 `disabled = !sheets.includes(id)`；
  - `n`：帧号 = `round(t × 24)`；
  - `measure`：true 时截图后量 `.cur` 光标位置写 `dsh/cursor.json`。

### 6.2 截图输出

- `node tools/screenshot.mjs [frames.json] [frame numbers...]`，默认 `seg_frames.json`；
- viewport `354×537`，deviceScaleFactor 1（即 `dsh_frames/NNNNN.png` 尺寸）；
- 页面加载 `dsh/templates/seg.html`（**不是** dsh/seg.html，见 6.4）；等待 `document.fonts.ready`；
- `src="avatars/..."` 在注入前改写为 `file://…/dsh/avatars/` 绝对路径；
- 输出 `dsh/dsh_frames/{String(n).padStart(5,"0")}.png`；每帧截图前 `Promise.all([...document.images].map(i => i.decode()))`；首帧前等待 150 ms。

### 6.3 mem 补丁链（附加截图）

`patches/mem.py` 写 `dsh/mem.html`（取 `templates/seg.html` 的 `<head>` 拼记忆卡）→ `node tools/mem_shot.mjs` 截图 → `dsh/assets/mem_sprites/*.png`。**sprite 不存在时 mem 补丁静默失效**（不报错），回归时必须抽查记忆气泡帧。

### 6.4 双 seg.html 契约（易错点）

| 文件 | 谁写 | 谁读 | 作用 |
|---|---|---|---|
| `dsh/templates/seg.html` | 仓库提交的模板 | `screenshot.mjs`（每帧）、`patches/mem.py`（取 head） | 出片页面模板 |
| `dsh/seg.html` | `batches/separator.py:607` 每次运行重写 | `batches/eval_love.py:526`（`measure()` 量光标） | 分隔页完整页面 |

两者**没有一致性校验**。`.gitignore` 已忽略 `dsh/seg.html`（运行产物）；`clear.bat` 不删它（prep 前会被重写）。复刻时保持这个双文件布局，不要合并。

### 6.5 其他跨语言产物

| 产物 | 写 | 读 | 说明 |
|---|---|---|---|
| `dsh/avatars/`（PNG） | `batches/*.py`（运行时） | `screenshot.mjs`（`src="avatars/..."`） | 构建生成，gitignore |
| `dsh/avatars/g/caret.json` | `eval_love.measure()` | 补丁 g | 光标位置 |
| `dsh/chime_g.wav` | `eval_love`（batches 阶段） | `render`（ffmpeg mux） | 结尾提示音 |
| `dsh/cursor.json` | `screenshot.mjs`（measure 帧） | `compose` | 光标 rect |
| `dsh/mem.html` | `patches/mem.py` | `mem_shot.mjs` | 记忆卡页面 |
| `dsh/wave_rms_1ms.npy` | `dsh/wave.py` | 自身缓存 | 波形 RMS |

---

## 7. 数据格式

### `data/song.json`
```json
{"title": "Mili - world.execute(me);", "sha256": "79c4e536…", "duration_s": 211.913,
 "codec": "mp3", "sample_rate": 44100, "channels": 2, "bit_rate": 320000, "note": "…"}
```
check 步骤仅告警不失败（`timing matches original` 标记进 RESULT.md）。

### `data/timing/`（无歌词文本）
- `lyrics_synced_notext.json`：`{lines: [{sha256, tag, pre, post, len}], target, format, sha256}`——`merge` 用 `tag+pre+text+post` 重建 LRC；
- `word_timeline_notext.json`：`{skeleton: {lines: [{id}], words: [{line_id, word_index}]}, patches: [{line_id, ops}]（reorder_words / replace_words）, target, format, sha256}`；
- 输出 `word_timeline.json`（带 text，skeleton 内联）。

### `data/lyrics/lyrics_synced.lrc`
`merge` 的 target；`engine/choreo.py` 在 import 时读取（cut 时间与 `lyric_start()` 查找全挂在它上面）。

### `data/h3_takes.json`
每个 take 的帧数与图像索引清单；`placeholder.py` 按它生成同等帧数的替身。

---

## 8. 关键常量与不变量（引擎 core.py / kit.py）

| 常量 | 值 | 意义 |
|---|---|---|
| `FPS` | 24 | 全局帧率 |
| `BPM` / `BEAT` | 130.0 / `60/130` | 节拍网格 |
| `FIRST_BEAT` | 0.1587 s | 第一拍时刻（engine 侧；placeholder 用 0.1807，两者各有用途） |
| `SONG_LEN` / `END_T` | 211.91 / 211.0 | 歌曲长 / 视频长 |
| `HARD_CUT` | 207.58 s | 静音检测的硬切点（timeline 侧重算为 207.083） |
| 画布区域 | `LEFT(24,56,384,604)` `CENTER(404,56,1164,604)` `TICK(1180,56,1256,604)` | 三栏布局（框内） |
| `CHAPTERS` | 0 BOOT / 16 PRETRAIN / 44 SFT / 58.5 RLHF / 73.5 DEPLOY / 103 USER_LEFT / 118 REWARD_HACK / 147.4 EXECUTION / 176.9 EVAL: LOVE / 193.4 WHALE_FALL | 章节 |
| `KEYWORDS` | 43 个词（power/execution/love…） | 歌词 token 高亮 |
| `ui_gain(t)` | (0,1.0)(110.4,1.0)(116.5,0.42)(176.9,0.42)(179.5,0.85)(193,0.75)(206,0.45) | 系统色=“你”，离开后不再满 |

**不变量（tests 覆盖）**：`MODS == 9`、`CUTS > 0`、`ALL > 0`、`HER == "h3"`、`WORDS` 为带 `text` 的 list、`FPS == 24`、`BEAT > 0`、字体对象非空。

---

## 9. 舞者（替身）机制

- 原片舞者帧**不在仓库**；`placeholder.py` 用 `maid-left.webp` 生成**同名、同帧数、同文件名**的替身 take，渲染逻辑零改动；
- 运动模型：一小节（4 拍）渲染为 `LOOP` 帧的循环，每个 take 的每帧按该 take 在影片中播放的时刻（`schedule.T0` 与 `h3_full.PLAN`）落在节拍网格上取对应循环帧——摆动一拍一次、下沉每拍一次；
- 输出两种格式（同一 take）：
  - `<cache>/<take>.json`：45×70 字符网格（每格 6×12 px），`{frame, art, shade, part}`；
  - `<cache>/rgba/<take>/NNN.png`：420×540 RGBA，脚踩 y=528，鞋心 x=228；
- 缓存目录：`dancer/pv_cache/`（schedule 读）+ `tui/continuity/cache/h3_full_v1/`（dancer_playback 读）；`_standin.json` 记录工具写过哪些 take，**未写的 take 永不覆盖**（可放自己的真实舞者帧，同名即可替换）；
- `schedule.py TIMELINE`：`keep`（沿用原 h3 条目）/ `direct`（原时刻直接播放）/ `reuse`（副歌 2 与红副歌复用副歌 1、EXECUTION 闪回复用 pilot）；`T0` 为各 take 的起始时刻表。

---

## 10. 一键脚本契约（run.bat / clear.bat）

- **编码**：GBK(936) + CRLF，`chcp 65001` 后输出中文；**自动提权**（`net session` 探测 → PowerShell `Start-Process -Verb RunAs` 重启自身）；`cd /d %~dp0` 定位根目录。
- **run.bat**（5 步检测 + 出片）：
  1. `.venv` 创建 + Pillow/NumPy 安装与 import 自检；
  2. 关键文件完整度（清单：cli/build.py、data/song.json、tui/kit.py、tui/engine/core.py、tui/continuity/timeline.py、tui/history/sidebar/sidebar.py、dsh/compose.py）；
  3. Node 官方版检测（`C:\Program Files\nodejs\npm.cmd`——**不是** PATH 里的其他 node）+ `npm install` + `npx playwright install chromium` + ffmpeg；
  4. `input/song.mp3` 存在性；
  5. `build.py check` 全量自检。
  任一步失败 → 汇总 `[缺失]` → `pause` 退出；成功 → `build.py all` → 完成提示。
- **clear.bat**（清理项见源码，均为运行产物）：`build/`、`dsh/dsh_frames/`、`dsh/segments/`、`dancer/pv_cache/`、`tui/continuity/cache/`、`dsh/avatars/`（含历史错位目录）、`*_frames.json`、`chime_g.wav`、`cursor.json`、`mem.html`、`wave_rms_1ms.npy`、`assets/audio/song_mono22k.wav`、`tui/engine/audio_features.json`、全部 `__pycache__`、`.pytest_cache`、egg-info。**保留**：原始文件、`output/` 成片、`templates/seg.html`（前置依赖）。

> **已知缺陷（复刻时修正）**：run.bat 的关键文件清单仍含已迁移的 `src\world_execute_replica\dsh\shim\audioop.py`（audioop 已在重构中迁至 `_shims/audioop.py`，`dsh/shim/` 不存在）→ 该行会误报 `[缺失]`。应改为 `src\world_execute_replica\_shims\audioop.py`。同理 `scripts/e2e_smoke.py` 仍调用旧名 `batches/a1.py`（现为 `batches/boot.py`），复刻时一并修正。

---

## 11. 测试与验证

- `tests/`：conftest（引导：`lyrics merge` → `prep` → 注入 `_shims` → `import music.table()` → `import _compat`）+ 3 个测试文件（§8 不变量）。运行：`.venv\Scripts\python.exe -m pytest tests -q`（当前 7 passed）。
- `scripts/e2e_smoke.py`：歌词 merge + 一个批次页 + 截图计数（修正 §10 缺陷后可用）。
- **全量回归**：`python src\world_execute_replica\cli\build.py all` → 归档 `output/YYYY-MM-DD-NN/` → ffmpeg 抽帧抽查关键段：BOOT(f6)、PRETRAIN(f24)、REWARD_HACK+mem(f120)、EXECUTION(f160)、EVAL:LOVE(f190)。
- 关键抽帧时刻的**判定点**：头像非破图、dsh 窗口排版正常、mem 记忆气泡出现（`last_message.txt` 生效）、字符画无错位。

---

## 12. 已知坑与维护警告

1. **history/ 与 _compat.py 是契约核心**：不删、不改名、不统一扁平名；任何 shots/scenes/sections/patches 改名都必须「先双别名 → pytest → 全量出片 → 对比成片 → 删旧名」。
2. **`timeline` 不可被提前 import**（PIL.Image.open 补丁会禁读立绘）。
3. **`dsh/` 不能进 PYTHONPATH**（`wave.py` 遮蔽标准库 `wave`）。
4. **双 seg.html** 是刻意布局，无一致性校验；合并需回归 G 段 caret 测量。
5. **mem 补丁静默失效**：sprite 目录缺失时 `install()` 直接 return，不报错。
6. **avatars 是运行时产物**：首次 pages 才会生成 `dsh/avatars/`；清空后需重跑 pages。
7. **audioop**：3.13 下 `_shims/audioop.py` 必须先于 `music.py` 进 sys.path（conftest/build.env 均已处理）。
8. **歌词 merge 是硬校验**：LRC 文本不一致会拒绝写文件（sha256 全链核对），这是防漂移设计。
9. 文档（README/NOTICE）路径必须跟随架构（src-layout）；`docs/original/` 是上游备份，不要改。

---

## 13. 1:1 复刻执行清单（给另一个 AI）

1. **取材**：从上游仓库复制素材与数据——`assets/mascot/whale_maid_expanded_20260926/`（立绘/表情/sources）、`assets/fonts/*.ttf`、`dsh/vendor/*`（含 LICENSE）、`dsh/templates/*`（seg.html、dsh_components.css、disclosure_map.json）、`dsh/tools/*.mjs`、`data/`（song.json、timing/、h3_takes.json）、`input/README.md`。歌曲/歌词自备。
2. **建骨架**：按 §3 目录树创建全部目录与 `__init__.py`；`pyproject.toml`/`requirements.txt`/`package.json` 按 §2。
3. **搬代码**：引擎（tui/kit.py + engine/ + sections/）→ 编排（continuity/ + shots/ + scenes/ + history/）→ 窗口（dsh/）→ 舞者（dancer/）→ 歌词（lyrics/）→ 入口（cli/build.py、__main__.py）。
4. **装配**：写 `_compat.py`（§5.1 全表）；确认 compose.install 顺序（§5.2）；确认 timeline MODS/CUTS/HER（§5.4）；确认 env() 的 PYTHONPATH（§4，DSH 缺席）。
5. **跨语言**：按 §6 契约实现/核对 screenshot.mjs、mem_shot.mjs；保持双 seg.html 布局；帧名 padStart(5)。
6. **一键脚本**：按 §10 写 run.bat / clear.bat（GBK+CRLF），并修正两个已知缺陷（shim 路径、e2e 旧名）。
7. **测试**：按 §11 建 tests/ 与 conftest；`pytest tests -q` 全绿。
8. **回归**：`build.py all` 全量出片；按 §11 抽帧清单人工判定；归档进 `output/` 并核对 RESULT.md。
9. **文档与许可**：按复刻版重写 README/NOTICE（本项目已重写，可直接参考）；LICENSES/ 放 CC/React 全文；OFL 文本需自补（见 §14）。

---

## 14. 许可边界

| 内容 | 许可 | 能否随复刻分发 |
|---|---|---|
| 代码（.py/.mjs/.html 自写部分） | MIT | ✅ |
| 鲸鱼娘立绘/表情及派生（替身、头像、成片形象） | CC BY-NC-SA 4.0（署名链：溟月©上善无形 → ZipZipPipe → Small-tailqwq → dsh-whale-galgame） | ✅ 非商用、保留署名、同协议分享 |
| dsh 前端（vendor/、templates/dsh_components.css、disclosure_map 类名） | MIT © 2026 DeepSeek | ✅ 保留 MIT 标头与 React-MIT.txt |
| 字体（Space Mono / Anton） | SIL OFL 1.1 | ✅ 本仓库未附带 OFL 文本，复刻时自行补齐 |
| 歌曲/歌词 | Mili 版权 | ❌ 自备；个人非商用二创按 [Mili 指引](https://projectmili.com/copyright-guidelines) |
| 上游舞者帧 | 授权未确认 | ❌ 用替身替代 |

完整署名链与证据范围见 `NOTICE.md`、`docs/ASSET_SOURCES.md`、`docs/original/`。
