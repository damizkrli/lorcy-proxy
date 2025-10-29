import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageTk

from src.core.make_proxies import generate_from_text, load_dataset
from src.core.config import (
    APP_TITLE,
    APP_VERSION,
    APP_AUTHOR,
    PRIMARY_COLOR,
    BG_COLOR,
    TEXT_COLOR,
    BUTTON_GREEN,
    BUTTON_RED,
    TEXT_BG,
    ICONS_DIR,
)


# ==========================================================
# BOUTON
# ==========================================================
class RoundedButton(tk.Canvas):
    def __init__(
        self,
        parent,
        text,
        command=None,
        bg="#10B981",
        fg="white",
        radius=8,
        padx=20,
        pady=8,
        font=("Segoe UI", 11, "bold"),
    ):
        super().__init__(parent, highlightthickness=0, bg=parent["bg"])
        self.command = command
        self.bg = bg
        self.fg = fg
        self.radius = radius
        self.padx = padx
        self.pady = pady
        self.font = font
        self.text = text
        self.id_text = None
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", lambda e: self.itemconfig("rect", fill=self._brighten(bg)))
        self.bind("<Leave>", lambda e: self.itemconfig("rect", fill=bg))
        self._draw_button()

    def _draw_button(self):
        width = 10 * len(self.text) + self.padx * 2
        height = 25 + self.pady * 2
        r = self.radius
        self.configure(width=width, height=height)
        self.create_rounded_rect(0, 0, width, height, r, fill=self.bg, outline="", tags="rect")
        self.id_text = self.create_text(width / 2, height / 2, text=self.text, fill=self.fg, font=self.font)

    def create_rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1
        ]
        return self.create_polygon(points, smooth=True, **kwargs)

    def _brighten(self, color):
        color = color.lstrip("#")
        r, g, b = [int(color[i:i + 2], 16) for i in (0, 2, 4)]
        r = min(r + 20, 255)
        g = min(g + 20, 255)
        b = min(b + 20, 255)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _on_click(self, event):
        if self.command:
            self.command()


