"""Onglet Calibration : reprend les programmes du dépôt.

  1. Réglage       test hauteur 20 -> 120 mm, début d'essai (Z = 70), origine (G92), photos
  En haut         dossier racine, date, nom de l'essai (toujours visibles)
  2. Plans z       Z départ, Z fin, pas
  3. Acquisition   en boucle fermée : photo une fois le plateau arrivé (sequence_calibration.py)
  4. Méthode       Pycaso/calibration_gui.py (Lagrange 4 / 10 it., Soloff 332 / 8, Zernike 6 / 9)
"""

import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

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
        # chemin de la calibration : bandeau fixe en haut de l'onglet (toujours visible)
        haut = ttk.LabelFrame(self, text="Dossier de calibration", padding=(4, 4))
        haut.pack(side="top", fill="x", padx=8, pady=(6, 2))
        self.dossier(haut)
        col = CadreDefilant(self, largeur=680, fond=a.P["fond"])
        col.pack(side="left", fill="both", expand=True)
        g = col.interieur
        self.reglage(a.cadre(g, "1. Réglage du plateau et des caméras"))
        self.plans(a.cadre(g, "2. Plans z (mm)"))
        self.acquisition(a.cadre(g, "3. Acquisition des images (plan par plan)"))
        self.methode(a.cadre(g, "4. Méthode et calcul (Pycaso)"))

    # ----------------------------------------------------------------- 1
    def reglage(self, f):
        a = self.app
        port = lambda: a.v("materiel.port_imprimante").get()  # noqa: E731
        b = ttk.Frame(f)
        b.grid(row=0, column=0, columnspan=5, sticky="w", padx=4, pady=4)
        ttk.Button(b, text="Test hauteur (Z 20 → 120)", command=self.test_hauteur
                   ).pack(side="left", padx=3)
        ttk.Button(b, text="Début d'essai (Z = 70)", command=lambda: a.outil(
            "Plateau en début d'essai", "aller_z", port(), 70, "--origine")).pack(side="left", padx=3)
        a.note(f, 1, "Test hauteur : aperçu des deux caméras avec leur netteté en direct ; origine "
                     "puis Z = 20 mm, Espace pour passer à Z = 120 mm (et revenir), q pour fermer. "
                     "La netteté de chaque hauteur est notée dans la console.", 620)
        b = ttk.Frame(f)
        b.grid(row=2, column=0, columnspan=5, sticky="w", padx=4, pady=4)
        ttk.Button(b, text="Changer origine Z", command=self.changer_origine).pack(side="left", padx=3)
        ttk.Button(b, text="Aperçu", command=self.apercu).pack(side="left", padx=3)
        ttk.Button(b, text="Prendre une photo", command=self.photo).pack(side="left", padx=3)
        ttk.Button(b, text="Tester les caméras", command=lambda: a.outil(
            "Test caméras", "test_cameras", a.v("materiel.sn_gauche").get(),
            a.v("materiel.sn_droite").get())).pack(side="left", padx=3)
        a.champ(f, 3, "Aller à Z", "calibration.z_reglage", "mm")
        self.origine_avant = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="origine avant (G28)", variable=self.origine_avant
                        ).grid(row=3, column=3, padx=6, sticky="w")
        ttk.Button(f, text="Aller", command=self.aller_z).grid(row=3, column=4, padx=4)

    def test_hauteur(self):
        a = self.app
        if not a.sauver_reglages():
            return
        if a.reglages["materiel"]["simulation"]:
            return a.log("[simulation] Test hauteur : pas de caméra ni d'imprimante", "alerte")
        a.preparer_cameras(lambda: a.lancer(
            "Test hauteur", [a.python(), "-u", str(a.ICI / "outils_machine.py"), "test_hauteur",
                             a.v("materiel.sn_gauche").get(), a.v("materiel.sn_droite").get(),
                             a.v("calibration.expo_gauche").get(),
                             a.v("calibration.expo_droite").get(),
                             a.v("materiel.port_imprimante").get()]))

    def apercu(self):
        a = self.app
        a.outil("Aperçu caméras", "apercu", a.v("materiel.sn_gauche").get(),
                a.v("materiel.sn_droite").get(), a.v("calibration.expo_gauche").get(),
                a.v("calibration.expo_droite").get())

    def changer_origine(self):
        """G92 : la position actuelle du plateau prend la valeur saisie."""
        z = simpledialog.askfloat(
            "Changer l'origine Z",
            "Valeur à donner à la position ACTUELLE du plateau (mm) :\n"
            "(0 = le plateau est à l'origine ici)\n\n"
            "Attention : une prise d'origine (G28 : « origine avant », Test hauteur, "
            "Début d'essai, acquisition) ou un redémarrage de l'imprimante revient à "
            "l'origine de la machine.", initialvalue=0.0, parent=self)
        if z is not None:
            self.app.outil(f"Origine Z = {z:g} à la position actuelle", "changer_origine",
                           self.app.v("materiel.port_imprimante").get(), z)

    def photo(self):
        """Une photo par caméra, dans <racine>/<date>/<nom de l'essai>/Photos."""
        a = self.app
        if not a.sauver_reglages():
            return
        if a.reglages["materiel"]["simulation"]:
            return a.log("[simulation] Prendre une photo : pas de caméra", "alerte")
        dossier = a.chemin(self._chemin_auto()).parent / "Photos"
        photos = {}

        def sur_ligne(l):
            if l.startswith("PHOTO="):
                nom, chemin = l.split("=", 1)[1].split("|", 1)
                photos[nom] = chemin

        def fin(code):
            self._montrer_photo(photos, dossier)

        a.preparer_cameras(lambda: a.lancer(
            "Photo des caméras", [a.python(), "-u", str(a.ICI / "outils_machine.py"), "photo",
                                  a.v("materiel.sn_gauche").get(), a.v("materiel.sn_droite").get(),
                                  a.v("calibration.expo_gauche").get(),
                                  a.v("calibration.expo_droite").get(), str(dossier)],
            sur_ligne=sur_ligne, sur_fin=fin))

    @staticmethod
    def _vignette(chemin, cote):
        """Image Tk réduite à partir d'un TIFF (Pillow) ou d'un PNG (Tk)."""
        try:
            from PIL import Image, ImageTk
            im = Image.open(chemin)
            if im.mode not in ("L", "RGB"):
                im = im.convert("L")
            im.thumbnail((cote, cote))
            return ImageTk.PhotoImage(im)
        except ImportError:
            img = tk.PhotoImage(file=chemin)        # PNG / GIF seulement
            while img.width() > cote:
                img = img.subsample(2)
            return img

    def _montrer_photo(self, photos, dossier):
        """Les deux photos TIFF côte à côte ; « pas d'image » si une caméra n'a pas répondu."""
        P = self.app.P
        fen = tk.Toplevel(self)
        fen.title(f"Photos — {dossier}")
        fen.configure(bg=P["fond"])
        ligne = tk.Frame(fen, bg=P["fond"])
        ligne.pack(padx=8, pady=8)
        for nom in ("gauche", "droite"):
            cadre = tk.Frame(ligne, bg=P["fond"])
            cadre.pack(side="left", padx=4)
            img = None
            if nom in photos:
                try:
                    img = self._vignette(photos[nom], 520)
                except Exception as e:
                    self.app.log(f"Photo {nom} illisible : {e}", "erreur")
            if img is not None:
                lbl = tk.Label(cadre, image=img, bg=P["fond"])
                lbl.image = img
                legende = Path(photos[nom]).name
            else:
                lbl = tk.Label(cadre, text=f"caméra {nom} :\npas d'image", width=40, height=18,
                               bg=P["panneau"], fg=P["rouge"])
                legende = ""
            lbl.pack()
            ttk.Label(cadre, text=f"{nom}  {legende}", style="Petit.TLabel").pack()
        ttk.Label(fen, text=f"TIFF pleine résolution dans {dossier}",
                  style="Petit.TLabel").pack(pady=(0, 6))
        ttk.Button(fen, text="Ouvrir le dossier", command=lambda: self.app.ouvrir(dossier)
                   ).pack(pady=(0, 8))

    def aller_z(self):
        z = self.app.nombre("calibration.z_reglage")
        if z is None or not 0 <= z <= 200:
            return messagebox.showerror("Hauteur", "Hauteur hors plage (0–200 mm)")
        extra = ["--origine"] if self.origine_avant.get() else []
        self.app.outil(f"Plateau à Z = {z}", "aller_z",
                       self.app.v("materiel.port_imprimante").get(), z, *extra)

    # ----------------------------------------------------------------- 2
    def dossier(self, f):
        """Racine / date / nom de l'essai -> <racine>/<date>/calib (images),
        <date>/Photos (photos de réglage) et <date>/results_calib (calcul, règle de Pycaso)."""
        a = self.app
        a.v("calibration.date").set(time.strftime("%Y_%m_%d"))   # aujourd'hui, comme l'original
        a.chemin_choisi(f, 0, "Dossier racine", "materiel.dossier_racine", dossier=True, largeur=60)
        ligne = ttk.Frame(f)
        ligne.grid(row=1, column=0, columnspan=4, sticky="w", padx=4, pady=3)
        ttk.Label(ligne, text="Date (AAAA_MM_JJ)").pack(side="left", padx=(4, 6))
        ttk.Entry(ligne, textvariable=a.v("calibration.date"), width=12).pack(side="left")
        ttk.Label(ligne, text="Dossier de calibration").pack(side="left", padx=(18, 6))
        ttk.Entry(ligne, textvariable=a.v("calibration.nom_essai"), width=22).pack(side="left")
        self.lbl_cible = a.note(f, 2, "", 1100)
        a.chemin_choisi(f, 3, "Images pour le calcul", "calibration.dossier_images",
                        dossier=True, largeur=60)
        self.lbl_resultats = a.note(f, 4, "", 1100)
        # le dossier du calcul suit racine / date / nom tant qu'il n'a pas été modifié à la main
        self.auto = self._chemin_auto()
        memo = a.v("calibration.dossier_images").get().strip()
        if not memo or a.v("calibration.date").get() not in memo:
            a.v("calibration.dossier_images").set(self.auto)
        for cle in ("calibration.date", "materiel.dossier_racine", "calibration.nom_essai"):
            a.v(cle).trace_add("write", lambda *_: self._suivre_date())
        a.v("calibration.dossier_images").trace_add("write", lambda *_: self._maj_resultats())
        self._maj_resultats()

    # ----------------------------------------------------------------- 2
    def plans(self, f):
        a = self.app
        ligne = ttk.Frame(f)
        ligne.grid(row=0, column=0, columnspan=4, sticky="w", padx=4, pady=4)
        for txt, cle in (("Z départ", "z_depart"), ("Z fin", "z_fin"), ("pas", "pas_z")):
            ttk.Label(ligne, text=txt).pack(side="left", padx=(8, 4))
            ttk.Entry(ligne, textvariable=a.v(f"calibration.{cle}"), width=7).pack(side="left")
        ttk.Label(ligne, text="mm", style="Petit.TLabel").pack(side="left", padx=4)
        self.lbl_plans = a.note(f, 1, "", 620)
        for k in ("z_depart", "z_fin", "pas_z", "stabilisation", "vitesse_plateau"):
            a.v(f"calibration.{k}").trace_add("write", lambda *_: self.maj_plans())

    def _chemin_auto(self):
        a = self.app
        racine = a.v("materiel.dossier_racine").get().rstrip("/")
        return f"{racine}/{a.v('calibration.date').get()}/{a.v('calibration.nom_essai').get()}"

    def _suivre_date(self):
        v = self.app.v("calibration.dossier_images")
        if v.get() == self.auto:
            self.auto = self._chemin_auto()
            v.set(self.auto)
        else:
            self.auto = self._chemin_auto()

    def _maj_resultats(self):
        base = self.app.chemin(self._chemin_auto())
        self.lbl_cible.configure(text=f"Acquisition dans : {base}  (puis {base.name}_00001… s'il est "
                                      f"déjà rempli) — photos de réglage dans {base.parent / 'Photos'}")
        p = self.app.v("calibration.dossier_images").get().strip()
        self.lbl_resultats.configure(
            text=f"Résultats dans {Path(p).parent / 'results_calib'}" if p else "Résultats dans —")

    def maj_plans(self):
        a = self.app
        z0, z1 = a.nombre("calibration.z_depart"), a.nombre("calibration.z_fin")
        pas, stab = a.nombre("calibration.pas_z"), a.nombre("calibration.stabilisation")
        v = a.nombre("calibration.vitesse_plateau")
        if None in (z0, z1, pas, stab, v) or pas == 0 or v <= 0:
            return self.lbl_plans.configure(text="valeurs invalides")
        z = rg.z_liste(z0, z1, pas)
        n = len(z)
        duree = rg.duree_estimee(z, z[0], v, stab)
        reste = "" if z[-1] == z1 else f" (Z fin {z1:g} non atteint avec ce pas)"
        self.lbl_plans.configure(text=f"{n} plans : {', '.join(map(str, z[:4]))}"
                                      f"{', …' if n > 5 else ''}{', ' + str(z[-1]) if n > 4 else ''}"
                                      f"{reste} — environ {duree / 60:.1f} min (origine puis Z = {z[0]:g})")

    # ----------------------------------------------------------------- 3
    def acquisition(self, f):
        a = self.app
        self.lbl_acq = ttk.Label(f, style="Petit.TLabel", wraplength=620)
        self.lbl_acq.grid(row=0, column=0, columnspan=4, sticky="w", padx=8, pady=3)
        for k in ("expo_gauche", "expo_droite", "stabilisation", "vitesse_plateau",
                  "graphe_hauteur"):
            a.v(f"calibration.{k}").trace_add("write", lambda *_: self.maj_acq())
        self.maj_acq()
        self.maj_plans()
        b = ttk.Frame(f)
        b.grid(row=1, column=0, columnspan=4, sticky="w", padx=4, pady=6)
        ttk.Button(b, text="▶  Lancer l'acquisition", style="Go.TButton",
                   command=self.lancer_acquisition).pack(side="left", padx=3)
        ttk.Button(b, text="Écrire le document des hauteurs", command=self.document
                   ).pack(side="left", padx=3)
        ttk.Button(b, text="Ouvrir le document", command=self.ouvrir_document
                   ).pack(side="left", padx=3)
        a.note(f, 2, "Le document hauteurs_calibration.txt (et .csv) est écrit "
                     "automatiquement dans le dossier images calib à chaque acquisition : "
                     "hauteur de départ, pas, hauteur de chaque plan et images prises.", 620)

    def maj_acq(self):
        """Rappel des réglages d'acquisition (modifiables dans l'onglet Matériel)."""
        v = lambda k: self.app.v(f"calibration.{k}").get()
        try:
            graphe = "graphe de la hauteur" if v("graphe_hauteur") else "sans graphe"
        except Exception:
            graphe = ""
        self.lbl_acq.configure(text=(
            f"Expositions {v('expo_gauche')} / {v('expo_droite')} µs, stabilisation "
            f"{v('stabilisation')} s, plateau {v('vitesse_plateau')} mm/min, {graphe} "
            "— réglages dans l'onglet Matériel."))

    def lancer_acquisition(self):
        a = self.app
        if a.occupe():
            return
        fichier = a.ecrire_config("derniere_config_calibration.json")
        if fichier is None:
            return
        c = a.reglages["calibration"]
        try:
            z = rg.zl(c)
        except ValueError as e:
            return messagebox.showerror("Plans z", str(e))
        if not messagebox.askokcancel("Acquisition", (
                f"{len(z)} plans de Z = {z[0]} à {z[-1]} mm (pas {c['pas_z']:g} mm), images dans\n"
                f"{a.chemin(self._chemin_auto())}\n\n"
                "La mire ChArUco est-elle en place et le plateau libre ?")):
            return

        def sur_ligne(l):
            if l.startswith("DOSSIER_CALIB="):
                a.v("calibration.dossier_images").set(l.split("=", 1)[1])
                a.sauver_reglages()
        def fin(code):
            d = a.chemin(a.v("calibration.dossier_images").get())
            n = [len(list((d / f"video_extenso_{c}").glob("*.tif*"))) for c in ("left", "right")]
            a.log(f"Images enregistrées : gauche {n[0]}, droite {n[1]} dans {d}",
                  "info" if min(n) > 0 else "erreur")
        a.preparer_cameras(lambda: a.lancer(
            "Acquisition calibration", [a.python(), "-u", str(a.ICI / "lancer_calibration.py"),
                                        "acquisition", str(fichier)], sur_ligne=sur_ligne, sur_fin=fin))

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
        a.note(f, 3, "Les metadata.csv sont sortis des dossiers caméra avant chaque calcul "
                     "(Pycaso les prendrait pour des images).")
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
        if not self._verifier_images(d):
            return
        fichier = a.ecrire_config("derniere_config_calibration.json")
        if not fichier:
            return
        c = a.reglages["calibration"]
        nom = {"Zernike": f"nZ_{c['pform']}/A_Zernike.npy",
               "Lagrange": f"Lpform_{c['pform']}/L_constants.npy"}.get(c["methode"])
        attendu = d.parent / "results_calib" / nom if nom else None

        figures = []

        def sur_ligne(l):
            if l.startswith("FIGURE="):
                figures.append(l.split("=", 1)[1])

        def fin(code):   # figures de résultat, et la calibration devient celle du pilotage 3D
            if figures:
                self._montrer_figures(figures, d.parent / "results_calib")
            if code == 0 and attendu is not None and attendu.is_file():
                a.v("essai.deformation.fichier_constantes").set(str(attendu.resolve()))
                a.essai.chercher_calibrations()
                a.log(f"Calibration retenue pour le pilotage 3D : {attendu}", "info")
        a.lancer(f"Calibration {c['methode']}",
                 [a.python(), "-u", str(a.ICI / "lancer_calibration.py"), "calcul", str(fichier)],
                 sur_fin=fin, sur_ligne=sur_ligne)

    def _montrer_figures(self, figures, dossier):
        """Fenêtre avec le nuage 3D de la mire et l'erreur de rétroprojection."""
        fen = tk.Toplevel(self)
        fen.title(f"Résultats de calibration — {dossier}")
        fen.configure(bg=self.app.P["fond"])
        ligne = tk.Frame(fen, bg=self.app.P["fond"])
        ligne.pack(padx=8, pady=8)
        for f in figures:
            apercu, _, svg = f.partition("|")       # copie PNG temporaire | fichier SVG enregistré
            try:
                img = self._vignette(apercu, 700)
            except Exception:
                continue
            cadre = tk.Frame(ligne, bg=self.app.P["fond"])
            cadre.pack(side="left", padx=4)
            lbl = tk.Label(cadre, image=img, bg="white")
            lbl.image = img
            lbl.pack()
            ttk.Label(cadre, text=Path(svg or apercu).name, style="Petit.TLabel").pack()
        ttk.Button(fen, text="Ouvrir le dossier des résultats",
                   command=lambda: self.app.ouvrir(dossier)).pack(pady=(0, 8))

    @staticmethod
    def _compter(d):
        ext = (".tif", ".tiff", ".png", ".bmp", ".jpg", ".jpeg")
        return [len([p for p in (d / f"video_extenso_{c}").glob("*") if p.suffix.lower() in ext])
                for c in ("left", "right")]

    def _verifier_images(self, d):
        """Avant le calcul : le dossier contient-il des images, autant que de plans ?"""
        a = self.app
        n_g, n_d = self._compter(d)
        if not n_g or not n_d:
            # images ailleurs ? (calib_00001… d'une autre acquisition du même jour)
            voisins = sorted((p for p in d.parent.glob(d.name.split("_0")[0] + "*") if p.is_dir() and p != d
                              and min(self._compter(p)) > 0), key=lambda p: p.stat().st_mtime)
            texte = (f"Aucune image dans\n{d}\n(gauche {n_g}, droite {n_d}).")
            if voisins and messagebox.askyesno("Aucune image", texte + "\n\nUtiliser le dossier "
                                               f"le plus récent qui en contient :\n{voisins[-1]} ?"):
                a.v("calibration.dossier_images").set(str(voisins[-1]))
                return self._verifier_images(voisins[-1])
            if not voisins:
                messagebox.showerror("Aucune image", texte + "\n\nChoisir le dossier calib de "
                                     "l'acquisition dans « Images pour le calcul ».")
            return False
        try:
            n_z = len(rg.zl(a.collecter()["calibration"]))
        except ValueError as e:
            return messagebox.showerror("Plans z", str(e))
        if n_g == n_d == n_z:
            a.log(f"Calcul sur {n_g} paires d'images ({d})", "info")
            return True
        fz = d / "z_list.json"
        if fz.exists():         # hauteurs notées par l'acquisition
            import json
            z = json.loads(fz.read_text())
            if len(z) == n_g == n_d and messagebox.askyesno("Plans z", (
                    f"{n_g} images par caméra mais {n_z} plans dans les champs.\n\n"
                    f"L'acquisition de ce dossier a été faite de {z[0]} à {z[-1]} mm par pas de "
                    f"{abs(z[1] - z[0]) if len(z) > 1 else 0:g} mm. Utiliser ces hauteurs ?")):
                a.v("calibration.z_depart").set(str(z[0]))
                a.v("calibration.z_fin").set(str(z[-1]))
                a.v("calibration.pas_z").set(str(abs(z[1] - z[0]) if len(z) > 1 else 1))
                return True
        messagebox.showerror("Plans z", f"Images : gauche {n_g}, droite {n_d}, mais {n_z} plans.\n"
                             "Pycaso associe l'image n à la hauteur n : corriger Z départ / Z fin / "
                             "pas, ou le dossier.")
        return False

    def ouvrir_resultats(self):
        d = self.app.v("calibration.dossier_images").get().strip()
        if d:
            self.app.ouvrir(self.app.chemin(d).parent / "results_calib")
