"""Interface tkinter de DetectionSpots : saisie des paramètres puis lancement.

Usage depuis un script placé à côté du dossier Pycaso/ :
    from Pycaso.detection_spots_gui import run_coord_gui
    run_coord_gui()

Les valeurs proposées au départ sont les valeurs par défaut de DetectionSpots.__init__.
"""

import glob
import os
import re
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox, filedialog

from Pycaso.detection_spots_general import DetectionSpots
from Pycaso.detection_spots_appariemment import AppariementStereo


# ----- palette -----
FOND = "#eef1f5"          # fond de la fenêtre
CARTE = "#ffffff"         # fond des cartes
BORD = "#dde2e8"          # bordure des cartes
TEXTE = "#1f2933"
DISCRET = "#6b7785"       # aides et textes secondaires
ACCENT = "#2563eb"        # bouton Lancer, liserés, cases cochées
ACCENT_FONCE = "#1d4ed8"
ENTETE = "#1e293b"
OK, OK_FOND = "#1b7a3d", "#e6f4ea"
ERR, ERR_FOND = "#b42318", "#fdecea"
AVERT, AVERT_FOND = "#a15c00", "#fff4e0"
INFO, INFO_FOND = "#1e3a8a", "#eef4ff"


class DetectionSpotsGUI:
    """Fenêtre de saisie des paramètres de DetectionSpots."""

    # nom, libellé, type, aide
    CHAMPS_SUIVI = [
        ("pix", "Marge de recherche", int, "px · < moitié de l'écart entre taches"),
        ("taille_min_pix", "Aire min d'une tache", int, "px"),
        ("taille_max_pix", "Aire max d'une tache", int, "px"),
        ("max_images_a_considerer", "Images à suivre", int, "après l'image 0"),
    ]
    CHAMPS_APPARIEMENT = [   # utilisés seulement avec l'étalonnage
        ("rayon_recherche", "Rayon de recherche", float, "px, sur l'autre caméra"),
        ("tolerance_plan", "Tolérance au plan", float, "mm, écart max d'une paire"),
    ]
    CASES = [
        ("w_spots", "Taches blanches sur fond sombre"),
        ("figures_suivi", "Une figure .svg par image (lent)"),
        ("afficher_figures", "Afficher la figure d'appariement à la fin"),
    ]
    REPRISE = [("left", "gauche_calculated", "Caméra gauche"),
               ("right", "droite_calculated", "Caméra droite")]
    MODELES_AIDE = {
        "affine": "translation, rotation, échelle (comme CoordCa10)",
        "homographie": "perspective d'un plan vu par deux caméras",
        "polynome2": "perspective + distorsion des objectifs (conseillé)",
        "polynome3": "distorsion plus forte",
    }

    def __init__(self):
        self.result = None
        self.root = tk.Tk()
        self.root.title("Détection des taches - coordonnées 2D")
        self.root.configure(background=FOND)
        self.root.resizable(False, False)
        self._setup_style()
        self._creer_variables(DetectionSpots())   # valeurs par défaut de la classe
        self._construire()
        # le dossier de mesure suit la date tant que l'utilisateur ne l'a pas modifié
        self._chemin_auto = self.v["dossier_mesure"].get()
        self.v["date"].trace_add("write", self._suivre_date)
        for k in ("date", "dossier_mesure", "l_pform"):
            self.v[k].trace_add("write", self._maj_essai)
        self.v["utiliser_etalonnage"].trace_add("write", self._maj_mode)
        self.v["modele_recalage"].trace_add("write", self._maj_aide_modele)
        self.v["max_images_a_considerer"].trace_add("write", self._maj_nb_images)
        self._maj_mode()
        self._maj_aide_modele()
        self._maj_nb_images()

    # ----- point d'entrée -----

    def ask(self):
        """Affiche la fenêtre ; renvoie un DetectionSpots rempli, ou None si annulé."""
        self.root.mainloop()
        return self.result

    # ----- style -----

    def _setup_style(self):
        """Thème 'clam' recoloré : cartes blanches sur fond gris clair, accent bleu."""
        base = tkfont.nametofont("TkDefaultFont")
        famille = base.actual("family")
        self.polices = {
            "texte": (famille, 10),
            "petit": (famille, 9),
            "carte": (famille, 11, "bold"),
            "titre": (famille, 15, "bold"),
            "sous_titre": (famille, 10),
            "bouton": (famille, 10, "bold"),
        }
        for nom in ("TkDefaultFont", "TkTextFont", "TkMenuFont"):
            tkfont.nametofont(nom).configure(family=famille, size=10)

        s = ttk.Style(self.root)
        s.theme_use("clam")
        p = self.polices
        s.configure(".", background=CARTE, foreground=TEXTE, font=p["texte"])
        s.configure("Fond.TFrame", background=FOND)
        s.configure("Carte.TFrame", background=CARTE)
        s.configure("TLabel", background=CARTE, foreground=TEXTE)
        s.configure("Aide.TLabel", foreground=DISCRET, font=p["petit"])
        s.configure("Carte.TLabel", font=p["carte"])
        s.configure("Entete.TLabel", background=ENTETE, foreground="white", font=p["titre"])
        s.configure("SousTitre.TLabel", background=ENTETE, foreground="#cbd5e1", font=p["sous_titre"])
        s.configure("Info.TLabel", background=INFO_FOND, foreground=INFO, font=p["petit"])

        # champs
        s.configure("TEntry", fieldbackground="white", bordercolor=BORD, lightcolor=BORD,
                    darkcolor=BORD, padding=(6, 4))
        s.map("TEntry", bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)],
              fieldbackground=[("disabled", "#f3f5f8")], foreground=[("disabled", "#a3acb7")])
        s.configure("TCombobox", fieldbackground="white", background="white", bordercolor=BORD,
                    lightcolor=BORD, darkcolor=BORD, arrowcolor=DISCRET, padding=(6, 4))
        s.map("TCombobox", fieldbackground=[("readonly", "white"), ("disabled", "#f3f5f8")],
              foreground=[("disabled", "#a3acb7")], bordercolor=[("focus", ACCENT)],
              selectbackground=[("readonly", "white")], selectforeground=[("readonly", TEXTE)])
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.root.option_add("*TCombobox*Listbox.font", p["texte"])

        # cases à cocher : carré blanc, bleu avec coche blanche si coché
        s.configure("TCheckbutton", background=CARTE, indicatorsize=15,
                    indicatormargin=(0, 0, 8, 0), indicatorbackground="white",
                    indicatorforeground="white", upperbordercolor="#9aa5b1",
                    lowerbordercolor="#9aa5b1", padding=(0, 3))
        s.map("TCheckbutton",
              background=[("active", CARTE)],
              indicatorbackground=[("disabled", "#eceff3"), ("selected", ACCENT)],
              upperbordercolor=[("selected", ACCENT)], lowerbordercolor=[("selected", ACCENT)],
              foreground=[("disabled", "#a3acb7")])

        # boutons
        s.configure("TButton", background="#f3f5f8", bordercolor=BORD, lightcolor="#f3f5f8",
                    darkcolor="#f3f5f8", padding=(14, 6), font=p["texte"])
        s.map("TButton", background=[("active", "#e6eaf0")])
        s.configure("Accent.TButton", background=ACCENT, foreground="white", bordercolor=ACCENT,
                    lightcolor=ACCENT, darkcolor=ACCENT, font=p["bouton"], padding=(22, 7))
        s.map("Accent.TButton", background=[("active", ACCENT_FONCE), ("pressed", ACCENT_FONCE)],
              lightcolor=[("active", ACCENT_FONCE)], darkcolor=[("active", ACCENT_FONCE)])
        s.configure("Parcourir.TButton", padding=(8, 4))
        s.configure("TSeparator", background=BORD)

    # ----- briques -----

    def _creer_variables(self, defaut):
        self.v = {}
        for nom in ("date", "dossier_mesure"):
            self.v[nom] = tk.StringVar(value=str(getattr(defaut, nom)))
        for nom, _, _, _ in self.CHAMPS_SUIVI + self.CHAMPS_APPARIEMENT:
            self.v[nom] = tk.StringVar(value=str(getattr(defaut, nom)))
        for nom, _ in self.CASES:
            self.v[nom] = tk.BooleanVar(value=bool(getattr(defaut, nom)))
        for _, nom, _ in self.REPRISE:
            self.v[nom] = tk.BooleanVar(value=bool(getattr(defaut, nom)))
        self.v["l_pform"] = tk.StringVar(value=str(defaut.l_pform))
        self.v["utiliser_etalonnage"] = tk.BooleanVar(value=bool(defaut.utiliser_etalonnage))
        self.v["seuils_recalage"] = tk.StringVar(value=" ".join(f"{s:g}" for s in defaut.seuils_recalage))
        self.v["modele_recalage"] = tk.StringVar(value=defaut.modele_recalage)

    def _carte(self, parent, titre, ligne, colonne, columnspan=1):
        """Carte blanche avec liseré bleu et titre ; renvoie le cadre intérieur (grille)."""
        bord = tk.Frame(parent, background=BORD)
        bord.grid(row=ligne, column=colonne, columnspan=columnspan, sticky="nsew", padx=8, pady=8)
        carte = tk.Frame(bord, background=CARTE)
        carte.pack(fill="both", expand=True, padx=1, pady=1)
        tk.Frame(carte, background=ACCENT, width=4).pack(side="left", fill="y")
        corps = ttk.Frame(carte, style="Carte.TFrame", padding=(16, 12, 16, 14))
        corps.pack(side="left", fill="both", expand=True)
        ttk.Label(corps, text=titre, style="Carte.TLabel").grid(row=0, column=0, columnspan=3,
                                                                sticky="w", pady=(0, 8))
        corps.columnconfigure(2, weight=1)
        return corps

    def _champ(self, f, ligne, libelle, var, aide="", largeur=10):
        ttk.Label(f, text=libelle).grid(row=ligne, column=0, sticky="w", padx=(0, 12), pady=4)
        e = ttk.Entry(f, textvariable=var, width=largeur)
        e.grid(row=ligne, column=1, sticky="w", pady=4)
        lbl = ttk.Label(f, text=aide, style="Aide.TLabel")
        lbl.grid(row=ligne, column=2, sticky="w", padx=(10, 0), pady=4)
        return e, lbl

    def _pastille(self, parent):
        """Label d'état coloré (rempli par _etat)."""
        return tk.Label(parent, font=self.polices["petit"], padx=8, pady=2, anchor="w",
                        background=CARTE, foreground=DISCRET)

    @staticmethod
    def _etat(lbl, texte, niveau=None):
        couleurs = {"ok": (OK, OK_FOND), "err": (ERR, ERR_FOND), "avert": (AVERT, AVERT_FOND),
                    None: (DISCRET, CARTE)}
        fg, bg = couleurs[niveau]
        lbl.configure(text=texte, foreground=fg, background=bg)

    # ----- construction -----

    def _construire(self):
        # --- en-tête ---
        entete = tk.Frame(self.root, background=ENTETE)
        entete.grid(row=0, column=0, sticky="ew")
        ttk.Label(entete, text="Détection et appariement des taches",
                  style="Entete.TLabel").pack(anchor="w", padx=24, pady=(16, 0))
        ttk.Label(entete, text="Suivi 2D sur les deux caméras, appariement gauche / droite, "
                               "enregistrement de Lp_final.npy",
                  style="SousTitre.TLabel").pack(anchor="w", padx=24, pady=(2, 16))

        corps = ttk.Frame(self.root, style="Fond.TFrame", padding=(12, 8, 12, 0))
        corps.grid(row=1, column=0, sticky="nsew")
        corps.columnconfigure(0, weight=1, uniform="col")
        corps.columnconfigure(1, weight=1, uniform="col")

        # --- Essai (pleine largeur) ---
        f = self._carte(corps, "Essai", 0, 0, columnspan=2)
        ttk.Label(f, text="Date").grid(row=1, column=0, sticky="w", padx=(0, 12), pady=4)
        ttk.Entry(f, textvariable=self.v["date"], width=14).grid(row=1, column=1, sticky="w", pady=4)
        ttk.Label(f, text="AAAA_MM_JJ", style="Aide.TLabel").grid(row=1, column=2, sticky="w",
                                                                   padx=(10, 0))
        ttk.Label(f, text="Dossier de l'essai").grid(row=2, column=0, sticky="w", padx=(0, 12), pady=4)
        ligne = ttk.Frame(f, style="Carte.TFrame")
        ligne.grid(row=2, column=1, columnspan=2, sticky="ew", pady=4)
        ligne.columnconfigure(0, weight=1)
        ttk.Entry(ligne, textvariable=self.v["dossier_mesure"]).grid(row=0, column=0, sticky="ew")
        ttk.Button(ligne, text="Parcourir…", style="Parcourir.TButton",
                   command=self._parcourir).grid(row=0, column=1, padx=(6, 0))
        etats = ttk.Frame(f, style="Carte.TFrame")
        etats.grid(row=3, column=1, columnspan=2, sticky="w", pady=(6, 0))
        self.lbl_dossier = self._pastille(etats)
        self.lbl_dossier.pack(anchor="w")
        self.lbl_resultats = ttk.Label(etats, style="Aide.TLabel")
        self.lbl_resultats.pack(anchor="w", pady=(4, 0))

        # --- colonne gauche : suivi, reprise, options ---
        gauche = ttk.Frame(corps, style="Fond.TFrame")
        gauche.grid(row=1, column=0, sticky="nsew")
        gauche.columnconfigure(0, weight=1)

        f = self._carte(gauche, "Détection et suivi des taches", 0, 0)
        for i, (nom, lib, _, aide) in enumerate(self.CHAMPS_SUIVI, start=1):
            _, lbl = self._champ(f, i, lib, self.v[nom], aide, largeur=8)
            if nom == "max_images_a_considerer":
                self.lbl_nb_images = lbl

        f = self._carte(gauche, "Reprise", 1, 0)
        ttk.Label(f, text="Relire les coordonnées déjà calculées au lieu de refaire le suivi",
                  style="Aide.TLabel").grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 4))
        self.cases_reprise, self.lbl_reprise = {}, {}
        for i, (cote, nom, lib) in enumerate(self.REPRISE, start=2):
            self.cases_reprise[cote] = ttk.Checkbutton(f, text=lib, variable=self.v[nom])
            self.cases_reprise[cote].grid(row=i, column=0, sticky="w", padx=(0, 12))
            self.lbl_reprise[cote] = self._pastille(f)
            self.lbl_reprise[cote].grid(row=i, column=1, columnspan=2, sticky="w")

        f = self._carte(gauche, "Options", 2, 0)
        for i, (nom, lib) in enumerate(self.CASES, start=1):
            ttk.Checkbutton(f, text=lib, variable=self.v[nom]).grid(row=i, column=0, columnspan=3,
                                                                    sticky="w")

        # --- colonne droite : appariement ---
        droite = ttk.Frame(corps, style="Fond.TFrame")
        droite.grid(row=1, column=1, sticky="nsew")
        droite.columnconfigure(0, weight=1)
        droite.rowconfigure(0, weight=1)
        f = self._carte(droite, "Appariement des deux caméras", 0, 0)

        ttk.Label(f, text="Recalage 2D (sans étalonnage)", foreground=ACCENT,
                  font=self.polices["bouton"]).grid(row=1, column=0, columnspan=3, sticky="w",
                                                    pady=(0, 2))
        self.ent_seuils, _ = self._champ(f, 2, "Seuils", self.v["seuils_recalage"],
                                         "px, du plus large au plus serré", largeur=12)
        ttk.Label(f, text="Modèle").grid(row=3, column=0, sticky="w", padx=(0, 12), pady=4)
        self.cb_modele = ttk.Combobox(f, textvariable=self.v["modele_recalage"], width=11,
                                      state="readonly", values=list(AppariementStereo.MODELES))
        self.cb_modele.grid(row=3, column=1, sticky="w", pady=4)
        self.lbl_modele = ttk.Label(f, style="Aide.TLabel", wraplength=230, justify="left")
        self.lbl_modele.grid(row=3, column=2, sticky="w", padx=(10, 0))

        ttk.Separator(f).grid(row=4, column=0, columnspan=3, sticky="ew", pady=12)

        ttk.Checkbutton(f, text="Utiliser plutôt l'étalonnage stéréo (Lagrange)",
                        variable=self.v["utiliser_etalonnage"]).grid(row=5, column=0, columnspan=3,
                                                                     sticky="w", pady=(0, 2))
        ttk.Label(f, text="Degré Lpform").grid(row=6, column=0, sticky="w", padx=(0, 12), pady=4)
        self.cb_lpform = ttk.Combobox(f, textvariable=self.v["l_pform"], width=6)
        self.cb_lpform.grid(row=6, column=1, sticky="w", pady=4)
        self.lbl_lpform = self._pastille(f)
        self.lbl_lpform.configure(wraplength=230, justify="left")
        self.lbl_lpform.grid(row=6, column=2, sticky="w", padx=(10, 0))
        entrees = [self._champ(f, i, lib, self.v[nom], aide, largeur=8)[0]
                   for i, (nom, lib, _, aide) in enumerate(self.CHAMPS_APPARIEMENT, start=7)]
        self.widgets_calib = [self.cb_lpform, *entrees]

        info = tk.Frame(f, background=INFO_FOND)
        info.grid(row=7 + len(self.CHAMPS_APPARIEMENT), column=0, columnspan=3, sticky="ew",
                  pady=(14, 0))
        ttk.Label(info, style="Info.TLabel", wraplength=480, justify="left",
                  text="Sans étalonnage : les taches de droite, tournées de 180°, sont recalées sur "
                       "celles de gauche, puis appariées au plus proche avec des seuils de plus en "
                       "plus serrés.\nAvec l'étalonnage : on garde la candidate dont le point 3D "
                       "tombe sur le plan de l'échantillon."
                  ).pack(anchor="w", padx=12, pady=10)

        # --- pied : boutons ---
        pied = ttk.Frame(self.root, style="Fond.TFrame", padding=(20, 4, 20, 16))
        pied.grid(row=2, column=0, sticky="ew")
        ttk.Label(pied, text="Entrée : lancer   ·   Échap : annuler", background=FOND,
                  foreground=DISCRET, font=self.polices["petit"]).pack(side="left")
        ttk.Button(pied, text="Lancer", style="Accent.TButton",
                   command=self._on_ok).pack(side="right")
        ttk.Button(pied, text="Annuler", command=self.root.destroy).pack(side="right", padx=(0, 8))
        self.root.bind("<Return>", lambda _e: self._on_ok())
        self.root.bind("<Escape>", lambda _e: self.root.destroy())

    # ----- chemin du dossier de mesure -----

    def _suivre_date(self, *_):
        """Met à jour le chemin d'après la date, sauf s'il a été modifié à la main."""
        if self.v["dossier_mesure"].get() == self._chemin_auto:
            self._chemin_auto = DetectionSpots.chemin_par_defaut(self.v["date"].get().strip())
            self.v["dossier_mesure"].set(self._chemin_auto)

    def _parcourir(self):
        depart = self.v["dossier_mesure"].get().strip()
        d = filedialog.askdirectory(initialdir=depart if os.path.isdir(depart) else ".",
                                    title="Dossier contenant video_extenso_left et video_extenso_right")
        if d:
            # chemin relatif si le dossier est sous le dossier courant (plus lisible)
            rel = os.path.relpath(d)
            self.v["dossier_mesure"].set(d if rel.startswith("..") else rel)

    # ----- vérifications en direct -----

    def _maj_nb_images(self, *_):
        """Rappelle combien d'images seront réellement traitées (+1 : l'image 0)."""
        try:
            n = int(self.v["max_images_a_considerer"].get())
            texte = f"après l'image 0 → {n + 1} images traitées"
        except ValueError:
            texte = "après l'image 0 "
        self.lbl_nb_images.configure(text=texte)

    def _maj_aide_modele(self, *_):
        self.lbl_modele.configure(text=self.MODELES_AIDE.get(self.v["modele_recalage"].get(), ""))

    def _maj_mode(self, *_):
        """Active les champs de la méthode d'appariement choisie."""
        calib = self.v["utiliser_etalonnage"].get()
        for w in self.widgets_calib:
            w.state(["!disabled"] if calib else ["disabled"])
        self.ent_seuils.state(["disabled"] if calib else ["!disabled"])
        self.cb_modele.state(["disabled"] if calib else ["!disabled", "readonly"])
        self._maj_essai()

    def _essai_courant(self):
        """DetectionSpots portant seulement la date et le dossier saisis (pour les chemins)."""
        return DetectionSpots(date=self.v["date"].get().strip(),
                              dossier_mesure=self.v["dossier_mesure"].get().strip() or None)

    @staticmethod
    def _lpforms_disponibles(essai):
        """Degrés Lagrange pour lesquels un L_constants.npy existe."""
        degres = set()
        for motif in essai.candidats_L_constants(l_pform="*"):
            for f in glob.glob(motif):
                r = re.search(r"Lpform_(\d+)", f)
                if r:
                    degres.add(int(r.group(1)))
        return sorted(degres)

    def _maj_essai(self, *_):
        essai = self._essai_courant()
        d = essai.dossier_images
        ok = all(os.path.isdir(d + f"video_extenso_{c}") for c in ("left", "right"))
        if ok:
            self._etat(self.lbl_dossier, "✔  video_extenso_left et video_extenso_right trouvés", "ok")
        else:
            self._etat(self.lbl_dossier, "✘  video_extenso_left / video_extenso_right introuvables", "err")
        self.lbl_resultats.configure(text=f"Résultats enregistrés dans  {essai.dossier}")

        for cote, nom, _ in self.REPRISE:
            if all(os.path.isfile(p) for p in essai.fichiers_reprise(cote)):
                self.cases_reprise[cote].state(["!disabled"])
                self._etat(self.lbl_reprise[cote], "résultats précédents trouvés", "ok")
            else:
                self.v[nom].set(False)
                self.cases_reprise[cote].state(["disabled"])
                self._etat(self.lbl_reprise[cote], "aucun : suivi complet")

        degres = self._lpforms_disponibles(essai)
        self.cb_lpform.configure(values=[str(n) for n in degres])
        liste = ", ".join(map(str, degres))
        if not self.v["utiliser_etalonnage"].get():
            self._etat(self.lbl_lpform, "non utilisé")
        elif degres:
            if self.v["l_pform"].get().strip() in map(str, degres):
                self._etat(self.lbl_lpform, f"✔  disponibles : {liste}", "ok")
            else:
                self._etat(self.lbl_lpform, f"⚠  pas ce degré (disponibles : {liste}) : "
                                            "recalage 2D à la place", "avert")
        else:
            self._etat(self.lbl_lpform, "⚠  aucun étalonnage trouvé : recalage 2D à la place", "avert")

    # ----- validation -----

    def _on_ok(self):
        params, erreurs = {}, []
        calib = self.v["utiliser_etalonnage"].get()
        params["utiliser_etalonnage"] = calib
        params["date"] = self.v["date"].get().strip()
        params["dossier_mesure"] = self.v["dossier_mesure"].get().strip()
        for nom, lib, typ, _ in self.CHAMPS_SUIVI + self.CHAMPS_APPARIEMENT:
            txt = self.v[nom].get().strip()
            try:
                params[nom] = typ(txt.replace(",", "."))
            except ValueError:
                erreurs.append(f"{lib} : « {txt} » n'est pas un nombre valide")
        try:
            params["l_pform"] = int(self.v["l_pform"].get())
        except ValueError:
            if calib:
                erreurs.append("Degré Lpform : entier attendu")
            else:
                params["l_pform"] = DetectionSpots().l_pform   # inutilisé sans étalonnage
        txt = self.v["seuils_recalage"].get().strip()
        try:
            seuils = tuple(float(s) for s in re.split(r"[;,\s]+", txt) if s)
            if not seuils or min(seuils) <= 0:
                raise ValueError
            params["seuils_recalage"] = seuils
        except ValueError:
            erreurs.append(f"Seuils de recalage : « {txt} » invalide (nombres positifs, ex. 80 30 10)")
        params["modele_recalage"] = self.v["modele_recalage"].get()
        for nom, _ in self.CASES:
            params[nom] = self.v[nom].get()
        for _, nom, _ in self.REPRISE:
            params[nom] = self.v[nom].get()

        if not erreurs:
            if not re.fullmatch(r"\d{4}_\d{2}_\d{2}", params["date"]):
                erreurs.append("Date attendue au format AAAA_MM_JJ")
            if params["taille_min_pix"] >= params["taille_max_pix"]:
                erreurs.append("L'aire min doit être inférieure à l'aire max")
            if min(params["pix"], params["taille_min_pix"], params["max_images_a_considerer"]) <= 0:
                erreurs.append("Les valeurs de suivi doivent être positives")
            if calib and (params["rayon_recherche"] <= 0 or params["tolerance_plan"] <= 0):
                erreurs.append("Le rayon et la tolérance doivent être positifs")
        if erreurs:
            messagebox.showerror("Paramètres invalides", "\n".join(erreurs))
            return

        # étalonnage demandé mais absent : pas bloquant, lancer() apparie par recalage 2D
        self.result = DetectionSpots(**params)
        self.root.destroy()


def run_coord_gui():
    """Demande les paramètres puis lance la détection.

    Renvoie l'objet DetectionSpots (résultats en attributs : Lp, paires, ...), ou None si annulé.
    """
    detection = DetectionSpotsGUI().ask()
    if detection is None:
        print("Annulé")
        return None
    print("Paramètres :", detection.parametres())
    detection.lancer()
    return detection