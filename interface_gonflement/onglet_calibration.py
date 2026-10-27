"""Onglet Calibration : réglage du plateau et des caméras, acquisition de la
mire plan par plan, calcul Pycaso."""

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

try:
    from . import reglages as rg
    from .widgets import CadreDefilant
except ImportError:
    import reglages as rg
    from widgets import CadreDefilant

FORMES = {"Zernike": [str(i) for i in range(1, 13)],      # Zernike_calibration : 1 à 12
          "Lagrange": [str(i) for i in range(1, 9)],
          "Soloff": ["111", "221", "222", "332", "333", "443", "444", "554", "555"]}
FORME_DEFAUT = {"Zernike": "12", "Lagrange": "4", "Soloff": "332"}


class OngletCalibration(ttk.Frame):

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = a = app
        col = CadreDefilant(self, largeur=680, fond=a.P["fond"])
        col.pack(side="left", fill="both", expand=True)
        g = col.interieur
        ttk.Label(g, wraplength=640, style="Petit.TLabel", text=(
            "Mire ChArUco posée sur le plateau de l'imprimante : 1) vérifier netteté et "
            "cadrage, 2) acquérir les images plan par plan, 3) calculer la calibration "
            "avec Pycaso. Le résultat Zernike est repris pour le pilotage 3D.")
        ).pack(anchor="w", padx=10, pady=8)
        self.reglage(a.cadre(g, "1. Réglage du plateau et des caméras"))
        self.acquisition(a.cadre(g, "2. Acquisition des images de calibration"))
        self.calcul(a.cadre(g, "3. Calcul de la calibration (Pycaso)"))
        self.maj_formes()

    # ----------------------------------------------------------------- 1
    def reglage(self, f):
        a = self.app
        b = ttk.Frame(f)
        b.grid(row=0, column=0, columnspan=4, sticky="w", padx=4, pady=4)
        ttk.Button(b, text="Origine Z (G28)", command=lambda: a.outil(
            "Origine Z", "origine", a.v("materiel.port_imprimante").get())).pack(side="left", padx=3)
        ttk.Button(b, text="Aperçu des caméras", command=self.apercu).pack(side="left", padx=3)
        ttk.Button(b, text="Tester les caméras", command=lambda: a.outil(
            "Test caméras", "test_cameras", a.v("materiel.sn_gauche").get(),
            a.v("materiel.sn_droite").get())).pack(side="left", padx=3)
        a.champ(f, 1, "Hauteur du plateau", "calibration.z_reglage", "mm")
        self.origine_avant = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="faire l'origine avant", variable=self.origine_avant
                        ).grid(row=1, column=3, padx=6, sticky="w")
        bz = ttk.Frame(f)
        bz.grid(row=2, column=0, columnspan=4, sticky="w", padx=4, pady=4)
        ttk.Button(bz, text="Aller à cette hauteur", command=self.aller_z).pack(side="left", padx=3)
        for z in (20, 70, 120):
            ttk.Button(bz, text=f"Z = {z}", width=7, command=lambda z=z: (
                a.v("calibration.z_reglage").set(str(z)), self.aller_z())).pack(side="left", padx=2)
        a.note(f, 3, "Vérifier que la mire est nette sur les deux caméras entre 20 et "
                     "120 mm. Z = 70 mm : position de début d'essai.", 620)

    def apercu(self):
        a = self.app
        a.outil("Aperçu caméras", "apercu", a.v("materiel.sn_gauche").get(),
                a.v("materiel.sn_droite").get(), a.v("calibration.expo_gauche").get(),
                a.v("calibration.expo_droite").get())

    def aller_z(self):
        z = self.app.nombre("calibration.z_reglage")
        if z is None or not 0 <= z <= 200:
            return messagebox.showerror("Hauteur", "Hauteur hors plage (0–200 mm)")
        extra = ["--origine"] if self.origine_avant.get() else []
        self.app.outil(f"Plateau à Z = {z}", "aller_z",
                       self.app.v("materiel.port_imprimante").get(), z, *extra)

    # ----------------------------------------------------------------- 2
    def acquisition(self, f):
        a = self.app
        a.champ(f, 0, "Hauteur de départ", "calibration.z_depart", "mm")
        a.champ(f, 1, "Pas (descente)", "calibration.pas_z", "mm")
        a.champ(f, 2, "Nombre de plans", "calibration.n_plans")
        a.champ(f, 3, "Temps par plan", "calibration.temps_plan", "s (0 = auto)",
                aide="Temps laissé à l'imprimante pour chaque plan ; les caméras sont "
                     "déclenchées dans la dernière seconde")
        a.champ(f, 4, "Exposition gauche", "calibration.expo_gauche", "µs")
        a.champ(f, 5, "Exposition droite", "calibration.expo_droite", "µs")
        self.lbl_plans = a.note(f, 6, "", 620)
        for k in ("z_depart", "pas_z", "n_plans", "temps_plan"):
            a.v(f"calibration.{k}").trace_add("write", lambda *_: self.maj_plans())
        self.maj_plans()
        ttk.Button(f, text="▶  Lancer l'acquisition", style="Go.TButton",
                   command=self.lancer_acquisition).grid(row=7, column=0, columnspan=2,
                                                        sticky="w", padx=8, pady=6)

    def maj_plans(self):
        a = self.app
        z0, pas = a.nombre("calibration.z_depart"), a.nombre("calibration.pas_z")
        n, t = a.nombre("calibration.n_plans"), a.nombre("calibration.temps_plan")
        if None in (z0, pas, n, t) or n < 1:
            return self.lbl_plans.configure(text="valeurs invalides")
        t = max(t or int(1 + abs(pas) / 0.6), 2.0)
        z = rg.z_liste(z0, pas, n)
        self.lbl_plans.configure(text=f"{int(n)} plans de {z[0]} à {z[-1]} mm — {t:.0f} s "
                                      f"par plan, environ {n * t / 60:.1f} min")

    def lancer_acquisition(self):
        a = self.app
        if a.occupe():
            return
        fichier = a.ecrire_config("derniere_config_calibration.json")
        if fichier is None:
            return
        c = a.reglages["calibration"]
        if not messagebox.askokcancel("Acquisition", (
                f"{c['n_plans']} plans à partir de Z = {c['z_depart']} mm.\n"
                "La mire ChArUco est-elle en place et le plateau libre ?")):
            return

        def sur_ligne(l):
            if l.startswith("DOSSIER_CALIB="):
                a.v("calibration.dossier_images").set(l.split("=", 1)[1])
                a.sauver_reglages()
        a.lancer("Acquisition calibration", [a.python(), "-u", str(a.ICI / "lancer_calibration.py"),
                                             "acquisition", str(fichier)], sur_ligne=sur_ligne)

    # ----------------------------------------------------------------- 3
    def calcul(self, f):
        a = self.app
        a.chemin_choisi(f, 0, "Dossier des images", "calibration.dossier_images",
                        dossier=True, largeur=50)
        a.note(f, 1, "Contient video_extenso_left/ et video_extenso_right/ ; rempli "
                     "automatiquement après l'acquisition.", 620)
        a.choix(f, 2, "Méthode", "calibration.methode", list(FORMES), commande=self.maj_formes)
        self.combo_forme = a.choix(f, 3, "Degré / forme", "calibration.pform", [])
        a.champ(f, 4, "Itérations", "calibration.iterations")
        a.case(f, 5, "Déplacer les metadata.csv vers le dossier parent",
               "calibration.deplacer_metadata")
        a.case(f, 6, "Afficher le nuage 3D à la fin", "calibration.afficher_3d")
        b = ttk.Frame(f)
        b.grid(row=7, column=0, columnspan=4, sticky="w", padx=4, pady=6)
        ttk.Button(b, text="▶  Lancer le calcul", style="Go.TButton",
                   command=self.lancer_calcul).pack(side="left", padx=3)
        ttk.Button(b, text="Ouvrir les résultats", command=self.ouvrir_resultats
                   ).pack(side="left", padx=3)
        ttk.Button(b, text="Fenêtre Pycaso d'origine", command=lambda: a.lancer(
            "Calibration Pycaso", [a.python(), "-u", "1_calibration.py"])).pack(side="left", padx=3)

    def maj_formes(self):
        m = self.app.v("calibration.methode").get()
        self.combo_forme.configure(values=FORMES.get(m, []))
        if self.app.v("calibration.pform").get() not in FORMES.get(m, []):
            self.app.v("calibration.pform").set(FORME_DEFAUT.get(m, "1"))

    def lancer_calcul(self):
        a = self.app
        if a.occupe():
            return
        d = a.v("calibration.dossier_images").get().strip()
        if not d or not Path(d).is_dir():
            return messagebox.showerror("Dossier", "Choisir le dossier des images de calibration")
        manquants = [s for s in ("video_extenso_left", "video_extenso_right")
                     if not (Path(d) / s).is_dir()]
        if manquants and not messagebox.askyesno(
                "Dossier", f"Sous-dossier(s) absent(s) : {', '.join(manquants)}\nContinuer ?"):
            return
        fichier = a.ecrire_config("derniere_config_calibration.json")
        if not fichier:
            return
        c = a.reglages["calibration"]
        nom = {"Zernike": f"nZ_{c['pform']}/A_Zernike.npy",
               "Lagrange": f"Lpform_{c['pform']}/L_constants.npy"}.get(c["methode"])
        attendu = Path(d).resolve().parent / "results_calib" / nom if nom else None

        def fin(code):   # le résultat devient la calibration du pilotage 3D
            if code == 0 and attendu is not None and attendu.is_file():
                a.v("essai.deformation.fichier_constantes").set(str(attendu))
                a.v("essai.deformation.methode_3d").set(c["methode"])
                a.log(f"Calibration retenue pour le pilotage 3D : {attendu}", "info")
        a.lancer(f"Calcul calibration {c['methode']}",
                 [a.python(), "-u", str(a.ICI / "lancer_calibration.py"), "calcul", str(fichier)],
                 sur_fin=fin)

    def ouvrir_resultats(self):
        d = self.app.v("calibration.dossier_images").get().strip()
        if d:
            self.app.ouvrir(Path(d).parent / "results_calib")
