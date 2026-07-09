"""简易钢琴卷帘：显示 88 键（A0-C8，MIDI note 21~108）与高亮 Zone。"""

from typing import List, Optional, Tuple

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget


class PianoRoll(QWidget):
    """显示 88 键钢琴键盘条（A0-C8，MIDI note 21~108），支持高亮指定 note 范围。"""

    # 0=C, 1=C#, 2=D, 3=D#, 4=E, 5=F, 6=F#, 7=G, 8=G#, 9=A, 10=A#, 11=B
    BLACK_KEYS = {1, 3, 6, 8, 10}

    MIN_NOTE = 21   # A0
    MAX_NOTE = 108  # C8
    NUM_KEYS = 88

    note_clicked = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._ranges: List[Tuple[int, int]] = []  # (min_note, max_note)
        self._root_notes: List[int] = []
        self._hover_note: Optional[int] = None
        self._accent: QColor = QColor(0, 150, 255)
        self.setMinimumHeight(40)
        self.setMaximumHeight(90)
        self.setFont(QFont("Microsoft YaHei", 8))

    def set_theme(self, theme) -> None:
        """应用主题色。"""
        self._accent = theme.accent
        self.update()

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
        """根据 X 坐标返回对应 MIDI note（21~108）。"""
        w = max(1, self.width())
        note = self.MIN_NOTE + int((x / w) * self.NUM_KEYS)
        return max(self.MIN_NOTE, min(self.MAX_NOTE, note))

    def _note_rect(self, note: int) -> QRect:
        w = self.width()
        key_w = w / float(self.NUM_KEYS)
        idx = note - self.MIN_NOTE
        x = int(idx * key_w)
        next_x = int((idx + 1) * key_w)
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
            for n in range(max(self.MIN_NOTE, min_n), min(self.MAX_NOTE + 1, max_n + 1)):
                rect = self._note_rect(n)
                painter.fillRect(rect, QColor(self._accent.red(), self._accent.green(), self._accent.blue(), 120))

        # 根音标记
        for root in self._root_notes:
            if self.MIN_NOTE <= root <= self.MAX_NOTE:
                rect = self._note_rect(root)
                painter.fillRect(rect, QColor(self._accent.red(), self._accent.green(), self._accent.blue(), 180))

        # 画黑键与白键分隔
        for n in range(self.MIN_NOTE, self.MAX_NOTE + 1):
            rect = self._note_rect(n)
            if n % 12 in self.BLACK_KEYS:
                painter.fillRect(rect.adjusted(1, 0, -1, -h // 3), Qt.black)
            painter.drawRect(rect)

        # 画 C 音标签
        painter.setPen(Qt.black)
        for n in range(self.MIN_NOTE, self.MAX_NOTE + 1):
            if n % 12 == 0:  # C
                rect = self._note_rect(n)
                label = f"C{n // 12 - 1}"
                if fm.horizontalAdvance(label) < rect.width() - 4:
                    painter.drawText(rect, Qt.AlignBottom | Qt.AlignHCenter, label)

        # 悬停 note
        if self._hover_note is not None and self.MIN_NOTE <= self._hover_note <= self.MAX_NOTE:
            painter.setPen(QPen(self._accent, 2))
            painter.drawRect(self._note_rect(self._hover_note))

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._hover_note = self.note_at_x(int(event.position().x()))
        self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover_note = None
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        note = self.note_at_x(int(event.position().x()))
        if self.MIN_NOTE <= note <= self.MAX_NOTE:
            self.note_clicked.emit(note)
