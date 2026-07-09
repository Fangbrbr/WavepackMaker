# WavePack Maker — AI 编码代理指南

> 本文件面向 AI 编码代理。阅读前请假设你对本项目一无所知。所有修改代码的行为必须基于本项目的实际文件内容，不要依赖外部假设。

---

## 项目概述

**WavePack Maker** 是面向 ESP32Synth（M5Stack Tab5 / ESP32-P4）的专业音色打包/编辑上位机 GUI 工具。本项目隶属于 TAB5_Music_Pad 项目开发。

核心职责：

- 创建/编辑音色工程文件 `.wpp`（上位机管理用，携带身份证元数据）。
- 导入 WAV 采样，配置 Zone 映射、ADSR、复音模式等参数。
- 导出符合 `WavePack_for_ESP32Synth_TechSpec_v1.0.md` 规范的 `.wavepack` 二进制文件，供下位机 ESP32Synth 直接加载。

一个 `.wavepack` 代表一个完整音色（Preset），运行时通过 `(note, velocity)` 在 Zone Directory 中命中对应采样。

技术规范原件当前位于 `doc/WavePack_for_ESP32Synth_TechSpec_v1.0.md`（工作区未跟踪状态）。修改打包/校验逻辑前必须对照该规范。

---

## 技术栈与运行环境

- **语言**：Python 3.13（虚拟环境由 uv 0.11.14 创建，见 `.venv/pyvenv.cfg`）
- **GUI 框架**：PySide6 ≥ 6.7.0
- **音频**：标准库 `wave` + `array`；GUI 预览使用 `PySide6.QtMultimedia.QMediaPlayer`
- **打包工具**：PyInstaller ≥ 6.0.0
- **脚本**：PowerShell（`build_exe.ps1`）
- **无第三方数值/音频库**：不使用 NumPy、SciPy、SoundFile 等
- **目标平台**：Windows 桌面（通过 PyInstaller 生成单文件 exe）

---

## 项目结构

```
wavepack_maker/
├── main.py                      # 程序入口：启动 PySide6 QApplication
├── wavepack_maker/
│   ├── __init__.py              # 导出 WavePackBuilder / WavePackValidator / ValidationError / WAVEPACK_VERSION
│   ├── builder.py               # .wavepack 二进制打包核心
│   ├── validator.py             # .wavepack 结构校验
│   ├── luts.py                  # CentiHz / Cents LUT 头文件生成（供下位机）
│   ├── models.py                # Project / SampleEntry / ZoneEntry / ProjectMetadata 数据模型
│   ├── project_io.py            # .wpp JSON 读写
│   ├── audio_player.py          # 基于 QMediaPlayer 的 WAV 预览
│   └── widgets/                 # PySide6 GUI 组件
│       ├── __init__.py
│       ├── main_window.py       # 主窗口、菜单、工程生命周期、导出
│       ├── metadata_panel.py    # 身份证元数据表单
│       ├── sample_list_panel.py # 采样列表：导入/删除/重新定位，显示每个采样的 Note/Vel/复音模式汇总
│       ├── zone_list_panel.py   # 已保留但当前主界面不再显示；采样配置通过 zone_editor 直接编辑
│       ├── zone_editor.py       # 采样配置面板：根音/范围/力度/ADSR/复音模式/flags
│       ├── waveform_view.py     # 波形绘制 + 循环区间鼠标框选
│       └── piano_roll.py        # MIDI note 0-127 钢琴卷帘高亮
├── tests/test_wavepack_maker.py # 单元测试
├── examples/piano_kit/          # 示例工程：3 个 WAV + .wpp + 已导出 .wavepack
├── requirements.txt             # PySide6>=6.7.0, PyInstaller>=6.0.0
├── wavepack_maker.spec          # PyInstaller 配置
├── build_exe.ps1                # 一键打包脚本
├── README.md                    # 面向人类的快速开始与说明
└── doc/
    └── WavePack_for_ESP32Synth_TechSpec_v1.0.md  # 二进制格式技术规范
```

