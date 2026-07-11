"""基于 PySide6 QAudioSink 的音频预览封装。"""

import array
import wave
from pathlib import Path
from typing import List

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject, Signal
from PySide6.QtMultimedia import QAudio, QAudioFormat, QAudioSink, QMediaDevices


class AudioPlayer(QObject):
    """使用 QAudioSink 播放 WAV，支持按 rate 变速变调。"""

    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sinks: List[QAudioSink] = []

    def play(self, file_path: str | Path, rate: float = 1.0) -> None:
        """播放指定 WAV 文件，rate=1.0 原速，rate=2.0 快一倍/高八度。"""
        file_path = Path(file_path)
        try:
            with wave.open(str(file_path), "rb") as wf:
                nch = wf.getnchannels()
                sw = wf.getsampwidth()
                fr = wf.getframerate()
                nframes = wf.getnframes()
                raw = wf.readframes(nframes)
        except Exception:
            return

        if sw != 2 or nch != 1:
            # 仅支持 16-bit mono
            return

        if rate <= 0:
            rate = 0.05
        pcm = self._resample(raw, rate) if rate != 1.0 else raw

        fmt = QAudioFormat()
        fmt.setSampleRate(fr)
        fmt.setChannelCount(1)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)

        media_devices = QMediaDevices(self)
        device = media_devices.defaultAudioOutput()
        sink = QAudioSink(device, fmt, self)
        sink.stateChanged.connect(
            lambda state, s=sink: self._on_state_changed(state, s)
        )
        buf = QBuffer(QByteArray(pcm))
        buf.open(QIODevice.ReadOnly)
        sink.start(buf)
        self._sinks.append(sink)

    @staticmethod
    def _resample(raw: bytes, rate: float) -> bytes:
        """对 16-bit mono PCM 做线性插值重采样，改变播放时长与音高。"""
        arr = array.array("h", raw)
        src_len = len(arr)
        new_len = max(1, int(src_len / rate))
        new_arr = array.array("h")
        for i in range(new_len):
            src = i * rate
            idx = int(src)
            frac = src - idx
            if idx + 1 < src_len:
                v = arr[idx] * (1 - frac) + arr[idx + 1] * frac
            elif idx < src_len:
                v = arr[idx]
            else:
                v = 0
            v = max(-32768, min(32767, int(v)))
            new_arr.append(v)
        return new_arr.tobytes()

    def _on_state_changed(self, state: QAudio.State, sink: QAudioSink) -> None:
        if state in (QAudio.State.IdleState, QAudio.State.StoppedState):
            if sink in self._sinks:
                self._sinks.remove(sink)
            sink.deleteLater()
            if not self._sinks:
                self.finished.emit()

    def stop(self) -> None:
        """停止所有正在播放的声音。"""
        for sink in list(self._sinks):
            sink.stop()
            sink.deleteLater()
        self._sinks.clear()

    def is_playing(self) -> bool:
        """是否有声音正在播放。"""
        return any(
            sink.state() == QAudio.State.ActiveState for sink in self._sinks
        )
