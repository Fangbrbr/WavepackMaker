# WavePack Maker - Agent 指南

> 本文件面向 AI 编码 Agent。阅读者应当被假设为对该项目一无所知。若你修改了本文件提及的流程、架构或约定，请同步更新本文件与 `README.md`。

## 1. 项目概述

**WavePack Maker** 是面向 ESP32Synth（M5Stack Tab5 / ESP32-P4）的 Windows 桌面音色打包/编辑上位机工具。

- **上位机工程文件**：`.wpp`，JSON 格式，用于管理音色身份证元数据、采样清单与 Zone 映射。
- **下位机输出文件**：`.wavepack`，二进制格式，符合 `doc/WavePack_for_ESP32Synth_TechSpec_v1.1.md`。
- **目标平台**：ESP32Synth v2.4.x，运行在一个 `.wavepack` 文件代表一个完整音色（Preset）。

核心功能：

- 导入 WAV（16-bit 单声道/立体声，自动混缩为单声道）并复制到工程 `samples/` 目录。
- 为每个采样编辑根音、循环标记，并对 Zone 设置 Note/Velocity 范围、复音模式、ADSR、音高微调。
- 可视化波形、循环区间、裁剪区，以及 88 键钢琴卷帘（A0-C8，MIDI 21-108）。
- 通过虚拟钢琴、PC 键盘映射或 Windows MIDI 输入设备预览音色。
- 一键导出 `.wavepack` 到工程 `output/` 目录，并自动通过结构校验。

## 2. 技术栈

- **Python 3.13**（开发环境使用 `.venv`，CI 使用 `uv`）。
- **PySide6 >= 6.7.0**：GUI 框架；使用 `QtMultimedia.QAudioSink` 做音频预览。
- **PyInstaller >= 6.0.0**：打包为独立 Windows 可执行文件。
- **标准库音频处理**：`wave` + `array`，不使用 NumPy/SciPy/SoundFile。
- **Windows MIDI**：`ctypes` + `winmm.dll`（仅 Windows）。

项目**没有** `pyproject.toml`、`setup.py`、`setup.cfg`、`package.json` 等文件，依赖直接写在 `requirements.txt`。

## 3. 关键配置文件

| 文件 | 作用 |
|------|------|
| `requirements.txt` | 依赖：`PySide6>=6.7.0`、`PyInstaller>=6.0.0`。 |
| `main.py` | 程序入口；初始化 QApplication、主题、主窗口；开发模式会自动刷新 `_version.py`。 |
| `wavepack_maker.spec` | PyInstaller 规格文件；单文件 EXE、无控制台、嵌入 `assets/logo.ico` 与 `assets/logo.png`。 |
| `build_exe.ps1` | 本地一键打包脚本：生成 `logo.ico` → 生成版本信息 → PyInstaller 打包。 |
| `.github/workflows/release.yml` | GitHub Actions：推送 `v*` 标签后自动构建并创建 Release。 |
| `.gitignore` | 忽略 `__pycache__/`、`.venv/`、`build/`、`dist/`、IDE 文件等。 |
| `scripts/gen_version.py` | 从 git 历史生成 `wavepack_maker/_version.py` 与 `build/version_info.txt`。 |
| `scripts/build_logo_ico.py` | 从 `assets/logo.png` 生成多尺寸 `assets/logo.ico`。 |
| `doc/WavePack_for_ESP32Synth_TechSpec_v1.1.md` | `.wavepack` 二进制格式权威规范。 |

## 4. 代码组织

