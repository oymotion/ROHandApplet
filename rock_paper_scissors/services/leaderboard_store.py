from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path


@dataclass
class LeaderboardEntry:
    player_id: str
    score: str
    created_at: str


class LeaderboardStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(__file__).resolve().parents[1] / "leaderboard.json"

    def load(self) -> list[LeaderboardEntry]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return [LeaderboardEntry(**item) for item in data]
        except Exception:
            return []

    def save(self, entries: list[LeaderboardEntry]) -> None:
        self.path.write_text(
            json.dumps([asdict(item) for item in entries], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add_perfect_game(self, player_id: str, score: str) -> None:
        entries = self.load()
        entries.insert(
            0,
            LeaderboardEntry(
                player_id=player_id.strip(),
                score=score,
                created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        self.save(entries[:10])
