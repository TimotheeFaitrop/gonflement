"""Anisotropie du gonflement : ellipses ajustées sur les lignes de niveau du déplacement z.

Remplace getaniso.py. Pour chaque image traitée :
  1. les positions des taches sont interpolées sur une grille (même calcul que Deformation) ;
  2. pour chaque niveau p (fraction du déplacement z maximal, de niveau_min à niveau_max par pas
     de pas_niveau), on garde les points de la grille où |Uz − p·max(Uz)| ≤ tolerance ;
  3. on ajuste une ellipse sur leurs positions actuelles (x, y) : demi-axes a ≥ b, centre, angle ;
  4. anisotropie = b / a (1 = isotrope), puis droite b/a = pente·p + ordonnée sur l'ensemble des niveaux.

Organisation des dossiers (dossier_essai = <date>/essai1) :
    <essai>/reconstruction/<source>/   X3d.txt, Y3d.txt, Z3d.txt (entrée)
    <essai>/anisotropie/<source>/      ellipses_<n>.txt et figures (sortie)
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Ellipse

from Pycaso.deformation_class import Deformation


def ajuster_ellipse(x, y):
    """Ellipse aux moindres carrés (Halir & Flusser, 1998) : (xc, yc, a, b, angle en degrés) ou None.

    a ≥ b sont les demi-axes ; angle = direction du grand axe par rapport à X, dans ]-90, 90].
    Les points sont centrés et réduits avant l'ajustement (meilleur conditionnement).
    """
    if len(x) < 6:
        return None
    xm, ym = x.mean(), y.mean()
    s = max(x.std(), y.std())
    if not s > 0:
        return None
    u, v = (x - xm) / s, (y - ym) / s
    D1 = np.column_stack((u * u, u * v, v * v))
    D2 = np.column_stack((u, v, np.ones_like(u)))
    S1, S2, S3 = D1.T @ D1, D1.T @ D2, D2.T @ D2
    try:
        T = -np.linalg.solve(S3, S2.T)
        M = S1 + S2 @ T
        M = np.array([M[2] / 2, -M[1], M[0] / 2])
        w, V = np.linalg.eig(M)
    except np.linalg.LinAlgError:
        return None
    V = V.real
    cond = 4 * V[0] * V[2] - V[1] ** 2
    k = np.nonzero(cond > 0)[0]
    if len(k) == 0:
        return None
    a1 = V[:, k[0]]
    A, B, C = a1
    Dc, Ec, Fc = T @ a1

    # forme géométrique : (p − c)ᵀ Q (p − c) = −F(c)
    Q = np.array([[A, B / 2], [B / 2, C]])
    try:
        c = np.linalg.solve(2 * Q, -np.array([Dc, Ec]))
    except np.linalg.LinAlgError:
        return None
    Fcentre = Fc + 0.5 * (Dc * c[0] + Ec * c[1])
    lam, vec = np.linalg.eigh(Q)
    demi = np.sqrt(-Fcentre / lam)                 # demi-axes associés aux vecteurs propres
    if not np.all(np.isfinite(demi)):
        return None
    i = int(np.argmax(demi))
    angle = np.degrees(np.arctan2(vec[1, i], vec[0, i]))
    angle = (angle + 90) % 180 - 90                # dans [-90, 90[
    if angle == -90:
        angle = 90.0
    return xm + s * c[0], ym + s * c[1], s * demi[i], s * demi[1 - i], angle


class Anisotropie:
    """Rapport b/a des ellipses de niveau du déplacement z, pour les images choisies."""

    SOUS_DOSSIER_SORTIE = "anisotropie"
    SENS_Z = {"auto": None, "inverser": True, "garder": False}   # libellé : valeur de inverser_z
    COLONNES = ("niveau", "z_niveau_mm", "a_mm", "b_mm", "b_sur_a", "angle_deg",
                "xc_mm", "yc_mm", "nb_points")

    def __init__(self,
                 # --- Essai à traiter ---
                 date=None,                 # AAAA_MM_JJ ; None = aujourd'hui
                 dossier_essai=None,        # ex. <date>/essai1 ; None = <date>/essai1
                 source=None,               # sous-dossier de reconstruction/ ; None = le premier trouvé
                 images=(-1,),              # images traitées (getaniso.py : ip, image à 245 mbar)
                 # --- Grille et interpolation (voir Deformation) ---
                 taille_grille=200,
                 interpolation="rbf",
                 fonction_rbf=None,
                 lissage=0.0,
                 voisins=0,
                 masque="disque",
                 rayon_masque=1.0,
                 seuil_aberrants=2.0,       # filtre des taches aberrantes (mm), 0 = aucun (voir Deformation)
                 exclusions_manuelles=True, # retirer les taches exclues à la main (selection_gui)
                 # --- Niveaux ---
                 niveau_min=0.40,           # fraction du déplacement z max
                 niveau_max=0.80,
                 pas_niveau=0.01,
                 tolerance=0.05,            # demi-épaisseur (mm) de la bande gardée autour du niveau
                 inverser_z=None,           # None = auto (dôme vers le haut), True / False = forcé
                 reference_deplacement=0,   # Uz = z − z(image de référence) ; source corrigée : 0 = état plat,
                                            # 1 = état serré
                 # --- Résultats ---
                 tracer_ellipses=True,      # vue de dessus : points des niveaux et ellipses
                 tracer_surface=False,      # surface 3D avec les ellipses
                 enregistrer_resultats=True,
                 enregistrer_figures=True,
                 afficher_figures=True):
        if not 0 < niveau_min <= niveau_max <= 1:
            raise ValueError("Il faut 0 < niveau_min ≤ niveau_max ≤ 1")
        if not pas_niveau > 0 or not tolerance > 0:
            raise ValueError("pas_niveau et tolerance doivent être > 0")
        # Deformation porte les chemins, la grille et l'interpolation (et vérifie les options)
        self.deformation = Deformation(date=date, dossier_essai=dossier_essai, source=source,
                                       taille_grille=taille_grille, interpolation=interpolation,
                                       fonction_rbf=fonction_rbf, lissage=lissage, voisins=voisins,
                                       masque=masque, rayon_masque=rayon_masque,
                                       seuil_aberrants=seuil_aberrants,
                                       exclusions_manuelles=exclusions_manuelles,
                                       inverser_z=False)      # le sens de z est géré ici (analyser)
        d = self.deformation
        self.date, self.dossier_essai, self.source = d.date, d.dossier_essai, d.source
        self.images = tuple(images)
        self.taille_grille, self.interpolation, self.fonction_rbf = d.taille_grille, d.interpolation, d.fonction_rbf
        self.lissage, self.voisins, self.masque, self.rayon_masque = d.lissage, d.voisins, d.masque, d.rayon_masque
        self.seuil_aberrants = d.seuil_aberrants
        self.exclusions_manuelles = d.exclusions_manuelles
        self.niveau_min, self.niveau_max, self.pas_niveau = niveau_min, niveau_max, pas_niveau
        self.tolerance = tolerance
        self.inverser_z = inverser_z
        self.reference_deplacement = int(reference_deplacement)
        self.tracer_ellipses = tracer_ellipses
        self.tracer_surface = tracer_surface
        self.enregistrer_resultats = enregistrer_resultats
        self.enregistrer_figures = enregistrer_figures
        self.afficher_figures = afficher_figures

    RESULTATS = ("deformation", "resultats")

    def parametres(self):
        """Paramètres sous forme de dictionnaire (pour affichage)."""
        return {k: v for k, v in vars(self).items() if k not in self.RESULTATS}

    # ----- chemins (délégués à Deformation) -----

    @property
    def dossier_entree(self):
        return self.deformation.dossier_entree

    @property
    def dossier_sortie(self):
        """<essai>/anisotropie/<source>."""
        return Path(self.dossier_essai) / self.SOUS_DOSSIER_SORTIE / self.source

    def sources_disponibles(self):
        return self.deformation.sources_disponibles()

    def infos(self):
        return self.deformation.infos()

    @property
    def niveaux(self):
        n = int(round((self.niveau_max - self.niveau_min) / self.pas_niveau)) + 1
        return np.round(self.niveau_min + self.pas_niveau * np.arange(n), 10)

    # ----- point d'entrée -----

    def lancer(self):
        """Ellipses de toutes les images demandées ; enregistre les tableaux et les figures.

        Renvoie {numéro d'image : résultat} (aussi dans self.resultats). Chaque résultat contient
        "tableau" (une ligne par niveau réussi, colonnes COLONNES), "pente", "ordonnee", "inverse".
        """
        d = self.deformation
        if not d._complet(d.dossier_entree):
            raise FileNotFoundError(f"X3d.txt, Y3d.txt, Z3d.txt introuvables dans {d.dossier_entree} : "
                                    "lancer d'abord la reconstruction 3D.")
        d.charger()
        d.grille = d.construire_grille()
        nb = len(d.X)
        numeros = list(dict.fromkeys(range(nb)[n] for n in self.images))
        print(f"{nb} images dans {d.dossier_entree} ; traitées : {numeros}")
        if self.enregistrer_resultats or self.enregistrer_figures:
            self.dossier_sortie.mkdir(parents=True, exist_ok=True)

        ref = range(nb)[self.reference_deplacement]
        r0 = d.interpoler(ref)
        if ref:
            print(f"Uz compté depuis l'image {ref}")
        self.resultats = {}
        for num in numeros:
            res = self.analyser(num, r0)
            self.resultats[num] = res
            t = res["tableau"]
            pente = "—" if res["pente"] is None else f"{res['pente']:.4f}"
            print(f"Image {num} : {len(t)} / {len(self.niveaux)} niveaux ajustés, "
                  f"b/a moyen = {np.mean(t[:, 4]) if len(t) else float('nan'):.3f}, pente = {pente}"
                  + ("  (z inversé)" if res["inverse"] else ""))
            self.diagnostic(res)
            if self.enregistrer_resultats:
                np.savetxt(self.dossier_sortie / f"ellipses_{num}.txt", t, fmt="%.6g",
                           header=" ".join(self.COLONNES))
        if self.enregistrer_resultats:
            print(f"Résultats enregistrés dans {self.dossier_sortie} (ellipses_<n>.txt)")

        if self.enregistrer_figures or self.afficher_figures:
            self.tracer_pente(numeros)
            for num in numeros:
                if self.tracer_ellipses:
                    self.tracer_vue_dessus(num)
                if self.tracer_surface:
                    self.tracer_surface_3d(num)
        return self.resultats

    # ----- calcul -----

    def analyser(self, num, r0=None):
        """Ellipses de tous les niveaux pour l'image num."""
        d = self.deformation
        r = d.interpoler(num)
        if r0 is None:
            r0 = d.interpoler(range(len(d.X))[self.reference_deplacement])
        dedans = d.grille["dedans"] & np.isfinite(r).all(axis=-1) & np.isfinite(r0).all(axis=-1)
        uz = r[..., 2] - r0[..., 2]
        inverse = self.inverser_z
        if inverse is None:                 # auto : le dôme doit monter
            inverse = bool(np.nanmax(-uz[dedans]) > np.nanmax(uz[dedans]))
        if inverse:
            uz = -uz
        uz = np.where(dedans, uz, np.nan)
        zmax = np.nanmax(uz)

        lignes, points = [], {}
        for p in self.niveaux:
            zn = p * zmax
            w = np.abs(uz - zn) <= self.tolerance
            x, y = r[..., 0][w], r[..., 1][w]
            e = ajuster_ellipse(x, y)
            if e is None:
                continue
            xc, yc, a, b, angle = e
            lignes.append((p, zn, a, b, b / a, angle, xc, yc, len(x)))
            points[p] = (x, y)
        tableau = np.array(lignes, dtype=float).reshape(-1, len(self.COLONNES))
        pente = ordonnee = None
        if len(tableau) >= 2:
            pente, ordonnee = np.polyfit(tableau[:, 0], tableau[:, 4], 1)
        return {"tableau": tableau, "pente": pente, "ordonnee": ordonnee, "inverse": inverse,
                "zmax": zmax, "uz": uz, "r": r, "points": points}

    def diagnostic(self, res):
        """Explique dans le terminal pourquoi des niveaux n'ont pas pu être ajustés."""
        uz, zmax = res["uz"], res["zmax"]
        if not np.isfinite(zmax):
            print("  ⚠ aucun point valide sur la grille (masque, NaN ?)")
            return
        p99 = np.nanpercentile(uz, 99)
        nb_niv = len(self.niveaux)
        if len(res["tableau"]) == nb_niv:
            return
        bandes = [int((np.abs(uz - p * zmax) <= self.tolerance).sum()) for p in self.niveaux]
        print(f"  Uz max = {zmax:.3g} mm, 99e centile = {p99:.3g} mm, Uz min = {np.nanmin(uz):.3g} mm ; "
              f"points par bande : min {min(bandes)}, médiane {int(np.median(bandes))}, max {max(bandes)}")
        if zmax > 1.5 * p99 > 0:
            print("  ⚠ Uz max est très au-dessus du 99e centile : pic isolé (tache aberrante ?). "
                  "Baisser seuil_aberrants ou changer d'interpolation.")
        elif zmax <= 0:
            print("  ⚠ Uz max ≤ 0 : le dôme est vers le bas, essayer « Sens de z » = inverser.")
        elif max(bandes) < 6:
            print(f"  ⚠ bandes presque vides : tolérance ({self.tolerance:g} mm) trop petite pour "
                  f"Uz max = {zmax:.3g} mm (Z encore 10× trop petit ?).")

    # ----- figures -----

    def _finir_figure(self, fig, nom):
        if self.enregistrer_figures:
            fig.savefig(self.dossier_sortie / nom)
        if self.afficher_figures:
            plt.show()
        plt.close(fig)

    def tracer_pente(self, numeros):
        """b/a et angle du grand axe en fonction du niveau, avec la droite ajustée."""
        nb = len(self.deformation.X)
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5), layout="constrained")
        for k, num in enumerate(numeros):
            res = self.resultats[num]
            t = res["tableau"]
            if not len(t):
                continue
            coul = f"C{k % 10}"
            lib = f"image {num}"
            if res["pente"] is not None:
                lib += f" : pente = {res['pente']:.3f}"
                xx = np.array([self.niveau_min, self.niveau_max])
                ax1.plot(xx, res["pente"] * xx + res["ordonnee"], c=coul)
            ax1.scatter(t[:, 0], t[:, 4], c=coul, label=lib)
            ax2.scatter(t[:, 0], t[:, 5], c=coul, label=f"image {num}")
        ax1.set_xlabel("niveau (fraction de Uz max)"); ax1.set_ylabel("b / a")
        ax1.set_title("Anisotropie des ellipses de niveau")
        if ax1.get_legend_handles_labels()[0]:
            ax1.legend()
        else:
            ax1.text(0.5, 0.5, "aucune ellipse ajustée\n(voir le terminal)", ha="center", va="center",
                     transform=ax1.transAxes)
        ax2.set_xlabel("niveau (fraction de Uz max)"); ax2.set_ylabel("angle du grand axe (°)")
        ax2.set_title("Orientation du grand axe / X"); ax2.set_ylim(-90, 90)
        fig.suptitle(f"{self.source} - {self.dossier_essai}")
        nom = "-".join(map(str, numeros)) if len(numeros) <= 5 else f"{numeros[0]}..{numeros[-1]}"
        self._finir_figure(fig, f"Aniso_pente_{nom}-{nb}.png")

    def _ellipses(self, num):
        """(niveau, z, Ellipse paramètres) de l'image num."""
        for p, zn, a, b, _, angle, xc, yc, _ in self.resultats[num]["tableau"]:
            yield p, zn, a, b, angle, xc, yc

    def tracer_vue_dessus(self, num):
        """Points de chaque bande de niveau (positions actuelles) et ellipses ajustées."""
        nb = len(self.deformation.X)
        res = self.resultats[num]
        fig, ax = plt.subplots(figsize=(9, 8), layout="constrained")
        cmap = plt.get_cmap("viridis")
        norme = plt.Normalize(self.niveau_min, self.niveau_max)
        for p, (x, y) in res["points"].items():
            ax.scatter(x, y, s=3, color=cmap(norme(p)), alpha=0.5)
        for p, zn, a, b, angle, xc, yc in self._ellipses(num):
            ax.add_patch(Ellipse((xc, yc), 2 * a, 2 * b, angle=angle, fill=False,
                                 edgecolor=cmap(norme(p)), linewidth=1.2))
        ax.set_aspect("equal")
        ax.set_xlabel("x (mm)"); ax.set_ylabel("y (mm)")
        fig.colorbar(plt.cm.ScalarMappable(norm=norme, cmap=cmap), ax=ax, label="niveau (fraction de Uz max)")
        moy = np.mean(res["tableau"][:, 4]) if len(res["tableau"]) else float("nan")
        ax.set_title(f"{self.source} - image {num} / {nb - 1} - ellipses de niveau (b/a moyen {moy:.3f})")
        self._finir_figure(fig, f"Ellipses_{num}-{nb}.png")

    def tracer_surface_3d(self, num):
        """Surface déformée (z = déplacement) avec les ellipses à leur hauteur."""
        nb = len(self.deformation.X)
        res = self.resultats[num]
        r, uz = res["r"], res["uz"]
        fig = plt.figure(figsize=(16, 9))
        ax = plt.axes(projection="3d")
        surf = ax.plot_surface(r[..., 0], r[..., 1], uz, cmap="viridis", alpha=0.6, linewidth=0)
        t = np.linspace(0, 2 * np.pi, 120)
        for p, zn, a, b, angle, xc, yc in self._ellipses(num):
            th = np.radians(angle)
            ex = xc + a * np.cos(t) * np.cos(th) - b * np.sin(t) * np.sin(th)
            ey = yc + a * np.cos(t) * np.sin(th) + b * np.sin(t) * np.cos(th)
            ax.plot(ex, ey, np.full_like(t, zn), color="k", linewidth=0.8)
        ax.set_xlabel("x (mm)", fontweight="bold")
        ax.set_ylabel("y (mm)", fontweight="bold")
        ax.set_zlabel("Uz (mm)", fontweight="bold")
        try:
            ax.set_aspect("equal")
        except NotImplementedError:
            pass
        fig.colorbar(surf, ax=ax, shrink=0.5, aspect=5, label="Uz (mm)")
        plt.title(f"{self.source} - image {num} / {nb - 1} - surface et ellipses de niveau")
        self._finir_figure(fig, f"Surface_{num}-{nb}.png")