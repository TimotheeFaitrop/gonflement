"""Interface tkinter de PressionUz : courbe pression = f(Uz max).

Usage depuis un script placé à côté du dossier Pycaso/ :
    from Pycaso.pression_gui import run_pression_gui
    run_pression_gui()

Les valeurs proposées au départ sont les valeurs par défaut de PressionUz.__init__.
"""

import os
import re
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox, filedialog

from Pycaso.deformation_class import Deformation
from Pycaso.pression_class import PressionUz, temps_image
from Pycaso.reconstruction_class import Detect3D


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


class PressionGUI:
    """Fenêtre de saisie des paramètres de PressionUz."""

    CASES = [
        ("exclusions_manuelles", "Retirer les taches exclues à la main (outil de sélection)"),
        ("tracer_temps", "Tracer aussi pression et Uz max en fonction du temps"),
        ("enregistrer_resultats", "Enregistrer le tableau (pression_uz.txt)"),
        ("enregistrer_figures", "Enregistrer les figures (.png dans <essai>/pression/<source>)"),
        ("afficher_figures", "Afficher les figures à la fin"),
    ]
    SENS = {"auto (dôme vers le haut)": None, "inverser": True, "garder": False}
    SEPARATEURS = {"virgule": ",", "point-virgule": ";", "tabulation": "\t", "espaces": ""}
    INTERPOLATIONS = {"linéaire (entre les 2 mesures qui encadrent)": "lineaire", "mesure la plus proche": "proche"}
    PAD = _PAD

    def __init__(self):
        self.result = None
        self.root = tk.Tk()
        self.root.title("Pression en fonction de Uz max")
        self.root.resizable(False, False)
        _appliquer_style(self.root)
        p = PressionUz(source="-")                     # valeurs par défaut de la classe
        self.v = {
            "date": tk.StringVar(value=p.date),
            "dossier_essai": tk.StringVar(value=p.dossier_essai),
            "source": tk.StringVar(),
            "fichier_pression": tk.StringVar(value=str(Path(p.dossier_essai) / p.fichier_pression)),
            "colonne_temps": tk.StringVar(value=str(p.colonne_temps)),
            "colonne_pression": tk.StringVar(value=str(p.colonne_pression)),
            "separateur": tk.StringVar(value=next(k for k, v in self.SEPARATEURS.items() if v == p.separateur)),
            "lignes_entete": tk.StringVar(value=str(p.lignes_entete)),
            "pression_relative": tk.BooleanVar(value=p.pression_relative),
            "unite_pression": tk.StringVar(value=p.unite_pression),
            "decalage_temps": tk.StringVar(value=f"{p.decalage_temps:g}"),
            "interpolation": tk.StringVar(value=next(k for k, v in self.INTERPOLATIONS.items() if v == p.interpolation)),
            "reference_deplacement": tk.StringVar(value=str(p.reference_deplacement)),
            "centile": tk.StringVar(value=f"{p.centile:g}"),
            "sens_z": tk.StringVar(value=next(k for k, v in self.SENS.items() if v == p.inverser_z)),
            "seuil_aberrants": tk.StringVar(value=f"{p.seuil_aberrants:g}"),
        }
        for nom, _ in self.CASES:
            self.v[nom] = tk.BooleanVar(value=bool(getattr(p, nom)))
        self._construire()
        self._chemin_auto = self.v["dossier_essai"].get()
        self._fichier_auto = self.v["fichier_pression"].get()
        self.v["date"].trace_add("write", self._suivre_date)
        self.v["dossier_essai"].trace_add("write", self._suivre_essai)
        for k in ("date", "dossier_essai"):
            self.v[k].trace_add("write", self._maj_sources)
        for k in ("source", "fichier_pression", "colonne_temps", "colonne_pression", "separateur", "lignes_entete",
                  "decalage_temps"):
            self.v[k].trace_add("write", self._maj)
        self._maj_sources()

    def ask(self):
        """Affiche la fenêtre ; renvoie un PressionUz rempli, ou None si annulé."""
        self.root.mainloop()
        return self.result

    # ----- construction -----

    def _bloc(self, titre, ligne):
        f = ttk.LabelFrame(self.root, text=titre)
        f.grid(row=ligne, column=0, sticky="ew", **self.PAD)
        f.columnconfigure(2, weight=1)
        return f

    def _ligne(self, f, ligne, texte, widget, aide=""):
        ttk.Label(f, text=texte).grid(row=ligne, column=0, sticky="w", **self.PAD)
        widget.grid(row=ligne, column=1, sticky="w", **self.PAD)
        lbl = ttk.Label(f, text=aide, foreground="gray")
        lbl.grid(row=ligne, column=2, sticky="w", **self.PAD)
        return lbl

    def _construire(self):
        pad = self.PAD
        # --- Essai ---
        f = self._bloc("Essai", 0)
        self._ligne(f, 0, "Date (AAAA_MM_JJ)", ttk.Entry(f, textvariable=self.v["date"], width=16))
        ttk.Label(f, text="Dossier de l'essai").grid(row=1, column=0, sticky="w", **pad)
        l = ttk.Frame(f)
        l.grid(row=1, column=1, columnspan=2, sticky="w", **pad)
        ttk.Entry(l, textvariable=self.v["dossier_essai"], width=52).grid(row=0, column=0)
        ttk.Button(l, text="…", width=3, command=self._parcourir).grid(row=0, column=1, padx=(4, 0))
        self.cb_source = ttk.Combobox(f, textvariable=self.v["source"], state="readonly", width=20)
        self.lbl_source = self._ligne(f, 2, "Reconstruction", self.cb_source)
        self.lbl_images = ttk.Label(f, wraplength=640, justify="left")
        self.lbl_images.grid(row=3, column=0, columnspan=3, sticky="w", **pad)

        # --- Pression ---
        f = self._bloc("Capteur de pression", 1)
        ttk.Label(f, text="Fichier").grid(row=0, column=0, sticky="w", **pad)
        l = ttk.Frame(f)
        l.grid(row=0, column=1, columnspan=2, sticky="w", **pad)
        ttk.Entry(l, textvariable=self.v["fichier_pression"], width=52).grid(row=0, column=0)
        ttk.Button(l, text="…", width=3, command=self._parcourir_fichier).grid(row=0, column=1, padx=(4, 0))
        lc = ttk.Frame(f)
        lc.grid(row=1, column=0, columnspan=3, sticky="w", **pad)
        for j, (cle, lib, w) in enumerate((("colonne_temps", "colonne du temps", 5),
                                           ("colonne_pression", "colonne de la pression", 5),
                                           ("lignes_entete", "lignes d'en-tête", 5))):
            ttk.Label(lc, text=lib).grid(row=0, column=2 * j, padx=(0 if j == 0 else 14, 4))
            ttk.Entry(lc, textvariable=self.v[cle], width=w).grid(row=0, column=2 * j + 1)
        ttk.Label(lc, text="séparateur").grid(row=0, column=6, padx=(14, 4))
        ttk.Combobox(lc, textvariable=self.v["separateur"], state="readonly", values=list(self.SEPARATEURS),
                     width=12).grid(row=0, column=7)
        ttk.Checkbutton(f, text="Pression relative (− première mesure du capteur)",
                        variable=self.v["pression_relative"]).grid(row=2, column=0, columnspan=2, sticky="w", **pad)
        lu = ttk.Frame(f)
        lu.grid(row=2, column=2, sticky="w", **pad)
        ttk.Label(lu, text="unité").grid(row=0, column=0, padx=(0, 4))
        ttk.Entry(lu, textvariable=self.v["unite_pression"], width=8).grid(row=0, column=1)
        lt = ttk.Frame(f)
        lt.grid(row=3, column=0, columnspan=3, sticky="w", **pad)
        ttk.Label(lt, text="décalage des horloges (s)").grid(row=0, column=0, padx=(0, 4))
        ttk.Entry(lt, textvariable=self.v["decalage_temps"], width=8).grid(row=0, column=1)
        ttk.Label(lt, text="temps capteur = temps image + décalage", foreground="gray").grid(row=0, column=2, padx=(6, 14))
        ttk.Label(lt, text="pression à chaque image").grid(row=1, column=0, padx=(0, 4), pady=(4, 0), sticky="w")
        ttk.Combobox(lt, textvariable=self.v["interpolation"], state="readonly", values=list(self.INTERPOLATIONS),
                     width=40).grid(row=1, column=1, columnspan=2, sticky="w", pady=(4, 0))
        self.lbl_pression = ttk.Label(f, wraplength=640, justify="left")
        self.lbl_pression.grid(row=4, column=0, columnspan=3, sticky="w", **pad)

        # --- Uz max ---
        f = self._bloc("Uz max", 2)
        self.lbl_ref = self._ligne(f, 0, "Déplacements / image",
                                   ttk.Entry(f, textvariable=self.v["reference_deplacement"], width=10), "")
        self._ligne(f, 1, "Centile", ttk.Entry(f, textvariable=self.v["centile"], width=10),
                    "100 = maximum ; 99 ou 99.5 = moins sensible à une tache isolée")
        self._ligne(f, 2, "Sens de z", ttk.Combobox(f, textvariable=self.v["sens_z"], state="readonly",
                                                     values=list(self.SENS), width=24))
        self._ligne(f, 3, "Seuil des aberrants (mm)", ttk.Entry(f, textvariable=self.v["seuil_aberrants"], width=10),
                    "comme la déformation ; 0 = aucun filtre")

        # --- Résultats ---
        f = self._bloc("Résultats", 3)
        for i, (nom, lib) in enumerate(self.CASES):
            ttk.Checkbutton(f, text=lib, variable=self.v[nom]).grid(row=i, column=0, columnspan=3, sticky="w", **pad)

        fb = ttk.Frame(self.root)
        fb.grid(row=4, column=0, sticky="e", **pad)
        ttk.Button(fb, text="Annuler", command=self.root.destroy).grid(row=0, column=0, **pad)
        ttk.Button(fb, text="Lancer", command=self._on_ok).grid(row=0, column=1, **pad)
        self.root.bind("<Return>", lambda _e: self._on_ok())
        self.root.bind("<Escape>", lambda _e: self.root.destroy())

    # ----- dossiers et fichiers -----

    def _suivre_date(self, *_):
        if self.v["dossier_essai"].get() == self._chemin_auto:
            self._chemin_auto = Detect3D.chemin_par_defaut(self.v["date"].get().strip())
            self.v["dossier_essai"].set(self._chemin_auto)

    def _parcourir(self):
        _parcourir_essai(self.root, self.v["dossier_essai"], Detect3D.DOSSIER_PARCOURIR)

    def _suivre_essai(self, *_):
        """Le fichier de pression suit le dossier de l'essai, sauf s'il a été modifié à la main."""
        if self.v["fichier_pression"].get() == self._fichier_auto:
            nom = Path(self._fichier_auto).name or "data_ali.txt"
            self._fichier_auto = str(Path(self.v["dossier_essai"].get().strip() or ".") / nom)
            self.v["fichier_pression"].set(self._fichier_auto)

    def _parcourir_fichier(self):
        actuel = Path(self.v["fichier_pression"].get().strip())
        depart = _dossier_depart(str(actuel.parent), self.v["dossier_essai"].get().strip() or ".")
        f = filedialog.askopenfilename(initialdir=depart, parent=self.root, title="Fichier du capteur de pression",
                                       filetypes=[("Texte", "*.txt *.csv *.dat"), ("Tous", "*")])
        if f:
            try:
                rel = os.path.relpath(f)
            except ValueError:                 # Windows : autre lecteur que le dossier d'exécution
                rel = ".."
            self.v["fichier_pression"].set(f if rel.startswith("..") else rel)

    def _courant(self, **kw):
        sep = self.SEPARATEURS.get(self.v["separateur"].get(), ",")
        try:
            cols = dict(colonne_temps=int(self.v["colonne_temps"].get()),
                        colonne_pression=int(self.v["colonne_pression"].get()),
                        lignes_entete=int(self.v["lignes_entete"].get()))
        except ValueError:
            cols = {}
        return PressionUz(date=self.v["date"].get().strip(),
                          dossier_essai=self.v["dossier_essai"].get().strip() or None,
                          source=self.v["source"].get() or "-",
                          fichier_pression=self.v["fichier_pression"].get().strip() or "data_ali.txt",
                          separateur=sep, **cols, **kw)

    # ----- mises à jour en direct -----

    def _maj_sources(self, *_):
        sources = Deformation(dossier_essai=self.v["dossier_essai"].get().strip() or ".", source="-").sources_disponibles()
        self.cb_source.configure(values=sources)
        if sources and self.v["source"].get() not in sources:
            self.v["source"].set(sources[0])
        else:
            self._maj()

    def _maj(self, *_):
        p = self._courant()
        self.plage_images = None
        if (p.dossier_source / "X3d.txt").is_file():
            with open(p.dossier_source / "X3d.txt") as fh:
                nb_taches = len(fh.readline().split())
                nb = 1 + sum(1 for ligne in fh if ligne.strip())
            corr = p.est_corrigee
            self.lbl_source.configure(text=f"✔ {nb} images, {nb_taches} taches"
                                           + (" (0 = état plat)" if corr else ""), foreground=_VERT)
            self.lbl_ref.configure(text="0 = état plat, 1 = 1re photo de l'essai" if corr
                                   else "1 = 1re photo de l'essai (pas d'état plat : 0 = 1re photo)")
            nb_photos = nb - (1 if corr else 0)
            images = p.images_essai()
            temps = [temps_image(f) for f in images[:nb_photos]]
            ok = [t for t in temps if t == t]
            if len(images) < nb_photos:
                self.lbl_images.configure(text=f"✘ {len(images)} image(s) dans video_extenso_left pour {nb_photos} "
                                               "photos dans la reconstruction", foreground=_ROUGE)
            elif not ok:
                self.lbl_images.configure(text="✘ pas de temps dans les noms des images (attendu : 000012_4.567.tiff)",
                                          foreground=_ROUGE)
            else:
                self.plage_images = (min(ok), max(ok))
                self.lbl_images.configure(text=f"✔ temps des {nb_photos} photos : {min(ok):.3g} à {max(ok):.3g} s",
                                          foreground=_VERT)
        else:
            self.lbl_source.configure(text="✘ aucune reconstruction dans cet essai", foreground=_ROUGE)
            self.lbl_images.configure(text="")
        try:
            t, pr = p.lire_pression()
            texte = f"✔ {len(t)} mesures, temps {t.min():.3g} à {t.max():.3g} s, pression {pr.min():.4g} à {pr.max():.4g}"
            couleur = _VERT
            try:
                dec = float(self.v["decalage_temps"].get().replace(",", "."))
            except ValueError:
                dec = 0.0
            if self.plage_images and (self.plage_images[0] + dec < t.min() or self.plage_images[1] + dec > t.max()):
                texte += "  ⚠ des images sont hors de la plage du capteur (pression NaN)"
                couleur = _ORANGE
            self.lbl_pression.configure(text=texte, foreground=couleur)
        except (OSError, ValueError, IndexError) as e:
            msg = "fichier introuvable" if not p.chemin_pression.is_file() else f"lecture impossible ({e})"
            self.lbl_pression.configure(text=f"✘ {p.chemin_pression} : {msg}", foreground=_ROUGE)

    # ----- validation -----

    def _nombre(self, cle, nom, erreurs, type_=float, mini=None, maxi=None, defaut=0):
        try:
            x = type_(self.v[cle].get().strip().replace(",", "."))
            if (mini is not None and x < mini) or (maxi is not None and x > maxi):
                raise ValueError
            return x
        except ValueError:
            borne = "" if mini is None else f" entre {mini:g} et {maxi:g}" if maxi is not None else f" ≥ {mini:g}"
            erreurs.append(f"{nom} : {'entier' if type_ is int else 'nombre'}{borne} attendu")
            return defaut

    def _on_ok(self):
        erreurs = []
        date = self.v["date"].get().strip()
        if not re.fullmatch(r"\d{4}_\d{2}_\d{2}", date):
            erreurs.append("Date attendue au format AAAA_MM_JJ")
        ct = self._nombre("colonne_temps", "Colonne du temps", erreurs, int, 0)
        cp = self._nombre("colonne_pression", "Colonne de la pression", erreurs, int, 0)
        le = self._nombre("lignes_entete", "Lignes d'en-tête", erreurs, int, 0)
        ref = self._nombre("reference_deplacement", "Image de référence", erreurs, int)
        centile = self._nombre("centile", "Centile", erreurs, float, 50, 100, defaut=100.0)
        seuil = self._nombre("seuil_aberrants", "Seuil des aberrants", erreurs, float, 0, defaut=2.0)
        decalage = self._nombre("decalage_temps", "Décalage des horloges", erreurs, float, defaut=0.0)
        p = self._courant()
        if not (p.dossier_source / "X3d.txt").is_file():
            erreurs.append("Aucune reconstruction choisie")
        if not erreurs:
            try:
                p.lire_pression()
            except (OSError, ValueError, IndexError) as e:
                erreurs.append(f"Fichier de pression illisible : {e}")
            if self.plage_images is None:
                erreurs.append("Temps des images introuvables (voir le bloc Essai)")
        if erreurs:
            messagebox.showerror("Paramètres invalides", "\n".join(erreurs), parent=self.root)
            return
        self.result = PressionUz(date=date, dossier_essai=self.v["dossier_essai"].get().strip(),
                                 source=self.v["source"].get(),
                                 fichier_pression=self.v["fichier_pression"].get().strip(),
                                 colonne_temps=ct, colonne_pression=cp, lignes_entete=le,
                                 separateur=self.SEPARATEURS[self.v["separateur"].get()],
                                 pression_relative=self.v["pression_relative"].get(),
                                 unite_pression=self.v["unite_pression"].get().strip() or "mbar",
                                 decalage_temps=decalage,
                                 interpolation=self.INTERPOLATIONS[self.v["interpolation"].get()],
                                 reference_deplacement=ref, centile=centile,
                                 inverser_z=self.SENS[self.v["sens_z"].get()], seuil_aberrants=seuil,
                                 **{nom: self.v[nom].get() for nom, _ in self.CASES})
        self.root.destroy()


def run_pression_gui():
    """Demande les paramètres puis trace la pression en fonction de Uz max.

    Renvoie l'objet PressionUz (résultats dans .resultats), ou None si annulé.
    """
    p = PressionGUI().ask()
    if p is None:
        print("Annulé")
        return None
    print("Paramètres :", p.parametres())
    p.lancer()
    return p