```
.
├── main.py                          # 程序入口
├── wavepack_maker/                  # 核心包
│   ├── __init__.py                  # 导出 WavePackBuilder / WavePackValidator / ValidationError / WAVEPACK_VERSION
│   ├── _version.py                  # 自动生成的版本号与编译时间
│   ├── models.py                    # ProjectMetadata / SampleEntry / ZoneEntry / Project 数据模型
│   ├── project_io.py                # .wpp 读写（JSON）
│   ├── builder.py                   # .wavepack 二进制打包器
│   ├── validator.py                 # .wavepack 结构校验器
│   ├── luts.py                      # 生成下位机用 CentiHz / Cents LUT 头文件
│   ├── audio_player.py              # 基于 QAudioSink 的软件混音预览
│   ├── midi_input.py                # Windows MIDI 输入封装
│   └── widgets/                     # PySide6 GUI 组件
│       ├── main_window.py           # 主窗口与工程生命周期
│       ├── metadata_panel.py        # 工程属性编辑对话框面板
│       ├── sample_list_panel.py     # 采样清单
│       ├── zone_list_panel.py       # Zone 列表（增删/复制）
│       ├── zone_editor.py           # Zone 参数编辑器
│       ├── waveform_view.py         # 波形显示 + Loop/裁剪标记
│       ├── piano_roll.py            # 88 键钢琴卷帘
│       ├── range_slider.py          # 双头范围滑块
│       └── theme.py                 # Windows 主题色读取与 QSS
├── scripts/                         # 构建辅助脚本
│   ├── gen_version.py
│   └── build_logo_ico.py
├── tests/                           # 单元测试
│   └── test_wavepack_maker.py
├── examples/                        # 示例工程
│   ├── default_piano/
│   └── piano_kit/
├── assets/                          # Logo 源图与打包图标
│   ├── logo.png
│   └── logo.ico
└── doc/
    └── WavePack_for_ESP32Synth_TechSpec_v1.1.md
```

## 5. 常用命令

在 PowerShell 中执行（假设已创建 `.venv` 并安装依赖）：

```powershell
# 创建虚拟环境并安装依赖
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

# 运行开发版（必须设置 PYTHONPATH=.）
$env:PYTHONPATH="."
python main.py

# 运行单元测试
$env:PYTHONPATH="."
python tests/test_wavepack_maker.py

# 语法检查（所有代码修改后必须执行）
$env:PYTHONPATH="."
python -m py_compile $(Get-ChildItem wavepack_maker -Recurse -Filter *.py | ForEach-Object { $_.FullName }) main.py scripts/*.py

# 生成本地版本信息
python scripts/gen_version.py

# 从 png 生成 ico
python scripts/build_logo_ico.py

# 打包 Windows 可执行文件
powershell -NoProfile -ExecutionPolicy Bypass -File build_exe.ps1
```

打包产物位于 `dist/WavePackMaker.exe`。`build_exe.ps1` 会依次执行 `scripts/build_logo_ico.py`、`scripts/gen_version.py`，再调用 PyInstaller。

## 6. 测试说明

- 测试框架为纯 Python 函数集合，不依赖 `pytest`。
- 测试文件：`tests/test_wavepack_maker.py`。
- 覆盖范围：
  - `ProjectMetadata` 序列化/反序列化。
  - `SampleEntry.from_wav()` 读取 WAV 元数据。
  - `ZoneEntry.validate()` 对旋律/打击乐 Zone 的校验。
  - `.wpp` 保存/加载、`WavePackBuilder.from_project()` 导出 `.wavepack`、二进制 Header 与版本、`WavePackValidator` 校验。
  - `Sample.root_note` 直接写入二进制 Sample Entry 的验证。

每次修改代码后，必须依次执行语法检查与单元测试。

## 7. 代码风格与约定

- 使用类型注解；函数签名保持与现有代码风格一致。
- 字符串统一使用双引号。
- 中文注释、提示语、错误信息使用标准中文标点。
- 不引入新的外部依赖；如确有必要，先在隔离环境中验证，并更新 `requirements.txt` 与本文件。
- 不要提交用户工程数据（如 `output/`、工程内的 `samples/`）或构建产物（`build/`、`dist/`、`__pycache__/`）。
- 模块间保持松耦合：`models.py` 负责数据结构，`builder.py` 负责二进制打包，`widgets/` 负责 UI。
- UI 回调使用 `_loading_zone` 等标志避免循环触发；编辑控件时通过 `blockSignals` 防止回环。

## 8. 关键架构约束

Agent 在修改代码前必须理解以下约束：

