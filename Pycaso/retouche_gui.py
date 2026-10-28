"""Interface d'exclusion manuelle de taches : choix de la reconstruction, puis sélection à la souris.

Usage depuis un script placé à côté du dossier Pycaso/ :
    from Pycaso.selection_gui import run_selection_gui
    run_selection_gui()

À lancer après la reconstruction ; les taches exclues sont retirées ensuite par la déformation
et l'anisotropie (option « Retirer les taches exclues à la main »).
"""

import os
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox, filedialog

from Pycaso.reconstruction_class import Detect3D
from Pycaso.retouche_class import (EditeurExclusions, ExclusionsTaches, FICHIER_CORRECTION, FICHIERS_3D,
                                    SOUS_DOSSIER_RECONSTRUCTION)


# ----- outils tkinter (style, explorateur de dossiers) -----

_PAD = {"padx": 6, "pady": 3}
_VERT, _ORANGE, _ROUGE = "#2e7d32", "#e65100", "#c62828"


def _appliquer_style(root):
    """Thème 'clam' + cases à cocher lisibles (vert avec coche si cochée)."""
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TCheckbutton", indicatorsize=16, indicatormargin=(2, 2, 8, 2),
                    indicatorbackground="white", indicatorforeground="white",
                    upperbordercolor="#555555", lowerbordercolor="#555555")
    style.map("TCheckbutton",
              indicatorbackground=[("disabled", "#dddddd"),
                                   ("pressed", "#a5d6a7"),
                                   ("selected", "#2e7d32")],
              indicatorforeground=[("selected", "white")],
              foreground=[("disabled", "#aaaaaa"), ("selected", "black"),
                          ("!selected", "#666666")])


# ----- dossiers -----

def _dossier_depart(prefere, secours="."):
    """prefere s'il existe ; sinon le premier dossier existant en remontant depuis secours."""
    d = os.path.abspath(os.path.expanduser(prefere))
    if os.path.isdir(d):
        return d
    d = os.path.abspath(secours or ".")
    while not os.path.isdir(d) and os.path.dirname(d) != d:
        d = os.path.dirname(d)
    return d


def _parcourir_essai(parent, var, prefere, titre="Dossier de l'essai (ex. date/essai1)"):
    """Explorateur de dossiers commençant dans prefere ; écrit le choix dans var (StringVar)."""
    d = filedialog.askdirectory(initialdir=_dossier_depart(prefere, var.get().strip()),
                                parent=parent, title=titre)
    if d:
        try:
            rel = os.path.relpath(d)
        except ValueError:                 # Windows : autre lecteur que le dossier d'exécution
            rel = ".."
        var.set(d if rel.startswith("..") else rel)


