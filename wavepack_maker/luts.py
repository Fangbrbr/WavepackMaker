"""生成 ESP32Synth 所需 CentiHz 与 Cents 比例查表。"""

import math
from pathlib import Path
from typing import Optional


def generate_centihz_lut(path: str | Path = "centihz_lut.h") -> None:
    """生成 MIDI note -> 频率×100 的查表头文件。"""
    path = Path(path)
    lut = [int(round(440.0 * math.pow(2.0, (n - 69) / 12.0) * 100)) for n in range(128)]

    with open(path, "w", encoding="utf-8") as f:
        f.write("#ifndef MIDI_TO_CENTIHZ_LUT_H\n")
        f.write("#define MIDI_TO_CENTIHZ_LUT_H\n\n")
        f.write("#include <stdint.h>\n\n")
        f.write("static const uint32_t MIDI_TO_CENTIHZ_LUT[128] = {\n    ")
        f.write(", ".join(str(x) for x in lut))
        f.write("\n};\n\n")
        f.write("#endif /* MIDI_TO_CENTIHZ_LUT_H */\n")


def generate_cent_ratio_lut(path: str | Path = "cent_ratio_lut.h") -> None:
    """生成 cents -> Q16 频率比例的查表头文件（范围 -100~+100 cents）。"""
    path = Path(path)
    lut = [int(round(math.pow(2.0, c / 1200.0) * 65536)) for c in range(-100, 101)]

    with open(path, "w", encoding="utf-8") as f:
        f.write("#ifndef CENT_RATIO_LUT_H\n")
        f.write("#define CENT_RATIO_LUT_H\n\n")
        f.write("#include <stdint.h>\n\n")
        f.write("static const uint32_t CENT_RATIO_LUT[201] = {\n    ")
        f.write(", ".join(str(x) for x in lut))
        f.write("\n};\n\n")
        f.write("#endif /* CENT_RATIO_LUT_H */\n")


def generate_all(
    output_dir: str | Path = ".",
    centihz_name: Optional[str] = "centihz_lut.h",
    cent_ratio_name: Optional[str] = "cent_ratio_lut.h",
) -> None:
    """一次性生成两种 LUT 头文件。"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if centihz_name:
        generate_centihz_lut(output_dir / centihz_name)
    if cent_ratio_name:
        generate_cent_ratio_lut(output_dir / cent_ratio_name)