# ==========================================================
# APPLICATION PRINCIPALE
# ==========================================================
class LorcanaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Lorcy – Proxy Generator")
        self.geometry("780x640")
        self.resizable(False, False)
        self.configure(bg=BG_COLOR)

        try:
            icon_path = ICONS_DIR / "app.ico"
            if icon_path.exists():
                self.iconbitmap(icon_path)
        except Exception:
            pass

        self._create_widgets()

    # ======================================================
    # CRÉATION DES WIDGETS
    # ======================================================
    def _create_widgets(self):
        title = tk.Label(
            self,
            text="Lorcy Proxy Generator",
            font=("Segoe UI", 18, "bold"),
            bg=BG_COLOR,
            fg=PRIMARY_COLOR,
        )
        title.pack(pady=(20, 5))

        # Champ Nom du deck
        deck_frame = tk.Frame(self, bg=BG_COLOR)
        deck_frame.pack(pady=(10, 0))
        tk.Label(
            deck_frame,
            text="Nom du deck :",
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left", padx=(0, 8))
        self.deckname_entry = tk.Entry(
            deck_frame,
            width=35,
            font=("Segoe UI", 10),
            bg=TEXT_BG,
            relief="flat",
            highlightthickness=2,
            highlightbackground="#CBD5E1",
            highlightcolor=PRIMARY_COLOR,
            justify="center",
        )
        self.deckname_entry.pack(side="left")
        deck_frame.pack(anchor="center")

        # Choix du modèle
        model_frame = tk.Frame(self, bg=BG_COLOR)
        model_frame.pack(pady=(15, 0))
        tk.Label(
            model_frame,
            text="Modèle :",
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left", padx=(0, 10))
        self.model_choice = tk.StringVar(value="text")
        ttk.Radiobutton(model_frame, text="Couleur", variable=self.model_choice, value="color").pack(side="left")
        ttk.Radiobutton(model_frame, text="Noir & Blanc", variable=self.model_choice, value="bw").pack(side="left", padx=10)
        ttk.Radiobutton(model_frame, text="Texte uniquement", variable=self.model_choice, value="text").pack(side="left")

        # Zone de texte principale
        text_frame = tk.Frame(self, bg=BG_COLOR)
        text_frame.pack(pady=(8, 15))
        self.text = tk.Text(
            text_frame,
            height=18,
            width=78,
            wrap="word",
            font=("Consolas", 10, "italic"),
            bg=TEXT_BG,
            fg=TEXT_COLOR,
            relief="flat",
            highlightthickness=1,
            bd=0,
        )
        self.text.pack()
        placeholder = (
            "Collez ici votre decklist\n"
            "4 Jasmine – Infiltrée pleine de ressource\n"
            "3 Capitaine Crochet – Duelliste aguerri\n"
            "..."
        )
        self.text.insert("1.0", placeholder)
        self.placeholder_text = placeholder
        self.placeholder_active = True
        self.text.bind("<FocusIn>", self._clear_placeholder)
        self.text.bind("<FocusOut>", self._restore_placeholder)
        self.text.bind("<Control-v>", self._paste_clipboard)
        self.text.bind("<Command-v>", self._paste_clipboard)

        # Barre de progression
        self.progress = ttk.Progressbar(self, orient="horizontal", length=400, mode="determinate")
        self.progress.pack_forget()

        # Boutons
        btn_frame = tk.Frame(self, bg=BG_COLOR)
        btn_frame.pack(pady=5)
        self.generate_btn = RoundedButton(
            btn_frame, text="Générer le PDF", bg=BUTTON_GREEN, fg="white", command=self.start_generation
        )
        self.generate_btn.grid(row=0, column=0, padx=20)
        self.reset_btn = RoundedButton(
            btn_frame, text="Vider le formulaire", bg=BUTTON_RED, fg="white", command=self.reset_fields
        )
        self.reset_btn.grid(row=0, column=1, padx=20)

        # Footer élégant et complet
        cards = load_dataset()
        today = datetime.now().strftime("%d %B %Y").capitalize()
        footer_text = (
            f"{APP_TITLE} {APP_VERSION}  •  {APP_AUTHOR}  "
            f"–  🧩 {len(cards):,} cartes chargées  •  {today}"
        ).replace(",", " ")

        footer = tk.Label(
            self,
            text=footer_text,
            bg=BG_COLOR,
            fg="#9CA3AF",
            font=("Segoe UI", 9, "italic"),
        )
        footer.pack(side="bottom", pady=10)

    # ======================================================
    # PLACEHOLDER MANAGEMENT
    # ======================================================
    def _clear_placeholder(self, event):
        if self.placeholder_active:
            self.text.delete("1.0", "end")
            self.text.configure(font=("Consolas", 10, "normal"))
            self.placeholder_active = False

    def _restore_placeholder(self, event):
        content = self.text.get("1.0", "end").strip()
        if not content:
            self.text.insert("1.0", self.placeholder_text)
            self.text.configure(font=("Consolas", 10, "italic"))
            self.placeholder_active = True

    # ======================================================
    # RÉINITIALISATION
    # ======================================================
    def reset_fields(self):
        self.text.delete("1.0", "end")
        self.text.insert("1.0", self.placeholder_text)
        self.text.configure(font=("Consolas", 10, "italic"))
        self.placeholder_active = True
        self.deckname_entry.delete(0, "end")
        self.progress.pack_forget()
        self.progress["value"] = 0
        self.deckname_entry.focus_set()

    # ======================================================
    # GÉNÉRATION PDF
    # ======================================================
    def start_generation(self):
        deck_text = self.text.get("1.0", "end").strip()
        if self.placeholder_active or not deck_text:
            messagebox.showwarning("Erreur", "Veuillez coller votre decklist.")
            return
        deck_name = self.deckname_entry.get().strip() or "proxies"
        model = self.model_choice.get()
        self.progress.pack(pady=(10, 20))
        self.progress["value"] = 0
        self.generate_btn.itemconfig(self.generate_btn.id_text, text="Génération…")
        threading.Thread(target=self.run_generation, args=(deck_text, deck_name, model), daemon=True).start()

    def run_generation(self, deck_text, deck_name, model):
        try:
            pdf_path = generate_from_text(deck_text, deck_name, model=model, progress_callback=self.update_progress)
            self.after(0, lambda: os.startfile(Path(pdf_path).parent))
        except Exception as e:
            err_msg = str(e)
            self.after(0, lambda msg=err_msg: messagebox.showerror("Erreur", msg))
        finally:
            self.after(0, lambda: self.generate_btn.itemconfig(self.generate_btn.id_text, text="Générer le PDF"))
            self.after(0, lambda: self.progress.pack_forget())
            self.after(0, lambda: self.progress.config(value=0))

    def update_progress(self, ratio):
        self.progress["value"] = ratio * 100

    # ======================================================
    # COLLER (CTRL+V)
    # ======================================================
    def _paste_clipboard(self, event=None):
        try:
            clip = self.clipboard_get()
            if self.placeholder_active:
                self._clear_placeholder(None)
            self.text.insert("insert", clip)
        except tk.TclError:
            pass
        return "break"
