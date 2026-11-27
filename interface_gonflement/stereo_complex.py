"""Calibration et reconstruction 3D avec StereoComplex, à la place de Pycaso.

  calibrer(...)   images de la mire (balayage en Z) -> <results_calib>/SC_<nmax>/
                    model.json + weights.npz   modèle de rayons de StereoComplex
                    repere_mire.npz            passage du repère de la caméra gauche au repère de Pycaso
                    bilan_calibration.json     erreurs mesurées sur les plans de la calibration
  Modele3D(f)     relit ce dossier et donne un identifieur  f(L, R) -> (x, y, z)  que l'on peut
                  brancher à la place de pcs.Zernike_identification / pcs.Lagrange_identification.

Repère de sortie
----------------
StereoComplex donne les points dans le repère de la caméra gauche. Pycaso, lui, donne X, Y dans
le plan de la mire (X = (ncx − 1 − j)·carré, Y = (i + 1)·carré pour le coin d'indice i, j) et Z =
hauteur du plateau. Toute la suite (plan de référence, inversion de Z, déformations…) suppose ce
repère.

Un balayage en Z seul (plans parallèles, la mire ne s'incline jamais) ne permet pas à StereoComplex
de fixer l'échelle métrique du modèle : les rayons sont cohérents entre eux (écart de quelques
µm) mais l'espace reconstruit est déformé par une transformation affine (sur des images simulées :
facteurs de 0,85 à 1,5 selon la direction). Elle est corrigée avec ce que l'on sait : les coordonnées
des coins de la mire et la hauteur du plateau de chaque plan. Les coins sont triangulés plan par plan,
puis la transformation affine (matrice 3 × 3 + translation) qui les amène sur leurs coordonnées
connues est enregistrée dans repere_mire.npz et appliquée à chaque triangulation. Conséquence : la
justesse en Z dépend de la justesse des hauteurs z_list, comme avec Pycaso.

Conventions (identiques à Pycaso) : pixels en (colonne, ligne), centre de pixel entier (OpenCV),
mire ChArUco 12 × 12 carrés de 7,5 mm, marqueurs de la moitié d'un carré, DICT_6X6_250.
Nécessite le paquet stereocomplex (https://github.com/jeffwitz/StereoComplex, branche develop) :
  git clone --branch develop https://github.com/jeffwitz/StereoComplex.git
  pip install -e StereoComplex
"""

import json
import re
from pathlib import Path

import numpy as np

NCX, NCY, SQR = 12, 12, 7.5            # mire ChArUco (comme Pycaso/calibration_class.py)
DICTIONNAIRE = "DICT_6X6_250"
EXT_IMAGES = (".tif", ".tiff", ".png", ".bmp", ".jpg", ".jpeg")
FICHIER_MODELE = "model.json"
FICHIER_REPERE = "repere_mire.npz"
FICHIER_BILAN = "bilan_calibration.json"


def importer_stereocomplex():
    try:
        import stereocomplex as sc
    except ImportError as e:
        raise RuntimeError(
            "Le paquet stereocomplex n'est pas installé. Dans le dossier du projet :\n"
            "  git clone --branch develop https://github.com/jeffwitz/StereoComplex.git\n"
            "  pip install -e StereoComplex") from e
    return sc


# ---------------------------------------------------------------- mire et images

def spec_mire(legacy, ncx=NCX, ncy=NCY, sqr=SQR):
    """Description de la mire pour StereoComplex (mêmes réglages de détection que Pycaso)."""
    sc = importer_stereocomplex()
    return sc.CharucoBoardSpec(squares_x=ncx, squares_y=ncy, square_size_mm=sqr,
                               marker_size_mm=sqr / 2, aruco_dictionary=DICTIONNAIRE,
                               adaptive_thresh_win_size_max=300, legacy_pattern=bool(legacy))


def _cle_nom(p):
    """Tri naturel : 2.tiff avant 10.tiff (le tri alphabétique les inverserait)."""
    m = re.match(r"\d+", p.name)
    return (int(m.group()) if m else 10 ** 12, p.name)


def _images_dossier(d):
    d = Path(d)
    return sorted((p for p in d.glob("*") if p.suffix.lower() in EXT_IMAGES), key=_cle_nom) \
        if d.is_dir() else []


def images_camera(path_images, cote):
    return _images_dossier(Path(path_images) / f"video_extenso_{cote}")


