"""Calibration stéréo : acquisition des images de la mire ChArUco, puis calcul.

  python lancer_calibration.py acquisition config.json
      Reprend calib_crappy_V2.py : l'imprimante descend le plateau plan par plan
      (z_depart, z_depart - pas, ...) et le FT232R déclenche les deux caméras
      une fois le plateau arrivé. Les images vont dans <dossier images calib>/
      video_extenso_left|right/ (<racine>/<date>/calib par défaut, comme
      Pycaso/calibration_gui) ; la liste des hauteurs est notée dans z_list.json.

  python lancer_calibration.py calcul config.json
      Lance la calibration Pycaso (Lagrange / Soloff / Zernike) avec les mêmes
      paramètres que la fenêtre de 1_calibration.py (date, dossier, z départ,
      pas, nb plans, méthode, degré, itérations, options).
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
DOCUMENT = "hauteurs_calibration.txt"     # récapitulatif lisible
TABLEAU = "hauteurs_calibration.csv"      # même tableau, pour un tableur


def temps_par_plan(cal):
    """Même règle que calib_crappy_V2 : time_sync = int(1 + |pas| / 0.6)."""
    t = float(cal["temps_plan"]) or int(1 + abs(float(cal["pas_z"])) / 0.6)
    return max(t, 2.0)


def ecrire_document(dossier, cfg, statut):
    """Écrit la hauteur de départ, le pas et la hauteur de chaque plan (avec les
    images prises, si elles existent) dans le dossier de calibration."""
    mat, cal = cfg["materiel"], cfg["calibration"]
    dossier = Path(dossier)
    z = z_liste(cal["z_depart"], cal["pas_z"], cal["n_plans"])
    images = {}
    for cote in ("left", "right"):
        images[cote] = sorted(p.name for p in (dossier / f"video_extenso_{cote}").glob("*.tif*"))
    t = temps_par_plan(cal)
    n = lambda x: f"{float(x):g}"  # noqa: E731   70.0 -> 70
    lignes = [
        "CALIBRATION STÉRÉO — HAUTEURS DU PLATEAU",
        "=" * 44,
        f"Date de calibration      : {cal['date']}",
        f"Document écrit le        : {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Statut                   : {statut}",
        f"Dossier des images       : {dossier.resolve()}",
        "",
        f"Hauteur de départ        : {n(cal['z_depart'])} mm",
        f"Pas (descente par plan)  : {n(cal['pas_z'])} mm",
        f"Nombre de plans          : {cal['n_plans']}",
        f"Hauteur finale           : {z[-1]} mm",
        f"Plage couverte           : {z[0]} -> {z[-1]} mm ({n(abs(z[0] - z[-1]))} mm)",
        f"Temps par plan           : {t:.0f} s (vitesse plateau 100 mm/min)",
        f"Exposition gauche/droite : {cal['expo_gauche']} / {cal['expo_droite']} µs",
        f"Caméras gauche/droite    : {mat['sn_gauche']} / {mat['sn_droite']}",
        "Mire ChArUco             : 12 x 12 carrés de 7.5 mm",
        "",
        f"{'Plan':>4}  {'Z (mm)':>8}  {'Image gauche':<28}  Image droite",
        f"{'-' * 4}  {'-' * 8}  {'-' * 28}  {'-' * 28}",
    ]
    csv = ["plan;z_mm;image_gauche;image_droite"]
    for i, zi in enumerate(z):
        g = images["left"][i] if i < len(images["left"]) else "-"
        d = images["right"][i] if i < len(images["right"]) else "-"
        lignes.append(f"{i + 1:>4}  {zi:>8}  {g:<28}  {d}")
        csv.append(f"{i + 1};{zi};{g};{d}")
    if any(images.values()) and (len(images["left"]) != len(z) or len(images["right"]) != len(z)):
        lignes += ["", f"ATTENTION : {len(images['left'])} images à gauche et "
                       f"{len(images['right'])} à droite pour {len(z)} plans."]
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / DOCUMENT).write_text("\n".join(lignes) + "\n", encoding="utf-8")
    (dossier / TABLEAU).write_text("\n".join(csv) + "\n", encoding="utf-8")
    with open(dossier / "z_list.json", "w") as f:
        json.dump(z, f)
    print(f"Document des hauteurs : {dossier / DOCUMENT}", flush=True)


def acquisition(cfg):
    mat, cal = cfg["materiel"], cfg["calibration"]
    z = z_liste(cal["z_depart"], cal["pas_z"], cal["n_plans"])
    t_plan = temps_par_plan(cal)

    # même règle que get_unique_save_path de calib_crappy_V2 : dossier, puis dossier_00001...
    dossier = dossier_unique(Path(cal["dossier_images"]))
    print(f"DOSSIER_CALIB={dossier.resolve()}", flush=True)
    ecrire_document(dossier, cfg, "acquisition en cours")
    print(f"{len(z)} plans : {z[0]} -> {z[-1]} mm, {t_plan:.1f} s par plan "
          f"(~{len(z) * t_plan / 60:.1f} min)", flush=True)

    if mat["simulation"]:
        for i, zi in enumerate(z):
            time.sleep(min(t_plan, 0.3))
            print(f"[simulation] plan {i + 1}/{len(z)} : Z = {zi} mm, images prises",
                  flush=True)
        ecrire_document(dossier, cfg, "acquisition simulée (aucune image)")
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
    ecrire_document(dossier, cfg, "acquisition terminée")
    if n_g != len(z) or n_d != len(z):
        print("ATTENTION : nombre d'images différent du nombre de plans")


def calcul(cfg):
    cal = cfg["calibration"]
    dossier = Path(cal["dossier_images"])
    # z_list comme Pycaso/calibration_gui : z départ - pas * [0 .. nb plans - 1]
    z = z_liste(cal["z_depart"], cal["pas_z"], cal["n_plans"])
    print(f"z_list : {z}", flush=True)

    import numpy as np
    from Pycaso.calibration_class import Calibration

    params = {"date": cal["date"], "path_images": str(dossier),
              "z_list": np.asarray(z), "show_plot": bool(cal["afficher_3d"])}
    calib = Calibration.from_params(params)
    if cal["deplacer_metadata"]:
        calib.move_metadata()
    print(f"Calibration {cal['methode']} (forme {cal['pform']}, "
          f"{cal['iterations']} itérations)...", flush=True)
    # comme Pycaso/calibration_gui : la forme est un entier (ex. 332 pour Soloff)
    calib.run(cal["methode"], int(cal["pform"]), int(cal["iterations"]))
    print(f"Résultats dans {Calibration.results_dir_for(dossier)}")
    doc = dossier / DOCUMENT
    if doc.exists():
        with open(doc, "a", encoding="utf-8") as f:
            f.write(f"\nCalcul {time.strftime('%Y-%m-%d %H:%M')} : {cal['methode']}, "
                    f"degré {cal['pform']}, {cal['iterations']} itérations -> "
                    f"{Calibration.results_dir_for(dossier)}\n")


if __name__ == "__main__":
    actions = {"acquisition": acquisition, "calcul": calcul,
               "document": lambda c: ecrire_document(c["calibration"]["dossier_images"], c,
                                                     "écrit depuis l'interface")}
    if len(sys.argv) != 3 or sys.argv[1] not in actions:
        sys.exit("usage : python lancer_calibration.py acquisition|calcul|document config.json")
    with open(sys.argv[2], encoding="utf-8") as f:
        config = json.load(f)
    actions[sys.argv[1]](config)
