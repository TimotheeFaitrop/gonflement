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
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))
sys.path.insert(0, str(ICI))

from reglages import dossier_unique, zl  # noqa: E402

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
    z = zl(cal)
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
        f"Hauteur finale           : {n(cal['z_fin'])} mm",
        f"Nombre de plans          : {len(z)}",
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


def memoire_usb_liberee():
    try:
        return Path("/sys/module/usbcore/parameters/usbfs_memory_mb").read_text().strip() == "0"
    except OSError:
        return True   # pas de paramètre (autre système) : rien à faire


def acquisition(cfg):
    mat, cal = cfg["materiel"], cfg["calibration"]
    z = zl(cal)
    t_plan = temps_par_plan(cal)

    # <racine>/<date>/<nom de l'essai>/Mesure, comme ./<date>/Mvt_Rigide/Mesure de
    # calib_crappy_V2, puis Mesure_00001... s'il est déjà rempli (get_unique_save_path)
    dossier = dossier_unique(Path(mat["dossier_racine"]) / cal["date"] / cal["nom_essai"] / "Mesure")
    print(f"DOSSIER_CALIB={dossier.resolve()}", flush=True)
    ecrire_document(dossier, cfg, "acquisition en cours")
    print(f"{len(z)} plans : {z[0]} -> {z[-1]} mm, {t_plan:.1f} s par plan "
          f"(~{len(z) * t_plan / 60:.1f} min)", flush=True)

    if mat["simulation"]:
        import simulation
        simulation.images_mire(dossier, z, t_plan, afficher=cal.get("graphe_hauteur", True))
        ecrire_document(dossier, cfg, "acquisition simulée (images de synthèse)")
        print("Acquisition simulée terminée")
        return

    import crappy
    import ft232R  # noqa: F401  enregistre Ft232r
    import moteur  # noqa: F401  enregistre Printer
    from calib_crappy_V2 import DualXiAPICamera

    if not memoire_usb_liberee():
        print("ATTENTION : usbfs_memory_mb n'est pas à 0 : les caméras risquent de ne "
              "renvoyer aucune image (bouton « Libérer la mémoire USB »)", flush=True)

    ftdi = crappy.blocks.IOBlock("Ft232r", cmd_labels=["cmd"], spam=False,
                                 direction=0b00000100, URL=mat["url_ftdi"])
    cams = DualXiAPICamera(
        serial_right=mat["sn_droite"], serial_left=mat["sn_gauche"],
        save_folder_right=str(dossier / "video_extenso_right") + "/",
        save_folder_left=str(dossier / "video_extenso_left") + "/",
        exposure_right=int(cal["expo_droite"]), exposure_left=int(cal["expo_gauche"]),
        # délai d'une image : un plan + 5 s (100 s dans calib_crappy_V2, ce qui
        # bloquait le programme si une caméra ne recevait pas le déclenchement)
        trigger="Hardware", timeout=int((t_plan + 5) * 1000))
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
    if cal.get("graphe_hauteur", True):
        # comme calib_crappy_V2 : courbe de la hauteur du plateau pendant l'acquisition
        graph_mot = crappy.blocks.Grapher(("t(s)", "position"))
        _BLOCS.append(graph_mot)
        crappy.link(mot, graph_mot)
    crappy.start(no_raise=True)

    n_g = len(list((dossier / "video_extenso_left").glob("*.tiff")))
    n_d = len(list((dossier / "video_extenso_right").glob("*.tiff")))
    nettoyer_dossiers_cameras(dossier)     # metadata.csv hors des dossiers d'images
    print(f"Images : gauche {n_g}, droite {n_d} (attendu {len(z)}) dans {dossier}")
    ecrire_document(dossier, cfg, "acquisition terminée")
    if n_g == 0 and n_d == 0:
        print("ERREUR : aucune image enregistrée. Causes possibles : mémoire USB non "
              "libérée, câble de déclenchement FT232R, caméras ouvertes par un autre "
              "programme (xiCamTool), exposition trop longue.")
    elif n_g != len(z) or n_d != len(z):
        print("ATTENTION : nombre d'images différent du nombre de plans")


EXT_IMAGES = (".tif", ".tiff", ".png", ".bmp", ".jpg", ".jpeg")
CACHE_PYCASO = ("all_X_", "all_xth_", "nb_pts_")      # détections mises en cache par Pycaso
TAGS = {"Lagrange": "Lpform_{}", "Soloff": "Spform_{}", "Zernike": "nZ_{}"}


def images_camera(dossier, cote):
    d = Path(dossier) / f"video_extenso_{cote}"
    return sorted(p for p in d.glob("*") if p.suffix.lower() in EXT_IMAGES) if d.is_dir() else []


