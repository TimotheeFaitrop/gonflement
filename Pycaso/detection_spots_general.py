"""Coordonnées 2D des taches sur les deux caméras, appariées gauche/droite.

Remplace CoordCa10.py. Étapes (méthode lancer) :
  1. détection des taches sur la première image et suivi image par image (SuiviTaches) ;
  2. appariement gauche/droite (AppariementStereo) :
       - par défaut, sans étalonnage : recalage 2D (vote de translation + hongrois/affine),
         comme dans CoordCa10 ;
       - en option (utiliser_etalonnage=True) : par l'étalonnage stéréo Lagrange ;
  3. enregistrement de Lp_final.npy, lu par detect3D_*.py.

Tous les fichiers produits sont dans <dossier de l'essai>/appariemment_et_suivi/.

Les paramètres et leurs valeurs par défaut sont dans DetectionSpots.__init__ ;
l'interface (detection_spots_gui.py) les reprend comme valeurs de départ.
Les chemins relatifs partent du dossier courant (celui d'où l'on lance le script).
"""
import os
import glob
import subprocess
import sys
import time
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

from Pycaso.detection_spots_suivi import SuiviTaches
from Pycaso.detection_spots_appariemment import AppariementStereo


# Fenêtre d'avertissement lancée dans un processus séparé : le calcul continue pendant
# qu'elle est affichée (elle se ferme avec OK). Sans écran, rien ne s'affiche (terminal seul).
_CODE_FENETRE = """
import sys, tkinter as tk
from tkinter import ttk
root = tk.Tk()
root.title(sys.argv[1])
root.resizable(False, False)
root.attributes("-topmost", True)
orange = "#e65100"
try:                                   # thème commun (Pycaso/style_gui.py), si on le trouve
    sys.path.insert(0, sys.argv[3])
    from Pycaso.style_gui import Style
    Style.appliquer(root)
    orange = Style.ORANGE
except Exception:
    pass
cadre = ttk.Frame(root, padding=12)
cadre.grid()
ttk.Label(cadre, text="\u26a0", font=("TkDefaultFont", 28), foreground=orange).grid(row=0, column=0, sticky="n", padx=(0, 12))
ttk.Label(cadre, text=sys.argv[2], justify="left", wraplength=560).grid(row=0, column=1, sticky="w")
ttk.Button(cadre, text="OK", command=root.destroy).grid(row=1, column=1, sticky="e", pady=(12, 0))
root.bind("<Return>", lambda _e: root.destroy())
root.bind("<Escape>", lambda _e: root.destroy())
root.mainloop()
"""


