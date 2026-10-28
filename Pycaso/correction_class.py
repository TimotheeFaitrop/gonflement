"""Correction d'un essai à partir de la photo de l'état plat (avant serrage, non flambé).

Au serrage des mors l'échantillon flambe : la première image de l'essai (état serré) n'est
plus plane. La paire de photos prise avant le serrage (photo_init_L / photo_init_R, dans
video_extenso_left / video_extenso_right) sert à :
  0. reconstruire l'état plat, automatiquement et avec les mêmes outils que l'essai :
     détection des taches (SuiviTaches), appariement gauche/droite (AppariementStereo),
     points 3D (Detect3D, même méthode, degré, étalonnage et facteur Z que la source) ;
  1. trier les taches : un plan est ajusté (de façon robuste) sur l'état plat ; les taches
     trop loin du plan sont aberrantes et retirées ;
  2. définir le repère : plan de l'état plat -> z = 0, Z normal à l'échantillon, X le long
     de l'axe X de l'étalonnage projeté sur le plan ;
  3. servir de référence : les taches plates sont appariées avec celles de l'état serré,
     et le résultat est écrit comme une nouvelle reconstruction dont l'image 0 est l'état plat.

Organisation des dossiers (dossier_essai = <date>/essai1) :
    <essai>/video_extenso_left/photo_init_L.*     photo plate, caméra gauche (+ maskL.tiff)
    <essai>/video_extenso_right/photo_init_R.*    photo plate, caméra droite (+ maskR.tiff)
    <essai>/reconstruction/<source>/              X3d, Y3d, Z3d de l'essai, image 0 = état serré (entrée)
    <essai>/correction/<source>/etat_plat/        état plat : Lp_plat.npy, X3d/Y3d/Z3d.txt, figures
    <essai>/correction/<source>/                  figures et bilan de la correction
    <essai>/reconstruction/<source>_corrige/      image 0 = état plat, image 1 = état serré,
                                                  image k + 1 = image k de l'essai (sortie)

La sortie se traite ensuite comme toute reconstruction (déformation, anisotropie) en
choisissant la source <source>_corrige : les déformations sont alors calculées par rapport
à l'état plat.
"""
import glob
import json
import re
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial import cKDTree

from Pycaso.reconstruction_class import Detect3D


def _defauts_detection():
    """Valeurs par défaut de la détection (celles de DetectionSpots, importé seulement ici)."""
    from Pycaso.detection_spots_general import DetectionSpots
    d = DetectionSpots()
    return {"taille_min_pix": d.taille_min_pix, "taille_max_pix": d.taille_max_pix, "w_spots": d.w_spots,
            "seuils_recalage": d.seuils_recalage, "modele_recalage": d.modele_recalage}


