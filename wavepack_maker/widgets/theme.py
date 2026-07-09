"""Windows 主题色读取与应用。"""

from typing import Optional

from PySide6.QtGui import QColor


def get_windows_accent_color() -> QColor:
    """读取 Windows 系统强调色，失败则返回默认青色。"""
    try:
        import winreg

        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\DWM")
        value, _ = winreg.QueryValueEx(key, "AccentColor")
        winreg.CloseKey(key)
        # DWORD 格式为 0xAABBGGRR
        r = value & 0xFF
        g = (value >> 8) & 0xFF
        b = (value >> 16) & 0xFF
        return QColor(r, g, b)
    except Exception:
        return QColor(0, 150, 255)


class ThemeManager:
    """管理从 Windows 主题色提取的配色方案。"""

    def __init__(self):
        self.accent = get_windows_accent_color()
        self.accent_light = self._lighten(self.accent, 40)
        self.accent_dark = self._darken(self.accent, 40)
        self.background = QColor(30, 30, 30)
        self.surface = QColor(45, 45, 45)
        self.text = QColor(240, 240, 240)

    @staticmethod
    def _lighten(color: QColor, amount: int) -> QColor:
        h = color.hue()
        s = color.saturation()
        v = min(255, color.value() + amount)
        return QColor.fromHsv(h, s, v)

    @staticmethod
    def _darken(color: QColor, amount: int) -> QColor:
        h = color.hue()
        s = color.saturation()
        v = max(0, color.value() - amount)
        return QColor.fromHsv(h, s, v)

    def stylesheet(self) -> str:
        """返回应用到整个应用的 QSS。"""
        accent = self.accent.name()
        accent_light = self.accent_light.name()
        bg = self.background.name()
        surface = self.surface.name()
        text = self.text.name()
        return f"""
            QMainWindow {{
                background-color: {bg};
                color: {text};
            }}
            QGroupBox {{
                background-color: {surface};
                color: {text};
                border: 1px solid #555555;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
            QPushButton {{
                background-color: {surface};
                color: {text};
                border: 1px solid #666666;
                border-radius: 4px;
                padding: 5px 12px;
            }}
            QPushButton:hover {{
                background-color: {accent};
                color: #ffffff;
                border-color: {accent_light};
            }}
            QPushButton:pressed {{
                background-color: {accent_dark};
                color: #ffffff;
                border-color: {accent};
            }}
            QPushButton:disabled {{
                background-color: {surface};
                color: #888888;
                border-color: #555555;
            }}
            QToolBar QToolButton:hover {{
                background-color: {accent};
                color: #ffffff;
                border-radius: 4px;
            }}
            QToolBar QToolButton:pressed {{
                background-color: {accent_dark};
            }}
            QLineEdit, QSpinBox, QComboBox, QPlainTextEdit {{
                background-color: {bg};
                color: {text};
                border: 1px solid #666666;
                border-radius: 3px;
                padding: 3px;
            }}
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {{
                border: 1px solid {accent};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {text};
                width: 0px;
                height: 0px;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                background: {surface};
                border: 1px solid #666666;
                width: 16px;
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background: {accent};
            }}
            QSlider::groove:horizontal {{
                height: 6px;
                background: #666666;
                border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                background: {accent};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {accent_light};
                width: 12px;
                margin: -3px 0;
                border-radius: 6px;
            }}
            QTableWidget {{
                background-color: {surface};
                color: {text};
                border: none;
                gridline-color: transparent;
                outline: none;
            }}
            QTableWidget::item {{
                padding: 4px;
            }}
            QTableWidget::item:selected, QTableWidget::item:selected:active, QTableWidget::item:selected:!active {{
                background-color: {accent};
                color: #ffffff;
            }}
            QTableWidget::item:focus {{
                border: none;
                outline: none;
            }}
            QHeaderView::section {{
                background-color: {surface};
                color: {text};
                border: 1px solid #555555;
                padding: 4px;
            }}
            QMenu {{
                background-color: {surface};
                color: {text};
                border: 1px solid #555555;
            }}
            QMenu::item:selected {{
                background-color: {accent};
                color: #ffffff;
            }}
            QMenuBar {{
                background-color: {bg};
                color: {text};
            }}
            QMenuBar::item:selected {{
                background-color: {accent};
                color: #ffffff;
            }}
        """