def avertir(message, titre="Avertissement"):
    """Affiche message dans le terminal et dans une fenêtre tkinter qui ne bloque pas le calcul."""
    print(f"\n⚠ {message}\n")
    try:
        racine = str(Path(__file__).resolve().parent.parent)      # dossier qui contient Pycaso/
        subprocess.Popen([sys.executable, "-c", _CODE_FENETRE, titre, message, racine],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass                                   # pas de fenêtre possible : le terminal suffit


class DetectionSpots:
    """Suivi des taches des deux caméras, appariement stéréo et enregistrement.

    Après lancer(), les résultats restent disponibles en attributs :
    all_pxl, all_pyl, all_pxr, all_pyr, all_pxr_corr, all_pyr_corr, paires, Lp.
    """

    def __init__(self,
                 # --- Essai à traiter ---
                 dossier_mesure=None,           # dossier de l'essai, contient video_extenso_left et _right ;
                                                # None = ../../Expériences/<aujourd'hui>/essai1
                 # --- Reprise ---
                 # False : détecte et suit les taches (long). True : relit les résultats enregistrés.
                 gauche_calculated=False,
                 droite_calculated=False,
                 # --- Détection et suivi des taches ---
                 pix=20,                        # marge (px) autour d'une tache pour la retrouver
                                                # (doit rester < moitié de l'écart entre taches)
                 taille_min_pix=100,            # aire minimale d'une tache (px)
                 taille_max_pix=1000,           # aire maximale d'une tache (px)
                 max_images_a_considerer=51,    # nombre d'images suivies après l'image 0 ;
                                                # 1 est ajouté d'office (l'image de référence)
                 w_spots=False,                 # True si taches blanches sur fond sombre
                 figures_suivi=True,            # une figure .svg par image (lent) dans ROI_left / ROI_right
                 # --- Appariement des deux caméras ---
                 seuils_recalage=(80.0, 30.0, 10.0),  # (sans étalonnage) distances max (px) des
                                                # itérations du recalage 2D, de la plus large à la plus serrée
                 modele_recalage="polynome2",   # (sans étalonnage) transformation droite -> gauche :
                                                # affine, homographie, polynome2 ou polynome3
                 utiliser_etalonnage=False,    # True : appariement par l'étalonnage Lagrange
                 l_pform=4,                     # (étalonnage) degré Lagrange (Results_Calib/Lpform_<n>)
                 rayon_recherche=150.0,         # (étalonnage) rayon (px) de recherche sur l'autre caméra
                 tolerance_plan=1.0,            # (étalonnage) écart max (mm) au plan de l'échantillon
                 # --- Affichage ---
                 afficher_figures=True):        # figure de vérification de l'appariement à la fin
        self.dossier_mesure = dossier_mesure or self.chemin_par_defaut(time.strftime("%Y_%m_%d"))
        self.gauche_calculated = gauche_calculated
        self.droite_calculated = droite_calculated
        self.pix = pix
        self.taille_min_pix = taille_min_pix
        self.taille_max_pix = taille_max_pix
        self.max_images_a_considerer = max_images_a_considerer
        self.w_spots = w_spots
        self.figures_suivi = figures_suivi
        self.seuils_recalage = tuple(float(s) for s in seuils_recalage)
        self.modele_recalage = modele_recalage
        self.utiliser_etalonnage = utiliser_etalonnage
        self.l_pform = l_pform
        self.rayon_recherche = rayon_recherche
        self.tolerance_plan = tolerance_plan
        self.afficher_figures = afficher_figures

    def parametres(self):
        """Paramètres sous forme de dictionnaire (pour affichage)."""
        return {k: v for k, v in vars(self).items() if not k.startswith(("all_", "paires", "Lp"))}

    # ----- chemins de l'essai -----

    @staticmethod
    def chemin_par_defaut(date):
        """Dossier de mesure habituel pour une date donnée."""
        return f"../../Expériences/{date}/essai1"

    @property
    def dossier_images(self):
        """Dossier des images (celui qui contient video_extenso_left et _right), avec '/' final."""
        return os.path.join(str(Path(self.dossier_mesure)), "")

    @property
    def dossier(self):
        """Dossier des résultats : <dossier de l'essai>/appariemment_et_suivi/.

        Tout ce que produit cette phase y est enregistré : coordonnées suivies (reprise),
        figures ROI_left / ROI_right, figures de contrôle, Lp_final.npy, mapping.npy, ...
        """
        return os.path.join(str(Path(self.dossier_mesure) / self.NOM_DOSSIER_RESULTATS), "")

    NOM_DOSSIER_RESULTATS = "appariemment_et_suivi"

    def fichiers_reprise(self, cote):
        """Fichiers enregistrés par le suivi d'une caméra ('left' ou 'right')."""
        lettre = cote[0]
        return [f"{self.dossier}all_px{lettre}.npy", f"{self.dossier}all_py{lettre}.npy",
                f"{self.dossier}points_spotted_{cote}.npy"]

    NOMS_DOSSIER_CALIB = ("Results_Calib", "results_calib")

    def dossiers_calib(self):
        """Dossiers d'étalonnage trouvés dans le dossier de mesure ou au-dessus,
        du plus proche au plus loin.

        Organisation type : <date>/essai1/...  ->  étalonnage dans <date>/Results_Calib/
        """
        trouves = []
        mesure = Path(self.dossier_mesure).resolve()
        for parent in [mesure, *mesure.parents]:
            for nom in self.NOMS_DOSSIER_CALIB:
                d = parent / nom
                if d.is_dir() and d not in trouves:
                    trouves.append(d)
        return trouves

    def candidats_L_constants(self, l_pform=None):
        """Emplacements possibles de L_constants.npy (l_pform='*' pour tous les degrés)."""
        n = self.l_pform if l_pform is None else l_pform
        return [str(d / f"Lpform_{n}" / "L_constants.npy") for d in self.dossiers_calib()]

    def chemin_L_constants(self):
        """Premier L_constants.npy trouvé pour le degré l_pform, ou None s'il n'y en a pas."""
        for c in self.candidats_L_constants():
            if os.path.isfile(c):
                return c
        return None

    # ----- point d'entrée -----

    def lancer(self):
        """Suivi des deux caméras, appariement, puis enregistrement de Lp_final.npy.

        Par défaut l'appariement se fait sans étalonnage (recalage 2D). Si
        utiliser_etalonnage est vrai mais qu'aucun étalonnage n'est trouvé, on prévient
        et on apparie sans étalonnage. Renvoie Lp.
        """
        self.paires, self.Lp = None, None
        os.makedirs(self.dossier, exist_ok=True)
        print(f"Résultats enregistrés dans : {self.dossier}")
        L_constants = None
        if self.utiliser_etalonnage:                 # cherché avant le suivi (long) pour prévenir tout de suite
            fichier_calib = self.chemin_L_constants()
            if fichier_calib is None:
                avertir(f"Aucun étalonnage Lagrange Lpform_{self.l_pform} trouvé "
                        f"(cherché dans un dossier Results_Calib au-dessus de {self.dossier_mesure}).\n"
                        "Appariement sans étalonnage (recalage 2D) à la place.", "Étalonnage introuvable")
            else:
                print(f"Étalonnage : {fichier_calib}")
                L_constants = np.load(fichier_calib)

        suivi = SuiviTaches(self.pix, self.taille_min_pix, self.taille_max_pix,
                            self.max_images_a_considerer + 1,   # + l'image de référence (image 0)
                            self.w_spots, self.figures_suivi)

        # 1. Coordonnées des taches sur chaque caméra (px = ligne, py = colonne)
        self.all_pxl, self.all_pyl, nb_g = self.coordonnees_camera(suivi, "left", self.gauche_calculated)
        self.all_pxr, self.all_pyr, nb_d = self.coordonnees_camera(suivi, "right", self.droite_calculated)
        self.figure_nb_points(nb_g, nb_d)
        self.aligner_images()

        # 2. Appariement gauche/droite sur la première image
        appariement = AppariementStereo(L_constants, self.l_pform, self.rayon_recherche,
                                        self.tolerance_plan, self.seuils_recalage, self.modele_recalage)
        self.paires = self.apparier(appariement)

        # 3. Enregistrement
        self.Lp = AppariementStereo.construire_Lp(self.all_pxl, self.all_pyl,
                                                  self.all_pxr, self.all_pyr, self.paires)
        self.enregistrer()
        return self.Lp

    # ===== 1. suivi =====

    def coordonnees_camera(self, suivi, cote, deja_calcule):
        """Lit les coordonnées déjà enregistrées, ou les calcule (détection + suivi)."""
        fichiers = self.fichiers_reprise(cote)
        if deja_calcule:
            manquants = [f for f in fichiers if not os.path.isfile(f)]
            if manquants:
                raise FileNotFoundError(f"Fichiers absents (décochez la reprise caméra {cote}) : {manquants}")
            print(f"Caméra {cote} : coordonnées relues")
            return (np.load(fichiers[0], allow_pickle=True).astype(float),
                    np.load(fichiers[1], allow_pickle=True).astype(float),
                    np.load(fichiers[2], allow_pickle=True).tolist())
        masque = "maskL.tiff" if cote == "left" else "maskR.tiff"
        dossier_cam = f"{self.dossier_images}video_extenso_{cote}/"
        if not os.path.isfile(dossier_cam + masque):
            raise FileNotFoundError(f"Masque absent : {dossier_cam + masque}")
        print(f"\nCaméra {cote} : détection et suivi des taches")
        px, py, nb = suivi.suivre_camera(dossier_cam, masque, f"{self.dossier}ROI_{cote}/")
        for f, val in zip(fichiers, (px, py, np.array(nb))):
            np.save(f, val)
        return px, py, nb

    def numeros_images(self, cote, nb):
        """Numéros (début du nom de fichier) des nb premières images suivies de la caméra cote."""
        dossier_cam = f"{self.dossier_images}video_extenso_{cote}/"
        images = sorted(glob.glob(os.path.join(dossier_cam, "[0-9]*")), key=SuiviTaches.numero_image)
        return [SuiviTaches.numero_image(f) for f in images[:nb]]

    def aligner_images(self):
        """Garde, pour les deux caméras, les mêmes images (même numéro), dans le même ordre.

        Si une caméra a des photos en plus ou en moins (photo manquante, ou en trop à la fin),
        Lp_final ne peut associer gauche et droite que sur les images présentes des deux côtés.
        Les images sont repérées par leur numéro (000012_4.567.tiff -> 12) ; si les numéros ne se
        correspondent pas, on garde les premières images, autant que la caméra qui en a le moins.
        """
        n_g, n_d = len(self.all_pxl), len(self.all_pxr)
        try:
            num_g, num_d = self.numeros_images("left", n_g), self.numeros_images("right", n_d)
        except OSError:
            num_g, num_d = [], []
        if len(num_g) == n_g and len(num_d) == n_d and num_g == num_d:
            return                                                   # cas normal : rien à faire
        communs = sorted(set(num_g) & set(num_d))
        par_numero = (len(num_g) == n_g and len(num_d) == n_d and len(set(num_g)) == n_g
                      and len(set(num_d)) == n_d and len(communs) > 0)
        if par_numero:
            iG = [num_g.index(n) for n in communs]
            iD = [num_d.index(n) for n in communs]
            seul_g = sorted(set(num_g) - set(communs))
            seul_d = sorted(set(num_d) - set(communs))
            detail = (f"images seulement à gauche : {seul_g or 'aucune'} ; "
                      f"seulement à droite : {seul_d or 'aucune'}")
        else:
            n = min(n_g, n_d)
            iG = iD = list(range(n))
            detail = f"numéros d'images non comparables : on garde les {n} premières de chaque caméra"
        avertir(f"Nombre d'images différent : {n_g} à gauche, {n_d} à droite.\n"
                f"{detail}.\nLp_final.npy est construit sur les {len(iG)} images communes.",
                "Images des deux caméras")
        self.all_pxl, self.all_pyl = self.all_pxl[iG], self.all_pyl[iG]
        self.all_pxr, self.all_pyr = self.all_pxr[iD], self.all_pyr[iD]

    # ===== 2. appariement =====

    def apparier(self, appariement):
        """Apparie les taches de la première image. Renvoie la liste des paires (gauche, droite)."""
        image_droite = sorted(glob.glob(f"{self.dossier_images}video_extenso_right/[0-9]*"))[0]
        h, w = plt.imread(image_droite).shape[:2]
        self.all_pxr_corr, self.all_pyr_corr = AppariementStereo.rotation_180(self.all_pxr, self.all_pyr, h, w)

        vL = ~np.isnan(self.all_pxl[0]) & ~np.isnan(self.all_pyl[0])
        vR = ~np.isnan(self.all_pxr[0]) & ~np.isnan(self.all_pyr[0])
        idxL, idxR = np.where(vL)[0], np.where(vR)[0]
        L = np.column_stack([self.all_pyl[0][vL], self.all_pxl[0][vL]])               # gauche (colonne, ligne)
        R_tourne = np.column_stack([self.all_pyr_corr[0][vR], self.all_pxr_corr[0][vR]])
        R_brut = np.column_stack([self.all_pyr[0][vR], self.all_pxr[0][vR]])          # format de l'étalonnage

        if appariement.avec_etalonnage:
            print("Appariement par l'étalonnage Lagrange")
            ri, ci, ecarts, R_recale = appariement.apparier(L, R_brut, R_tourne)
            nom, unite, limite = "Écart au plan de l'échantillon", "mm", self.tolerance_plan
            conseil = "augmenter la tolérance au plan ou le rayon de recherche"
        else:
            print(f"Appariement sans étalonnage (recalage 2D {self.modele_recalage}, "
                  f"seuils {self.seuils_recalage} px)")
            ri, ci, ecarts, R_recale = appariement.apparier_sans_etalonnage(L, R_tourne)
            nom, unite, limite = "Résidu après recalage", "px", self.seuils_recalage[-1]
            conseil = "augmenter les seuils de recalage"
        if len(ri) == 0:
            raise RuntimeError(f"Aucune paire trouvée entre les deux caméras : {conseil}.")

        paires = [(int(idxL[i]), int(idxR[j])) for i, j in zip(ri, ci)]
        print(f"Paires appariées : {len(paires)} (sur {vL.sum()} taches à gauche et {vR.sum()} à droite)")
        print(f"{nom} ({unite}) : médian {np.median(ecarts):.2f}, max {ecarts.max():.2f}")
        self.figure_appariement(L, R_recale, ri, ci, ecarts, nom, unite, limite)
        return paires

    # ===== 3. enregistrement =====

    def enregistrer(self):
        d = self.dossier
        np.save(f"{d}Lp_final.npy", self.Lp)
        np.save(f"{d}mapping.npy", dict(self.paires))
        np.save(f"{d}all_pxr_corr.npy", self.all_pxr_corr)
        np.save(f"{d}all_pyr_corr.npy", self.all_pyr_corr)
        print(f"Lp_final.npy enregistré : {self.Lp.shape[0]} images, {self.Lp.shape[2]} points")

    # ===== figures =====

    def figure_nb_points(self, nb_g, nb_d):
        plt.figure()
        plt.plot(nb_g, "o-", label="Caméra gauche")
        plt.plot(nb_d, "s-", label="Caméra droite")
        plt.ylim(bottom=0); plt.xlabel("Image"); plt.ylabel("Taches suivies"); plt.legend()
        plt.savefig(f"{self.dossier}Number_points_spotted_{max(len(nb_g), len(nb_d))}_iterations.svg")
        plt.close()

    def figure_appariement(self, L, R_recale, ri, ci, ecarts, nom, unite, limite):
        fig, ax = plt.subplots(1, 3, figsize=(18, 6))
        ok = np.zeros(len(L), bool); ok[ri] = True
        ax[0].scatter(*L[~ok].T, s=12, c="tab:orange", label=f"non appariées ({(~ok).sum()})")
        ax[0].scatter(*L[ok].T, s=12, c="tab:blue", label=f"appariées ({ok.sum()})")
        ax[0].set_title("Caméra gauche, image 0")
        for i, j in zip(ri, ci):
            ax[1].plot([L[i, 0], R_recale[j, 0]], [L[i, 1], R_recale[j, 1]], "r-", lw=0.6)
        ax[1].scatter(*L.T, s=6, c="k")
        ax[1].scatter(*R_recale.T, s=8, c="tab:blue", marker="x", lw=0.6)
        ax[1].set_title("Paires (segments courts et réguliers attendus)")
        for a in ax[:2]:
            a.invert_yaxis(); a.set_aspect("equal")
        ax[0].legend(loc="lower left")
        ax[2].hist(ecarts, bins=30, range=(0, limite), color="tab:blue")
        ax[2].axvline(np.median(ecarts), color="k", ls="--", lw=1,
                      label=f"médiane {np.median(ecarts):.2f} {unite}")
        ax[2].set_xlabel(f"{nom} ({unite})"); ax[2].set_ylabel("Nombre de paires")
        ax[2].set_title(f"{nom} des paires retenues (limite {limite:g} {unite})")
        ax[2].legend()
        fig.tight_layout()
        fig.savefig(f"{self.dossier}appariement.png", dpi=120)
        if self.afficher_figures:
            plt.show()
        plt.close(fig)