def format_mire(images, n_test=6):
    """True si la mire est au format « ancien » (legacy), False si « nouveau » : celui des deux qui
    donne le plus de coins sur quelques images (comme lancer_calibration.format_mire)."""
    sc = importer_stereocomplex()
    pas = max(1, len(images) // n_test)
    scores = {}
    for legacy in (True, False):
        spec = spec_mire(legacy)
        total = 0
        for im in images[::pas][:n_test]:
            det = sc.detect_charuco_corners(image=im, board=spec)
            total += 0 if det is None else len(det.charuco_ids)
        scores[legacy] = total
    print(f"Format de la mire : ancien (legacy) {scores[True]} coins, nouveau {scores[False]} coins "
          f"sur {min(n_test, len(images))} images test", flush=True)
    return scores[True] >= scores[False]


def coord_reference(ids, ncx=NCX, ncy=NCY, sqr=SQR):
    """X, Y (mm) de chaque coin de la mire dans le repère de Pycaso (data_library.calibration_model).
    Le numéro k d'un coin est k = i·(ncx − 1) + j, i = ligne, j = colonne de la mire."""
    ids = np.asarray(ids, dtype=int).ravel()
    i, j = ids // (ncx - 1), ids % (ncx - 1)
    return np.column_stack([(ncx - (j + 1)) * sqr, (i + 1) * sqr])


def _coins(sc, spec, image):
    """{numéro de coin: (colonne, ligne)} d'une image, avec le raffinement 2D de StereoComplex."""
    det = sc.detect_charuco_corners(image=image, board=spec)
    if det is None or len(det.charuco_ids) == 0:
        return {}
    xy = sc.refine_charuco_corners(method="rayfield_tps_robust", board=spec, detections=det)
    return {int(k): np.asarray(v, float) for k, v in zip(np.ravel(det.charuco_ids), xy)}


# ---------------------------------------------------------------- calibration

def _transformation_affine(P, T):
    """M (3×3), t tels que T ≈ P·Mᵀ + t, par moindres carrés."""
    A, *_ = np.linalg.lstsq(np.c_[P, np.ones(len(P))], T, rcond=None)
    return A[:3].T, A[3]


def _transformation_rigide(P, T):
    """R (3×3, orthogonale), t tels que T ≈ P·Rᵀ + t (Procruste orthogonal, sans échelle).
    det(R) = −1 est possible : le repère de Pycaso peut être l'image en miroir du repère
    de la caméra (X est compté dans le sens inverse des colonnes de la mire)."""
    Pc, Tc = P.mean(0), T.mean(0)
    U, _, Vt = np.linalg.svd((P - Pc).T @ (T - Tc))
    R = (U @ Vt).T
    return R, Tc - R @ Pc


def calibrer(path_images, z_list, dossier_sortie, nmax=10, legacy=None, figures=True,
             sous_dossiers=None, afficher=False):
    """Calibre la paire de caméras avec StereoComplex à partir des images de la mire.

    path_images   dossier contenant video_extenso_left et video_extenso_right
    z_list        hauteur du plateau (mm) pour chaque paire d'images, dans l'ordre des photos
    dossier_sortie  dossier de résultats (ex. results_calib/SC_10)
    nmax          ordre maximal de Zernike du champ de rayons (10 par défaut)
    legacy        format de la mire ; None = détecté sur quelques images
    sous_dossiers (gauche, droite) : noms des sous-dossiers des caméras ; None = video_extenso_left / _right
    afficher      ouvre les figures à la fin (sinon elles sont seulement enregistrées)
    Renvoie le dictionnaire du bilan (écrit aussi dans bilan_calibration.json).
    """
    sc = importer_stereocomplex()
    sg, sd = sous_dossiers or ("video_extenso_left", "video_extenso_right")
    gauches, droites = _images_dossier(Path(path_images) / sg), _images_dossier(Path(path_images) / sd)
    z_list = np.asarray(z_list, float)
    if not (len(gauches) == len(droites) == len(z_list)):
        raise ValueError(f"{len(gauches)} images à gauche, {len(droites)} à droite, {len(z_list)} "
                         "plans : il en faut autant (l'image n correspond à la hauteur n)")
    if len(z_list) < 3:
        raise ValueError("Il faut au moins 3 plans")
    if legacy is None:
        legacy = format_mire(gauches + droites)
    spec = spec_mire(legacy)
    dossier_sortie = Path(dossier_sortie)
    dossier_sortie.mkdir(parents=True, exist_ok=True)

    paires = [sc.StereoImagePair(left_path=g, right_path=d, frame_id=k)
              for k, (g, d) in enumerate(zip(gauches, droites))]
    print(f"StereoComplex : calibration sur {len(paires)} paires, ordre de Zernike {nmax} "
          "(quelques minutes)...", flush=True)
    from stereocomplex.api import fit_stereo_central_rayfield_from_image_pairs
    res = fit_stereo_central_rayfield_from_image_pairs(
        image_pairs=paires, board=spec, method2d="rayfield_tps_robust", nmax=int(nmax),
        export_model_dir=dossier_sortie)
    modele, rapport = res.model, res.report
    utilises = [int(k) for k in rapport.used_frame_ids]
    ecartes = [k + 1 for k in range(len(paires)) if k not in utilises]
    print(f"Plans utilisés : {len(utilises)} sur {len(paires)}"
          + (f" ; écartés (mire non détectée sur les deux caméras) : plans n° {ecartes}" if ecartes else ""),
          flush=True)

    # coins de la mire triangulés sur chaque plan -> repère de Pycaso
    P, T, plan = [], [], []
    for k in utilises:
        cg, cd = _coins(sc, spec, gauches[k]), _coins(sc, spec, droites[k])
        communs = sorted(set(cg) & set(cd))
        if len(communs) < 10:
            continue
        xyz, _ = modele.triangulate(np.array([cg[i] for i in communs]), np.array([cd[i] for i in communs]))
        xy = coord_reference(communs)
        P.append(xyz)
        T.append(np.column_stack([xy, np.full(len(communs), z_list[k])]))
        plan += [k] * len(communs)
    if not P:
        raise RuntimeError("Aucun plan exploitable pour établir le repère de la mire")
    P, T, plan = np.vstack(P), np.vstack(T), np.asarray(plan)
    M, t = _transformation_affine(P, T)
    ecart = T - (P @ M.T + t)                       # mm, dans le repère de Pycaso
    Rr, tr = _transformation_rigide(P, T)           # pour mesurer ce que la correction affine apporte
    ecart_rigide = T - (P @ Rr.T + tr)
    # validation croisée : chaque plan est prédit par une transformation ajustée sur les autres
    croise = []
    for k in np.unique(plan):
        a = plan != k
        if len(np.unique(plan[a])) >= 3:
            Mk, tk = _transformation_affine(P[a], T[a])
            croise.append(T[~a] - (P[~a] @ Mk.T + tk))
    ecart_croise = np.vstack(croise) if croise else None
    par_plan = {int(k): {"z_mm": float(z_list[k]), "ecart_z_moyen_mm": float(ecart[plan == k, 2].mean()),
                         "rms_xyz_mm": float(np.sqrt((ecart[plan == k] ** 2).sum(1).mean()))}
                for k in np.unique(plan)}
    bilan = {
        "methode": "StereoComplex", "nmax": int(nmax), "format_mire": "legacy" if legacy else "nouveau",
        "plans": len(paires), "plans_utilises": len(utilises), "plans_ecartes": ecartes,
        "image_largeur_px": int(rapport.image_width_px), "image_hauteur_px": int(rapport.image_height_px),
        "skew_rms_mm": float(rapport.train_skew_rms_mm), "skew_p95_mm": float(rapport.train_skew_p95_mm),
        "rms_x_mm": float(np.sqrt((ecart[:, 0] ** 2).mean())),
        "rms_y_mm": float(np.sqrt((ecart[:, 1] ** 2).mean())),
        "rms_z_mm": float(np.sqrt((ecart[:, 2] ** 2).mean())),
        "rms_xyz_mm": float(np.sqrt((ecart ** 2).sum(1).mean())),
        "rms_rigide_xyz_mm": float(np.sqrt((ecart_rigide ** 2).sum(1).mean())),
        "rms_validation_croisee_mm": None if ecart_croise is None
        else float(np.sqrt((ecart_croise ** 2).sum(1).mean())),
        "valeurs_singulieres": [float(v) for v in np.linalg.svd(M)[1]],
        "repere_inverse": bool(np.linalg.det(M) < 0),
        "par_plan": par_plan,
    }
    np.savez(dossier_sortie / FICHIER_REPERE, M=M, t=t, z_list=z_list, nmax=int(nmax),
             largeur=int(rapport.image_width_px), hauteur=int(rapport.image_height_px))
    (dossier_sortie / FICHIER_BILAN).write_text(json.dumps(bilan, indent=2, ensure_ascii=False),
                                                encoding="utf-8")
    print(f"Écart avec la mire connue, sur {len(P)} coins : X {bilan['rms_x_mm']:.4f}, "
          f"Y {bilan['rms_y_mm']:.4f}, Z {bilan['rms_z_mm']:.4f} mm (RMS) ; "
          f"écart des rayons {bilan['skew_rms_mm']:.4f} mm", flush=True)
    if bilan["rms_validation_croisee_mm"] is not None:
        print(f"Validation croisée (chaque plan prédit sans lui) : {bilan['rms_validation_croisee_mm']:.4f} mm "
              f"(RMS 3D) ; avec une simple rotation, l'écart serait de {bilan['rms_rigide_xyz_mm']:.3f} mm",
              flush=True)
    if bilan["rms_validation_croisee_mm"] is not None and bilan["rms_validation_croisee_mm"] > 0.2:
        print("ATTENTION : la validation croisée dépasse 0,2 mm : hauteurs z_list fausses, mire mal "
              "détectée sur certains plans, ou plateau qui n'a pas atteint sa hauteur.", flush=True)
    if figures:
        _figures(dossier_sortie, T - ecart, ecart, plan, z_list, afficher)
    return bilan


def _figures(dossier, points, ecart, plan, z_list, afficher=False):
    """Nuage 3D des coins reconstruits et erreur par plan (noms repris par l'interface)."""
    import matplotlib
    import matplotlib.pyplot as plt
    ax = plt.figure().add_subplot(111, projection="3d")
    ax.scatter(points[:, 0], points[:, 1], points[:, 2], s=4, c=points[:, 2])
    ax.set_xlabel("X"), ax.set_ylabel("Y"), ax.set_zlabel("Z")
    ax.set_title("StereoComplex - coins de la mire reconstruits")
    plt.savefig(dossier / "Coord3D_StereoComplex.png")
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4))
    k = np.unique(plan)
    a1.plot([z_list[i] for i in k], [ecart[plan == i, 2].mean() for i in k], "o-")
    a1.set_xlabel("Z du plan (mm)"), a1.set_ylabel("écart Z moyen (mm)")
    a1.set_title("Erreur en Z par plan")
    a2.hist(np.sqrt((ecart ** 2).sum(1)), bins=40)
    a2.set_xlabel("écart 3D (mm)"), a2.set_ylabel("coins")
    a2.set_title("Distribution de l'erreur")
    fig.tight_layout()
    plt.savefig(dossier / "Retroprojection_erreur_StereoComplex.png")
    if afficher:
        plt.show()
    plt.close("all")


