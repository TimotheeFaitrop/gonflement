"""Construit et lance l'essai de gonflement crappy à partir d'un fichier JSON.

Appelé par l'interface :  python lancer_essai.py config_essai.json
(utilisable aussi à la main, sans interface.)

Graphe crappy (mode réel) :

    FT232R <- Générateur cyclique (déclenchement caméras à freq_cam)
    Caméra droite (VideoExtenso) --+--> Recorder, [StereoDeformation 3D Zernike]
    Caméra gauche (VideoExtenso) --+
    Débitmètre Alicat --> Contrôleur (débit | pression | déformation) --> Alicat
    tout le monde --> FluxInterface (UDP vers l'interface)
"""

import json
import subprocess
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))   # modules du dépôt (alicat, ft232R, ...)
sys.path.insert(0, str(ICI))

import crappy  # noqa: E402

import blocs_pilotage as bp  # noqa: E402
import simulation  # noqa: E402,F401  enregistre AlicatSimule
from reglages import dossier_unique  # noqa: E402

# crappy ne garde qu'une référence faible vers les blocs : on les conserve ici,
# sinon un bloc créé directement dans crappy.link(...) disparaît.
_BLOCS = []


def garder(bloc):
    _BLOCS.append(bloc)
    return bloc


def liberer_memoire_usb():
    """echo 0 | sudo tee /sys/module/usbcore/parameters/usbfs_memory_mb,
    sans mot de passe (sudo -n). Si sudo demande un mot de passe, utiliser le
    bouton de l'onglet Matériel avant de lancer l'essai."""
    try:
        r = subprocess.run(["sudo", "-n", "tee",
                            "/sys/module/usbcore/parameters/usbfs_memory_mb"],
                           input=b"0\n", capture_output=True, timeout=10)
        if r.returncode == 0:
            print("Mémoire USB des caméras libérée")
        else:
            print("ATTENTION : mémoire USB non libérée (sudo demande un mot de passe)."
                  " Utiliser le bouton « Libérer la mémoire USB » de l'onglet Matériel.")
    except (OSError, subprocess.SubprocessError) as e:
        print(f"ATTENTION : mémoire USB non libérée ({e})")


