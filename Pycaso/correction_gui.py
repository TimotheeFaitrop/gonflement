"""Interface tkinter de Correction : correction d'un essai par les photos de l'état plat.

Usage depuis un script placé à côté du dossier Pycaso/ :
    from Pycaso.correction_gui import run_correction_gui
    run_correction_gui()

Les valeurs proposées au départ sont les valeurs par défaut de Correction.__init__.
"""

import os
import re
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox, filedialog

from Pycaso.correction_class import Correction
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


class CorrectionGUI:
    """Fenêtre de saisie des paramètres de Correction."""

    CASES = [
        ("enregistrer_figures", "Enregistrer les figures (.png dans <essai>/correction/<source>)"),
        ("afficher_figures", "Afficher les figures à la fin"),
    ]
    MODELES = ("affine", "homographie", "polynome2", "polynome3")     # ceux d'AppariementStereo
    PAD = _PAD

    def __init__(self):
        self.result = None
        self.root = tk.Tk()
        self.root.title("Correction par l'état plat")
        self.root.resizable(False, False)
        _appliquer_style(self.root)
        self._creer_variables(Correction())        # valeurs par défaut de la classe
        self._construire()
        # le dossier de l'essai suit la date tant que l'utilisateur ne l'a pas modifié
        self._chemin_auto = self.v["dossier_essai"].get()
        self.v["date"].trace_add("write", self._suivre_date)
        for k in ("date", "dossier_essai"):
            self.v[k].trace_add("write", self._maj_sources)
        for k in ("source", "prefixe_photo"):
            self.v[k].trace_add("write", self._maj)
        self._maj_sources()

    def ask(self):
        """Affiche la fenêtre ; renvoie un Correction rempli, ou None si annulé."""
        self.root.mainloop()
        return self.result

    # ----- construction -----

    def _creer_variables(self, c):
        self.v = {
            "date": tk.StringVar(value=c.date),
            "dossier_essai": tk.StringVar(value=c.dossier_essai),
            "source": tk.StringVar(value=c.source),
            "prefixe_photo": tk.StringVar(value=c.prefixe_photo),
            "relire_plat": tk.BooleanVar(value=bool(c.relire_plat)),
            "facteur_z": tk.StringVar(value="" if c.facteur_z is None else f"{c.facteur_z:g}"),
            "taille_min_pix": tk.StringVar(value=str(c.taille_min_pix)),
            "taille_max_pix": tk.StringVar(value=str(c.taille_max_pix)),
            "w_spots": tk.BooleanVar(value=bool(c.w_spots)),
            "seuils_recalage": tk.StringVar(value=" ".join(f"{s:g}" for s in c.seuils_recalage)),
            "modele_recalage": tk.StringVar(value=c.modele_recalage),
            "seuil_plan": tk.StringVar(value=f"{c.seuil_plan:g}"),
            "nb_ecarts": tk.StringVar(value=f"{c.nb_ecarts:g}"),
            "seuil_appariement": tk.StringVar(value=f"{c.seuil_appariement:g}"),
            "degre_recalage": tk.StringVar(value=str(c.degre_recalage)),
            "recherche_angle": tk.StringVar(value=f"{c.recherche_angle:g}"),
            "recherche_decalage": tk.StringVar(value=f"{c.recherche_decalage:g}"),
        }
        for nom, _ in self.CASES:
            self.v[nom] = tk.BooleanVar(value=bool(getattr(c, nom)))

    def _bloc(self, titre, ligne):
        f = ttk.LabelFrame(self.root, text=titre)
        f.grid(row=ligne, column=0, sticky="ew", **self.PAD)
        f.columnconfigure(2, weight=1)
        return f

    def _aide(self, f, texte, ligne, colonne=2):
        lbl = ttk.Label(f, text=texte, foreground="gray")
        lbl.grid(row=ligne, column=colonne, sticky="w", **self.PAD)
        return lbl

    def _entree(self, f, ligne, texte, cle, aide):
        ttk.Label(f, text=texte).grid(row=ligne, column=0, sticky="w", **self.PAD)
        e = ttk.Entry(f, textvariable=self.v[cle], width=16)
        e.grid(row=ligne, column=1, sticky="w", **self.PAD)
        return e, self._aide(f, aide, ligne)

    def _construire(self):
        pad = self.PAD

        # --- Essai ---
        f = self._bloc("Essai à corriger", 0)
        ttk.Label(f, text="Date (AAAA_MM_JJ)").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(f, textvariable=self.v["date"], width=16).grid(row=0, column=1, sticky="w", **pad)
        ttk.Label(f, text="Dossier de l'essai").grid(row=1, column=0, sticky="w", **pad)
        l = ttk.Frame(f)
        l.grid(row=1, column=1, columnspan=2, sticky="w", **pad)
        ttk.Entry(l, textvariable=self.v["dossier_essai"], width=52).grid(row=0, column=0)
        ttk.Button(l, text="…", width=3, command=self._parcourir).grid(row=0, column=1, padx=(4, 0))
        ttk.Label(f, text="Reconstruction").grid(row=2, column=0, sticky="w", **pad)
        self.cb_source = ttk.Combobox(f, textvariable=self.v["source"], state="readonly", width=20)
        self.cb_source.grid(row=2, column=1, sticky="w", **pad)
        self.lbl_source = ttk.Label(f, wraplength=440, justify="left")
        self.lbl_source.grid(row=2, column=2, sticky="w", **pad)

        # --- État plat ---
        f = self._bloc("État plat (photos avant serrage, dans video_extenso_left / _right)", 1)
        self._entree(f, 0, "Préfixe des photos", "prefixe_photo", "photos <préfixe>_L.* et <préfixe>_R.*")
        self.lbl_photos = ttk.Label(f, wraplength=640, justify="left")
        self.lbl_photos.grid(row=1, column=0, columnspan=3, sticky="w", **pad)
        self.case_relire = ttk.Checkbutton(f, text="Relire l'état plat déjà reconstruit (sans refaire la détection)",
                                           variable=self.v["relire_plat"], command=self._maj_plat)
        self.case_relire.grid(row=2, column=0, columnspan=2, sticky="w", **pad)
        self.lbl_relire = self._aide(f, "", 2)
        self.e_facteur, self.lbl_facteur = self._entree(f, 3, "Facteur Z", "facteur_z", "")
        self.e_aire_min, _ = self._entree(f, 4, "Aire min d'une tache (px)", "taille_min_pix",
                                          "comme la détection des taches de l'essai")
        self.e_aire_max, _ = self._entree(f, 5, "Aire max d'une tache (px)", "taille_max_pix", "")
        self.case_w = ttk.Checkbutton(f, text="Taches blanches sur fond sombre", variable=self.v["w_spots"])
        self.case_w.grid(row=6, column=0, columnspan=3, sticky="w", **pad)
        self.e_seuils, _ = self._entree(f, 7, "Seuils gauche/droite (px)", "seuils_recalage",
                                        "appariement des deux caméras, du plus large au plus serré")
        ttk.Label(f, text="Modèle gauche/droite").grid(row=8, column=0, sticky="w", **pad)
        self.cb_modele = ttk.Combobox(f, textvariable=self.v["modele_recalage"], state="readonly",
                                      values=list(self.MODELES), width=14)
        self.cb_modele.grid(row=8, column=1, sticky="w", **pad)
        self._aide(f, "transformation droite → gauche (polynome2 conseillé)", 8)
        self.widgets_detection = [self.e_facteur, self.e_aire_min, self.e_aire_max, self.case_w,
                                  self.e_seuils, self.cb_modele]

        # --- Tri et appariement ---
        f = self._bloc("Tri des taches et appariement plat → serré", 2)
        self._entree(f, 0, "Distance max au plan (mm)", "seuil_plan",
                     "taches plus loin du plan de l'état plat retirées ; 0 = auto")
        self._entree(f, 1, "Seuil auto (× écart)", "nb_ecarts",
                     "seuil auto = ce nombre × écart robuste des distances au plan")
        self._entree(f, 2, "Écart max d'appariement (mm)", "seuil_appariement",
                     "après recalage ; 0 = auto (0,4 × espacement des taches)")
        self._entree(f, 3, "Degré du recalage", "degre_recalage",
                     "champ de déplacement plat → serré dans le plan (2 à 5)")
        ttk.Label(f, text="Recherche initiale").grid(row=4, column=0, sticky="w", **pad)
        lr = ttk.Frame(f)
        lr.grid(row=4, column=1, columnspan=2, sticky="w", **pad)
        ttk.Label(lr, text="rotation ±").grid(row=0, column=0, padx=(0, 4))
        ttk.Entry(lr, textvariable=self.v["recherche_angle"], width=8).grid(row=0, column=1)
        ttk.Label(lr, text="°    décalage ±").grid(row=0, column=2, padx=(4, 4))
        ttk.Entry(lr, textvariable=self.v["recherche_decalage"], width=8).grid(row=0, column=3)
        ttk.Label(lr, text="mm   (mouvement max de l'échantillon au serrage)",
                  foreground="gray").grid(row=0, column=4, padx=(4, 0))

        # --- Résultats ---
        f = self._bloc("Résultats", 3)
        self.lbl_sortie = ttk.Label(f, wraplength=640, justify="left")
        self.lbl_sortie.grid(row=0, column=0, columnspan=3, sticky="w", **pad)
        for i, (nom, lib) in enumerate(self.CASES, start=1):
            ttk.Checkbutton(f, text=lib, variable=self.v[nom]).grid(row=i, column=0, columnspan=3,
                                                                     sticky="w", **pad)

        # --- Boutons ---
        fb = ttk.Frame(self.root)
        fb.grid(row=4, column=0, sticky="e", **pad)
        ttk.Button(fb, text="Annuler", command=self.root.destroy).grid(row=0, column=0, **pad)
        ttk.Button(fb, text="Lancer", command=self._on_ok).grid(row=0, column=1, **pad)
        self.root.bind("<Return>", lambda _e: self._on_ok())
        self.root.bind("<Escape>", lambda _e: self.root.destroy())

    # ----- dossiers -----

    def _suivre_date(self, *_):
        """Met à jour le chemin d'après la date, sauf s'il a été modifié à la main."""
        if self.v["dossier_essai"].get() == self._chemin_auto:
            self._chemin_auto = Detect3D.chemin_par_defaut(self.v["date"].get().strip())
            self.v["dossier_essai"].set(self._chemin_auto)

    def _parcourir(self):
        _parcourir_essai(self.root, self.v["dossier_essai"], Detect3D.DOSSIER_PARCOURIR)

    def _courant(self):
        """Correction portant le dossier, la source et le préfixe saisis (pour les chemins)."""
        return Correction(date=self.v["date"].get().strip(),
                          dossier_essai=self.v["dossier_essai"].get().strip() or None,
                          source=self.v["source"].get() or None,
                          prefixe_photo=self.v["prefixe_photo"].get().strip() or "photo_init",
                          taille_min_pix=0, taille_max_pix=0, w_spots=False,    # inutiles ici :
                          seuils_recalage=(1,), modele_recalage="affine")       # évite d'importer la détection

    # ----- mises à jour en direct -----

    def _maj_sources(self, *_):
        sources = self._courant().sources_disponibles()
        self.cb_source.configure(values=sources)
        if sources and self.v["source"].get() not in sources:
            self.v["source"].set(sources[0])         # déclenche _maj
        else:
            self._maj()

    def _maj(self, *_):
        c = self._courant()
        infos = c.infos(c.dossier_entree)
        if infos:
            self.lbl_source.configure(text=f"✔ {infos[0]} images, {infos[1]} taches (image 0 = état serré)",
                                      foreground=_VERT)
        else:
            self.lbl_source.configure(text=f"✘ aucune reconstruction dans "
                                           f"{Path(c.dossier_essai) / Correction.SOUS_DOSSIER_RECONSTRUCTION}",
                                      foreground=_ROUGE)

        lignes, tout = [], True
        for cote in Correction.CAMERAS:
            photo, masque = c.photo_plat(cote), c.masque(cote)
            ok = photo is not None and masque.is_file()
            tout &= ok
            lignes.append(f"{'✔' if ok else '✘'} {cote} : "
                          + (photo.name if photo else f"{c.prefixe_photo}_{Correction.CAMERAS[cote][0]}.* absente")
                          + ("" if masque.is_file() else f", {masque.name} absent"))
        self.lbl_photos.configure(text="    ".join(lignes) + f"   (dans {c.dossier_essai})",
                                  foreground=_VERT if tout else _ROUGE)

        if c.plat_deja_reconstruit():
            self.case_relire.state(["!disabled"])
            n = c.infos(c.dossier_plat)
            self.lbl_relire.configure(text=f"trouvé : {n[1]} taches dans {c.dossier_plat}")
        else:
            self.v["relire_plat"].set(False)
            self.case_relire.state(["disabled"])
            self.lbl_relire.configure(text="pas encore reconstruit")

        try:
            methode, degre, fz = c.methode_source()
            self.lbl_facteur.configure(text=f"vide = celui de la source ({methode} {degre}, facteur {fz:g})")
        except ValueError as e:
            self.lbl_facteur.configure(text=f"vide = celui de la source ({e})")
        self.lbl_sortie.configure(text=f"Reconstruction corrigée : {c.dossier_corrige}\n"
                                       f"(image 0 = état plat, 1 = état serré ; à choisir comme source "
                                       f"« {c.source_corrigee} » pour la déformation et l'anisotropie)")
        self._maj_plat()

    def _maj_plat(self, *_):
        """Les réglages de détection ne servent que si l'état plat est reconstruit."""
        etat = ["disabled"] if self.v["relire_plat"].get() else ["!disabled"]
        for w in self.widgets_detection:
            w.state(etat)
        if not self.v["relire_plat"].get():
            self.cb_modele.state(["readonly"])

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
        prefixe = self.v["prefixe_photo"].get().strip()
        if not prefixe:
            erreurs.append("Préfixe des photos : obligatoire")
        relire = self.v["relire_plat"].get()
        facteur = None
        if self.v["facteur_z"].get().strip():
            facteur = self._nombre("facteur_z", "Facteur Z", erreurs, float)
            if facteur == 0:
                erreurs.append("Facteur Z : non nul")
        aire_min = self._nombre("taille_min_pix", "Aire min", erreurs, int, 1, defaut=100)
        aire_max = self._nombre("taille_max_pix", "Aire max", erreurs, int, 1, defaut=1000)
        if aire_min >= aire_max:
            erreurs.append("L'aire min doit être inférieure à l'aire max")
        txt = self.v["seuils_recalage"].get().strip()
        try:
            seuils = tuple(float(s) for s in re.split(r"[;,\s]+", txt) if s)
            if not seuils or min(seuils) <= 0:
                raise ValueError
        except ValueError:
            seuils = (80.0, 30.0, 10.0)
            erreurs.append(f"Seuils gauche/droite : « {txt} » invalide (nombres positifs, ex. 80 30 10)")
        seuil_plan = self._nombre("seuil_plan", "Distance max au plan", erreurs, float, 0)
        nb_ecarts = self._nombre("nb_ecarts", "Seuil auto", erreurs, float, 0, strict=True, defaut=4.0)
        seuil_app = self._nombre("seuil_appariement", "Écart max d'appariement", erreurs, float, 0)
        degre = self._nombre("degre_recalage", "Degré du recalage", erreurs, int, 1, defaut=3)
        angle = self._nombre("recherche_angle", "Rotation cherchée", erreurs, float, 0, defaut=15.0)
        decalage = self._nombre("recherche_decalage", "Décalage cherché", erreurs, float, 0,
                                strict=True, defaut=10.0)
        if degre > 6:
            erreurs.append("Degré du recalage : 6 au plus")
        if not erreurs:
            c = self._courant()
            if c.infos(c.dossier_entree) is None:
                erreurs.append(f"Reconstruction de l'essai introuvable : {c.dossier_entree}")
            if not relire:
                for cote, (lettre, _) in Correction.CAMERAS.items():
                    if c.photo_plat(cote) is None:
                        erreurs.append(f"Photo {prefixe}_{lettre}.* introuvable dans {c.dossier_camera(cote)}")
                    if not c.masque(cote).is_file():
                        erreurs.append(f"Masque introuvable : {c.masque(cote)}")
                try:
                    c.methode_source()
                except ValueError as e:
                    erreurs.append(str(e))
        if erreurs:
            messagebox.showerror("Paramètres invalides", "\n".join(erreurs), parent=self.root)
            return

        self.result = Correction(date=date,
                                 dossier_essai=self.v["dossier_essai"].get().strip(),
                                 source=self.v["source"].get(),
                                 prefixe_photo=prefixe, relire_plat=relire, facteur_z=facteur,
                                 taille_min_pix=aire_min, taille_max_pix=aire_max,
                                 w_spots=self.v["w_spots"].get(),
                                 seuils_recalage=seuils, modele_recalage=self.v["modele_recalage"].get(),
                                 seuil_plan=seuil_plan, nb_ecarts=nb_ecarts,
                                 seuil_appariement=seuil_app, degre_recalage=degre,
                                 recherche_angle=angle, recherche_decalage=decalage,
                                 **{nom: self.v[nom].get() for nom, _ in self.CASES})
        self.root.destroy()


def run_correction_gui():
    """Demande les paramètres puis corrige l'essai par l'état plat.

    Renvoie l'objet Correction (bilan dans .bilan), ou None si annulé.
    """
    correction = CorrectionGUI().ask()
    if correction is None:
        print("Annulé")
        return None
    print("Paramètres :", correction.parametres())
    correction.lancer()
    return correction