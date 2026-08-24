from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from ui.main_window import RockPaperScissorsGame


def main() -> int:
    app = QApplication(sys.argv)
    game = RockPaperScissorsGame()
    game.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
