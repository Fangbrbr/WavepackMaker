"""WavePack Maker GUI 数据模型。

说明：
- ProjectMetadata 仅保存在 .wpp 工程文件中，用于上位机管理音色库。
- WavePackHeaderInfo 是实际写入 .wavepack 二进制 Header 的字段子集。
"""

from __future__ import annotations

import uuid
import wave
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from .builder import DEFAULT_ADSR, WAVEPACK_VERSION


def _now_iso() -> str:
    """返回当前 UTC 时间的 ISO 8601 字符串。"""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ProjectMetadata:
    """WavePack 工程（.wpp）身份证信息。

    这些字段主要供上位机展示与管理，不一定全部写入 .wavepack 二进制。
    """

    name: str = "未命名音色"
    version: str = "1.0.0"
    author: str = ""
    copyright: str = ""
    category: str = ""
    tags: List[str] = field(default_factory=list)
    description: str = ""
    notes: str = ""
    sample_rate: int = 44100
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    def touch_updated(self) -> None:
        """更新修改时间。"""
        self.updated_at = _now_iso()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "copyright": self.copyright,
            "category": self.category,
            "tags": list(self.tags),
            "description": self.description,
            "notes": self.notes,
            "sample_rate": self.sample_rate,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ProjectMetadata:
        return cls(
            name=d.get("name", "未命名音色"),
            version=d.get("version", "1.0.0"),
            author=d.get("author", ""),
            copyright=d.get("copyright", ""),
            category=d.get("category", ""),
            tags=list(d.get("tags", [])),
            description=d.get("description", ""),
            notes=d.get("notes", ""),
            sample_rate=int(d.get("sample_rate", 44100)),
            created_at=d.get("created_at", _now_iso()),
            updated_at=d.get("updated_at", _now_iso()),
        )


@dataclass
class SampleEntry:
    """工程内的一个采样条目。"""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    file_path: str = ""  # 绝对路径或相对于工程文件的路径
    name: str = ""        # 显示名，默认取文件名
    sample_rate: int = 44100
    channels: int = 1
    bits: int = 16
    nframes: int = 0
    root_note: int = 60
    loop_start: int = 0
    loop_end: int = 0
    # 工程文件不保存音频数据，保存路径；加载时若找不到则提示重新定位

    def to_dict(self, project_dir: Optional[Path] = None) -> dict:
        """序列化，可选将绝对路径转为相对路径。"""
        path = Path(self.file_path)
        if project_dir is not None and path.is_absolute():
            try:
                rel = path.relative_to(project_dir)
                stored_path = str(rel)
            except ValueError:
                stored_path = str(path)
        else:
            stored_path = str(path)
        return {
            "id": self.id,
            "file_path": stored_path,
            "name": self.name,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "bits": self.bits,
            "nframes": self.nframes,
            "root_note": self.root_note,
            "loop_start": self.loop_start,
            "loop_end": self.loop_end,
        }

    @classmethod
    def from_dict(cls, d: dict) -> SampleEntry:
        return cls(
            id=d.get("id", str(uuid.uuid4())[:8]),
            file_path=d.get("file_path", ""),
            name=d.get("name", ""),
            sample_rate=int(d.get("sample_rate", 44100)),
            channels=int(d.get("channels", 1)),
            bits=int(d.get("bits", 16)),
            nframes=int(d.get("nframes", 0)),
            root_note=int(d.get("root_note", 60)),
            loop_start=int(d.get("loop_start", 0)),
            loop_end=int(d.get("loop_end", 0)),
        )

    def resolve_path(self, project_dir: Optional[Path] = None) -> Path:
        """根据工程目录解析采样文件路径。"""
        p = Path(self.file_path)
        if p.is_absolute():
            return p
        if project_dir is not None:
            candidate = project_dir / p
            if candidate.exists():
                return candidate
        return p

    def is_valid(self, project_dir: Optional[Path] = None) -> bool:
        """采样文件是否实际存在。"""
        return self.resolve_path(project_dir).is_file()

    @staticmethod
    def from_wav(file_path: str | Path) -> SampleEntry:
        """从 WAV 文件创建 SampleEntry。"""
        file_path = Path(file_path).resolve()
        with wave.open(str(file_path), "rb") as wf:
            sample_rate = wf.getframerate()
            channels = wf.getnchannels()
            bits = wf.getsampwidth() * 8
            nframes = wf.getnframes()

        name = file_path.stem  # 显示名使用完整文件名
        return SampleEntry(
            file_path=str(file_path),
            name=name,
            sample_rate=sample_rate,
            channels=channels,
            bits=bits,
            nframes=nframes,
        )


