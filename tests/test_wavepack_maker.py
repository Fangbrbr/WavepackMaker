"""WavePack Maker 核心逻辑单元测试。"""

import array
import json
import struct
import tempfile
import wave
from pathlib import Path

from wavepack_maker.builder import WavePackBuilder
from wavepack_maker.models import Project, ProjectMetadata, SampleEntry, ZoneEntry
from wavepack_maker.project_io import load_project, save_project
from wavepack_maker.validator import ValidationError, WavePackValidator


def _make_wav(path: Path, freq: float = 440.0, duration: float = 0.1, sample_rate: int = 44100):
    """生成单声道 16-bit 正弦波测试 WAV。"""
    import math

    nframes = int(sample_rate * duration)
    samples = array.array(
        "h",
        [int(32767 * 0.5 * math.sin(2 * math.pi * freq * i / sample_rate)) for i in range(nframes)],
    )
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples.tobytes())


def test_project_metadata_roundtrip():
    meta = ProjectMetadata(
        name="Test Piano",
        version="1.0.0",
        author="Tester",
        copyright="CC0",
        category="Piano",
        tags=["acoustic", "grand"],
        description="A test piano",
        notes="Some notes",
        sample_rate=48000,
    )
    d = meta.to_dict()
    meta2 = ProjectMetadata.from_dict(d)
    assert meta2.name == "Test Piano"
    assert meta2.author == "Tester"
    assert meta2.copyright == "CC0"
    assert meta2.sample_rate == 48000


def test_sample_from_wav():
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "c4.wav"
        _make_wav(wav, sample_rate=44100)
        sample = SampleEntry.from_wav(wav)
        assert sample.sample_rate == 44100
        assert sample.channels == 1
        assert sample.bits == 16
        assert sample.nframes > 0


def test_zone_validation():
    zone = ZoneEntry(root_note=60, min_note=55, max_note=72, poly_mode="multi")
    assert not zone.validate()

    # 旋律 Zone 要求根音在范围内
    zone_bad = ZoneEntry(
        root_note=80, min_note=55, max_note=72, poly_mode="multi"
    )
    assert zone_bad.validate()

    # 打击乐 Zone 要求 min == max == root
    zone_perc = ZoneEntry(
        root_note=36, min_note=36, max_note=36, poly_mode="retrigger"
    )
    assert not zone_perc.validate()


def test_project_io_and_export(tmp_path: Path = None):
    if tmp_path is None:
        tmp_path = Path(tempfile.mkdtemp())
    wav = tmp_path / "c4.wav"
    _make_wav(wav, freq=261.63)

    project = Project(metadata=ProjectMetadata(name="Test Kit"))
    sample = SampleEntry.from_wav(wav)
    sample.root_note = 60
    project.add_sample(sample)

    zone = ZoneEntry(
        sample_id=sample.id,
        name="C4 Zone",
        root_note=60,
        min_note=55,
        max_note=67,
        min_vel=0,
        max_vel=127,
        poly_mode="multi",
        max_same_note_voices=2,
    )
    project.add_zone(zone)

    # 保存工程
    wpp_path = tmp_path / "test.wpp"
    save_project(project, wpp_path)
    assert wpp_path.is_file()

    # 加载工程
    project2 = load_project(wpp_path)
    assert project2.metadata.name == "Test Kit"
    assert len(project2.samples) == 1
    assert len(project2.zones) == 1

    # 导出 wavepack
    out = tmp_path / "test.wavepack"
    builder = WavePackBuilder.from_project(project2)
    builder.build(out)
    assert out.is_file()

    # 校验
    header = WavePackValidator(out).validate()
    assert header["num_zones"] == 1
    assert header["num_samples"] == 1

    # 验证 Header magic
    with open(out, "rb") as f:
        assert f.read(8) == b"WAVEPACK"


def test_wavepack_header_version():
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "kick.wav"
        _make_wav(wav, freq=100)
        out = Path(tmp) / "kick.wavepack"
        builder = WavePackBuilder()
        builder.add_zone(wav, root_note=36, min_note=36, max_note=36, poly_mode="retrigger")
        builder.build(out)
        with open(out, "rb") as f:
            magic = f.read(8)
            version = struct.unpack("<H", f.read(2))[0]
        assert magic == b"WAVEPACK"
        assert version == 0x0100


if __name__ == "__main__":
    test_project_metadata_roundtrip()
    test_sample_from_wav()
    test_zone_validation()
    test_project_io_and_export()
    test_wavepack_header_version()
    print("All tests passed.")
