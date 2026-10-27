"""Calibration stéréo : acquisition des images de la mire ChArUco, puis calcul.

  python lancer_calibration.py acquisition config.json
      Reprend calib_crappy_V2.py : l'imprimante descend le plateau plan par plan
      (z_depart, z_depart - pas, ...) et le FT232R déclenche les deux caméras
      une fois le plateau arrivé. Les images vont dans
      <racine>/<date>/calib/video_extenso_left|right/ et la liste des hauteurs
      dans z_list.json.

  python lancer_calibration.py calcul config.json
      Lance la calibration Pycaso (Lagrange / Soloff / Zernike) sur un dossier
      d'images, comme 1_calibration.py mais sans repasser par sa fenêtre.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))
sys.path.insert(0, str(ICI))

from reglages import dossier_unique, z_liste  # noqa: E402

# crappy ne garde qu'une référence faible vers les blocs
_BLOCS = []


def acquisition(cfg):
    mat, cal = cfg["materiel"], cfg["calibration"]
    z = z_liste(cal["z_depart"], cal["pas_z"], cal["n_plans"])
    pas = abs(float(cal["pas_z"]))
    # temps entre deux plans : même règle que calib_crappy_V2 (>= 1 + distance/0.6)
    t_plan = float(cal["temps_plan"]) or int(1 + pas / 0.6)
    t_plan = max(t_plan, 2.0)

    date = time.strftime("%Y_%m_%d")
    dossier = dossier_unique(Path(mat["dossier_racine"]) / date / "calib")
    print(f"DOSSIER_CALIB={dossier.resolve()}", flush=True)
    with open(dossier / "z_list.json", "w") as f:
        json.dump(z, f)
    print(f"{len(z)} plans : {z[0]} -> {z[-1]} mm, {t_plan:.1f} s par plan "
          f"(~{len(z) * t_plan / 60:.1f} min)", flush=True)

    if mat["simulation"]:
        for i, zi in enumerate(z):
            time.sleep(min(t_plan, 0.3))
            print(f"[simulation] plan {i + 1}/{len(z)} : Z = {zi} mm, images prises",
                  flush=True)
        print("Acquisition simulée terminée")
        return

    import crappy
    import ft232R  # noqa: F401  enregistre Ft232r
    import moteur  # noqa: F401  enregistre Printer
    from calib_crappy_V2 import DualXiAPICamera

    r = subprocess.run(["sudo", "-n", "tee",
                        "/sys/module/usbcore/parameters/usbfs_memory_mb"],
                       input=b"0\n", capture_output=True)
    if r.returncode != 0:
        print("ATTENTION : mémoire USB non libérée (voir onglet Matériel)")

    ftdi = crappy.blocks.IOBlock("Ft232r", cmd_labels=["cmd"], spam=False,
                                 direction=0b00000100, URL=mat["url_ftdi"])
    cams = DualXiAPICamera(
        serial_right=mat["sn_droite"], serial_left=mat["sn_gauche"],
        save_folder_right=str(dossier / "video_extenso_right") + "/",
        save_folder_left=str(dossier / "video_extenso_left") + "/",
        exposure_right=int(cal["expo_droite"]), exposure_left=int(cal["expo_gauche"]),
        trigger="Hardware", timeout=100000)
    mot = crappy.blocks.Machine([{"type": "Printer", "mode": "position",
                                  "cmd_label": "pos", "position_label": "position",
                                  "speed": 100, "port": mat["port_imprimante"]}],
                                freq=50)
    gen_mot = crappy.blocks.Generator(
        path=[{"type": "Constant", "value": zi, "condition": f"delay={t_plan}"}
              for zi in z], cmd_label="pos")
    # déclenchement 1 s avant la fin de chaque plan, quand le plateau est arrivé
    gen_ft = crappy.blocks.Generator(
        [{"type": "Cyclic", "value1": 0, "condition1": f"delay={t_plan - 1}",
          "value2": 1, "condition2": "delay=1", "cycles": len(z)}],
        cmd_label="cmd")
    _BLOCS.extend([ftdi, cams, mot, gen_mot, gen_ft])

    crappy.link(gen_ft, ftdi)
    crappy.link(gen_mot, mot)
    crappy.start(no_raise=True)

    n_g = len(list((dossier / "video_extenso_left").glob("*.tiff")))
    n_d = len(list((dossier / "video_extenso_right").glob("*.tiff")))
    print(f"Images : gauche {n_g}, droite {n_d} (attendu {len(z)})")
    if n_g != len(z) or n_d != len(z):
        print("ATTENTION : nombre d'images différent du nombre de plans")


def calcul(cfg):
    cal = cfg["calibration"]
    dossier = Path(cal["dossier_images"])
    fichier_z = dossier / "z_list.json"
    if fichier_z.exists():
        with open(fichier_z) as f:
            z = json.load(f)
        print(f"Hauteurs lues dans {fichier_z}")
    else:
        z = z_liste(cal["z_depart"], cal["pas_z"], cal["n_plans"])
    print(f"z_list : {z}", flush=True)

    import numpy as np
    from Pycaso.calibration_class import Calibration

    date = dossier.parent.name if dossier.parent.name[:2] == "20" else \
        time.strftime("%Y_%m_%d")
    params = {"date": date, "path_images": str(dossier),
              "z_list": np.asarray(z), "show_plot": bool(cal["afficher_3d"])}
    calib = Calibration.from_params(params)
    if cal["deplacer_metadata"]:
        calib.move_metadata()
    print(f"Calibration {cal['methode']} (forme {cal['pform']}, "
          f"{cal['iterations']} itérations)...", flush=True)
    # comme Pycaso/calibration_gui : la forme est un entier (ex. 332 pour Soloff)
    calib.run(cal["methode"], int(cal["pform"]), int(cal["iterations"]))
    print(f"Résultats dans {Calibration.results_dir_for(dossier)}")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("acquisition", "calcul"):
        sys.exit("usage : python lancer_calibration.py acquisition|calcul config.json")
    with open(sys.argv[2], encoding="utf-8") as f:
        config = json.load(f)
    {"acquisition": acquisition, "calcul": calcul}[sys.argv[1]](config)
