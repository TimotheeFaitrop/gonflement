"""Appariement des taches entre les caméras gauche et droite, par l'étalonnage stéréo."""
import os
import sys
import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "Pycaso"))
from Pycaso import pycaso as pcs


def rotation_180(lignes, colonnes, hauteur, largeur):
    """Coordonnées dans l'image tournée de 180° (caméras en miroir)."""
    return hauteur - lignes - 1, largeur - colonnes - 1


def translation_par_vote(L, R, pas=5.0):
    """Translation t la plus fréquente telle que R + t ≈ L, sans connaître les paires."""
    dx = (L[:, 0][:, None] - R[:, 0][None, :]).ravel()
    dy = (L[:, 1][:, None] - R[:, 1][None, :]).ravel()
    H, xe, ye = np.histogram2d(dx, dy, bins=[max(1, int(np.ptp(dx) / pas)), max(1, int(np.ptp(dy) / pas))])
    i, j = np.unravel_index(H.argmax(), H.shape)
    return np.array([(xe[i] + xe[i + 1]) / 2, (ye[j] + ye[j + 1]) / 2])


def ajuster_affine(src, dst):
    """Transformation affine dst ≈ src @ A.T + t, au sens des moindres carrés."""
    X = np.hstack([src, np.ones((len(src), 1))])
    M, *_ = np.linalg.lstsq(X, dst, rcond=None)
    return M[:2].T, M[2]


def apparier_stereo(L, R_brut, R_tourne, L_constants, l_pform, rayon=150.0, tol_z=1.0):
    """Apparie les taches gauche et droite de la première image.

    Pour chaque tache de gauche, on prend les taches de droite voisines comme
    candidates, on calcule le point 3D de chaque paire avec l'étalonnage Lagrange,
    et on garde celle qui tombe sur le plan de l'échantillon (plat à l'image 0).

    L        : (N,2) taches gauche (colonne, ligne)
    R_brut   : (M,2) taches droite dans l'image brute (colonne, ligne), format de l'étalonnage
    R_tourne : (M,2) taches droite tournées de 180° (pour chercher les voisines)
    Renvoie  : indices gauche, indices droite, écart au plan (mm), R recalée sur L (pour la figure)
    """
    L, R_brut, R_tourne = (np.asarray(a, dtype=float) for a in (L, R_brut, R_tourne))
    t0 = translation_par_vote(L, R_tourne)
    voisines = cKDTree(R_tourne + t0).query_ball_point(L, rayon)
    I = np.array([i for i, v in enumerate(voisines) for _ in v], dtype=int)
    J = np.array([j for v in voisines for j in v], dtype=int)
    x, y, z = pcs.Lagrange_identification(L[I], R_brut[J], L_constants, l_pform)

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
    A, t = ajuster_affine(R_tourne[ci], L[ri])
    R_recale = R_tourne @ A.T + t
    ok = np.hypot(*(R_recale[ci] - L[ri]).T) < 40
    return ri[ok], ci[ok], C[ri[ok], ci[ok]], R_recale


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
