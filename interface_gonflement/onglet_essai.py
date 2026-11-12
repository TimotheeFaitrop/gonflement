"""Onglet Essai : paramètres du pilotage, valeurs et commandes en direct, courbes."""

import json
import math
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

try:
    from . import reglages as rg
    from .courbes import Courbes
    from .widgets import Bulle, CadreDefilant
except ImportError:
    import reglages as rg
    from courbes import Courbes
    from widgets import Bulle, CadreDefilant

ETATS = {0: "attente", 1: "rampe", 2: "palier", 3: "fin du profil", 4: "pause", 5: "SÉCURITÉ"}
UNITES = {"debit": ("mL/min", "mL/min/s"), "pression": ("(unité P)", "(unité P)/s"),
          "deformation": ("%", "%/s")}
TITRES = {"debit": "Consigne de débit", "pression": "Consigne de pression",
          "deformation": "Consigne de déformation"}


def limite_utile(cle, mode):
    """Une limite n'a de sens que si la grandeur n'est pas déjà fixée par la consigne :
    en mode débit la consigne EST le débit, en mode pression elle EST la pression."""
    return not ((cle == "debit_max" and mode == "debit")
                or (cle == "pression_max" and mode == "pression"))


CLES_PROFIL = ("essai.mode",
               "essai.debit.consigne", "essai.debit.duree_rampe", "essai.debit.attente",
               "essai.debit.duree_palier",
               "essai.pression.consigne", "essai.pression.vitesse", "essai.pression.duree_palier",
               "essai.deformation.eps_max", "essai.deformation.vitesse",
               "essai.deformation.duree_palier")


def profil_prevu(app):
    """Consigne prévue en fonction du temps, d'après les champs de l'onglet.
    Renvoie None si une valeur est invalide, sinon un dict :
      points   [(t, y), ...]            courbe de consigne
      illimite True si le palier n'a pas de fin (la dernière portion est alors indicative)
      t_palier instant où le palier commence
      duree    durée totale (None si illimitée)."""
    n, mode = app.nombre, app.v("essai.mode").get()
    if mode == "debit":
        y, rampe, attente, palier = (n("essai.debit.consigne"), n("essai.debit.duree_rampe"),
                                     n("essai.debit.attente"), n("essai.debit.duree_palier"))
        if None in (y, rampe, attente, palier) or y < 0 or rampe < 0 or attente < 0:
            return None
        pts = [(0.0, 0.0)]
        if attente > 0:
            pts.append((attente, 0.0))
        pts.append((attente + rampe, y))                # rampe = 0 : échelon vertical
        note = ""
    else:
        cle = "pression" if mode == "pression" else "deformation"
        y = n("essai.pression.consigne" if mode == "pression" else "essai.deformation.eps_max")
        vit, palier = n(f"essai.{cle}.vitesse"), n(f"essai.{cle}.duree_palier")
        if None in (y, vit, palier) or y < 0 or vit <= 0:
            return None
        pts = [(0.0, 0.0), (y / vit, y)]
        note = "  (montée supposée depuis 0)"
    if palier < 0:
        return None
    t = pts[-1][0]
    illimite = palier == 0
    pts.append((t + (max(0.35 * t, 10.0) if illimite else palier), y))
    return {"points": pts, "illimite": illimite, "t_palier": t, "note": note,
            "duree": None if illimite else pts[-1][0]}


def _pas_propre(vmax, n=4):
    """Pas de graduation « rond » (1, 2, 2.5, 5 × 10^k) donnant environ n graduations."""
    brut = vmax / n
    mag = 10 ** math.floor(math.log10(brut))
    return next(m * mag for m in (1, 2, 2.5, 5, 10) if brut <= m * mag * (1 + 1e-9))


