"""Interface tkinter de Detect3D : saisie des paramètres puis reconstruction 3D.

Usage depuis un script placé à côté du dossier Pycaso/ :
    from Pycaso.detect3D_gui import run_detect3D_gui
    run_detect3D_gui()

Les valeurs proposées au départ sont les valeurs par défaut de Detect3D.__init__.
"""

import os
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from Pycaso.reconstruction_class import Detect3D


class Detect3DGUI:
    """Fenêtre de saisie des paramètres de Detect3D."""

    CASES = [
        ("deplacement", "Tracer le déplacement z − z(image 0) plutôt que z"),
        ("inverser_z", "Inverser l'axe Z (dôme vers le haut)"),
        ("afficher_figures", "Afficher les figures à la fin"),
    ]
    PAD = {"padx": 6, "pady": 3}
    VERT, ORANGE, ROUGE = "#2e7d32", "#e65100", "#c62828"

    def __init__(self):
        self.result = None
        self.root = tk.Tk()
        self.root.title("Reconstruction 3D des taches")
        self.root.resizable(False, False)
        self._setup_style()
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
            "images_a_tracer": tk.StringVar(value=", ".join(map(str, defaut.images_a_tracer))),
            "seuil_aberrants": tk.StringVar(value=f"{defaut.seuil_aberrants:g}"),
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
        self.lbl_Lp = ttk.Label(f, wraplength=520, justify="left")
        self.lbl_Lp.grid(row=2, column=0, columnspan=3, sticky="w", **pad)
        self.lbl_sortie = ttk.Label(f, foreground="gray", wraplength=520)
        self.lbl_sortie.grid(row=3, column=0, columnspan=3, sticky="w", **pad)

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

        # --- Figures ---
        f = self._bloc("Figures", 2)
        ttk.Label(f, text="Images à tracer").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(f, textvariable=self.v["images_a_tracer"], width=16).grid(row=0, column=1, sticky="w", **pad)
        ttk.Label(f, text="indices séparés par des virgules ; -1 = dernière",
                  foreground="gray").grid(row=0, column=2, sticky="w", **pad)
        ttk.Label(f, text="Seuil des aberrants (mm)").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(f, textvariable=self.v["seuil_aberrants"], width=16).grid(row=1, column=1, sticky="w", **pad)
        ttk.Label(f, text="déplacement max affiché ; 0 = pas de filtre",
                  foreground="gray").grid(row=1, column=2, sticky="w", **pad)
        for i, (nom, lib) in enumerate(self.CASES, start=2):
            ttk.Checkbutton(f, text=lib, variable=self.v[nom]).grid(row=i, column=0, columnspan=3,
                                                                     sticky="w", **pad)

        # --- Boutons ---
        fb = ttk.Frame(self.root)
        fb.grid(row=3, column=0, sticky="e", **pad)
        ttk.Button(fb, text="Annuler", command=self.root.destroy).grid(row=0, column=0, **pad)
        ttk.Button(fb, text="Lancer", command=self._on_ok).grid(row=0, column=1, **pad)
        self.root.bind("<Return>", lambda _e: self._on_ok())
        self.root.bind("<Escape>", lambda _e: self.root.destroy())

    def _setup_style(self):
        """Thème 'clam' + cases à cocher lisibles (vert avec coche si cochée)."""
        style = ttk.Style(self.root)
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

    # ----- chemin du dossier de mesure -----

    def _suivre_date(self, *_):
        """Met à jour le chemin d'après la date, sauf s'il a été modifié à la main."""
        if self.v["dossier_essai"].get() == self._chemin_auto:
            self._chemin_auto = Detect3D.chemin_par_defaut(self.v["date"].get().strip())
            self.v["dossier_essai"].set(self._chemin_auto)

    def _parcourir(self):
        depart = self.v["dossier_essai"].get().strip()
        d = filedialog.askdirectory(initialdir=depart if os.path.isdir(depart) else ".",
                                    title="Dossier de l'essai (ex. date/essai1)")
        if d:
            rel = os.path.relpath(d)
            self.v["dossier_essai"].set(d if rel.startswith("..") else rel)

    # ----- vérifications en direct -----

    def _courant(self, degre=None):
        """Detect3D portant la date, le dossier et la méthode saisis (pour les chemins)."""
        return Detect3D(date=self.v["date"].get().strip(),
                        dossier_essai=self.v["dossier_essai"].get().strip() or None,
                        methode=self.v["methode"].get(), degre=degre)

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

        infos = essai.infos_Lp()
        if infos:
            self.lbl_Lp.configure(text=f"✔ Lp_final.npy : {infos[0]} images, {infos[1]} points "
                                       f"(dans {essai.dossier_entree})", foreground=self.VERT)
        else:
            self.lbl_Lp.configure(text=f"✘ Lp_final.npy introuvable dans {essai.dossier_entree} : "
                                       "lancer d'abord la détection des taches", foreground=self.ROUGE)
        self.lbl_sortie.configure(text=f"Résultats dans : {essai.dossier_sortie}")

        degres = essai.degres_disponibles()
        if degre is not None and degre in degres:
            ou = os.path.relpath(essai.dossier_constantes())
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
            images = tuple(int(x) for x in self.v["images_a_tracer"].get().replace(";", ",").split(",")
                           if x.strip())
        except ValueError:
            images = ()
            erreurs.append("Images à tracer : entiers séparés par des virgules attendus (ex. 0, 20, -1)")
        try:
            seuil = float(self.v["seuil_aberrants"].get().replace(",", "."))
            if seuil < 0:
                raise ValueError
        except ValueError:
            seuil = 0.0
            erreurs.append("Seuil des aberrants : nombre positif attendu")

        if not erreurs:
            essai = self._courant(degre)
            infos = essai.infos_Lp()
            if infos is None:
                erreurs.append(f"Lp_final.npy introuvable dans {essai.dossier_entree}")
            else:
                hors = [n for n in images if not -infos[0] <= n < infos[0]]
                if hors:
                    erreurs.append(f"Images à tracer hors limites : {hors} "
                                   f"(Lp_final contient {infos[0]} images : 0 à {infos[0] - 1})")
            if essai.dossier_constantes() is None:
                erreurs.append(f"Étalonnage {essai.methode} {essai.tag} introuvable : "
                               "il est nécessaire pour la reconstruction 3D")
        if erreurs:
            messagebox.showerror("Paramètres invalides", "\n".join(erreurs))
            return

        self.result = Detect3D(date=date,
                               dossier_essai=self.v["dossier_essai"].get().strip(),
                               methode=self.v["methode"].get(), degre=degre,
                               images_a_tracer=images, seuil_aberrants=seuil,
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