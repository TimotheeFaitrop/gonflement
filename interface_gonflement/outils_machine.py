"""Petites actions sur le matériel, lancées en sous-processus par l'interface
(pour ne jamais bloquer la fenêtre ni garder un port série ouvert).

    python outils_machine.py ports
    python outils_machine.py origine   PORT_IMPRIMANTE
    python outils_machine.py aller_z   PORT_IMPRIMANTE Z [--origine]
    python outils_machine.py apercu    SN_GAUCHE SN_DROITE EXPO_G EXPO_D
    python outils_machine.py reglage_init SN_GAUCHE SN_DROITE EXPO_G EXPO_D PORT_IMPRIMANTE
    python outils_machine.py test_cameras SN_GAUCHE SN_DROITE
    python outils_machine.py changer_origine PORT_IMPRIMANTE Z
    python outils_machine.py test_hauteur SN_GAUCHE SN_DROITE EXPO_G EXPO_D PORT_IMPRIMANTE
    python outils_machine.py photo SN_GAUCHE SN_DROITE EXPO_G EXPO_D DOSSIER
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


def changer_origine(port, z):
    """G92 : la position actuelle du plateau devient Z = z (sans le déplacer).
    Valable jusqu'à la prochaine prise d'origine (G28) ou au redémarrage de l'imprimante."""
    from serial import Serial
    with Serial(port, baudrate=115200, timeout=2) as dev:
        time.sleep(2)
        _envoyer_gcode(dev, f"G92 Z{z}")
        _envoyer_gcode(dev, "M114")
    print(f"Nouvelle origine : la position actuelle vaut maintenant Z = {z} mm")


def test_hauteur(sn_g, sn_d, expo_g, expo_d, port):
    """Test de netteté sur toute la plage : origine, Z = 20 mm, puis Espace pour
    Z = 120 mm (et retour), avec l'aperçu des deux caméras et leur netteté."""
    apercu(sn_g, sn_d, expo_g, expo_d, port=port, hauteurs=(20, 120))
    print("Test de hauteur terminé")


