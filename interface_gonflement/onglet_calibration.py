"""Onglet Calibration : reprend les programmes du dépôt.

  1. Réglage       reglage_hauteur_init.py / _debut_exp.py / _reinit.py
  2. Essai, plans  champs de Pycaso/calibration_gui.py (date, dossier, z départ, pas, nb plans)
  3. Acquisition   calib_crappy_V2.py (expositions 41389 / 28757 µs, déclenchement matériel)
  4. Méthode       Pycaso/calibration_gui.py (Lagrange 4 / 10 it., Soloff 332 / 8, Zernike 6 / 9)
"""

import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

try:
    from . import reglages as rg
    from .widgets import CadreDefilant
except ImportError:
    import reglages as rg
    from widgets import CadreDefilant

# Comme METHOD_DEFAULTS de Pycaso/calibration_gui.py : (valeurs, degré, itérations)
METHODES = {
    "Lagrange": ([str(i) for i in range(1, 9)], "4", 10),
    "Soloff": (["111", "221", "222", "332", "333", "443", "444", "554", "555"], "332", 8),
    "Zernike": ([str(i) for i in range(2, 16)], "6", 9),
}
LIBELLES = {"Lagrange": "Degré (Lpform)", "Soloff": "Forme (aab)", "Zernike": "Ordre (nZ)"}
NCX, NCY, SQR = 12, 12, 7.5        # mire ChArUco fixée dans Pycaso/calibration_class.py


