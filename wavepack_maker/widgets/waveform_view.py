"""波形显示组件：读取 WAV 并缩略绘制，支持标记循环点。"""

import array
import wave
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QCursor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget


class WaveformView(QWidget):
    """显示单声道 16-bit WAV 波形，支持左键/右键标记循环起止点。"""

    loop_changed = Signal(int, int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._samples: List[int] = []
        self._sample_rate: int = 44100
        self._loop_start: int = 0
        self._loop_end: int = 0
        self._editable: bool = False
        self._dragging: Optional[str] = None  # 'start' / 'end'
        self._accent: QColor = QColor(0, 150, 255)
        self._bg: QColor = QColor(30, 30, 30)
        self._start_color: QColor = QColor(255, 255, 255)
        self._end_color: QColor = QColor(255, 220, 0)
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

    def set_editable(self, editable: bool) -> None:
        """设置循环标记是否可编辑。"""
        self._editable = editable
        if not editable:
            self._dragging = None
            self.unsetCursor()
        self.update()

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
        self._dragging = None
        self.update()
        return True

    def clear(self) -> None:
        self._samples = []
        self._loop_start = 0
        self._loop_end = 0
        self._dragging = None
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
        """判断鼠标 X 是否靠近 loop start/end 光标。"""
        if not self._samples or not self._editable:
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
        timeline_h = 24
        wave_h = max(1, h - timeline_h)
        mid = wave_h // 2

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
        scale = (wave_h / 2 - 2) / 32768.0
        for x, peak in enumerate(peaks):
            amp = int(peak * scale)
            painter.drawLine(x, mid - amp, x, mid + amp)

        # 绘制循环起始/结束光标
        ls_x = self._x_for_frame(self._loop_start)
        le_x = self._x_for_frame(self._loop_end)
        painter.setPen(QPen(self._start_color, 2))
        painter.drawLine(ls_x, 0, ls_x, wave_h)
        painter.setPen(QPen(self._end_color, 2))
        painter.drawLine(le_x, 0, le_x, wave_h)

        # 绘制底部时间轴
        self._draw_time_axis(painter, w, wave_h, timeline_h)

    def _draw_time_axis(self, painter: QPainter, w: int, y: int, h: int) -> None:
        """在底部绘制时间轴（秒）。"""
        if not self._samples or self._sample_rate <= 0:
            return
        total_seconds = len(self._samples) / self._sample_rate
        if total_seconds <= 0:
            return

        # 背景条
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(40, 40, 40))
        painter.drawRect(0, y, w, h)

        # 计算合适的刻度间隔
        target_ticks = max(2, w // 100)
        raw_step = total_seconds / target_ticks
        # 对齐到 1 / 2 / 5 / 10 / 20 / 30 / 60 秒
        nice_steps = [0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 30, 60]
        step = next((s for s in nice_steps if s >= raw_step), nice_steps[-1])

        painter.setPen(QPen(Qt.white, 1))
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)

        t = 0.0
        while t <= total_seconds + 1e-9:
            x = int((t / total_seconds) * w)
            painter.drawLine(x, y, x, y + 6)
            painter.drawText(x + 2, y + 18, f"{t:.3g}s")
            t += step

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if not self._samples or not self._editable:
            return
        x = int(event.position().x())
        handle = self._nearby_loop_handle(x)
        if handle is not None:
            self._dragging = handle
            return
        frame = self.frame_at_x(x)
        if event.button() == Qt.LeftButton:
            self._loop_start = max(0, min(frame, self._loop_end))
            self._dragging = "start"
        elif event.button() == Qt.RightButton:
            self._loop_end = max(self._loop_start, min(frame, len(self._samples)))
            self._dragging = "end"
        self.loop_changed.emit(self._loop_start, self._loop_end)
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if not self._samples:
            return
        x = int(event.position().x())

        if self._editable:
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

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._dragging = None
        self.unsetCursor()
