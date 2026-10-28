"""Pression en fonction du déplacement hors plan maximal Uz max, image par image.

Remplace getuzpress.py. Pour chaque image de la reconstruction :
  - Uz max = plus grand déplacement hors plan des taches (z − z de l'image de référence),
    ou un centile élevé pour ne pas dépendre d'une seule tache ;
  - temps de l'image = lu dans son nom (000012_4.567.tiff -> 4.567 s), dans video_extenso_left ;
  - pression = interpolée linéairement au temps de l'image dans le fichier du capteur
    (data_ali.txt : temps, pression), relative à la première mesure si demandé.

Les taches sont chargées comme pour la déformation (classe Deformation) : exclusions manuelles,
filtre des aberrants et sens de z (dôme vers le haut) y sont appliqués.

Numérotation des images : 0 = état plat (seulement pour une source corrigée), 1..n = photos de
l'essai (la k-ième image de video_extenso_left).

Fichiers :
    <essai>/reconstruction/<source>/      X3d, Y3d, Z3d (entrée)
    <essai>/video_extenso_left/           images de l'essai : temps dans le nom (entrée)
    <essai>/data_ali.txt                  temps, pression du capteur (entrée)
    <essai>/pression/<source>/            pression_uz.txt et figures (sortie)
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
                 date=None,                 # AAAA_MM_JJ ; None = aujourd'hui
                 dossier_essai=None,        # ex. <date>/essai1 ; None = <date>/essai1
                 source=None,               # reconstruction (Lpform_4, Lpform_4_corrige...) ; None = la première
                 # --- Pression ---
                 fichier_pression="data_ali.txt",   # relatif au dossier de l'essai, ou chemin absolu
                 colonne_temps=0,
                 colonne_pression=1,
                 separateur=",",
                 lignes_entete=1,
                 pression_relative=True,    # pression − première mesure du capteur
                 unite_pression="mbar",
                 # --- Uz max ---
                 reference_deplacement=0,   # Uz = z − z(image de référence) ; 0 = état plat si source corrigée
                 centile=100.0,             # 100 = maximum ; 99 ou 99.5 : moins sensible à une tache isolée
                 inverser_z=None,           # None = auto (dôme vers le haut) ; voir Deformation
                 seuil_aberrants=2.0,       # filtre des taches aberrantes (mm), 0 = aucun ; voir Deformation
                 exclusions_manuelles=True, # retirer les taches exclues à la main (selection_gui)
                 # --- Résultats ---
                 tracer_temps=True,         # figure supplémentaire : pression et Uz max en fonction du temps
                 enregistrer_resultats=True,
                 enregistrer_figures=True,
                 afficher_figures=True):
        self.date = date or time.strftime("%Y_%m_%d")
        self.dossier_essai = dossier_essai or Detect3D.chemin_par_defaut(self.date)
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
        self.reference_deplacement = int(reference_deplacement)
        self.centile = float(centile)
        self.inverser_z = inverser_z
        self.seuil_aberrants = seuil_aberrants
        self.exclusions_manuelles = exclusions_manuelles
        self.tracer_temps = tracer_temps
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
        p = Path(self.fichier_pression)
        return Path(self.dossier_essai) / p

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

    # ----- point d'entrée -----

    def lancer(self):
        """Calcule Uz max et la pression de chaque image ; enregistre le tableau et les figures.

        Renvoie un dict : image, temps, pression, uz_max (tableaux, une valeur par image de l'essai).
        """
        if not self.chemin_pression.is_file():
            raise FileNotFoundError(f"Fichier de pression introuvable : {self.chemin_pression}")
        self.deformation = d = Deformation(date=self.date, dossier_essai=self.dossier_essai, source=self.source,
                                           inverser_z=self.inverser_z, seuil_aberrants=self.seuil_aberrants,
                                           exclusions_manuelles=self.exclusions_manuelles)
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
        pression = np.interp(temps, t_p, p_p, left=np.nan, right=np.nan)
        hors = np.isfinite(temps) & ~np.isfinite(pression)
        if corrigee:
            pression[0] = 0.0 if self.pression_relative else np.nan      # état plat : avant la mise en pression
        print(f"{nb_photos} photos de l'essai, temps {np.nanmin(temps_photos):.3g} à {np.nanmax(temps_photos):.3g} s ; "
              f"capteur : {len(t_p)} mesures, {t_p.min():.3g} à {t_p.max():.3g} s"
              + (f" ; ⚠ {hors.sum()} image(s) hors de la plage du capteur (pression NaN)" if hors.any() else ""))
        print(f"Uz = z − z(image {numeros[ref]}){' (z inversé)' if d.z_inverse else ''} ; "
              f"Uz max {'= maximum' if self.centile >= 100 else f'= centile {self.centile:g}'} : "
              f"de {np.nanmin(uz_max):.3g} à {np.nanmax(uz_max):.3g} mm")

        self.resultats = {"image": numeros, "temps": temps, "pression": pression, "uz_max": uz_max}
        if self.enregistrer_resultats or self.enregistrer_figures:
            self.dossier_sortie.mkdir(parents=True, exist_ok=True)
        if self.enregistrer_resultats:
            np.savetxt(self.dossier_sortie / "pression_uz.txt",
                       np.column_stack((numeros, temps, pression, uz_max)), fmt=["%d", "%.6g", "%.6g", "%.6g"],
                       header=f"image temps_s pression_{self.unite_pression} uz_max_mm")
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
        ax.plot(r["uz_max"][ok], r["pression"][ok], "o-", ms=3, label=self.source)
        ax.set_xlabel(f"{quoi} (mm)"); ax.set_ylabel(f"Pression ({self.unite_pression})")
        ax.set_title(f"{Path(self.dossier_essai).name} - {self.source}")
        ax.grid(alpha=0.3); ax.legend(fontsize=10)
        self._finir_figure(fig, "Pression_Uz.png")

        if self.tracer_temps:
            ok_t = np.isfinite(r["temps"])
            fig, ax1 = plt.subplots(figsize=(9, 6), layout="constrained")
            ax1.plot(r["temps"][ok_t], r["pression"][ok_t], "o-", ms=3, c="tab:blue")
            ax1.set_xlabel("temps (s)"); ax1.set_ylabel(f"Pression ({self.unite_pression})", color="tab:blue")
            ax2 = ax1.twinx()
            ax2.plot(r["temps"][ok_t], r["uz_max"][ok_t], "s-", ms=3, c="tab:orange")
            ax2.set_ylabel(f"{quoi} (mm)", color="tab:orange")
            ax1.set_title(f"{Path(self.dossier_essai).name} - {self.source} : pression et {quoi} au cours du temps")
            ax1.grid(alpha=0.3)
            self._finir_figure(fig, "Pression_Uz_temps.png")