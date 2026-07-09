"""WavePack 打包器：JSON + WAV -> .wavepack。"""

import array
import json
import math
import struct
import wave
from pathlib import Path
from typing import TYPE_CHECKING, List, Tuple

if TYPE_CHECKING:
    from .models import Project

WAVEPACK_VERSION = 0x0100

# Zone flags
ZONE_FLAG_PERCUSSION = 0x00
ZONE_FLAG_MELODIC = 0x01
ZONE_FLAG_LOOP = 0x02
ZONE_FLAG_POLY_RETRIGGER = 0x00
ZONE_FLAG_POLY_MULTI = 0x04
ZONE_FLAG_POLY_LEGATO = 0x08
ZONE_FLAG_POLY_MASK = 0x0C
ZONE_FLAG_MAX_SAME_NOTE_SHIFT = 4
ZONE_FLAG_MAX_SAME_NOTE_MASK = 0xF0

# Default ADSR: [attack_ms, decay_ms, sustain_level_0_255, release_ms]
DEFAULT_ADSR: Tuple[int, int, int, int] = (5, 1500, 0, 120)


def _encode_flags(
    flags: int | None,
    poly_mode: str,
    max_same_note_voices: int,
    melodic: bool,
) -> int:
    """将 poly_mode 与复音数编码为 Zone flags。"""
    if flags is not None:
        return flags & 0xFF

    if poly_mode == "multi":
        mode_bit = ZONE_FLAG_POLY_MULTI
    elif poly_mode == "legato":
        mode_bit = ZONE_FLAG_POLY_LEGATO
    elif poly_mode == "retrigger":
        mode_bit = ZONE_FLAG_POLY_RETRIGGER
    else:
        raise ValueError(f"Unknown poly_mode: {poly_mode}")

    melodic_bit = ZONE_FLAG_MELODIC if melodic else ZONE_FLAG_PERCUSSION
    max_same = max(1, min(16, max_same_note_voices)) - 1
    return melodic_bit | mode_bit | (max_same << ZONE_FLAG_MAX_SAME_NOTE_SHIFT)