# ---------------------------------------------------------------- reconstruction

class Modele3D:
    """Modèle calibré : triangulation (colonne, ligne) -> (x, y, z) dans le repère de Pycaso."""

    def __init__(self, chemin):
        """chemin : le dossier SC_<n> ou son model.json."""
        sc = importer_stereocomplex()
        d = Path(chemin)
        self.dossier = d.parent if d.is_file() else d
        self.modele = sc.load_stereo_central_rayfield(self.dossier)
        rep = self.dossier / FICHIER_REPERE
        if not rep.is_file():
            raise FileNotFoundError(f"{rep} introuvable : refaire la calibration StereoComplex")
        r = np.load(rep)
        self.M, self.t = r["M"], r["t"]
        self.largeur, self.hauteur = int(r["largeur"]), int(r["hauteur"])

    @property
    def dims(self):
        """[lignes g, colonnes g, lignes d, colonnes d], comme taille_cameras de stereo_3d."""
        return [self.hauteur, self.largeur, self.hauteur, self.largeur]

    def triangulation(self, L, R, ecart_max_mm=None):
        """Points 3D (3, n) pour les pixels L (gauche) et R (droite), tableaux (n, 2) en (colonne, ligne).
        ecart_max_mm : si donné, les points dont les deux rayons passent à plus de cette distance
        l'un de l'autre (mauvais appariement) sont remplacés par NaN."""
        L, R = np.asarray(L, float).reshape(-1, 2), np.asarray(R, float).reshape(-1, 2)
        ok = np.isfinite(L).all(1) & np.isfinite(R).all(1)        # tache perdue (NaN) -> point NaN
        p = np.full((len(L), 3), np.nan)
        ecart = np.full(len(L), np.nan)
        if ok.any():
            xyz, e = self.modele.triangulate(L[ok], R[ok])
            p[ok] = xyz @ self.M.T + self.t
            ecart[ok] = e
        if ecart_max_mm is not None:
            p[ecart > ecart_max_mm] = np.nan
        return p.T

    __call__ = triangulation


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Calibration StereoComplex d'un dossier d'images de mire")
    ap.add_argument("dossier_images", help="dossier avec video_extenso_left et video_extenso_right")
    ap.add_argument("z_depart", type=float)
    ap.add_argument("z_fin", type=float)
    ap.add_argument("pas", type=float)
    ap.add_argument("--nmax", type=int, default=10)
    a = ap.parse_args()
    n = int(round(abs(a.z_fin - a.z_depart) / a.pas)) + 1
    z = a.z_depart + (1 if a.z_fin >= a.z_depart else -1) * a.pas * np.arange(n)
    sortie = Path(a.dossier_images).resolve().parent / "results_calib" / f"SC_{a.nmax}"
    calibrer(a.dossier_images, z, sortie, nmax=a.nmax)
    print(f"Modèle enregistré dans {sortie}")