1. **`samples/` 目录是工程采样的唯一事实来源**。内存中的 `project.samples` 必须与磁盘保持双向同步，入口为 `Project.sync_samples_with_directory()`。
2. **Loop 标记保存在 `SampleEntry`**（`loop_start`、`loop_end`），而不是 Zone。打包时若采样存在有效 loop， builder 会在 Zone flags 中追加 `ZONE_FLAG_LOOP`。
3. **采样根音是播放速度的唯一基准**：
   - `SampleEntry.root_note` 是 WAV 真实录制的 MIDI 音高，写入二进制 Sample Entry，供下位机计算播放速度。
   - v1.1 协议已删除 `Zone.root_note`；Zone 仅负责 note/velocity 命中映射。
4. **Zone 设计规则**：
   - 不同 Zone 的 note 范围不允许重叠（工程级校验 `Project.validate()` 会报错）。
   - 旋律 Zone 要求 `min_note < max_note`；打击乐 Zone 要求 `min_note == max_note`。
   - `poly_mode` 取值 `retrigger` / `multi` / `legato`，由 `_encode_flags()` 编码到 flags 的 bit2~3；`max_same_note_voices` 编码到 bit4~7。
5. **钢琴键盘仅显示 88 键**（A0-C8，MIDI note 21-108），见 `PianoRoll.MIN_NOTE` / `MAX_NOTE`。
6. **版本号来自 git 历史**：优先使用当前 commit 对应的 tag，无 tag 时使用 commit 短 hash。版本文件由 `scripts/gen_version.py` 自动生成。
7. **二进制格式**：`.wavepack` 当前版本 `0x0101`；Header 64 bytes、Zone Entry 48 bytes、Sample Entry 32 bytes；PCM 数据区按 4096 bytes 对齐；仅支持 16-bit mono（立体声会在打包时混缩为单声道）。

## 9. 数据模型速查

### 9.1 工程文件 `.wpp`

JSON 格式，顶层字段：

- `__wpp_version`：固定为 `1`。
- `metadata`：`ProjectMetadata` 字典（名称、版本、作者、版权、分类、标签、描述、备注、目标采样率、创建/修改时间）。
- `samples`：`SampleEntry` 数组。
- `zones`：`ZoneEntry` 数组。

### 9.2 `SampleEntry`

| 字段 | 说明 |
|------|------|
| `id` | 8 位 uuid 风格短 ID。 |
| `file_path` | 绝对路径或相对工程文件的路径。 |
| `name` | 显示名，默认取文件名。 |
| `sample_rate` / `channels` / `bits` / `nframes` | WAV 元数据。 |
| `root_note` | 该 WAV 真实录制的 MIDI 音高（0-127）。 |
| `loop_start` / `loop_end` | 循环区间（sample frame，左闭右开）。 |

### 9.3 `ZoneEntry`

| 字段 | 说明 |
|------|------|
| `sample_id` | 指向 `SampleEntry.id`。 |
| `min_note` / `max_note` | Note 命中范围（0-127）。 |
| `min_vel` / `max_vel` | Velocity 命中范围（0-127）。 |
| `poly_mode` | `retrigger` / `multi` / `legato`。 |
| `max_same_note_voices` | 同音最大 Voice 数（1-16）。 |
| `adsr` | `[attack_ms, decay_ms, sustain_level_0_255, release_ms]`。 |
| `pitch_cents` | 音高微调（-100 ~ +100 cents）。 |
| `filter_cutoff` / `filter_resonance` / `reverb_send` | 当前预留，固定写入 0。 |

## 10. GUI 交互与信号流

- `MainWindow` 持有 `Project`、`AudioPlayer`、`MidiInput` 以及各面板实例。
- `SampleListPanel`：选择采样 → `MainWindow._on_sample_selected()` → `WaveformView.load_wav()`。
- `ZoneListPanel`：选择 Zone → `MainWindow._on_zone_selected()` → `ZoneEditor.set_zone()`。
- `ZoneEditor`：字段变更 → `MainWindow._on_zone_edited()` → `ZoneListPanel.refresh()` + 钢琴卷帘更新。
- `WaveformView`：拖动 loop 标记 → `loop_changed` → `MainWindow._on_loop_changed()` → 更新 `SampleEntry.loop_start/end`。
- `PianoRoll`（虚拟键盘）：点击 → `note_clicked` → `MainWindow._on_piano_key_clicked()` → `_play_note()`，按目标 note 与 `sample.root_note` 差值计算播放 rate。
- `MidiInput`：收到 NOTE_ON → `note_on` 信号 → `_on_midi_note_on()` → 同上播放。