### 核心数据流

```
GUI 编辑 → Project 模型 → .wpp JSON
导出时：Project → WavePackBuilder.from_project() → .wavepack → WavePackValidator.validate()
```

### 主界面布局

当前 GUI 简化为"采样即配置"的心智模型，主界面分为：

1. **左上：采样列表**——显示所有 WAV，列包含根音、Note 范围、Velocity 范围、复音模式等汇总信息。
2. **右上：采样配置**——选中某个采样后，直接编辑其对应的 Zone 参数（根音/范围/力度/ADSR/复音模式）。
3. **中下：波形预览**——显示当前选中 WAV 的波形，并支持鼠标框选 loop 区间。
4. **底部：钢琴键**——高度较矮，高亮当前 Zone 的 note 范围；点击钢琴键可在当前 Zone 音域内试听对应采样。

> 说明：底层 `.wavepack` 格式仍允许一个 Sample 被多个 Zone 引用，但上位机 UI 强制一个 Sample 对应一个 Zone。导入 WAV 时自动创建默认 Zone；删除采样时同步删除其 Zone。工程身份证元数据通过菜单「文件 → 工程属性」编辑，不再常驻主界面。

---

## 构建、运行与测试命令

### 开发环境准备

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 运行程序

```powershell
$env:PYTHONPATH = "."
python main.py
```

### 运行测试

本项目**未使用 pytest**，测试直接以函数形式写在 `tests/test_wavepack_maker.py`。

```powershell
$env:PYTHONPATH = "."
python tests/test_wavepack_maker.py
```

测试覆盖点：

- `ProjectMetadata` 序列化/反序列化
- `SampleEntry.from_wav()` 读取
- `ZoneEntry.validate()`（旋律 Zone 根音范围、打击乐 Zone 约束）
- 完整工程 IO + 导出 + `WavePackValidator` 校验
- Header magic / version 验证

新增核心逻辑时，请同步在该文件中添加对应测试。

