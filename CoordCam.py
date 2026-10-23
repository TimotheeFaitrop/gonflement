"""Coordonnées 2D des taches sur les deux caméras, appariées gauche/droite.

Remplace CoordCa10.py. Étapes :
  1. détection des taches sur la première image et suivi image par image (suivi_taches.py) ;
  2. appariement gauche/droite par l'étalonnage stéréo (appariement_stereo.py) ;
  3. enregistrement de Lp_final.npy, lu par detect3D_*.py.
Les paramètres sont dans config_coord.py.

Lancer depuis le dossier qui contient le dossier de date :
    python ..\\..\\gonflement-main\\CoordCam.py
"""
import os
import glob
import numpy as np
import matplotlib.pyplot as plt

import config_coord as cfg
from suivi_taches import suivre_camera
from appariement_stereo import rotation_180, apparier_stereo, construire_Lp

dossier = f"./{cfg.date}/{cfg.sample}/"
dossier_images = f"./{cfg.date}/{cfg.sample}/{cfg.mesure}/"


def coordonnees_camera(cote, deja_calcule):
    """Lit les coordonnées déjà enregistrées, ou les calcule (détection + suivi)."""
    lettre = cote[0]                                   # 'l' ou 'r'
    fichiers = [f"{dossier}all_px{lettre}.npy", f"{dossier}all_py{lettre}.npy",
                f"{dossier}points_spotted_{cote}.npy"]
    if deja_calcule:
        manquants = [f for f in fichiers if not os.path.isfile(f)]
        if manquants:
            raise FileNotFoundError(f"Fichiers absents (mettez {cote}_calculated à False) : {manquants}")
        print(f"Caméra {cote} : coordonnées relues")
        return (np.load(fichiers[0], allow_pickle=True).astype(float),
                np.load(fichiers[1], allow_pickle=True).astype(float),
                np.load(fichiers[2], allow_pickle=True).tolist())
    masque = "maskL.tiff" if cote == "left" else "maskR.tiff"
    dossier_cam = f"{dossier_images}video_extenso_{cote}/"
    if not os.path.isfile(dossier_cam + masque):
        raise FileNotFoundError(f"Masque absent : {dossier_cam + masque}")
    print(f"\nCaméra {cote} : détection et suivi des taches")
    px, py, nb = suivre_camera(dossier_cam, masque, f"{dossier}ROI_{cote}/", cfg)
    for f, val in zip(fichiers, (px, py, np.array(nb))):
        np.save(f, val)
    return px, py, nb


# 1. Coordonnées des taches sur chaque caméra (px = ligne, py = colonne)
all_pxl, all_pyl, nb_g = coordonnees_camera("left", cfg.gauche_calculated)
all_pxr, all_pyr, nb_d = coordonnees_camera("right", cfg.droite_calculated)

plt.figure()
plt.plot(nb_g, "o-", label="Caméra gauche")
plt.plot(nb_d, "s-", label="Caméra droite")
plt.ylim(bottom=0); plt.xlabel("Image"); plt.ylabel("Taches suivies"); plt.legend()
plt.savefig(f"{dossier}Number_points_spotted_{max(len(nb_g), len(nb_d))}_iterations.svg")
plt.close()

# 2. Appariement gauche/droite sur la première image
image_droite = sorted(glob.glob(f"{dossier_images}video_extenso_right/[0-9]*"))[0]
h, w = plt.imread(image_droite).shape[:2]
all_pxr_corr, all_pyr_corr = rotation_180(all_pxr, all_pyr, h, w)

vL = ~np.isnan(all_pxl[0]) & ~np.isnan(all_pyl[0])
vR = ~np.isnan(all_pxr[0]) & ~np.isnan(all_pyr[0])
idxL, idxR = np.where(vL)[0], np.where(vR)[0]
L = np.column_stack([all_pyl[0][vL], all_pxl[0][vL]])               # gauche (colonne, ligne)
R_tourne = np.column_stack([all_pyr_corr[0][vR], all_pxr_corr[0][vR]])
R_brut = np.column_stack([all_pyr[0][vR], all_pxr[0][vR]])          # format de l'étalonnage

L_constants = np.load(f"./{cfg.date}/Results_Calib/Lpform_{cfg.l_pform}/L_constants.npy")
ri, ci, ecarts, R_recale = apparier_stereo(L, R_brut, R_tourne, L_constants, cfg.l_pform,
                                           rayon=cfg.rayon_recherche, tol_z=cfg.tolerance_plan)
paires = [(int(idxL[i]), int(idxR[j])) for i, j in zip(ri, ci)]
print(f"Paires appariées : {len(paires)} (sur {vL.sum()} taches à gauche et {vR.sum()} à droite)")
print(f"Écart au plan (mm) : médian {np.median(ecarts):.2f}, max {ecarts.max():.2f}")

# Figure de vérification
fig, ax = plt.subplots(1, 3, figsize=(18, 6))
ok = np.zeros(len(L), bool); ok[ri] = True
ax[0].scatter(*L[~ok].T, s=12, c="tab:orange", label=f"non appariées ({(~ok).sum()})")
ax[0].scatter(*L[ok].T, s=12, c="tab:blue", label=f"appariées ({ok.sum()})")
ax[0].set_title("Caméra gauche, image 0")
for i, j in zip(ri, ci):
    ax[1].plot([L[i, 0], R_recale[j, 0]], [L[i, 1], R_recale[j, 1]], "r-", lw=0.6)
ax[1].scatter(*L.T, s=6, c="k")
ax[1].set_title("Paires (segments courts et réguliers attendus)")
for a in ax[:2]:
    a.invert_yaxis(); a.set_aspect("equal")
ax[0].legend(loc="lower left")
ax[2].hist(ecarts, bins=30, range=(0, cfg.tolerance_plan), color="tab:blue")
ax[2].axvline(np.median(ecarts), color="k", ls="--", lw=1, label=f"médiane {np.median(ecarts):.2f} mm")
ax[2].set_xlabel("Écart au plan de l'échantillon (mm)"); ax[2].set_ylabel("Nombre de paires")
ax[2].set_title(f"Écart au plan des paires retenues (limite {cfg.tolerance_plan} mm)")
ax[2].legend()
fig.tight_layout()
fig.savefig(f"{dossier}appariement.png", dpi=120)
if cfg.afficher_figures:
    plt.show()
plt.close(fig)

# 3. Enregistrement
Lp = construire_Lp(all_pxl, all_pyl, all_pxr, all_pyr, paires)
np.save(f"{dossier}Lp_final.npy", Lp)
np.save(f"{dossier}mapping.npy", dict(paires))
np.save(f"{dossier}all_pxr_corr.npy", all_pxr_corr)
np.save(f"{dossier}all_pyr_corr.npy", all_pyr_corr)
print(f"Lp_final.npy enregistré : {Lp.shape[0]} images, {Lp.shape[2]} points")
