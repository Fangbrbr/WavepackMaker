"""WavePack Maker 上位机入口。

用法：
    python main.py
"""

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from wavepack_maker.widgets.main_window import MainWindow
from wavepack_maker.widgets.theme import ThemeManager


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("WavePack Maker")
    app.setApplicationDisplayName("WavePack Maker")

    # 设置应用图标（窗口左上角、任务栏、打包后可执行文件图标）
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # PyInstaller 单文件模式：资源解压到临时目录
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).parent
    icon_path = base_path / "assets" / "logo.ico"
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))

    theme = ThemeManager()
    app.setStyleSheet(theme.stylesheet())

    window = MainWindow()
    window.set_theme(theme)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