class OngletCalibration(ttk.Frame):

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = a = app
        col = CadreDefilant(self, largeur=680, fond=a.P["fond"])
        col.pack(side="left", fill="both", expand=True)
        g = col.interieur
        self.reglage(a.cadre(g, "1. Réglage du plateau et des caméras"))
        self.essai_plans(a.cadre(g, "2. Essai et plans z (mm)"))
        self.acquisition(a.cadre(g, "3. Acquisition des images (calib_crappy_V2)"))
        self.methode(a.cadre(g, "4. Méthode et calcul (Pycaso)"))

    # ----------------------------------------------------------------- 1
    def reglage(self, f):
        a = self.app
        port = lambda: a.v("materiel.port_imprimante").get()  # noqa: E731
        b = ttk.Frame(f)
        b.grid(row=0, column=0, columnspan=4, sticky="w", padx=4, pady=4)
        ttk.Button(b, text="Réglage initial (aperçu puis Z 20 → 120)",
                   command=self.reglage_init).pack(side="left", padx=3)
        ttk.Button(b, text="Début d'essai (Z = 70)", command=lambda: a.outil(
            "Plateau en début d'essai", "aller_z", port(), 70, "--origine")).pack(side="left", padx=3)
        ttk.Button(b, text="Réinitialiser (Z = 120)", command=lambda: a.outil(
            "Plateau réinitialisé", "aller_z", port(), 120, "--origine")).pack(side="left", padx=3)
        a.note(f, 1, "Comme reglage_hauteur_init.py : origine, aperçu des deux caméras (fermer "
                     "la fenêtre une fois la mire visible), puis Z = 20 et Z = 120 mm pour "
                     "vérifier la netteté.", 620)
        b = ttk.Frame(f)
        b.grid(row=2, column=0, columnspan=4, sticky="w", padx=4, pady=4)
        ttk.Button(b, text="Origine Z (G28)", command=lambda: a.outil(
            "Origine Z", "origine", port())).pack(side="left", padx=3)
        ttk.Button(b, text="Aperçu seul", command=lambda: self._apercu("apercu")
                   ).pack(side="left", padx=3)
        ttk.Button(b, text="Tester les caméras", command=lambda: a.outil(
            "Test caméras", "test_cameras", a.v("materiel.sn_gauche").get(),
            a.v("materiel.sn_droite").get())).pack(side="left", padx=3)
        a.champ(f, 3, "Aller à Z", "calibration.z_reglage", "mm")
        self.origine_avant = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="origine avant", variable=self.origine_avant
                        ).grid(row=3, column=3, padx=6, sticky="w")
        ttk.Button(f, text="Aller", command=self.aller_z).grid(row=3, column=4, padx=4)

    def _apercu(self, action):
        a = self.app
        extra = [a.v("materiel.port_imprimante").get()] if action == "reglage_init" else []
        a.outil("Aperçu caméras", action, a.v("materiel.sn_gauche").get(),
                a.v("materiel.sn_droite").get(), a.v("calibration.expo_gauche").get(),
                a.v("calibration.expo_droite").get(), *extra)

    def reglage_init(self):
        self._apercu("reglage_init")

    def aller_z(self):
        z = self.app.nombre("calibration.z_reglage")
        if z is None or not 0 <= z <= 200:
            return messagebox.showerror("Hauteur", "Hauteur hors plage (0–200 mm)")
        extra = ["--origine"] if self.origine_avant.get() else []
        self.app.outil(f"Plateau à Z = {z}", "aller_z",
                       self.app.v("materiel.port_imprimante").get(), z, *extra)

    # ----------------------------------------------------------------- 2
    def essai_plans(self, f):
        a = self.app
        a.v("calibration.date").set(time.strftime("%Y_%m_%d"))   # aujourd'hui, comme l'original
        a.champ(f, 0, "Date (AAAA_MM_JJ)", "calibration.date", largeur=14)
        a.chemin_choisi(f, 1, "Dossier images calib", "calibration.dossier_images",
                        dossier=True, largeur=44)
        self.lbl_resultats = a.note(f, 2, "", 620)
        # le dossier suit la date tant qu'il n'a pas été modifié à la main
        self.auto = self._chemin_auto()
        memo = a.v("calibration.dossier_images").get().strip()
        if not memo or a.v("calibration.date").get() not in memo:
            a.v("calibration.dossier_images").set(self.auto)   # dossier du jour par défaut
        a.v("calibration.date").trace_add("write", lambda *_: self._suivre_date())
        a.v("materiel.dossier_racine").trace_add("write", lambda *_: self._suivre_date())
        a.v("calibration.dossier_images").trace_add("write", lambda *_: self._maj_resultats())
        self._maj_resultats()

        ligne = ttk.Frame(f)
        ligne.grid(row=3, column=0, columnspan=4, sticky="w", padx=4, pady=4)
        for txt, cle in (("z départ", "z_depart"), ("pas", "pas_z"), ("nb plans", "n_plans")):
            ttk.Label(ligne, text=txt).pack(side="left", padx=(8, 4))
            ttk.Entry(ligne, textvariable=a.v(f"calibration.{cle}"), width=7).pack(side="left")
        self.lbl_plans = a.note(f, 4, "", 620)
        for k in ("z_depart", "pas_z", "n_plans", "temps_plan"):
            a.v(f"calibration.{k}").trace_add("write", lambda *_: self.maj_plans())

    def _chemin_auto(self):
        racine = self.app.v("materiel.dossier_racine").get().rstrip("/")
        return f"{racine}/{self.app.v('calibration.date').get()}/calib"

    def _suivre_date(self):
        v = self.app.v("calibration.dossier_images")
        if v.get() == self.auto:
            self.auto = self._chemin_auto()
            v.set(self.auto)
        else:
            self.auto = self._chemin_auto()

    def _maj_resultats(self):
        p = self.app.v("calibration.dossier_images").get().strip()
        self.lbl_resultats.configure(
            text=f"Résultats dans {Path(p).parent / 'results_calib'}" if p else "Résultats dans —")

    def maj_plans(self):
        a = self.app
        z0, pas = a.nombre("calibration.z_depart"), a.nombre("calibration.pas_z")
        n, t = a.nombre("calibration.n_plans"), a.nombre("calibration.temps_plan")
        if None in (z0, pas, n, t) or n < 1:
            return self.lbl_plans.configure(text="valeurs invalides")
        z = rg.z_liste(z0, pas, n)
        t = t or int(1 + abs(pas) / 0.6)
        self.lbl_plans.configure(text=f"{z[0]} → {z[-1]}  ({int(n)} plans) — acquisition "
                                      f"{max(t, 2):.0f} s par plan, environ {n * max(t, 2) / 60:.1f} min")

    # ----------------------------------------------------------------- 3
    def acquisition(self, f):
        a = self.app
        a.champ(f, 0, "Exposition gauche", "calibration.expo_gauche", "µs")
        a.champ(f, 1, "Exposition droite", "calibration.expo_droite", "µs")
        a.champ(f, 2, "Temps par plan", "calibration.temps_plan", "s (0 = 1 + pas/0,6)",
                aide="calib_crappy_V2 : time_sync = int(1 + |pas| / 0.6), soit 4 s pour 2 mm ; "
                     "les caméras sont déclenchées dans la dernière seconde")
        a.note(f, 3, "Le plateau part de Z = 70 (Printer.open), puis descend plan par plan à "
                     "100 mm/min. Si le dossier existe déjà et n'est pas vide, les images vont "
                     "dans <dossier>_00001, comme get_unique_save_path.", 620)
        self.maj_plans()
        b = ttk.Frame(f)
        b.grid(row=4, column=0, columnspan=4, sticky="w", padx=4, pady=6)
        ttk.Button(b, text="▶  Lancer l'acquisition", style="Go.TButton",
                   command=self.lancer_acquisition).pack(side="left", padx=3)
        ttk.Button(b, text="Écrire le document des hauteurs", command=self.document
                   ).pack(side="left", padx=3)
        ttk.Button(b, text="Ouvrir le document", command=self.ouvrir_document
                   ).pack(side="left", padx=3)
        a.note(f, 5, "Le document hauteurs_calibration.txt (et .csv) est écrit "
                     "automatiquement dans le dossier images calib à chaque acquisition : "
                     "hauteur de départ, pas, hauteur de chaque plan et images prises.", 620)

    def lancer_acquisition(self):
        a = self.app
        if a.occupe():
            return
        fichier = a.ecrire_config("derniere_config_calibration.json")
        if fichier is None:
            return
        c = a.reglages["calibration"]
        if not messagebox.askokcancel("Acquisition", (
                f"{c['n_plans']} plans à partir de Z = {c['z_depart']} mm, images dans\n"
                f"{c['dossier_images']}\n\nLa mire ChArUco est-elle en place et le plateau libre ?")):
            return

        def sur_ligne(l):
            if l.startswith("DOSSIER_CALIB="):
                a.v("calibration.dossier_images").set(l.split("=", 1)[1])
                a.sauver_reglages()
        a.lancer("Acquisition calibration", [a.python(), "-u", str(a.ICI / "lancer_calibration.py"),
                                             "acquisition", str(fichier)], sur_ligne=sur_ligne)

    def document(self):
        a = self.app
        if a.occupe():
            return
        fichier = a.ecrire_config("derniere_config_calibration.json")
        if fichier:
            a.lancer("Document des hauteurs", [a.python(), "-u", str(a.ICI / "lancer_calibration.py"),
                                                "document", str(fichier)])

    def ouvrir_document(self):
        d = self.app.chemin(self.app.v("calibration.dossier_images").get().strip() or ".")
        self.app.ouvrir(d / "hauteurs_calibration.txt")

    # ----------------------------------------------------------------- 4
    def methode(self, f):
        a = self.app
        a.choix(f, 0, "Méthode", "calibration.methode", list(METHODES), commande=self.changer_methode)
        self.lbl_forme = ttk.Label(f, text=LIBELLES[a.v("calibration.methode").get()])
        self.lbl_forme.grid(row=1, column=0, sticky="w", padx=8, pady=3)
        self.combo_forme = ttk.Combobox(f, textvariable=a.v("calibration.pform"), width=12)
        self.combo_forme.grid(row=1, column=1, sticky="w", padx=4, pady=3)
        ttk.Label(f, text="Itérations").grid(row=2, column=0, sticky="w", padx=8, pady=3)
        ttk.Spinbox(f, from_=1, to=12, textvariable=a.v("calibration.iterations"), width=6
                    ).grid(row=2, column=1, sticky="w", padx=4, pady=3)
        a.case(f, 3, "Déplacer les metadata.csv vers le dossier parent",
               "calibration.deplacer_metadata")
        a.case(f, 4, "Afficher le nuage 3D à la fin", "calibration.afficher_3d")
        a.note(f, 5, f"Mire ChArUco : {NCX} × {NCY} carrés de {SQR} mm")
        b = ttk.Frame(f)
        b.grid(row=6, column=0, columnspan=4, sticky="w", padx=4, pady=6)
        ttk.Button(b, text="▶  Lancer la calibration", style="Go.TButton",
                   command=self.lancer_calcul).pack(side="left", padx=3)
        ttk.Button(b, text="Ouvrir les résultats", command=self.ouvrir_resultats
                   ).pack(side="left", padx=3)
        self.changer_methode(garder=True)

    def changer_methode(self, garder=False):
        """Comme on_method_change de calibration_gui : degré et itérations par défaut."""
        a = self.app
        m = a.v("calibration.methode").get()
        valeurs, degre, iterations = METHODES[m]
        self.combo_forme.configure(values=valeurs,
                                   state="readonly" if m == "Soloff" else "normal")
        self.lbl_forme.configure(text=LIBELLES[m])
        if not garder:
            a.v("calibration.pform").set(degre)
            a.v("calibration.iterations").set(str(iterations))

    def lancer_calcul(self):
        a = self.app
        if a.occupe():
            return
        try:
            time.strptime(a.v("calibration.date").get(), "%Y_%m_%d")
        except ValueError:
            return messagebox.showerror("Erreur", "Date attendue au format AAAA_MM_JJ")
        d = a.chemin(a.v("calibration.dossier_images").get().strip() or ".")
        if not d.is_dir() and not messagebox.askyesno(
                "Dossier introuvable", f"{d} n'existe pas.\nContinuer quand même ?"):
            return
        fichier = a.ecrire_config("derniere_config_calibration.json")
        if not fichier:
            return
        c = a.reglages["calibration"]
        nom = {"Zernike": f"nZ_{c['pform']}/A_Zernike.npy",
               "Lagrange": f"Lpform_{c['pform']}/L_constants.npy"}.get(c["methode"])
        attendu = d.parent / "results_calib" / nom if nom else None

        def fin(code):   # le résultat devient la calibration du pilotage 3D
            if code == 0 and attendu is not None and attendu.is_file():
                a.v("essai.deformation.fichier_constantes").set(str(attendu))
                a.v("essai.deformation.methode_3d").set(c["methode"])
                a.log(f"Calibration retenue pour le pilotage 3D : {attendu}", "info")
        a.lancer(f"Calibration {c['methode']}",
                 [a.python(), "-u", str(a.ICI / "lancer_calibration.py"), "calcul", str(fichier)],
                 sur_fin=fin)

    def ouvrir_resultats(self):
        d = self.app.v("calibration.dossier_images").get().strip()
        if d:
            self.app.ouvrir(self.app.chemin(d).parent / "results_calib")
