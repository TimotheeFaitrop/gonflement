"""Interface tkinter d'Anisotropie : saisie des paramètres puis calcul des ellipses de niveau.

Usage depuis un script placé à côté du dossier Pycaso/ :
    from Pycaso.anisotropie_gui import run_anisotropie_gui
    run_anisotropie_gui()

Les valeurs proposées au départ sont les valeurs par défaut d'Anisotropie.__init__.
"""

import os
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from Pycaso.anisotropie_class import Anisotropie
from Pycaso.correction_class import Correction
from Pycaso.deformation_class import Deformation
from Pycaso.reconstruction_class import Detect3D


# ----- outils tkinter (style, choix des images, explorateur de dossiers) -----

_PAD = {"padx": 6, "pady": 3}
_VERT, _ORANGE, _ROUGE = "#2e7d32", "#e65100", "#c62828"
_AIDE_IMAGES = "ex. 0, 10:20, -1   (a:b = de a à b inclus ; -1 = dernière)"


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


# ----- images -----

def _lire_images(texte):
    """'0, 10:13, -1' -> [0, 10, 11, 12, 13, -1] ; ValueError si mal écrit."""
    images = []
    for morceau in texte.replace(";", ",").split(","):
        morceau = morceau.strip()
        if not morceau:
            continue
        if ":" in morceau:
            a, b = (int(x) for x in morceau.split(":"))
            images.extend(range(a, b + 1) if a <= b else range(a, b - 1, -1))
        else:
            images.append(int(morceau))
    return images


def _ecrire_images(images):
    """[0, 10, 11, 12, 13, -1] -> '0, 10:13, -1' (suites de 3 et plus regroupées)."""
    morceaux, i, images = [], 0, list(images)
    while i < len(images):
        j = i
        while j + 1 < len(images) and images[j + 1] == images[j] + 1:
            j += 1
        if j - i >= 2:
            morceaux.append(f"{images[i]}:{images[j]}")
        else:
            morceaux.extend(str(n) for n in images[i:j + 1])
        i = j + 1
    return ", ".join(morceaux)


