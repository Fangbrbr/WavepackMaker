# WavePack Maker - Agent 指南

## 项目简介

WavePack Maker 是面向 ESP32Synth 的音色打包/编辑上位机工具，使用 PySide6 构建 Windows 桌面 GUI，输出 `.wavepack` 二进制音色包。

## 技术栈

- Python 3.13
- PySide6 >= 6.7.0
- PyInstaller >= 6.0.0
- 无 NumPy/SciPy/SoundFile；使用标准库 `wave` + `array` + PySide6 QtMultimedia

## 常用命令

```powershell
# 运行开发版
$env:PYTHONPATH="."; python main.py

# 运行单元测试
$env:PYTHONPATH="."; python tests/test_wavepack_maker.py

# 语法检查（所有代码修改后必须执行）
$env:PYTHONPATH="."; python -m py_compile $(Get-ChildItem wavepack_maker -Recurse -Filter *.py | ForEach-Object { $_.FullName }) main.py

# 打包 Windows 可执行文件
powershell -NoProfile -ExecutionPolicy Bypass -File build_exe.ps1
```

## 代码约定

- 使用类型注解，保持与现有代码风格一致。
- 字符串使用双引号，中文注释/提示语使用标准中文标点。
- 不引入新的外部依赖；如确有必要，先在隔离环境中验证。

## 关键架构约束

- `samples/` 目录是工程采样的唯一事实来源。
- `Project.sync_samples_with_directory()` 负责让内存中的 `project.samples` 与磁盘保持一致。
- Loop 标记保存在 `SampleEntry`（`loop_start`、`loop_end`）而非 Zone。
- Zone 编辑通过信号回调实时同步到 `ZoneListPanel`，使用 `_loading_zone` 标志避免循环触发。
- 钢琴键盘仅显示 88 键（A0-C8，MIDI note 21-108）。

## 提交流程

1. 修改代码后运行 `python -m py_compile` 确保无语法错误。
2. 运行 `python tests/test_wavepack_maker.py` 确保测试通过。
3. 使用 `git add` 暂存相关文件。
4. 使用 `git commit` 提交，提交信息用中文简要说明修改内容。
