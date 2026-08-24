import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROHDEMO_VENDOR = ROOT / "vendor" / "rohdemo_common"
URDF_VENDOR = ROOT / "vendor" / "urdf_scripts"


def install_vendor_paths():
    for path in (ROHDEMO_VENDOR, URDF_VENDOR):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)
