"""WavePack Maker 上位机入口。

用法：
    python main.py
"""

import sys

from PySide6.QtWidgets import QApplication

from wavepack_maker.widgets.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("WavePack Maker")
    app.setApplicationDisplayName("WavePack Maker")

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