### 打包为独立 exe

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File build_exe.ps1
```

流程：

1. 清理 `build/` 和 `dist/`
2. 调用 `.venv\Scripts\python.exe -m PyInstaller wavepack_maker.spec --noconfirm --clean`
3. 输出：`dist/WavePackMaker.exe`

`wavepack_maker.spec` 配置为 `console=False` 的窗口应用，`upx=True`。

---

## 代码风格与开发约定

- **语言**：所有代码注释、GUI 标签、错误提示、文档均使用**中文**。新增代码必须保持中文注释。
- **类型注解**：核心模块（`models.py`、`builder.py`、`validator.py`）已使用类型注解，新增公共函数建议保留此风格。
- **导入顺序**：标准库 → 第三方库 → 本项目模块。
- **字符串引号**：代码中混用单双引号均可，优先保持与周围代码一致。
- **路径处理**：
  - 采样路径保存为相对于 `.wpp` 工程文件目录（`SampleEntry.to_dict(project_dir)`）。
  - 加载时若相对路径不存在，回退到原始路径。
  - 跨平台路径统一使用 `pathlib.Path`。
- **数据模型**：使用 `@dataclass` 定义模型（`ProjectMetadata`、`SampleEntry`、`ZoneEntry`、`Project`）。
- **ID 生成**：sample / zone ID 使用 UUID 前 8 位。
- **工程脏检测**：`MainWindow` 通过 `_last_save_state` 保存完整字典快照，与 `Project.to_dict()` 比较。
- **面板解耦**：各 widget 通过 `set_on_*_changed` 回调与主窗口通信，避免直接引用主窗口。
- **校验分层**：
  - 模型层：`ZoneEntry.validate()` / `Project.validate()`
  - 二进制层：`WavePackValidator` 按 TechSpec 逐项校验

---

## .wavepack 二进制格式要点

导出/校验相关代码必须严格遵守 `doc/WavePack_for_ESP32Synth_TechSpec_v1.0.md`。关键约束如下：

- 文件结构（小端序）：
  - Header: 64 bytes
  - Zone Directory: N × 48 bytes
  - Sample Directory: M × 32 bytes
  - Padding: 对齐到 4096 bytes
  - Sample Data: 连续 s16le mono PCM
- `magic = "WAVEPACK"`，`version = 0x0100`
- 仅支持 16-bit mono PCM；立体声 WAV 自动混缩为单声道
- `data_offset` 必须 4096 字节对齐
- Zone `flags` 编码：
  - `bit0`：0 = 打击乐，1 = 旋律
  - `bit2~3`：复音模式（retrigger=0x00, multi=0x04, legato=0x08）
  - `bit4~7`：同音最大 Voice 数 - 1
- ADSR：`[attack_ms, decay_ms, sustain_level_0_255, release_ms]`
- `pitch_cents` 限制 ±100 cents
- 打击乐 Zone 必须满足 `min_note == max_note == root_note`
- 旋律 Zone 必须满足 `min_note < max_note` 且 `min_note <= root_note <= max_note`

---

## 测试策略

- 所有核心逻辑测试集中在 `tests/test_wavepack_maker.py`。
- 测试辅助函数 `_make_wav()` 用标准库生成单声道 16-bit 正弦波 WAV。
- 修改 `builder.py`/`validator.py`/`models.py` 后，必须运行测试并确保通过。
- GUI 组件当前无自动化测试，新增 widget 时应通过手工运行 `main.py` 验证交互。

---

## 部署与分发

- 目标平台：**Windows 桌面**。
- 分发产物：通过 `build_exe.ps1` 生成的 `dist/WavePackMaker.exe`。
- 下位机部署：将 `.wavepack` 文件放入 ESP32 的 `/sdcard/wavepack/` 目录。
- 当前无 PyPI/网络分发、无 CI/CD 配置文件（无 `.github/workflows/`、`pyproject.toml` 等）。

---

## 安全与边界注意事项

- **不要运行 `git commit` / `git push` / `git reset` / `git rebase` 等变更仓库历史的命令**，除非用户明确授权。
- 修改二进制格式相关代码前，务必对照 `doc/WavePack_for_ESP32Synth_TechSpec_v1.0.md`，避免破坏下位机兼容性。
- 采样文件路径在 `.wpp` 中尽量保存为相对路径，避免工程迁移后文件丢失。
- `crc32` 字段当前固定写 0（未计算），下位机加载时会跳过校验；如需启用 CRC32，必须同步更新下位机加载逻辑。
- `luts.py` 生成的 C 头文件供下位机查表使用，当前未在 GUI 中集成；修改 LUT 生成逻辑时需注意与下位机查找表范围一致。

---

## 常用修改入口

| 需求 | 应查看/修改的文件 |
|---|---|
| 修改 `.wavepack` 打包逻辑 | `wavepack_maker/builder.py` |
| 修改 `.wavepack` 校验规则 | `wavepack_maker/validator.py` |
| 修改数据模型或校验规则 | `wavepack_maker/models.py` |
| 修改 GUI 主窗口/菜单/导出流程 | `wavepack_maker/widgets/main_window.py` |
| 修改采样列表显示/导入逻辑 | `wavepack_maker/widgets/sample_list_panel.py` |
| 修改采样配置（Zone）编辑表单 | `wavepack_maker/widgets/zone_editor.py` |
| 修改钢琴键预览/高亮 | `wavepack_maker/widgets/piano_roll.py` |
| 修改身份证元数据表单 | `wavepack_maker/widgets/metadata_panel.py` |
| 添加/修改测试 | `tests/test_wavepack_maker.py` |
| 修改打包 exe 配置 | `wavepack_maker.spec`、`build_exe.ps1` |

---

## 许可证

本工具仅用于 TAB5_Music_Pad 项目开发。