def photo(sn_g, sn_d, expo_g, expo_d, dossier):
    """Une photo avec chaque caméra (acquisition libre), en TIFF pleine résolution.
    L'interface les affiche directement (pas de fichier d'aperçu)."""
    import cv2
    from pathlib import Path
    import compat_cv2
    compat_cv2.installer()
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    heure = time.strftime("%H%M%S")
    vues = []
    for nom, sn, expo in (("gauche", sn_g, expo_g), ("droite", sn_d, expo_d)):
        print(f"Photo caméra {nom} ({sn})…", flush=True)
        try:
            c, img = _ouvrir_camera(sn, expo)
        except Exception as e:
            print(f"Caméra {nom} ({sn}) INDISPONIBLE : {e}", flush=True)
            vues.append(None)
            continue
        try:
            c.get_image(img, timeout=int(expo) // 1000 + 3000)
            f = img.get_image_data_numpy()
            chemin = dossier / f"photo_{nom}_{heure}.tiff"
            cv2.imwrite(str(chemin), f)
            print(f"PHOTO={nom}|{chemin}", flush=True)
            vues.append(f)
        except Exception as e:
            print(f"Caméra {nom} ({sn}) : aucune image ({e})", flush=True)
            vues.append(None)
        finally:
            _fermer_camera(c)
    if any(v is None for v in vues):
        sys.exit(1)


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


class Plateau:
    """Envoi de G-code sans bloquer l'aperçu : les commandes partent une par une,
    chacune après le « ok » de la précédente."""

    def __init__(self, port):
        from serial import Serial
        self.dev = Serial(port, baudrate=115200, timeout=0)
        time.sleep(2)                        # l'imprimante redémarre à l'ouverture du port
        self.dev.reset_input_buffer()
        self.file, self.en_attente, self.tampon = [], None, b""

    def envoyer(self, *cmds):
        self.file.extend(cmds)
        self.poll()

    @property
    def occupe(self):
        return bool(self.file) or self.en_attente is not None

    def poll(self):
        self.tampon += self.dev.read(self.dev.in_waiting or 1)
        while b"\n" in self.tampon:
            ligne, self.tampon = self.tampon.split(b"\n", 1)
            ligne = ligne.decode(errors="ignore").strip()
            if ligne:
                print(">>", ligne, flush=True)
            if ligne.lower().startswith("ok"):
                self.en_attente = None
        if self.en_attente is None and self.file:
            self.en_attente = self.file.pop(0)
            self.dev.write((self.en_attente + "\r\n").encode())

    def fermer(self):
        self.dev.close()


def nettete(f):
    """Netteté = variance du laplacien sur le centre de l'image (plus c'est grand,
    plus c'est net). Sert à comparer les hauteurs entre elles, pas en absolu."""
    import cv2
    h, w = f.shape[:2]
    centre = f[h // 4: 3 * h // 4, w // 4: 3 * w // 4]
    return float(cv2.Laplacian(centre, cv2.CV_64F).var())


def apercu(sn_g, sn_d, expo_g, expo_d, port=None, hauteurs=()):
    """Aperçu des deux caméras côte à côte (q, Échap ou fermeture de la fenêtre).

    Avec `port` et `hauteurs` (test hauteur) : origine, puis le plateau va à la
    première hauteur ; Espace passe à la hauteur suivante (en boucle). La netteté
    de chaque caméra est affichée en direct et notée dans la console.
    Une caméra qui ne répond pas n'empêche ni d'afficher l'autre, ni de fermer."""
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
    plateau, i_h = None, 0
    if port and hauteurs:
        plateau = Plateau(port)
        plateau.envoyer("G28 Z0", "G90", f"G0 X0 Y0 Z{hauteurs[0]}", "M400")
        print(f"Origine puis Z = {hauteurs[0]} mm…", flush=True)
    titre = "Apercu  gauche | droite   (q pour fermer)"
    print("Aperçu ouvert : q ou Échap pour fermer" +
          (", Espace pour changer de hauteur" if plateau else ""), flush=True)
    cote = 676
    vide = np.zeros((cote, cote, 3), np.uint8)
    try:
        while True:
            vues, scores = [], {}
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
                    cv2.putText(v, f"camera {nom} : pas d'image", (40, cote // 2),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (80, 80, 230), 2)
                else:
                    scores[nom] = nettete(f)
                    v = cv2.cvtColor(cv2.resize(f, (cote, cote), interpolation=cv2.INTER_AREA),
                                     cv2.COLOR_GRAY2BGR)
                    cv2.line(v, (cote // 2, 0), (cote // 2, cote), (0, 200, 0), 1)
                    cv2.line(v, (0, cote // 2), (cote, cote // 2), (0, 200, 0), 1)
                    cv2.putText(v, f"{nom}  nettete {scores[nom]:.0f}", (12, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (80, 220, 80), 2)
                vues.append(v)
            image = np.hstack(vues)
            if plateau:
                plateau.poll()
                z = hauteurs[i_h]
                etat = (f"deplacement vers Z = {z} mm..." if plateau.occupe else
                        f"Z = {z} mm   Espace : Z = {hauteurs[(i_h + 1) % len(hauteurs)]} mm   q : fermer")
                bande = np.zeros((44, image.shape[1], 3), np.uint8)
                cv2.putText(bande, etat, (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                            (80, 200, 230) if plateau.occupe else (230, 230, 230), 2)
                image = np.vstack([image, bande])
            cv2.imshow(titre, image)
            k = cv2.waitKey(30) & 0xFF
            if k in (ord("q"), 27) or cv2.getWindowProperty(titre, cv2.WND_PROP_VISIBLE) < 1:
                break
            if plateau and k == ord(" ") and not plateau.occupe:
                print(f"Z = {hauteurs[i_h]} mm : netteté " + ", ".join(
                    f"{n} {s:.0f}" for n, s in scores.items()), flush=True)
                i_h = (i_h + 1) % len(hauteurs)
                plateau.envoyer(f"G0 X0 Y0 Z{hauteurs[i_h]}", "M400")
                print(f"Plateau vers Z = {hauteurs[i_h]} mm…", flush=True)
    finally:
        for cam in cams.values():
            if cam is not None:
                _fermer_camera(cam[0])
        cv2.destroyAllWindows()
        if plateau:
            plateau.fermer()


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
    elif action == "changer_origine":
        changer_origine(args[0], float(args[1]))
    elif action == "test_hauteur":
        test_hauteur(*args[:5])
    elif action == "photo":
        photo(*args[:5])
    elif action == "test_cameras":
        test_cameras(*args)
    elif action == "debit_zero":
        debit_zero(args[0], args[1])
    else:
        sys.exit(f"Action inconnue : {action}\n{__doc__}")
