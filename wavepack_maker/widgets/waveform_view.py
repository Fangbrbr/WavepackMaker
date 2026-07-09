"""波形显示组件：读取 WAV 并缩略绘制，支持拖动标记循环点。"""

import array
import wave
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget


class WaveformView(QWidget):
    """显示单声道 16-bit WAV 波形，支持拖动两个光标标记循环区间。"""

    loop_changed = Signal(int, int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._samples: List[int] = []
        self._sample_rate: int = 44100
        self._loop_start: int = 0
        self._loop_end: int = 0
        self._selection_start: Optional[int] = None
        self._selection_end: Optional[int] = None
        self._dragging: Optional[str] = None  # 'start' / 'end' / 'region'
        self._accent: QColor = QColor(0, 150, 255)
        self._bg: QColor = QColor(30, 30, 30)
        self.setMinimumHeight(180)
        self.setAutoFillBackground(True)
        self._update_palette()

    def set_theme(self, theme) -> None:
        """应用主题色。"""
        self._accent = theme.accent
        self._bg = theme.background
        self._update_palette()
        self.update()

    def _update_palette(self) -> None:
        pal = self.palette()
        pal.setColor(self.backgroundRole(), self._bg)
        self.setPalette(pal)

    def load_wav(self, file_path: str | Path) -> bool:
        """加载 WAV 文件并缓存样本。"""
        file_path = Path(file_path)
        if not file_path.is_file():
            self._samples = []
            self.update()
            return False

        try:
            with wave.open(str(file_path), "rb") as wf:
                nch = wf.getnchannels()
                sw = wf.getsampwidth()
                self._sample_rate = wf.getframerate()
                nframes = wf.getnframes()
                raw = wf.readframes(nframes)

                if sw != 2:
                    self._samples = []
                    self.update()
                    return False

                data = array.array("h", raw)
                if nch == 2:
                    self._samples = [
                        (data[i * 2] + data[i * 2 + 1]) // 2 for i in range(nframes)
                    ]
                else:
                    self._samples = list(data)
        except Exception:
            self._samples = []
            self.update()
            return False

        self._loop_start = 0
        self._loop_end = len(self._samples)
        self._selection_start = None
        self._selection_end = None
        self.update()
        return True

    def clear(self) -> None:
        self._samples = []
        self._loop_start = 0
        self._loop_end = 0
        self._selection_start = None
        self._selection_end = None
        self.update()

    def set_loop_region(self, start: int, end: int) -> None:
        """设置循环区间（样本 frame 数）。"""
        if self._samples:
            end = max(start, min(end, len(self._samples)))
            start = max(0, min(start, end))
        self._loop_start = start
        self._loop_end = end
        self.update()

    def get_loop_region(self) -> tuple[int, int]:
        return self._loop_start, self._loop_end

    def frame_at_x(self, x: int) -> int:
        """将鼠标 X 坐标转换为样本 frame 索引。"""
        if not self._samples:
            return 0
        width = max(1, self.width())
        return int((x / width) * len(self._samples))

    def _x_for_frame(self, frame: int) -> int:
        """将样本 frame 索引转换为 X 坐标。"""
        if not self._samples:
            return 0
        width = max(1, self.width())
        return int((frame / len(self._samples)) * width)

    def _nearby_loop_handle(self, x: int) -> Optional[str]:
        """判断鼠标 X 是否靠近 loop start/end 光标，返回 'start' / 'end' / None。"""
        if not self._samples:
            return None
        sx = self._x_for_frame(self._loop_start)
        ex = self._x_for_frame(self._loop_end)
        threshold = 8
        if abs(x - sx) <= threshold:
            return "start"
        if abs(x - ex) <= threshold:
            return "end"
        return None

    def _downsample(self, target_width: int) -> List[int]:
        """降采样到目标像素宽度，返回每个像素的最大振幅绝对值。"""
        if not self._samples or target_width <= 0:
            return []
        n = len(self._samples)
        if n <= target_width:
            return [abs(s) for s in self._samples]

        block = n // target_width
        result: List[int] = []
        for i in range(target_width):
            start = i * block
            end = min(start + block, n)
            peak = max(abs(self._samples[j]) for j in range(start, end)) if end > start else 0
            result.append(peak)
        return result

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        rect = self.rect()
        w, h = rect.width(), rect.height()
        mid = h // 2

        if not self._samples:
            painter.setPen(Qt.white)
            painter.drawText(rect, Qt.AlignCenter, "无波形数据")
            return

        peaks = self._downsample(w)
        if not peaks:
            return

        # 绘制波形
        pen = QPen(self._accent)
        pen.setWidth(1)
        painter.setPen(pen)
        scale = (h / 2 - 2) / 32768.0
        for x, peak in enumerate(peaks):
            amp = int(peak * scale)
            painter.drawLine(x, mid - amp, x, mid + amp)

        # 绘制循环区间背景
        ls_x = self._x_for_frame(self._loop_start)
        le_x = self._x_for_frame(self._loop_end)
        painter.fillRect(
            QRect(ls_x, 0, le_x - ls_x, h),
            QColor(self._accent.red(), self._accent.green(), self._accent.blue(), 60),
        )

        # 绘制循环起始/结束光标
        painter.setPen(QPen(self._accent, 2))
        painter.drawLine(ls_x, 0, ls_x, h)
        painter.drawLine(le_x, 0, le_x, h)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if not self._samples:
            return
        x = int(event.position().x())
        handle = self._nearby_loop_handle(x)
        if handle is not None:
            self._dragging = handle
            return
        # 否则框选新区域
        frame = self.frame_at_x(x)
        self._selection_start = frame
        self._selection_end = frame
        self._dragging = "region"

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if not self._samples:
            return
        x = int(event.position().x())

        # 悬停时改变光标形状
        handle = self._nearby_loop_handle(x)
        if handle is not None and self._dragging is None:
            self.setCursor(QCursor(Qt.SizeHorCursor))
        elif self._dragging is None:
            self.unsetCursor()

        if self._dragging == "start":
            frame = max(0, min(self._loop_end, self.frame_at_x(x)))
            self._loop_start = frame
            self.loop_changed.emit(self._loop_start, self._loop_end)
            self.update()
        elif self._dragging == "end":
            frame = max(self._loop_start, min(len(self._samples), self.frame_at_x(x)))
            self._loop_end = frame
            self.loop_changed.emit(self._loop_start, self._loop_end)
            self.update()
        elif self._dragging == "region" and self._selection_start is not None:
            self._selection_end = self.frame_at_x(x)
            start = max(0, min(self._selection_start, self._selection_end))
            end = min(len(self._samples), max(self._selection_start, self._selection_end))
            self.set_loop_region(start, end)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._dragging == "region" and self._selection_start is not None:
            start = max(0, min(self._selection_start, self._selection_end or self._selection_start))
            end = min(len(self._samples), max(self._selection_start, self._selection_end or self._selection_start))
            self.set_loop_region(start, end)
            self.loop_changed.emit(self._loop_start, self._loop_end)
        self._dragging = None
        self._selection_start = None
        self._selection_end = None
        self.unsetCursor()
