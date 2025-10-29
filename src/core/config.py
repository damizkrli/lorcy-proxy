# src/core/config.py
from __future__ import annotations
import sys
from pathlib import Path

# Base du projet (mode script) = dossier parent de "src"
PROJECT_ROOT = Path(__file__).resolve().parents[2]

def _frozen_base() -> Path:
    # En mode PyInstaller, les fichiers sont extraits dans _MEIPASS
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) if base else PROJECT_ROOT

def resource_path(*parts: str) -> Path:
    """
    Retourne un chemin lisible à la fois en dev et en binaire PyInstaller.
    Exemple : resource_path('assets', 'icons', 'app.ico')
    """
    return _frozen_base().joinpath(*parts)

# -------------------------
# Métadonnées / Version
# -------------------------
APP_TITLE = "LORCY"
APP_AUTHOR = "Damien Carli"

# On LIT seulement la version (pas d'auto-incrément en binaire)
def _read_version() -> str:
    # On cherche d'abord à côté du binaire (PyInstaller), sinon au projet
    for candidate in (resource_path("version.txt"), PROJECT_ROOT / "version.txt"):
        try:
            txt = candidate.read_text(encoding="utf-8").strip()
            if txt:
                return f"v{txt}"
        except Exception:
            pass
    return "v0.1"

APP_VERSION = _read_version()

# -------------------------
# Thème / Couleurs UI
# -------------------------
PRIMARY_COLOR = "#4169E1"
BG_COLOR = "#F8FAFC"
TEXT_COLOR = "#111827"
BUTTON_GREEN = "#10B981"
BUTTON_RED = "#EF4444"
TEXT_BG = "#FFFFFF"

# -------------------------
# Dossiers de ressources
# -------------------------
ASSETS_DIR = resource_path("assets")
ICONS_DIR = ASSETS_DIR / "icons"
IMAGES_DIR = ASSETS_DIR / "images"
FONTS_DIR = ASSETS_DIR / "fonts"