@dataclass
class ZoneEntry:
    """工程内的一个 Zone 条目。"""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    sample_id: str = ""
    name: str = ""
    root_note: int = 60
    min_note: int = 60
    max_note: int = 60
    min_vel: int = 0
    max_vel: int = 127
    flags: Optional[int] = None  # None 表示由 poly_mode/max_same 自动编码
    poly_mode: str = "multi"
    max_same_note_voices: int = 2
    adsr: Tuple[int, int, int, int] = field(default_factory=lambda: DEFAULT_ADSR)
    pitch_cents: int = 0
    filter_cutoff: int = 0
    filter_resonance: int = 0
    reverb_send: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sample_id": self.sample_id,
            "name": self.name,
            "root_note": self.root_note,
            "min_note": self.min_note,
            "max_note": self.max_note,
            "min_vel": self.min_vel,
            "max_vel": self.max_vel,
            "flags": self.flags,
            "poly_mode": self.poly_mode,
            "max_same_note_voices": self.max_same_note_voices,
            "adsr": list(self.adsr),
            "pitch_cents": self.pitch_cents,
            "filter_cutoff": self.filter_cutoff,
            "filter_resonance": self.filter_resonance,
            "reverb_send": self.reverb_send,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ZoneEntry:
        return cls(
            id=d.get("id", str(uuid.uuid4())[:8]),
            sample_id=d.get("sample_id", ""),
            name=d.get("name", ""),
            root_note=int(d.get("root_note", 60)),
            min_note=int(d.get("min_note", 60)),
            max_note=int(d.get("max_note", 60)),
            min_vel=int(d.get("min_vel", 0)),
            max_vel=int(d.get("max_vel", 127)),
            flags=d.get("flags", None),
            poly_mode=d.get("poly_mode", "multi"),
            max_same_note_voices=int(d.get("max_same_note_voices", 2)),
            adsr=tuple(d.get("adsr", list(DEFAULT_ADSR))),
            pitch_cents=int(d.get("pitch_cents", 0)),
            filter_cutoff=int(d.get("filter_cutoff", 0)),
            filter_resonance=int(d.get("filter_resonance", 0)),
            reverb_send=int(d.get("reverb_send", 0)),
        )

    def validate(self) -> List[str]:
        """返回该 Zone 的校验错误列表。"""
        errs: List[str] = []
        if self.min_note > self.max_note:
            errs.append("音域下限不能大于上限")
        if self.min_vel > self.max_vel:
            errs.append("力度下限不能大于上限")
        if not (0 <= self.sustain_level <= 255):
            errs.append("Sustain 等级必须在 0~255 之间")
        if not (-100 <= self.pitch_cents <= 100):
            errs.append("音高微调必须在 -100~+100 cents 之间")

        flags = self.encoded_flags()
        poly_bits = flags & 0x0C
        if poly_bits not in (0x00, 0x04, 0x08):
            errs.append("Poly 模式位非法")

        is_percussion = (flags & 0x01) == 0
        if is_percussion:
            if not (self.min_note == self.max_note == self.root_note):
                errs.append("打击乐 Zone 要求根音=最低音=最高音")
        else:
            if self.min_note >= self.max_note:
                errs.append("旋律 Zone 要求最低音 < 最高音")
            if not (self.min_note <= self.root_note <= self.max_note):
                errs.append("旋律 Zone 根音必须在音域范围内")
        return errs

    def encoded_flags(self) -> int:
        """计算最终写入二进制的 flags。"""
        from .builder import _encode_flags

        is_melodic = self.min_note < self.max_note
        return _encode_flags(
            self.flags,
            self.poly_mode,
            self.max_same_note_voices,
            is_melodic,
        )

    @property
    def sustain_level(self) -> int:
        return self.adsr[2]

    @sustain_level.setter
    def sustain_level(self, value: int) -> None:
        self.adsr = (self.adsr[0], self.adsr[1], value, self.adsr[3])


