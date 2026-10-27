"""Interface tkinter de Deformation : saisie des paramètres puis calcul des champs de déformation.

Usage depuis un script placé à côté du dossier Pycaso/ :
    from Pycaso.deformation_gui import run_deformation_gui
    run_deformation_gui()

Les valeurs proposées au départ sont les valeurs par défaut de Deformation.__init__.
"""

import os
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

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


class DeformationGUI:
    """Fenêtre de saisie des paramètres de Deformation."""

    CASES = [
        ("nuage_3d", "Tracer aussi le nuage de points 3D"),
        ("nuage_deplacement", "Nuage 3D : tracer le déplacement z − z(image 0) plutôt que z"),
        ("enregistrer_champs", "Enregistrer les champs calculés (champs_<n>.npz)"),
        ("enregistrer_figures", "Enregistrer les figures (.png dans le dossier des résultats)"),
        ("afficher_figures", "Afficher les figures à la fin"),
    ]
    AIDE_INTERPOLATION = {
        "rbf": "comme getdef.py ; ne reproduit pas exactement un champ linéaire",
        "rbf_polynome": "RBF + polynôme de degré 1 : plus précis (thin_plate_spline conseillé)",
        "griddata": "linéaire par triangles : très rapide, gradients constants par triangle",
    }
    SENS = {"auto (dôme vers le haut)": None, "inverser": True, "garder": False}
    PAD = _PAD

    def __init__(self):
        self.result = None
        self.root = tk.Tk()
        self.root.title("Champs de déformation")
        self.root.resizable(False, False)
        _appliquer_style(self.root)
        self._creer_variables(Deformation())       # valeurs par défaut de la classe
        self._construire()
        # le dossier de l'essai suit la date tant que l'utilisateur ne l'a pas modifié
        self._chemin_auto = self.v["dossier_essai"].get()
        self.v["date"].trace_add("write", self._suivre_date)
        for k in ("date", "dossier_essai"):
            self.v[k].trace_add("write", self._maj_sources)
        self.v["source"].trace_add("write", self._maj)
        self._maj_sources()
        self._maj_calcul()

    def ask(self):
        """Affiche la fenêtre ; renvoie un Deformation rempli, ou None si annulé."""
        self.root.mainloop()
        return self.result

    # ----- construction -----

    def _creer_variables(self, d):
        self.v = {
            "date": tk.StringVar(value=d.date),
            "dossier_essai": tk.StringVar(value=d.dossier_essai),
            "source": tk.StringVar(value=d.source),
            "taille_grille": tk.StringVar(value=str(d.taille_grille)),
            "interpolation": tk.StringVar(value=d.interpolation),
            "fonction_rbf": tk.StringVar(value=d.fonction_rbf),
            "lissage": tk.StringVar(value=f"{d.lissage:g}"),
            "voisins": tk.StringVar(value=str(d.voisins)),
            "masque": tk.StringVar(value=d.masque),
            "rayon_masque": tk.StringVar(value=f"{d.rayon_masque:g}"),
            "images": tk.StringVar(value=_ecrire_images(d.images)),
            "sens_z": tk.StringVar(value=next(l for l, v in self.SENS.items() if v == d.inverser_z)),
        }
        for nom, _ in self.CASES:
            self.v[nom] = tk.BooleanVar(value=bool(getattr(d, nom)))
        self.v_grandeurs = {g: tk.BooleanVar(value=g in d.grandeurs) for g in Deformation.GRANDEURS}
        self.v_composantes = {c: tk.BooleanVar(value=c in d.composantes) for c in Deformation.COMPOSANTES}

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
        self.cb_source = ttk.Combobox(f, textvariable=self.v["source"], state="readonly", width=14)
        self.cb_source.grid(row=2, column=1, sticky="w", **pad)
        self.lbl_source = ttk.Label(f, wraplength=420, justify="left")
        self.lbl_source.grid(row=2, column=2, sticky="w", **pad)
        self.lbl_sortie = ttk.Label(f, foreground="gray", wraplength=600)
        self.lbl_sortie.grid(row=3, column=0, columnspan=3, sticky="w", **pad)

        # --- Calcul ---
        f = self._bloc("Calcul", 1)
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
        ttk.Label(lm, text="× demi-largeur de la zone initiale (disque) ; hors masque : NaN",
                  foreground="gray").grid(row=0, column=2, padx=(8, 0))

        ttk.Label(f, text="Sens de z").grid(row=4, column=0, sticky="w", **pad)
        ttk.Combobox(f, textvariable=self.v["sens_z"], state="readonly", values=list(self.SENS),
                     width=22).grid(row=4, column=1, sticky="w", **pad)
        self._aide(f, "change seulement le signe de Uz et des composantes xz, yz de F et LE", 4)

        # --- Résultats ---
        f = self._bloc("Images et figures", 2)
        ttk.Label(f, text="Images à traiter").grid(row=0, column=0, sticky="w", **pad)
        li = ttk.Frame(f)
        li.grid(row=0, column=1, columnspan=2, sticky="w", **pad)
        ttk.Entry(li, textvariable=self.v["images"], width=30).grid(row=0, column=0)
        ttk.Button(li, text="Choisir…", command=self._choisir_images).grid(row=0, column=1, padx=(4, 8))
        ttk.Label(li, text=_AIDE_IMAGES, foreground="gray").grid(row=0, column=2, sticky="w")

        ttk.Label(f, text="Grandeurs tracées").grid(row=1, column=0, sticky="nw", **pad)
        lg = ttk.Frame(f)
        lg.grid(row=1, column=1, columnspan=2, sticky="w", **pad)
        for k, (g, (titre, _)) in enumerate(Deformation.GRANDEURS.items()):
            ttk.Checkbutton(lg, text=f"{g}  –  {titre}", variable=self.v_grandeurs[g]).grid(
                row=k // 2, column=k % 2, sticky="w", padx=(0, 16), pady=1)

        ttk.Label(f, text="Composantes").grid(row=2, column=0, sticky="w", **pad)
        lc = ttk.Frame(f)
        lc.grid(row=2, column=1, columnspan=2, sticky="w", **pad)
        for k, c in enumerate(Deformation.COMPOSANTES):
            ttk.Checkbutton(lc, text=c, variable=self.v_composantes[c]).grid(row=0, column=k, padx=(0, 10))
        ttk.Label(lc, text="(des tenseurs ; U trace x, y, z)", foreground="gray").grid(row=0, column=6)

        for i, (nom, lib) in enumerate(self.CASES, start=3):
            ttk.Checkbutton(f, text=lib, variable=self.v[nom]).grid(row=i, column=0, columnspan=3,
                                                                     sticky="w", **pad)

        # --- Boutons ---
        fb = ttk.Frame(self.root)
        fb.grid(row=3, column=0, sticky="e", **pad)
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
        d = self._courant()
        sources = d.sources_disponibles()
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
        self.lbl_sortie.configure(text=f"Résultats dans : {d.dossier_sortie}")

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
        taille = self._nombre("taille_grille", "Taille de la grille", erreurs, int, 10, defaut=100)
        lissage = self._nombre("lissage", "Lissage", erreurs, float, 0)
        voisins = self._nombre("voisins", "Voisins", erreurs, int, 0)
        rayon = self._nombre("rayon_masque", "Rayon du masque", erreurs, float, 0, strict=True, defaut=1.0)
        if self.v["interpolation"].get() == "rbf_polynome" and 0 < voisins < 10:
            erreurs.append("Voisins : 0 (toutes les taches) ou au moins 10")
        try:
            images = tuple(_lire_images(self.v["images"].get()))
            if not images:
                erreurs.append("Images à traiter : au moins une image")
        except ValueError:
            images = ()
            erreurs.append("Images : entiers ou plages a:b séparés par des virgules (ex. 0, 10:20, -1)")
        grandeurs = tuple(g for g, v in self.v_grandeurs.items() if v.get())
        composantes = tuple(c for c, v in self.v_composantes.items() if v.get())
        if any(Deformation.GRANDEURS[g][1] == "tenseur" for g in grandeurs) and not composantes:
            erreurs.append("Composantes : en cocher au moins une pour tracer un tenseur")

        if not erreurs:
            d = self._courant()
            infos = d.infos()
            if infos is None:
                erreurs.append(f"X3d.txt, Y3d.txt, Z3d.txt introuvables dans {d.dossier_entree}")
            else:
                hors = [n for n in images if not -infos[0] <= n < infos[0]]
                if hors:
                    erreurs.append(f"Images hors limites : {hors} "
                                   f"({infos[0]} images : 0 à {infos[0] - 1})")
        if erreurs:
            messagebox.showerror("Paramètres invalides", "\n".join(erreurs), parent=self.root)
            return

        self.result = Deformation(date=date,
                                  dossier_essai=self.v["dossier_essai"].get().strip(),
                                  source=self.v["source"].get(),
                                  taille_grille=taille,
                                  interpolation=self.v["interpolation"].get(),
                                  fonction_rbf=self.v["fonction_rbf"].get() or None,
                                  lissage=lissage, voisins=voisins,
                                  masque=self.v["masque"].get(), rayon_masque=rayon,
                                  inverser_z=self.SENS[self.v["sens_z"].get()],
                                  images=images, grandeurs=grandeurs, composantes=composantes,
                                  **{nom: self.v[nom].get() for nom, _ in self.CASES})
        self.root.destroy()


def run_deformation_gui():
    """Demande les paramètres puis calcule les champs de déformation.

    Renvoie l'objet Deformation (champs dans .champs : {image : {"F": ..., "E": ...}}), ou None si annulé.
    """
    deformation = DeformationGUI().ask()
    if deformation is None:
        print("Annulé")
        return None
    print("Paramètres :", deformation.parametres())
    deformation.lancer()
    return deformation