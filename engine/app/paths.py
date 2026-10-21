import sys
from pathlib import Path

# PyInstaller onedir puts bundled data under sys._MEIPASS; in dev use the package folder.
BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
DATA = BASE / "app" / "data"
