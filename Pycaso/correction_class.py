"""Correction par l'état plat : appariement entre l'état non flambé et la 1re image de l'essai.

Au serrage des mors l'échantillon flambe : la première image de l'essai n'est plus l'état
initial. La paire de photos prise avant le serrage (photo_init_L / photo_init_R, dans
video_extenso_left / video_extenso_right) donne l'état plat. Cette étape se place entre la
détection des taches et la reconstruction :

    détection des taches (Lp_final.npy)
      -> correction : Lp_final_corrige.npy (image 0 = état plat)
      -> reconstruction avec « état plat » coché (reconstruction/<tag>_corrige)
      -> déformation, anisotropie : l'état initial est l'état plat

Pour chaque caméra :
  1. les taches de la photo plate sont détectées (SuiviTaches.detecter_taches, avec le
     masque de la caméra, comme pour l'essai) ;
  2. elles sont appariées avec les taches de la 1re image de l'essai (Lp_final.npy, image 0) :
     alignement grossier par vote (rotation + translation), recalage polynomial robuste, puis
     affinage local (déplacement médian des voisines sûres) qui suit le déplacement dû au
     flambement, et enfin plus proches voisins mutuels.
Une tache de l'essai est gardée si elle est retrouvée sur les deux photos plates. En option,
le couple (plate gauche, plate droite) obtenu doit aussi être une paire de l'appariement
gauche/droite des photos plates (AppariementStereo) : contrôle indépendant.

Fichiers (dans <essai>/appariemment_et_suivi/) :
    Lp_final.npy               taches de l'essai (entrée, inchangé)
    Lp_final_corrige.npy       image 0 = état plat, image k + 1 = image k de l'essai
    correction_infos.json      bilan ; recopié dans reconstruction/<tag>_corrige (marque d'une source corrigée)
    correction/                figures
"""
import glob
import json
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from scipy.spatial import cKDTree

from Pycaso.reconstruction_class import Detect3D


def _defauts_detection():
    """Valeurs par défaut de la détection (celles de DetectionSpots, importé seulement ici)."""
    from Pycaso.detection_spots_general import DetectionSpots
    d = DetectionSpots()
    return {"taille_min_pix": d.taille_min_pix, "taille_max_pix": d.taille_max_pix, "w_spots": d.w_spots,
            "seuils_recalage": d.seuils_recalage, "modele_recalage": d.modele_recalage}


