"""Reconstruction 3D des taches appariées (Lp_final.npy) avec un étalonnage stéréo.

Remplace detect3D_Lagrange.py, detect3D_Soloff.py et detect3D_Zernike.py : une seule
classe, la méthode d'étalonnage est un paramètre.

Organisation des dossiers (dossier_essai = <date>/essai1, choisi par l'utilisateur) :
    <date>/essai1/appariemment_et_suivi/Lp_final.npy   taches appariées (entrée)
    <date>/essai1/reconstruction/Lpform_4/             résultats 3D (X3d.txt, Y3d.txt, Z3d.txt, figures)
    <date>/essai1/mesure/                              images (seulement pour Zernike : taille des caméras)
    <date>/Results_Calib/Lpform_4/                     étalonnage, cherché dans l'essai puis ses parents
Les noms des sous-dossiers sont des constantes de la classe (SOUS_DOSSIER_*).
"""
import json
import os
import re
import sys
import time
from pathlib import Path

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np

# pycaso.py fait "import solve_library" (sans "Pycaso.") : le dossier Pycaso,
# celui qui contient ce fichier, doit donc être dans sys.path avant de l'importer.
_pycaso_dir = str(Path(__file__).resolve().parent)
if _pycaso_dir not in sys.path:
    sys.path.insert(0, _pycaso_dir)
from Pycaso import pycaso as pcs
from Pycaso import data_library as data
from Pycaso.calibration_class import Calibration   # dimensions de la mire (Zernike)


