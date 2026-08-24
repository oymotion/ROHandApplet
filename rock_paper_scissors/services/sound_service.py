from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer


class SoundService:
    def __init__(self) -> None:
        base_dir = Path(__file__).resolve().parent
        self._countdown_file = base_dir / "rock_scissors_paper.mp3"

        self._countdown_audio = QAudioOutput()
        self._countdown_audio.setVolume(1.0)
        self._countdown_player = QMediaPlayer()
        self._countdown_player.setAudioOutput(self._countdown_audio)

        if self._countdown_file.exists():
            self._countdown_player.setSource(QUrl.fromLocalFile(str(self._countdown_file)))

    def play_countdown(self) -> None:
        if not self._countdown_file.exists():
            return

        self._countdown_player.stop()
        self._countdown_player.setPosition(0)
        self._countdown_player.play()

    def play_win(self) -> None:
        # Reserved for a future dedicated victory clip.
        return

    def play_tie(self) -> None:
        # Reserved for a future dedicated tie clip.
        return
