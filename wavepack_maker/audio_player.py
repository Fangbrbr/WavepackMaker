"""基于 PySide6 QMediaPlayer 的音频预览封装。"""

import array
import tempfile
import uuid
import wave
from pathlib import Path
from typing import List, Tuple

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer


class AudioPlayer:
    """包装 QMediaPlayer，支持复音与变速变调播放。"""

    def __init__(self, parent=None, max_voices: int = 8):
        self._parent = parent
        self._max_voices = max(max_voices, 1)
        self._voices: List[Tuple[QMediaPlayer, QAudioOutput]] = []
        self._temp_dir = tempfile.TemporaryDirectory()

    def play(self, file_path: str | Path, rate: float = 1.0) -> None:
        """播放指定 WAV 文件，rate=1.0 原速，rate=2.0 快一倍/高八度。

        每次调用会找一个空闲的 Voice 或使用新的 Voice，从而支持复音。
        """
        file_path = Path(file_path)
        if not file_path.is_file():
            return

        if rate <= 0:
            rate = 0.05

        source_path = file_path
        if rate != 1.0:
            source_path = self._make_resampled_wav(file_path, rate)
            if source_path is None:
                return

        player, output = self._allocate_voice()
        output.setVolume(0.8)
        player.setSource(QUrl.fromLocalFile(str(source_path)))
        player.play()

    def _allocate_voice(self) -> Tuple[QMediaPlayer, QAudioOutput]:
        """分配一个可用的播放 Voice；优先复用已停止的，否则创建新的。"""
        for player, output in self._voices:
            if player.playbackState() == QMediaPlayer.StoppedState:
                return player, output

        if len(self._voices) < self._max_voices:
            output = QAudioOutput(self._parent)
            output.setVolume(0.8)
            player = QMediaPlayer(self._parent)
            player.setAudioOutput(output)
            self._voices.append((player, output))
            return player, output

        # 达到上限：复用最早创建的 Voice（会截断它当前播放的声音）
        return self._voices[0]

    def _make_resampled_wav(self, file_path: Path, rate: float) -> Path | None:
        """将 WAV 按 rate 重采样后写入临时文件，返回临时文件路径。"""
        try:
            with wave.open(str(file_path), "rb") as wf:
                nch = wf.getnchannels()
                sw = wf.getsampwidth()
                fr = wf.getframerate()
                nframes = wf.getnframes()
                raw = wf.readframes(nframes)
        except Exception:
            return None

        if sw != 2 or nch != 1:
            return None

        pcm = self._resample(raw, rate)
        tmp_path = Path(self._temp_dir.name) / f"{uuid.uuid4().hex}.wav"
        with wave.open(str(tmp_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(fr)
            wf.writeframes(pcm)
        return tmp_path

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
        for player, _ in self._voices:
            player.stop()

    def set_volume(self, volume: float) -> None:
        """volume: 0.0 ~ 1.0。"""
        for _, output in self._voices:
            output.setVolume(max(0.0, min(1.0, volume)))

    def is_playing(self) -> bool:
        return any(
            player.playbackState() == QMediaPlayer.PlayingState
            for player, _ in self._voices
        )
