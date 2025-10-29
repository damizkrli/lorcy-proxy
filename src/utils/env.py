import sys
from pathlib import Path

def get_base_dir() -> Path:
    """Retourne le dossier racine du projet, compatible PyInstaller."""
    if getattr(sys, "frozen", False):
        # Exécution depuis le .exe (PyInstaller)
        return Path(sys._MEIPASS)
    else:
        # Exécution depuis le code source
        return Path(__file__).resolve().parent.parent

BASE_DIR = get_base_dir()
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = BASE_DIR / "cache_lorcana"

DATASET_PATH = DATA_DIR / "full.json"
OUTPUT_DIR = Path.home() / "Downloads"

def ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
