"""Style commun des interfaces tkinter de Pycaso : thème sombre bleu nuit (travail le soir).

Usage dans une interface :
    from Pycaso.style_gui import Style
    root = tk.Tk()
    Style.appliquer(root)                       # à faire juste après tk.Tk()
    ttk.Label(f, text="aide", foreground=Style.GRIS)
    ttk.Label(f, text="✔ trouvé", foreground=Style.VERT)
    fen = tk.Toplevel(root, background=Style.FOND)

Pour changer l'apparence de toutes les interfaces, il suffit de modifier les couleurs ci-dessous.
"""
import tkinter as tk
from tkinter import ttk


class Style:
    """Palette et application du thème (ttk 'clam') à une fenêtre et à toutes ses fenêtres filles."""

    # --- palette ---
    FOND = "#1b2433"          # fond des fenêtres
    CHAMP = "#26324a"         # fond des champs de saisie et des listes
    BORD = "#3a4a66"          # bordures
    TEXTE = "#d6deeb"         # texte principal
    TEXTE_NON_COCHE = "#b3bfd1"   # libellé d'une case non cochée
    TITRE = "#9fc3ff"         # titres des cadres
    GRIS = "#8a9bb5"          # texte d'aide
    INACTIF = "#56657e"       # texte des éléments désactivés
    ACCENT = "#3d7bd9"        # cases cochées, sélection, bouton enfoncé
    BOUTON = "#2c3b57"        # fond des boutons
    SURVOL = "#36507a"        # bouton survolé
    # messages ✔ / ⚠ / ✘ (éclaircis pour rester lisibles sur fond sombre)
    VERT, ORANGE, ROUGE = "#7cc68a", "#f0a35e", "#f07878"

    PAD = {"padx": 6, "pady": 3}  # marges habituelles autour des widgets

    @classmethod
    def appliquer(cls, root):
        """Applique le thème à root (tk.Tk ou tk.Toplevel) et à tout ce qui sera créé dedans."""
        root.configure(background=cls.FOND)
        # widgets tk classiques : listes des Combobox, boîtes de message, explorateur de dossiers
        for cle, val in (("*Background", cls.FOND), ("*Foreground", cls.TEXTE),
                         ("*selectBackground", cls.ACCENT), ("*selectForeground", "white"),
                         ("*insertBackground", cls.TEXTE), ("*activeBackground", cls.BOUTON),
                         ("*activeForeground", cls.TEXTE), ("*highlightBackground", cls.FOND),
                         ("*highlightColor", cls.ACCENT), ("*troughColor", cls.CHAMP),
                         ("*Entry.Background", cls.CHAMP), ("*Listbox.Background", cls.CHAMP),
                         ("*TCombobox*Listbox.background", cls.CHAMP),
                         ("*TCombobox*Listbox.foreground", cls.TEXTE),
                         ("*TCombobox*Listbox.selectBackground", cls.ACCENT),
                         ("*TCombobox*Listbox.selectForeground", "white")):
            root.option_add(cle, val)

        s = ttk.Style(root)
        s.theme_use("clam")
        s.configure(".", background=cls.FOND, foreground=cls.TEXTE, fieldbackground=cls.CHAMP,
                    bordercolor=cls.BORD, lightcolor=cls.FOND, darkcolor=cls.FOND, troughcolor=cls.CHAMP,
                    selectbackground=cls.ACCENT, selectforeground="white", insertcolor=cls.TEXTE,
                    focuscolor=cls.ACCENT)
        s.map(".", foreground=[("disabled", cls.INACTIF)])
        s.configure("TLabelframe", background=cls.FOND, bordercolor=cls.BORD,
                    lightcolor=cls.FOND, darkcolor=cls.FOND)
        s.configure("TLabelframe.Label", background=cls.FOND, foreground=cls.TITRE)
        s.configure("TButton", background=cls.BOUTON, foreground=cls.TEXTE, bordercolor=cls.BORD,
                    lightcolor=cls.BOUTON, darkcolor=cls.BOUTON, padding=(8, 3))
        s.map("TButton", background=[("disabled", cls.FOND), ("pressed", cls.ACCENT), ("active", cls.SURVOL)],
              foreground=[("disabled", cls.INACTIF)])
        for w in ("TEntry", "TCombobox", "TSpinbox"):
            s.configure(w, fieldbackground=cls.CHAMP, foreground=cls.TEXTE, background=cls.BOUTON,
                        bordercolor=cls.BORD, lightcolor=cls.CHAMP, darkcolor=cls.CHAMP, arrowcolor=cls.TEXTE)
            s.map(w, fieldbackground=[("disabled", cls.FOND), ("readonly", cls.CHAMP)],
                  foreground=[("disabled", cls.INACTIF)], bordercolor=[("focus", cls.ACCENT)],
                  lightcolor=[("focus", cls.ACCENT)], arrowcolor=[("disabled", cls.INACTIF)])
        for w in ("TCheckbutton", "TRadiobutton"):
            s.configure(w, background=cls.FOND, foreground=cls.TEXTE, indicatorsize=15,
                        indicatormargin=(2, 2, 8, 2), indicatorbackground=cls.CHAMP,
                        indicatorforeground="white", upperbordercolor=cls.BORD, lowerbordercolor=cls.BORD)
            s.map(w, background=[("active", cls.FOND)],
                  indicatorbackground=[("disabled", cls.FOND), ("pressed", cls.SURVOL), ("selected", cls.ACCENT)],
                  foreground=[("disabled", cls.INACTIF), ("!selected", cls.TEXTE_NON_COCHE),
                              ("selected", cls.TEXTE)])
        s.configure("TScrollbar", background=cls.BOUTON, troughcolor=cls.FOND, bordercolor=cls.FOND,
                    arrowcolor=cls.TEXTE, lightcolor=cls.BOUTON, darkcolor=cls.BOUTON, gripcount=0)
        s.map("TScrollbar", background=[("disabled", cls.FOND), ("pressed", cls.ACCENT), ("active", cls.SURVOL)],
              arrowcolor=[("disabled", cls.INACTIF)])
        return s

    @classmethod
    def fenetre(cls, parent, titre):
        """tk.Toplevel au fond du thème (fenêtres secondaires)."""
        fen = tk.Toplevel(parent, background=cls.FOND)
        fen.title(titre)
        return fen