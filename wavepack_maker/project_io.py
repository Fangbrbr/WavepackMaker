"""WavePack Maker 工程文件（.wpp）读写。"""

import json
from pathlib import Path
from typing import Optional

from .models import Project


def load_project(path: str | Path) -> Project:
    """从 .wpp 文件加载工程。"""
    path = Path(path).resolve()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Project.from_dict(data, str(path))


def save_project(project: Project, path: Optional[str | Path] = None) -> str:
    """保存工程到 .wpp 文件，返回保存后的绝对路径。"""
    if path is not None:
        project.file_path = str(Path(path).resolve())
    if project.file_path is None:
        raise ValueError("未指定工程保存路径")

    save_path = Path(project.file_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    project.metadata.touch_updated()
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(project.to_dict(), f, ensure_ascii=False, indent=2)
    return str(save_path)


def suggest_project_name(wavepack_name: str) -> str:
    """由音色名生成默认工程文件名。"""
    base = Path(wavepack_name).stem
    return f"{base}.wpp"
