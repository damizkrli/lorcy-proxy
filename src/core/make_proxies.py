import json
import re
import io
import unicodedata
import requests
import sys
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont, ImageOps
from src.utils.env import DATASET_PATH, OUTPUT_DIR, ensure_dirs

# =========================
# Constantes impression
# =========================
DPI = 300
MM_PER_INCH = 25.4
CARD_W_MM, CARD_H_MM = 63.0, 88.0
CARD_W_PX = int((CARD_W_MM / MM_PER_INCH) * DPI)
CARD_H_PX = int((CARD_H_MM / MM_PER_INCH) * DPI)
A4_W_PX = int((210 / MM_PER_INCH) * DPI)
A4_H_PX = int((297 / MM_PER_INCH) * DPI)
COLS, ROWS = 3, 3
GUTTER = 30

# =========================
# Gestion du cache
# =========================
def get_cache_dir() -> Path:
    """Retourne un dossier de cache valide, compatible PyInstaller."""
    if getattr(sys, "frozen", False):
        base_dir = Path(tempfile.gettempdir()) / "Lorcy" / "cache_lorcana"
    else:
        base_dir = Path(__file__).resolve().parent / "cache_lorcana"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir

CACHE_DIR = get_cache_dir()

# =========================
# Outils dataset
# =========================
def normalize(txt: str) -> str:
    txt = txt.lower().strip()
    txt = txt.replace("–", "-").replace("—", "-").replace("−", "-")
    txt = "".join(c for c in unicodedata.normalize("NFD", txt) if unicodedata.category(c) != "Mn")
    return txt

CACHE_JSON = CACHE_DIR / "cards_cache.json"
from datetime import datetime