## 11. 版本与打包

### 11.1 版本来源

`scripts/gen_version.py`：

1. 尝试 `git describe --tags --exact-match`；命中 tag 则使用 tag（如 `v1.0.0`）。
2. 否则使用 `git rev-parse --short HEAD`（如 `88cf4cc`）。
3. 生成 `wavepack_maker/_version.py`：`__version__`、`__build_time__`（UTC ISO）。
4. 生成 `build/version_info.txt`：PyInstaller 使用的 `VSVersionInfo`（Windows exe 文件属性）。

`main.py` 在开发模式下会静默调用 `scripts/gen_version.py`，确保开发时版本信息最新。正式发布应以 CI 重新生成的 `_version.py` 为准。

### 11.2 Logo

- 源图：`assets/logo.png`（推荐带透明通道的 PNG）。
- 打包用：`assets/logo.ico`（由 `scripts/build_logo_ico.py` 生成 256/128/64/48/32/16 多尺寸）。
- 更换 Logo 后必须重新运行 `build_exe.ps1` 或 `scripts/build_logo_ico.py`。

### 11.3 CI 自动发布

`.github/workflows/release.yml`：

- 触发条件：`push` 的 tag 匹配 `v*`。
- 在 `windows-latest` runner 上：
  1. 检出完整 git 历史（用于获取 tag/commit）。
  2. 安装 Python 3.13 与 `uv`。
  3. `uv venv` 并安装依赖。
  4. 生成 `logo.ico` 与版本信息。
  5. PyInstaller 打包。
  6. 按 tag 重命名产物为 `WavePackMaker-{version}.exe`。
  7. 上传 artifact 并创建 GitHub Release。

## 12. 部署与安全注意事项

- **绝不自行打 Tag / 发版**：见下一节严格规定。
- 项目仅在 Windows 桌面运行；PyInstaller 打包为单文件 EXE，不依赖管理员权限。
- 程序会读取/写入用户指定的 WAV 文件与工程目录，并执行 `shutil.copy2` 导入采样；Agent 不应在未经用户确认时操作用户家目录或系统路径。
- MIDI 输入使用 Windows `winmm.dll` 回调，属于本地 Win32 API 调用；不要尝试在非 Windows 环境启用该模块。
- 不要向仓库提交密钥、token、签名证书或 `.env` 文件；CI 使用默认 `GITHUB_TOKEN`，无需额外 secrets。
- 打包脚本 `build_exe.ps1` 会删除 `dist/` 目录；执行前确保没有需要保留的旧产物。

## 13. ⚠️ 严禁 Agent 自行打 Tag / 发版

**打 Tag、创建 Release、推送到远程仓库发布版本，必须由用户本人给出明确、严肃的指令后才可以执行。**

Agent **绝对不允许**在以下任何场景自行操作：

- 创建 `git tag`
- 删除 `git tag`
- 推送 tag 到远程
- 触发 GitHub Release
- 代替用户决定版本号

Agent 可以做的：

- 修改代码、跑测试、提交到当前分支。
- 向用户报告状态。
- 在用户明确说"打 tag vX.Y.Z 并发布"之后，才执行对应命令。

## 14. 提交流程

1. 修改代码后运行 `python -m py_compile` 确保无语法错误。
2. 运行 `python tests/test_wavepack_maker.py` 确保测试通过。
3. 如果修改了功能、流程或本文件提及的约定，同步更新 `README.md` 与本 `AGENTS.md`。
4. 使用 `git add` 暂存相关文件。
5. 使用 `git commit` 提交，提交信息用中文简要说明修改内容。
6. **只有用户明确说"打 tag vX.Y.Z 并发布"时**，才执行 `git tag vX.Y.Z && git push origin vX.Y.Z`。
