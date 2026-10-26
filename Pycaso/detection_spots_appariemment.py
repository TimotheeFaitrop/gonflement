"""Appariement des taches entre les caméras gauche et droite.

Deux méthodes :
  - apparier_sans_etalonnage (par défaut) : recalage 2D des deux nuages de taches,
    comme l'ancien CoordCa10 : translation dominante par vote, puis alternance
    appariement hongrois / ajustement affine avec des seuils de plus en plus serrés.
    Aucun étalonnage nécessaire.
  - apparier (option) : choix des paires avec l'étalonnage Lagrange (le point 3D
    de la bonne paire tombe sur le plan de l'échantillon).
"""
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import uniform_filter
from scipy.optimize import linear_sum_assignment
from scipy.spatial import cKDTree
from scipy.spatial.distance import cdist


def _pycaso():
    """Import de pycaso seulement quand l'étalonnage est utilisé.

    pycaso.py fait "import solve_library" (sans "Pycaso.") : le dossier Pycaso,
    celui qui contient ce fichier, doit donc être dans sys.path avant de l'importer.
    """
    dossier = str(Path(__file__).resolve().parent)
    if dossier not in sys.path:
        sys.path.insert(0, dossier)
    from Pycaso import pycaso as pcs
    return pcs


class AppariementStereo:
    """Apparie les taches gauche/droite de la première image.

    Sans L_constants (None) : recalage 2D, pas besoin d'étalonnage.
    Avec L_constants : sélection des paires par l'étalonnage Lagrange.
    Les valeurs par défaut sont dans DetectionSpots.__init__, qui crée cet objet.
    """

    # Modèles de recalage 2D et nombre minimal de paires pour les ajuster
    MODELES = {"affine": 3, "homographie": 4, "polynome2": 6, "polynome3": 10}

    def __init__(self, L_constants=None, l_pform=4, rayon=150.0, tol_z=1.0,
                 seuils=(80.0, 30.0, 10.0), modele="polynome2"):
        if modele not in self.MODELES:
            raise ValueError(f"Modèle de recalage inconnu : {modele} (choix : {', '.join(self.MODELES)})")
        self.L_constants = L_constants
        self.l_pform = l_pform
        self.rayon = rayon          # (étalonnage) rayon (px) de recherche des candidates
        self.tol_z = tol_z          # (étalonnage) écart max (mm) au plan de l'échantillon
        self.seuils = tuple(float(s) for s in seuils)   # (recalage 2D) distances max (px), de plus en plus serrées
        self.modele = modele        # (recalage 2D) transformation droite -> gauche

    @property
    def avec_etalonnage(self):
        return self.L_constants is not None

    # ----- méthode 1 : sans étalonnage (par défaut) -----

    def apparier_sans_etalonnage(self, L, R_tourne):
        """Apparie par recalage 2D des deux nuages de taches (méthode de CoordCa10).

        L        : (N,2) taches gauche (colonne, ligne)
        R_tourne : (M,2) taches droite tournées de 180° (déjà à peu près dans le repère de gauche)
        Renvoie  : indices gauche, indices droite, résidus (px), R recalée sur L
        """
        L, R = (np.asarray(a, dtype=float) for a in (L, R_tourne))
        if len(L) == 0 or len(R) == 0:
            raise ValueError("Pas de taches sur l'une des deux caméras à l'image 0")

        # (1) translation grossière, sans connaître les paires
        R_cur = R + self.translation_par_vote(L, R)

        # (2) appariement hongrois puis ré-ajustement, seuils de plus en plus serrés.
        #     Le premier ajustement est affine (robuste avec des paires encore approximatives),
        #     les suivants utilisent le modèle choisi (perspective, distorsion des objectifs).
        for k, seuil in enumerate(self.seuils):
            ri, ci, _ = self.hongrois(L, R_cur, seuil)
            modele = "affine" if k == 0 else self.modele
            if len(ri) < self.MODELES[modele]:
                if len(ri) < self.MODELES["affine"]:
                    break                               # trop peu de paires pour ajuster
                modele = "affine"
            R_cur = self.ajuster_transformation(R[ci], L[ri], modele)(R)   # ajusté sur R d'origine

        # (3) consolidation au seuil le plus serré : on ré-ajuste tant que des paires
        #     s'ajoutent ou changent (les taches du centre et du bord sont récupérées)
        precedentes = None
        for _ in range(20):
            ri, ci, _ = self.hongrois(L, R_cur, self.seuils[-1])
            paires = set(zip(ri.tolist(), ci.tolist()))
            if paires == precedentes or len(ri) < self.MODELES[self.modele]:
                break
            precedentes = paires
            R_cur = self.ajuster_transformation(R[ci], L[ri], self.modele)(R)

        ri, ci, residus = self.hongrois(L, R_cur, self.seuils[-1])
        return ri, ci, residus, R_cur

    # ----- méthode 2 : avec l'étalonnage Lagrange (option) -----

    def apparier(self, L, R_brut, R_tourne):
        """Apparie les taches gauche et droite de la première image avec l'étalonnage.

        Pour chaque tache de gauche, on prend les taches de droite voisines comme
        candidates, on calcule le point 3D de chaque paire avec l'étalonnage Lagrange,
        et on garde celle qui tombe sur le plan de l'échantillon (plat à l'image 0).

        L        : (N,2) taches gauche (colonne, ligne)
        R_brut   : (M,2) taches droite dans l'image brute (colonne, ligne), format de l'étalonnage
        R_tourne : (M,2) taches droite tournées de 180° (pour chercher les voisines)
        Renvoie  : indices gauche, indices droite, écart au plan (mm), R recalée sur L (pour la figure)
        """
        if not self.avec_etalonnage:
            raise ValueError("Pas d'étalonnage : utiliser apparier_sans_etalonnage")
        pcs = _pycaso()
        tol_z = self.tol_z
        L, R_brut, R_tourne = (np.asarray(a, dtype=float) for a in (L, R_brut, R_tourne))
        t0 = self.translation_par_vote(L, R_tourne)
        voisines = cKDTree(R_tourne + t0).query_ball_point(L, self.rayon)
        I = np.array([i for i, v in enumerate(voisines) for _ in v], dtype=int)
        J = np.array([j for v in voisines for j in v], dtype=int)
        x, y, z = pcs.Lagrange_identification(L[I], R_brut[J], self.L_constants, self.l_pform)

        # Plan de l'échantillon : départ au Z le plus fréquent, puis ajustements de plus en plus serrés
        hist, bords = np.histogram(z[np.isfinite(z)], bins=400)
        coef = np.array([0.0, 0.0, (bords[hist.argmax()] + bords[hist.argmax() + 1]) / 2])
        for tol in (5.0, 3.0, 2.0, tol_z):
            ok = np.abs(z - (coef[0] * x + coef[1] * y + coef[2])) < tol
            coef, *_ = np.linalg.lstsq(np.column_stack([x[ok], y[ok], np.ones(ok.sum())]), z[ok], rcond=None)
        ecart = np.abs(z - (coef[0] * x + coef[1] * y + coef[2]))
        print(f"Plan de l'échantillon : z = {coef[0]:.3f} x + {coef[1]:.3f} y + {coef[2]:.2f} mm")

        # Appariement un pour un, en minimisant l'écart au plan
        C = np.full((len(L), len(R_brut)), 1e6)
        garde = ecart < tol_z
        C[I[garde], J[garde]] = ecart[garde]
        ri, ci = linear_sum_assignment(C)
        ok = C[ri, ci] < tol_z
        ri, ci = ri[ok], ci[ok]

        # Cohérence de voisinage : on écarte les paires très loin du recalage d'ensemble
        A, t = self.ajuster_affine(R_tourne[ci], L[ri])
        R_recale = R_tourne @ A.T + t
        ok = np.hypot(*(R_recale[ci] - L[ri]).T) < 40
        return ri[ok], ci[ok], C[ri[ok], ci[ok]], R_recale

    # ----- outils (ne dépendent pas des paramètres) -----

    @staticmethod
    def rotation_180(lignes, colonnes, hauteur, largeur):
        """Coordonnées dans l'image tournée de 180° (caméras en miroir)."""
        return hauteur - lignes - 1, largeur - colonnes - 1

    @staticmethod
    def translation_par_vote(L, R, pas=5.0):
        """Translation t la plus fréquente telle que R + t ≈ L, sans connaître les paires.

        Chaque couple (gauche, droite) vote pour son décalage. L'histogramme est lissé
        sur 3x3 cases (un pic à cheval sur deux cases n'est pas coupé en deux), puis la
        translation est affinée par la médiane des votes proches du pic.
        """
        dx = (L[:, 0][:, None] - R[:, 0][None, :]).ravel()
        dy = (L[:, 1][:, None] - R[:, 1][None, :]).ravel()
        H, xe, ye = np.histogram2d(dx, dy, bins=[max(1, int(np.ptp(dx) / pas)),
                                                 max(1, int(np.ptp(dy) / pas))])
        H = uniform_filter(H, size=3, mode="constant")
        i, j = np.unravel_index(H.argmax(), H.shape)
        t = np.array([(xe[i] + xe[i + 1]) / 2, (ye[j] + ye[j + 1]) / 2])
        proches = (np.abs(dx - t[0]) < 2 * pas) & (np.abs(dy - t[1]) < 2 * pas)
        return np.array([np.median(dx[proches]), np.median(dy[proches])])

    @staticmethod
    def hongrois(L, R, dist_max):
        """Appariement un pour un optimal, limité aux paires à moins de dist_max.

        Le seuil est appliqué dans le coût, pas après : un couple trop éloigné coûte
        autant que de laisser une tache sans partenaire. Sinon, une tache vue par une
        seule caméra « vole » le partenaire de sa voisine, qui vole celui de la suivante,
        et toute une rangée de paires est décalée d'un cran puis rejetée par le seuil.
        """
        C = cdist(L, R)
        cout = np.where(C <= dist_max, C, 1e9)
        ri, ci = linear_sum_assignment(cout)
        ok = C[ri, ci] <= dist_max
        return ri[ok], ci[ok], C[ri[ok], ci[ok]]

    @staticmethod
    def monomes(P, degre):
        """Colonnes x^i y^j (i + j <= degre) des points P (n,2)."""
        x, y = P[:, 0], P[:, 1]
        return np.column_stack([x**i * y**j for d in range(degre + 1) for i in range(d + 1)
                                for j in [d - i]])

    @classmethod
    def ajuster_transformation(cls, src, dst, modele):
        """Ajuste dst ≈ f(src) au sens des moindres carrés ; renvoie la fonction f.

        affine      : translation, rotation, échelle, cisaillement (6 paramètres)
        homographie : perspective d'un plan vu par deux caméras (8 paramètres)
        polynome2/3 : perspective + distorsion des objectifs (12 / 20 paramètres)
        Les coordonnées sont centrées et réduites pour un calcul bien conditionné.
        """
        src, dst = np.asarray(src, float), np.asarray(dst, float)
        cs, ss = src.mean(0), src.std() or 1.0
        cd, sd = dst.mean(0), dst.std() or 1.0
        S, D = (src - cs) / ss, (dst - cd) / sd
        if modele == "homographie":
            A = []
            for (x, y), (u, v) in zip(S, D):
                A.append([-x, -y, -1, 0, 0, 0, x * u, y * u, u])
                A.append([0, 0, 0, -x, -y, -1, x * v, y * v, v])
            H = np.linalg.svd(np.asarray(A))[2][-1].reshape(3, 3)

            def f(p):
                q = np.column_stack([(np.asarray(p, float) - cs) / ss, np.ones(len(p))]) @ H.T
                return q[:, :2] / q[:, 2:3] * sd + cd
            return f
        degre = {"affine": 1, "polynome2": 2, "polynome3": 3}[modele]
        M, *_ = np.linalg.lstsq(cls.monomes(S, degre), D, rcond=None)
        return lambda p: cls.monomes((np.asarray(p, float) - cs) / ss, degre) @ M * sd + cd

    @staticmethod
    def ajuster_affine(src, dst):
        """Transformation affine dst ≈ src @ A.T + t, au sens des moindres carrés."""
        X = np.hstack([src, np.ones((len(src), 1))])
        M, *_ = np.linalg.lstsq(X, dst, rcond=None)
        return M[:2].T, M[2]

    @staticmethod
    def construire_Lp(all_pxl, all_pyl, all_pxr, all_pyr, paires):
        """Lp[image] = [points gauche, points droite], chaque point = (colonne, ligne).

        C'est le format lu par detect3D_*.py (Lp_final.npy). La droite est en
        coordonnées brutes, comme pour l'étalonnage.
        """
        iL = np.array([a for a, _ in paires], dtype=int)
        iR = np.array([b for _, b in paires], dtype=int)
        gauche = np.stack([all_pyl[:, iL], all_pxl[:, iL]], axis=-1)
        droite = np.stack([all_pyr[:, iR], all_pxr[:, iR]], axis=-1)
        return np.stack([gauche, droite], axis=1).astype(float)