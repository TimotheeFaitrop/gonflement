"""Choix du point (tache) où la déformation E est lue pour la courbe pression = f(E).

Fenêtre tkinter avec une figure matplotlib : photo_init gauche ou droite (ou, à défaut, vue de dessus en mm)
avec toutes les taches superposées. Le point choisi automatiquement (tache la plus proche du centre de la
zone initiale) est déjà sélectionné ; un clic sur une autre tache le remplace.

Usage :
    from Pycaso.point_gui import choisir_point
    res = choisir_point(fenetre_parent, pression, indice_actuel)
    # res = {"indice": colonne de X3d, "x": mm, "y": mm, "auto": bool}, ou None si annulé
"""

import tkinter as tk
from tkinter import ttk, messagebox

import matplotlib
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from Pycaso.retouche_class import _RC_SOMBRE
from Pycaso.style_gui import Style


def lire_image(chemin):
    """Image en niveaux de gris (tableau de flottants), ou None si elle est illisible."""
    a = None
    try:
        from PIL import Image
        a = np.asarray(Image.open(chemin))
    except Exception:
        try:
            import cv2
            a = cv2.imread(str(chemin), cv2.IMREAD_UNCHANGED)
        except Exception:
            a = None
    if a is None:
        return None
    a = np.asarray(a, dtype=float)
    return a[..., :3].mean(axis=-1) if a.ndim == 3 else a


def _orienter(pts, image):
    """Échange x et y si les positions ne tiennent dans l'image qu'ainsi (convention (ligne, colonne))."""
    ok = np.isfinite(pts).all(axis=1)
    if not ok.any():
        return pts
    h, w = image.shape
    x, y = pts[ok, 0], pts[ok, 1]
    if (x.max() > 1.05 * w or y.max() > 1.05 * h) and (y.max() <= 1.05 * w and x.max() <= 1.05 * h):
        return pts[:, ::-1]
    return pts


