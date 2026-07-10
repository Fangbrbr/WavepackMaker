# WavePack Maker - Agent 指南

## 项目简介

WavePack Maker 是面向 ESP32Synth 的音色打包/编辑上位机工具，使用 PySide6 构建 Windows 桌面 GUI，输出 `.wavepack` 二进制音色包。

## 技术栈

- Python 3.13
- PySide6 >= 6.7.0
- PyInstaller >= 6.0.0
- uv（可选，CI 中使用）
- 无 NumPy/SciPy/SoundFile；使用标准库 `wave` + `array` + PySide6 QtMultimedia

## 常用命令

```powershell
# 运行开发版
$env:PYTHONPATH="."; python main.py

# 运行单元测试
$env:PYTHONPATH="."; python tests/test_wavepack_maker.py

# 语法检查（所有代码修改后必须执行）
$env:PYTHONPATH="."; python -m py_compile $(Get-ChildItem wavepack_maker -Recurse -Filter *.py | ForEach-Object { $_.FullName }) main.py scripts/*.py

# 生成本地版本信息
python scripts/gen_version.py

# 从 png 生成 ico
python scripts/build_logo_ico.py

# 打包 Windows 可执行文件
powershell -NoProfile -ExecutionPolicy Bypass -File build_exe.ps1
```

## 代码约定

- 使用类型注解，保持与现有代码风格一致。
- 字符串使用双引号，中文注释/提示语使用标准中文标点。
- 不引入新的外部依赖；如确有必要，先在隔离环境中验证。
- 不要提交用户数据目录（如 `wavwpack/`）或构建产物（`build/`、`dist/`）。

## 关键架构约束

- `samples/` 目录是工程采样的唯一事实来源。
- `Project.sync_samples_with_directory()` 负责让内存中的 `project.samples` 与磁盘保持一致。
- Loop 标记保存在 `SampleEntry`（`loop_start`、`loop_end`）而非 Zone。
- Zone 编辑通过信号回调实时同步到 `ZoneListPanel`，使用 `_loading_zone` 标志避免循环触发。
- 钢琴键盘仅显示 88 键（A0-C8，MIDI note 21-108）。
- 版本号来自 git 历史：优先使用 tag，无 tag 时使用 commit 短 hash。

## 版本与打包

### 版本来源

`wavepack_maker/_version.py` 由 `scripts/gen_version.py` 自动生成：
- 当前 commit 有 tag → `__version__ = "v1.0.0"`
- 无 tag → `__version__ = "abc1234"`（commit 短 hash）
- `__build_time__` 为 UTC ISO 时间

该文件会被提交到 git，但正式发布时应以 CI 中重新生成的为准。

### Logo

- 源图：`assets/logo.png`（带透明通道的 PNG）
- 打包用：`assets/logo.ico`（由 `scripts/build_logo_ico.py` 生成）
- 更换 Logo 后必须重新运行 `build_exe.ps1` 或 `scripts/build_logo_ico.py`

### 本地打包

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File build_exe.ps1
```

`build_exe.ps1` 会依次执行：
1. `scripts/build_logo_ico.py`
2. `scripts/gen_version.py`
3. PyInstaller 打包

产物在 `dist/WavePackMaker.exe`。

### CI 自动发布

项目使用 GitHub Actions（`.github/workflows/release.yml`）：
- 触发条件：推送 `v*` 标签
- 自动在 Windows runner 上打包
- 产物重命名为 `WavePackMaker-{tag}.exe`
- 自动创建 GitHub Release 并上传产物

发版命令：
```bash
git tag v1.1.0
git push origin v1.1.0
```

## 提交流程

1. 修改代码后运行 `python -m py_compile` 确保无语法错误。
2. 运行 `python tests/test_wavepack_maker.py` 确保测试通过。
3. 如果修改了功能或流程，同步更新 `README.md` 与本 `AGENTS.md`。
4. 使用 `git add` 暂存相关文件。
5. 使用 `git commit` 提交，提交信息用中文简要说明修改内容。
6. 如需发版，执行 `git tag vX.Y.Z && git push origin vX.Y.Z`。
