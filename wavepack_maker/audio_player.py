"""基于 PySide6 QMediaPlayer 的音频预览封装。"""

import array
import tempfile
import uuid
import wave
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer


class AudioPlayer:
    """包装 QMediaPlayer，通过预重采样实现变速变调播放。"""

    def __init__(self, parent=None):
        self._player = QMediaPlayer(parent)
        self._audio_output = QAudioOutput(parent)
        self._player.setAudioOutput(self._audio_output)
        self._audio_output.setVolume(0.8)
        self._temp_dir = tempfile.TemporaryDirectory()

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

        # 生成临时 WAV，让 QMediaPlayer 原速播放重采样后的数据
        tmp_path = Path(self._temp_dir.name) / f"{uuid.uuid4().hex}.wav"
        with wave.open(str(tmp_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(fr)
            wf.writeframes(pcm)

        self._player.setSource(QUrl.fromLocalFile(str(tmp_path)))
        self._audio_output.setVolume(0.8)
        self._player.play()

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

    def pause(self) -> None:
        self._player.pause()

    def stop(self) -> None:
        self._player.stop()

    def set_volume(self, volume: float) -> None:
        """volume: 0.0 ~ 1.0。"""
        self._audio_output.setVolume(max(0.0, min(1.0, volume)))

    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlayingState
