"""Pression en fonction du déplacement hors plan maximal Uz max, image par image.

Remplace getuzpress.py. Pour chaque image de la reconstruction :
  - Uz max = plus grand déplacement hors plan des taches (z − z de l'image de référence),
    ou un centile élevé pour ne pas dépendre d'une seule tache ;
  - temps de l'image = lu dans son nom (000012_4.567.tiff -> 4.567 s), dans video_extenso_left ;
  - pression = celle du capteur (data_ali.txt : temps, pression) au temps de l'image, interpolée
    linéairement entre les deux mesures qui l'encadrent (ou mesure la plus proche), relative à la
    première mesure si demandé. Si les deux horloges ne partent pas du même instant, decalage_temps
    les recale : temps capteur = temps image + decalage_temps.

  - déformation de Green-Lagrange E (classe Deformation, par rapport à l'image 0) en un point de mesure :
    Exx, Eyy, Ezz. Le point est une tache (point_centre, choisie sur la photo avec point_gui), par défaut
    celle qui est la plus proche du centre de la zone initiale.

Trois figures sont toujours tracées : Uz max = f(pression), pression et Uz max = f(temps),
pression = f(E au centre du dôme).

Les taches sont chargées comme pour la déformation (classe Deformation) : exclusions manuelles,
filtre des aberrants et sens de z (dôme vers le haut) y sont appliqués.

Numérotation des images : 0 = état plat (seulement pour une source corrigée), 1..n = photos de
l'essai (la k-ième image de video_extenso_left).

Fichiers :
    <essai>/reconstruction/<source>/      X3d, Y3d, Z3d (entrée)
    <essai>/video_extenso_left/           images de l'essai : temps dans le nom (entrée)
    <essai>/data_ali.txt                  temps, pression du capteur (entrée)
    <essai>/pression/<source>/            pression_uz.txt (avec Exx, Eyy, Ezz au centre) et figures (sortie)
"""
import glob
import os
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from Pycaso.deformation_class import Deformation
from Pycaso.reconstruction_class import Detect3D

FICHIER_CORRECTION = "correction_infos.json"      # présent dans une source corrigée (image 0 = état plat)


def numero_image(chemin):
    """Numéro de l'image, lu au début de son nom (000012_4.567.tiff -> 12)."""
    try:
        return int(os.path.basename(chemin).split("_")[0])
    except ValueError:
        return 99999


def temps_image(chemin):
    """Temps (s) lu dans le nom de l'image (000012_4.567.tiff -> 4.567) ; NaN s'il n'y en a pas."""
    nom = os.path.basename(chemin)
    if "_" not in nom:
        return float("nan")
    partie = nom.split("_", 1)[1]
    for essai in (partie.split(".t")[0], os.path.splitext(partie)[0]):     # .tif / .tiff, puis autre extension
        try:
            return float(essai)
        except ValueError:
            pass
    return float("nan")


class PressionUz:
    """Courbe pression = f(Uz max) d'un essai."""

    SOUS_DOSSIER_SORTIE = "pression"
    DOSSIER_IMAGES = "video_extenso_left"

    def __init__(self,
                 # --- Essai ---
                 dossier_essai=None,        # ex. ../../Expériences/2026_10_29/essai1 ; None = <aujourd'hui>/essai1
                 source=None,               # reconstruction (Lpform_4, Lpform_4_corrige...) ; None = la première
                 # --- Pression ---
                 fichier_pression="data_ali.txt",   # nom seul : dans le dossier de l'essai ; sinon chemin
                                                    # absolu ou relatif au dossier d'exécution
                 colonne_temps=0,
                 colonne_pression=1,
                 separateur=",",
                 lignes_entete=1,
                 pression_relative=True,    # pression − première mesure du capteur
                 unite_pression="mbar",
                 decalage_temps=0.0,        # (s) temps capteur = temps image + décalage (horloges non synchrones)
                 interpolation="lineaire",  # "lineaire" (entre les 2 mesures qui encadrent) ou "proche"
                 # --- Uz max ---
                 reference_deplacement=0,   # Uz = z − z(image de référence) ; 0 = état plat si source corrigée
                 centile=100.0,             # 100 = maximum ; 99 ou 99.5 : moins sensible à une tache isolée
                 inverser_z=None,           # None = auto (dôme vers le haut) ; voir Deformation
                 exclusions_manuelles=True, # retirer les taches exclues à la main (retouche_gui)
                 # --- Déformation au centre du dôme (E de Green-Lagrange) ---
                 point_centre=None,         # tache où E est lue (indice de colonne de X3d, voir choisir_point) ;
                                            # None = la tache la plus proche du centre de la zone initiale
                 taille_grille=100,         # grille de la classe Deformation
                 interpolation_deformation="rbf",   # "rbf", "rbf_polynome" ou "griddata" ; voir Deformation
                 # --- Résultats ---
                 enregistrer_resultats=True,
                 enregistrer_figures=True,
                 afficher_figures=True):
        self.dossier_essai = dossier_essai or Detect3D.chemin_par_defaut(time.strftime("%Y_%m_%d"))
        if source is None:
            dispo = Deformation(dossier_essai=self.dossier_essai, source="-").sources_disponibles()
            source = dispo[0] if dispo else Deformation.SOURCE_DEFAUT
        self.source = source
        self.fichier_pression = fichier_pression
        self.colonne_temps = int(colonne_temps)
        self.colonne_pression = int(colonne_pression)
        self.separateur = separateur
        self.lignes_entete = int(lignes_entete)
        self.pression_relative = pression_relative
        self.unite_pression = unite_pression
        self.decalage_temps = float(decalage_temps)
        if interpolation not in ("lineaire", "proche"):
            raise ValueError(f"interpolation : 'lineaire' ou 'proche' (pas {interpolation})")
        self.interpolation = interpolation
        self.reference_deplacement = int(reference_deplacement)
        self.centile = float(centile)
        self.inverser_z = inverser_z
        self.exclusions_manuelles = exclusions_manuelles
        if interpolation_deformation not in Deformation.INTERPOLATIONS:
            raise ValueError(f"interpolation_deformation inconnue : {interpolation_deformation} "
                             f"(choix : {', '.join(Deformation.INTERPOLATIONS)})")
        self.point_centre = None if point_centre is None else int(point_centre)
        self.indice_point = None
        self.taille_grille = int(taille_grille)
        self.interpolation_deformation = interpolation_deformation
        self.enregistrer_resultats = enregistrer_resultats
        self.enregistrer_figures = enregistrer_figures
        self.afficher_figures = afficher_figures

    RESULTATS = ("resultats", "deformation")

    def parametres(self):
        """Paramètres sous forme de dictionnaire (pour affichage)."""
        return {k: v for k, v in vars(self).items() if k not in self.RESULTATS}

    # ----- chemins -----

    @property
    def dossier_source(self):
        return Path(self.dossier_essai) / Detect3D.SOUS_DOSSIER_SORTIE / self.source

    @property
    def dossier_sortie(self):
        """<essai>/pression/<source>."""
        return Path(self.dossier_essai) / self.SOUS_DOSSIER_SORTIE / self.source

    @property
    def chemin_pression(self):
        """Nom seul (data_ali.txt) : dans le dossier de l'essai ; sinon le chemin tel quel."""
        p = Path(self.fichier_pression)
        return p if p.is_absolute() or p.parent != Path(".") else Path(self.dossier_essai) / p

    @property
    def est_corrigee(self):
        return (self.dossier_source / FICHIER_CORRECTION).is_file()

    def images_essai(self):
        """Images de l'essai (video_extenso_left), triées par numéro ; les masques et photo_init sont ignorés."""
        d = Path(self.dossier_essai) / self.DOSSIER_IMAGES
        return sorted(glob.glob(str(d / "[0-9]*")), key=numero_image)

    def lire_pression(self):
        """(temps, pression) du capteur, triés par temps ; pression relative à la 1re mesure si demandé."""
        donnees = np.loadtxt(self.chemin_pression, delimiter=self.separateur or None, skiprows=self.lignes_entete,
                             ndmin=2)
        t, p = donnees[:, self.colonne_temps], donnees[:, self.colonne_pression]
        if self.pression_relative:
            p = p - p[0]                                 # 1re mesure dans l'ordre du fichier, comme getuzpress
        ordre = np.argsort(t)
        return t[ordre], p[ordre]

    @staticmethod
    def ligne(numero, nb_lignes, corrigee):
        """Numéro d'image (0 = état plat, 1..n = photos, -1 = dernière) -> ligne de X3d.

        Sans état plat (source non corrigée), l'image 0 n'existe pas : la 1re photo est prise à la place.
        """
        if numero < 0:
            return range(nb_lignes)[numero]
        if not corrigee:
            numero = max(numero - 1, 0)
        return range(nb_lignes)[numero]

    def pression_aux_temps(self, t, t_p, p_p):
        """Pression aux temps t (NaN hors de la plage du capteur) : interpolation linéaire ou mesure la plus proche."""
        if self.interpolation == "lineaire":
            return np.interp(t, t_p, p_p, left=np.nan, right=np.nan)
        res = np.full(len(t), np.nan)
        ok = np.isfinite(t) & (t >= t_p[0]) & (t <= t_p[-1])
        i = np.clip(np.searchsorted(t_p, t[ok]), 1, len(t_p) - 1)
        plus_proche = np.where(np.abs(t_p[i - 1] - t[ok]) <= np.abs(t_p[i] - t[ok]), i - 1, i)
        res[ok] = p_p[plus_proche]
        return res

    @staticmethod
    def ecart_mesure(t, t_p):
        """Écart (s) entre chaque temps t et la mesure du capteur la plus proche."""
        res = np.full(len(t), np.nan)
        ok = np.isfinite(t)
        i = np.clip(np.searchsorted(t_p, t[ok]), 1, len(t_p) - 1)
        res[ok] = np.minimum(np.abs(t_p[i - 1] - t[ok]), np.abs(t_p[i] - t[ok]))
        return res

    # ----- point de mesure -----

    EXTENSIONS_IMAGES = (".tif", ".tiff", ".svg", ".jpg", ".jpeg", ".bmp")
    DOSSIERS_PHOTOS = {"L": "video_extenso_left", "R": "video_extenso_right"}

    def _deformation(self):
        """Deformation réglée comme ce calcul (chargement des taches, grille, interpolation)."""
        return Deformation(dossier_essai=self.dossier_essai, source=self.source,
                           inverser_z=self.inverser_z, 
                           exclusions_manuelles=self.exclusions_manuelles,
                           taille_grille=self.taille_grille,
                           interpolation=self.interpolation_deformation)

    @property
    def fichier_Lp(self):
        """Lp_final.npy (positions en pixels des taches), ou Lp_final_corrige.npy pour une source corrigée."""
        nom = Detect3D.FICHIER_LP_CORRIGE if self.est_corrigee else Detect3D.FICHIER_LP
        return Path(self.dossier_essai) / Detect3D.SOUS_DOSSIER_ENTREE / nom

    def pixels_taches(self, nb_colonnes):
        """Positions en pixels (x, y) des taches de l'image 0 : [gauche, droite], chacune (nb_colonnes, 2).

        Les colonnes sont celles de X3d : un indice de tache désigne le même point matériel partout.
        Image 0 = état plat (photo_init) pour une source corrigée, sinon la 1re photo de l'essai.
        """
        Lp = np.load(self.fichier_Lp, allow_pickle=True)
        ligne = 0
        res = []
        for cote in (0, 1):
            p = np.asarray(Lp[ligne][cote], dtype=float)
            if p.ndim == 2 and p.shape[0] != nb_colonnes and p.shape[1] == nb_colonnes:
                p = p.T                                    # stocké (2, taches)
            if p.ndim != 2 or p.shape[0] != nb_colonnes or p.shape[1] < 2:
                raise ValueError(f"{self.fichier_Lp.name} : {p.shape} ne correspond pas aux "
                                 f"{nb_colonnes} taches de X3d")
            res.append(p[:, :2])
        return res

    def chemin_photo_init(self, cote):
        """photo_init de la caméra "L" ou "R" (dans video_extenso_left / _right, sinon dans l'essai) ; None si absente."""
        for d in (Path(self.dossier_essai) / self.DOSSIERS_PHOTOS[cote], Path(self.dossier_essai)):
            trouves = sorted(p for p in d.glob("photo_init*")
                             if p.is_file() and p.suffix.lower() in self.EXTENSIONS_IMAGES)
            propres = [p for p in trouves if p.stem.lower().endswith(cote.lower())]
            if propres or (trouves and d.name == self.DOSSIERS_PHOTOS[cote]):
                return (propres or trouves)[0]
        return None

    @staticmethod
    def indice_centre(d):
        """Tache (colonne de X3d) la plus proche du centre de la zone initiale (image 0) ; d : Deformation chargée."""
        x0, y0 = d.X[0], d.Y[0]
        ok = np.isfinite(x0) & np.isfinite(y0) & np.isfinite(d.Z[0])
        if not ok.any():
            raise ValueError("Aucune tache valide à l'image 0")
        xc, yc = (x0[ok].min() + x0[ok].max()) / 2, (y0[ok].min() + y0[ok].max()) / 2
        dist = np.hypot(x0 - xc, y0 - yc)
        dist[~ok] = np.inf
        return int(np.argmin(dist))

    def deformation_centre(self, d):
        """Exx, Eyy, Ezz (Green-Lagrange, / image 0) de chaque image au point de mesure.

        Le point est la tache point_centre (colonne de X3d), ou la plus proche du centre de la zone initiale
        si point_centre est None. E est lu au nœud de la grille le plus proche de sa position initiale.
        d : Deformation dont les taches sont déjà chargées (charger). Seul ce point est conservé pour chaque
        image, pour ne pas garder tous les champs en mémoire.
        Renvoie ((x, y) du nœud, tableau (images, 3)) ; l'indice de la tache est dans self.indice_point.
        """
        j = self.indice_centre(d) if self.point_centre is None else self.point_centre
        if not 0 <= j < d.X.shape[1]:
            raise ValueError(f"Tache {j} inexistante ({d.X.shape[1]} taches : 0 à {d.X.shape[1] - 1})")
        if not (np.isfinite(d.X[0, j]) and np.isfinite(d.Y[0, j]) and np.isfinite(d.Z[0, j])):
            raise ValueError(f"Tache {j} absente, exclue ou aberrante à l'image 0 : en choisir une autre")
        self.indice_point = j
        d.grille = d.construire_grille()
        d._r_ref = (None, None)
        g = d.grille
        dist = (g["X"] - d.X[0, j]) ** 2 + (g["Y"] - d.Y[0, j]) ** 2
        dist[~g["dedans"]] = np.inf                        # nœud hors du masque : NaN
        ic, jc = np.unravel_index(np.argmin(dist), dist.shape)
        centre = (float(g["X"][ic, jc]), float(g["Y"][ic, jc]))
        nb = len(d.X)
        E = np.full((nb, 3), np.nan)
        for k in range(nb):
            print(f"Déformation au point {j} : image {k + 1} / {nb}", end="\r")
            E[k] = np.diag(d.calculer(k)["E"][ic, jc])
        print()
        return centre, E

    # ----- point d'entrée -----

    def lancer(self):
        """Calcule Uz max et la pression de chaque image ; enregistre le tableau et les figures.

        Renvoie un dict : image, temps, pression, uz_max (tableaux, une valeur par image de l'essai).
        """
        if not self.chemin_pression.is_file():
            raise FileNotFoundError(f"Fichier de pression introuvable : {self.chemin_pression}")
        self.deformation = d = self._deformation()
        if not d._complet(d.dossier_entree):
            raise FileNotFoundError(f"X3d.txt, Y3d.txt, Z3d.txt introuvables dans {d.dossier_entree}")
        X, Y, Z = d.charger()
        nb_lignes = len(Z)
        corrigee = self.est_corrigee
        decalage = 0 if corrigee else 1                   # numéro d'image = ligne (+1 sans état plat)
        ref = self.ligne(self.reference_deplacement, nb_lignes, corrigee)
        Uz = Z - Z[ref]
        with np.errstate(all="ignore"):
            uz_max = np.array([np.nanpercentile(u, self.centile) if np.isfinite(u).any() else np.nan for u in Uz])

        # temps des images : la ligne k de la reconstruction est la (k + 1 − décalage)-ième photo de l'essai
        images = self.images_essai()
        nb_photos = nb_lignes - (1 if corrigee else 0)
        if len(images) < nb_photos:
            raise ValueError(f"{len(images)} image(s) dans {Path(self.dossier_essai) / self.DOSSIER_IMAGES}, "
                             f"mais {nb_photos} dans la reconstruction")
        temps_photos = np.array([temps_image(f) for f in images[:nb_photos]])
        if np.isnan(temps_photos).all():
            raise ValueError("Aucun temps lu dans les noms des images (format attendu : 000012_4.567.tiff)")
        temps = np.concatenate(([np.nan], temps_photos)) if corrigee else temps_photos
        numeros = np.arange(nb_lignes) + decalage

        t_p, p_p = self.lire_pression()
        pression = self.pression_aux_temps(temps + self.decalage_temps, t_p, p_p)
        hors = np.isfinite(temps) & ~np.isfinite(pression)
        ecart = self.ecart_mesure(temps + self.decalage_temps, t_p)
        if corrigee:
            pression[0] = 0.0 if self.pression_relative else np.nan      # état plat : avant la mise en pression
        print(f"{nb_photos} photos de l'essai, temps {np.nanmin(temps_photos):.3g} à {np.nanmax(temps_photos):.3g} s ; "
              f"capteur : {len(t_p)} mesures, {t_p.min():.3g} à {t_p.max():.3g} s"
              + (f" ; ⚠ {hors.sum()} image(s) hors de la plage du capteur (pression NaN)" if hors.any() else ""))
        print(f"Pression {'interpolée linéairement' if self.interpolation == 'lineaire' else 'de la mesure la plus proche'}"
              + (f", décalage {self.decalage_temps:+g} s" if self.decalage_temps else "")
              + (f" ; mesure la plus proche à {np.nanmax(ecart):.3g} s au plus d'une image" if np.isfinite(ecart).any() else ""))
        print(f"Uz = z − z(image {numeros[ref]}){' (z inversé)' if d.z_inverse else ''} ; "
              f"Uz max {'= maximum' if self.centile >= 100 else f'= centile {self.centile:g}'} : "
              f"de {np.nanmin(uz_max):.3g} à {np.nanmax(uz_max):.3g} mm")

        self.centre, E = self.deformation_centre(d)
        print(f"E à la tache {self.indice_point}{' (automatique)' if self.point_centre is None else ''}, "
              f"nœud de grille x = {self.centre[0]:.4g} mm, y = {self.centre[1]:.4g} mm ; "
              f"Exx de {np.nanmin(E[:, 0]):.3g} à {np.nanmax(E[:, 0]):.3g}")

        self.resultats = {"image": numeros, "temps": temps, "pression": pression, "uz_max": uz_max,
                          "ecart_mesure": ecart, "Exx": E[:, 0], "Eyy": E[:, 1], "Ezz": E[:, 2]}
        if self.enregistrer_resultats or self.enregistrer_figures:
            self.dossier_sortie.mkdir(parents=True, exist_ok=True)
        if self.enregistrer_resultats:
            np.savetxt(self.dossier_sortie / "pression_uz.txt",
                       np.column_stack((numeros, temps, pression, uz_max, E)),
                       fmt=["%d", "%.6g", "%.6g", "%.6g", "%.6g", "%.6g", "%.6g"],
                       header=f"image temps_s pression_{self.unite_pression} uz_max_mm "
                              f"Exx Eyy Ezz (tache {self.indice_point} : x={self.centre[0]:.4g} "
                              f"y={self.centre[1]:.4g} mm)")
            print(f"Tableau enregistré : {self.dossier_sortie / 'pression_uz.txt'}")
        if self.enregistrer_figures or self.afficher_figures:
            self.tracer()
        return self.resultats

    # ----- figures -----

    def _finir_figure(self, fig, nom):
        if self.enregistrer_figures:
            fig.savefig(self.dossier_sortie / nom)
        if self.afficher_figures:
            plt.show()
        plt.close(fig)

    def tracer(self):
        r = self.resultats
        ok = np.isfinite(r["uz_max"]) & np.isfinite(r["pression"])
        quoi = "Uz max" if self.centile >= 100 else f"Uz (centile {self.centile:g})"
        fig, ax = plt.subplots(figsize=(9, 6), layout="constrained")
        ax.plot(r["pression"][ok], r["uz_max"][ok], "o-", ms=3, label=self.source)
        ax.set_ylabel(f"{quoi} (mm)"); ax.set_xlabel(f"Pression ({self.unite_pression})")
        ax.set_title(f"{Path(self.dossier_essai).name} - {self.source}")
        ax.grid(alpha=0.3); ax.legend(fontsize=10)
        self._finir_figure(fig, "Pression_Uz.svg")

        ok_t = np.isfinite(r["temps"])
        fig, ax1 = plt.subplots(figsize=(9, 6), layout="constrained")
        l1 = ax1.plot(r["temps"][ok_t], r["pression"][ok_t], "o-", ms=3, c="tab:blue",
                      label=f"Pression ({self.unite_pression})")
        ax1.set_xlabel("temps (s)"); ax1.set_ylabel(f"Pression ({self.unite_pression})")
        ax2 = ax1.twinx()
        l2 = ax2.plot(r["temps"][ok_t], r["uz_max"][ok_t], "s-", ms=3, c="tab:orange", label=f"{quoi} (mm)")
        ax2.set_ylabel(f"{quoi} (mm)")
        ax1.legend(l1 + l2, [l.get_label() for l in l1 + l2], loc="best")
        ax1.set_title(f"{Path(self.dossier_essai).name} - {self.source} : pression et {quoi} au cours du temps")
        ax1.grid(alpha=0.3)
        self._finir_figure(fig, "Pression_Uz_temps.svg")

        # pression = f(E) au point central du dôme
        fig, ax = plt.subplots(figsize=(9, 6), layout="constrained")
        for nom, couleur in (("Exx", "tab:blue"), ("Eyy", "tab:orange"), ("Ezz", "tab:green")):
            ok_e = np.isfinite(r[nom]) & np.isfinite(r["pression"])
            ax.plot(r[nom][ok_e], r["pression"][ok_e], "o-", ms=3, c=couleur, label=nom)
        ax.set_xlabel("Déformation de Green-Lagrange E (au point de mesure)")
        ax.set_ylabel(f"Pression ({self.unite_pression})")
        ax.set_title(f"{Path(self.dossier_essai).name} - {self.source} : pression = f(E), tache {self.indice_point} "
                     f"(x = {self.centre[0]:.3g} mm, y = {self.centre[1]:.3g} mm)")
        ax.grid(alpha=0.3); ax.legend(fontsize=10)
        self._finir_figure(fig, "Pression_E_centre.svg")