"""WavePack Maker 上位机入口。

用法：
    python main.py
"""

import sys

from PySide6.QtWidgets import QApplication

from wavepack_maker.widgets.main_window import MainWindow
from wavepack_maker.widgets.theme import ThemeManager


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("WavePack Maker")
    app.setApplicationDisplayName("WavePack Maker")

    theme = ThemeManager()
    app.setStyleSheet(theme.stylesheet())

    window = MainWindow()
    window.set_theme(theme)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
