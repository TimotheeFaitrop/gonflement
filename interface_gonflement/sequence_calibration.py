"""Acquisition de calibration en boucle fermée.

Dans calib_crappy_V2.py, le déplacement du plateau et le déclenchement des
caméras sont deux générateurs indépendants réglés sur un temps fixe par plan
(int(1 + pas / 0.6) s). Ça marche tant que chaque déplacement dure moins que ce
temps. Mais le plateau part de Z = 70 (Printer.open) : pour une acquisition de
120 à 10 mm, le premier déplacement fait 50 mm (30 s à 100 mm/min) au lieu de
2 mm. Les ordres s'empilent dans l'imprimante pendant que les caméras sont
déclenchées toutes les 4 s : photos prises en mouvement, à des hauteurs
quelconques, jusqu'à ce que l'imprimante rattrape son retard.

Ici, un seul bloc enchaîne les étapes, plan par plan :
  1. envoie la hauteur au plateau ;
  2. attend que la position lue (M114.2) soit atteinte et stable pendant
     « stabilisation » secondes ;
  3. envoie une impulsion au FT232R ;
  4. attend que les deux caméras aient enregistré leur image, puis passe au plan
     suivant.
La position réelle au moment de chaque photo est notée dans positions_photos.csv.
"""

import csv
import time
from pathlib import Path

import crappy

try:
    from .reglages import duree_estimee  # noqa: F401
except ImportError:
    from reglages import duree_estimee  # noqa: F401

FICHIER_POSITIONS = "positions_photos.csv"


class SequenceurCalibration(crappy.blocks.Block):
    """Pilote plateau et déclenchement. Entrées : la Machine (label 'position')
    puis le bloc caméras (un message par paire d'images enregistrée).
    Sorties : 'pos' (consigne de hauteur) et 'cmd' (impulsion, valeur croissante :
    l'IOBlock du FT232R ne transmet que les valeurs qui changent)."""

    def __init__(self, z_list, dossier, z_init=70.0, vitesse=100.0, stabilisation=1.0,
                 tolerance=0.05, delai_image=6.0, freq=50):
        super().__init__()
        self.freq = freq
        self.z_list = [float(z) for z in z_list]
        self.dossier = Path(dossier)
        self.z_init = float(z_init)
        self.v = float(vitesse) / 60.0            # mm/s (G0 F en mm/min)
        self.stabilisation = float(stabilisation)
        self.tolerance = float(tolerance)
        self.delai_image = float(delai_image)

    def prepare(self):
        self.i = 0
        self.position = None            # dernière position lue
        self.depuis_arrivee = None      # instant où la position est entrée dans la tolérance
        self.etat = None
        self.impulsion = 0
        self.images = 0                 # paires d'images enregistrées
        self.essais = 0
        self.lignes = []
        self.z_prec = self.z_init

    def begin(self):
        self.send({"cmd": 0})
        self._aller(0)

    def _aller(self, i):
        z = self.z_list[i]
        self.etat = "deplacement"
        self.t_ordre = time.time()
        self.depuis_arrivee = None
        # durée prévue du déplacement, utilisée si l'imprimante ne renvoie pas sa position
        self.t_prevu = abs(z - self.z_prec) / self.v
        self.send({"pos": z})
        print(f"Plan {i + 1}/{len(self.z_list)} : plateau vers Z = {z:g} mm "
              f"(~{self.t_prevu:.0f} s)", flush=True)

    def _declencher(self):
        self.etat = "photo"
        self.impulsion += 1
        self.attendues = self.images + 1
        self.t_photo = time.time()
        self.send({"cmd": self.impulsion})

    def loop(self):
        maintenant = time.time()
        # les liens arrivent dans l'ordre des crappy.link : Machine puis caméras
        for lien in self.recv_all_data_raw():
            if "position" in lien:
                for p in lien["position"]:
                    try:
                        self.position = float(p)
                    except (TypeError, ValueError):
                        pass
            elif "t(s)" in lien:
                self.images += len(lien["t(s)"])

        z = self.z_list[self.i]
        if self.etat == "deplacement":
            ecoule = maintenant - self.t_ordre
            if self.position is not None:
                proche = abs(self.position - z) <= self.tolerance
                if not proche:
                    self.depuis_arrivee = None
                elif self.depuis_arrivee is None:
                    self.depuis_arrivee = maintenant
                arrive = proche and maintenant - self.depuis_arrivee >= self.stabilisation
                if not arrive and ecoule > 2 * self.t_prevu + 20:
                    print(f"ATTENTION : Z = {z:g} mm non atteint (lu {self.position:.3f} mm) "
                          "après le temps prévu : photo prise quand même", flush=True)
                    arrive = True
            else:   # pas de position lue : temps de trajet prévu + marge
                arrive = ecoule >= self.t_prevu + 2 + self.stabilisation
            if arrive:
                self._declencher()

        elif self.etat == "photo":
            if self.images >= self.attendues:
                pos = "" if self.position is None else f"{self.position:.4f}"
                self.lignes.append([self.i + 1, z, pos, f"{maintenant - self.t0:.3f}"])
                print(f"   photo prise à Z = {pos or '?'} mm (consigne {z:g})", flush=True)
                self.z_prec = z
                self.i += 1
                self.essais = 0
                if self.i >= len(self.z_list):
                    self._ecrire()
                    print("Acquisition terminée : tous les plans sont photographiés", flush=True)
                    self.stop()
                    return
                self._aller(self.i)
            elif maintenant - self.t_photo > self.delai_image:
                self.essais += 1
                if self.essais <= 2:
                    print(f"ATTENTION : pas d'image après {self.delai_image:.0f} s au plan "
                          f"{self.i + 1}, nouvelle impulsion ({self.essais}/2)", flush=True)
                    self._declencher()
                else:
                    print(f"ERREUR : aucune image au plan {self.i + 1} (Z = {z:g} mm) : "
                          "acquisition arrêtée (déclenchement FT232R ou caméra)", flush=True)
                    self._ecrire()
                    self.stop()

    def _ecrire(self):
        self.dossier.mkdir(parents=True, exist_ok=True)
        with open(self.dossier / FICHIER_POSITIONS, "w", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["plan", "z_consigne_mm", "z_lu_mm", "t_s"])
            w.writerows(self.lignes)

    def finish(self):
        if self.lignes:
            self._ecrire()


