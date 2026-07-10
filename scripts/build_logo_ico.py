"""将 assets/logo.png 转换为 assets/logo.ico，供 PyInstaller 打包使用。"""

import struct
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    png_path = root / "assets" / "logo.png"
    ico_path = root / "assets" / "logo.ico"

    if not png_path.is_file():
        print(f"未找到 {png_path}，跳过 logo.ico 生成")
        return

    src = QImage(str(png_path))
    if src.isNull():
        print(f"无法加载 {png_path}")
        return

    sizes = [256, 128, 64, 48, 32, 16]
    entries = []
    images = []
    offset = 6 + 16 * len(sizes)

    for size in sizes:
        img = src.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if img.format() != QImage.Format_ARGB32:
            img = img.convertToFormat(QImage.Format_ARGB32)

        pixels = []
        for y in range(size - 1, -1, -1):
            for x in range(size):
                rgb = img.pixel(x, y)
                # QRgb 是 0xAARRGGBB，小端存储为 BGRA
                a = (rgb >> 24) & 0xFF
                r = (rgb >> 16) & 0xFF
                g = (rgb >> 8) & 0xFF
                b = rgb & 0xFF
                pixels.extend([b, g, r, a])

        bmp_header = struct.pack(
            "<IIIHHIIiiII",
            40, size, size * 2, 1, 32, 0, 0, 0, 0, 0, 0,
        )
        bmp = bmp_header + bytes(pixels)
        images.append(bmp)
        width_byte = size if size < 256 else 0
        height_byte = size if size < 256 else 0
        entries.append(
            struct.pack(
                "<BBBBHHII",
                width_byte, height_byte, 0, 0, 1, 32, len(bmp), offset,
            )
        )
        offset += len(bmp)

    icondir = struct.pack("<HHH", 0, 1, len(sizes))
    data = icondir + b"".join(entries) + b"".join(images)
    ico_path.write_bytes(data)
    print(f"generated {ico_path} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
