# WavePack Maker 一键打包脚本
# 生成 dist/WavePackMaker.exe

$ErrorActionPreference = "Stop"

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Error "未找到 .venv，请先创建虚拟环境并安装依赖：pip install -r requirements.txt"
    exit 1
}

Write-Host "生成 logo.ico..."
& $venvPython ([System.IO.Path]::Combine($PSScriptRoot, "scripts", "build_logo_ico.py"))

Write-Host "生成版本信息..."
& $venvPython ([System.IO.Path]::Combine($PSScriptRoot, "scripts", "gen_version.py"))
if ($LASTEXITCODE -ne 0) {
    Write-Error "版本信息生成失败"
    exit 1
}

Write-Host "清理旧构建..."
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $PSScriptRoot "dist")

Write-Host "运行 PyInstaller 打包..."
& $venvPython -m PyInstaller (Join-Path $PSScriptRoot "wavepack_maker.spec") --noconfirm --clean

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller 打包失败"
    exit 1
}

Write-Host "打包完成：dist/WavePackMaker.exe"