def bloc_cameras(delai_ms=3000, **kw):
    """DualXiAPICamera de calib_crappy_V2, pilotée par le séquenceur : la caméra
    ne lit une image QUE lorsqu'une impulsion vient d'être envoyée (label 'cmd'),
    avec un délai borné. Avant, elle attendait en boucle avec un délai court, et
    xiAPI affichait « xiGetImage Finished with Error:10 » (délai dépassé) à chaque
    tour pendant les déplacements du plateau. Une paire n'est enregistrée que si
    les DEUX images arrivent."""
    from ximea import xiapi
    from calib_crappy_V2 import DualXiAPICamera

    class CamerasCalibration(DualXiAPICamera):

        def prepare(self):
            super().prepare()
            self.derniere_impulsion = 0
            for cam in (self.cam_right, self.cam_left):
                try:        # les délais dépassés sont gérés ici : pas de message xiAPI
                    cam.set_debug_level("XI_DL_FATAL")
                except Exception:
                    pass

        def _lire(self, cam, img):
            try:
                cam.get_image(img, timeout=delai_ms)
                return True
            except xiapi.Xi_error:
                return False

        def loop(self):
            import os
            from datetime import datetime
            import imageio.v3 as iio
            if self.t_start is None:
                self.t_start = time.time()
            d = self.recv_last_data(fill_missing=False)
            n_imp = d.get("cmd", 0)
            if not n_imp or n_imp <= self.derniere_impulsion:
                return                      # pas de nouvelle impulsion : rien à lire
            self.derniere_impulsion = n_imp
            ok_d = self._lire(self.cam_right, self.img_right)
            ok_g = self._lire(self.cam_left, self.img_left)
            if not (ok_d and ok_g):
                manque = " et ".join(c for c, ok in (("droite", ok_d), ("gauche", ok_g)) if not ok)
                print(f"ATTENTION : pas d'image {manque} pour l'impulsion {n_imp} "
                      f"({delai_ms / 1000:.0f} s) : paire ignorée", flush=True)
                return
            droite = self.img_right.get_image_data_numpy()
            gauche = self.img_left.get_image_data_numpy()
            maintenant = time.time()
            ecoule = maintenant - self.t_start
            dt = datetime.fromtimestamp(maintenant)
            for img, dossier, writer, n in (
                    (droite, self.save_folder_right, self.csv_right_writer, self.counter_right),
                    (gauche, self.save_folder_left, self.csv_left_writer, self.counter_left)):
                iio.imwrite(os.path.join(dossier, f"{n:06d}__{ecoule:.3f}.tiff"), img)
                writer.writerow([n, maintenant, ecoule, dt.isoformat(), f"{dt.microsecond:06d}"])
            self.counter_right += 1
            self.counter_left += 1
            self.send({"t(s)": maintenant})

    return CamerasCalibration(**kw)


_PLATEAU = []


def enregistrer_plateau():
    """Actuator crappy « PlateauCalibration » : comme moteur.Printer, mais après
    l'origine (G28) le plateau va directement à z_init (la hauteur de départ de
    la calibration) au lieu de Z = 70, avec une attente bornée (Printer.open
    attendait sans limite une égalité exacte)."""
    if _PLATEAU:
        return _PLATEAU[0]
    import serial
    import moteur

    class PlateauCalibration(moteur.Printer):

        def __init__(self, port="/dev/ttyACM0", baudrate=115200, z_init=70.0):
            super().__init__(port=port, baudrate=baudrate)
            self.z_init = float(z_init)

        def open(self):
            self.ser = serial.Serial(self.port, self.baudrate)
            self.ser.write(b"M999\r\n")
            self.abscoord()
            self.backtozero()
            self.set_position(pos=self.z_init, speed=150)
            t0 = time.time()
            while time.time() - t0 < 180:
                p = self.get_position()
                if p is not None and abs(p - self.z_init) < 0.05:
                    break
                time.sleep(0.01)
            else:
                print(f"ATTENTION : plateau pas à Z = {self.z_init:g} après 3 min", flush=True)

    _PLATEAU.append(PlateauCalibration)
    return PlateauCalibration