class Correction:
    """État plat -> tri des taches, repère du plan, référence des déformations."""

    FICHIERS = ("X3d.txt", "Y3d.txt", "Z3d.txt")
    SOUS_DOSSIER_RECONSTRUCTION = Detect3D.SOUS_DOSSIER_SORTIE    # "reconstruction"
    SOUS_DOSSIER_SORTIE = "correction"
    SOUS_DOSSIER_PLAT = "etat_plat"
    CAMERAS = {"left": ("L", "maskL.tiff"), "right": ("R", "maskR.tiff")}   # dossier video_extenso_<cote>
    SUFFIXE = "_corrige"
    FICHIER_INFOS = "correction_infos.json"      # présent dans <source>_corrige : la marque d'une source corrigée
    SOURCE_DEFAUT = "Lpform_4"

    def __init__(self,
                 # --- Essai à corriger ---
                 date=None,                 # AAAA_MM_JJ ; None = aujourd'hui
                 dossier_essai=None,        # ex. <date>/essai1 ; None = <date>/essai1
                 source=None,               # reconstruction de l'essai (Lpform_4...) ; None = la première trouvée
                 # --- État plat : photos et reconstruction ---
                 prefixe_photo="photo_init",  # photos <prefixe>_L.* et <prefixe>_R.*
                 relire_plat=False,         # True : relit l'état plat déjà reconstruit (etat_plat/)
                 facteur_z=None,            # None = celui de la reconstruction de la source
                 taille_min_pix=None,       # aire min / max d'une tache (px) ; None = valeurs de DetectionSpots
                 taille_max_pix=None,
                 w_spots=None,              # taches blanches sur fond sombre ; None = DetectionSpots
                 seuils_recalage=None,      # appariement gauche/droite (px) ; None = DetectionSpots
                 modele_recalage=None,      # affine, homographie, polynome2, polynome3 ; None = DetectionSpots
                 # --- Tri des taches ---
                 seuil_plan=0.0,            # distance max au plan (mm) ; 0 = auto (nb_ecarts × écart robuste)
                 nb_ecarts=4.0,             # seuil auto = nb_ecarts × 1,4826 × médiane |distance|
                 # --- Appariement plat <-> serré ---
                 seuil_appariement=0.0,     # distance max (mm) après recalage ; 0 = auto (0,4 × espacement des taches)
                 degre_recalage=3,          # degré du champ de déplacement plat -> serré (dans le plan)
                 recherche_angle=15.0,      # alignement grossier : rotation max cherchée (degrés)
                 recherche_decalage=10.0,   # alignement grossier : décalage max cherché (mm)
                 iterations=8,              # itérations du recalage
                 # --- Résultats ---
                 enregistrer_figures=True,
                 afficher_figures=True):
        self.date = date or time.strftime("%Y_%m_%d")
        self.dossier_essai = dossier_essai or Detect3D.chemin_par_defaut(self.date)
        if source is None:
            dispo = self.sources_disponibles()
            source = dispo[0] if dispo else self.SOURCE_DEFAUT
        self.source = source
        self.prefixe_photo = prefixe_photo
        self.relire_plat = relire_plat
        self.facteur_z = facteur_z
        defauts = None
        for nom, val in (("taille_min_pix", taille_min_pix), ("taille_max_pix", taille_max_pix),
                         ("w_spots", w_spots), ("seuils_recalage", seuils_recalage),
                         ("modele_recalage", modele_recalage)):
            if val is None:
                defauts = defauts or _defauts_detection()
                val = defauts[nom]
            setattr(self, nom, val)
        self.seuils_recalage = tuple(float(s) for s in self.seuils_recalage)
        self.seuil_plan = float(seuil_plan)
        self.nb_ecarts = float(nb_ecarts)
        self.seuil_appariement = float(seuil_appariement)
        self.degre_recalage = int(degre_recalage)
        self.recherche_angle = float(recherche_angle)
        self.recherche_decalage = float(recherche_decalage)
        self.iterations = int(iterations)
        self.enregistrer_figures = enregistrer_figures
        self.afficher_figures = afficher_figures

    RESULTATS = ("bilan", "plat", "essai", "repere", "appariement", "alignement", "stereo")

    def parametres(self):
        """Paramètres sous forme de dictionnaire (pour affichage)."""
        return {k: v for k, v in vars(self).items() if k not in self.RESULTATS}

    # ----- chemins -----

    @classmethod
    def _complet(cls, dossier):
        return all((Path(dossier) / f).is_file() for f in cls.FICHIERS)

    def sources_disponibles(self):
        """Reconstructions de l'essai (hors sources déjà corrigées)."""
        d = Path(self.dossier_essai) / self.SOUS_DOSSIER_RECONSTRUCTION
        if not d.is_dir():
            return []
        return sorted(c.name for c in d.iterdir()
                      if c.is_dir() and self._complet(c) and not self.est_corrigee(c))

    @property
    def dossier_entree(self):
        return Path(self.dossier_essai) / self.SOUS_DOSSIER_RECONSTRUCTION / self.source

    @property
    def source_corrigee(self):
        return self.source + self.SUFFIXE

    @property
    def dossier_corrige(self):
        """<essai>/reconstruction/<source>_corrige : la reconstruction corrigée."""
        return Path(self.dossier_essai) / self.SOUS_DOSSIER_RECONSTRUCTION / self.source_corrigee

    @property
    def dossier_sortie(self):
        """<essai>/correction/<source> : figures et bilan."""
        return Path(self.dossier_essai) / self.SOUS_DOSSIER_SORTIE / self.source

    @property
    def dossier_plat(self):
        """<essai>/correction/<source>/etat_plat : reconstruction de l'état plat."""
        return self.dossier_sortie / self.SOUS_DOSSIER_PLAT

    def dossier_camera(self, cote):
        return Path(self.dossier_essai) / f"video_extenso_{cote}"

    def photo_plat(self, cote):
        """Photo plate d'une caméra ('left' ou 'right') : <prefixe>_L.* / _R.*, ou None."""
        lettre = self.CAMERAS[cote][0]
        motif = str(self.dossier_camera(cote) / f"{glob.escape(self.prefixe_photo)}_{lettre}.*")
        trouves = sorted(glob.glob(motif))
        return Path(trouves[0]) if trouves else None

    def masque(self, cote):
        return self.dossier_camera(cote) / self.CAMERAS[cote][1]

    def plat_deja_reconstruit(self):
        return self._complet(self.dossier_plat)

    @staticmethod
    def infos(dossier):
        """(nombre d'images, nombre de taches) de dossier/X3d.txt, sans tout charger ; None si absent."""
        f = Path(dossier) / "X3d.txt"
        if not f.is_file():
            return None
        with open(f) as fh:
            premiere = fh.readline()
            nb = 1 + sum(1 for ligne in fh if ligne.strip())
        return nb, len(premiere.split())

    @classmethod
    def est_corrigee(cls, dossier_source):
        """True si dossier_source a été produit par Correction (son image 0 est l'état plat)."""
        return (Path(dossier_source) / cls.FICHIER_INFOS).is_file()

    def methode_source(self):
        """(méthode, degré, facteur Z) de la reconstruction de la source.

        Lus dans reconstruction_infos.json s'il existe (écrit par Detect3D), sinon déduits du
        nom de la source (Lpform_4 -> Lagrange 4, Spform_555 -> Soloff 555, nZ_12 -> Zernike 12)
        avec le facteur Z par défaut de Detect3D. facteur_z, s'il est donné, est prioritaire.
        """
        infos = self.dossier_entree / Detect3D.FICHIER_INFOS
        if infos.is_file():
            with open(infos, encoding="utf-8") as fh:
                i = json.load(fh)
            methode, degre, fz = i["methode"], int(i["degre"]), float(i["facteur_z"])
        else:
            methode = degre = None
            for m, (modele, _, _) in Detect3D.METHODES.items():
                r = re.fullmatch(re.escape(modele.split("{}")[0]) + r"(\d+)", self.source)
                if r:
                    methode, degre = m, int(r.group(1))
            if methode is None:
                raise ValueError(f"Méthode de la source {self.source} inconnue "
                                 f"(attendu Lpform_<n>, Spform_<n> ou nZ_<n>)")
            fz = Detect3D().facteur_z
        return methode, degre, (fz if self.facteur_z is None else float(self.facteur_z))

    # ----- point d'entrée -----

    def lancer(self):
        """État plat, tri, repère, appariement, puis écriture de <source>_corrige. Renvoie le bilan (dict)."""
        if not self._complet(self.dossier_entree):
            raise FileNotFoundError(f"X3d.txt, Y3d.txt, Z3d.txt introuvables dans {self.dossier_entree}")
        if self.enregistrer_figures or self.afficher_figures:
            self.dossier_sortie.mkdir(parents=True, exist_ok=True)
        plat = self.etat_plat()
        plat = plat[np.isfinite(plat).all(axis=1)]
        essai = np.stack([np.loadtxt(self.dossier_entree / f, ndmin=2) for f in self.FICHIERS], axis=-1)
        print(f"État plat : {len(plat)} taches")
        print(f"Essai : {essai.shape[0]} images, {essai.shape[1]} taches ({self.dossier_entree})")

        # 1. plan de l'état plat et tri
        centre, R, dist, garde, seuil = self.ajuster_plan(plat)
        print(f"Plan : écart robuste {1.4826 * np.median(np.abs(dist[garde])):.3f} mm, seuil {seuil:.3f} mm ; "
              f"{(~garde).sum()} tache(s) hors plan retirée(s) sur {len(plat)}")

        # 2. repère du plan pour l'état plat et toutes les images de l'essai
        plat_r = self.vers_repere(plat[garde], centre, R)
        essai_r = self.vers_repere(essai, centre, R)

        # 3. appariement plat <-> serré (image 0 de l'essai)
        serre = essai_r[0]
        i_serre, i_plat, d_app, seuil_app, espacement = self.apparier(plat_r, serre)
        print(f"Appariement : {len(i_serre)} taches appariées (espacement {espacement:.2f} mm, "
              f"seuil {seuil_app:.2f} mm, écart résiduel médian {np.median(d_app):.3f} mm) ; "
              f"{np.isfinite(serre).all(axis=1).sum() - len(i_serre)} tache(s) de l'état serré sans "
              f"correspondant plat retirée(s)")

        # 4. reconstruction corrigée : image 0 = plat, puis l'essai
        corr = np.concatenate((plat_r[i_plat][None], essai_r[:, i_serre]), axis=0)   # (1 + images, taches, 3)
        self.dossier_corrige.mkdir(parents=True, exist_ok=True)
        for k, f in enumerate(self.FICHIERS):
            np.savetxt(self.dossier_corrige / f, corr[..., k])

        self.plat, self.essai, self.repere = plat, essai, (centre, R)
        self.appariement = {"i_serre": i_serre, "i_plat": i_plat, "distance": d_app,
                            "plat_r": plat_r, "serre": serre, "garde": garde, "dist_plan": dist}
        flambement = corr[1, :, 2]
        self.bilan = {
            "source": self.source, "photos_plat": [str(self.photo_plat(c)) for c in self.CAMERAS],
            "reconstruction_plat": self.stereo,
            "taches_plat": int(len(plat)), "taches_hors_plan": int((~garde).sum()),
            "seuil_plan_mm": float(seuil), "ecart_plan_mm": float(1.4826 * np.median(np.abs(dist[garde]))),
            "taches_essai": int(essai.shape[1]), "taches_appariees": int(len(i_serre)),
            "espacement_mm": float(espacement), "seuil_appariement_mm": float(seuil_app),
            "alignement_grossier": self.alignement,
            "ecart_appariement_median_mm": float(np.median(d_app)),
            "flambement_z_min_mm": float(np.nanmin(flambement)), "flambement_z_max_mm": float(np.nanmax(flambement)),
            "centre_plan": centre.tolist(), "repere_lignes_ex_ey_ez": R.tolist(),
            "images": "0 = état plat, 1 = état serré (image 0 de l'essai), k + 1 = image k de l'essai",
            "indices_essai": i_serre.tolist(),
        }
        with open(self.dossier_corrige / self.FICHIER_INFOS, "w", encoding="utf-8") as fh:
            json.dump(self.bilan, fh, indent=1, ensure_ascii=False)
        print(f"Flambement au serrage : z de {self.bilan['flambement_z_min_mm']:.2f} à "
              f"{self.bilan['flambement_z_max_mm']:.2f} mm")
        print(f"Reconstruction corrigée : {self.dossier_corrige} ({corr.shape[0]} images, {corr.shape[1]} taches)"
              f"\n  -> choisir la source « {self.source_corrigee} » pour la déformation et l'anisotropie")

        if self.enregistrer_figures or self.afficher_figures:
            self.tracer_plan()
            self.tracer_appariement()
            self.tracer_flambement(corr)
        return self.bilan

    # ----- état plat : détection, appariement gauche/droite, 3D -----

    def etat_plat(self):
        """Points 3D (taches, 3) de l'état plat : relus (relire_plat) ou reconstruits depuis les photos."""
        if self.relire_plat:
            if not self.plat_deja_reconstruit():
                raise FileNotFoundError(f"Pas d'état plat déjà reconstruit dans {self.dossier_plat} : "
                                        "décocher « relire l'état plat »")
            P = np.column_stack([np.loadtxt(self.dossier_plat / f, ndmin=2)[0] for f in self.FICHIERS])
            fichier = self.dossier_plat / "etat_plat_infos.json"
            self.stereo = json.load(open(fichier, encoding="utf-8")) if fichier.is_file() else {}
            print(f"État plat relu : {self.dossier_plat}")
            return P
        return self.reconstruire_plat()

    def reconstruire_plat(self):
        """Détection (SuiviTaches), appariement (AppariementStereo) et 3D (Detect3D) de la photo plate."""
        from Pycaso.detection_spots_suivi import SuiviTaches
        from Pycaso.detection_spots_appariemment import AppariementStereo

        manquants = [f"{self.dossier_camera(c)}/{self.prefixe_photo}_{l}.*" for c, (l, _) in self.CAMERAS.items()
                     if self.photo_plat(c) is None]
        manquants += [str(self.masque(c)) for c in self.CAMERAS if not self.masque(c).is_file()]
        if manquants:
            raise FileNotFoundError("Fichiers de l'état plat introuvables :\n  " + "\n  ".join(manquants))
        methode, degre, fz = self.methode_source()
        rec = Detect3D(date=self.date, dossier_essai=self.dossier_essai, methode=methode, degre=degre)
        constantes = rec.charger_constantes()          # avant la détection : prévient tout de suite si absent

        # 1. taches de chaque caméra (centres : ligne, colonne), comme la détection de l'essai
        suivi = SuiviTaches(20, self.taille_min_pix, self.taille_max_pix, 1, self.w_spots, False)
        taches = {}
        for cote in self.CAMERAS:
            image = suivi.lire_gris(str(self.photo_plat(cote)))
            masque = suivi.lire_gris(str(self.masque(cote))) / 255.0
            centres, _ = suivi.detecter_taches(image, masque)
            taches[cote] = (centres, image.shape[:2], image)
            print(f"État plat, caméra {cote} : {len(centres)} taches ({self.photo_plat(cote).name})")

        # 2. appariement gauche/droite, comme DetectionSpots.apparier (sans étalonnage)
        cL, cR = taches["left"][0], taches["right"][0]
        h, w = taches["right"][1]
        L = cL[:, [1, 0]]                                   # gauche (colonne, ligne)
        lr, cr = AppariementStereo.rotation_180(cR[:, 0], cR[:, 1], h, w)
        R_tourne = np.column_stack([cr, lr])
        R_brut = cR[:, [1, 0]]                              # droite brute (colonne, ligne), format de l'étalonnage
        app = AppariementStereo(None, seuils=self.seuils_recalage, modele=self.modele_recalage)
        ri, ci, residus, R_recale = app.apparier_sans_etalonnage(L, R_tourne)
        if len(ri) == 0:
            raise RuntimeError("Aucune paire gauche/droite sur l'état plat : augmenter les seuils de recalage")
        gauche, droite = L[ri], R_brut[ci]
        print(f"État plat : {len(ri)} paires gauche/droite (sur {len(L)} à gauche et {len(R_brut)} à droite), "
              f"résidu médian {np.median(residus):.2f} px")

        # 3. points 3D : même méthode, degré, étalonnage et facteur Z que la source
        x, y, z = rec.identifier(gauche, droite, constantes)
        P = np.column_stack([np.asarray(x, float), np.asarray(y, float), np.asarray(z, float) * fz])
        print(f"État plat reconstruit : {methode} {rec.tag}, facteur Z {fz:g}")

        d = self.dossier_plat
        d.mkdir(parents=True, exist_ok=True)
        np.save(d / "Lp_plat.npy", np.stack([gauche, droite])[None])     # même format que Lp_final.npy
        for k, f in enumerate(self.FICHIERS):
            np.savetxt(d / f, P[:, k][None])
        self.stereo = {"methode": methode, "degre": degre, "facteur_z": fz,
                       "etalonnage": str(rec.dossier_constantes()),
                       "taches_gauche": int(len(L)), "taches_droite": int(len(R_brut)),
                       "paires": int(len(ri)), "residu_median_px": float(np.median(residus)),
                       "photos": [str(self.photo_plat(c)) for c in self.CAMERAS]}
        with open(d / "etat_plat_infos.json", "w", encoding="utf-8") as fh:
            json.dump(self.stereo, fh, indent=1, ensure_ascii=False)
        if self.enregistrer_figures or self.afficher_figures:
            self.tracer_stereo(taches["left"][2], L, R_recale, ri, ci, residus)
        return P

    # ----- plan -----

    def ajuster_plan(self, P):
        """Plan robuste : (centre, R lignes ex ey ez, distances signées, taches gardées, seuil)."""
        garde = np.ones(len(P), dtype=bool)
        for _ in range(10):
            centre = P[garde].mean(axis=0)
            _, _, Vt = np.linalg.svd(P[garde] - centre, full_matrices=False)
            n = Vt[2]
            dist = (P - centre) @ n
            ecart = 1.4826 * np.median(np.abs(dist[garde]))
            seuil = self.seuil_plan or max(self.nb_ecarts * ecart, 1e-3)
            nouveau = np.abs(dist) <= seuil
            if np.array_equal(nouveau, garde):
                break
            garde = nouveau
        # repère : ez normal, orienté comme l'axe Z de l'étalonnage ; ex = X projeté sur le plan
        if n[2] < 0:
            n = -n
        ex = np.array([1.0, 0, 0]) - n[0] * n
        if np.linalg.norm(ex) < 1e-6:
            ex = np.array([0, 1.0, 0]) - n[1] * n
        ex /= np.linalg.norm(ex)
        ey = np.cross(n, ex)
        R = np.vstack((ex, ey, n))
        dist = (P - centre) @ n
        return centre, R, dist, np.abs(dist) <= seuil, seuil

    @staticmethod
    def vers_repere(P, centre, R):
        """Coordonnées dans le repère du plan (dernier axe = x, y, z) ; les NaN restent NaN."""
        return (P - centre) @ R.T

    # ----- appariement -----

    @staticmethod
    def _monomes(p, centre, echelle, degre):
        """Base polynomiale x^i y^j (i + j ≤ degre) sur des coordonnées centrées réduites."""
        x, y = ((p - centre) / echelle).T
        return np.column_stack([x ** i * y ** (k - i) for k in range(degre + 1) for i in range(k + 1)])

    def aligner(self, p, s, espacement):
        """Alignement grossier plat -> serré : (angle en degrés, centre de rotation, translation, score).

        Pour chaque rotation de -recherche_angle à +recherche_angle, chaque tache plate (un
        échantillon) vote pour les translations qui l'amènent sur une tache serrée à moins de
        recherche_decalage ; la rotation et la translation qui recueillent le plus de votes
        gagnent. Insensible aux taches manquantes et au motif aléatoire des taches.
        """
        rng = np.random.default_rng(0)
        ech = p[rng.choice(len(p), min(400, len(p)), replace=False)]
        cp = p.mean(axis=0)
        t0 = np.median(s, axis=0) - np.median(p, axis=0)
        arbre = cKDTree(s)
        case = espacement / 4
        nb_cases = int(np.ceil(2 * self.recherche_decalage / case)) + 1
        pas_angle = np.degrees(case / max(np.ptp(p, axis=0).max() / 2, 1e-9))     # ~ case au bord
        angles = np.arange(-self.recherche_angle, self.recherche_angle + pas_angle / 2, max(pas_angle, 0.05))
        meilleur = (-1, 0.0, t0)
        for a in angles:
            c, sn = np.cos(np.radians(a)), np.sin(np.radians(a))
            q = (ech - cp) @ np.array([[c, sn], [-sn, c]]) + cp + t0
            voisins = arbre.query_ball_point(q, self.recherche_decalage)
            diffs = np.concatenate([s[v] - qi for qi, v in zip(q, voisins) if v] or [np.zeros((0, 2))])
            if not len(diffs):
                continue
            k = np.floor((diffs + self.recherche_decalage) / case).astype(int)
            k = k[(k >= 0).all(axis=1) & (k < nb_cases).all(axis=1)]
            hist = np.bincount(k[:, 0] * nb_cases + k[:, 1], minlength=nb_cases * nb_cases).reshape(nb_cases, nb_cases)
            # somme sur 3x3 cases : robuste au bruit et à une légère déformation
            lisse = sum(np.roll(np.roll(hist, i, 0), j, 1) for i in (-1, 0, 1) for j in (-1, 0, 1))
            m = np.unravel_index(np.argmax(lisse), lisse.shape)
            if lisse[m] > meilleur[0]:
                t = t0 + (np.array(m) + 0.5) * case - self.recherche_decalage
                meilleur = (int(lisse[m]), a, t)
        score, a, t = meilleur
        return a, cp, t, score / len(ech)

    def apparier(self, plat, serre):
        """Apparie les taches plates et serrées dans le plan (x, y).

        Le serrage déplace les taches dans le plan (flambement, glissement, rotation dans les
        mors). On recale l'état plat sur l'état serré par un champ de déplacement polynomial
        (affine aux premières itérations, puis de degré degre_recalage), ajusté de façon robuste
        sur les appariements sûrs : plus proches voisins mutuels nettement plus proches que le
        deuxième voisin ; les appariements qui s'écartent du champ sont écartés à chaque passe.
        Renvoie (indices serré, indices plat, distances résiduelles, seuil, espacement).
        """
        ok = np.isfinite(serre).all(axis=1)
        idx_s = np.nonzero(ok)[0]
        p, s = plat[:, :2], serre[ok, :2]
        arbre_s = cKDTree(s)
        espacement = float(np.median(cKDTree(p).query(p, k=2)[0][:, 1]))
        seuil = self.seuil_appariement or 0.4 * espacement
        centre, echelle = p.mean(axis=0), p.std(axis=0).max()

        angle, cp, t, score = self.aligner(p, s, espacement)          # départ : alignement grossier
        c, sn = np.cos(np.radians(angle)), np.sin(np.radians(angle))
        deplace = (p - cp) @ np.array([[c, sn], [-sn, c]]) + cp + t
        self.alignement = {"angle_deg": float(angle), "translation_mm": t.tolist(), "score": float(score)}
        print(f"Alignement grossier : rotation {angle:.2f}°, translation ({t[0]:.2f}, {t[1]:.2f}) mm, "
              f"{100 * score:.0f} % des taches retrouvées")
        for it in range(self.iterations):
            d, j = arbre_s.query(deplace, k=2)
            mutuel = cKDTree(deplace).query(s[j[:, 0]])[1] == np.arange(len(p))
            sur = mutuel & (d[:, 0] < 0.6 * d[:, 1])
            degre = 1 if it < 2 else self.degre_recalage
            A = self._monomes(p, centre, echelle, degre)
            if sur.sum() < 3 * A.shape[1]:
                break
            u = s[j[:, 0]] - p
            garde = sur.copy()
            for _ in range(5):                       # moindres carrés robustes (élagage à 3 écarts)
                coef = np.linalg.lstsq(A[garde], u[garde], rcond=None)[0]
                res = np.linalg.norm(A @ coef - u, axis=1)
                ecart = 1.4826 * np.median(res[garde])
                nouveau = sur & (res <= max(3 * ecart, 1e-3))
                if np.array_equal(nouveau, garde):
                    break
                garde = nouveau
            deplace = p + A @ coef

        d, j = arbre_s.query(deplace, k=2)
        retour = cKDTree(deplace).query(s[j[:, 0]])[1]
        bon = (retour == np.arange(len(p))) & (d[:, 0] <= seuil)
        i_plat = np.nonzero(bon)[0]
        i_serre = idx_s[j[bon, 0]]
        ordre = np.argsort(i_serre)                      # garder l'ordre des taches de l'essai
        return i_serre[ordre], i_plat[ordre], d[bon, 0][ordre], seuil, espacement

    # ----- figures -----

    def _finir_figure(self, fig, nom):
        if self.enregistrer_figures:
            fig.savefig(self.dossier_sortie / nom)
        if self.afficher_figures:
            plt.show()
        plt.close(fig)

    def tracer_stereo(self, image, L, R_recale, ri, ci, residus):
        """État plat : taches appariées gauche/droite sur la photo gauche, et résidus."""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6.5), layout="constrained",
                                       gridspec_kw={"width_ratios": (1.4, 1)})
        ax1.imshow(image, cmap="gray")
        ok = np.zeros(len(L), bool); ok[ri] = True
        ax1.scatter(*L[~ok].T, s=10, c="tab:orange", label=f"non appariées ({(~ok).sum()})")
        ax1.scatter(*L[ok].T, s=10, c="tab:blue", label=f"appariées ({ok.sum()})")
        for i, j in zip(ri, ci):
            ax1.plot([L[i, 0], R_recale[j, 0]], [L[i, 1], R_recale[j, 1]], "r-", lw=0.6)
        ax1.set_title(f"État plat, caméra gauche ({self.prefixe_photo}_L)"); ax1.legend(loc="lower left")
        ax1.set_axis_off()
        ax2.hist(residus, bins=30, range=(0, self.seuils_recalage[-1]), color="tab:blue")
        ax2.axvline(np.median(residus), color="k", ls="--", lw=1, label=f"médiane {np.median(residus):.2f} px")
        ax2.set_xlabel("résidu après recalage (px)"); ax2.set_ylabel("nombre de paires")
        ax2.set_title("Appariement gauche / droite de l'état plat"); ax2.legend()
        if self.enregistrer_figures:
            fig.savefig(self.dossier_plat / "appariement_stereo_plat.png", dpi=120)
        if self.afficher_figures:
            plt.show()
        plt.close(fig)

    def tracer_plan(self):
        """État plat : distance au plan ajusté, taches retirées en rouge."""
        a = self.appariement
        P = self.vers_repere(self.plat, *self.repere)
        garde, dist = a["garde"], a["dist_plan"]
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6.5), layout="constrained")
        lim = np.nanpercentile(np.abs(dist[garde]), 99) or 1
        sc = ax1.scatter(P[garde, 0], P[garde, 1], c=dist[garde], cmap="coolwarm", vmin=-lim, vmax=lim, s=8)
        ax1.scatter(P[~garde, 0], P[~garde, 1], marker="x", c="r", s=40,
                    label=f"hors plan : {(~garde).sum()} tache(s)")
        ax1.set_aspect("equal"); ax1.set_xlabel("x (mm)"); ax1.set_ylabel("y (mm)")
        ax1.set_title("État plat : distance au plan ajusté"); ax1.legend(loc="upper right")
        fig.colorbar(sc, ax=ax1, label="distance au plan (mm)")
        ax2.hist(dist, bins=80, color="0.6")
        ax2.axvline(self.bilan["seuil_plan_mm"], c="r"); ax2.axvline(-self.bilan["seuil_plan_mm"], c="r")
        ax2.set_yscale("log"); ax2.set_xlabel("distance au plan (mm)"); ax2.set_ylabel("nombre de taches")
        ax2.set_title(f"Seuil ± {self.bilan['seuil_plan_mm']:.3f} mm (écart robuste {self.bilan['ecart_plan_mm']:.3f} mm)")
        self._finir_figure(fig, "Plan_etat_plat.png")

    def tracer_appariement(self):
        """Déplacements dans le plan entre l'état plat et l'état serré (taches appariées)."""
        a = self.appariement
        p = a["plat_r"][a["i_plat"]]
        s = a["serre"][a["i_serre"]]
        u = s - p
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6.5), layout="constrained")
        tout = a["serre"][np.isfinite(a["serre"]).all(axis=1)]
        ax1.scatter(tout[:, 0], tout[:, 1], s=3, c="0.8", label="état serré (toutes)")
        pas = max(1, len(p) // 1500)
        q = ax1.quiver(p[::pas, 0], p[::pas, 1], u[::pas, 0], u[::pas, 1], np.hypot(u[::pas, 0], u[::pas, 1]),
                       angles="xy", scale_units="xy", scale=1, cmap="viridis", width=0.002)
        fig.colorbar(q, ax=ax1, label="déplacement dans le plan (mm)")
        ax1.set_aspect("equal"); ax1.set_xlabel("x (mm)"); ax1.set_ylabel("y (mm)")
        ax1.set_title(f"Plat -> serré : {len(p)} taches appariées (flèches à l'échelle)")
        ax1.legend(loc="upper right")
        ax2.hist(a["distance"], bins=60, color="0.6")
        ax2.axvline(self.bilan["seuil_appariement_mm"], c="r")
        ax2.set_xlabel("écart résiduel après recalage (mm)"); ax2.set_ylabel("nombre de taches")
        ax2.set_title(f"Écart médian {self.bilan['ecart_appariement_median_mm']:.3f} mm "
                      f"(espacement des taches {self.bilan['espacement_mm']:.2f} mm)")
        self._finir_figure(fig, "Appariement_plat_serre.png")

    def tracer_flambement(self, corr):
        """État serré dans le repère du plan : z = flambement au serrage."""
        x, y, z = corr[1, :, 0], corr[1, :, 1], corr[1, :, 2]
        ok = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
        fig = plt.figure(figsize=(16, 9))
        ax = plt.axes(projection="3d")
        sc = ax.scatter3D(x[ok], y[ok], z[ok], c=z[ok], cmap="viridis", s=4)
        ax.set_xlabel("x (mm)"); ax.set_ylabel("y (mm)"); ax.set_zlabel("z (mm)")
        ax.set_box_aspect((1, 1, 0.4))
        fig.colorbar(sc, ax=ax, shrink=0.5, aspect=5, label="z / plan de l'état plat (mm)")
        plt.title(f"{self.source} - état serré dans le repère de l'état plat (flambement au serrage)")
        self._finir_figure(fig, "Flambement_serrage.png")