class Correction:
    """Appariement état plat <-> 1re image de l'essai, sur les deux caméras, avant la reconstruction."""

    SOUS_DOSSIER = Detect3D.SOUS_DOSSIER_ENTREE          # "appariemment_et_suivi"
    SOUS_DOSSIER_FIGURES = "correction"
    FICHIER_LP = "Lp_final.npy"
    FICHIER_LP_CORRIGE = "Lp_final_corrige.npy"
    FICHIER_INFOS = "correction_infos.json"
    SUFFIXE = "_corrige"                                  # reconstruction/<tag>_corrige
    # cote : (lettre de la photo, masque, indice de la caméra dans Lp)
    CAMERAS = {"left": ("L", "maskL.tiff", 0), "right": ("R", "maskR.tiff", 1)}
    ITERATIONS_LOCALES = 10                               # affinage local après le recalage polynomial
    VOISINES_LOCALES = 12

    def __init__(self,
                 # --- Essai ---
                 dossier_essai=None,        # ex. ../../Expériences/2026_10_29/essai1 ; None = <aujourd'hui>/essai1
                 # --- Photos de l'état plat ---
                 prefixe_photo="photo_init",  # photos <prefixe>_L.* et <prefixe>_R.*
                 taille_min_pix=None,       # aire min / max d'une tache (px) ; None = valeurs de DetectionSpots
                 taille_max_pix=None,
                 w_spots=None,              # taches blanches sur fond sombre ; None = DetectionSpots
                 # --- Appariement plat <-> 1re image (sur chaque caméra, en pixels) ---
                 seuil_appariement=0.0,     # écart max (px) après recalage ; 0 = auto (0,4 × espacement des taches)
                 degre_recalage=3,          # degré du champ de déplacement plat -> 1re image
                 recherche_angle=15.0,      # alignement grossier : rotation max cherchée (degrés)
                 recherche_decalage=200.0,  # alignement grossier : décalage max cherché (px)
                 iterations=8,              # itérations du recalage
                 # --- Contrôle par l'appariement gauche/droite des photos plates ---
                 controle_stereo=True,
                 seuils_recalage=None,      # (px) ; None = DetectionSpots
                 modele_recalage=None,      # affine, homographie, polynome2, polynome3 ; None = DetectionSpots
                 # --- Figures ---
                 enregistrer_figures=True,
                 afficher_figures=True):
        self.dossier_essai = dossier_essai or Detect3D.chemin_par_defaut(time.strftime("%Y_%m_%d"))
        self.prefixe_photo = prefixe_photo
        defauts = None
        for nom, val in (("taille_min_pix", taille_min_pix), ("taille_max_pix", taille_max_pix),
                         ("w_spots", w_spots), ("seuils_recalage", seuils_recalage),
                         ("modele_recalage", modele_recalage)):
            if val is None:
                defauts = defauts or _defauts_detection()
                val = defauts[nom]
            setattr(self, nom, val)
        self.seuils_recalage = tuple(float(s) for s in self.seuils_recalage)
        self.seuil_appariement = float(seuil_appariement)
        self.degre_recalage = int(degre_recalage)
        self.recherche_angle = float(recherche_angle)
        self.recherche_decalage = float(recherche_decalage)
        self.iterations = int(iterations)
        self.iterations_locales = self.ITERATIONS_LOCALES
        self.voisines_locales = self.VOISINES_LOCALES
        self.controle_stereo = controle_stereo
        self.enregistrer_figures = enregistrer_figures
        self.afficher_figures = afficher_figures

    RESULTATS = ("bilan", "Lp", "Lp_corrige", "cameras")

    def parametres(self):
        """Paramètres sous forme de dictionnaire (pour affichage)."""
        return {k: v for k, v in vars(self).items() if k not in self.RESULTATS}

    # ----- chemins -----

    @property
    def dossier(self):
        """<essai>/appariemment_et_suivi : Lp_final.npy (entrée) et Lp_final_corrige.npy (sortie)."""
        return Path(self.dossier_essai) / self.SOUS_DOSSIER

    @property
    def fichier_Lp(self):
        return self.dossier / self.FICHIER_LP

    @property
    def fichier_Lp_corrige(self):
        return self.dossier / self.FICHIER_LP_CORRIGE

    @property
    def dossier_figures(self):
        return self.dossier / self.SOUS_DOSSIER_FIGURES

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

    @staticmethod
    def infos_Lp(fichier):
        """(nombre d'images, nombre de taches) d'un fichier Lp, ou None s'il n'existe pas."""
        if not Path(fichier).is_file():
            return None
        Lp = np.load(fichier, allow_pickle=True, mmap_mode="r")
        return Lp.shape[0], Lp.shape[2]

    @classmethod
    def est_corrigee(cls, dossier_source):
        """True si une reconstruction a été faite depuis Lp_final_corrige.npy (image 0 = état plat)."""
        return (Path(dossier_source) / cls.FICHIER_INFOS).is_file()

    # ----- point d'entrée -----

    def lancer(self):
        """Détection sur les photos plates, appariement avec la 1re image, écriture de Lp_final_corrige.npy.

        Renvoie le bilan (dict).
        """
        from Pycaso.detection_spots_suivi import SuiviTaches

        manquants = [] if self.fichier_Lp.is_file() else [f"{self.fichier_Lp} (lancer d'abord la détection des taches)"]
        for cote, (lettre, _, _) in self.CAMERAS.items():
            if self.photo_plat(cote) is None:
                manquants.append(f"{self.dossier_camera(cote)}/{self.prefixe_photo}_{lettre}.*")
            if not self.masque(cote).is_file():
                manquants.append(str(self.masque(cote)))
        if manquants:
            raise FileNotFoundError("Fichiers introuvables :\n  " + "\n  ".join(manquants))

        self.Lp = np.load(self.fichier_Lp, allow_pickle=True).astype(float)   # (images, 2, taches, 2)
        nb_images, _, nb_taches, _ = self.Lp.shape
        print(f"Essai : {nb_images} images, {nb_taches} taches ({self.fichier_Lp})")

        # 1. et 2. : chaque caméra, photo plate <-> 1re image
        suivi = SuiviTaches(20, self.taille_min_pix, self.taille_max_pix, 1, self.w_spots, False)
        self.cameras = {}
        correspondance = {}
        for cote, (lettre, _, k) in self.CAMERAS.items():
            image = suivi.lire_gris(str(self.photo_plat(cote)))
            masque = suivi.lire_gris(str(self.masque(cote))) / 255.0
            centres, _ = suivi.detecter_taches(image, masque)
            plat = centres[:, [1, 0]]                     # (colonne, ligne), comme Lp
            premiere = self.Lp[0, k]
            ok = np.isfinite(premiere).all(axis=1)
            i_essai, i_plat, ecarts, seuil, espacement, alignement = self.apparier(plat, premiere[ok])
            i_essai = np.nonzero(ok)[0][i_essai]
            correspondance[cote] = dict(zip(i_essai.tolist(), i_plat.tolist()))
            self.cameras[cote] = {"image": image, "plat": plat, "premiere": premiere, "i_essai": i_essai,
                                  "i_plat": i_plat, "ecarts": ecarts, "seuil": seuil,
                                  "espacement": espacement, "alignement": alignement}
            print(f"Caméra {cote} : {len(plat)} taches sur {self.photo_plat(cote).name} ; alignement "
                  f"{alignement['angle_deg']:.2f}°, ({alignement['translation_px'][0]:.0f}, "
                  f"{alignement['translation_px'][1]:.0f}) px ; {len(i_essai)} taches de la 1re image "
                  f"retrouvées sur {ok.sum()} (écart médian {np.median(ecarts):.2f} px, seuil {seuil:.1f} px)")
            if len(i_essai) < 0.8 * min(ok.sum(), len(plat)):
                print(f"  ⚠ peu de taches retrouvées sur la caméra {cote} : vérifier la figure ; si les taches "
                      "bougent beaucoup au serrage, augmenter le décalage cherché ou le degré du recalage")

        # taches de l'essai retrouvées sur les deux photos plates
        garde = [j for j in range(nb_taches) if j in correspondance["left"] and j in correspondance["right"]]
        rejet_stereo = 0
        if self.controle_stereo and garde:
            paires_plates = self.paires_stereo_plates()
            avant = len(garde)
            garde = [j for j in garde
                     if (correspondance["left"][j], correspondance["right"][j]) in paires_plates]
            rejet_stereo = avant - len(garde)
            print(f"Contrôle gauche/droite des photos plates : {len(paires_plates)} paires plates ; "
                  f"{rejet_stereo} tache(s) écartée(s) (incohérentes entre les deux caméras)")
            if rejet_stereo > 0.05 * avant:
                print("  ⚠ beaucoup de taches écartées par le contrôle : une caméra a probablement des "
                      "appariements faux (vérifier la figure). Les taches gardées restent sûres.")
        if not garde:
            raise RuntimeError("Aucune tache de l'essai retrouvée sur les deux photos plates : vérifier les "
                               "photos, ou augmenter la recherche initiale (rotation / décalage)")
        garde = np.array(garde)

        # 3. Lp corrigé : image 0 = état plat, puis l'essai (taches gardées, dans l'ordre de Lp_final)
        plat_L = self.cameras["left"]["plat"][[correspondance["left"][j] for j in garde]]
        plat_R = self.cameras["right"]["plat"][[correspondance["right"][j] for j in garde]]
        self.Lp_corrige = np.concatenate((np.stack((plat_L, plat_R))[None], self.Lp[:, :, garde]), axis=0)
        np.save(self.fichier_Lp_corrige, self.Lp_corrige)

        self.bilan = {
            "photos_plat": [str(self.photo_plat(c)) for c in self.CAMERAS],
            "taches_essai": int(nb_taches), "taches_gardees": int(len(garde)),
            "rejet_controle_stereo": int(rejet_stereo),
            "cameras": {c: {"taches_photo_plate": int(len(v["plat"])), "retrouvees": int(len(v["i_essai"])),
                            "ecart_median_px": float(np.median(v["ecarts"])), "seuil_px": float(v["seuil"]),
                            "espacement_px": float(v["espacement"]), "alignement": v["alignement"]}
                        for c, v in self.cameras.items()},
            "images": "0 = état plat, 1 = 1re image de l'essai (flambée), k + 1 = image k de l'essai",
            "indices_essai": garde.tolist(),
        }
        with open(self.dossier / self.FICHIER_INFOS, "w", encoding="utf-8") as fh:
            json.dump(self.bilan, fh, indent=1, ensure_ascii=False)
        print(f"Lp_final_corrige.npy : {self.Lp_corrige.shape[0]} images (0 = état plat), {len(garde)} taches "
              f"sur {nb_taches} ; {self.fichier_Lp_corrige}\n"
              "  -> reconstruction : cocher « état plat » (résultats dans reconstruction/<tag>_corrige)")

        if self.enregistrer_figures or self.afficher_figures:
            if self.enregistrer_figures:
                self.dossier_figures.mkdir(parents=True, exist_ok=True)
            self.tracer_appariement(garde, correspondance)
        return self.bilan

    # ----- appariement plat <-> 1re image (une caméra) -----

    @staticmethod
    def _monomes(p, centre, echelle, degre):
        """Base polynomiale x^i y^j (i + j ≤ degre) sur des coordonnées centrées réduites."""
        x, y = ((p - centre) / echelle).T
        return np.column_stack([x ** i * y ** (k - i) for k in range(degre + 1) for i in range(k + 1)])

    def aligner(self, p, s, espacement):
        """Alignement grossier plat -> 1re image : (angle en degrés, centre de rotation, translation, score).

        Pour chaque rotation de -recherche_angle à +recherche_angle, chaque tache plate (un
        échantillon) vote pour les translations qui l'amènent sur une tache de la 1re image à
        moins de recherche_decalage ; la rotation et la translation qui recueillent le plus de
        votes gagnent. Insensible aux taches manquantes et au motif aléatoire des taches.
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

    def apparier(self, plat, premiere):
        """Apparie les taches de la photo plate avec celles de la 1re image (mêmes pixels d'une caméra).

        Le flambement déplace les taches dans l'image : on recale l'état plat sur la 1re image par
        un champ de déplacement polynomial (affine aux premières itérations, puis de degré
        degre_recalage), ajusté de façon robuste sur les appariements sûrs : plus proches voisins
        mutuels nettement plus proches que le deuxième voisin. Renvoie (indices 1re image,
        indices plat, écarts résiduels, seuil, espacement, alignement grossier).
        """
        p, s = plat, premiere
        arbre_s = cKDTree(s)
        espacement = float(np.median(cKDTree(p).query(p, k=2)[0][:, 1]))
        seuil = self.seuil_appariement or 0.4 * espacement
        centre, echelle = p.mean(axis=0), p.std(axis=0).max()

        angle, cp, t, score = self.aligner(p, s, espacement)          # départ : alignement grossier
        c, sn = np.cos(np.radians(angle)), np.sin(np.radians(angle))
        deplace = (p - cp) @ np.array([[c, sn], [-sn, c]]) + cp + t
        alignement = {"angle_deg": float(angle), "translation_px": t.tolist(), "score": float(score)}

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

        # affinage local : chaque tache est prédite par le déplacement médian de ses voisines sûres
        # (suit un flambement de forme quelconque, qu'un polynôme global ne suit pas toujours)
        for _ in range(self.iterations_locales):
            d, j = arbre_s.query(deplace, k=2)
            mutuel = cKDTree(deplace).query(s[j[:, 0]])[1] == np.arange(len(p))
            sur = np.nonzero(mutuel & (d[:, 0] < 0.5 * d[:, 1]) & (d[:, 0] < 0.25 * espacement))[0]
            if len(sur) < self.voisines_locales:
                break
            u_sur = s[j[sur, 0]] - p[sur]
            _, vois = cKDTree(p[sur]).query(p, k=self.voisines_locales)
            nouveau = p + np.median(u_sur[vois], axis=1)
            if np.allclose(nouveau, deplace, atol=1e-3 * espacement):
                break
            deplace = nouveau

        d, j = arbre_s.query(deplace, k=2)
        retour = cKDTree(deplace).query(s[j[:, 0]])[1]
        bon = (retour == np.arange(len(p))) & (d[:, 0] <= seuil)
        i_plat = np.nonzero(bon)[0]
        i_s = j[bon, 0]
        ordre = np.argsort(i_s)
        return i_s[ordre], i_plat[ordre], d[bon, 0][ordre], seuil, espacement, alignement

    # ----- contrôle : appariement gauche/droite des photos plates -----

    def paires_stereo_plates(self):
        """Paires (indice plat gauche, indice plat droite) de l'appariement gauche/droite des photos plates.

        Même méthode que DetectionSpots (sans étalonnage) : droite tournée de 180°, recalage 2D.
        """
        from Pycaso.detection_spots_appariemment import AppariementStereo
        L = self.cameras["left"]["plat"]
        R = self.cameras["right"]["plat"]
        h, w = self.cameras["right"]["image"].shape[:2]
        lignes, colonnes = AppariementStereo.rotation_180(R[:, 1], R[:, 0], h, w)
        R_tourne = np.column_stack((colonnes, lignes))
        app = AppariementStereo(None, seuils=self.seuils_recalage, modele=self.modele_recalage)
        ri, ci, _, _ = app.apparier_sans_etalonnage(L, R_tourne)
        return set(zip(ri.tolist(), ci.tolist()))

    # ----- figures -----

    def tracer_appariement(self, garde, correspondance):
        """Pour chaque caméra : photo plate, taches plates, taches de la 1re image et liens."""
        fig, axes = plt.subplots(2, 2, figsize=(16, 14), layout="constrained",
                                 gridspec_kw={"height_ratios": (3, 1)})
        for col, (cote, v) in enumerate(self.cameras.items()):
            ax, ax_h = axes[0, col], axes[1, col]
            ax.imshow(v["image"], cmap="gray", alpha=0.6)
            ax.scatter(*v["plat"].T, s=8, c="tab:blue", label=f"photo plate ({len(v['plat'])})")
            prem = v["premiere"][np.isfinite(v["premiere"]).all(axis=1)]
            ax.scatter(*prem.T, s=10, c="tab:orange", marker="x", lw=0.7,
                       label=f"1re image, flambée ({len(prem)})")
            p = v["plat"][[correspondance[cote][j] for j in garde]]
            q = v["premiere"][garde]
            ax.add_collection(LineCollection(np.stack((p, q), axis=1), colors="r", linewidths=0.8,
                                             label=f"appariées ({len(garde)})"))
            ax.set_title(f"Caméra {cote} : photo plate → 1re image")
            ax.legend(loc="lower left", markerscale=2)
            ax.set_axis_off()
            dep = np.hypot(*(q - p).T)
            ax_h.hist(dep, bins=60, color="0.6")
            ax_h.set_xlabel("déplacement dans l'image entre la photo plate et la 1re image (px)")
            ax_h.set_ylabel("nombre de taches")
            ax_h.set_title(f"écart résiduel du recalage : médian {np.median(v['ecarts']):.2f} px "
                           f"(espacement des taches {v['espacement']:.1f} px)")
        if self.enregistrer_figures:
            fig.savefig(self.dossier_figures / "appariement_plat_premiere_image.svg", dpi=110)
        if self.afficher_figures:
            plt.show()
        plt.close(fig)