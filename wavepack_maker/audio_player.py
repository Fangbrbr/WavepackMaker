"""基于 PySide6 QAudioSink 的软件混音音频预览封装。"""

import array
import wave
from pathlib import Path
from typing import List

from PySide6.QtCore import QIODevice, QObject
from PySide6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices


class _MixerStream:
    """一个待播放的 PCM 流及其当前读取位置。"""

    def __init__(self, pcm: bytes):
        self.pcm = pcm
        self.pos = 0


class _MixerIODevice(QIODevice):
    """软件混音器：把多个 PCM 流实时混合后提供给 QAudioSink。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._streams: List[_MixerStream] = []
        self.open(QIODevice.ReadOnly)

    def add_stream(self, pcm: bytes) -> None:
        """添加一个待播放的 16-bit mono PCM 流。"""
        self._streams.append(_MixerStream(pcm))

    def readData(self, maxlen: int) -> bytes:
        """QAudioSink 主动拉取数据时调用。"""
        frames = maxlen // 2
        if frames <= 0:
            return b""

        mixed = array.array("h", [0] * frames)
        active: List[_MixerStream] = []

        for stream in self._streams:
            arr = array.array("h", stream.pcm)
            src_len = len(arr)
            end = stream.pos + frames
            if end <= src_len:
                # 本 chunk 内流不会结束
                for i in range(frames):
                    mixed[i] += arr[stream.pos + i]
                stream.pos = end
                active.append(stream)
            else:
                # 流在本 chunk 内结束，只混合剩余部分
                remaining = src_len - stream.pos
                for i in range(remaining):
                    mixed[i] += arr[stream.pos + i]
                # 不加入 active，自然移除

        self._streams = active

        # clip 到 16-bit 范围
        for i in range(frames):
            mixed[i] = max(-32768, min(32767, mixed[i]))

        return mixed.tobytes()

    def bytesAvailable(self) -> int:
        # 让 QAudioSink 始终认为有数据可读；没有 stream 时返回静音。
        return 1024 * 1024


class AudioPlayer(QObject):
    """使用 QAudioSink + 软件混音播放 WAV，支持复音与变速变调。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        fmt = QAudioFormat()
        fmt.setSampleRate(44100)
        fmt.setChannelCount(1)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)

        media_devices = QMediaDevices(self)
        device = media_devices.defaultAudioOutput()

        self._mixer = _MixerIODevice(self)
        self._sink = QAudioSink(device, fmt, self)
        self._sink.setBufferSize(16384)
        self._sink.start(self._mixer)

    def play(self, file_path: str | Path, rate: float = 1.0) -> None:
        """播放指定 WAV 文件，rate=1.0 原速，rate=2.0 快一倍/高八度。

        多次调用会叠加播放，从而支持复音。
        """
        file_path = Path(file_path)
        if not file_path.is_file():
            return

        pcm = self._load_and_resample(file_path, rate)
        if pcm:
            self._mixer.add_stream(pcm)

    def _load_and_resample(self, file_path: Path, rate: float) -> bytes:
        """读取 WAV 并返回按目标 rate 重采样后的 16-bit mono PCM。"""
        try:
            with wave.open(str(file_path), "rb") as wf:
                nch = wf.getnchannels()
                sw = wf.getsampwidth()
                fr = wf.getframerate()
                nframes = wf.getnframes()
                raw = wf.readframes(nframes)
        except Exception:
            return b""

        if sw != 2 or nch != 1:
            return b""

        if rate <= 0:
            rate = 0.05

        # 先把不同采样率的源重采样到 44.1kHz，再按 rate 变速
        if fr != 44100:
            raw = self._resample(raw, 44100 / fr)

        if rate != 1.0:
            raw = self._resample(raw, rate)

        return raw

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

    def stop(self) -> None:
        """停止所有正在播放的声音。"""
        self._mixer._streams.clear()
        self._sink.stop()
        self._sink.start(self._mixer)

    def set_volume(self, volume: float) -> None:
        """volume: 0.0 ~ 1.0。"""
        self._sink.setVolume(max(0.0, min(1.0, volume)))

    def is_playing(self) -> bool:
        return bool(self._mixer._streams)
