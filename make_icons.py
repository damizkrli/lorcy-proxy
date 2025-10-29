from pathlib import Path
from PIL import Image, ImageDraw

# ==========================================================
# Répertoire de sortie
# ==========================================================
OUT_DIR = Path(r"C:\Users\damie\Documents\lorcana-proxy\assets\icons")
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================================
# Icône : ENCRABLE (carré vert)
# ==========================================================
def make_inkable_icon():
    size = 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    margin = 60
    color = "#10B981"  # vert Lorcana
    d.rectangle([margin, margin, size - margin, size - margin],
                outline=color, width=40)
    img.save(OUT_DIR / "inkable.png", "PNG")
    print("✅ inkable.png (carré vert) créé")


# ==========================================================
# Icône : NON-ENCRABLE (cercle rouge)
# ==========================================================
def make_not_inkable_icon():
    size = 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    margin = 40
    color = "#FF0000"  # rouge
    d.ellipse([margin, margin, size - margin, size - margin],
              outline=color, width=40)
    img.save(OUT_DIR / "not_inkable.png", "PNG")
    print("✅ not_inkable.png (cercle rouge) créé")


# ==========================================================
# Point d’entrée
# ==========================================================
if __name__ == "__main__":
    make_inkable_icon()
    make_not_inkable_icon()
    print(f"\nIcônes générées dans : {OUT_DIR}")
