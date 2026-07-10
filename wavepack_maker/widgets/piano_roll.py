"""钢琴卷帘：显示 88 键（A0-C8，MIDI note 21~108），正确绘制黑白键布局。"""

from typing import List, Optional, Set, Tuple

from PySide6.QtCore import QRect, Qt, Signal, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget


class PianoRoll(QWidget):
    """显示 88 键钢琴键盘条（A0-C8，MIDI 21~108）。

    - 白键连续排列，黑键位于相邻白键之间。
    - 未配置（不在任何 Zone note 范围内）的白键显示灰色。
    - 已配置的白键显示白色。
    - 黑键始终显示黑色。
    - 点击的键显示主题色高亮。
    """

    # 0=C, 1=C#, 2=D, 3=D#, 4=E, 5=F, 6=F#, 7=G, 8=G#, 9=A, 10=A#, 11=B
    BLACK_KEYS = {1, 3, 6, 8, 10}

    MIN_NOTE = 21   # A0
    MAX_NOTE = 108  # C8

    note_clicked = Signal(int)
    note_released = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._ranges: List[Tuple[int, int]] = []
        self._configured_notes: Set[int] = set()
        self._root_notes: List[int] = []
        self._hover_note: Optional[int] = None
        self._pressed_note: Optional[int] = None
        self._accent: QColor = QColor(0, 150, 255)
        self._release_timer = QTimer(self)
        self._release_timer.setSingleShot(True)
        self._release_timer.timeout.connect(self._release_pressed)
        self.setMinimumHeight(40)
        self.setMaximumHeight(90)
        self.setFont(QFont("Microsoft YaHei", 8))

    def set_theme(self, theme) -> None:
        """应用主题色。"""
        self._accent = theme.accent
        self.update()

    def set_highlight(self, ranges: List[Tuple[int, int]], root_notes: List[int]) -> None:
        """设置已配置的 note 范围与根音位置。"""
        self._ranges = list(ranges)
        self._root_notes = list(root_notes)
        self._configured_notes = set()
        for min_n, max_n in self._ranges:
            for n in range(max(self.MIN_NOTE, min_n), min(self.MAX_NOTE + 1, max_n + 1)):
                self._configured_notes.add(n)
        self.update()

    def clear_highlight(self) -> None:
        self._ranges = []
        self._configured_notes = set()
        self._root_notes = []
        self.update()

    def _white_key_notes(self) -> List[int]:
        """返回所有白键 note（A0-C8 范围内）。"""
        return [n for n in range(self.MIN_NOTE, self.MAX_NOTE + 1) if n % 12 not in self.BLACK_KEYS]

    def _white_key_index(self, note: int) -> int:
        """返回 note 在白键序列中的索引；若 note 是黑键则返回前一个白键索引。"""
        whites = self._white_key_notes()
        # 找到小于等于 note 的最大白键
        idx = 0
        for i, w in enumerate(whites):
            if w <= note:
                idx = i
            else:
                break
        return idx

    def _white_key_rect(self, note: int) -> QRect:
        """返回白键矩形。"""
        whites = self._white_key_notes()
        try:
            idx = whites.index(note)
        except ValueError:
            return QRect()
        w = self.width()
        n_white = len(whites)
        key_w = w / max(1, n_white)
        x = int(idx * key_w)
        next_x = int((idx + 1) * key_w)
        return QRect(x, 0, max(1, next_x - x), self.height())

    def _black_key_rect(self, note: int) -> QRect:
        """返回黑键矩形：位于相邻白键之间，宽度约为白键 60%，高度 60%。"""
        if note % 12 not in self.BLACK_KEYS:
            return QRect()
        prev_white = note - 1
        while prev_white >= self.MIN_NOTE and prev_white % 12 in self.BLACK_KEYS:
            prev_white -= 1
        next_white = note + 1
        while next_white <= self.MAX_NOTE and next_white % 12 in self.BLACK_KEYS:
            next_white += 1
        if prev_white < self.MIN_NOTE or next_white > self.MAX_NOTE:
            return QRect()
        prev_rect = self._white_key_rect(prev_white)
        next_rect = self._white_key_rect(next_white)
        center = (prev_rect.right() + next_rect.left()) // 2
        black_w = int(prev_rect.width() * 0.6)
        black_h = int(self.height() * 0.62)
        x = center - black_w // 2
        return QRect(x, 0, black_w, black_h)

    def note_at_x(self, x: int) -> int:
        """根据 X 坐标返回对应 MIDI note，优先黑键。"""
        # 先检查黑键
        for note in range(self.MIN_NOTE, self.MAX_NOTE + 1):
            if note % 12 in self.BLACK_KEYS:
                rect = self._black_key_rect(note)
                if rect.left() <= x <= rect.right():
                    return note
        # 再按白键位置
        whites = self._white_key_notes()
        if not whites:
            return self.MIN_NOTE
        w = self.width()
        n_white = len(whites)
        key_w = w / max(1, n_white)
        idx = max(0, min(n_white - 1, int(x / key_w)))
        return whites[idx]

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        h = self.height()
        fm = QFontMetrics(self.font())

        # 先画白键
        for note in range(self.MIN_NOTE, self.MAX_NOTE + 1):
            if note % 12 in self.BLACK_KEYS:
                continue
            rect = self._white_key_rect(note)
            if note == self._pressed_note:
                painter.fillRect(rect, self._accent)
            elif note in self._configured_notes:
                painter.fillRect(rect, Qt.white)
            else:
                painter.fillRect(rect, QColor(120, 120, 120))
            painter.setPen(QPen(Qt.gray, 1))
            painter.drawRect(rect)

        # 再画黑键（覆盖在白键接缝处）
        for note in range(self.MIN_NOTE, self.MAX_NOTE + 1):
            if note % 12 not in self.BLACK_KEYS:
                continue
            rect = self._black_key_rect(note)
            if note == self._pressed_note:
                painter.fillRect(rect, self._accent)
            else:
                painter.fillRect(rect, Qt.black)
            painter.setPen(QPen(Qt.darkGray, 1))
            painter.drawRect(rect)

        # C 音标签（仅在白键配置区域显示）
        painter.setPen(Qt.black)
        for note in range(self.MIN_NOTE, self.MAX_NOTE + 1):
            if note % 12 != 0:
                continue
            rect = self._white_key_rect(note)
            if rect.width() < 20:
                continue
            label = f"C{note // 12 - 1}"
            if fm.horizontalAdvance(label) < rect.width() - 4:
                painter.drawText(rect, Qt.AlignBottom | Qt.AlignHCenter, label)

        # 根音小圆点标记
        painter.setBrush(self._accent)
        painter.setPen(Qt.NoPen)
        for root in self._root_notes:
            if self.MIN_NOTE <= root <= self.MAX_NOTE:
                if root % 12 in self.BLACK_KEYS:
                    rect = self._black_key_rect(root)
                else:
                    rect = self._white_key_rect(root)
                if rect.isValid():
                    dot_y = int(rect.height() * 0.75)
                    painter.drawEllipse(rect.center().x() - 3, dot_y - 3, 6, 6)

        # 悬停 note 边框
        if self._hover_note is not None and self.MIN_NOTE <= self._hover_note <= self.MAX_NOTE:
            painter.setPen(QPen(self._accent, 2))
            painter.setBrush(Qt.NoBrush)
            if self._hover_note % 12 in self.BLACK_KEYS:
                painter.drawRect(self._black_key_rect(self._hover_note))
            else:
                painter.drawRect(self._white_key_rect(self._hover_note))

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._hover_note = self.note_at_x(int(event.position().x()))
        self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover_note = None
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        note = self.note_at_x(int(event.position().x()))
        if self.MIN_NOTE <= note <= self.MAX_NOTE:
            self._pressed_note = note
            self.note_clicked.emit(note)
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._release_pressed()

    def _release_pressed(self) -> None:
        if self._pressed_note is not None:
            self.note_released.emit(self._pressed_note)
            self._pressed_note = None
            self.update()

    def press_note(self, note: int) -> None:
        """外部调用：视觉按下某个 note（如 MIDI 输入时）。"""
        if self.MIN_NOTE <= note <= self.MAX_NOTE:
            self._pressed_note = note
            self._release_timer.start(150)
            self.update()