def _choisir_images(parent, nb, var, titre="Images"):
    """Fenêtre de cases à cocher (une par image 0..nb-1) ; écrit le choix dans var (StringVar)."""
    try:
        actuelles = {n % nb for n in _lire_images(var.get()) if -nb <= n < nb}
    except ValueError:
        actuelles = set()

    fen = tk.Toplevel(parent)
    fen.title(f"{titre} ({nb} images)")
    fen.transient(parent)
    fen.grab_set()
    cases = [tk.BooleanVar(value=i in actuelles) for i in range(nb)]
    COLONNES = 10

    # zone défilante (utile quand il y a beaucoup d'images)
    cadre = ttk.Frame(fen)
    cadre.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
    canvas = tk.Canvas(cadre, highlightthickness=0,
                       height=min(400, 30 * ((nb + COLONNES - 1) // COLONNES) + 4))
    barre = ttk.Scrollbar(cadre, orient="vertical", command=canvas.yview)
    grille = ttk.Frame(canvas)
    canvas.create_window((0, 0), window=grille, anchor="nw")
    canvas.configure(yscrollcommand=barre.set)
    canvas.grid(row=0, column=0, sticky="nsew")
    barre.grid(row=0, column=1, sticky="ns")
    for i, v in enumerate(cases):
        ttk.Checkbutton(grille, text=f"{i:>3}", variable=v, width=5).grid(
            row=i // COLONNES, column=i % COLONNES, sticky="w", padx=2, pady=2)
    grille.update_idletasks()
    canvas.configure(width=grille.winfo_reqwidth(), scrollregion=canvas.bbox("all"))
    molette = lambda e: canvas.yview_scroll(-1 if (e.num == 4 or e.delta > 0) else 1, "units")
    for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        fen.bind_all(seq, molette)

    def tout(val):
        for v in cases:
            v.set(val if val is not None else not v.get())

    def fermer():
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            fen.unbind_all(seq)
        fen.destroy()

    def valider():
        var.set(_ecrire_images([i for i, v in enumerate(cases) if v.get()]))
        fermer()

    fb = ttk.Frame(fen)
    fb.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 6))
    for j, (lib, val) in enumerate((("Tout", True), ("Aucune", False), ("Inverser", None))):
        ttk.Button(fb, text=lib, command=lambda v=val: tout(v)).grid(row=0, column=j, padx=2)
    ttk.Button(fb, text="Dernière", command=lambda: cases[-1].set(True)).grid(row=0, column=3, padx=2)
    fb.columnconfigure(4, weight=1)
    ttk.Button(fb, text="Annuler", command=fermer).grid(row=0, column=5, padx=2)
    ttk.Button(fb, text="OK", command=valider).grid(row=0, column=6, padx=2)
    fen.bind("<Return>", lambda _e: valider())
    fen.bind("<Escape>", lambda _e: fermer())
    fen.protocol("WM_DELETE_WINDOW", fermer)
    return fen


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


class AnisotropieGUI:
    """Fenêtre de saisie des paramètres d'Anisotropie."""

    CASES = [
        ("exclusions_manuelles", "Retirer les taches exclues à la main (outil de sélection)"),
        ("tracer_ellipses", "Tracer la vue de dessus (points des niveaux et ellipses)"),
        ("tracer_surface", "Tracer la surface 3D avec les ellipses"),
        ("enregistrer_resultats", "Enregistrer les ellipses (ellipses_<n>.txt)"),
        ("enregistrer_figures", "Enregistrer les figures (.png dans le dossier des résultats)"),
        ("afficher_figures", "Afficher les figures à la fin"),
    ]
    AIDE_INTERPOLATION = {
        "rbf": "comme getaniso.py",
        "rbf_polynome": "RBF + polynôme de degré 1 : plus précis (thin_plate_spline conseillé)",
        "griddata": "linéaire par triangles : très rapide",
    }
    SENS = {"auto (dôme vers le haut)": None, "inverser": True, "garder": False}
    PAD = _PAD

    def __init__(self):
        self.result = None
        self.root = tk.Tk()
        self.root.title("Anisotropie du gonflement")
        self.root.resizable(False, False)
        _appliquer_style(self.root)
        self._creer_variables(Anisotropie())       # valeurs par défaut de la classe
        self._construire()
        # le dossier de l'essai suit la date tant que l'utilisateur ne l'a pas modifié
        self._chemin_auto = self.v["dossier_essai"].get()
        self.v["date"].trace_add("write", self._suivre_date)
        for k in ("date", "dossier_essai"):
            self.v[k].trace_add("write", self._maj_sources)
        self.v["source"].trace_add("write", self._maj)
        for k in ("niveau_min", "niveau_max", "pas_niveau"):
            self.v[k].trace_add("write", self._maj_niveaux)
        self._maj_sources()
        self._maj_calcul()
        self._maj_niveaux()

    def ask(self):
        """Affiche la fenêtre ; renvoie un Anisotropie rempli, ou None si annulé."""
        self.root.mainloop()
        return self.result

    # ----- construction -----

    def _creer_variables(self, a):
        sens = next(lib for lib, val in self.SENS.items() if val == a.inverser_z)
        self.v = {
            "date": tk.StringVar(value=a.date),
            "dossier_essai": tk.StringVar(value=a.dossier_essai),
            "source": tk.StringVar(value=a.source),
            "images": tk.StringVar(value=_ecrire_images(a.images)),
            "taille_grille": tk.StringVar(value=str(a.taille_grille)),
            "interpolation": tk.StringVar(value=a.interpolation),
            "fonction_rbf": tk.StringVar(value=a.fonction_rbf),
            "lissage": tk.StringVar(value=f"{a.lissage:g}"),
            "voisins": tk.StringVar(value=str(a.voisins)),
            "masque": tk.StringVar(value=a.masque),
            "rayon_masque": tk.StringVar(value=f"{a.rayon_masque:g}"),
            "seuil_aberrants": tk.StringVar(value=f"{a.seuil_aberrants:g}"),
            "reference_deplacement": tk.StringVar(value=str(a.reference_deplacement)),
            "niveau_min": tk.StringVar(value=f"{a.niveau_min:g}"),
            "niveau_max": tk.StringVar(value=f"{a.niveau_max:g}"),
            "pas_niveau": tk.StringVar(value=f"{a.pas_niveau:g}"),
            "tolerance": tk.StringVar(value=f"{a.tolerance:g}"),
            "sens_z": tk.StringVar(value=sens),
        }
        for nom, _ in self.CASES:
            self.v[nom] = tk.BooleanVar(value=bool(getattr(a, nom)))

    def _bloc(self, titre, ligne):
        f = ttk.LabelFrame(self.root, text=titre)
        f.grid(row=ligne, column=0, sticky="ew", **self.PAD)
        f.columnconfigure(2, weight=1)
        return f

    def _aide(self, f, texte, ligne, colonne=2):
        lbl = ttk.Label(f, text=texte, foreground="gray")
        lbl.grid(row=ligne, column=colonne, sticky="w", **self.PAD)
        return lbl

    def _construire(self):
        pad = self.PAD

        # --- Essai ---
        f = self._bloc("Essai", 0)
        ttk.Label(f, text="Date (AAAA_MM_JJ)").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(f, textvariable=self.v["date"], width=16).grid(row=0, column=1, sticky="w", **pad)
        ttk.Label(f, text="Dossier de l'essai").grid(row=1, column=0, sticky="w", **pad)
        ligne = ttk.Frame(f)
        ligne.grid(row=1, column=1, columnspan=2, sticky="w", **pad)
        ttk.Entry(ligne, textvariable=self.v["dossier_essai"], width=44).grid(row=0, column=0)
        ttk.Button(ligne, text="…", width=3, command=self._parcourir).grid(row=0, column=1, padx=(4, 0))
        ttk.Label(f, text="Reconstruction").grid(row=2, column=0, sticky="w", **pad)
        self.cb_source = ttk.Combobox(f, textvariable=self.v["source"], state="readonly", width=20)
        self.cb_source.grid(row=2, column=1, sticky="w", **pad)
        self.lbl_source = ttk.Label(f, wraplength=420, justify="left")
        self.lbl_source.grid(row=2, column=2, sticky="w", **pad)
        ttk.Label(f, text="Images à traiter").grid(row=3, column=0, sticky="w", **pad)
        li = ttk.Frame(f)
        li.grid(row=3, column=1, columnspan=2, sticky="w", **pad)
        ttk.Entry(li, textvariable=self.v["images"], width=30).grid(row=0, column=0)
        ttk.Button(li, text="Choisir…", command=self._choisir_images).grid(row=0, column=1, padx=(4, 8))
        ttk.Label(li, text=_AIDE_IMAGES, foreground="gray").grid(row=0, column=2, sticky="w")
        self.lbl_sortie = ttk.Label(f, foreground="gray", wraplength=600)
        self.lbl_sortie.grid(row=4, column=0, columnspan=3, sticky="w", **pad)

        # --- Grille et interpolation ---
        f = self._bloc("Grille et interpolation", 1)
        ttk.Label(f, text="Taille de la grille").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(f, textvariable=self.v["taille_grille"], width=16).grid(row=0, column=1, sticky="w", **pad)
        self._aide(f, "points par côté", 0)

        ttk.Label(f, text="Interpolation").grid(row=1, column=0, sticky="w", **pad)
        cb = ttk.Combobox(f, textvariable=self.v["interpolation"], state="readonly",
                          values=list(Deformation.INTERPOLATIONS), width=14)
        cb.grid(row=1, column=1, sticky="w", **pad)
        cb.bind("<<ComboboxSelected>>", self._changer_interpolation)
        self.lbl_interp = self._aide(f, "", 1)

        ttk.Label(f, text="Fonction radiale").grid(row=2, column=0, sticky="w", **pad)
        self.cb_fonction = ttk.Combobox(f, textvariable=self.v["fonction_rbf"], state="readonly", width=14)
        self.cb_fonction.grid(row=2, column=1, sticky="w", **pad)
        lr = ttk.Frame(f)
        lr.grid(row=2, column=2, sticky="w", **pad)
        ttk.Label(lr, text="lissage").grid(row=0, column=0, padx=(0, 4))
        self.e_lissage = ttk.Entry(lr, textvariable=self.v["lissage"], width=8)
        self.e_lissage.grid(row=0, column=1)
        ttk.Label(lr, text="voisins").grid(row=0, column=2, padx=(12, 4))
        self.e_voisins = ttk.Entry(lr, textvariable=self.v["voisins"], width=8)
        self.e_voisins.grid(row=0, column=3)
        ttk.Label(lr, text="(0 = sans lissage / toutes les taches)", foreground="gray").grid(
            row=0, column=4, padx=(8, 0))

        ttk.Label(f, text="Masque").grid(row=3, column=0, sticky="w", **pad)
        cb = ttk.Combobox(f, textvariable=self.v["masque"], state="readonly",
                          values=list(Deformation.MASQUES), width=14)
        cb.grid(row=3, column=1, sticky="w", **pad)
        cb.bind("<<ComboboxSelected>>", self._maj_calcul)
        lm = ttk.Frame(f)
        lm.grid(row=3, column=2, sticky="w", **pad)
        ttk.Label(lm, text="rayon").grid(row=0, column=0, padx=(0, 4))
        self.e_rayon = ttk.Entry(lm, textvariable=self.v["rayon_masque"], width=8)
        self.e_rayon.grid(row=0, column=1)
        ttk.Label(lm, text="× demi-largeur de la zone initiale (disque)",
                  foreground="gray").grid(row=0, column=2, padx=(8, 0))

        ttk.Label(f, text="Seuil des aberrants (mm)").grid(row=4, column=0, sticky="w", **pad)
        ttk.Entry(f, textvariable=self.v["seuil_aberrants"], width=16).grid(row=4, column=1, sticky="w", **pad)
        self._aide(f, "tache écartée si son déplacement s'écarte de plus de ce seuil de ses voisines ; 0 = aucun filtre", 4)

        # --- Niveaux ---
        f = self._bloc("Niveaux du déplacement z", 2)
        ttk.Label(f, text="Niveaux (fraction de Uz max)").grid(row=0, column=0, sticky="w", **pad)
        ln = ttk.Frame(f)
        ln.grid(row=0, column=1, columnspan=2, sticky="w", **pad)
        for j, (cle, lib) in enumerate((("niveau_min", "de"), ("niveau_max", "à"), ("pas_niveau", "pas"))):
            ttk.Label(ln, text=lib).grid(row=0, column=2 * j, padx=(0 if j == 0 else 12, 4))
            ttk.Entry(ln, textvariable=self.v[cle], width=8).grid(row=0, column=2 * j + 1)
        self.lbl_niveaux = ttk.Label(ln, foreground="gray")
        self.lbl_niveaux.grid(row=0, column=6, padx=(12, 0))
        ttk.Label(f, text="Tolérance (mm)").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(f, textvariable=self.v["tolerance"], width=16).grid(row=1, column=1, sticky="w", **pad)
        self._aide(f, "points gardés : |Uz − niveau·Uz max| ≤ tolérance", 1)
        ttk.Label(f, text="Sens de z").grid(row=2, column=0, sticky="w", **pad)
        ttk.Combobox(f, textvariable=self.v["sens_z"], state="readonly", values=list(self.SENS),
                     width=22).grid(row=2, column=1, sticky="w", **pad)
        self._aide(f, "le dôme doit avoir un Uz positif", 2)
        ttk.Label(f, text="Déplacements / image").grid(row=3, column=0, sticky="w", **pad)
        ttk.Entry(f, textvariable=self.v["reference_deplacement"], width=16).grid(row=3, column=1, sticky="w", **pad)
        self.lbl_reference = self._aide(f, "", 3)

        # --- Résultats ---
        f = self._bloc("Résultats", 3)
        for i, (nom, lib) in enumerate(self.CASES):
            ttk.Checkbutton(f, text=lib, variable=self.v[nom]).grid(row=i, column=0, columnspan=3,
                                                                     sticky="w", **pad)

        # --- Boutons ---
        fb = ttk.Frame(self.root)
        fb.grid(row=4, column=0, sticky="e", **pad)
        ttk.Button(fb, text="Annuler", command=self.root.destroy).grid(row=0, column=0, **pad)
        ttk.Button(fb, text="Lancer", command=self._on_ok).grid(row=0, column=1, **pad)
        self.root.bind("<Return>", lambda _e: self._on_ok())
        self.root.bind("<Escape>", lambda _e: self.root.destroy())

    # ----- dossier de l'essai -----

    def _suivre_date(self, *_):
        """Met à jour le chemin d'après la date, sauf s'il a été modifié à la main."""
        if self.v["dossier_essai"].get() == self._chemin_auto:
            self._chemin_auto = Detect3D.chemin_par_defaut(self.v["date"].get().strip())
            self.v["dossier_essai"].set(self._chemin_auto)

    def _parcourir(self):
        _parcourir_essai(self.root, self.v["dossier_essai"], Detect3D.DOSSIER_PARCOURIR)

    def _courant(self):
        """Deformation portant la date, le dossier et la source saisis (pour les chemins)."""
        return Deformation(date=self.v["date"].get().strip(),
                           dossier_essai=self.v["dossier_essai"].get().strip() or None,
                           source=self.v["source"].get() or None)

    # ----- mises à jour en direct -----

    def _maj_sources(self, *_):
        """Quand l'essai change : liste des reconstructions disponibles."""
        sources = self._courant().sources_disponibles()
        self.cb_source.configure(values=sources)
        if sources and self.v["source"].get() not in sources:
            self.v["source"].set(sources[0])        # déclenche _maj
        else:
            self._maj()

    def _maj(self, *_):
        d = self._courant()
        infos = d.infos()
        if infos:
            self.lbl_source.configure(text=f"✔ {infos[0]} images, {infos[1]} taches", foreground=_VERT)
        elif d.sources_disponibles():
            self.lbl_source.configure(text=f"✘ X3d/Y3d/Z3d incomplets dans {d.dossier_entree}",
                                      foreground=_ROUGE)
        else:
            self.lbl_source.configure(text=f"✘ aucune reconstruction dans {d.dossier_reconstruction} : "
                                           "lancer d'abord la reconstruction 3D", foreground=_ROUGE)
        sortie = d.dossier_essai and f"{d.dossier_essai}/{Anisotropie.SOUS_DOSSIER_SORTIE}/{d.source}"
        if Correction.est_corrigee(d.dossier_entree):
            self.lbl_reference.configure(text="source corrigée : 0 = état plat, 1 = état serré (début de l'essai)",
                                         foreground=_VERT)
        else:
            self.lbl_reference.configure(text="image d'où sont comptés les déplacements (0 = première image)",
                                         foreground="gray")
        self.lbl_sortie.configure(text=f"Résultats dans : {sortie}")

    def _maj_niveaux(self, *_):
        """Nombre de niveaux correspondant à de / à / pas."""
        try:
            a, b, p = (float(self.v[k].get().replace(",", ".")) for k in ("niveau_min", "niveau_max", "pas_niveau"))
            n = int(round((b - a) / p)) + 1 if p > 0 and b >= a else 0
            self.lbl_niveaux.configure(text=f"→ {n} niveaux" if n > 0 else "")
        except ValueError:
            self.lbl_niveaux.configure(text="")

    def _changer_interpolation(self, *_):
        """Nouvelle interpolation : fonction radiale par défaut de cette interpolation."""
        fonctions = Deformation.INTERPOLATIONS[self.v["interpolation"].get()]
        self.v["fonction_rbf"].set(fonctions[0] if fonctions else "")
        self._maj_calcul()

    def _maj_calcul(self, *_):
        """Active seulement les champs utiles pour l'interpolation et le masque choisis."""
        interp = self.v["interpolation"].get()
        fonctions = Deformation.INTERPOLATIONS[interp]
        self.cb_fonction.configure(values=list(fonctions), state="readonly" if fonctions else "disabled")
        self.e_lissage.configure(state="normal" if fonctions else "disabled")
        self.e_voisins.configure(state="normal" if interp == "rbf_polynome" else "disabled")
        self.e_rayon.configure(state="normal" if self.v["masque"].get() == "disque" else "disabled")
        self.lbl_interp.configure(text=self.AIDE_INTERPOLATION.get(interp, ""))

    def _choisir_images(self):
        infos = self._courant().infos()
        if infos is None:
            messagebox.showerror("Images à traiter", "X3d.txt introuvable : impossible de lister "
                                 "les images.\nVérifier le dossier de l'essai.", parent=self.root)
            return
        _choisir_images(self.root, infos[0], self.v["images"], "Images à traiter")

    # ----- validation -----

    def _nombre(self, cle, nom, erreurs, type_=float, mini=None, strict=False, defaut=0):
        try:
            x = type_(self.v[cle].get().strip().replace(",", "."))
            if mini is not None and (x <= mini if strict else x < mini):
                raise ValueError
            return x
        except ValueError:
            borne = "" if mini is None else f" {'>' if strict else '≥'} {mini:g}"
            erreurs.append(f"{nom} : {'entier' if type_ is int else 'nombre'}{borne} attendu")
            return defaut

    def _on_ok(self):
        erreurs = []
        date = self.v["date"].get().strip()
        if not re.fullmatch(r"\d{4}_\d{2}_\d{2}", date):
            erreurs.append("Date attendue au format AAAA_MM_JJ")
        taille = self._nombre("taille_grille", "Taille de la grille", erreurs, int, 10, defaut=200)
        lissage = self._nombre("lissage", "Lissage", erreurs, float, 0)
        voisins = self._nombre("voisins", "Voisins", erreurs, int, 0)
        rayon = self._nombre("rayon_masque", "Rayon du masque", erreurs, float, 0, strict=True, defaut=1.0)
        seuil_ab = self._nombre("seuil_aberrants", "Seuil des aberrants", erreurs, float, 0)
        ref = self._nombre("reference_deplacement", "Image de référence des déplacements", erreurs, int)
        if self.v["interpolation"].get() == "rbf_polynome" and 0 < voisins < 10:
            erreurs.append("Voisins : 0 (toutes les taches) ou au moins 10")
        nmin = self._nombre("niveau_min", "Niveau de départ", erreurs, float, 0, strict=True, defaut=0.4)
        nmax = self._nombre("niveau_max", "Niveau de fin", erreurs, float, 0, strict=True, defaut=0.8)
        pas = self._nombre("pas_niveau", "Pas des niveaux", erreurs, float, 0, strict=True, defaut=0.01)
        tol = self._nombre("tolerance", "Tolérance", erreurs, float, 0, strict=True, defaut=0.05)
        if not nmin <= nmax <= 1:
            erreurs.append("Niveaux : il faut départ ≤ fin ≤ 1")
        try:
            images = tuple(_lire_images(self.v["images"].get()))
            if not images:
                erreurs.append("Images à traiter : au moins une image")
        except ValueError:
            images = ()
            erreurs.append("Images : entiers ou plages a:b séparés par des virgules (ex. 0, 10:20, -1)")

        if not erreurs:
            d = self._courant()
            infos = d.infos()
            if infos is None:
                erreurs.append(f"X3d.txt, Y3d.txt, Z3d.txt introuvables dans {d.dossier_entree}")
            else:
                hors = [n for n in images + (ref,) if not -infos[0] <= n < infos[0]]
                if hors:
                    erreurs.append(f"Images hors limites : {hors} "
                                   f"({infos[0]} images : 0 à {infos[0] - 1})")
        if erreurs:
            messagebox.showerror("Paramètres invalides", "\n".join(erreurs), parent=self.root)
            return

        self.result = Anisotropie(date=date,
                                  dossier_essai=self.v["dossier_essai"].get().strip(),
                                  source=self.v["source"].get(),
                                  images=images,
                                  taille_grille=taille,
                                  interpolation=self.v["interpolation"].get(),
                                  fonction_rbf=self.v["fonction_rbf"].get() or None,
                                  lissage=lissage, voisins=voisins,
                                  masque=self.v["masque"].get(), rayon_masque=rayon,
                                  seuil_aberrants=seuil_ab, reference_deplacement=ref,
                                  niveau_min=nmin, niveau_max=nmax, pas_niveau=pas, tolerance=tol,
                                  inverser_z=self.SENS[self.v["sens_z"].get()],
                                  **{nom: self.v[nom].get() for nom, _ in self.CASES})
        self.root.destroy()


def run_anisotropie_gui():
    """Demande les paramètres puis calcule l'anisotropie.

    Renvoie l'objet Anisotropie (résultats dans .resultats : {image : {"tableau", "pente", ...}}),
    ou None si annulé.
    """
    aniso = AnisotropieGUI().ask()
    if aniso is None:
        print("Annulé")
        return None
    print("Paramètres :", aniso.parametres())
    aniso.lancer()
    return aniso