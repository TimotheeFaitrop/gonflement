"""Champs de déformation à partir des positions 3D reconstruites (X3d, Y3d, Z3d).

Remplace getdef.py. Les positions des taches sont interpolées sur une grille régulière
construite sur la configuration initiale (image 0) ; on en déduit, pour chaque image traitée :

    U    déplacement (x, y, z)                       Ux, Uy, Uz
    F1   gradient surfacique 3x2 (dérivées en X, Y)
    J    rapport de surfaces det U1 = |dr/dX ^ dr/dY|  (U1 = sqrt(F1ᵀF1))
    F    gradient 3x3 : [F1 | n / J]                 (incompressibilité : λ3 = 1 / (λ1 λ2))
    C    Cauchy-Green droit FᵀF
    E    Green-Lagrange ½ (C − I)
    H    Hencky lagrangien ½ ln(FᵀF)
    LE   Hencky eulérien ½ ln(FFᵀ)                   (« LE » d'Abaqus)
    I1, I2  invariants de C

Organisation des dossiers (dossier_essai = <date>/essai1) :
    <essai>/reconstruction/<source>/   X3d.txt, Y3d.txt, Z3d.txt (entrée, source = Lpform_4, nZ_12...)
    <essai>/deformation/<source>/      champs_<n>.npz et figures (sortie)
"""
import os
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import RBFInterpolator, Rbf, griddata

from Pycaso.reconstruction_class import Detect3D