class SelectionGUI:
    """Fenêtre de choix de la reconstruction, puis ouverture de l'éditeur d'exclusions."""

    SENS = {"auto (dôme vers le haut)": None, "inverser": True, "garder": False}
    QUANTITES = {"Uz : z − z(image de référence)": "Uz", "z": "z"}
    PAD = _PAD

    def __init__(self):
        self.result = None
        self.root = tk.Tk()
        self.root.title("Exclusion manuelle de taches")
        self.root.resizable(False, False)
        _appliquer_style(self.root)
        date = time.strftime("%Y_%m_%d")
        self.v = {
            "date": tk.StringVar(value=date),
            "dossier_essai": tk.StringVar(value=Detect3D.chemin_par_defaut(date)),
            "source": tk.StringVar(),
            "image": tk.StringVar(value="-1"),
            "image_reference": tk.StringVar(value="0"),
            "quantite": tk.StringVar(value=list(self.QUANTITES)[0]),
            "sens_z": tk.StringVar(value=list(self.SENS)[0]),
        }
        self._construire()
        self._chemin_auto = self.v["dossier_essai"].get()
        self.v["date"].trace_add("write", self._suivre_date)
        for k in ("date", "dossier_essai"):
            self.v[k].trace_add("write", self._maj_sources)
        self.v["source"].trace_add("write", self._maj)
        self._maj_sources()

    def ask(self):
        """Affiche la fenêtre ; renvoie un EditeurExclusions prêt à ouvrir, ou None si annulé."""
        self.root.mainloop()
        return self.result

    # ----- construction -----

    def _ligne(self, f, ligne, texte, widget, aide=""):
        ttk.Label(f, text=texte).grid(row=ligne, column=0, sticky="w", **self.PAD)
        widget.grid(row=ligne, column=1, sticky="w", **self.PAD)
        lbl = ttk.Label(f, text=aide, foreground="gray")
        lbl.grid(row=ligne, column=2, sticky="w", **self.PAD)
        return lbl

    def _construire(self):
        pad = self.PAD
        f = ttk.LabelFrame(self.root, text="Reconstruction")
        f.grid(row=0, column=0, sticky="ew", **pad)
        self._ligne(f, 0, "Date (AAAA_MM_JJ)", ttk.Entry(f, textvariable=self.v["date"], width=16))
        ttk.Label(f, text="Dossier de l'essai").grid(row=1, column=0, sticky="w", **pad)
        l = ttk.Frame(f)
        l.grid(row=1, column=1, columnspan=2, sticky="w", **pad)
        ttk.Entry(l, textvariable=self.v["dossier_essai"], width=52).grid(row=0, column=0)
        ttk.Button(l, text="…", width=3, command=self._parcourir).grid(row=0, column=1, padx=(4, 0))
        self.cb_source = ttk.Combobox(f, textvariable=self.v["source"], state="readonly", width=20)
        self.lbl_source = self._ligne(f, 2, "Reconstruction", self.cb_source)
        self.lbl_exclues = ttk.Label(f, wraplength=600, justify="left")
        self.lbl_exclues.grid(row=3, column=0, columnspan=3, sticky="w", **pad)

        f = ttk.LabelFrame(self.root, text="Affichage (modifiable ensuite dans la fenêtre)")
        f.grid(row=1, column=0, sticky="ew", **pad)
        self._ligne(f, 0, "Image affichée au départ", ttk.Entry(f, textvariable=self.v["image"], width=10),
                    "-1 = dernière (curseur ou flèches du clavier ensuite)")
        self._ligne(f, 1, "Valeur verticale", ttk.Combobox(f, textvariable=self.v["quantite"], state="readonly",
                                                            values=list(self.QUANTITES), width=28))
        self._ligne(f, 2, "Image de référence", ttk.Entry(f, textvariable=self.v["image_reference"], width=10),
                    "pour Uz (source corrigée : 0 = état plat)")
        self._ligne(f, 3, "Sens de z", ttk.Combobox(f, textvariable=self.v["sens_z"], state="readonly",
                                                     values=list(self.SENS), width=28))
        ttk.Label(f, foreground="gray", justify="left", text=(
            "Dans la fenêtre : clic sur une tache = l'exclure / la rétablir ; glisser = lasso. "
            "Les taches exclues le sont sur toutes les images.\nZoom : loupe de la barre d'outils "
            "(la désactiver pour sélectionner). Clavier : flèches gauche/droite = image, u = annuler, e = enregistrer.")
        ).grid(row=5, column=0, columnspan=3, sticky="w", **pad)

        fb = ttk.Frame(self.root)
        fb.grid(row=2, column=0, sticky="e", **pad)
        ttk.Button(fb, text="Annuler", command=self.root.destroy).grid(row=0, column=0, **pad)
        ttk.Button(fb, text="Ouvrir", command=self._on_ok).grid(row=0, column=1, **pad)
        self.root.bind("<Return>", lambda _e: self._on_ok())
        self.root.bind("<Escape>", lambda _e: self.root.destroy())

    # ----- mises à jour -----

    def _suivre_date(self, *_):
        if self.v["dossier_essai"].get() == self._chemin_auto:
            self._chemin_auto = Detect3D.chemin_par_defaut(self.v["date"].get().strip())
            self.v["dossier_essai"].set(self._chemin_auto)

    def _parcourir(self):
        _parcourir_essai(self.root, self.v["dossier_essai"], Detect3D.DOSSIER_PARCOURIR)

    def _sources(self):
        d = Path(self.v["dossier_essai"].get().strip() or ".") / SOUS_DOSSIER_RECONSTRUCTION
        if not d.is_dir():
            return []
        return sorted(c.name for c in d.iterdir() if c.is_dir() and all((c / f).is_file() for f in FICHIERS_3D))

    def _maj_sources(self, *_):
        sources = self._sources()
        self.cb_source.configure(values=sources)
        if sources and self.v["source"].get() not in sources:
            self.v["source"].set(sources[0])
        else:
            self._maj()

    def _maj(self, *_):
        source = self.v["source"].get()
        if source not in self._sources():
            self.lbl_source.configure(text="✘ aucune reconstruction dans cet essai", foreground=_ROUGE)
            self.lbl_exclues.configure(text="")
            return
        ex = ExclusionsTaches(self.v["dossier_essai"].get().strip(), source)
        with open(ex.dossier_source / "X3d.txt") as fh:
            nb_taches = len(fh.readline().split())
            nb_images = 1 + sum(1 for ligne in fh if ligne.strip())
        corrige = (ex.dossier_source / FICHIER_CORRECTION).is_file()
        self.lbl_source.configure(text=f"✔ {nb_images} images, {nb_taches} taches"
                                       + (" (0 = état plat)" if corrige else ""), foreground=_VERT)
        self.lbl_exclues.configure(text=f"Déjà enregistré : {ex.resume()}")
        self.nb_images = nb_images

    # ----- validation -----

    def _on_ok(self):
        erreurs = []
        if self.v["source"].get() not in self._sources():
            erreurs.append("Aucune reconstruction choisie")
        try:
            image, ref = int(self.v["image"].get()), int(self.v["image_reference"].get())
            if not erreurs and not (-self.nb_images <= image < self.nb_images and -self.nb_images <= ref < self.nb_images):
                erreurs.append(f"Images hors limites (0 à {self.nb_images - 1})")
        except ValueError:
            image = ref = 0
            erreurs.append("Image affichée et image de référence : entiers attendus")
        if erreurs:
            messagebox.showerror("Paramètres invalides", "\n".join(erreurs), parent=self.root)
            return
        self.result = EditeurExclusions(self.v["dossier_essai"].get().strip(), self.v["source"].get(),
                                        image=image, image_reference=ref,
                                        quantite=self.QUANTITES[self.v["quantite"].get()],
                                        inverser_z=self.SENS[self.v["sens_z"].get()])
        self.root.destroy()


def run_selection_gui():
    """Choisit une reconstruction puis ouvre l'éditeur ; renvoie les indices (Lp_final) exclus, ou None."""
    editeur = SelectionGUI().ask()
    if editeur is None:
        print("Annulé")
        return None
    print(f"Reconstruction : {editeur.exclusions.dossier_source} ({editeur.nb_images} images, "
          f"{editeur.nb_taches} taches) ; {editeur.exclusions.resume()}")
    return editeur.ouvrir()