class ProfilPrevu(tk.Canvas):
    """Courbe de consigne prévue de l'essai, affichée avant son lancement."""

    def __init__(self, parent, palette, hauteur=165):
        self.P = palette
        try:
            fond = palette["panneau"]
        except Exception:
            fond = "#ffffff"
        super().__init__(parent, height=hauteur, bg=fond, highlightthickness=1,
                         highlightbackground="#888888")
        self.titre, self.unite, self.profil = "", "", None
        self.bind("<Configure>", lambda _e: self.dessiner())

    def afficher(self, titre, unite, profil):
        self.titre, self.unite, self.profil = titre, unite, profil
        self.dessiner()

    def dessiner(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 120 or h < 80:
            return
        r, g, b = (c / 65535 for c in self.winfo_rgb(self.cget("bg")))
        clair = 0.299 * r + 0.587 * g + 0.114 * b > 0.5
        fg, grille = ("#222222", "#d0d0d0") if clair else ("#dddddd", "#4a4a4a")
        try:
            trace = self.P["accent"]
        except Exception:
            trace = "#2a7de1"
        police = ("TkDefaultFont", 8)
        p = self.profil
        if p is None:
            self.create_text(w / 2, h / 2, fill=fg, text="Profil prévu : valeurs de consigne invalides")
            return
        gauche, droite, haut, bas = 56, 16, 24, 26
        x0, x1, ybas, yhaut = gauche, w - droite, h - bas, haut
        pts = p["points"]
        tmax = pts[-1][0] or 1.0
        ymax = max(y for _, y in pts) or 1.0
        pas_y, pas_t = _pas_propre(ymax), _pas_propre(tmax, 6)
        ymax = math.ceil(ymax / pas_y - 1e-9) * pas_y

        def X(t):
            return x0 + (x1 - x0) * t / tmax

        def Y(y):
            return ybas - (ybas - yhaut) * y / ymax

        k = 0
        while k * pas_y <= ymax * (1 + 1e-9):
            self.create_line(x0, Y(k * pas_y), x1, Y(k * pas_y), fill=grille)
            self.create_text(x0 - 5, Y(k * pas_y), text=f"{k * pas_y:g}", anchor="e", fill=fg, font=police)
            k += 1
        k = 0
        while k * pas_t <= tmax * (1 + 1e-9):
            self.create_line(X(k * pas_t), yhaut, X(k * pas_t), ybas, fill=grille)
            self.create_text(X(k * pas_t), ybas + 4, text=f"{k * pas_t:g}", anchor="n", fill=fg, font=police)
            k += 1
        self.create_line(x0, yhaut, x0, ybas, x1, ybas, fill=fg)

        plein = pts[:-1] if p["illimite"] else pts
        self.create_line(*[c for t, y in plein for c in (X(t), Y(y))], fill=trace, width=2)
        if p["illimite"]:
            (ta, ya), (tb, yb) = pts[-2], pts[-1]
            self.create_line(X(ta), Y(ya), X(tb), Y(yb), fill=trace, width=2, dash=(5, 3))
            self.create_text((X(ta) + X(tb)) / 2, Y(yb) - 4, text="palier illimité", anchor="s",
                             fill=fg, font=police)
        self.create_text(x0, 4, anchor="nw", fill=fg, font=("TkDefaultFont", 9, "bold"),
                         text=f"{self.titre} prévue ({self.unite}){p['note']}")
        bilan = (f"palier atteint à t = {p['t_palier']:g} s" if p["illimite"]
                 else f"durée totale {p['duree']:g} s")
        self.create_text(x1, 4, anchor="ne", fill=fg, font=police, text=bilan)
        self.create_text(x1, h - 3, anchor="se", fill=fg, font=police, text="t (s)")


class OngletEssai(ttk.Frame):

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = a = app
        self.en_cours = False
        self.en_pause = False
        self.mode_en_cours = None
        self.dossier = None
        gauche = CadreDefilant(self, largeur=420, fond=a.P["fond"])
        gauche.pack(side="left", fill="y")
        self.colonne_parametres(gauche.interieur)
        droite = ttk.Frame(self)
        droite.pack(side="left", fill="both", expand=True, padx=8)
        self.panneau_direct(droite)
        self.courbes = Courbes(droite, a.P)
        self.courbes.pack(fill="both", expand=True, pady=(6, 4))
        # profil de consigne prévu : visible tant qu'aucun essai n'est en cours (voir etat_boutons)
        self.profil = ProfilPrevu(droite, a.P)
        self._profil_en_attente = None
        for cle in CLES_PROFIL:
            a.v(cle).trace_add("write", lambda *_: self.planifier_profil())
        self.etat_boutons()
        self.maj_mode()
        self.maj_source()

    # ================================================================ paramètres
    def colonne_parametres(self, g):
        a = self.app
        f = a.cadre(g, "Échantillon et mode de pilotage")
        a.champ(f, 0, "Échantillon", "essai.echantillon", largeur=24)
        # même variable que le « Dossier racine » de l'onglet Calibration : choisi ici, il l'est là-bas
        a.chemin_choisi(f, 1, "Dossier racine", "materiel.dossier_racine", dossier=True, largeur=22)
        a.chemin_choisi(f, 2, "Dossier de l'essai", "essai.dossier", dossier=True, largeur=22)
        self.lbl_prevu = a.note(f, 3, "")
        for cle in ("essai.echantillon", "essai.dossier", "materiel.dossier_racine"):
            a.v(cle).trace_add("write", lambda *_: self.maj_prevu())
        self.maj_prevu()
        modes = ttk.Frame(f)
        modes.grid(row=4, column=0, columnspan=3, sticky="w", padx=4, pady=4)
        for i, (val, txt) in enumerate((("debit", "Débit"), ("pression", "Pression"),
                                        ("deformation", "Déformation"))):
            ttk.Radiobutton(modes, text=txt, value=val, variable=a.v("essai.mode"),
                            command=self.maj_mode).grid(row=0, column=i, padx=8)

        self.cadre_consigne = a.cadre(g, "Consigne")
        self.cadres = {m: ttk.Frame(self.cadre_consigne) for m in TITRES}

        c = self.cadres["debit"]
        a.champ(c, 0, "Débit de consigne", "essai.debit.consigne", "mL/min")
        a.champ(c, 1, "Durée de la rampe", "essai.debit.duree_rampe", "s",
                aide="Montée de 0 à la consigne (0 = échelon)")
        a.champ(c, 2, "Attente à débit nul", "essai.debit.attente", "s")
        a.champ(c, 3, "Durée du palier", "essai.debit.duree_palier", "s (0 = illimité)")
        a.note(c, 4, "Pause = débit coupé.")

        c = self.cadres["pression"]
        a.champ(c, 0, "Pression de consigne", "essai.pression.consigne", "(unité P)",
                aide="Unité du débitmètre (absolue ou relative, voir Matériel)")
        a.champ(c, 1, "Vitesse de montée", "essai.pression.vitesse", "(unité P)/s")
        a.champ(c, 2, "Durée du palier", "essai.pression.duree_palier", "s (0 = illimité)")
        self._pi(c, 3, "pression", "unité P")
        a.note(c, 7, "Pause = maintien à la pression atteinte.")

        c = self.cadres["deformation"]
        a.choix(c, 0, "Mesure", "essai.deformation.source", ["3D", "2D"],
                commande=self.maj_source)
        a.choix(c, 1, "Composante", "essai.deformation.composante",
                ["toutes", "exx", "eyy", "moyenne", "max"])
        self.choix_camera = a.choix(c, 2, "Caméra (2D)", "essai.deformation.camera",
                                    ["moyenne", "droite", "gauche"])
        a.champ(c, 3, "Déformation visée", "essai.deformation.eps_max", "%")
        a.champ(c, 4, "Vitesse de déformation", "essai.deformation.vitesse", "%/s")
        a.champ(c, 5, "Durée du palier", "essai.deformation.duree_palier", "s (0 = illimité)")
        self._pi(c, 6, "deformation", "%")
        a.champ(c, 10, "Anticipation Kff", "essai.deformation.kff", "mL/min par %/s",
                aide="Débit ajouté proportionnel à la vitesse de rampe (0 = désactivé)")
        a.champ(c, 11, "Coupure sans mesure", "essai.deformation.timeout_mesure", "s",
                aide="Débit coupé si plus aucune déformation n'arrive (taches perdues)")
        self.cadre_3d = ttk.LabelFrame(c, text="Stéréo-corrélation 3D (Pycaso)", padding=4)
        self.cadre_3d.grid(row=12, column=0, columnspan=3, sticky="ew", padx=4, pady=6)
        d = self.cadre_3d
        a.choix(d, 0, "Modèle", "essai.deformation.methode_3d", ["Zernike", "Lagrange"])
        a.chemin_choisi(d, 1, "Constantes", "essai.deformation.fichier_constantes", largeur=22)
        a.champ(d, 2, "Degré", "essai.deformation.pform",
                aide="Lu dans le nom du dossier (nZ_12 -> 12)")
        a.case(d, 3, "Caméra droite en miroir (tournée de 180°)",
               "essai.deformation.rotation_droite")
        ttk.Button(d, text="Prendre la dernière calibration",
                   command=self.derniere_calibration).grid(row=4, column=0, columnspan=3,
                                                           sticky="w", padx=8, pady=4)
        a.v("essai.deformation.fichier_constantes").trace_add("write", lambda *_: self.degre_auto())
        self.lbl_source = a.note(c, 13, "")
        a.note(c, 14, "Pause = maintien de la déformation atteinte.")

        f = a.cadre(g, "Sécurité")
        a.champ(f, 0, "Pression maximale", "essai.pression_max", "(unité P)",
                aide="Au-delà, le débit est coupé définitivement")
        a.champ(f, 1, "Débit maximal", "essai.debit_max", "mL/min")
        # widgets de chaque ligne, pour pouvoir les masquer selon le mode (voir maj_securite)
        self.lignes_secu = {cle: f.grid_slaves(row=i)
                            for i, cle in enumerate(("pression_max", "debit_max"))}
        a.champ(f, 2, "Variation max du débit", "essai.vitesse_cmd_max", "mL/min/s")
        a.champ(f, 3, "Durée maximale", "essai.duree_max", "s")
        a.case(f, 4, "Arrêter l'essai à la fin du profil", "essai.arret_auto")

        f = a.cadre(g, "Acquisition")
        a.champ(f, 0, "Fréquence des images", "essai.freq_cam", "Hz",
                aide="Déclenchement des deux caméras par le FT232R")
        a.case(f, 1, "Enregistrer les images", "essai.sauver_images")
        a.case(f, 2, "Ouvrir aussi les fenêtres Grapher de crappy", "essai.graphers_crappy")

        f = ttk.Frame(g)
        f.pack(fill="x", padx=8, pady=10)
        self.btn_go = ttk.Button(f, text="▶  Démarrer l'essai", style="Go.TButton",
                                 command=self.demarrer)
        self.btn_go.pack(fill="x", pady=2)
        self.btn_relancer = ttk.Button(f, text="↻  Relancer le même essai", command=self.relancer)
        self.btn_relancer.pack(fill="x", pady=2)
        Bulle(self.btn_relancer, "Mêmes paramètres que l'essai précédent, nouveau dossier "
                                 "Mesure_0000N (les champs modifiés depuis sont ignorés)")
        self.btn_stop = ttk.Button(f, text="■  Arrêter l'essai", command=a.arreter,
                                   state="disabled")
        self.btn_stop.pack(fill="x", pady=2)
        ttk.Button(f, text="ARRÊT D'URGENCE", style="Danger.TButton",
                   command=a.arret_urgence).pack(fill="x", pady=(10, 2), ipady=4)
        ttk.Label(f, text="Urgence : débit coupé et essai tué immédiatement.",
                  style="Petit.TLabel").pack(anchor="w")

    def _pi(self, c, ligne, mode, unite):
        ttk.Separator(c).grid(row=ligne, column=0, columnspan=3, sticky="ew", pady=4)
        self.app.note(c, ligne + 1, "Régulateur PI → débit")
        self.app.champ(c, ligne + 2, "Kp", f"essai.{mode}.kp", f"mL/min par {unite}")
        self.app.champ(c, ligne + 3, "Ki", f"essai.{mode}.ki", f"mL/min par {unite}·s")

    # ================================================================ en direct
    def panneau_direct(self, droite):
        val = ttk.Frame(droite)
        val.pack(fill="x", pady=(8, 4))
        self.tuiles = {}
        for i, (cle, titre) in enumerate((("press", "Pression"), ("debit", "Débit (mL/min)"),
                                          ("eps", "Déformation (%)"), ("etat", "État"),
                                          ("t", "Temps (s)"))):
            carte = ttk.Frame(val, style="Carte.TFrame", padding=(10, 6))
            carte.grid(row=0, column=i, sticky="nsew", padx=3)
            val.columnconfigure(i, weight=1)
            ttk.Label(carte, text=titre, style="Carte.TLabel").pack(anchor="w")
            self.tuiles[cle] = ttk.Label(carte, text="—", style="Valeur.TLabel")
            self.tuiles[cle].pack(anchor="w")

        cmd = ttk.LabelFrame(droite, text="Pilotage en direct", padding=4)
        cmd.pack(fill="x", pady=4)
        self.boutons_direct, self.unites = [], []
        self.saisies = {}
        for ligne, (texte, action) in enumerate((("Nouvelle consigne", "consigne"),
                                                 ("Nouvelle vitesse", "vitesse"))):
            var = self.saisies[action] = tk.StringVar()
            ttk.Label(cmd, text=texte).grid(row=ligne, column=0, padx=8, pady=3, sticky="w")
            ttk.Entry(cmd, textvariable=var, width=10).grid(row=ligne, column=1)
            u = ttk.Label(cmd, text="", style="Petit.TLabel", width=11)
            u.grid(row=ligne, column=2, sticky="w", padx=4)
            self.unites.append(u)
            b = ttk.Button(cmd, text="Appliquer",
                           command=lambda act=action, v=var: self.envoyer_valeur(act, v))
            b.grid(row=ligne, column=3, padx=4)
            self.boutons_direct.append(b)
        ttk.Separator(cmd, orient="vertical").grid(row=0, column=4, rowspan=2, sticky="ns", padx=10)
        self.btn_pause = ttk.Button(cmd, text="⏸  Pause", width=14, command=self.basculer_pause)
        self.btn_pause.grid(row=0, column=5, padx=4)
        b = ttk.Button(cmd, text="Terminer le profil", width=16, command=self.terminer_profil)
        b.grid(row=1, column=5, padx=4)
        Bulle(b, "Coupe le débit et arrête la prise de points : l'essai se termine")
        self.boutons_direct += [self.btn_pause, b]
        self.lbl_dossier = ttk.Label(cmd, text="", style="Petit.TLabel")
        self.lbl_dossier.grid(row=0, column=6, padx=10, sticky="w")
        ttk.Button(cmd, text="Ouvrir le dossier de l'essai",
                   command=lambda: self.dossier and self.app.ouvrir(Path(self.dossier))
                   ).grid(row=1, column=6, padx=10, sticky="w")
        cmd.columnconfigure(6, weight=1)
        self.etat_boutons()

    def afficher(self, p):
        """Met à jour les tuiles avec le dernier paquet de mesures."""
        def f(x, fmt):
            return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else fmt.format(x)
        self.tuiles["press"].configure(text=f(p.get("press"), "{:.1f}"))
        self.tuiles["debit"].configure(text=f(p.get("volumetric_flow"), "{:.2f}") + (
            f"  (cmd {p['debit_cmd']:.1f})" if "debit_cmd" in p else ""))
        self.tuiles["eps"].configure(text=f(p.get("eps"), "{:.2f}") + (
            f"  (uz {p['uz_3d']:.2f} mm)" if "uz_3d" in p else ""))
        etat = p.get("etat")
        self.tuiles["etat"].configure(
            text=ETATS.get(int(etat), "?") if etat is not None else "—",
            foreground=self.app.P["rouge" if etat == 5 else "accent"])
        self.tuiles["t"].configure(text=f(p.get("t"), "{:.0f}"))

    # ================================================================ mises à jour
    def maj_mode(self):
        mode = self.app.v("essai.mode").get()
        for c in self.cadres.values():
            c.pack_forget()
        self.cadres[mode].pack(fill="x", padx=2, pady=2)
        self.cadre_consigne.configure(text=TITRES[mode])
        for u, txt in zip(self.unites, UNITES[mode]):
            u.configure(text=txt)
        self.maj_securite(mode)
        self.maj_profil()
        if not self.en_cours:
            self.courbes.preparer(mode, self.app.nombre("essai.pression_max")
                                  if limite_utile("pression_max", mode) else None)

    def planifier_profil(self):
        """Regroupe les modifications successives des champs en un seul redessin."""
        if self._profil_en_attente is None:
            self._profil_en_attente = self.after_idle(self.maj_profil)

    def maj_profil(self):
        self._profil_en_attente = None
        mode = self.app.v("essai.mode").get()
        self.profil.afficher(TITRES[mode], UNITES[mode][0], profil_prevu(self.app))

    def maj_securite(self, mode):
        """N'affiche que les limites qui ont un sens pour le mode de pilotage."""
        for cle, widgets in self.lignes_secu.items():
            for w in widgets:
                (w.grid if limite_utile(cle, mode) else w.grid_remove)()

    def maj_source(self):
        is3d = self.app.v("essai.deformation.source").get() == "3D"
        (self.cadre_3d.grid if is3d else self.cadre_3d.grid_remove)()
        self.choix_camera.configure(state="disabled" if is3d else "readonly")
        self.lbl_source.configure(text=(
            "3D : taches suivies sur les deux caméras, appariées puis reconstruites avec "
            "l'étalonnage ; déformation = allongement des distances 3D entre taches "
            "(« toutes » = moyenne de toutes les paires)." if is3d else
            "2D : déformation VideoExtenso dans le plan image (faussée quand le dôme se "
            "rapproche des caméras) ; « toutes » = moyenne exx/eyy."))

    def maj_prevu(self):
        a = self.app
        choisi = a.v("essai.dossier").get().strip()
        base = a.chemin(choisi) if choisi else (
            a.chemin(a.v("materiel.dossier_racine").get()) / time.strftime("%Y_%m_%d")
            / a.v("essai.echantillon").get())
        aide = "" if choisi else "  (dossier vide : racine/date/échantillon)"
        self.lbl_prevu.configure(text=f"Données dans : {base}/Mesure…{aide}")

    def degre_auto(self):
        fichier = self.app.v("essai.deformation.fichier_constantes").get()
        n = rg.degre_depuis_chemin(fichier)
        if n is not None:
            self.app.v("essai.deformation.pform").set(str(n))
            self.app.v("essai.deformation.methode_3d").set(
                "Lagrange" if Path(fichier).name.startswith("L_") else "Zernike")

    def derniere_calibration(self):
        """Fichier de constantes le plus récent sous le dossier racine."""
        m = self.app.v("essai.deformation.methode_3d").get()
        motif = "nZ_*/A_Zernike.npy" if m == "Zernike" else "Lpform_*/L_constants.npy"
        racine = self.app.chemin(self.app.v("materiel.dossier_racine").get())
        trouves = sorted(racine.glob(f"**/[Rr]esults_[Cc]alib/{motif}"),
                         key=lambda p: p.stat().st_mtime) if racine.is_dir() else []
        if not trouves:
            messagebox.showinfo("Calibration", f"Aucun {motif} dans {racine}/<date>/results_calib/")
            return
        self.app.v("essai.deformation.fichier_constantes").set(str(trouves[-1]))
        self.app.log(f"Calibration 3D : {trouves[-1]}", "info")

    def etat_boutons(self):
        if self.en_cours and not (self.app.proc and self.app.proc.vivant()):
            self.en_cours = self.en_pause = False      # le processus d'essai n'existe plus
        self.btn_go.configure(state="disabled" if self.en_cours else "normal")
        dernier = (self.app.ICI / "derniere_config_essai.json").is_file()
        self.btn_relancer.configure(state="normal" if dernier and not self.en_cours else "disabled")
        self.btn_stop.configure(state="normal" if self.en_cours else "disabled")
        for b in self.boutons_direct:
            b.configure(state="normal" if self.en_cours else "disabled")
        self.btn_pause.configure(text="▶  Reprendre" if self.en_pause else "⏸  Pause")
        if hasattr(self, "profil"):        # profil prévu : avant / après l'essai seulement
            if self.en_cours:
                self.profil.pack_forget()
            else:
                self.profil.pack(fill="x", pady=(6, 0), before=self.courbes)

    # ================================================================ lancement
    def demarrer(self):
        a = self.app
        if a.occupe():
            return
        try:
            cfg = a.collecter()
        except ValueError as e:
            messagebox.showerror("Réglage invalide", str(e))
            return
        erreurs = verifier(cfg)
        if erreurs:
            messagebox.showerror("Paramètres à corriger", "\n".join(erreurs))
            return
        if not messagebox.askokcancel("Démarrer l'essai ?", resume(cfg)):
            return
        fichier = a.ecrire_config("derniere_config_essai.json")
        if fichier is not None:
            a.preparer_cameras(lambda: self._lancer(fichier, cfg))

    def relancer(self):
        """Relance l'essai précédent avec exactement les mêmes paramètres."""
        a = self.app
        fichier = a.ICI / "derniere_config_essai.json"
        if a.occupe() or not fichier.is_file():
            return
        with open(fichier, encoding="utf-8") as f:
            cfg = json.load(f)
        if not messagebox.askokcancel("Relancer l'essai ?", "Mêmes paramètres que l'essai "
                                      "précédent, données dans un nouveau dossier Mesure.\n\n"
                                      + resume(cfg)):
            return
        a.preparer_cameras(lambda: self._lancer(fichier, cfg))

    def _lancer(self, fichier, cfg):
        a = self.app
        if not a.ecouter_mesures(cfg["materiel"]["port_udp_donnees"]):
            return
        mode = cfg["essai"]["mode"]
        self.courbes.donnees.clear()
        self.courbes.preparer(mode, cfg["essai"]["pression_max"]
                              if limite_utile("pression_max", mode) else None)
        self.dossier = None
        self.lbl_dossier.configure(text="")

        def sur_ligne(l):
            if l.startswith("DOSSIER_ESSAI="):
                self.dossier = l.split("=", 1)[1]
                self.lbl_dossier.configure(text=Path(self.dossier).name)

        def fin(code):
            self.en_cours = self.en_pause = False
            self.etat_boutons()
            if self.dossier:
                a.log(f"Données enregistrées dans {self.dossier}", "info")
            a.log("Essai terminé : « Relancer le même essai » pour en refaire un "
                  "identique, ou modifier les paramètres puis « Démarrer ».", "info")

        if a.lancer(f"Essai ({mode})", [a.python(), "-u", str(a.ICI / "lancer_essai.py"),
                                        str(fichier)], sur_fin=fin, sur_ligne=sur_ligne):
            self.en_cours, self.en_pause, self.mode_en_cours = True, False, mode
            self.etat_boutons()

    def envoyer_valeur(self, action, var):
        try:
            x = float(var.get().replace(",", "."))
        except ValueError:
            messagebox.showerror("Valeur invalide", f"« {var.get()} » n'est pas un nombre")
            return
        mode = self.mode_en_cours or self.app.v("essai.mode").get()
        self.app.commande({"action": action, "valeur": x})
        unite = UNITES[mode][0 if action == "consigne" else 1]
        self.app.log(f"→ {action} = {x} {unite}", "info")

    def terminer_profil(self):
        """Fin du profil : débit coupé, puis arrêt de l'essai (donc de la prise de points),
        que « Arrêter l'essai à la fin du profil » soit coché ou non
        (le pilotage, blocs_pilotage.py, passe alors en arrêt automatique)."""
        a = self.app
        a.commande({"action": "fin"})
        a.log("→ fin du profil : débit coupé, arrêt de la prise de points", "info")

    def basculer_pause(self):
        self.en_pause = not self.en_pause
        self.app.commande({"action": "pause" if self.en_pause else "reprendre"})
        self.etat_boutons()


def verifier(cfg):
    e, ess = [], cfg["essai"]
    d = ess["deformation"]
    if not ess["echantillon"]:
        e.append("Nom d'échantillon vide")
    if ess["freq_cam"] <= 0:
        e.append("Fréquence des images doit être > 0")
    if limite_utile("debit_max", ess["mode"]) and ess["debit_max"] <= 0:
        e.append("Débit maximal doit être > 0")
    if ess["mode"] == "deformation":
        if d["vitesse"] <= 0:
            e.append("Vitesse de déformation doit être > 0")
        if d["source"] == "3D" and not cfg["materiel"]["simulation"] \
                and not Path(d["fichier_constantes"]).is_file():
            e.append("Constantes de calibration 3D introuvables : "
                     f"{d['fichier_constantes'] or '(vide)'}\n"
                     "(results_calib/nZ_<degré>/A_Zernike.npy)")
    return e


def resume(cfg):
    ess = cfg["essai"]
    d, p, q = ess["deformation"], ess["pression"], ess["debit"]
    txt = {"debit": f"Débit {q['consigne']} mL/min (rampe {q['duree_rampe']} s)",
           "pression": f"Pression {p['consigne']} à {p['vitesse']} /s",
           "deformation": f"Déformation {d['eps_max']} % à {d['vitesse']} %/s "
                          f"(mesure {d['source']})"}[ess["mode"]]
    secu = []
    if limite_utile("pression_max", ess["mode"]):
        secu.append(f"P max {ess['pression_max']}")
    if limite_utile("debit_max", ess["mode"]):
        secu.append(f"débit max {ess['debit_max']} mL/min")
    secu.append(f"durée max {ess['duree_max']} s")
    txt = f"Échantillon : {ess['echantillon']}\n{txt}\n\nSécurité : {', '.join(secu)}\n\n"
    if cfg["materiel"]["simulation"]:
        return txt + "MODE SIMULATION (aucun matériel)."
    return txt + ("Vérifier : échantillon serré, compresseur ouvert, caméras / FT232R / "
                  "débitmètre branchés.\nLes fenêtres VideoExtenso vont s'ouvrir : "
                  "sélectionner les mêmes taches sur les deux caméras puis les fermer.")
