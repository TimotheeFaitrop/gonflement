"""État d'un essai pour le post-traitement complet (chaine_gui.py) : ce qui est déjà fait, ce qui manque.

Étapes de la chaîne :
    1 calibration           <calib>/../results_calib/<Lpform_4, Spform_332, nZ_6...>
    2 détection des taches  <essai>/appariemment_et_suivi/Lp_final.npy
    3 correction plate      <essai>/appariemment_et_suivi/Lp_final_corrige.npy (photos photo_init_L / _R)
    4 reconstruction        <essai>/reconstruction/<tag>[_corrige]/X3d.txt, Y3d.txt, Z3d.txt
    5 retouche              <essai>/reconstruction/[<source>/]taches_exclues.json
    6 déformation, 7 anisotropie, 8 pression (data_ali.txt)

Aucune interface ici : seulement la lecture des dossiers, pour proposer de sauter les étapes
déjà faites (par exemple refaire seulement la reconstruction avec une autre calibration).
"""
import re
from pathlib import Path

ETAPES = {
    1: "Calibration",
    2: "Détection et appariement des taches",
    3: "Correction par l'état plat",
    4: "Reconstruction 3D",
    5: "Retouche des taches aberrantes",
    6: "Déformation",
    7: "Anisotropie",
    8: "Pression en fonction de Uz",
}

# méthode : motif du sous-dossier d'étalonnage et fichiers de constantes (comme Detect3D.METHODES)
METHODES = {
    "Lagrange": ("Lpform", ("L_constants.npy",)),
    "Soloff":   ("Spform", ("S_constants0.npy", "S_constants.npy")),
    "Zernike":  ("nZ",     ("A_Zernike.npy",)),
}
DOSSIER_RESULTATS_CALIB = "results_calib"      # Calibration.RESULTS_FOLDER : à côté du dossier des images
SOUS_DOSSIERS_CAMERAS = ("video_extenso_left", "video_extenso_right")
FICHIERS_3D = ("X3d.txt", "Y3d.txt", "Z3d.txt")


def source_vers_methode(nom):
    """'Lpform_4_corrige' -> ('Lagrange', 4, True) ; None si le nom n'est pas reconnu."""
    m = re.fullmatch(r"(Lpform|Spform|nZ)_(\d+)(_corrige)?", nom)
    if not m:
        return None
    methode = next(k for k, (p, _) in METHODES.items() if p == m.group(1))
    return methode, int(m.group(2)), bool(m.group(3))


class EtatEssai:
    """Fichiers présents pour un dossier de calibration et un dossier d'essai."""

    def __init__(self, dossier_calib, dossier_essai):
        self.dossier_calib = Path(dossier_calib) if dossier_calib else None
        self.dossier_essai = Path(dossier_essai) if dossier_essai else None

    # ----- calibration -----

    @property
    def resultats_calib(self):
        """<calib>/../results_calib (là où Calibration enregistre)."""
        if self.dossier_calib is None:
            return None
        return self.dossier_calib.resolve().parent / DOSSIER_RESULTATS_CALIB

    def photos_calib(self):
        """Nombre de photos (gauche, droite) du dossier de calibration ; None si un sous-dossier manque."""
        if self.dossier_calib is None:
            return None
        res = []
        for sous in SOUS_DOSSIERS_CAMERAS:
            d = self.dossier_calib / sous
            if not d.is_dir():
                return None
            res.append(len([f for f in d.glob("[0-9]*") if f.is_file()]))
        return tuple(res)

    def etalonnages(self):
        """Étalonnages complets déjà calculés : [(méthode, degré, dossier)], du plus récent au plus ancien."""
        r = self.resultats_calib
        if r is None or not r.is_dir():
            return []
        trouves = []
        for methode, (prefixe, fichiers) in METHODES.items():
            for d in r.glob(f"{prefixe}_*"):
                m = re.fullmatch(rf"{prefixe}_(\d+)", d.name)
                if m and all((d / f).is_file() for f in fichiers):
                    trouves.append((methode, int(m.group(1)), d))
        return sorted(trouves, key=lambda t: max((t[2] / f).stat().st_mtime for f in METHODES[t[0]][1]),
                      reverse=True)

    # ----- essai -----

    @property
    def dossier_appariement(self):
        return self.dossier_essai / "appariemment_et_suivi"

    @property
    def lp_final(self):
        return self.dossier_appariement / "Lp_final.npy"

    @property
    def lp_corrige(self):
        return self.dossier_appariement / "Lp_final_corrige.npy"

    def essai_valide(self):
        return self.dossier_essai is not None and all((self.dossier_essai / s).is_dir()
                                                      for s in SOUS_DOSSIERS_CAMERAS)

    def photos_planes(self):
        """Photos de l'état plat (photo_init_L.*, photo_init_R.*) : (gauche, droite), None si absente."""
        res = []
        for sous, lettre in zip(SOUS_DOSSIERS_CAMERAS, "LR"):
            trouves = sorted((self.dossier_essai / sous).glob(f"photo_init_{lettre}.*")) if self.dossier_essai else []
            res.append(trouves[0] if trouves else None)
        return tuple(res)

    def correction_a_jour(self):
        """True si Lp_final_corrige.npy existe et est plus récent que Lp_final.npy."""
        return (self.lp_corrige.is_file() and self.lp_final.is_file()
                and self.lp_corrige.stat().st_mtime >= self.lp_final.stat().st_mtime)

    def reconstructions(self):
        """Reconstructions complètes : [(nom, date de Z3d.txt)], de la plus récente à la plus ancienne."""
        d = self.dossier_essai / "reconstruction" if self.dossier_essai else None
        if d is None or not d.is_dir():
            return []
        res = [(c.name, (c / "Z3d.txt").stat().st_mtime) for c in d.iterdir()
               if c.is_dir() and all((c / f).is_file() for f in FICHIERS_3D)]
        return sorted(res, key=lambda t: t[1], reverse=True)

    def fichier_pression(self):
        f = self.dossier_essai / "data_ali.txt" if self.dossier_essai else None
        return f if f is not None and f.is_file() else None

    def exclusions(self, source):
        """Résumé des taches exclues à la main pour une reconstruction."""
        from Pycaso.retouche_class import ExclusionsTaches
        return ExclusionsTaches(self.dossier_essai, source).resume()