class WavePackBuilder:
    """由 WAV 与 JSON 描述构建 .wavepack 文件。"""

    def __init__(self, sample_rate: int = 44100):
        self.global_sample_rate = sample_rate
        self.zones: List[dict] = []
        self.samples: List[dict] = []
        self.pcm_data = bytearray()

    def add_sample(
        self,
        wav_path: str | Path,
        root_note: int = 60,
        loop_start: int = 0,
        loop_end: int = 0,
        name: str = "",
    ) -> int:
        """仅添加一个 Sample，返回 sample_idx。"""
        wav_path = Path(wav_path)
        if not wav_path.exists():
            raise FileNotFoundError(f"WAV not found: {wav_path}")

        with wave.open(str(wav_path), "rb") as wf:
            nch = wf.getnchannels()
            sw = wf.getsampwidth()
            fr = wf.getframerate()
            nframes = wf.getnframes()
            raw = wf.readframes(nframes)

        if sw != 2:
            raise ValueError(f"Only 16-bit WAV supported, got {sw * 8}-bit")

        if nch == 2:
            stereo = array.array("h", raw)
            mono = array.array(
                "h", [(stereo[i * 2] + stereo[i * 2 + 1]) // 2 for i in range(nframes)]
            )
            pcm = mono.tobytes()
        elif nch == 1:
            pcm = raw
        else:
            raise ValueError(f"Unsupported channel count: {nch}")

        while len(pcm) % 4 != 0:
            pcm += b"\x00"

        sample_idx = len(self.samples)
        data_offset = len(self.pcm_data)

        short_name = name.encode("ascii")[:8].ljust(8, b"\x00")
        if not name:
            short_name = Path(wav_path).stem[:8].encode("ascii").ljust(8, b"\x00")

        self.samples.append(
            {
                "data_offset": data_offset,
                "data_size": len(pcm),
                "sample_rate": fr,
                "root_note": root_note,
                "loop_start": loop_start,
                "loop_end": loop_end,
                "channels": 1,
                "bits": 16,
                "name": short_name,
            }
        )

        self.pcm_data += pcm
        return sample_idx

    def add_zone(
        self,
        wav_path: str | Path,
        root_note: int,
        min_note: int,
        max_note: int,
        min_vel: int = 0,
        max_vel: int = 127,
        flags: int | None = None,
        poly_mode: str = "multi",
        max_same_note_voices: int = 2,
        adsr: Tuple[int, int, int, int] = DEFAULT_ADSR,
        pitch_cents: int = 0,
        loop_start: int = 0,
        loop_end: int = 0,
        name: str = "",
    ) -> int:
        """添加一个 Zone 并返回其 sample_idx。"""
        sample_idx = self.add_sample(
            wav_path=wav_path,
            root_note=root_note,
            loop_start=loop_start,
            loop_end=loop_end,
            name=name,
        )

        # 默认：melodic zone 用 melodic bit，percussion zone 不用
        is_melodic_default = min_note < max_note
        resolved_flags = _encode_flags(
            flags, poly_mode, max_same_note_voices, is_melodic_default
        )

        self.zones.append(
            {
                "zone_id": len(self.zones),
                "sample_idx": sample_idx,
                "root_note": root_note,
                "min_note": min_note,
                "max_note": max_note,
                "min_vel": min_vel,
                "max_vel": max_vel,
                "flags": resolved_flags,
                "attack_ms": adsr[0],
                "decay_ms": adsr[1],
                "sustain_level": adsr[2],
                "release_ms": adsr[3],
                "pitch_cents": max(-100, min(100, pitch_cents)),
                "filter_cutoff": 0,
                "filter_resonance": 0,
                "reverb_send": 0,
            }
        )

        return sample_idx

    def add_zone_from_json(self, base_dir: Path, zone_cfg: dict) -> int:
        """从 pack.json 的 zone 条目解析并添加 Zone。"""
        file_path = base_dir / zone_cfg["file"]

        poly_mode = zone_cfg.get("poly_mode", "multi")
        max_same = zone_cfg.get(
            "max_same_note_voices",
            2 if poly_mode == "multi" else 1,
        )

        return self.add_zone(
            wav_path=file_path,
            root_note=int(zone_cfg["root_note"]),
            min_note=int(zone_cfg["min_note"]),
            max_note=int(zone_cfg["max_note"]),
            min_vel=int(zone_cfg.get("min_vel", 0)),
            max_vel=int(zone_cfg.get("max_vel", 127)),
            flags=zone_cfg.get("flags", None),
            poly_mode=poly_mode,
            max_same_note_voices=max_same,
            adsr=tuple(zone_cfg.get("adsr", list(DEFAULT_ADSR))),
            pitch_cents=int(zone_cfg.get("pitch_cents", 0)),
            loop_start=int(zone_cfg.get("loop_start", 0)),
            loop_end=int(zone_cfg.get("loop_end", 0)),
            name=zone_cfg.get("name", ""),
        )

    def load_json(self, json_path: str | Path) -> None:
        """从 pack.json 批量加载所有 Zone。"""
        json_path = Path(json_path)
        base_dir = json_path.parent
        with open(json_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        self.global_sample_rate = int(cfg.get("sample_rate", self.global_sample_rate))
        for zone_cfg in cfg.get("zones", []):
            self.add_zone_from_json(base_dir, zone_cfg)

    def build(self, output_path: str | Path) -> None:
        """写出 .wavepack 文件。"""
        output_path = Path(output_path)
        header_size = 64
        zone_size = len(self.zones) * 48
        sample_dir_size = len(self.samples) * 32
        data_offset_base = header_size + zone_size + sample_dir_size
        padding = (4096 - (data_offset_base % 4096)) % 4096
        data_offset = data_offset_base + padding

        with open(output_path, "wb") as f:
            # Header
            f.write(b"WAVEPACK")
            f.write(
                struct.pack(
                    "<HHHH",
                    WAVEPACK_VERSION,
                    len(self.zones),
                    len(self.samples),
                    0x0001,
                )
            )
            f.write(
                struct.pack(
                    "<IIII",
                    64,
                    64 + zone_size,
                    data_offset,
                    len(self.pcm_data),
                )
            )
            f.write(struct.pack("<I", self.global_sample_rate))
            f.write(b"\x00" * 24)  # reserved[6]
            f.write(struct.pack("<I", 0))  # crc32 暂不计算

            # Zones
            for z in self.zones:
                f.write(
                    struct.pack(
                        "<BBBBBBBB",
                        z["zone_id"],
                        z["sample_idx"],
                        z["root_note"],
                        z["min_note"],
                        z["max_note"],
                        z["min_vel"],
                        z["max_vel"],
                        z["flags"],
                    )
                )
                f.write(
                    struct.pack(
                        "<HHHHhHHH",
                        z["attack_ms"],
                        z["decay_ms"],
                        z["sustain_level"],
                        z["release_ms"],
                        z["pitch_cents"],
                        z["filter_cutoff"],
                        z["filter_resonance"],
                        z["reverb_send"],
                    )
                )
                f.write(b"\x00" * 24)  # reserved[6]

            # Samples
            for s in self.samples:
                f.write(
                    struct.pack(
                        "<IIIII",
                        s["data_offset"],
                        s["data_size"],
                        s["sample_rate"],
                        s["loop_start"],
                        s["loop_end"],
                    )
                )
                f.write(struct.pack("<HBB", s["channels"], s["bits"], s["root_note"]))
                f.write(s["name"])

            # Padding + Data
            f.write(b"\x00" * padding)
            f.write(self.pcm_data)

        print(
            f"Built: {len(self.zones)} zones, {len(self.samples)} samples, "
            f"{len(self.pcm_data)} bytes PCM -> {output_path}"
        )

    @classmethod
    def from_project(cls, project: "Project") -> "WavePackBuilder":
        """从 GUI 工程模型构造打包器。"""
        builder = cls(sample_rate=project.metadata.sample_rate)

        # 建立 sample_id -> builder sample_idx 映射
        sample_index_map: dict[str, int] = {}
        for sample in project.samples:
            path = sample.resolve_path()
            if not path.is_file():
                raise FileNotFoundError(f"采样文件不存在: {path}")
            idx = builder.add_sample(
                wav_path=path,
                root_note=sample.root_note,
                loop_start=sample.loop_start,
                loop_end=sample.loop_end,
                name=sample.name,
            )
            # 工程可指定与 WAV 不同的采样率，写入二进制时以工程为准
            builder.samples[idx]["sample_rate"] = sample.sample_rate
            sample_index_map[sample.id] = idx
        for zone in project.zones:
            sample_idx = sample_index_map.get(zone.sample_id)
            if sample_idx is None:
                raise ValueError(f"Zone 引用了不存在的采样: {zone.sample_id}")

            flags = zone.encoded_flags()
            builder.zones.append(
                {
                    "zone_id": len(builder.zones),
                    "sample_idx": sample_idx,
                    "root_note": zone.root_note,
                    "min_note": zone.min_note,
                    "max_note": zone.max_note,
                    "min_vel": zone.min_vel,
                    "max_vel": zone.max_vel,
                    "flags": flags,
                    "attack_ms": zone.adsr[0],
                    "decay_ms": zone.adsr[1],
                    "sustain_level": zone.adsr[2],
                    "release_ms": zone.adsr[3],
                    "pitch_cents": zone.pitch_cents,
                    "filter_cutoff": zone.filter_cutoff,
                    "filter_resonance": zone.filter_resonance,
                    "reverb_send": zone.reverb_send,
                }
            )

        return builder

    def clear(self) -> None:
        """清空内部状态，用于复用 Builder 实例。"""
        self.zones.clear()
        self.samples.clear()
        self.pcm_data = bytearray()
