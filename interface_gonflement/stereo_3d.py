"""Déformation 3D en temps réel par stéréo-corrélation (Pycaso, Zernike ou Lagrange).

Chaîne utilisée pour le pilotage en déformation :

  caméra gauche (VideoExtenso, taches suivies) --+
                                                  +--> StereoDeformation --> PilotageDeformation
  caméra droite (VideoExtenso, taches suivies) --+         eps_3d (%)

1. Synchronisation : les deux caméras sont déclenchées par la même impulsion du
   FT232R ; l'image n de gauche est associée à l'image n de droite (contrôle sur
   les temps tl(s) / tr(s)).
2. Appariement (à la première image, une fois pour toutes) : les taches de
   droite sont tournées de 180° (caméras en miroir), recentrées sur celles de
   gauche, puis appariées une à une par l'algorithme hongrois — même principe
   que Pycaso/detection_spots_appariemment.py.
3. Identification 3D de chaque paire avec l'étalonnage :
   pcs.Zernike_identification(gauche, droite, A_Zernike, degré, taille caméras)
   (ou pcs.Lagrange_identification). Les points sont au format Pycaso
   (colonne, ligne), la droite en coordonnées brutes, comme à l'étalonnage.
4. Déformation = allongement des distances 3D entre taches par rapport à la
   première image :
     exx : paire de taches extrêmes selon X (repère de la mire)
     eyy : paire de taches extrêmes selon Y
     moyenne, max : de exx et eyy
     toutes : moyenne sur toutes les paires de taches (équibiaxial)
   La distance est la corde 3D entre taches : elle suit la membrane hors plan,
   contrairement à la vidéo-extensométrie 2D qui est faussée quand le dôme
   monte vers les caméras.

Le banc stéréo simulé (pour tester sans matériel) est dans simulation.py.
"""

import sys
from collections import deque
from itertools import combinations
from pathlib import Path

import numpy as np

import crappy

try:
    from .reglages import degre_depuis_chemin  # noqa: F401
except ImportError:
    from reglages import degre_depuis_chemin  # noqa: F401

RACINE = Path(__file__).resolve().parent.parent
COMPOSANTES = ("exx", "eyy", "moyenne", "max", "toutes")


