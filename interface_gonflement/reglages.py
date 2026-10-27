"""Paramètres par défaut de l'interface et sauvegarde/chargement JSON.

Les valeurs par défaut reprennent celles des scripts du dépôt
(alicat_flow_crappy_V3.py, calib_crappy_V2.py, Pycaso/calibration_gui.py).
"""

import copy
import json
from pathlib import Path

DOSSIER_INTERFACE = Path(__file__).resolve().parent
RACINE_DEPOT = DOSSIER_INTERFACE.parent
FICHIER_REGLAGES = DOSSIER_INTERFACE / "reglages_utilisateur.json"

DEFAUTS = {
    "materiel": {
        "simulation": False,              # True : aucun matériel, ballon simulé
        "theme": "sombre",                # sombre | clair
        "port_alicat": "/dev/ttyUSB1",
        "baud_alicat": 9600,
        "pression_relative": False,       # soustrait la pression lue à l'ouverture
        "pleine_echelle": 1000.0,         # mL/min correspondant à cmd = 1
        "port_imprimante": "/dev/ttyACM0",
        "url_ftdi": "ftdi://ftdi:232:FTU7DIHC/1",
        "sn_droite": "14482450",
        "sn_gauche": "32482550",
        "expo_droite": 41389,             # µs
        "expo_gauche": 31740,             # µs
        "taille_image": 2048,
        "dossier_racine": "../../Expériences",
        "port_udp_donnees": 50555,
        "port_udp_commandes": 50556,
    },
    "essai": {
        "echantillon": "Pro_Grip",
        "dossier": "",                    # vide = <racine>/<date>/<échantillon>
        "mode": "debit",                  # "debit" | "pression" | "deformation"
        "freq_cam": 2.5,                  # Hz, déclenchement FT232R
        "sauver_images": True,
        "graphers_crappy": False,         # fenêtres Grapher de crappy en plus
        "pression_max": 1500.0,           # coupure sécurité (unité du débitmètre)
        "duree_max": 1800.0,              # s
        "debit_max": 200.0,               # mL/min, saturation de la commande
        "vitesse_cmd_max": 100.0,         # mL/min par s, limite de variation
        "arret_auto": True,               # arrête l'essai à la fin du profil
        "debit": {
            "consigne": 13.2,             # mL/min
            "duree_rampe": 20.0,          # s, 0 -> consigne
            "attente": 2.0,               # s à débit nul avant la rampe
            "duree_palier": 0.0,          # s, 0 = jusqu'à l'arrêt
        },
        "pression": {
            "consigne": 1111.0,
            "vitesse": 1.4,               # unité de pression / s
            "duree_palier": 0.0,
            "kp": 5.0,                    # mL/min par unité de pression
            "ki": 0.5,                    # mL/min par (unité de pression . s)
        },
        "deformation": {
            "source": "3D",               # "3D" (stéréo Pycaso) | "2D" (VideoExtenso)
            "composante": "toutes",       # exx | eyy | moyenne | max | toutes
            "camera": "moyenne",          # droite | gauche | moyenne
            "eps_max": 15.0,              # %
            "vitesse": 0.02,              # %/s
            "duree_palier": 0.0,
            "kp": 20.0,                   # mL/min par %
            "ki": 2.0,                    # mL/min par (% . s)
            "kff": 0.0,                   # mL/min par (%/s), anticipation
            "timeout_mesure": 5.0,        # s sans mesure -> débit coupé
            "methode_3d": "Zernike",      # Zernike | Lagrange
            "pform": 12,                  # lu dans le nom du dossier nZ_<degré>
            "fichier_constantes": "",     # results_calib/nZ_<degré>/A_Zernike.npy
            "rotation_droite": True,      # caméra droite en miroir (180°)
        },
    },
    "calibration": {
        "z_depart": 70.0,
        "pas_z": 2.0,
        "z_fin": 32.0,                    # dernière hauteur photographiée (incluse)
        "nom_essai": "Mvt_Rigide",        # <racine>/<date>/<nom>/Mesure, comme calib_crappy_V2
        "temps_plan": 0.0,                # s, 0 = calcul auto (comme calib_crappy_V2)
        "expo_droite": 41389,
        "expo_gauche": 28757,
        "graphe_hauteur": True,           # Grapher de la position du plateau
        "z_reglage": 70.0,                # hauteur pour "Aller à Z"
        # comme Pycaso/calibration_gui.py
        "date": "",                       # vide = aujourd'hui (AAAA_MM_JJ)
        "dossier_images": "",             # vide = <racine>/<date>/<nom>/Mesure
        "methode": "Lagrange",
        "pform": "4",
        "iterations": 10,
        "deplacer_metadata": False,
        "afficher_3d": True,
    },
}


def fusion(base, ajout):
    """Fusion récursive : les clés de `ajout` écrasent celles de `base`."""
    out = copy.deepcopy(base)
    for k, v in (ajout or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = fusion(out[k], v)
        elif k in out:
            out[k] = v
    return out


def charger(fichier=FICHIER_REGLAGES):
    try:
        with open(fichier, encoding="utf-8") as f:
            return fusion(DEFAUTS, json.load(f))
    except (OSError, ValueError):
        return copy.deepcopy(DEFAUTS)


def sauver(reglages, fichier=FICHIER_REGLAGES):
    with open(fichier, "w", encoding="utf-8") as f:
        json.dump(reglages, f, indent=2, ensure_ascii=False)


def dossier_unique(base):
    """Comme get_unique_save_path de calib_crappy_V2 : base, puis base_00001…"""
    base = Path(base)
    if not base.exists() or not any(base.iterdir()):
        base.mkdir(parents=True, exist_ok=True)
        return base
    i = 1
    while True:
        p = Path(f"{base}_{i:05d}")
        if not p.exists() or not any(p.iterdir()):
            p.mkdir(parents=True, exist_ok=True)
            return p
        i += 1


def z_liste(z_depart, z_fin, pas_z):
    """Hauteurs de calibration de z_depart à z_fin (inclus) par pas de |pas_z|,
    en descendant si z_fin < z_depart. 70, 32, 2 -> 70, 68, ..., 32 (20 plans),
    soit les plans de calib_crappy_V2 (range(70, 30, -2))."""
    pas = abs(float(pas_z))
    if pas == 0:
        raise ValueError("le pas doit être non nul")
    sens = -1 if z_fin < z_depart else 1
    n = int(abs(z_fin - z_depart) / pas + 1e-9) + 1
    z = [round(z_depart + sens * pas * i, 6) for i in range(n)]
    return [int(v) if float(v).is_integer() else v for v in z]


def zl(cal):
    """z_liste à partir de la section « calibration » des réglages."""
    return z_liste(cal["z_depart"], cal["z_fin"], cal["pas_z"])


def degre_depuis_chemin(fichier, defaut=None):
    """nZ_12/A_Zernike.npy -> 12 ; Lpform_4/L_constants.npy -> 4."""
    import re
    for part in reversed(Path(fichier).parts):
        m = re.fullmatch(r"(?:nZ|Lpform)_(\d+)", part)
        if m:
            return int(m.group(1))
    return defaut


def dossier_base_essai(cfg, date):
    """Dossier choisi dans l'interface, sinon <racine>/<date>/<échantillon>.
    Les données vont dans <ce dossier>/Mesure (puis Mesure_00001, ...)."""
    ess = cfg["essai"]
    if ess.get("dossier", "").strip():
        return Path(ess["dossier"].strip())
    return Path(cfg["materiel"]["dossier_racine"]) / date / ess["echantillon"]
