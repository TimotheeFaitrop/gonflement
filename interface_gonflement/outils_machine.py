"""Petites actions sur le matériel, lancées en sous-processus par l'interface
(pour ne jamais bloquer la fenêtre ni garder un port série ouvert).

    python outils_machine.py ports
    python outils_machine.py origine   PORT_IMPRIMANTE
    python outils_machine.py aller_z   PORT_IMPRIMANTE Z [--origine]
    python outils_machine.py apercu    SN_GAUCHE SN_DROITE EXPO_G EXPO_D
    python outils_machine.py reglage_init SN_GAUCHE SN_DROITE EXPO_G EXPO_D PORT_IMPRIMANTE
    python outils_machine.py test_cameras SN_GAUCHE SN_DROITE
    python outils_machine.py debit_zero PORT_ALICAT BAUD
"""

import struct
import sys
import time


def _envoyer_gcode(dev, cmd, timeout=120):
    """Envoie une ligne G-code et attend le 'ok' (comme reglage_hauteur_init)."""
    dev.write((cmd + "\r\n").encode())
    t0 = time.time()
    while time.time() - t0 < timeout:
        ligne = dev.readline().decode(errors="ignore").strip()
        if ligne:
            print(">>", ligne, flush=True)
        if ligne.lower().startswith("ok"):
            return
    raise TimeoutError(f"Pas de réponse 'ok' pour {cmd}")


def ports():
    from serial.tools import list_ports
    lp = list(list_ports.comports())
    if not lp:
        print("Aucun port série détecté")
    for p in lp:
        print(f"{p.device:16s} {p.description}  [{p.hwid}]")
    try:
        from pyftdi.ftdi import Ftdi
        Ftdi.show_devices()
    except Exception as e:  # pyftdi absent ou pas de droits USB
        print(f"(FTDI non listé : {e})")


def origine(port):
    from serial import Serial
    with Serial(port, baudrate=115200, timeout=2) as dev:
        time.sleep(2)  # l'imprimante redémarre à l'ouverture du port
        _envoyer_gcode(dev, "G28 Z0")
    print("Origine Z faite")


def aller_z(port, z, avec_origine=False):
    from serial import Serial
    with Serial(port, baudrate=115200, timeout=2) as dev:
        time.sleep(2)
        if avec_origine:
            _envoyer_gcode(dev, "G28 Z0")
        _envoyer_gcode(dev, "G90")
        _envoyer_gcode(dev, f"G0 X0 Y0 Z{z}")
        _envoyer_gcode(dev, "M400")      # attend la fin du déplacement
    print(f"Plateau en Z = {z} mm")


def _ouvrir_camera(sn, expo):
    """Ouvre une caméra en acquisition libre ; renvoie (camera, image) ou lève une erreur."""
    from ximea import xiapi
    c = xiapi.Camera()
    c.open_device_by_SN(sn)
    try:
        c.set_imgdataformat("XI_MONO8")
        c.set_trigger_source("XI_TRG_OFF")       # au cas où un essai l'a laissée en déclenché
        c.set_exposure(int(expo))
        c.start_acquisition()
    except Exception:
        c.close_device()
        raise
    return c, xiapi.Image()


def _fermer_camera(c):
    for f in (c.stop_acquisition, c.close_device):
        try:
            f()
        except Exception:
            pass


