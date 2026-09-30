#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import multiprocessing as mp
import ft232R
import moteur
#import struct



def get_unique_save_path(base_path):
    """
    Creates the folder to regroup all data from one calibration
    """
    import os

    if not os.path.exists(base_path):
        os.makedirs(base_path)
        return base_path

    if not os.listdir(base_path):
        return base_path

    counter = 1
    while True:
        new_path = f"{base_path}_{counter:05d}"
        if not os.path.exists(new_path):
            os.makedirs(new_path)
            print(f"The desired path was not available, the new path is {new_path}")
            return new_path
        if not os.listdir(new_path):
            print(f"The desired path was not available, the new path is {new_path}")
            return new_path
        counter += 1


if __name__ == "__main__":

    # ==========================================================
    # 🔴 OBLIGATOIRE avec XiAPI + multiprocessing
    # ==========================================================
    mp.set_start_method("spawn", force=True)

    # ==========================================================
    # Imports (APRÈS spawn)
    # ==========================================================
    import crappy
    import time
    import os
    import pathlib
    import subprocess
    import sys



    # ==========================================================
    # USB buffer (recommandé avec Ximea USB3)
    # ==========================================================
    try:
        subprocess.run(
            ["sudo", "tee", "/sys/module/usbcore/parameters/usbfs_memory_mb"],
            input=b"1000\n",
            check=True
        )
        print("USB buffer set to 1000 MB")
    except Exception as e:
        print("⚠️ Unable to set usbfs_memory_mb")
        print(e)

    # ==========================================================
    # Paths & metadata
    # ==========================================================
    date = time.strftime("%Y_%m_%d")
    sample = "Pro_Grip"
    white_spots = True

    saving_folder = get_unique_save_path(f"./{date}/{sample}/Mesure")

    pathlib.Path(saving_folder).mkdir(parents=True, exist_ok=True)

    # ==========================================================
    # VideoExtenso blocks (cameras)
    # ==========================================================
    try:
        ver = crappy.blocks.VideoExtenso(
            camera="XiAPI",
            config=True,
            save_images=True,
            save_folder=os.path.join(saving_folder, "video_extenso_right"),
            img_shape=(2048, 2048),
            img_dtype="uint8",
            labels=["tr(s)", "meta_r", "pix_r", "eyy_r", "exx_r"],
            white_spots=white_spots,
            serial_number="14482450",
            exposure=41389,
            trigger="Hdw after config"
        )
        print("Camera 14482450 connected")
    except Exception as e:
        print("❌ Camera 14482450 unavailable")
        print(e)
        sys.exit(1)

    time.sleep(1)

    try:
        vel = crappy.blocks.VideoExtenso(
            camera="XiAPI",
            config=True,
            save_images=True,
            save_folder=os.path.join(saving_folder, "video_extenso_left"),
            img_shape=(2048, 2048),
            img_dtype="uint8",
            labels=["tl(s)", "meta_l", "pix_l", "eyy_l", "exx_l"],
            white_spots=white_spots,
            serial_number="32482550",
            exposure=31740,
            trigger="Hdw after config"
        )
        print("Camera 32482550 connected")
    except Exception as e:
        print("❌ Camera 32482550 unavailable")
        print(e)
        sys.exit(1)

    time.sleep(1)

    # ==========================================================
    # IO / Machine / Generators
    # ==========================================================
    ftdi = crappy.blocks.IOBlock(
        "Ft232r",
        cmd_labels=["cmd"],
        spam=False,
        direction=0b00000100,
        URL="ftdi://ftdi:232:FTU7DIHC/1"
    )

    mot = crappy.blocks.Machine(
        [{
            "type": "Printer",
            "mode": "position",
            "cmd_label": "pos",
            "position_label": "position",
            "speed": 100,
            "port": "/dev/ttyACM0"
        }],
        freq=50
    )

    gen_ft = crappy.blocks.Generator(
        [{
            "type": "Cyclic",
            "value1": 0, "condition1": "delay=0.1",
            "value2": 1, "condition2": "delay=0.3",
            "cycles": 2000
        }],
        cmd_label="cmd"
    )

    path_mot = [{
        "type": "Ramp",
        "speed": -0.5,
        "condition": "position < 40",
        "init_value": 70
    }]

    gen_mot = crappy.blocks.Generator(
        path=path_mot,
        cmd_label="pos"
    )

    # ==========================================================
    # Recorders & Grapher
    # ==========================================================
    rec_ver = crappy.blocks.Recorder(
        file_name=os.path.join(saving_folder, "data_ver.txt"),
        labels=["tr(s)", "pix_r", "exx_r", "eyy_r"]
    )

    rec_vel = crappy.blocks.Recorder(
        file_name=os.path.join(saving_folder, "data_vel.txt"),
        labels=["tl(s)", "pix_l", "exx_l", "eyy_l"]
    )

    graph_mot = crappy.blocks.Grapher(("t(s)", "position"))

    record_mot = crappy.blocks.Recorder(
        file_name=os.path.join(saving_folder, "z_list"),
        labels=["t(s)", "position"],
        freq=1,
        delay=5
    )

    # ==========================================================
    # Links
    # ==========================================================
    crappy.link(gen_ft, ftdi)

    crappy.link(gen_mot, mot)
    crappy.link(mot, gen_mot)

    crappy.link(ver, rec_ver)
    crappy.link(vel, rec_vel)

    crappy.link(mot, graph_mot)
    crappy.link(mot, record_mot)

    # ==========================================================
    # Start experiment
    # ==========================================================
    crappy.start()