def nettoyer_dossiers_cameras(dossier):
    """Pycaso prend TOUS les fichiers des dossiers caméra comme images
    (glob('*')). Les autres fichiers (metadata.csv écrit par l'acquisition…) sont
    déplacés à côté : metadata.csv -> metadata_left.csv, comme move_metadata."""
    for cote in ("left", "right"):
        d = Path(dossier) / f"video_extenso_{cote}"
        if not d.is_dir():
            continue
        for p in d.iterdir():
            if p.is_file() and p.suffix.lower() not in EXT_IMAGES:
                cible = Path(dossier) / (f"metadata_{cote}.csv" if p.name == "metadata.csv"
                                         else f"{cote}_{p.name}")
                p.replace(cible)
                print(f"{p.name} sorti de {d.name} -> {cible.name} (Pycaso le prendrait pour une image)",
                      flush=True)


def invalider_cache(dossier_resultats, images):
    """Pycaso réutilise all_X / all_xth / nb_pts s'ils existent, sans regarder les
    images. On les efface si les images ne sont plus les mêmes que lors du calcul
    précédent (autre dossier Mesure, nouvelle acquisition, détection ratée)."""
    dossier_resultats.mkdir(parents=True, exist_ok=True)
    signature = [[str(p), p.stat().st_size, int(p.stat().st_mtime)] for p in images]
    tampon = dossier_resultats / "images_utilisees.json"
    ancienne = json.loads(tampon.read_text()) if tampon.exists() else None
    caches = [p for p in dossier_resultats.glob("*.npy") if p.name.startswith(CACHE_PYCASO)]
    if caches and ancienne != signature:
        for p in caches:
            p.unlink()
        print("Détection précédente effacée (faite sur d'autres images) : nouvelle détection "
              "de la mire", flush=True)
    tampon.write_text(json.dumps(signature))