@dataclass
class Project:
    """一个 WavePack Maker 工程。"""

    metadata: ProjectMetadata = field(default_factory=ProjectMetadata)
    samples: List[SampleEntry] = field(default_factory=list)
    zones: List[ZoneEntry] = field(default_factory=list)
    file_path: Optional[str] = None

    # 文件格式版本，便于后续迁移
    PROJECT_VERSION: int = 1

    def to_dict(self) -> dict:
        """序列化为可写入 .wpp 的字典。"""
        project_dir = Path(self.file_path).parent if self.file_path else None
        return {
            "__wpp_version": self.PROJECT_VERSION,
            "metadata": self.metadata.to_dict(),
            "samples": [s.to_dict(project_dir) for s in self.samples],
            "zones": [z.to_dict() for z in self.zones],
        }

    @classmethod
    def from_dict(cls, d: dict, file_path: Optional[str] = None) -> Project:
        """从 .wpp 字典反序列化。"""
        project_dir = Path(file_path).parent if file_path else None
        samples = [
            SampleEntry.from_dict(sd) for sd in d.get("samples", [])
        ]
        if project_dir is not None:
            for s in samples:
                if not Path(s.file_path).is_absolute():
                    candidate = project_dir / s.file_path
                    if candidate.exists():
                        s.file_path = str(candidate.resolve())

        return cls(
            metadata=ProjectMetadata.from_dict(d.get("metadata", {})),
            samples=samples,
            zones=[ZoneEntry.from_dict(zd) for zd in d.get("zones", [])],
            file_path=file_path,
        )

    def add_sample(self, sample: SampleEntry) -> None:
        self.samples.append(sample)
        self.metadata.touch_updated()

    def remove_sample(self, sample_id: str) -> None:
        """删除采样，并同步删除引用它的 Zone。"""
        self.samples = [s for s in self.samples if s.id != sample_id]
        self.zones = [z for z in self.zones if z.sample_id != sample_id]
        self.metadata.touch_updated()

    def add_zone(self, zone: ZoneEntry) -> None:
        self.zones.append(zone)
        self.metadata.touch_updated()

    def remove_zone(self, zone_id: str) -> None:
        self.zones = [z for z in self.zones if z.id != zone_id]
        self.metadata.touch_updated()

    def get_sample(self, sample_id: str) -> Optional[SampleEntry]:
        for s in self.samples:
            if s.id == sample_id:
                return s
        return None

    def get_zone(self, zone_id: str) -> Optional[ZoneEntry]:
        for z in self.zones:
            if z.id == zone_id:
                return z
        return None

    def get_zone_for_sample(self, sample_id: str) -> Optional[ZoneEntry]:
        """返回与指定 Sample 关联的第一个 Zone；UI 上强制一个 Sample 对应一个 Zone。"""
        for z in self.zones:
            if z.sample_id == sample_id:
                return z
        return None

    def ensure_zone_for_sample(self, sample: SampleEntry) -> ZoneEntry:
        """确保指定 Sample 有对应的 Zone；不存在则自动创建默认 Zone。"""
        zone = self.get_zone_for_sample(sample.id)
        if zone is not None:
            return zone
        # 默认创建旋律 Zone，根音取 sample.root_note，音域向两侧扩展 6 个半音
        zone = ZoneEntry(
            sample_id=sample.id,
            name=sample.name,
            root_note=sample.root_note,
            min_note=max(0, sample.root_note - 6),
            max_note=min(127, sample.root_note + 6),
        )
        self.add_zone(zone)
        return zone

    def _zones_overlap(self, a: ZoneEntry, b: ZoneEntry) -> bool:
        """判断两个 Zone 的 note 范围与 velocity 范围同时存在交集。"""
        note_overlap = a.min_note <= b.max_note and b.min_note <= a.max_note
        vel_overlap = a.min_vel <= b.max_vel and b.min_vel <= a.max_vel
        return note_overlap and vel_overlap

    def validate(self) -> List[str]:
        """返回工程级校验错误列表。"""
        errs: List[str] = []
        if not self.samples:
            errs.append("工程中至少需要一个采样")
        if not self.zones:
            errs.append("工程中至少需要一个 Zone")
        for z in self.zones:
            sample = self.get_sample(z.sample_id)
            if sample is None:
                errs.append(f"Zone {z.name or z.id} 引用了不存在的采样")
            else:
                # 若采样文件丢失，打包时会失败，此处仅警告
                if not sample.is_valid():
                    errs.append(f"Zone {z.name or z.id} 引用的采样文件不存在: {sample.file_path}")
            zone_errs = z.validate()
            for e in zone_errs:
                errs.append(f"Zone {z.name or z.id}: {e}")

        # Zone 之间 (note, velocity) 范围不允许重叠
        for i in range(len(self.zones)):
            for j in range(i + 1, len(self.zones)):
                a, b = self.zones[i], self.zones[j]
                if self._zones_overlap(a, b):
                    errs.append(
                        f"Zone {a.name or a.id} 与 Zone {b.name or b.id} "
                        f"的 Note/Velocity 范围存在重叠"
                    )
        return errs

    def is_dirty(self, other_state: Optional[dict] = None) -> bool:
        """对比快照判断工程是否被修改。"""
        if other_state is None:
            return True
        return self.to_dict() != other_state
