import argparse
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from visual.main_window import ShowcaseMainWindow


ROOT = Path(__file__).resolve().parents[1]
ICON_PATH = ROOT / "assets" / "icon.ico"


def parse_args():
    parser = argparse.ArgumentParser(description="AP002 left-hand showcase demo.")
    parser.add_argument(
        "--port",
        default=None,
        help="Optional RS485 port. If omitted, the app auto-detects.",
    )
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--hand-id", type=lambda value: int(value, 0), default=0x02)
    parser.add_argument(
        "--motion-profile",
        choices=("fixed", "adaptive"),
        default="fixed",
        help="Motion stepping profile. fixed keeps the current behavior; adaptive enables segmented error-based steps.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(ICON_PATH)))
    window = ShowcaseMainWindow(
        port=args.port, baudrate=args.baudrate, hand_id=args.hand_id, motion_profile=args.motion_profile
    )
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