def format_mire(images, ncx=12, ncy=12, sqr=7.5, n_test=6):
    """Pycaso impose board.setLegacyPattern(True) (ancien format OpenCV). Pour une
    mire à nombre pair de carrés (12 x 12), ancien et nouveau formats placent les
    marqueurs différemment : avec le mauvais, aucun coin n'est trouvé, Pycaso
    rejette toutes les images et ne produit aucune figure. On teste les deux formats
    sur quelques images et on renvoie True (ancien) ou False (nouveau)."""
    import cv2
    d = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
    p = cv2.aruco.DetectorParameters()
    p.adaptiveThreshWinSizeMax = 300
    scores = {}
    pas = max(1, len(images) // n_test)
    for legacy in (True, False):
        b = cv2.aruco.CharucoBoard((ncx, ncy), sqr, sqr / 2, d)
        b.setLegacyPattern(legacy)
        total = 0
        for im in images[::pas][:n_test]:
            img = cv2.imread(str(im), cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            c, i, _ = cv2.aruco.ArucoDetector(d, p).detectMarkers(img)
            ch, _, _, _ = cv2.aruco.CharucoDetector(b, detectorParams=p).detectBoard(
                img, markerCorners=c, markerIds=i)
            total += 0 if ch is None else len(ch)
        scores[legacy] = total
    print(f"Format de la mire : ancien (legacy) {scores[True]} coins, nouveau "
          f"{scores[False]} coins sur {min(n_test, len(images))} images test", flush=True)
    if max(scores.values()) == 0:
        print("ERREUR : aucun coin de mire détecté dans les images test (mire hors champ, "
              "floue, surexposée ?)", flush=True)
    return scores[True] >= scores[False]


def forcer_format_mire(legacy):
    """Adapte OpenCV à ce qu'attend Pycaso, sans modifier Pycaso :
    - le format de mire détecté remplace le setLegacyPattern(True) codé en dur ;
    - les coins sont renvoyés en (N, 1, 2) et les numéros en (N, 1), comme dans
      OpenCV 4.7 : selon les versions, OpenCV renvoie (N, 2) et Pycaso plante en
      lisant chcorners[i][0]."""
    import cv2
    import numpy as np
    original = cv2.aruco.CharucoBoard.setLegacyPattern
    cv2.aruco.CharucoBoard.setLegacyPattern = lambda self, _v: original(self, legacy)
    if hasattr(cv2.aruco, "CharucoDetector"):
        detecter = cv2.aruco.CharucoDetector.detectBoard

        def detect_board(self, *a, **k):
            coins, ids, coins_mrk, ids_mrk = detecter(self, *a, **k)
            if coins is not None and len(coins):
                coins = np.asarray(coins, dtype=np.float32).reshape(-1, 1, 2)
            if ids is not None and len(ids):
                ids = np.asarray(ids).reshape(-1, 1)
            return coins, ids, coins_mrk, ids_mrk
        cv2.aruco.CharucoDetector.detectBoard = detect_board


def figures_en_png():
    """Pycaso enregistre l'erreur de rétroprojection en PDF : on en fait aussi un PNG,
    que l'interface peut afficher."""
    import matplotlib.pyplot as plt
    original = plt.savefig

    def savefig(nom, *a, **k):
        original(nom, *a, **k)
        if str(nom).lower().endswith(".pdf"):
            k.pop("format", None)
            original(str(nom)[:-4] + ".png", *a, **{**k, "dpi": 110})
    plt.savefig = savefig


def resume_detection(resultats, n_plans):
    """Coins détectés par image et images que Pycaso rejette (premier coin absent)."""
    import numpy as np
    try:
        X = np.load(next(resultats.glob("all_X_*.npy")))
    except (StopIteration, OSError):
        return
    n = (~np.isnan(X[:, :, 0])).sum(1)
    g, d = n[:len(n) // 2], n[len(n) // 2:]
    rejet = sorted(set(np.where(np.isnan(X[:, 0, 0]))[0] % (len(n) // 2)))
    print(f"Coins détectés par image (sur {X.shape[1]}) : gauche {g.min()}–{g.max()}, "
          f"droite {d.min()}–{d.max()}", flush=True)
    if rejet:
        print(f"ATTENTION : Pycaso rejette {len(rejet)} plan(s) sur {n_plans} (premier coin de "
              f"la mire non vu) : plans n° {[r + 1 for r in rejet]}", flush=True)


def calcul(cfg):
    cal = cfg["calibration"]
    dossier = Path(cal["dossier_images"])
    # mêmes hauteurs que l'acquisition : z départ -> z fin par pas
    z = zl(cal)
    print(f"z_list : {z}", flush=True)
    print(f"Images : {dossier}", flush=True)

    nettoyer_dossiers_cameras(dossier)
    g, d = images_camera(dossier, "left"), images_camera(dossier, "right")
    print(f"Images trouvées : gauche {len(g)}, droite {len(d)}, plans {len(z)}", flush=True)
    if not g or not d:
        sys.exit(f"ERREUR : aucune image dans {dossier}/video_extenso_left ou _right. "
                 "Vérifier « Images pour le calcul » (dossier Mesure de l'acquisition).")
    if not len(g) == len(d) == len(z):
        sys.exit("ERREUR : Pycaso associe l'image n à la hauteur n : il faut autant d'images "
                 f"à gauche ({len(g)}) et à droite ({len(d)}) que de plans ({len(z)}). "
                 "Corriger Z départ / Z fin / pas, ou le dossier.")

    import numpy as np
    from Pycaso.calibration_class import Calibration

    resultats = Calibration.results_dir_for(dossier) / TAGS[cal["methode"]].format(int(cal["pform"]))
    invalider_cache(resultats, g + d)
    legacy = format_mire(g + d)
    print(f"Mire au format {'ancien (legacy)' if legacy else 'nouveau'} : utilisé pour Pycaso",
          flush=True)
    forcer_format_mire(legacy)
    figures_en_png()

    params = {"date": cal["date"], "path_images": str(dossier),
              "z_list": np.asarray(z), "show_plot": bool(cal["afficher_3d"])}
    calib = Calibration.from_params(params)
    print(f"Calibration {cal['methode']} (forme {cal['pform']}, "
          f"{cal['iterations']} itérations)...", flush=True)
    # comme Pycaso/calibration_gui : la forme est un entier (ex. 332 pour Soloff)
    try:
        calib.run(cal["methode"], int(cal["pform"]), int(cal["iterations"]))
    except TypeError as e:
        if "0-dimensional arrays" in str(e):
            sys.exit(f"ERREUR : Pycaso n'est pas compatible avec NumPy {np.__version__} "
                     "(int() sur un tableau, refusé depuis NumPy 2.5). Installer une version "
                     "antérieure : pip install \"numpy<2.5\"")
        raise
    print(f"Résultats dans {Calibration.results_dir_for(dossier)}")
    resume_detection(resultats, len(z))
    retro = sorted((resultats / "Pycaso_retroprojection_error").glob("*.png"),
                   key=lambda p: p.stat().st_mtime)
    figures = sorted(resultats.glob("3D_coordinates/*.png")) + retro[-1:]
    if not retro:
        print("ATTENTION : pas de figure d'erreur de rétroprojection (« No iterations "
              "possible » : trop peu d'images utilisables).", flush=True)
    for f in figures:
        print(f"FIGURE={f}", flush=True)
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