class Detect3D:
    """Coordonnées 3D de toutes les taches, pour toutes les images."""

    # méthode : (sous-dossier de l'étalonnage, fichiers de constantes, degré par défaut)
    METHODES = {
        "Lagrange": ("Lpform_{}", ("L_constants.npy",), 4),
        "Soloff":   ("Spform_{}", ("S_constants0.npy", "S_constants.npy"), 555),
        "Zernike":  ("nZ_{}",     ("A_Zernike.npy",), 12),
    }
    NOMS_DOSSIER_CALIB = ("Results_Calib", "results_calib")
    SOUS_DOSSIER_ENTREE = "appariemment_et_suivi"   # contient Lp_final.npy
    SOUS_DOSSIER_SORTIE = "reconstruction"          # reçoit les résultats 3D
    SOUS_DOSSIER_MESURE = ""                  # images (Zernike seulement)
    # dossier où l'explorateur « … » de l'interface commence la recherche (absolu ou relatif au
    # dossier d'exécution ; "~" accepté). S'il n'existe pas, on remonte au premier parent existant.
    DOSSIER_PARCOURIR = "../../Expériences"
    FICHIER_INFOS = "reconstruction_infos.json"   # méthode, degré, facteur Z de la reconstruction
    SOLOFF_METHODE = "curve_fit"          # méthode de résolution de Soloff_identification

    def __init__(self,
                 # --- Essai à traiter ---
                 date=None,                 # AAAA_MM_JJ ; None = aujourd'hui
                 dossier_essai=None,        # ex. <date>/essai1 ; None = <date>/essai1
                 # --- Étalonnage ---
                 methode="Lagrange",        # "Lagrange", "Soloff" ou "Zernike"
                 degre=None,                # degré du polynôme ; None = valeur par défaut de la méthode
                 facteur_z=10.0,            # Z reconstruit × facteur (Z sorti 10× trop petit) ; 1 = brut
                 etat_plat=True,           # True : lit Lp_final_corrige.npy (image 0 = état plat, voir
                                            # correction_class) et écrit dans reconstruction/<tag>_corrige
                 # --- Figures ---
                 images_a_tracer=(-1,),     # images tracées : 0 = état plat (seulement avec etat_plat),
                                            # 1..n = photos de l'essai, -1 = dernière
                 deplacement=True,          # tracer z - z(image 0) plutôt que z (axe vertical fixé à -10..90 ;
                                            # sinon axe vertical automatique)
                 inverser_z=True,           # changer le signe de Z (dôme vers le haut)
                 exclusions_manuelles=True, # ne pas tracer les taches exclues à la main (retouche_gui)
                 couleurs_fixes=False,      # échelle de couleur fixe (sinon : min/max des données)
                 z_min=-10.0,               # bas de l'échelle fixe (mm), violet foncé
                 z_bleu=0.0,                # Z (mm) affiché en bleu
                 z_jaune=60.0,              # Z (mm) affiché en jaune
                 z_max=100.0,               # haut de l'échelle fixe (mm), jaune vif
                 enregistrer_figures=True,  # enregistrer les figures en .svg dans dossier_sortie
                 afficher_figures=True):    # ouvrir les figures à l'écran
        if methode not in self.METHODES:
            raise ValueError(f"Méthode inconnue : {methode} (choix : {', '.join(self.METHODES)})")
        self.date = date or time.strftime("%Y_%m_%d")
        self.dossier_essai = dossier_essai or self.chemin_par_defaut(self.date)
        self.methode = methode
        self.degre = self.METHODES[methode][2] if degre is None else degre
        self.images_a_tracer = tuple(images_a_tracer)
        self.deplacement = deplacement
        self.inverser_z = inverser_z
        self.exclusions_manuelles = exclusions_manuelles
        self.facteur_z = facteur_z
        self.etat_plat = etat_plat
        self.couleurs_fixes = couleurs_fixes
        self.z_min = z_min
        self.z_bleu = z_bleu
        self.z_jaune = z_jaune
        self.z_max = z_max
        self.enregistrer_figures = enregistrer_figures
        self.afficher_figures = afficher_figures

    RESULTATS = ("X", "Y", "Z")

    def parametres(self):
        """Paramètres sous forme de dictionnaire (pour affichage)."""
        return {k: v for k, v in vars(self).items() if k not in self.RESULTATS}

    # ----- chemins -----

    @staticmethod
    def chemin_par_defaut(date):
        """Dossier d'essai proposé pour une date donnée."""
        return f"../../Expériences/{date}/essai1"

    @property
    def dossier_entree(self):
        """<essai>/appariemment_et_suivi : contient Lp_final.npy."""
        return Path(self.dossier_essai) / self.SOUS_DOSSIER_ENTREE

    FICHIER_LP, FICHIER_LP_CORRIGE = "Lp_final.npy", "Lp_final_corrige.npy"
    FICHIER_CORRECTION = "correction_infos.json"   # écrit par la correction ; recopié dans <tag>_corrige
    SUFFIXE_CORRIGE = "_corrige"

    @property
    def fichier_Lp(self):
        """Lp_final.npy, ou Lp_final_corrige.npy si etat_plat (image 0 = état plat)."""
        return self.dossier_entree / (self.FICHIER_LP_CORRIGE if self.etat_plat else self.FICHIER_LP)

    @property
    def tag(self):
        """Nom du sous-dossier de la méthode : Lpform_4, Spform_555, nZ_12..."""
        return self.METHODES[self.methode][0].format(self.degre)

    @property
    def dossier_sortie(self):
        """<essai>/reconstruction/<tag> (ou <tag>_corrige avec l'état plat) : un sous-dossier par méthode."""
        return (Path(self.dossier_essai) / self.SOUS_DOSSIER_SORTIE
                / (self.tag + (self.SUFFIXE_CORRIGE if self.etat_plat else "")))

    @property
    def dossier_mesure(self):
        """<essai>/mesure : images, utilisées seulement par Zernike (taille des caméras)."""
        return Path(self.dossier_essai) / self.SOUS_DOSSIER_MESURE

    def dossiers_calib(self):
        """Dossiers Results_Calib trouvés dans l'essai ou au-dessus, du plus proche au plus loin."""
        trouves = []
        essai = Path(self.dossier_essai).resolve()
        for parent in [essai, *essai.parents]:
            for nom in self.NOMS_DOSSIER_CALIB:
                d = parent / nom
                if d.is_dir() and d not in trouves:
                    trouves.append(d)
        return trouves

    def _complet(self, dossier, methode):
        return all((dossier / f).is_file() for f in self.METHODES[methode][1])

    def dossier_constantes(self):
        """Dossier de l'étalonnage (méthode, degré) le plus proche, ou None."""
        for d in self.dossiers_calib():
            cand = d / self.tag
            if self._complet(cand, self.methode):
                return cand
        return None

    def degres_disponibles(self, methode=None):
        """Degrés pour lesquels un étalonnage complet de cette méthode existe."""
        methode = methode or self.methode
        modele = self.METHODES[methode][0]
        prefixe = modele.split("{}")[0]
        degres = set()
        for d in self.dossiers_calib():
            for cand in d.glob(modele.format("*")):
                m = re.fullmatch(re.escape(prefixe) + r"(\d+)", cand.name)
                if m and self._complet(cand, methode):
                    degres.add(int(m.group(1)))
        return sorted(degres)

    def infos_Lp(self):
        """(nombre d'images, nombre de points) de Lp_final.npy, ou None s'il n'existe pas."""
        if not self.fichier_Lp.is_file():
            return None
        Lp = np.load(self.fichier_Lp, allow_pickle=True, mmap_mode="r")
        return Lp.shape[0], Lp.shape[2]

    # ----- point d'entrée -----

    def lancer(self):
        """Coordonnées 3D de toutes les images ; enregistre X3d/Y3d/Z3d.txt et les figures.

        Renvoie X, Y, Z : tableaux (images, points). Restent aussi en attributs.
        """
        if not self.fichier_Lp.is_file():
            if self.etat_plat:
                raise FileNotFoundError(f"{self.fichier_Lp} introuvable : lancer d'abord la correction par "
                                        "l'état plat (ou décocher « état plat »).")
            raise FileNotFoundError(f"{self.fichier_Lp} introuvable : lancer d'abord la détection des taches "
                                    f"(Lp_final.npy attendu dans {self.dossier_entree}).")
        constantes = self.charger_constantes()
        Lp = np.load(self.fichier_Lp, allow_pickle=True)

        X, Y, Z = [], [], []
        for i, (gauche, droite) in enumerate(Lp):
            print(f"Identification 3D ({self.methode}) : image {i + 1} / {len(Lp)}", end="\r")
            x, y, z = self.identifier(gauche, droite, constantes)
            X.append(x); Y.append(y); Z.append(z)
        print()
        self.X, self.Y, self.Z = (np.array(v, dtype=float) for v in (X, Y, Z))
        self.Z *= self.facteur_z               # correction d'échelle de Z (aussi dans Z3d.txt)

        self.enregistrer()
        if self.enregistrer_figures or self.afficher_figures:
            for n in self.images_a_tracer:
                self.tracer(n)
        return self.X, self.Y, self.Z

    # ----- étalonnage -----

    def charger_constantes(self):
        """Constantes de l'étalonnage choisi (plus la taille des caméras pour Zernike)."""
        d = self.dossier_constantes()
        if d is None:
            cherches = [str(c / self.tag) for c in self.dossiers_calib()] or \
                       ["(aucun dossier Results_Calib au-dessus de l'essai)"]
            raise FileNotFoundError(f"Étalonnage {self.methode} {self.tag} introuvable "
                                    f"({', '.join(self.METHODES[self.methode][1])}).\nCherché :\n  "
                                    + "\n  ".join(cherches))
        print(f"Étalonnage {self.methode} : {d}")
        constantes = [np.load(d / f) for f in self.METHODES[self.methode][1]]
        if self.methode == "Zernike":
            constantes.append(self.taille_cameras(d))
        return constantes

    def taille_cameras(self, dossier_calib):
        """Dimensions des caméras, nécessaires à Zernike_identification."""
        return data.cameras_size(
            cam1_folder=os.path.join(str(self.dossier_mesure), "video_extenso_left", ""),
            cam2_folder=os.path.join(str(self.dossier_mesure), "video_extenso_right", ""),
            name="calibration",
            saving_folder=str(dossier_calib) + "/",
            ncx=Calibration.NCX, ncy=Calibration.NCY, sqr=Calibration.SQR)

    def identifier(self, gauche, droite, constantes):
        """Points 3D (x, y, z) des taches d'une image."""
        if self.methode == "Lagrange":
            (L_constants,) = constantes
            return pcs.Lagrange_identification(gauche, droite, L_constants, self.degre)
        if self.methode == "Soloff":
            S_constants0, S_constants = constantes
            return pcs.Soloff_identification(gauche, droite, S_constants0, S_constants,
                                             Soloff_pform=self.degre, method=self.SOLOFF_METHODE)
        A_constant, C_dim = constantes
        return pcs.Zernike_identification(gauche, droite, A_constant, self.degre, C_dim)

    # ----- résultats -----

    def enregistrer(self):
        self.dossier_sortie.mkdir(parents=True, exist_ok=True)
        for nom, val in (("X3d", self.X), ("Y3d", self.Y), ("Z3d", self.Z)):
            np.savetxt(self.dossier_sortie / f"{nom}.txt", val)
        # méthode et facteur Z utilisés : relus par la correction (reconstruction de l'état plat)
        with open(self.dossier_sortie / self.FICHIER_INFOS, "w", encoding="utf-8") as f:
            json.dump({"methode": self.methode, "degre": self.degre, "facteur_z": self.facteur_z,
                       "etalonnage": str(self.dossier_constantes()), "etat_plat": bool(self.etat_plat)},
                      f, indent=1, ensure_ascii=False)
        marque = self.dossier_sortie / self.FICHIER_CORRECTION
        if self.etat_plat:          # marque d'une source corrigée (lue par la déformation et l'anisotropie)
            source = self.dossier_entree / self.FICHIER_CORRECTION
            marque.write_text(source.read_text(encoding="utf-8") if source.is_file() else "{}", encoding="utf-8")
        elif marque.is_file():
            marque.unlink()
        print(f"X3d.txt, Y3d.txt, Z3d.txt enregistrés dans {self.dossier_sortie} "
              f"({self.X.shape[0]} images, {self.X.shape[1]} points)")

    # places de z_bleu et z_jaune dans viridis (0 = violet foncé, 0.25 = bleu, 0.9 = jaune, 1 = jaune vif)
    POSITION_BLEU = 0.25
    POSITION_JAUNE = 0.9

    def norme_couleurs(self):
        """Normalisation de la colormap : None (automatique) ou échelle fixe par morceaux.

        L'échelle va de z_min à z_max ; z_bleu tombe à POSITION_BLEU (bleu) et z_jaune à
        POSITION_JAUNE (jaune), linéairement entre ces points. Hors [z_min, z_max] : couleur du bout.
        """
        if not self.couleurs_fixes:
            return None
        zs = [self.z_min, self.z_bleu, self.z_jaune, self.z_max]
        if not all(a < b for a, b in zip(zs, zs[1:])):
            raise ValueError(f"Échelle de couleur : il faut z_min < z_bleu < z_jaune < z_max ({zs})")
        ps = [0.0, self.POSITION_BLEU, self.POSITION_JAUNE, 1.0]
        return mcolors.FuncNorm((lambda z: np.interp(z, zs, ps, left=-0.01, right=1.01),
                                 lambda p: np.interp(p, ps, zs)),
                                vmin=self.z_min, vmax=self.z_max)

    def ligne_image(self, n):
        """Numéro d'image (0 = état plat, 1..n = photos de l'essai ; -1 = dernière) -> ligne de X, Y, Z."""
        nb = len(self.X)
        if n < 0:
            return range(nb)[n]
        if not self.etat_plat:
            if n == 0:
                raise IndexError("Image 0 (état plat) : disponible seulement avec l'état plat")
            n -= 1                                         # Lp_final.npy : ligne 0 = photo 1 de l'essai
        return range(nb)[n]

    def tracer(self, n):
        """Nuage 3D de l'image n (0 = état plat, 1..n = photos de l'essai ; -1 = dernière)."""
        ligne = self.ligne_image(n)
        num = ligne if self.etat_plat else ligne + 1       # numéro affiché (titre, nom du fichier)
        derniere = len(self.X) - 1 if self.etat_plat else len(self.X)
        x, y, z = self.X[ligne], self.Y[ligne], self.Z[ligne]
        if self.deplacement:
            z = z - self.Z[0]              # nouveau tableau : self.Z reste intact
        if self.inverser_z:
            z = -z
        ok = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
        if self.exclusions_manuelles:                             # taches exclues à la main (retouche_gui)
            from Pycaso.retouche_class import ExclusionsTaches
            ok &= ~ExclusionsTaches(self.dossier_essai, self.dossier_sortie.name).masque_colonnes(len(x))
        x, y, z = x[ok], y[ok], z[ok]

        fig = plt.figure(figsize=(16, 9))
        ax = plt.axes(projection="3d")
        ax.grid(visible=True, color="grey", linestyle="-.", linewidth=0.3, alpha=0.2)
        ax.set_xlabel("X"); ax.set_ylabel("Y"); ax.set_zlabel("Z")
        ax.set_xlim(-10, 90); ax.set_ylim(-10, 90)
        if self.deplacement:               # déplacement : axe vertical fixé ; position : automatique
            ax.set_zlim(-10, 90)
        sctt = ax.scatter3D(x, y, z, alpha=0.8, c=z, cmap=plt.get_cmap("viridis"),
                            norm=self.norme_couleurs())
        ax.set_box_aspect((1, 1, 0.4))
        try:
            ax.set_aspect("equal")
        except NotImplementedError:        # anciennes versions de matplotlib
            pass
        quoi = "déplacement Z" if self.deplacement else "Z"
        plt.title(f"{self.methode} {self.tag} - image {num} / {derniere} - {quoi} (mm), "
                  f"{ok.sum()} points")
        cbar = fig.colorbar(sctt, ax=ax, shrink=0.5, aspect=5,
                            extend="both" if self.couleurs_fixes else "neither")
        if self.couleurs_fixes:            # échelle par morceaux : graduer seulement les 4 valeurs
            cbar.set_ticks([self.z_min, self.z_bleu, self.z_jaune, self.z_max])
            cbar.set_ticklabels([f"{v:g}" for v in (self.z_min, self.z_bleu, self.z_jaune, self.z_max)])
        if self.enregistrer_figures:
            plt.savefig(self.dossier_sortie / f"Déplacement_{num}-{derniere}.svg")
        if self.afficher_figures:
            plt.show()
        plt.close(fig)