def main(fichier_config):
    with open(fichier_config, encoding="utf-8") as f:
        cfg = json.load(f)
    mat, ess = cfg["materiel"], cfg["essai"]
    simu = mat["simulation"]
    mode = ess["mode"]
    fs = float(mat["pleine_echelle"])

    date = time.strftime("%Y_%m_%d")
    dossier = dossier_unique(Path(mat["dossier_racine"]) / date
                             / ess["echantillon"] / "Mesure")
    # le chemin est lu par l'interface : ne pas changer ce préfixe
    print(f"DOSSIER_ESSAI={dossier.resolve()}", flush=True)
    with open(dossier / "parametres_essai.json", "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

    # ---------------------------------------------------------------- débitmètre
    labels_ali = ["t(s)", "press", "volumetric_flow", "mass_flow"]
    if simu:
        flow_ali = crappy.blocks.IOBlock(
            "AlicatSimule", pleine_echelle=fs,
            pression_relative=mat["pression_relative"],
            cmd_labels=["cmd"], labels=labels_ali + ["exx_sim", "eyy_sim"],
            freq=20)
    else:
        import alicat_flow_crappy_V3  # noqa: F401  enregistre Flow_controller_alicat
        if not hasattr(alicat_flow_crappy_V3, "Flow_controller_alicat"):
            import pymodbus
            sys.exit(f"pymodbus {pymodbus.__version__} non géré par "
                     "alicat_flow_crappy_V3.py (versions 3.0.2, 3.8.6, 3.9.0)")
        flow_ali = crappy.blocks.IOBlock(
            "Flow_controller_alicat", port=mat["port_alicat"],
            startbit=1, databits=8, parity="N", stopbits=1, errorcheck="crc",
            baudrate=int(mat["baud_alicat"]), timeout=30,
            press="relative" if mat["pression_relative"] else "absolue",
            svp=["Pressure", "Volumetric_flow", "Mass_flow"],
            cmd_labels=["cmd"], labels=labels_ali)

    # --------------------------------------------------------------- caméras
    ver = vel = None
    if not simu:
        liberer_memoire_usb()
        from alicat_flow_crappy_V3 import FixedVideoExtenso
        import ft232R  # noqa: F401  enregistre Ft232r

        taille = int(mat["taille_image"])
        commun = dict(camera="XiAPI", config=True,
                      save_images=bool(ess["sauver_images"]),
                      img_shape=(taille, taille), img_dtype="uint8",
                      white_spots=False)
        ver = FixedVideoExtenso(
            save_folder=str(dossier / "video_extenso_right"),
            labels=["tr(s)", "meta_r", "pix_r", "eyy_r", "exx_r"],
            **commun, **{"serial_number": mat["sn_droite"],
                         "exposure": int(mat["expo_droite"]),
                         "trigger": "Hdw after config"})
        vel = FixedVideoExtenso(
            save_folder=str(dossier / "video_extenso_left"),
            labels=["tl(s)", "meta_l", "pix_l", "eyy_l", "exx_l"],
            **commun, **{"serial_number": mat["sn_gauche"],
                         "exposure": int(mat["expo_gauche"]),
                         "trigger": "Hdw after config"})

        periode = 1.0 / float(ess["freq_cam"])
        ftdi = crappy.blocks.IOBlock("Ft232r", cmd_labels=["cmd"], spam=False,
                                     direction=0b00000100, URL=mat["url_ftdi"])
        gen_ft = crappy.blocks.Generator(
            [{"type": "Cyclic",
              "value1": 0, "condition1": f"delay={0.25 * periode}",
              "value2": 1, "condition2": f"delay={0.75 * periode}",
              "cycles": float(ess["duree_max"]) / periode + 10}],
            cmd_label="cmd")
        crappy.link(gen_ft, ftdi)

        crappy.link(ver, garder(crappy.blocks.Recorder(
            file_name=str(dossier / "data_ver.txt"),
            labels=["tr(s)", "pix_r", "exx_r", "eyy_r"])))
        crappy.link(vel, garder(crappy.blocks.Recorder(
            file_name=str(dossier / "data_vel.txt"),
            labels=["tl(s)", "pix_l", "exx_l", "eyy_l"])))

    # -------------------------------------------- mesure de déformation
    d = ess["deformation"]
    stereo = mode == "deformation" and d["source"] == "3D"
    if simu:
        # deux caméras simulées qui regardent le ballon simulé
        cams_sim = garder(simulation.CamerasSimulees(freq_cam=float(ess["freq_cam"])))
        crappy.link(flow_ali, cams_sim)
        ver = vel = cams_sim
    if stereo:
        estimateur = bp.EstimateurDeformation("3D")
    else:
        estimateur = bp.EstimateurDeformation("2D", d["composante"], d["camera"])

    source_3d = None
    if stereo:
        import stereo_3d
        fichier, dims, degre = d["fichier_constantes"], None, int(d["pform"])
        if simu:
            # étalonnage Zernike synthétique du banc simulé
            import numpy as np
            degre = 8
            A, dims, err = simulation.BancStereo().calibration_zernike(degre)
            fichier = dossier / "calib_simulee" / f"nZ_{degre}" / "A_Zernike.npy"
            fichier.parent.mkdir(parents=True, exist_ok=True)
            np.save(fichier, A)
            print(f"Étalonnage Zernike simulé (erreur max {err:.3f} mm) : {fichier}")
        source_3d = garder(stereo_3d.StereoDeformation(
            fichier_constantes=fichier, methode=d["methode_3d"] if not simu else "Zernike",
            degre=degre, taille_image=int(mat["taille_image"]),
            rotation_droite=bool(d["rotation_droite"]), composante=d["composante"],
            freq_cam=float(ess["freq_cam"]), dims_cameras=dims))
        for s_ in {id(vel): vel, id(ver): ver}.values():
            crappy.link(s_, source_3d)
        crappy.link(source_3d, garder(crappy.blocks.Recorder(
            file_name=str(dossier / "data_stereo_3d.txt"),
            labels=["t_3d", "eps_3d", "exx_3d", "eyy_3d", "eall_3d", "uz_3d",
                    "points_3d"])))

    # ---------------------------------------------------------- contrôleur
    commun = dict(pleine_echelle=fs,
                  debit_max=float(ess["debit_max"]),
                  vitesse_cmd_max=float(ess["vitesse_cmd_max"]),
                  pression_max=float(ess["pression_max"]),
                  duree_max=float(ess["duree_max"]),
                  arret_auto=bool(ess["arret_auto"]),
                  port_commandes=int(mat["port_udp_commandes"]))
    if mode == "debit":
        p = ess["debit"]
        q = float(p["consigne"])
        rampe = float(p["duree_rampe"])
        controleur = bp.PilotageDebit(
            consigne=q, vitesse=q / rampe if rampe > 0 else 0,
            duree_palier=float(p["duree_palier"]), attente=float(p["attente"]),
            **commun)
    elif mode == "pression":
        p = ess["pression"]
        controleur = bp.PilotagePression(
            consigne=float(p["consigne"]), vitesse=float(p["vitesse"]),
            duree_palier=float(p["duree_palier"]),
            kp=float(p["kp"]), ki=float(p["ki"]), **commun)
    elif mode == "deformation":
        controleur = bp.PilotageDeformation(
            consigne=float(d["eps_max"]), vitesse=float(d["vitesse"]),
            duree_palier=float(d["duree_palier"]),
            kp=float(d["kp"]), ki=float(d["ki"]), kff=float(d["kff"]),
            timeout_mesure=float(d["timeout_mesure"]),
            estimateur=estimateur, **commun)
        sources = [source_3d] if source_3d else [ver, vel]
        for s in {id(b): b for b in sources if b is not None}.values():
            crappy.link(s, controleur)
    else:
        sys.exit(f"Mode de pilotage inconnu : {mode}")

    crappy.link(flow_ali, controleur)
    crappy.link(controleur, flow_ali)

    # ---------------------------------------------------------- enregistrement
    crappy.link(flow_ali, garder(crappy.blocks.Recorder(
        file_name=str(dossier / "data_ali.txt"))))
    crappy.link(controleur, garder(crappy.blocks.Recorder(
        file_name=str(dossier / f"data_pilotage_{mode}.txt"))))

    # ---------------------------------------------------- retour vers l'interface
    flux = bp.FluxInterface(port=mat["port_udp_donnees"], estimateur=estimateur)
    for b in {id(b): b for b in (flow_ali, controleur, ver, vel, source_3d)
              if b is not None}.values():
        crappy.link(b, flux)

    if ess.get("graphers_crappy"):
        g = garder(crappy.blocks.Grapher(("t(s)", "press")))
        crappy.link(flow_ali, g)
        g = garder(crappy.blocks.Grapher(("t(s)", "volumetric_flow")))
        crappy.link(flow_ali, g)
        if ver is not None:
            g = garder(crappy.blocks.Grapher(("tr(s)", "exx_r"), ("tr(s)", "eyy_r")))
            crappy.link(ver, g)
            g = garder(crappy.blocks.Grapher(("tl(s)", "exx_l"), ("tl(s)", "eyy_l")))
            crappy.link(vel, g)

    print(f"Essai lancé : mode {mode}, {'SIMULATION' if simu else 'matériel réel'}",
          flush=True)
    crappy.start(no_raise=True)
    print("Essai terminé", flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage : python lancer_essai.py config_essai.json")
    main(sys.argv[1])
