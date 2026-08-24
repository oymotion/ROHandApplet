from dataclasses import dataclass, field
from typing import Dict


PARTS = ("thumb", "index", "middle", "ring", "little", "palm")


@dataclass
class PressureFrame:
    timestamp: float = 0.0
    scores: Dict[str, float] = field(
        default_factory=lambda: {name: 0.0 for name in PARTS}
    )

    def normalized(self, scale: float = 1000.0) -> Dict[str, float]:
        return {name: max(0.0, min(1.0, value / scale)) for name, value in self.scores.items()}
