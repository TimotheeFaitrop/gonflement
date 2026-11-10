"""Matériel simulé, pour essayer l'interface et régler les gains sans banc d'essai.

  AlicatSimule    : débitmètre + ballon (volume -> pression, déformation)
  BancStereo      : deux caméras sténopé en miroir + étalonnage Zernike synthétique
  CamerasSimulees : remplace les deux VideoExtenso (taches projetées sur le banc)
"""

import math
import random
import time

import numpy as np

import crappy

try:
    from .stereo_3d import importer_pycaso
except ImportError:
    from stereo_3d import importer_pycaso


class AlicatSimule(crappy.inout.InOut):
    """Remplace Flow_controller_alicat. Modèle simple de membrane gonflée :
    volume = intégrale du débit (moins une petite fuite), pression et
    déformation fonctions croissantes du volume, avec un peu de bruit."""

    def __init__(self, pleine_echelle=1000.0, pression_relative=False, **_):
        super().__init__()
        self.fs = pleine_echelle
        self.p_atm = 0.0 if pression_relative else 1013.0

    def open(self):
        self.t = time.time()
        self.volume = 0.0       # mL
        self.q = 0.0            # mL/min réel (retard du 1er ordre)
        self.cmd = 0.0

    def _etat(self):
        now = time.time()
        dt, self.t = now - self.t, now
        self.q += (self.cmd * self.fs - self.q) * min(1.0, dt / 0.5)
        p_rel = 300 * (1 - math.exp(-self.volume / 20)) + 2.0 * self.volume
        fuite = 0.01 * p_rel                       # mL/min
        self.volume = max(0.0, self.volume + (self.q - fuite) * dt / 60)
        return p_rel

    def get_data(self):
        p_rel = self._etat()
        eps = 100 * (math.sqrt(1 + self.volume / 40) - 1)
        b = random.gauss
        return [time.time(), self.p_atm + p_rel + b(0, 0.5), self.q + b(0, 0.05),
                self.q * 1.2e-3, eps * 1.05 + b(0, 0.03), eps * 0.95 + b(0, 0.03)]

    def set_cmd(self, cmd):
        if cmd is not None:
            self._etat()
            self.cmd = max(0.0, float(cmd))

    def close(self):
        self.cmd = 0.0


class BancStereo:
    """Deux caméras sténopé au-dessus du plateau, caméra droite tournée de 180°.
    Repère monde en mm : x, y sur la mire, z hauteur (comme le Z de l'imprimante)."""

    def __init__(self, taille=2048, f=5600.0, hauteur_cam=330.0, base=70.0,
                 cible=(40.0, 40.0, 50.0)):
        self.taille = taille
        self.f = f
        self.cams = []
        for sx in (-1, 1):
            c = np.array([cible[0] + sx * base, cible[1], hauteur_cam])
            avant = np.asarray(cible) - c
            avant /= np.linalg.norm(avant)
            droite = np.cross(avant, [0, 1, 0])
            droite /= np.linalg.norm(droite)
            bas = np.cross(avant, droite)
            self.cams.append((c, np.vstack([droite, bas, avant])))

    def projeter(self, P, cam):
        """P (n,3) mm -> (n,2) pixels (colonne, ligne)."""
        c, Rm = self.cams[cam]
        q = (np.asarray(P, float) - c) @ Rm.T
        u = self.f * q[:, 0] / q[:, 2] + self.taille / 2
        v = self.f * q[:, 1] / q[:, 2] + self.taille / 2
        if cam == 1:                                # caméra droite en miroir
            u, v = self.taille - 1 - u, self.taille - 1 - v
        return np.column_stack([u, v])

    def calibration_zernike(self, degre=8, z_list=range(70, 30, -2)):
        """Constantes A (3, n) ajustées comme Pycaso.Zernike_calibration :
        points de mire sur chaque plan z, X = A . M(Xc1, Xc2)."""
        pcs = importer_pycaso()
        import solve_library as solvel
        g = np.arange(0, 81, 4.0)
        X, Y = np.meshgrid(g, g)
        pts = []
        for z in z_list:
            pts.append(np.column_stack([X.ravel(), Y.ravel(), np.full(X.size, z)]))
        P = np.vstack(pts)
        Xc1 = self.projeter(P, 0).T
        Xc2 = self.projeter(P, 1).T
        dims = [self.taille] * 4
        M = solvel.Zernike_Polynome({"polynomial_form": degre}).pol_form(Xc1, Xc2, dims)
        A, *_ = np.linalg.lstsq(M.T, P, rcond=None)
        A = A.T
        Pr = pcs.Zernike_identification(Xc1.T, Xc2.T, A, degre, dims)
        err = np.abs(np.asarray(Pr) - P.T).max()
        return A, dims, err


