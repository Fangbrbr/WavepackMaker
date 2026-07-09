"""基于 PySide6 QMediaPlayer 的音频预览封装。"""

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer


class AudioPlayer:
    """包装 QMediaPlayer，提供简单的播放/暂停/停止接口。"""

    def __init__(self):
        self._player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._player.setAudioOutput(self._audio_output)
        self._audio_output.setVolume(0.8)

    def play(self, file_path: str | Path, rate: float = 1.0) -> None:
        """播放指定 WAV 文件，可指定播放速率（rate=1.0 原速，rate=2.0 快一倍/高八度）。"""
        # QMediaPlayer.setPlaybackRate 支持范围约 0.05 ~ 5.0
        self._player.setPlaybackRate(max(0.05, min(5.0, rate)))
        self._player.setSource(QUrl.fromLocalFile(str(file_path)))
        self._player.play()

    def pause(self) -> None:
        self._player.pause()

    def stop(self) -> None:
        self._player.stop()

    def set_volume(self, volume: float) -> None:
        """volume: 0.0 ~ 1.0。"""
        self._audio_output.setVolume(max(0.0, min(1.0, volume)))

    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlayingState
