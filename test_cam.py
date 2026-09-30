import ximea.xiapi as xi
import time
import subprocess

def test_camera_sn(serial_number):
    cam = xi.Camera()
    try:
        print(f"\n→ Test de connexion pour la caméra SN = {serial_number} ...")
        cam.open_device_by_SN(serial_number)  # ouvre par numéro de série
        print("✔ Ouverture réussie !")

        # Informations utiles via get_device_info_string()
        sn = cam.get_device_info_string("device_sn")
        name = cam.get_device_info_string("device_name")
        path = cam.get_device_info_string("device_loc_path")
        devtype = cam.get_device_info_string("device_type")

        print(f" Serial number     : {sn}")
        print(f" Device name       : {name}")
        print(f" Device OS path    : {path}")
        print(f" Device type       : {devtype}")

    except xi.Xi_error as e:
        print(f"❌ Erreur XIMEA pour {serial_number} : {e}")
    finally:
        try:
            cam.close_device()
            print("✔ Fermeture de la caméra.")
        except xi.Xi_error:
            print("⚠ La caméra n'était pas ouverte ou déjà fermée.")

if __name__ == "__main__":

    subprocess.run(
		["sudo", "tee", "/sys/module/usbcore/parameters/usbfs_memory_mb"],
		input=b"0\n",
		check = True
		)
    print("Emptying the buffer")
    # Optionnel : affiche combien de caméras sont détectées
    cam_enum = xi.Camera()
    n = cam_enum.get_number_devices()
    print(f"\n📌 Nombre de caméras détectées : {n}")

    # Remplace ces SN par ceux visibles si nécessaire
    serials = ["14482450", "32482550"]

    for sn in serials:
        time.sleep(1.5)
        test_camera_sn(sn)


