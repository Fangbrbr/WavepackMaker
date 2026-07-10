# WavePack Maker

面向 ESP32Synth 的专业音色打包/编辑上位机工具。

- 工程文件：`.wpp`（上位机管理用，携带身份证元数据）
- 输出文件：`.wavepack`（下位机加载用，符合 `doc/WavePack_for_ESP32Synth_TechSpec_v1.1.md`）

## 最新发布

- **v1.0.0** 已发布：[下载 WavePackMaker-v1.0.0.exe](https://github.com/Fangbrbr/WavepackMaker/releases/download/v1.0.0/WavePackMaker-v1.0.0.exe)
- Release 页面：https://github.com/Fangbrbr/WavepackMaker/releases/tag/v1.0.0

版本号取自 git 历史：有 tag 显示 tag（如 `v1.0.0`），无 tag 显示 commit 短 hash。

## 功能特性

- **身份证元数据**：音色名称、版本、作者、版权、分类、标签、描述、备注、目标采样率、创建/修改时间。
- **采样管理**：
  - 导入 WAV（支持 16-bit 单声道/立体声，自动混缩为单声道）
  - 自动复制到工程目录 `samples/`
  - 显示采样率 / 通道 / 位深
  - 采样裁剪：框选拖尾音并删除，减小音色包体积
- **Zone 编辑**：
  - 指定 Note 范围、Velocity 范围
  - 复音模式：retrigger / multi / legato
  - 同音最大 Voice 数
  - ADSR 包络编辑器
  - 音高微调（-100 ~ +100 cents）
  - **采样根音编辑**：每个 Sample 独立设置根音，直接决定下位机播放速度基准
- **可视化**：
  - 波形显示 + 循环区间框选 + 底部时间轴
  - 88 键钢琴卷帘展示所有 Zone 的 Note 映射
  - 未配置键显示灰色，已配置键显示白色，点击触发主题色高亮
- **预览**：
  - 虚拟钢琴键盘点击预览
  - PC 键盘映射预览
  - Windows MIDI 输入设备预览
  - 所有预览均基于当前 Zone 设计并按根音差变速播放
- **导出与校验**：一键导出 `.wavepack` 到 `output/` 目录，自动通过结构校验。

## 采样根音

`Sample.root_note` 是该 WAV 采样真实录制的 MIDI 音高，也是下位机计算播放速度的唯一根音来源：

- 你录制了一个 A0（MIDI 21）的钢琴采样 → `Sample.root_note = 21`
- 这个采样覆盖 note 0~27 → Zone 的 `min_note=0, max_note=27`
- 下位机收到 MIDI note 33 时，知道要把该采样提高 12 个半音播放

Zone 仅负责命中映射（note/velocity 范围），不再携带根音字段。

## 工程目录约定

保存 `.wpp` 工程后，工程目录会自动创建以下结构：

```
MyProject/
├── MyProject.wpp
├── samples/           # 所有 WAV 音源
└── output/            # 默认 .wavepack 导出目录
```

工程内采样清单与 `samples/` 目录双向同步：
- 目录中新增 WAV 会自动加入工程
- 目录中删除 WAV 会自动从工程移除并清理无效 Zone

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

打包脚本会自动：
1. 从 `assets/logo.png` 生成 `assets/logo.ico`
2. 从 git 历史生成版本号与编译时间
3. 调用 PyInstaller 打包

### 4. 替换 Logo

把 `assets/logo.png` 换成你的 Logo（推荐带透明通道的 PNG），重新运行 `build_exe.ps1` 即可。

## 发布流程（GitHub Actions）

> ⚠️ **只有项目所有者本人才能决定何时打 tag 发布。Agent 或自动化脚本严禁自行创建/推送 tag。**

项目配置了 `.github/workflows/release.yml`，**由用户手动推送 `v*` 标签**后会自动打包并创建 Release：

```bash
git tag v1.1.0
git push origin v1.1.0
```

GitHub Actions 会在 Windows runner 上：
1. 安装 Python 与 uv
2. 创建虚拟环境并安装依赖
3. 生成 logo.ico 与版本信息
4. PyInstaller 打包
5. 重命名产物为 `WavePackMaker-v1.1.0.exe`
6. 创建 GitHub Release 并上传产物

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
      "file_path": "samples/piano_c4.wav",
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
│   ├── _version.py              # 版本号与编译时间（自动生成）
│   ├── builder.py               # .wavepack 二进制打包
│   ├── validator.py             # .wavepack 结构校验
│   ├── luts.py                  # CentiHz / Cents LUT 生成
│   ├── models.py                # Project / Sample / Zone / Metadata 数据模型
│   ├── project_io.py            # .wpp 读写
│   ├── audio_player.py          # 音频预览
│   ├── midi_input.py            # Windows MIDI 输入
│   └── widgets/                 # PySide6 GUI 组件
│       ├── main_window.py
│       ├── metadata_panel.py
│       ├── sample_list_panel.py
│       ├── zone_list_panel.py
│       ├── zone_editor.py
│       ├── waveform_view.py
│       ├── piano_roll.py
│       ├── theme.py
│       └── range_slider.py
├── scripts/
│   ├── gen_version.py           # 从 git 生成版本信息
│   └── build_logo_ico.py        # 从 png 生成 ico
├── tests/
│   └── test_wavepack_maker.py
├── examples/piano_kit/          # 示例工程
├── assets/
│   ├── logo.png                 # Logo 源图
│   └── logo.ico                 # 打包用图标
├── .github/workflows/release.yml
├── requirements.txt
├── wavepack_maker.spec          # PyInstaller 配置
└── build_exe.ps1                # 一键打包脚本
```

## 作者

- 作者：Fmil
- 邮箱：fmil123@qq.com

## 许可证

本工具仅用于 TAB5_Music_Pad 项目开发。
