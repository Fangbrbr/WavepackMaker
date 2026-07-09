"""简易钢琴卷帘：显示 0~127 MIDI note 范围与高亮 Zone。"""

from typing import List, Optional, Tuple

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget


class PianoRoll(QWidget):
    """显示 MIDI note 0-127 的钢琴键盘条，支持高亮指定 note 范围。"""

    # 0=C, 1=C#, 2=D, 3=D#, 4=E, 5=F, 6=F#, 7=G, 8=G#, 9=A, 10=A#, 11=B
    BLACK_KEYS = {1, 3, 6, 8, 10}

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._ranges: List[Tuple[int, int]] = []  # (min_note, max_note)
        self._root_notes: List[int] = []
        self._hover_note: Optional[int] = None
        self.setMinimumHeight(60)
        self.setFont(QFont("Microsoft YaHei", 8))

    def set_highlight(self, ranges: List[Tuple[int, int]], root_notes: List[int]) -> None:
        """设置要高亮的 note 范围与根音位置。"""
        self._ranges = list(ranges)
        self._root_notes = list(root_notes)
        self.update()

    def clear_highlight(self) -> None:
        self._ranges = []
        self._root_notes = []
        self.update()

    def note_at_x(self, x: int) -> int:
        """根据 X 坐标返回对应 MIDI note（0~127）。"""
        w = max(1, self.width())
        return int((x / w) * 128)

    def _note_rect(self, note: int) -> QRect:
        w = self.width()
        key_w = w / 128.0
        x = int(note * key_w)
        next_x = int((note + 1) * key_w)
        return QRect(x, 0, max(1, next_x - x), self.height())

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        h = self.height()
        fm = QFontMetrics(self.font())

        # 画白键底
        painter.fillRect(self.rect(), Qt.white)
        painter.setPen(QPen(Qt.gray, 1))

        # 高亮范围
        for min_n, max_n in self._ranges:
            for n in range(max(0, min_n), min(128, max_n + 1)):
                rect = self._note_rect(n)
                painter.fillRect(rect, QColor(100, 200, 100, 120))

        # 根音标记
        for root in self._root_notes:
            if 0 <= root < 128:
                rect = self._note_rect(root)
                painter.fillRect(rect, QColor(255, 80, 80, 180))

        # 画黑键与白键分隔
        for n in range(128):
            rect = self._note_rect(n)
            if n % 12 in self.BLACK_KEYS:
                painter.fillRect(rect.adjusted(1, 0, -1, -h // 3), Qt.black)
            painter.drawRect(rect)

        # 画 C 音标签
        painter.setPen(Qt.black)
        for n in range(0, 128, 12):
            rect = self._note_rect(n)
            label = f"C{n // 12 - 1}"
            if fm.horizontalAdvance(label) < rect.width() - 4:
                painter.drawText(rect, Qt.AlignBottom | Qt.AlignHCenter, label)

        # 悬停 note
        if self._hover_note is not None and 0 <= self._hover_note < 128:
            painter.setPen(QPen(Qt.red, 2))
            painter.drawRect(self._note_rect(self._hover_note))

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._hover_note = self.note_at_x(int(event.position().x()))
        self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover_note = None
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        note = self.note_at_x(int(event.position().x()))
        # 可扩展：点击发出信号供外部设置 root_note
