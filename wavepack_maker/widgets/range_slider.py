"""双头范围滑块组件。"""

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget


class RangeSlider(QWidget):
    """支持同时拖动下限与上限的范围滑块。"""

    range_changed = Signal(int, int)

    def __init__(self, minimum: int = 0, maximum: int = 127, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._minimum = minimum
        self._maximum = maximum
        self._low = minimum
        self._high = maximum
        self._dragging: Optional[str] = None  # 'low' / 'high'
        self.setMinimumHeight(28)
        self.setMaximumHeight(36)

    def set_range(self, low: int, high: int) -> None:
        low = max(self._minimum, min(self._maximum, low))
        high = max(self._minimum, min(self._maximum, high))
        if low > high:
            low, high = high, low
        if low != self._low or high != self._high:
            self._low = low
            self._high = high
            self.range_changed.emit(self._low, self._high)
            self.update()

    def low(self) -> int:
        return self._low

    def high(self) -> int:
        return self._high

    def _value_at_x(self, x: int) -> int:
        w = max(1, self.width() - 20)
        ratio = max(0.0, min(1.0, (x - 10) / w))
        return int(self._minimum + ratio * (self._maximum - self._minimum))

    def _x_for_value(self, value: int) -> int:
        ratio = (value - self._minimum) / max(1, self._maximum - self._minimum)
        return int(10 + ratio * (self.width() - 20))

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        h = self.height()
        mid = h // 2

        # 背景条
        painter.setPen(Qt.NoPen)
        painter.setBrush(Qt.gray)
        painter.drawRoundedRect(10, mid - 4, self.width() - 20, 8, 4, 4)

        # 选中范围
        x1 = self._x_for_value(self._low)
        x2 = self._x_for_value(self._high)
        painter.setBrush(Qt.darkGreen)
        painter.drawRoundedRect(x1, mid - 4, x2 - x1, 8, 4, 4)

        # 两个滑块
        painter.setPen(QPen(Qt.white, 1))
        painter.setBrush(Qt.darkBlue)
        for value in (self._low, self._high):
            x = self._x_for_value(value)
            painter.drawEllipse(x - 6, mid - 6, 12, 12)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        x = int(event.position().x())
        x_low = self._x_for_value(self._low)
        x_high = self._x_for_value(self._high)

        if abs(x - x_low) <= abs(x - x_high):
            self._dragging = "low"
        else:
            self._dragging = "high"
        self._update_drag(x)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._dragging is None:
            return
        self._update_drag(int(event.position().x()))

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._dragging = None

    def _update_drag(self, x: int) -> None:
        value = self._value_at_x(x)
        if self._dragging == "low":
            if value > self._high:
                self._low = self._high
                self._high = value
                self._dragging = "high"
            else:
                self._low = value
        elif self._dragging == "high":
            if value < self._low:
                self._high = self._low
                self._low = value
                self._dragging = "low"
            else:
                self._high = value
        self.range_changed.emit(self._low, self._high)
        self.update()
