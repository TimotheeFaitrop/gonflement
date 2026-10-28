"""Interface tkinter de Detect3D : saisie des paramètres puis reconstruction 3D.

Usage depuis un script placé à côté du dossier Pycaso/ :
    from Pycaso.reconstruction_gui import run_detect3D_gui
    run_detect3D_gui()

Les valeurs proposées au départ sont les valeurs par défaut de Detect3D.__init__.
"""

import os
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

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


def _choisir_images(parent, nb, var, titre="Images", indisponibles=()):
    """Fenêtre de cases à cocher (une par image 0..nb-1) ; écrit le choix dans var (StringVar).

    indisponibles : images grisées, non sélectionnables (ex. l'image 0 sans l'état plat).
    """
    indisponibles = set(indisponibles)
    try:
        actuelles = {n % nb for n in _lire_images(var.get()) if -nb <= n < nb} - indisponibles
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
        ttk.Checkbutton(grille, text=f"{i:>3}", variable=v, width=5,
                        state="disabled" if i in indisponibles else "normal").grid(
            row=i // COLONNES, column=i % COLONNES, sticky="w", padx=2, pady=2)
    grille.update_idletasks()
    canvas.configure(width=grille.winfo_reqwidth(), scrollregion=canvas.bbox("all"))
    molette = lambda e: canvas.yview_scroll(-1 if (e.num == 4 or e.delta > 0) else 1, "units")
    for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        fen.bind_all(seq, molette)

    def tout(val):
        for i, v in enumerate(cases):
            if i not in indisponibles:
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


class Detect3DGUI:
    """Fenêtre de saisie des paramètres de Detect3D."""

    CASES = [
        ("inverser_z", "Inverser l'axe Z (dôme vers le haut)"),
        ("enregistrer_figures", "Enregistrer les figures (.png dans le dossier des résultats)"),
        ("afficher_figures", "Afficher les figures à la fin"),
    ]
    PAD = _PAD
    VERT, ORANGE, ROUGE = _VERT, _ORANGE, _ROUGE

    def __init__(self):
        self.result = None
        self.root = tk.Tk()
        self.root.title("Reconstruction 3D des taches")
        self.root.resizable(False, False)
        _appliquer_style(self.root)
        self._creer_variables(Detect3D())       # valeurs par défaut de la classe
        self._construire()
        # le dossier de mesure suit la date tant que l'utilisateur ne l'a pas modifié
        self._chemin_auto = self.v["dossier_essai"].get()
        self.v["date"].trace_add("write", self._suivre_date)
        for k in ("date", "dossier_essai", "degre"):
            self.v[k].trace_add("write", self._maj)
        self._maj_degres()

    # ----- point d'entrée -----

    def ask(self):
        """Affiche la fenêtre ; renvoie un Detect3D rempli, ou None si annulé."""
        self.root.mainloop()
        return self.result

    # ----- construction -----

    def _creer_variables(self, defaut):
        self.v = {
            "date": tk.StringVar(value=defaut.date),
            "dossier_essai": tk.StringVar(value=defaut.dossier_essai),
            "methode": tk.StringVar(value=defaut.methode),
            "degre": tk.StringVar(value=str(defaut.degre)),
            "images_a_tracer": tk.StringVar(value=_ecrire_images(defaut.images_a_tracer)),
            "facteur_z": tk.StringVar(value=f"{defaut.facteur_z:g}"),
            "couleurs_fixes": tk.BooleanVar(value=bool(defaut.couleurs_fixes)),
            "z_min": tk.StringVar(value=f"{defaut.z_min:g}"),
            "z_bleu": tk.StringVar(value=f"{defaut.z_bleu:g}"),
            "z_jaune": tk.StringVar(value=f"{defaut.z_jaune:g}"),
            "z_max": tk.StringVar(value=f"{defaut.z_max:g}"),
            "etat_plat": tk.BooleanVar(value=bool(defaut.etat_plat)),
            "deplacement": tk.BooleanVar(value=bool(defaut.deplacement)),
        }
        for nom, _ in self.CASES:
            self.v[nom] = tk.BooleanVar(value=bool(getattr(defaut, nom)))

    def _bloc(self, titre, ligne):
        f = ttk.LabelFrame(self.root, text=titre)
        f.grid(row=ligne, column=0, sticky="ew", **self.PAD)
        f.columnconfigure(2, weight=1)
        return f

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
        self.case_plat = ttk.Checkbutton(f, text="Utiliser l'état initial à partir des photos non flambées",
                                         variable=self.v["etat_plat"], command=self._maj)
        self.case_plat.grid(row=2, column=0, columnspan=3, sticky="w", **pad)
        ttk.Checkbutton(f, text="Tracer le déplacement z − z(image 0) plutôt que la position z "
                                "(décoché : axe vertical automatique)",
                        variable=self.v["deplacement"]).grid(row=3, column=0, columnspan=3, sticky="w", **pad)
        self.lbl_Lp = ttk.Label(f, wraplength=520, justify="left")
        self.lbl_Lp.grid(row=4, column=0, columnspan=3, sticky="w", **pad)
        self.lbl_sortie = ttk.Label(f, foreground="gray", wraplength=520)
        self.lbl_sortie.grid(row=5, column=0, columnspan=3, sticky="w", **pad)

        # --- Étalonnage ---
        f = self._bloc("Étalonnage", 1)
        ttk.Label(f, text="Méthode").grid(row=0, column=0, sticky="w", **pad)
        cb = ttk.Combobox(f, textvariable=self.v["methode"], state="readonly",
                          values=list(Detect3D.METHODES), width=12)
        cb.grid(row=0, column=1, sticky="w", **pad)
        cb.bind("<<ComboboxSelected>>", self._maj_degres)
        self.lbl_degre = ttk.Label(f, text="Degré")
        self.lbl_degre.grid(row=1, column=0, sticky="w", **pad)
        self.cb_degre = ttk.Combobox(f, textvariable=self.v["degre"], width=12)
        self.cb_degre.grid(row=1, column=1, sticky="w", **pad)
        self.lbl_calib = ttk.Label(f, wraplength=440, justify="left")
        self.lbl_calib.grid(row=0, column=2, rowspan=2, sticky="w", **pad)
        ttk.Label(f, text="Facteur Z").grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(f, textvariable=self.v["facteur_z"], width=14).grid(row=2, column=1, sticky="w", **pad)
        ttk.Label(f, text="Z reconstruit multiplié par ce facteur (aussi dans Z3d.txt) ; 1 = brut",
                  foreground="gray").grid(row=2, column=2, sticky="w", **pad)

        # --- Figures ---
        f = self._bloc("Figures", 2)
        ttk.Label(f, text="Images à tracer").grid(row=0, column=0, sticky="w", **pad)
        li = ttk.Frame(f)
        li.grid(row=0, column=1, columnspan=2, sticky="w", **pad)
        ttk.Entry(li, textvariable=self.v["images_a_tracer"], width=30).grid(row=0, column=0)
        ttk.Button(li, text="Choisir…", command=self._choisir_images).grid(row=0, column=1, padx=(4, 8))
        ttk.Label(li, text=_AIDE_IMAGES,
                  foreground="gray").grid(row=0, column=2, sticky="w")
        for i, (nom, lib) in enumerate(self.CASES, start=1):
            ttk.Checkbutton(f, text=lib, variable=self.v[nom]).grid(row=i, column=0, columnspan=3,
                                                                     sticky="w", **pad)
        i += 1
        ttk.Checkbutton(f, text="Échelle de couleur fixe", variable=self.v["couleurs_fixes"],
                        command=self._maj_couleurs).grid(row=i, column=0, sticky="w", **pad)
        lc = ttk.Frame(f)
        lc.grid(row=i, column=1, columnspan=2, sticky="w", **pad)
        self.champs_couleurs = []
        for j, (cle, lib) in enumerate((("z_min", "min"), ("z_bleu", "bleu"), ("z_jaune", "jaune"), ("z_max", "max (mm)"))):
            ttk.Label(lc, text=lib).grid(row=0, column=2 * j, padx=(0 if j == 0 else 12, 4))
            e = ttk.Entry(lc, textvariable=self.v[cle], width=8)
            e.grid(row=0, column=2 * j + 1)
            self.champs_couleurs.append(e)
        self._maj_couleurs()

        # --- Boutons ---
        fb = ttk.Frame(self.root)
        fb.grid(row=3, column=0, sticky="e", **pad)
        ttk.Button(fb, text="Annuler", command=self.root.destroy).grid(row=0, column=0, **pad)
        ttk.Button(fb, text="Lancer", command=self._on_ok).grid(row=0, column=1, **pad)
        self.root.bind("<Return>", lambda _e: self._on_ok())
        self.root.bind("<Escape>", lambda _e: self.root.destroy())

    def _maj_couleurs(self):
        """Les champs Z bleu / Z jaune ne sont actifs que si l'échelle fixe est cochée."""
        etat = "normal" if self.v["couleurs_fixes"].get() else "disabled"
        for e in self.champs_couleurs:
            e.configure(state=etat)

    # ----- images à tracer -----

    def _choisir_images(self):
        """Cases à cocher : 0 = état plat (grisée sans la correction), 1..n = photos de l'essai."""
        essai = self._courant()
        infos = essai.infos_Lp()
        if infos is None:
            messagebox.showerror("Images à tracer", f"{essai.fichier_Lp.name} introuvable : impossible de "
                                 "lister les images.\nVérifier le dossier de l'essai.", parent=self.root)
            return
        if essai.etat_plat:
            nb, indisponibles = infos[0], ()
        else:
            nb, indisponibles = infos[0] + 1, (0,)        # image 0 = état plat, absente de Lp_final.npy
        _choisir_images(self.root, nb, self.v["images_a_tracer"], "Images à tracer", indisponibles)

    # ----- chemin du dossier de mesure -----

    def _suivre_date(self, *_):
        """Met à jour le chemin d'après la date, sauf s'il a été modifié à la main."""
        if self.v["dossier_essai"].get() == self._chemin_auto:
            self._chemin_auto = Detect3D.chemin_par_defaut(self.v["date"].get().strip())
            self.v["dossier_essai"].set(self._chemin_auto)

    def _parcourir(self):
        """Explorateur de dossiers commençant dans Detect3D.DOSSIER_PARCOURIR."""
        _parcourir_essai(self.root, self.v["dossier_essai"], Detect3D.DOSSIER_PARCOURIR)

    # ----- vérifications en direct -----

    def _courant(self, degre=None):
        """Detect3D portant la date, le dossier et la méthode saisis (pour les chemins)."""
        return Detect3D(date=self.v["date"].get().strip(),
                        dossier_essai=self.v["dossier_essai"].get().strip() or None,
                        methode=self.v["methode"].get(), degre=degre, etat_plat=self.v["etat_plat"].get())

    def _maj_degres(self, *_):
        """Quand la méthode change : liste des degrés étalonnés et degré proposé."""
        essai = self._courant()
        degres = essai.degres_disponibles()
        self.cb_degre.configure(values=[str(n) for n in degres])
        defaut = Detect3D.METHODES[essai.methode][2]
        self.lbl_degre.configure(text={"Lagrange": "Degré (Lpform)", "Soloff": "Forme (Spform)",
                                       "Zernike": "Ordre (nZ)"}[essai.methode])
        self.v["degre"].set(str(defaut if defaut in degres or not degres else degres[0]))
        self._maj()

    def _maj(self, *_):
        try:
            degre = int(self.v["degre"].get())
        except ValueError:
            degre = None
        essai = self._courant(degre)
        corrige = essai.dossier_entree / Detect3D.FICHIER_LP_CORRIGE
        self.case_plat.state(["!disabled"] if corrige.is_file() or essai.etat_plat else ["disabled"])
        nom = essai.fichier_Lp.name

        infos = essai.infos_Lp()
        if infos:
            plat = " ; image 0 = état plat, 1 = 1re image de l'essai" if essai.etat_plat else ""
            self.lbl_Lp.configure(text=f"✔ {nom} : {infos[0]} images, {infos[1]} points "
                                       f"(dans {essai.dossier_entree}){plat}", foreground=self.VERT)
        else:
            avant = "la correction par l'état plat" if essai.etat_plat else "la détection des taches"
            self.lbl_Lp.configure(text=f"✘ {nom} introuvable dans {essai.dossier_entree} : "
                                       f"lancer d'abord {avant}", foreground=self.ROUGE)
        self.lbl_sortie.configure(text=f"Résultats dans : {essai.dossier_sortie}")

        degres = essai.degres_disponibles()
        if degre is not None and degre in degres:
            ou = essai.dossier_constantes()
            self.lbl_calib.configure(text=f"✔ étalonnage trouvé :\n{ou}", foreground=self.VERT)
        elif degres:
            self.lbl_calib.configure(text=f"✘ pas d'étalonnage {essai.methode} pour ce degré\n"
                                          f"(disponibles : {', '.join(map(str, degres))})",
                                     foreground=self.ROUGE)
        else:
            self.lbl_calib.configure(text=f"✘ aucun étalonnage {essai.methode} trouvé\n"
                                          "(Results_Calib dans le dossier mesure ou au-dessus)",
                                     foreground=self.ROUGE)

    # ----- validation -----

    def _on_ok(self):
        erreurs = []
        date = self.v["date"].get().strip()
        if not re.fullmatch(r"\d{4}_\d{2}_\d{2}", date):
            erreurs.append("Date attendue au format AAAA_MM_JJ")
        try:
            degre = int(self.v["degre"].get())
        except ValueError:
            degre = None
            erreurs.append("Degré : entier attendu")
        try:
            images = tuple(_lire_images(self.v["images_a_tracer"].get()))
        except ValueError:
            images = ()
            erreurs.append("Images à tracer : entiers ou plages a:b séparés par des virgules (ex. 0, 10:20, -1)")
        try:
            facteur_z = float(self.v["facteur_z"].get().replace(",", "."))
            if facteur_z == 0:
                raise ValueError
        except ValueError:
            facteur_z = 1.0
            erreurs.append("Facteur Z : nombre non nul attendu")
        echelle = dict(z_min=-10.0, z_bleu=0.0, z_jaune=60.0, z_max=100.0)
        if self.v["couleurs_fixes"].get():
            try:
                echelle = {k: float(self.v[k].get().replace(",", ".")) for k in echelle}
                zs = list(echelle.values())
                if not all(a < b for a, b in zip(zs, zs[1:])):
                    erreurs.append("Échelle de couleur : il faut min < bleu < jaune < max")
            except ValueError:
                erreurs.append("Échelle de couleur : min, bleu, jaune et max doivent être des nombres")

        if not erreurs:
            essai = self._courant(degre)
            infos = essai.infos_Lp()
            if infos is None:
                erreurs.append(f"{essai.fichier_Lp.name} introuvable dans {essai.dossier_entree}")
            else:
                plat = essai.etat_plat
                nb = infos[0] if plat else infos[0] + 1        # numéros 0..nb-1 (0 = état plat)
                premiere = 0 if plat else 1
                hors = [n for n in images if not (premiere <= n < nb or -(nb - premiere) <= n < 0)]
                if hors:
                    erreurs.append(f"Images à tracer hors limites : {hors} (images {premiere} à {nb - 1}"
                                   + ("" if plat else " ; l'image 0, état plat, demande « État plat »") + ")")
            if essai.dossier_constantes() is None:
                erreurs.append(f"Étalonnage {essai.methode} {essai.tag} introuvable : "
                               "il est nécessaire pour la reconstruction 3D")
        if erreurs:
            messagebox.showerror("Paramètres invalides", "\n".join(erreurs), parent=self.root)
            return

        self.result = Detect3D(date=date,
                               dossier_essai=self.v["dossier_essai"].get().strip(),
                               methode=self.v["methode"].get(), degre=degre,
                               images_a_tracer=images,
                               facteur_z=facteur_z, couleurs_fixes=self.v["couleurs_fixes"].get(),
                               etat_plat=self.v["etat_plat"].get(),
                               deplacement=self.v["deplacement"].get(),
                               **echelle,
                               **{nom: self.v[nom].get() for nom, _ in self.CASES})
        self.root.destroy()


def run_detect3D_gui():
    """Demande les paramètres puis lance la reconstruction 3D.

    Renvoie l'objet Detect3D (résultats en attributs : X, Y, Z), ou None si annulé.
    """
    detect = Detect3DGUI().ask()
    if detect is None:
        print("Annulé")
        return None
    print("Paramètres :", detect.parametres())
    detect.lancer()
    return detect