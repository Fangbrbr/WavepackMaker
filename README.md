# WavePack Maker

面向 ESP32Synth 的专业音色打包/编辑上位机工具。

- 工程文件：`.wpp`（上位机管理用，携带身份证元数据）
- 输出文件：`.wavepack`（下位机加载用，符合 `WavePack_for_ESP32Synth_TechSpec_v1.0.md`）

## 功能特性

- **身份证元数据**：音色名称、版本、作者、版权、分类、标签、描述、备注、目标采样率、创建/修改时间。
- **采样管理**：导入 WAV（支持 16-bit 单声道/立体声，自动混缩为单声道），显示采样率/通道/位深，支持重新定位丢失文件。
- **Zone 编辑**：
  - 指定根音、Note 范围、Velocity 范围
  - 复音模式：retrigger / multi / legato
  - 同音最大 Voice 数
  - ADSR 包络编辑器
  - 音高微调（-100 ~ +100 cents）
- **可视化**：
  - 波形显示 + 循环区间框选
  - 钢琴卷帘展示所有 Zone 的 Note 映射
- **导出与校验**：一键导出 `.wavepack`，自动通过结构校验。

## 快速开始

### 1. 创建虚拟环境并安装依赖

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 运行程序

```powershell
$env:PYTHONPATH = "."
python main.py
```

### 3. 打包为独立 exe

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File build_exe.ps1
```

打包完成后，可执行文件位于 `dist/WavePackMaker.exe`。

## 工程文件格式（.wpp）

`.wpp` 为 JSON 格式，示例：

```json
{
  "__wpp_version": 1,
  "metadata": {
    "name": "Acoustic Piano",
    "version": "1.0.0",
    "author": "Your Name",
    "copyright": "CC0",
    "category": "Piano",
    "tags": ["acoustic", "grand"],
    "description": "示例钢琴音色",
    "notes": "",
    "sample_rate": 44100,
    "created_at": "2026-07-09T06:38:54.481195+00:00",
    "updated_at": "2026-07-09T06:38:54.481195+00:00"
  },
  "samples": [
    {
      "id": "abc123",
      "file_path": "piano_c4.wav",
      "name": "piano_c",
      "sample_rate": 44100,
      "channels": 1,
      "bits": 16,
      "nframes": 13230,
      "root_note": 60,
      "loop_start": 0,
      "loop_end": 0
    }
  ],
  "zones": [
    {
      "id": "def456",
      "sample_id": "abc123",
      "name": "C4 Zone",
      "root_note": 60,
      "min_note": 55,
      "max_note": 67,
      "min_vel": 0,
      "max_vel": 127,
      "flags": null,
      "poly_mode": "multi",
      "max_same_note_voices": 2,
      "adsr": [5, 1500, 0, 120],
      "pitch_cents": 0,
      "filter_cutoff": 0,
      "filter_resonance": 0,
      "reverb_send": 0
    }
  ]
}
```

## 示例工程

`examples/piano_kit/` 包含一个示例钢琴工程，可直接打开或导出：

```powershell
python -c "
from wavepack_maker.project_io import load_project
from wavepack_maker.builder import WavePackBuilder
p = load_project('examples/piano_kit/piano_kit.wpp')
WavePackBuilder.from_project(p).build('examples/piano_kit/piano_kit.wavepack')
"
```

## 测试

```powershell
$env:PYTHONPATH = "."
python tests/test_wavepack_maker.py
```

## 目录结构

```
wavepack_maker/
├── main.py                      # 程序入口
├── wavepack_maker/
│   ├── __init__.py
│   ├── builder.py               # .wavepack 二进制打包
│   ├── validator.py             # .wavepack 结构校验
│   ├── luts.py                  # CentiHz / Cents LUT 生成
│   ├── models.py                # Project / Sample / Zone / Metadata 数据模型
│   ├── project_io.py            # .wpp 读写
│   ├── audio_player.py          # 音频预览
│   └── widgets/                 # PySide6 GUI 组件
│       ├── main_window.py
│       ├── metadata_panel.py
│       ├── sample_list_panel.py
│       ├── zone_list_panel.py
│       ├── zone_editor.py
│       ├── waveform_view.py
│       └── piano_roll.py
├── tests/
│   └── test_wavepack_maker.py
├── examples/piano_kit/          # 示例工程
├── requirements.txt
├── wavepack_maker.spec          # PyInstaller 配置
└── build_exe.ps1                # 一键打包脚本
```

## 许可证

本工具仅用于 TAB5_Music_Pad 项目开发。