def apercu(sn_g, sn_d, expo_g, expo_d):
    """Aperçu des deux caméras côte à côte (q, Échap ou fermeture de la fenêtre).

    Une caméra qui ne s'ouvre pas ou ne renvoie pas d'image n'empêche ni
    d'afficher l'autre, ni de fermer la fenêtre : lecture avec délai d'attente."""
    import cv2
    import numpy as np

    cams = {}
    for nom, sn, expo in (("gauche", sn_g, expo_g), ("droite", sn_d, expo_d)):
        try:
            cams[nom] = _ouvrir_camera(sn, expo)
            print(f"Caméra {nom} ({sn}) ouverte", flush=True)
        except Exception as e:
            cams[nom] = None
            print(f"Caméra {nom} ({sn}) INDISPONIBLE : {e}", flush=True)
    # délai de lecture : exposition + 1 s (ms), pour ne jamais rester bloqué
    delai = {"gauche": int(expo_g) // 1000 + 1000, "droite": int(expo_d) // 1000 + 1000}
    print("Aperçu ouvert : q ou Échap pour fermer", flush=True)
    titre = "Apercu  gauche | droite   (q pour fermer)"
    vide = np.zeros((676, 676, 3), np.uint8)
    try:
        while True:
            vues = []
            for nom in ("gauche", "droite"):
                f = None
                if cams[nom] is not None:
                    c, img = cams[nom]
                    try:
                        c.get_image(img, timeout=delai[nom])
                        f = img.get_image_data_numpy()
                    except Exception:
                        f = None
                if f is None:
                    v = vide.copy()
                    cv2.putText(v, f"camera {nom} : pas d'image", (40, 338),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (80, 80, 230), 2)
                else:
                    v = cv2.cvtColor(cv2.resize(f, (676, 676), interpolation=cv2.INTER_AREA),
                                     cv2.COLOR_GRAY2BGR)
                    cv2.line(v, (338, 0), (338, 676), (0, 200, 0), 1)
                    cv2.line(v, (0, 338), (676, 338), (0, 200, 0), 1)
                vues.append(v)
            cv2.imshow(titre, np.hstack(vues))
            k = cv2.waitKey(30) & 0xFF
            if k in (ord("q"), 27) or cv2.getWindowProperty(titre, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        for cam in cams.values():
            if cam is not None:
                _fermer_camera(cam[0])
        cv2.destroyAllWindows()


def reglage_init(sn_g, sn_d, expo_g, expo_d, port):
    """Comme reglage_hauteur_init.py : origine, aperçu des caméras jusqu'à fermeture,
    puis Z = 20 et Z = 120 mm pour vérifier la netteté de la mire."""
    from serial import Serial
    with Serial(port, baudrate=115200, timeout=2) as dev:
        time.sleep(2)
        _envoyer_gcode(dev, "G28 Z0")
        apercu(sn_g, sn_d, expo_g, expo_d)
        _envoyer_gcode(dev, "G0 X0 Y0 Z20")
        _envoyer_gcode(dev, "G0 X0 Y0 Z120")
    print("Réglage initial terminé (plateau à Z = 120 mm)")


def test_cameras(*serials):
    """Ouvre chaque caméra et lit une image (délai 3 s). Code de sortie 0 si toutes
    répondent. Chaque étape est annoncée avant d'être faite : si une caméra bloque,
    la dernière ligne affichée indique laquelle (l'interface coupe le test au bout de 20 s)."""
    ok = True
    for sn in serials:
        print(f"Test caméra {sn}…", flush=True)
        try:
            c, img = _ouvrir_camera(sn, 10000)
        except Exception as e:
            ok = False
            print(f"Caméra {sn} : NE S'OUVRE PAS ({e})", flush=True)
            continue
        try:
            c.get_image(img, timeout=3000)
            print(f"Caméra {sn} : OK (image {img.width} x {img.height})", flush=True)
        except Exception as e:
            ok = False
            print(f"Caméra {sn} : OUVERTE MAIS AUCUNE IMAGE ({e})", flush=True)
        finally:
            _fermer_camera(c)
    sys.exit(0 if ok else 1)


def debit_zero(port, baud):
    """Écrit une consigne nulle dans le registre 1009 de l'Alicat (secours)."""
    from pymodbus.client import ModbusSerialClient
    import pymodbus
    ancien = pymodbus.__version__.startswith("3.0")
    kw = {"method": "rtu"} if ancien else {}
    cli = ModbusSerialClient(port=port, baudrate=int(baud), parity="N",
                             stopbits=1, timeout=3, **kw)
    if not cli.connect():
        sys.exit(f"Impossible d'ouvrir {port}")
    octets = struct.pack(">f", 0.0)
    regs = [struct.unpack(">H", octets[i:i + 2])[0] for i in (0, 2)]
    if ancien:   # même appel que alicat_flow_crappy_V3 pour pymodbus 3.0.2
        cli.write_registers(address=1009, values=regs, unit=1)
    else:
        cli.write_registers(address=1009, values=regs)
    cli.close()
    print("Consigne de débit remise à 0")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    action, args = sys.argv[1], sys.argv[2:]
    if action == "ports":
        ports()
    elif action == "origine":
        origine(args[0])
    elif action == "aller_z":
        aller_z(args[0], float(args[1]), "--origine" in args)
    elif action == "apercu":
        apercu(*args[:4])
    elif action == "reglage_init":
        reglage_init(*args[:5])
    elif action == "test_cameras":
        test_cameras(*args)
    elif action == "debit_zero":
        debit_zero(args[0], args[1])
    else:
        sys.exit(f"Action inconnue : {action}\n{__doc__}")