def importer_pycaso():
    """pycaso.py fait « import solve_library » : le dossier Pycaso doit être dans
    sys.path (comme dans Pycaso/reconstruction_class.py)."""
    for p in (str(RACINE), str(RACINE / "Pycaso")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        from Pycaso import pycaso as pcs
    return pcs


def taille_cameras(fichier_constantes, taille_defaut):
    """[lignes g, colonnes g, lignes d, colonnes d], lue sur la première image de
    calibration si on la trouve (<date>/calib/Mesure/video_extenso_left), sinon taille_defaut."""
    try:
        from . import compat_cv2
    except ImportError:
        import compat_cv2
    compat_cv2.installer()
    try:
        import cv2
        resultats = Path(fichier_constantes).resolve().parent.parent  # results_calib
        dossier = resultats.parent          # <date>/calib (ou ancien <date>)
        for calib in sorted([*dossier.glob("Mesure*"), *dossier.glob("calib*")]):
            dims = []
            for cote in ("video_extenso_left", "video_extenso_right"):
                imgs = sorted(p for p in (calib / cote).glob("*")
                              if p.suffix.lower() in (".tiff", ".tif", ".png", ".bmp"))
                im = cv2.imread(str(imgs[0]), 0) if imgs else None
                if im is None:
                    break
                dims += list(im.shape[:2])
            if len(dims) == 4:
                return dims, f"lue sur {calib.name}"
    except Exception:
        pass
    t = int(taille_defaut)
    return [t, t, t, t], "taille d'image des réglages"


# ==========================================================================
# Appariement et déformation (sans crappy, testable seul)
# ==========================================================================
def pix_vers_pycaso(pix):
    """VideoExtenso envoie [(ligne, colonne), ...] ; Pycaso attend (colonne, ligne)."""
    a = np.asarray(pix, dtype=float).reshape(-1, 2)
    return a[:, ::-1].copy()


def apparier(L, R, hauteur, largeur, rotation_droite=True):
    """Indices (i_gauche, i_droite) des paires et résidu par paire (px).

    L, R : (N,2) et (M,2) en (colonne, ligne). R brute (non tournée).
    """
    from scipy.optimize import linear_sum_assignment
    from scipy.spatial.distance import cdist
    R2 = R.copy()
    if rotation_droite:
        R2[:, 0] = largeur - 1 - R[:, 0]
        R2[:, 1] = hauteur - 1 - R[:, 1]
    R2 = R2 - R2.mean(0) + L.mean(0)
    C = cdist(L, R2)
    ri, ci = linear_sum_assignment(C)
    return ri, ci, C[ri, ci]


class CalculDeformation:
    """Garde l'appariement et l'état initial, calcule la déformation à chaque image."""

    def __init__(self, identifier, hauteur, largeur, rotation_droite=True,
                 composante="toutes"):
        self.identifier = identifier          # f(L(n,2), R(n,2)) -> x, y, z
        self.h, self.w = hauteur, largeur
        self.rotation_droite = rotation_droite
        self.composante = composante
        self.ri = self.ci = None
        self.P0 = None
        self.messages = []

    def _initialiser(self, L, R):
        self.ri, self.ci, res = apparier(L, R, self.h, self.w, self.rotation_droite)
        if len(self.ri) < 2:
            raise ValueError("Il faut au moins 2 taches appariées")
        P = self._points(L, R)
        espacement = min(np.linalg.norm(L[a] - L[b]) for a, b in
                         combinations(range(len(L)), 2))
        self.messages.append(
            f"Appariement gauche->droite : {dict(zip(self.ri.tolist(), self.ci.tolist()))}, "
            f"résidu max {res.max():.1f} px (espacement mini {espacement:.0f} px)")
        if res.max() > 0.35 * espacement:
            self.messages.append("ATTENTION : appariement douteux (résidu grand devant "
                                 "l'espacement des taches) : vérifier les taches "
                                 "sélectionnées et l'option « droite tournée de 180° »")
        if not np.all(np.isfinite(P)):
            raise ValueError("Points 3D non finis à la première image (étalonnage ?)")
        self.P0 = P
        x0 = P[:, 0]
        y0 = P[:, 1]
        self.paire_x = (int(np.argmin(x0)), int(np.argmax(x0)))
        self.paire_y = (int(np.argmin(y0)), int(np.argmax(y0)))
        self.paires = list(combinations(range(len(P)), 2))
        self.d0 = {p: np.linalg.norm(P[p[0]] - P[p[1]]) for p in self.paires}
        self.messages.append(
            "Points 3D initiaux (mm) : " + "; ".join(
                f"({a:.2f}, {b:.2f}, {c:.2f})" for a, b, c in P)
            + f" — dispersion en z {np.ptp(P[:, 2]):.2f} mm")

    def _points(self, L, R):
        x, y, z = self.identifier(L[self.ri], R[self.ci])
        return np.column_stack([np.ravel(x), np.ravel(y), np.ravel(z)])

    def __call__(self, pix_g, pix_d):
        L, R = pix_vers_pycaso(pix_g), pix_vers_pycaso(pix_d)
        if self.P0 is None:
            self._initialiser(L, R)
        if max(self.ri.max(), 0) >= len(L) or max(self.ci.max(), 0) >= len(R):
            raise ValueError("Nombre de taches modifié en cours d'essai")
        P = self._points(L, R)

        def allong(p):
            d0 = self.d0[tuple(sorted(p))]
            return 100.0 * (np.linalg.norm(P[p[0]] - P[p[1]]) / d0 - 1.0)
        exx = allong(self.paire_x)
        eyy = allong(self.paire_y)
        toutes = float(np.mean([allong(p) for p in self.paires]))
        eps = {"exx": exx, "eyy": eyy, "moyenne": (exx + eyy) / 2,
               "max": max(exx, eyy), "toutes": toutes}[self.composante]
        uz = float(np.mean(P[:, 2] - self.P0[:, 2]))
        return {"eps_3d": float(eps), "exx_3d": float(exx), "eyy_3d": float(eyy),
                "eall_3d": toutes, "uz_3d": uz, "points_3d": P.round(4).tolist()}


# ==========================================================================
# Bloc crappy
# ==========================================================================
class StereoDeformation(crappy.blocks.Block):
    """Reçoit pix_l / pix_r des deux VideoExtenso et envoie la déformation 3D.

    Labels envoyés : t_3d, eps_3d (composante choisie, %), exx_3d, eyy_3d,
    eall_3d (%), uz_3d (mm, déplacement moyen hors plan), points_3d.
    """

    def __init__(self, fichier_constantes, methode="Zernike", degre=None,
                 taille_image=2048, rotation_droite=True, composante="toutes",
                 freq_cam=2.5, dims_cameras=None, freq=100):
        super().__init__()
        self.freq = freq
        self.fichier = str(fichier_constantes)
        self.methode = methode
        self.degre = degre or degre_depuis_chemin(fichier_constantes,
                                                  12 if methode == "Zernike" else 4)
        self.taille_image = taille_image
        self.dims = dims_cameras
        self.rotation_droite = rotation_droite
        self.composante = composante
        self.tol_sync = 0.5 / float(freq_cam)
        self.labels = ["t_3d", "eps_3d", "exx_3d", "eyy_3d", "eall_3d", "uz_3d",
                       "points_3d"]

    def prepare(self):
        pcs = importer_pycaso()
        A = np.load(self.fichier)
        if self.dims is None:
            self.dims, origine = taille_cameras(self.fichier, self.taille_image)
        else:
            origine = "fournie"
        self.log(20, f"Stéréo {self.methode} degré {self.degre}, constantes "
                     f"{A.shape} ({self.fichier}), caméras {self.dims} ({origine})")
        if self.methode == "Zernike":
            dims = self.dims

            def identifier(L, R):
                return pcs.Zernike_identification(L, R, A, self.degre, dims)
        else:
            def identifier(L, R):
                return pcs.Lagrange_identification(L, R, A, self.degre)
        self.calcul = CalculDeformation(identifier, self.dims[0], self.dims[1],
                                        self.rotation_droite, self.composante)
        self.gauche = deque(maxlen=200)
        self.droite = deque(maxlen=200)
        self.erreurs = 0

    def loop(self):
        d = self.recv_all_data()
        for t, p in zip(d.get("tl(s)", []), d.get("pix_l", [])):
            self.gauche.append((t, p))
        for t, p in zip(d.get("tr(s)", []), d.get("pix_r", [])):
            self.droite.append((t, p))
        while self.gauche and self.droite:
            (tg, pg), (td, pd) = self.gauche[0], self.droite[0]
            if abs(tg - td) > self.tol_sync:      # image perdue sur une caméra
                (self.gauche if tg < td else self.droite).popleft()
                self.log(30, f"Images non synchrones (tl={tg:.2f}, tr={td:.2f}) : "
                             "image isolée ignorée")
                continue
            self.gauche.popleft()
            self.droite.popleft()
            try:
                r = self.calcul(pg, pd)
            except Exception as e:
                self.erreurs += 1
                if self.erreurs <= 5:
                    self.log(40, f"Calcul 3D impossible : {e}")
                continue
            for m in self.calcul.messages:
                self.log(20, m)
            self.calcul.messages.clear()
            self.send({"t_3d": (tg + td) / 2, **r})
