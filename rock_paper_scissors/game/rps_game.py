from __future__ import annotations

import random
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal


GESTURES = ("Rock", "Paper", "Scissors")


@dataclass
class RoundOutcome:
    round_number: int
    player_gesture: str
    computer_gesture: str
    result: str
    player_score: int
    computer_score: int

    @property
    def perfect_game(self) -> bool:
        return self.player_score == 5 and self.computer_score == 0 and self.round_number == 5


class RpsGame(QObject):
    round_changed = Signal(int, int, int)
    round_finished = Signal(object)
    game_finished = Signal(bool, int, int)
    reset_requested = Signal()

    def __init__(self, max_rounds: int = 5) -> None:
        super().__init__()
        self.max_rounds = max_rounds
        self.reset()

    def reset(self) -> None:
        self.current_round = 1
        self.player_score = 0
        self.computer_score = 0
        self.game_over = False
        self.reset_requested.emit()
        self.round_changed.emit(self.current_round, self.player_score, self.computer_score)

    def judge_winner(self, player: str, computer: str) -> str:
        if player == computer:
            return "tie"
        if (player == "Rock" and computer == "Scissors") or (
            player == "Scissors" and computer == "Paper"
        ) or (player == "Paper" and computer == "Rock"):
            return "win"
        return "lose"

    def resolve_round(self, player_gesture: str) -> RoundOutcome | None:
        if self.game_over or player_gesture not in GESTURES:
            return None

        computer_gesture = random.choice(GESTURES)
        result = self.judge_winner(player_gesture, computer_gesture)

        if result == "win":
            self.player_score += 1
        elif result == "lose":
            self.computer_score += 1

        outcome = RoundOutcome(
            round_number=self.current_round,
            player_gesture=player_gesture,
            computer_gesture=computer_gesture,
            result=result,
            player_score=self.player_score,
            computer_score=self.computer_score,
        )

        self.round_finished.emit(outcome)
        self.round_changed.emit(self.current_round, self.player_score, self.computer_score)

        if self.current_round >= self.max_rounds:
            self.game_over = True
            self.game_finished.emit(outcome.perfect_game, self.player_score, self.computer_score)
            return outcome

        self.current_round += 1
        self.round_changed.emit(self.current_round, self.player_score, self.computer_score)
        return outcome
