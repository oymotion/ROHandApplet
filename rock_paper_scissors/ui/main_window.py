from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QFile, Qt, QTimer, Slot
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QLabel, QListWidget, QMainWindow, QMessageBox, QPushButton, QInputDialog, QVBoxLayout, QWidget

from game.rps_game import RpsGame
from hardware.roh_controller import RohController
from services.leaderboard_store import LeaderboardStore
from services.sound_service import SoundService
from ui.fireworks import FireworksOverlay
from vision.gesture_recognizer import GestureRecognizerThread


class RockPaperScissorsGame(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Rock Paper Scissors - vs Computer")
        self._apply_window_icon()

        self.camera_available = False
        self.phase = "idle"
        self.last_gesture = None
        self.gesture_stable_count = 0
        self.gesture_triggered = False
        self.waiting_for_reset = False

        self.game = RpsGame(max_rounds=5)
        self.roh = RohController()
        self.sound = SoundService()
        self.leaderboard = LeaderboardStore()

        self.status_timer = QTimer(self)
        self.status_timer.setSingleShot(True)
        self.status_timer.timeout.connect(self.reset_status_hint)

        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.advance_countdown)
        self.countdown_steps = ["3", "2", "1", "Rock Paper Scissors"]
        self.countdown_index = 0

        self.setup_ui()
        self.fireworks = FireworksOverlay(self.centralWidget())
        self.refresh_leaderboard()

        self.game.round_changed.connect(self.on_round_changed)
        self.game.game_finished.connect(self.on_game_finished, Qt.QueuedConnection)

        self.recognizer_thread = GestureRecognizerThread(0)
        self.recognizer_thread.frame_processed.connect(self.update_frame)
        self.recognizer_thread.camera_status.connect(self.handle_camera_status)
        self.recognizer_thread.start()

        self.roh.open_port()
        self.roh.set_neutral()
        self.start_round()

    def _apply_window_icon(self) -> None:
        icon_path = Path(__file__).with_name("icon.ico")
        if not icon_path.exists():
            return

        icon = QIcon(str(icon_path))
        if icon.isNull():
            return

        self.setWindowIcon(icon)

    def setup_ui(self) -> None:
        ui_path = Path(__file__).with_name("main_window.ui")
        loader = QUiLoader()
        ui_file = QFile(str(ui_path))
        if not ui_file.open(QFile.ReadOnly):
            raise RuntimeError(f"Unable to open UI file: {ui_path}")

        try:
            root_widget = loader.load(ui_file, self)
        finally:
            ui_file.close()

        if root_widget is None:
            raise RuntimeError(f"Unable to load UI file: {ui_path}")

        self.setCentralWidget(root_widget)
        self.setMinimumSize(root_widget.minimumSizeHint())
        self._bind_widgets(root_widget)
        self._apply_base_styles()

    def _bind_widgets(self, root_widget: QWidget) -> None:
        self.camera_status_label = self._require_widget(root_widget, "camera_status_label", QLabel)
        self.video_label = self._require_widget(root_widget, "video_label", QLabel)
        self.gesture_display = self._require_widget(root_widget, "gesture_display", QLabel)
        self.status_hint = self._require_widget(root_widget, "status_hint", QLabel)
        self.countdown_label = self._ensure_countdown_label(root_widget)
        self.round_label = self._require_widget(root_widget, "round_label", QLabel)
        self.player_score_label = self._require_widget(root_widget, "player_score_label", QLabel)
        self.computer_score_label = self._require_widget(root_widget, "computer_score_label", QLabel)
        self.player_choice_display = self._require_widget(root_widget, "player_choice_display", QLabel)
        self.computer_choice_display = self._require_widget(root_widget, "computer_choice_display", QLabel)
        self.result_label = self._require_widget(root_widget, "result_label", QLabel)
        self.leaderboard_list = self._require_widget(root_widget, "leaderboard_list", QListWidget)
        self.reset_btn = self._require_widget(root_widget, "reset_btn", QPushButton)
        self.reset_btn.clicked.connect(self.reset_game)

    def _require_widget(self, root_widget: QWidget, name: str, widget_type):
        widget = root_widget.findChild(widget_type, name)
        if widget is None:
            raise RuntimeError(f"Missing widget '{name}' in main_window.ui")
        return widget

    def _find_widget(self, root_widget: QWidget, name: str, widget_type):
        return root_widget.findChild(widget_type, name)

    def _ensure_countdown_label(self, root_widget: QWidget) -> QLabel:
        countdown_label = self._find_widget(root_widget, "countdown_label", QLabel)
        if countdown_label is not None:
            return countdown_label

        gesture_frame = self._require_widget(root_widget, "gesture_frame", QWidget)
        gesture_layout = gesture_frame.layout()
        if not isinstance(gesture_layout, QVBoxLayout):
            raise RuntimeError("gesture_frame must use a vertical layout in main_window.ui")

        countdown_label = QLabel("")
        countdown_label.setObjectName("countdown_label")
        countdown_label.setAlignment(Qt.AlignCenter)
        gesture_layout.addWidget(countdown_label)
        return countdown_label

    def _apply_base_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow { background-color: #1a1a1a; color: #fff; }
            QWidget#RockPaperScissorsForm { background-color: #1a1a1a; color: #fff; }
            QLabel#camera_status_label { color: #4CAF50; font-size: 14px; font-weight: bold; }
            QLabel#video_label {
                background-color: #2b2b2b;
                border: 2px solid #555;
                color: #bbb;
            }
            QFrame#gesture_frame,
            QFrame#round_frame,
            QFrame#choice_frame {
                background-color: #2a2a2a;
                border-radius: 10px;
            }
            QFrame#score_frame {
                background-color: #1e3a5f;
                border-radius: 15px;
            }
            QFrame#player_panel {
                background-color: #244675;
                border-radius: 12px;
            }
            QFrame#computer_panel {
                background-color: #4a2f2f;
                border-radius: 12px;
            }
            QFrame#leaderboard_frame {
                background-color: #202020;
                border-radius: 10px;
            }
            QLabel#title_label {
                font-size: 28px;
                font-weight: bold;
                color: #FFD700;
            }
            QLabel#round_label,
            QLabel#score_title_label,
            QLabel#leaderboard_title_label,
            QLabel#player_label,
            QLabel#computer_label {
                color: #FFFFFF;
                font-weight: bold;
            }
            QLabel#round_label {
                font-size: 18px;
            }
            QLabel#score_title_label,
            QLabel#leaderboard_title_label {
                font-size: 16px;
            }
            QLabel#player_label,
            QLabel#computer_label {
                font-size: 14px;
            }
            QLabel#player_score_label,
            QLabel#computer_score_label {
                color: #FFFFFF;
                font-size: 34px;
                font-weight: bold;
            }
            QLabel#player_choice_display,
            QLabel#computer_choice_display {
                font-size: 48px;
            }
            QLabel#vs_label,
            QLabel#vs_small_label {
                color: #FFD700;
                font-weight: bold;
            }
            QLabel#vs_label {
                font-size: 18px;
            }
            QLabel#vs_small_label {
                font-size: 20px;
            }
            QLabel#gesture_title_label {
                color: #ccc;
                font-size: 14px;
                font-weight: bold;
            }
            QLabel#gesture_display {
                color: #4CAF50;
                font-size: 28px;
                font-weight: bold;
            }
            QLabel#status_hint,
            QLabel#score_hint_label {
                font-size: 12px;
            }
            QLabel#status_hint {
                color: #FFD700;
            }
            QLabel#score_hint_label {
                color: #C8D6E5;
            }
            QLabel#countdown_label {
                color: #FFFFFF;
                font-size: 36px;
                font-weight: bold;
            }
            QLabel#result_label {
                font-size: 24px;
                font-weight: bold;
                color: #FFD700;
            }
            QListWidget#leaderboard_list {
                background-color: #111;
                color: #ddd;
                border: none;
            }
            QPushButton#reset_btn {
                background-color: #4CAF50;
                color: white;
                font-size: 16px;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 8px;
            }
            QPushButton#reset_btn:hover {
                background-color: #45a049;
            }
            """
        )

    def refresh_leaderboard(self) -> None:
        self.leaderboard_list.clear()
        entries = self.leaderboard.load()
        if not entries:
            self.leaderboard_list.addItem("No perfect 5:0 record yet")
            return
        for entry in entries:
            self.leaderboard_list.addItem(f"{entry.player_id}  |  {entry.score}  |  {entry.created_at}")

    @Slot(int, int, int)
    def on_round_changed(self, round_number: int, player_score: int, computer_score: int) -> None:
        self.round_label.setText(f"Round {round_number} / {self.game.max_rounds}")
        self.player_score_label.setText(str(player_score))
        self.computer_score_label.setText(str(computer_score))

    @Slot(bool, str)
    def handle_camera_status(self, success: bool, message: str) -> None:
        self.camera_available = success
        prefix = "OK" if success else "ERR"
        self.camera_status_label.setText(f"{prefix} {message}")
        self.camera_status_label.setStyleSheet(
            "color: #4CAF50; font-size: 14px; font-weight: bold;"
            if success
            else "color: #FF6B6B; font-size: 14px; font-weight: bold;"
        )
        if not success:
            self.video_label.setText("No camera detected\nPlease check connection")

    @Slot(np.ndarray, str)
    def update_frame(self, frame: np.ndarray, gesture: str) -> None:
        if not self.camera_available:
            return

        h, w, ch = frame.shape
        qt_image = QImage(frame.data, w, h, ch * w, QImage.Format_BGR888)
        self.video_label.setPixmap(
            QPixmap.fromImage(qt_image).scaled(
                self.video_label.width(),
                self.video_label.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )
        self.gesture_display.setText(gesture)

        if self.phase != "listening" or self.game.game_over:
            return

        if gesture == "Scissors (spread fingers)":
            self.status_hint.setText("Please spread your index and middle fingers")
            self.status_hint.setStyleSheet("color: #FF6B6B; font-size: 12px; font-weight: bold;")
            self.last_gesture = None
            self.gesture_stable_count = 0
            self.gesture_triggered = False
            return

        if gesture not in ("Rock", "Paper", "Scissors"):
            self.last_gesture = None
            self.gesture_stable_count = 0
            self.gesture_triggered = False
            return

        if gesture != self.last_gesture:
            self.last_gesture = gesture
            self.gesture_stable_count = 0
            self.gesture_triggered = False
            self.status_hint.setText(f"Detected {gesture}, hold...")
            self.status_hint.setStyleSheet("color: #4FC3F7; font-size: 12px;")

        if self.gesture_triggered or self.waiting_for_reset:
            return

        self.gesture_stable_count += 1
        if self.gesture_stable_count < 3:
            progress = "o" * self.gesture_stable_count + "." * (3 - self.gesture_stable_count)
            self.status_hint.setText(f"Stabilizing [{progress}]")
            self.status_hint.setStyleSheet("color: #FFD700; font-size: 12px;")
            return

        self.gesture_triggered = True
        self.waiting_for_reset = True
        self.phase = "resolving"
        self.countdown_label.setText("")
        self.status_hint.setText(f"Recognized: {gesture}")
        self.status_hint.setStyleSheet("color: #4CAF50; font-size: 12px; font-weight: bold;")
        QTimer.singleShot(350, lambda g=gesture: self.play_round(g))

    def start_round(self) -> None:
        if self.game.game_over:
            return
        self.phase = "countdown"
        self.countdown_index = 0
        self.countdown_label.setText(self.countdown_steps[self.countdown_index])
        self.status_hint.setText("Get ready")
        self.status_hint.setStyleSheet("color: #FFD700; font-size: 12px;")
        self.sound.play_countdown()
        self.countdown_timer.start(650)
        self.roh.set_neutral()

    def advance_countdown(self) -> None:
        self.countdown_index += 1
        if self.countdown_index < len(self.countdown_steps):
            self.countdown_label.setText(self.countdown_steps[self.countdown_index])
            return

        self.countdown_timer.stop()
        self.countdown_label.setText("")
        self.phase = "listening"
        self.last_gesture = None
        self.gesture_stable_count = 0
        self.gesture_triggered = False
        self.waiting_for_reset = False
        self.status_hint.setText("Hold gesture for 3 stable frames")
        self.status_hint.setStyleSheet("color: #FFD700; font-size: 12px;")

    def play_round(self, player_gesture: str) -> None:
        outcome = self.game.resolve_round(player_gesture)
        if outcome is None:
            return

        gesture_emoji = {
            "Rock": "\u270a",
            "Scissors": "\u270c",
            "Paper": "\u270b",
        }
        self.player_choice_display.setText(gesture_emoji.get(outcome.player_gesture, "?"))
        self.computer_choice_display.setText(gesture_emoji.get(outcome.computer_gesture, "?"))

        self.roh.show(outcome.computer_gesture)

        if outcome.result == "win":
            self.result_label.setText("You won this round!")
            self.result_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #4CAF50;")
            self.sound.play_win()
        elif outcome.result == "lose":
            self.result_label.setText("Computer won this round!")
            self.result_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #FF6B6B;")
        else:
            self.result_label.setText("It's a tie!")
            self.result_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #FFD700;")
            self.sound.play_tie()

        self.status_hint.setText("Move complete")
        self.status_hint.setStyleSheet("color: #FFD700; font-size: 12px;")
        self.status_timer.start(1200)
        QTimer.singleShot(900, self.roh.set_neutral)

        if not self.game.game_over:
            QTimer.singleShot(1400, self.start_round)

        self.phase = "idle"

    @Slot(bool, int, int)
    def on_game_finished(self, perfect: bool, player_score: int, computer_score: int) -> None:
        QTimer.singleShot(1100, lambda: self.finish_game(perfect, player_score, computer_score))

    def finish_game(self, perfect: bool, player_score: int, computer_score: int) -> None:
        self.roh.set_neutral()
        if perfect:
            self.fireworks.start()
            player_id, ok = QInputDialog.getText(self, "Perfect Game", "Enter your ID:")
            if ok and player_id.strip():
                self.leaderboard.add_perfect_game(player_id.strip(), f"{player_score}:{computer_score}")
                self.refresh_leaderboard()
            QMessageBox.information(self, "Victory", "Perfect 5:0 win!")
        else:
            QMessageBox.information(self, "Game Over", f"Final Score: {player_score} : {computer_score}")

        self.result_label.setText("Game over, click New Game")
        self.result_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #FFD700;")
        self.status_hint.setText("Game over")
        self.status_hint.setStyleSheet("color: #FF6B6B; font-size: 12px; font-weight: bold;")

    def reset_status_hint(self) -> None:
        if not self.game.game_over:
            self.status_hint.setText("Hold gesture for 3 stable frames")
            self.status_hint.setStyleSheet("color: #FFD700; font-size: 12px;")

    def reset_game(self) -> None:
        self.countdown_timer.stop()
        self.status_timer.stop()
        self.fireworks.stop()
        self.game.reset()
        self.phase = "idle"
        self.last_gesture = None
        self.gesture_stable_count = 0
        self.gesture_triggered = False
        self.waiting_for_reset = False
        self.round_label.setText("Round 1 / 5")
        self.player_score_label.setText("0")
        self.computer_score_label.setText("0")
        self.player_choice_display.setText("?")
        self.computer_choice_display.setText("?")
        self.result_label.setText("Make your move...")
        self.result_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #FFD700;")
        self.gesture_display.setText("Waiting...")
        self.countdown_label.setText("")
        self.status_hint.setText("Hold gesture for 3 stable frames")
        self.status_hint.setStyleSheet("color: #FFD700; font-size: 12px;")
        self.roh.set_neutral()
        self.start_round()

    def closeEvent(self, event) -> None:
        self.countdown_timer.stop()
        self.status_timer.stop()
        self.fireworks.stop()
        self.recognizer_thread.stop()
        self.roh.close_port()
        event.accept()
