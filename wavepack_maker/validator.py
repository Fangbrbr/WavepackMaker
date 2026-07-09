"""WavePack 文件结构校验器。"""

import struct
from pathlib import Path
from typing import List


class ValidationError(Exception):
    """校验失败时抛出，messages 包含全部错误描述。"""

    def __init__(self, messages: List[str]):
        self.messages = messages
        super().__init__("\n".join(messages))


class WavePackValidator:
    """按技术规范 v1.0 逐项校验 .wavepack 文件。"""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.errors: List[str] = []
        self.data: bytes = b""
        self.header: dict = {}
        self.zones: List[dict] = []
        self.samples: List[dict] = []

    def _read_header(self) -> bool:
        """读取并校验 Header，返回是否继续后续校验。"""
        if len(self.data) < 64:
            self.errors.append("文件长度不足 64 字节，无法包含 Header")
            return False

        magic = self.data[0:8]
        if magic != b"WAVEPACK":
            self.errors.append(f"magic 错误: {magic!r}，应为 b'WAVEPACK'")

        (
            version,
            num_zones,
            num_samples,
            flags,
            zone_dir_offset,
            sample_dir_offset,
            data_offset,
            data_size,
            sample_rate,
        ) = struct.unpack("<HHHHIIIII", self.data[8:36])

        self.header = {
            "magic": magic,
            "version": version,
            "num_zones": num_zones,
            "num_samples": num_samples,
            "flags": flags,
            "zone_dir_offset": zone_dir_offset,
            "sample_dir_offset": sample_dir_offset,
            "data_offset": data_offset,
            "data_size": data_size,
            "sample_rate": sample_rate,
        }

        if version != 0x0100:
            self.errors.append(f"version 错误: 0x{version:04X}，应为 0x0100")
        if num_zones == 0:
            self.errors.append("num_zones 必须大于 0")
        if num_samples == 0:
            self.errors.append("num_samples 必须大于 0")
        if flags != 0x0001:
            self.errors.append(f"flags 错误: 0x{flags:04X}，当前应固定为 0x0001")
        if zone_dir_offset != 64:
            self.errors.append(f"zone_dir_offset 错误: {zone_dir_offset}，应为 64")
        if sample_dir_offset != 64 + num_zones * 48:
            self.errors.append(
                f"sample_dir_offset 错误: {sample_dir_offset}，"
                f"应为 {64 + num_zones * 48}"
            )
        if data_offset % 4096 != 0:
            self.errors.append(f"data_offset 未 4096 对齐: {data_offset}")
        if data_offset + data_size > len(self.data):
            self.errors.append(
                f"采样数据区超出文件末尾: data_offset={data_offset}, "
                f"data_size={data_size}, file_size={len(self.data)}"
            )

        return not self.errors

    def _read_zones(self) -> None:
        """读取 Zone Directory。"""
        n = self.header["num_zones"]
        off = self.header["zone_dir_offset"]
        size = n * 48
        if off + size > len(self.data):
            self.errors.append("Zone Directory 超出文件末尾")
            return

        for i in range(n):
            base = off + i * 48
            (
                zone_id,
                sample_idx,
                root_note,
                min_note,
                max_note,
                min_vel,
                max_vel,
                flags,
                attack_ms,
                decay_ms,
                sustain_level,
                release_ms,
                pitch_cents,
                filter_cutoff,
                filter_resonance,
                reverb_send,
            ) = struct.unpack(
                "<BBBBBBBB HHHH hHHH",
                self.data[base : base + 24],
            )
            self.zones.append(
                {
                    "zone_id": zone_id,
                    "sample_idx": sample_idx,
                    "root_note": root_note,
                    "min_note": min_note,
                    "max_note": max_note,
                    "min_vel": min_vel,
                    "max_vel": max_vel,
                    "flags": flags,
                    "attack_ms": attack_ms,
                    "decay_ms": decay_ms,
                    "sustain_level": sustain_level,
                    "release_ms": release_ms,
                    "pitch_cents": pitch_cents,
                }
            )

    def _read_samples(self) -> None:
        """读取 Sample Directory。"""
        n = self.header["num_samples"]
        off = self.header["sample_dir_offset"]
        size = n * 32
        if off + size > len(self.data):
            self.errors.append("Sample Directory 超出文件末尾")
            return

        for i in range(n):
            base = off + i * 32
            fields = self.data[base : base + 24]
            (
                data_offset,
                data_size,
                sample_rate,
                loop_start,
                loop_end,
                channels,
                bits,
                root_note,
            ) = struct.unpack("<IIIII HBB", fields)
            name = self.data[base + 24 : base + 32]
            self.samples.append(
                {
                    "data_offset": data_offset,
                    "data_size": data_size,
                    "sample_rate": sample_rate,
                    "loop_start": loop_start,
                    "loop_end": loop_end,
                    "channels": channels,
                    "bits": bits,
                    "root_note": root_note,
                    "name": name,
                }
            )

    def _validate_zones(self) -> None:
        """校验 Zone 字段语义。"""
        num_samples = self.header["num_samples"]
        data_size_total = self.header["data_size"]

        for i, z in enumerate(self.zones):
            prefix = f"Zone[{i}]"
            if z["sample_idx"] >= num_samples:
                self.errors.append(f"{prefix}: sample_idx {z['sample_idx']} >= num_samples {num_samples}")
            if z["min_note"] > z["max_note"]:
                self.errors.append(f"{prefix}: min_note {z['min_note']} > max_note {z['max_note']}")
            if z["min_vel"] > z["max_vel"]:
                self.errors.append(f"{prefix}: min_vel {z['min_vel']} > max_vel {z['max_vel']}")

            poly_bits = z["flags"] & 0x0C
            if poly_bits not in (0x00, 0x04, 0x08):
                self.errors.append(f"{prefix}: flags 的 bit2~3 非法: 0x{poly_bits:02X}")

            is_percussion = (z["flags"] & 0x01) == 0
            if is_percussion:
                if not (z["min_note"] == z["max_note"] == z["root_note"]):
                    self.errors.append(
                        f"{prefix}: percussion zone 要求 min_note == max_note == root_note"
                    )
            else:
                if z["min_note"] >= z["max_note"]:
                    self.errors.append(
                        f"{prefix}: melodic zone 要求 min_note < max_note"
                    )
                if not (z["min_note"] <= z["root_note"] <= z["max_note"]):
                    self.errors.append(
                        f"{prefix}: melodic zone 要求 root_note 在 [min_note, max_note] 内"
                    )

            if not (0 <= z["sustain_level"] <= 255):
                self.errors.append(f"{prefix}: sustain_level {z['sustain_level']} 超出 0~255")
            if not (-100 <= z["pitch_cents"] <= 100):
                self.errors.append(f"{prefix}: pitch_cents {z['pitch_cents']} 超出 -100~+100")

    def _validate_samples(self) -> None:
        """校验 Sample 字段语义。"""
        data_size_total = self.header["data_size"]

        for i, s in enumerate(self.samples):
            prefix = f"Sample[{i}]"
            if s["data_size"] % 2 != 0:
                self.errors.append(f"{prefix}: data_size {s['data_size']} 不是偶数")
            if s["data_offset"] + s["data_size"] > data_size_total:
                self.errors.append(
                    f"{prefix}: data_offset+data_size ({s['data_offset'] + s['data_size']}) "
                    f"超过 data_size_total ({data_size_total})"
                )
            if s["channels"] != 1:
                self.errors.append(f"{prefix}: 当前仅支持 channels=1， got {s['channels']}")
            if s["bits"] != 16:
                self.errors.append(f"{prefix}: 当前仅支持 bits=16， got {s['bits']}")

    def validate(self) -> dict:
        """执行完整校验；通过返回 header 字典，失败抛出 ValidationError。"""
        with open(self.path, "rb") as f:
            self.data = f.read()

        self.errors.clear()
        self.zones.clear()
        self.samples.clear()

        if self._read_header():
            self._read_zones()
            self._read_samples()
            self._validate_zones()
            self._validate_samples()

        if self.errors:
            raise ValidationError(self.errors)

        return self.header