class Deformation:
    """Champs de déformation (F, E, H, LE...) d'un essai, pour les images choisies."""

    # nom : (titre, nature) ; nature = "tenseur" (3x3), "vecteur" (x, y, z) ou "scalaire"
    GRANDEURS = {
        "U":  ("Déplacement (mm)", "vecteur"),
        "F":  ("Gradient de la transformation F", "tenseur"),
        "C":  ("Cauchy-Green droit C = tF.F", "tenseur"),
        "E":  ("Green-Lagrange E = ½(C − I)", "tenseur"),
        "H":  ("Hencky lagrangien ½ ln(tF.F)", "tenseur"),
        "LE": ("Hencky eulérien ½ ln(F.tF) (LE Abaqus)", "tenseur"),
        "J":  ("Rapport de surfaces J = det U1", "scalaire"),
        "I1": ("Premier invariant I1 = tr C", "scalaire"),
        "I2": ("Second invariant I2", "scalaire"),
    }
    COMPOSANTES = {"xx": (0, 0), "yy": (1, 1), "zz": (2, 2),
                   "xy": (0, 1), "xz": (0, 2), "yz": (1, 2)}
    # interpolation : fonctions de base radiale proposées (la première est la valeur par défaut)
    #   rbf          : scipy Rbf, comme getdef.py ; ne reproduit pas exactement un champ linéaire
    #   rbf_polynome : RBFInterpolator + polynôme de degré 1 : plus précis, option voisins pour la vitesse
    #   griddata     : interpolation linéaire par triangles (rapide, gradients constants par triangle)
    INTERPOLATIONS = {
        "rbf": ("linear", "cubic", "thin_plate", "multiquadric", "inverse", "gaussian", "quintic"),
        "rbf_polynome": ("thin_plate_spline", "cubic", "linear", "quintic"),
        "griddata": (),
    }
    MASQUES = ("disque", "enveloppe", "aucun")

    SOUS_DOSSIER_ENTREE = Detect3D.SOUS_DOSSIER_SORTIE    # "reconstruction"
    SOUS_DOSSIER_SORTIE = "deformation"
    FICHIERS = ("X3d.txt", "Y3d.txt", "Z3d.txt")
    SOURCE_DEFAUT = "Lpform_4"

    def __init__(self,
                 # --- Essai à traiter ---
                 date=None,                 # AAAA_MM_JJ ; None = aujourd'hui
                 dossier_essai=None,        # ex. <date>/essai1 ; None = <date>/essai1
                 source=None,               # sous-dossier de reconstruction/ (Lpform_4, nZ_12...) ; None = le premier trouvé
                 # --- Calcul ---
                 taille_grille=100,         # nombre de points de la grille par côté
                 interpolation="rbf",       # "rbf" (comme getdef.py), "rbf_polynome" (plus précis) ou "griddata"
                 fonction_rbf=None,         # fonction de base radiale ; None = la première de INTERPOLATIONS
                 lissage=0.0,               # lissage des RBF (0 = passe exactement par les taches)
                 voisins=0,                 # rbf_polynome : nb de taches voisines utilisées (0 = toutes)
                 masque="disque",           # "disque", "enveloppe" (des taches) ou "aucun"
                 rayon_masque=1.0,          # rayon du disque / demi-largeur de la zone initiale
                 inverser_z=None,           # changer le signe de Z : None = auto (dôme vers le haut), True / False
                 # --- Images et figures ---
                 images=(-1,),              # indices des images traitées (-1 = dernière)
                 grandeurs=("F",),          # grandeurs tracées (clés de GRANDEURS)
                 composantes=("xx", "yy", "zz"),   # composantes tracées des tenseurs
                 nuage_3d=False,            # tracer aussi le nuage de points 3D
                 nuage_deplacement=True,    # nuage 3D : tracer z − z(image 0) plutôt que z
                 enregistrer_champs=True,   # champs_<n>.npz : tous les champs de l'image n
                 enregistrer_figures=True,  # figures en .png
                 afficher_figures=True):    # ouvrir les figures à l'écran
        for nom, val, choix in (("interpolation", interpolation, self.INTERPOLATIONS),
                                ("masque", masque, self.MASQUES)):
            if val not in choix:
                raise ValueError(f"{nom} inconnu(e) : {val} (choix : {', '.join(choix)})")
        fonctions = self.INTERPOLATIONS[interpolation]
        if fonction_rbf is None:
            fonction_rbf = fonctions[0] if fonctions else ""
        elif fonctions and fonction_rbf not in fonctions:
            raise ValueError(f"Fonction {fonction_rbf} impossible avec {interpolation} "
                             f"(choix : {', '.join(fonctions)})")
        inconnues = [g for g in grandeurs if g not in self.GRANDEURS]
        inconnues += [c for c in composantes if c not in self.COMPOSANTES]
        if inconnues:
            raise ValueError(f"Grandeurs / composantes inconnues : {inconnues}")
        self.date = date or time.strftime("%Y_%m_%d")
        self.dossier_essai = dossier_essai or Detect3D.chemin_par_defaut(self.date)
        if source is None:
            dispo = self.sources_disponibles()
            source = dispo[0] if dispo else self.SOURCE_DEFAUT
        self.source = source
        self.taille_grille = int(taille_grille)
        self.interpolation = interpolation
        self.fonction_rbf = fonction_rbf
        self.lissage = lissage
        self.voisins = int(voisins)
        self.masque = masque
        self.rayon_masque = rayon_masque
        self.inverser_z = inverser_z
        self.images = tuple(images)
        self.grandeurs = tuple(grandeurs)
        self.composantes = tuple(composantes)
        self.nuage_3d = nuage_3d
        self.nuage_deplacement = nuage_deplacement
        self.enregistrer_champs = enregistrer_champs
        self.enregistrer_figures = enregistrer_figures
        self.afficher_figures = afficher_figures

    RESULTATS = ("X", "Y", "Z", "grille", "champs", "z_inverse")

    def parametres(self):
        """Paramètres sous forme de dictionnaire (pour affichage)."""
        return {k: v for k, v in vars(self).items() if k not in self.RESULTATS}

    # ----- chemins -----

    @property
    def dossier_reconstruction(self):
        return Path(self.dossier_essai) / self.SOUS_DOSSIER_ENTREE

    @property
    def dossier_entree(self):
        """<essai>/reconstruction/<source> : X3d.txt, Y3d.txt, Z3d.txt."""
        return self.dossier_reconstruction / self.source

    @property
    def dossier_sortie(self):
        """<essai>/deformation/<source>."""
        return Path(self.dossier_essai) / self.SOUS_DOSSIER_SORTIE / self.source

    def _complet(self, dossier):
        return all((dossier / f).is_file() for f in self.FICHIERS)

    def sources_disponibles(self):
        """Sous-dossiers de reconstruction/ contenant X3d, Y3d et Z3d."""
        d = self.dossier_reconstruction
        if not d.is_dir():
            return []
        return sorted(c.name for c in d.iterdir() if c.is_dir() and self._complet(c))

    def infos(self):
        """(nombre d'images, nombre de points) de X3d.txt, sans tout charger ; None si absent."""
        if not self._complet(self.dossier_entree):
            return None
        with open(self.dossier_entree / "X3d.txt") as f:
            premiere = f.readline()
            nb = 1 + sum(1 for ligne in f if ligne.strip())
        return nb, len(premiere.split())

    # ----- point d'entrée -----

    def lancer(self):
        """Calcule les champs des images demandées, les enregistre et les trace.

        Renvoie un dictionnaire {numéro d'image : champs} (aussi dans self.champs).
        """
        if not self._complet(self.dossier_entree):
            raise FileNotFoundError(f"X3d.txt, Y3d.txt, Z3d.txt introuvables dans {self.dossier_entree} : "
                                    "lancer d'abord la reconstruction 3D.")
        self.charger()
        nb = len(self.X)
        numeros = list(dict.fromkeys(range(nb)[n] for n in self.images))   # sans doublon, dans l'ordre
        print(f"{nb} images dans {self.dossier_entree} ; traitées : {numeros}"
              + ("  (Z inversé)" if self.z_inverse else ""))
        self.grille = self.construire_grille()
        if self.enregistrer_champs or self.enregistrer_figures:
            self.dossier_sortie.mkdir(parents=True, exist_ok=True)

        self.champs = {}
        for k, num in enumerate(numeros):
            print(f"Déformations : image {num} ({k + 1} / {len(numeros)})", end="\r")
            champs = self.calculer(num)
            self.champs[num] = champs
            if self.enregistrer_champs:
                np.savez_compressed(self.dossier_sortie / f"champs_{num}.npz",
                                    Xgrille=self.grille["X"], Ygrille=self.grille["Y"], **champs)
        print()
        if self.enregistrer_champs:
            print(f"Champs enregistrés dans {self.dossier_sortie} (champs_<n>.npz)")

        if self.enregistrer_figures or self.afficher_figures:
            for num in numeros:
                if self.nuage_3d:
                    self.tracer_nuage(num)
                for g in self.grandeurs:
                    self.tracer(num, g)
        return self.champs

    def charger(self):
        """Lit X3d, Y3d, Z3d ; change le signe de Z si demandé (ou si auto et que le dôme descend).

        Changer le signe de Z (symétrie z -> -z) ne modifie ni J, ni I1, ni I2, ni E, C, H, ni les
        composantes xx, yy, zz, xy de F et LE : seuls Uz et les composantes xz, yz de F et LE
        changent de signe. Le choix sert à garder les mêmes conventions que les figures de la
        reconstruction (dôme vers le haut, Uz > 0).
        """
        self.X, self.Y, self.Z = (np.loadtxt(self.dossier_entree / f, ndmin=2) for f in self.FICHIERS)
        inverse = self.inverser_z
        if inverse is None:
            dz = self.Z - self.Z[0]
            inverse = bool(np.nanmax(-dz) > np.nanmax(dz))
        if inverse:
            self.Z = -self.Z
        self.z_inverse = inverse
        return self.X, self.Y, self.Z

    # ----- grille -----

    def construire_grille(self):
        """Grille régulière sur la zone initiale ; la ligne 0 est en haut (Y max), comme une image."""
        x0, y0 = self.X[0], self.Y[0]
        ok = np.isfinite(x0) & np.isfinite(y0) & np.isfinite(self.Z[0])
        x0, y0 = x0[ok], y0[ok]
        xmin, xmax, ymin, ymax = x0.min(), x0.max(), y0.min(), y0.max()
        n = self.taille_grille
        Xg, Yg = np.meshgrid(np.linspace(xmin, xmax, n), np.linspace(ymax, ymin, n), indexing="xy")

        if self.masque == "disque":           # comme getdef.py : disque centré sur la grille
            xc, yc = Xg[n // 2, n // 2], Yg[n // 2, n // 2]
            rayon = self.rayon_masque * (xmax - xmin) / 2
            dedans = (Xg - xc) ** 2 + (Yg - yc) ** 2 <= rayon ** 2
        elif self.masque == "enveloppe":      # enveloppe convexe des taches initiales
            from scipy.spatial import Delaunay
            dedans = Delaunay(np.column_stack((x0, y0))).find_simplex(np.column_stack((Xg.ravel(), Yg.ravel())))
            dedans = (dedans >= 0).reshape(Xg.shape)
        else:
            dedans = np.ones_like(Xg, dtype=bool)
        return {"X": Xg, "Y": Yg, "dedans": dedans,
                "dx": Xg[0, 1] - Xg[0, 0], "dy": Yg[1, 0] - Yg[0, 0],   # dy < 0 (Y décroît vers le bas)
                "etendue": (xmin, xmax, ymin, ymax)}

    def interpoler(self, num):
        """Positions x, y, z de l'image num, fonctions de la position initiale, sur la grille."""
        g = self.grille
        x0, y0 = self.X[0], self.Y[0]
        val = (self.X[num], self.Y[num], self.Z[num])
        ok = np.isfinite(x0) & np.isfinite(y0) & np.isfinite(self.Z[0])
        for v in val:
            ok &= np.isfinite(v)          # taches perdues sur l'image num : écartées
        sortie = []
        for v in val:
            if self.interpolation == "rbf":
                f = Rbf(x0[ok], y0[ok], v[ok], function=self.fonction_rbf, smooth=self.lissage)
                sortie.append(f(g["X"], g["Y"]))
            elif self.interpolation == "rbf_polynome":
                f = RBFInterpolator(np.column_stack((x0[ok], y0[ok])), v[ok], kernel=self.fonction_rbf,
                                    degree=1, smoothing=self.lissage, neighbors=self.voisins or None)
                sortie.append(f(np.column_stack((g["X"].ravel(), g["Y"].ravel()))).reshape(g["X"].shape))
            else:
                sortie.append(griddata((x0[ok], y0[ok]), v[ok], (g["X"], g["Y"]), method="linear"))
        return np.stack(sortie, axis=-1)          # (n, n, 3)

    # ----- calcul -----

    @staticmethod
    def _log_sym(A):
        """Logarithme d'une matrice symétrique définie positive (sur les deux derniers axes)."""
        w, V = np.linalg.eigh(A)
        w = np.log(np.clip(w, 1e-12, None))
        return np.einsum("...ik,...k,...jk->...ij", V, w, V)

    def calculer(self, num):
        """Tous les champs de l'image num, sur la grille (NaN hors du masque)."""
        g = self.grille
        r = self.interpoler(num)              # positions actuelles r(X, Y)
        r0 = r if num == 0 else self.interpoler(0)

        # F1 : dérivées de r par rapport à X (colonnes) et Y (lignes)
        drdX = np.gradient(r, g["dx"], axis=1)
        drdY = np.gradient(r, g["dy"], axis=0)
        F1 = np.stack((drdX, drdY), axis=-1)             # (n, n, 3, 2)

        # normale et rapport de surfaces : |drdX ^ drdY| = sqrt(det(F1ᵀF1)) = det U1
        normale = np.cross(drdX, drdY)
        J = np.linalg.norm(normale, axis=-1)
        with np.errstate(invalid="ignore", divide="ignore"):
            F2 = normale / J[..., None] ** 2              # n / J, avec n unitaire
        F = np.concatenate((F1, F2[..., None]), axis=-1)  # (n, n, 3, 3)

        invalide = ~g["dedans"] | ~np.isfinite(F).all(axis=(-2, -1)) | ~(J > 0)
        I = np.eye(3)
        F[invalide] = I                       # valeur neutre pour les calculs, remise à NaN ensuite

        Ft = np.swapaxes(F, -1, -2)
        C = Ft @ F
        champs = {
            "U": r - r0,
            "F": F,
            "C": C,
            "E": 0.5 * (C - I),
            "H": 0.5 * self._log_sym(C),
            "LE": 0.5 * self._log_sym(F @ Ft),
            "J": J,
            "I1": np.trace(C, axis1=-2, axis2=-1),
            "I2": 0.5 * (np.trace(C, axis1=-2, axis2=-1) ** 2
                         - np.trace(C @ C, axis1=-2, axis2=-1)),
        }
        for v in champs.values():
            v[invalide] = np.nan
        champs["masque"] = ~invalide
        return champs

    # ----- figures -----

    def _finir_figure(self, fig, nom):
        if self.enregistrer_figures:
            fig.savefig(self.dossier_sortie / nom)
        if self.afficher_figures:
            plt.show()
        plt.close(fig)

    def tracer(self, num, grandeur):
        """Cartographie(s) d'une grandeur pour l'image num : une vignette par composante."""
        nb = len(self.X)
        champ = self.champs[num][grandeur]
        titre, nature = self.GRANDEURS[grandeur]
        if nature == "tenseur":
            vignettes = [(f"{grandeur} {c}", champ[..., i, j])
                         for c, (i, j) in self.COMPOSANTES.items() if c in self.composantes]
        elif nature == "vecteur":
            vignettes = [(f"{grandeur}{c}", champ[..., k]) for k, c in enumerate("xyz")]
        else:
            vignettes = [(grandeur, champ)]
        if not vignettes:
            return

        fig, axes = plt.subplots(1, len(vignettes), figsize=(5.5 * len(vignettes) + 1, 5.5),
                                 squeeze=False, layout="constrained")
        for ax, (nom, carte) in zip(axes[0], vignettes):
            im = ax.imshow(carte, extent=self.grille["etendue"], origin="upper", cmap="viridis")
            ax.set_title(nom)
            ax.set_xlabel("X (mm)"); ax.set_ylabel("Y (mm)")
            ax.set_aspect("equal")
            fig.colorbar(im, ax=ax, shrink=0.8)
        fig.suptitle(f"{titre} - {self.source} - image {num} / {nb - 1}")
        self._finir_figure(fig, f"{grandeur}_{num}-{nb}.png")

    def tracer_nuage(self, num):
        """Nuage 3D des taches de l'image num, couleur = z (ou déplacement z)."""
        nb = len(self.X)
        x, y, z = self.X[num], self.Y[num], self.Z[num]
        if self.nuage_deplacement:
            z = z - self.Z[0]
        ok = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
        fig = plt.figure(figsize=(16, 9))
        ax = plt.axes(projection="3d")
        ax.grid(visible=True, color="grey", linestyle="-.", linewidth=0.3, alpha=0.2)
        sctt = ax.scatter3D(x[ok], y[ok], z[ok], alpha=0.8, c=z[ok], cmap="viridis")
        ax.set_xlabel("x (mm)", fontweight="bold")
        ax.set_ylabel("y (mm)", fontweight="bold")
        ax.set_zlabel("z (mm)", fontweight="bold")
        quoi = "déplacement z" if self.nuage_deplacement else "z"
        plt.title(f"{self.source} - image {num} / {nb - 1} - {quoi} (mm)"
                  + (" - Z inversé" if self.z_inverse else ""))
        fig.colorbar(sctt, ax=ax, shrink=0.5, aspect=5)
        self._finir_figure(fig, f"Nuage3D_{num}-{nb}.png")