class CamerasSimulees(crappy.blocks.Block):
    """Remplace les deux VideoExtenso en simulation : 4 taches en croix sur la
    membrane, étirées selon exx_sim / eyy_sim du ballon simulé et soulevées vers
    les caméras (dôme), projetées sur les deux caméras du banc.
    Envoie les mêmes labels que les VideoExtenso (pix_l, exx_l, ... en %)."""

    def __init__(self, freq_cam=2.5, demi_ecart=10.0, z0=50.0, fleche_par_pc=0.6):
        super().__init__()
        self.freq = float(freq_cam)
        self.demi = demi_ecart
        self.z0 = z0
        self.fleche = fleche_par_pc
        self.labels = ["tl(s)", "pix_l", "eyy_l", "exx_l",
                       "tr(s)", "pix_r", "eyy_r", "exx_r"]

    def prepare(self):
        self.banc = BancStereo()
        self.eps = (0.0, 0.0)
        self.l0 = None
        self.ordre_droite = [2, 0, 3, 1]   # ordre de sélection différent à droite
        self.rng = np.random.default_rng(0)

    def _taches(self):
        ex, ey = self.eps
        a, b = self.demi * (1 + ex / 100), self.demi * (1 + ey / 100)
        z = self.z0 + self.fleche * (ex + ey) / 2
        cx, cy = 40.0, 40.0
        return np.array([[cx - a, cy, z], [cx + a, cy, z], [cx, cy - b, z], [cx, cy + b, z]])

    def loop(self):
        d = self.recv_last_data(fill_missing=False)
        if "exx_sim" in d:
            self.eps = (float(d["exx_sim"]), float(d["eyy_sim"]))
        P = self._taches()
        t = time.time() - self.t0
        out = {}
        for cam, s in ((0, "l"), (1, "r")):
            uv = self.banc.projeter(P, cam) + self.rng.normal(0, 0.05, (len(P), 2))
            if cam == 1:
                uv = uv[self.ordre_droite]
            x, y = uv[:, 0], uv[:, 1]
            if self.l0 is None or s not in self.l0:
                self.l0 = {**(self.l0 or {}), s: (np.ptp(x), np.ptp(y))}
            out[f"t{s}(s)"] = t
            out[f"pix_{s}"] = [(float(r), float(c)) for c, r in uv]   # (ligne, colonne)
            out[f"exx_{s}"] = 100 * (np.ptp(x) / self.l0[s][0] - 1)
            out[f"eyy_{s}"] = 100 * (np.ptp(y) / self.l0[s][1] - 1)
        self.send(out)


def images_mire(dossier, z_list, t_plan, afficher=True, ncx=12, ncy=12, sqr=7.5):
    """Acquisition de calibration simulée : la mire ChArUco de Pycaso (DICT_6X6_250,
    12 x 12 carrés de 7,5 mm) posée à chaque hauteur et vue par les deux caméras du
    banc. Images nommées comme DualXiAPICamera (calib_crappy_V2)."""
    import cv2
    from pathlib import Path
    dossier = Path(dossier)
    dico = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
    planche = cv2.aruco.CharucoBoard((ncx, ncy), sqr, sqr / 2, dico)
    px_mm = 20
    L, H = int(ncx * sqr * px_mm), int(ncy * sqr * px_mm)
    img_planche = planche.generateImage((L, H), marginSize=0)
    banc = BancStereo()
    taille = banc.taille
    coins_px = np.float32([[0, 0], [L, 0], [L, H], [0, H]])
    x0, y0 = 40 - ncx * sqr / 2, 40 - ncy * sqr / 2          # mire centrée sur le banc
    graphe = None
    if afficher:
        try:
            import matplotlib.pyplot as plt
            plt.ion()
            fig, ax = plt.subplots(figsize=(6, 3.5))
            fig.canvas.manager.set_window_title("Hauteur du plateau (simulation)")
            ax.set_xlabel("t (s)"), ax.set_ylabel("position (mm)")
            ligne, = ax.step([], [], where="post")
            graphe = (plt, ax, ligne, [], [])
        except Exception:
            graphe = None
    for cote in ("left", "right"):
        (dossier / f"video_extenso_{cote}").mkdir(parents=True, exist_ok=True)
    for i, z in enumerate(z_list):
        # mire imprimée face visible : la ligne 0 de l'image de la planche est en haut
        # (y monde max) vue du dessus, sinon l'image est en miroir et ArUco ne lit rien
        monde = np.array([[x0, y0 + ncy * sqr, z], [x0 + ncx * sqr, y0 + ncy * sqr, z],
                          [x0 + ncx * sqr, y0, z], [x0, y0, z]])
        t = i * t_plan
        for cam, cote in ((0, "left"), (1, "right")):
            M = cv2.getPerspectiveTransform(coins_px, np.float32(banc.projeter(monde, cam)))
            im = cv2.warpPerspective(img_planche, M, (taille, taille), flags=cv2.INTER_LINEAR,
                                     borderValue=90)
            cv2.imwrite(str(dossier / f"video_extenso_{cote}" / f"{i:06d}__{t:.3f}.tiff"), im)
        print(f"[simulation] plan {i + 1}/{len(z_list)} : Z = {z} mm, 2 images de la mire",
              flush=True)
        if graphe:
            plt_, ax, ligne, ts, zs = graphe
            ts += [t, t + t_plan]
            zs += [z, z]
            ligne.set_data(ts, zs)
            ax.relim(), ax.autoscale_view()
            plt_.pause(0.05)
        else:
            time.sleep(0.05)
    if graphe:
        graphe[0].ioff()
        graphe[0].show(block=False)
        graphe[0].pause(1.5)