class ChoixPoint:
    """Fenêtre de choix du point de mesure (une tache parmi celles de X3d)."""

    RAYON_CLIC = 30                      # pixels d'écran : distance maximale d'un clic à la tache choisie
    C_TACHE, C_CHOIX, C_AUTO = "#4cc9f0", "#ff5c5c", "#ffd166"

    def __init__(self, parent, pression, indice=None):
        self.parent = parent
        d = pression._deformation()
        d.charger()                                    # exclusions, aberrants et sens de z comme le calcul
        self.x0, self.y0 = d.X[0], d.Y[0]
        self.valides = np.isfinite(self.x0) & np.isfinite(self.y0) & np.isfinite(d.Z[0])
        nb = len(self.x0)
        self.auto = pression.indice_centre(d)
        self.choix = indice if indice is not None and 0 <= indice < nb and self.valides[indice] else self.auto
        self.resultat = None
        self.remarques = []

        self.vues = {}                                 # nom : (positions (nb, 2), image ou None, titre)
        try:
            pixels = pression.pixels_taches(nb)
        except (OSError, ValueError, IndexError) as e:
            pixels = None
            self.remarques.append(f"positions en pixels indisponibles ({e})")
        if pixels is not None:
            for k, cote, nom in ((0, "L", "gauche"), (1, "R", "droite")):
                chemin = pression.chemin_photo_init(cote)
                if chemin is None:
                    self.remarques.append(f"photo_init {nom} introuvable")
                    continue
                image = lire_image(chemin)
                if image is None:
                    self.remarques.append(f"{chemin.name} illisible")
                    continue
                self.vues[f"Photo {nom}"] = (_orienter(pixels[k], image), image, chemin.name)
        self.vues["Dessus (mm)"] = (np.column_stack((self.x0, self.y0)), None, "Vue de dessus (état initial)")

    def ouvrir(self):
        """Ouvre la fenêtre (bloquant). Renvoie le choix, ou None si annulé."""
        with matplotlib.rc_context(_RC_SOMBRE):
            self.fen = Style.fenetre(self.parent, "Choix du point de mesure de E")
            self.fen.transient(self.parent)
            self.fen.grab_set()
            self._construire()
            self.fen.wait_window()
        return self.resultat

    # ----- construction -----

    def _construire(self):
        fen = self.fen
        fen.columnconfigure(0, weight=1)
        fen.rowconfigure(1, weight=1)
        haut = ttk.Frame(fen)
        haut.grid(row=0, column=0, sticky="w", padx=6, pady=(6, 0))
        self.var_vue = tk.StringVar(value=next(iter(self.vues)))
        for j, nom in enumerate(self.vues):
            ttk.Radiobutton(haut, text=nom, value=nom, variable=self.var_vue,
                            command=self.changer_vue).grid(row=0, column=j, padx=(0, 14))

        self.fig = Figure(figsize=(9, 7))
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=fen)
        self.canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        barre = ttk.Frame(fen)
        barre.grid(row=2, column=0, sticky="w", padx=6)
        self.toolbar = NavigationToolbar2Tk(self.canvas, barre, pack_toolbar=False)
        self.toolbar.grid(row=0, column=0)

        self.lbl = ttk.Label(fen, wraplength=820, justify="left")
        self.lbl.grid(row=3, column=0, sticky="w", padx=6, pady=(6, 0))
        ttk.Label(fen, foreground=Style.GRIS, wraplength=820, justify="left", text=(
            "Clic sur une tache = la choisir (cercle rouge). Cercle jaune pointillé : choix automatique. "
            "Zoom et déplacement : loupe et main de la barre d'outils (les désactiver pour cliquer).")
        ).grid(row=4, column=0, sticky="w", padx=6)
        if self.remarques:
            ttk.Label(fen, foreground=Style.ORANGE, wraplength=820, justify="left",
                      text="⚠ " + " ; ".join(self.remarques)).grid(row=5, column=0, sticky="w", padx=6)

        fb = ttk.Frame(fen)
        fb.grid(row=6, column=0, sticky="e", padx=6, pady=6)
        ttk.Button(fb, text="Point automatique", command=self.revenir_auto).grid(row=0, column=0, padx=4)
        ttk.Button(fb, text="Annuler", command=self.fen.destroy).grid(row=0, column=1, padx=4)
        ttk.Button(fb, text="OK", command=self.valider).grid(row=0, column=2, padx=4)
        fen.bind("<Return>", lambda _e: self.valider())
        fen.bind("<Escape>", lambda _e: self.fen.destroy())
        self.canvas.mpl_connect("button_press_event", self.clic)
        self.changer_vue()

    # ----- affichage -----

    def changer_vue(self):
        pts, image, titre = self.vues[self.var_vue.get()]
        ax = self.ax
        ax.clear()
        if image is not None:
            lo, hi = np.percentile(image, (1, 99.5))
            ax.imshow(image, cmap="gray", vmin=lo, vmax=hi)
            ax.set_autoscale_on(False)
            ax.set_xlabel("x (pixels)"); ax.set_ylabel("y (pixels)")
        else:
            ax.set_aspect("equal")
            ax.set_xlabel("x (mm)"); ax.set_ylabel("y (mm)")
        ax.set_title(titre, fontsize=10)
        self.pts = pts
        self.ok = self.valides & np.isfinite(pts).all(axis=1)
        ax.scatter(pts[self.ok, 0], pts[self.ok, 1], s=14, facecolors="none", edgecolors=self.C_TACHE,
                   linewidths=0.8)
        if self.ok[self.auto]:
            ax.scatter([pts[self.auto, 0]], [pts[self.auto, 1]], s=240, marker="o", facecolors="none",
                       edgecolors=self.C_AUTO, linestyle="--", linewidths=1.2, zorder=4)
        self.anneau = ax.scatter([], [], s=190, marker="o", facecolors="none", edgecolors=self.C_CHOIX,
                                 linewidths=2, zorder=5)
        self.croix = ax.scatter([], [], s=320, marker="+", color=self.C_CHOIX, linewidths=1.2, zorder=5)
        self.maj_choix()

    def maj_choix(self):
        j = self.choix
        pos = np.array([self.pts[j]]) if self.ok[j] else np.empty((0, 2))
        self.anneau.set_offsets(pos)
        self.croix.set_offsets(pos)
        texte = f"Tache {j} : x = {self.x0[j]:.4g} mm, y = {self.y0[j]:.4g} mm"
        if j == self.auto:
            texte += "   (choix automatique : la plus proche du centre de la zone initiale)"
        if not self.ok[j]:
            texte += "   (hors de cette vue)"
        self.lbl.configure(text=texte)
        self.canvas.draw_idle()

    # ----- actions -----

    def clic(self, event):
        mode = getattr(self.toolbar.mode, "value", self.toolbar.mode)
        if event.inaxes is not self.ax or event.button != 1 or mode:
            return
        idx = np.flatnonzero(self.ok)
        if not len(idx):
            return
        ecran = self.ax.transData.transform(self.pts[idx])
        d = np.hypot(ecran[:, 0] - event.x, ecran[:, 1] - event.y)
        k = int(np.argmin(d))
        if d[k] <= self.RAYON_CLIC:
            self.choix = int(idx[k])
            self.maj_choix()

    def revenir_auto(self):
        self.choix = self.auto
        self.maj_choix()

    def valider(self):
        j = self.choix
        self.resultat = {"indice": j, "x": float(self.x0[j]), "y": float(self.y0[j]), "auto": j == self.auto}
        self.fen.destroy()


def choisir_point(parent, pression, indice=None):
    """Ouvre la fenêtre de choix ; renvoie {"indice", "x", "y", "auto"} ou None (annulé ou erreur)."""
    try:
        return ChoixPoint(parent, pression, indice).ouvrir()
    except (OSError, ValueError) as e:
        messagebox.showerror("Choix du point", str(e), parent=parent)
        return None