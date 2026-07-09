"""波形显示组件：读取 WAV 并缩略绘制。"""

import array
import wave
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget


class WaveformView(QWidget):
    """显示单声道 16-bit WAV 波形，支持循环区间标记。"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._samples: List[int] = []
        self._sample_rate: int = 44100
        self._loop_start: int = 0
        self._loop_end: int = 0
        self._selection_start: Optional[int] = None
        self._selection_end: Optional[int] = None
        self.setMinimumHeight(80)
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(self.backgroundRole(), QColor(245, 245, 245))
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
            painter.drawText(rect, Qt.AlignCenter, "无波形数据")
            return

        peaks = self._downsample(w)
        if not peaks:
            return

        # 绘制波形
        pen = QPen(Qt.darkBlue)
        pen.setWidth(1)
        painter.setPen(pen)
        scale = (h / 2 - 2) / 32768.0
        for x, peak in enumerate(peaks):
            amp = int(peak * scale)
            painter.drawLine(x, mid - amp, x, mid + amp)

        # 绘制循环区间
        if self._loop_end > self._loop_start and self._samples:
            ls_x = int((self._loop_start / len(self._samples)) * w)
            le_x = int((self._loop_end / len(self._samples)) * w)
            painter.fillRect(QRect(ls_x, 0, le_x - ls_x, h), QColor(0, 128, 255, 40))
            painter.setPen(QPen(Qt.blue, 1, Qt.DashLine))
            painter.drawLine(ls_x, 0, ls_x, h)
            painter.drawLine(le_x, 0, le_x, h)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if not self._samples:
            return
        frame = self.frame_at_x(int(event.position().x()))
        self._selection_start = frame
        self._selection_end = frame

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._selection_start is None or not self._samples:
            return
        self._selection_end = self.frame_at_x(int(event.position().x()))
        start = max(0, min(self._selection_start, self._selection_end))
        end = min(len(self._samples), max(self._selection_start, self._selection_end))
        self.set_loop_region(start, end)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._selection_start = None
        self._selection_end = None