def load_dataset() -> List[Dict]:
    """Charge toutes les cartes depuis le JSON principal, avec gestion de cache."""
    if CACHE_JSON.exists():
        try:
            data = json.loads(CACHE_JSON.read_text(encoding="utf-8"))
            print(f"[DEBUG] Cache chargé ({len(data)} cartes)")
            return data
        except Exception:
            print("[DEBUG] Cache corrompu, rechargement du dataset complet.")

    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Fichier de dataset introuvable : {DATASET_PATH}")

    raw = DATASET_PATH.read_text(encoding="utf-8").strip()
    data = json.loads(raw)

    if "cards" not in data:
        raise ValueError("Le fichier JSON ne contient pas de clé 'cards'.")

    cards_section = data["cards"]
    cards: List[Dict] = []
    seen_ids = set()

    def add_card(c: Dict):
        """Ajoute une carte et explore ses sous-structures si besoin."""
        if not isinstance(c, dict):
            return
        cid = str(c.get("card_id") or c.get("id") or id(c))
        if cid not in seen_ids:
            cards.append(c)
            seen_ids.add(cid)
        for key, val in c.items():
            if isinstance(val, list):
                for sub in val:
                    if isinstance(sub, dict):
                        add_card(sub)
            elif isinstance(val, dict):
                add_card(val)

    if isinstance(cards_section, list):
        for c in cards_section:
            add_card(c)
    elif isinstance(cards_section, dict):
        for subset_name, subset in cards_section.items():
            if isinstance(subset, list):
                for c in subset:
                    add_card(c)
            elif isinstance(subset, dict):
                add_card(subset)
    else:
        raise ValueError("Format inattendu pour la clé 'cards'.")

    print(f"[DEBUG] {len(cards)} cartes détectées dans le dataset (avec variantes et promos)")

    try:
        CACHE_JSON.write_text(json.dumps(cards, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[DEBUG] Cache mis à jour : {CACHE_JSON}")
    except Exception as e:
        print(f"[DEBUG] Impossible d’écrire le cache : {e}")

    return cards

def get_card_name(card: Dict) -> str:
    n = card.get("name", "")
    s = card.get("subtitle")
    return f"{n} – {s}" if s else n

# ---- Index global (construit une seule fois) ----
_CARD_INDEX = None

def _build_card_index(cards: List[Dict]):
    """Prépare un index pour une recherche robuste, bilingue, sans faux positifs."""
    index = []
    for c in cards:
        name = c.get("name") or ""
        subtitle = c.get("subtitle") or ""
        full_title = f"{name} – {subtitle}" if subtitle else name

        kws = c.get("searchable_keywords") or []
        kws = [k for k in kws if isinstance(k, str)]

        def to_tokens(s: str) -> list[str]:
            s_norm = normalize(s)
            return [t for t in re.split(r"[^a-z0-9]+", s_norm) if t]

        title_tokens = to_tokens(full_title) + to_tokens(name) + to_tokens(subtitle)
        kw_tokens = []
        for k in kws:
            kw_tokens.extend(to_tokens(k))

        token_set = set(title_tokens + kw_tokens)
        full_title_norm = normalize(full_title)

        index.append({
            "card": c,
            "full_title_norm": full_title_norm,
            "token_set": token_set,
        })
    return index

def search_local(cards: List[Dict], q: str) -> List[Dict]:
    """Recherche stricte, bilingue et sans faux positifs."""
    global _CARD_INDEX
    if _CARD_INDEX is None:
        _CARD_INDEX = _build_card_index(cards)

    q_norm = normalize(q).strip()
    if not q_norm:
        return []

    q_tokens = [t for t in re.split(r"[^a-z0-9]+", q_norm) if t]
    if not q_tokens:
        return []

    def token_matches(query_tok: str, candidate_tok: str) -> bool:
        if query_tok == candidate_tok:
            return True
        return len(query_tok) >= 3 and candidate_tok.startswith(query_tok)

    def card_matches(entry) -> bool:
        tokens = entry["token_set"]
        for qt in q_tokens:
            if not any(token_matches(qt, ct) for ct in tokens):
                return False
        return True

    exact = [e["card"] for e in _CARD_INDEX if e["full_title_norm"] == q_norm]
    if exact:
        return exact

    hits = [e["card"] for e in _CARD_INDEX if card_matches(e)]

    seen = set()
    out = []
    for c in hits:
        cid = c.get("card_id") or id(c)
        if cid not in seen:
            out.append(c)
            seen.add(cid)
    return out

def pick_image_url(card: Dict[str, Any]) -> Optional[str]:
    vs = card.get("variants")
    if isinstance(vs, list):
        for v in vs:
            if isinstance(v, dict):
                u = v.get("detail_image_url")
                if u:
                    return u
    return card.get("thumbnail_url")

def fetch_image(url: str) -> Image.Image:
    safe = url.replace("://", "_").replace("/", "_").replace("?", "_").replace("=", "_")
    p = CACHE_DIR / f"{safe}.jpg"
    if p.exists():
        return Image.open(p).convert("RGB")
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    im = Image.open(io.BytesIO(r.content)).convert("RGB")
    im.save(p, "JPEG", quality=90)
    return im

def resize_and_gray(im: Image.Image) -> Image.Image:
    sw, sh = im.size
    scale = max(CARD_W_PX / sw, CARD_H_PX / sh)
    nw, nh = int(sw * scale), int(sh * scale)
    im = im.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - CARD_W_PX)//2, (nh - CARD_H_PX)//2
    im = im.crop((left, top, left + CARD_W_PX, top + CARD_H_PX))
    im = ImageOps.grayscale(im)
    im = ImageOps.autocontrast(im)
    return im.convert("RGB")

def text_size(draw, text, font):
    x0, y0, x1, y1 = draw.textbbox((0, 0), text, font=font)
    return (x1 - x0, y1 - y0)

def draw_wrapped(draw, text, font, x, y, max_w, line_gap=6, fill="black"):
    words = text.split()
    line = ""
    _, line_h = text_size(draw, "Hg", font)
    cy = y
    for w in words:
        probe = (line + " " + w) if line else w
        tw, _ = text_size(draw, probe, font)
        if tw <= max_w:
            line = probe
        else:
            draw.text((x, cy), line, fill=fill, font=font)
            cy += line_h + line_gap
            line = w
    if line:
        draw.text((x, cy), line, fill=fill, font=font)
        cy += line_h + line_gap
    return cy

def generate_text_card(card: Dict) -> Image.Image:
    W, H = CARD_W_PX, CARD_H_PX
    P = 26
    COST_BOX = 82
    LORE_COL_W = 56
    BORDER = 3

    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([(5, 5), (W - 5, H - 5)], radius=22, outline="#B0B8C0", width=BORDER)

    f_name = ImageFont.truetype("comicbd.ttf", 50)
    f_sub = ImageFont.truetype("comic.ttf", 36)
    f_type = ImageFont.truetype("comicbd.ttf", 32)
    f_ability = ImageFont.truetype("comicbd.ttf", 44)
    f_text = ImageFont.truetype("comic.ttf", 40)
    f_stat = ImageFont.truetype("comicbd.ttf", 46)
    f_cost = ImageFont.truetype("comicbd.ttf", 40)
    f_tag = ImageFont.truetype("comic.ttf", 32)

    name = card.get("name", "")
    subtitle = card.get("subtitle", "")
    ctype = card.get("type", "")
    rules_raw = (card.get("rules_text") or "").strip()

    ability_name, rules_text = "", rules_raw
    if "\n" in rules_raw:
        parts = [p.strip() for p in rules_raw.split("\n", 1)]
        ability_name, rules_text = parts[0], parts[1]

    strength = str(card.get("strength") or "")
    willpower = str(card.get("willpower") or "")
    ink_cost = str(card.get("ink_cost") or "?")
    inkable = bool(card.get("ink_convertible", False))
    lore_val = int(card.get("quest_value") or 0)

    tag_color = "#10B981" if inkable else "#FF0000"
    tag_txt = "ENCRABLE" if inkable else "NON-ENCRABLE"

    cost_x, cost_y = P, P
    d.rounded_rectangle([cost_x, cost_y, cost_x + COST_BOX, cost_y + COST_BOX], radius=6, outline=tag_color, width=4)
    tw, th = text_size(d, ink_cost, f_cost)
    d.text((cost_x + (COST_BOX - tw)//2, cost_y + (COST_BOX - th)//2), ink_cost, fill=tag_color, font=f_cost)
    d.text((cost_x + COST_BOX + 14, cost_y + 8), tag_txt, fill=tag_color, font=f_tag)

    title_y = cost_y + COST_BOX + 14
    d.text((P, title_y), name, fill="black", font=f_name)
    _, name_h = text_size(d, "Hg", f_name)
    sub_y = title_y + name_h - 6
    d.text((P, sub_y), subtitle, fill="black", font=f_sub)
    _, sub_h = text_size(d, "Hg", f_sub)

    sep_y = sub_y + sub_h + 8
    d.line((P, sep_y, W - P, sep_y), fill="#B0B8C0", width=2)

    type_y = sep_y + 8
    d.text((P, type_y), ctype, fill="black", font=f_type)
    _, type_h = text_size(d, "Hg", f_type)

    text_top = type_y + type_h + 18
    text_x = P
    text_max_w = W - 2 * P - LORE_COL_W

    if ability_name:
        d.text((text_x, text_top), ability_name, fill="black", font=f_ability)
        _, ability_h = text_size(d, "Hg", f_ability)
        text_top += ability_h + 8

    cy = draw_wrapped(d, rules_text, f_text, text_x, text_top, max_w=text_max_w, line_gap=8)

    if strength or willpower:
        stats = f"{strength}/{willpower}" if strength and willpower else (strength or willpower)
        tw, th = text_size(d, stats, f_stat)
        d.text((W - P - tw, H - P - th), stats, fill="black", font=f_stat)

    return img

def layout_pages(images: List[Image.Image]) -> List[Image.Image]:
    pages: List[Image.Image] = []
    total_w = COLS * CARD_W_PX + (COLS - 1) * GUTTER
    total_h = ROWS * CARD_H_PX + (ROWS - 1) * GUTTER
    start_x = (A4_W_PX - total_w)//2
    start_y = (A4_H_PX - total_h)//2
    page = Image.new("RGB", (A4_W_PX, A4_H_PX), "white")
    col = row = 0
    for i, card in enumerate(images):
        x = start_x + col * (CARD_W_PX + GUTTER)
        y = start_y + row * (CARD_H_PX + GUTTER)
        page.paste(card, (x, y))
        col += 1
        if col == COLS:
            col = 0
            row += 1
        if row == ROWS or i == len(images) - 1:
            pages.append(page)
            if i != len(images) - 1:
                page = Image.new("RGB", (A4_W_PX, A4_H_PX), "white")
                col = row = 0
    return pages

def generate_from_text(deck_text: str, deck_name: str, model="text", progress_callback=None):
    ensure_dirs()
    cards = load_dataset()

    for c in cards[:5]:
        name = c.get("name") or c.get("title") or "??"
        print(" -", name)

    lines = [l.strip() for l in deck_text.splitlines() if l.strip()]
    selected: List[Dict] = []

    for i, line in enumerate(lines, 1):
        if progress_callback:
            progress_callback(i / len(lines))
        qty, name_part = 1, line
        parts = line.split(" ", 1)
        if len(parts) == 2 and parts[0].isdigit():
            qty = int(parts[0])
            name_part = parts[1].strip()
        results = search_local(cards, name_part)
        if not results:
            continue
        selected.extend([results[0]] * qty)

    if not selected:
        raise ValueError("Aucune carte trouvée.")

    downloads = Path.home() / "Downloads"
    out_pdf = downloads / f"{deck_name}.pdf"

    images: List[Image.Image] = []

    for c in selected:
        url = pick_image_url(c)
        if model == "color" and url:
            im = fetch_image(url)
            sw, sh = im.size
            scale = max(CARD_W_PX / sw, CARD_H_PX / sh)
            im = im.resize((int(sw * scale), int(sh * scale)), Image.LANCZOS)
            left, top = (im.width - CARD_W_PX)//2, (im.height - CARD_H_PX)//2
            im = im.crop((left, top, left + CARD_W_PX, top + CARD_H_PX))
        elif model == "bw" and url:
            im = resize_and_gray(fetch_image(url))
        else:
            im = generate_text_card(c)
        images.append(im)

    pages = layout_pages(images)
    first, rest = pages[0], pages[1:]
    first.save(out_pdf, "PDF", resolution=DPI, save_all=True, append_images=rest)
    return out_pdf

if __name__ == "__main__":
    print("Utiliser via main.py")
