"""Calibration stéréo (Lagrange / Soloff / Zernike) basée sur Pycaso.

Les hauteurs du plateau (z de départ, pas, z final) sont lues dans hauteurs_calibration.txt,
écrit par le programme d'acquisition dans le dossier des images de calibration (voir
Calibration.lire_hauteurs). Après chaque calcul, une ligne « Calcul … » y est ajoutée.
"""

import importlib.util
import re
import time
import sys
from glob import glob
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np

# pycaso.py fait "import solve_library" (import absolu) :
# le dossier Pycaso doit être dans sys.path avant de l'importer.
_spec = importlib.util.find_spec("Pycaso")
if _spec is not None and _spec.submodule_search_locations:
    _pycaso_dir = list(_spec.submodule_search_locations)[0]
    if _pycaso_dir not in sys.path:
        sys.path.insert(0, _pycaso_dir)

try:
    from Pycaso import pycaso as pcs
except ModuleNotFoundError as err:  # fichier lancé depuis l'intérieur de Pycaso/
    if err.name != "Pycaso":
        raise
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import pycaso as pcs


class Calibration:
    """Calibration stéréo avec trois méthodes interchangeables."""

    METHODS = ("Lagrange", "Soloff", "Zernike")

    # Mire ChArUco (fixe)
    NCX = 12      # nombre de carrés en x
    NCY = 12      # nombre de carrés en y
    SQR = 7.5     # taille d'un carré, en mm

    RESULTS_FOLDER = "results_calib"   # créé à côté du dossier des images

    FICHIER_HAUTEURS = "hauteurs_calibration.txt"    # écrit par l'acquisition, dans path_images

    def __init__(self, path_images, z_list,
                 left_subfolder="video_extenso_left",
                 right_subfolder="video_extenso_right",
                 show_plot=True,
                 date=None):                # pour les titres ; None = celle de hauteurs_calibration.txt
        self.path_images = Path(path_images)
        self.z_list = np.asarray(z_list)
        if date is None:
            date = (self.lire_hauteurs(path_images) or {}).get("date") or self.path_images.resolve().name
        self.date = date
        self.left_subfolder = left_subfolder
        self.right_subfolder = right_subfolder
        self.show_plot = show_plot

    @staticmethod
    def results_dir_for(path_images):
        """Dossier de résultats associé à un dossier d'images.

        .../calib  ->  .../results_calib
        """
        return Path(path_images).resolve().parent / Calibration.RESULTS_FOLDER

    @property
    def results_dir(self):
        return self.results_dir_for(self.path_images)

    @classmethod
    def from_params(cls, params):
        """Construit l'objet à partir du dictionnaire renvoyé par l'interface."""
        keys = ("path_images", "z_list", "show_plot", "date")
        return cls(**{k: params[k] for k in keys if k in params})

    @staticmethod
    def liste_z(z_init, z_final, pas):
        """Hauteurs des plans de z_init à z_final (inclus) par pas (> 0), dans l'ordre des photos.

        ValueError si (z_final − z_init) n'est pas un multiple du pas.
        """
        if not pas > 0:
            raise ValueError("Le pas doit être > 0")
        n = (z_final - z_init) / pas
        if abs(n - round(n)) > 1e-6:
            raise ValueError(f"z_final − z_init ({z_final - z_init:g} mm) n'est pas un multiple du pas ({pas:g} mm)")
        sens = 1 if z_final >= z_init else -1
        z = z_init + sens * pas * np.arange(abs(int(round(n))) + 1)
        return z.astype(int) if np.allclose(z, np.round(z)) else z

    @classmethod
    def fichier_hauteurs(cls, dossier):
        """hauteurs_calibration*.txt dans le dossier des images (ou son parent), sinon None."""
        d = Path(dossier)
        for ou in (d, d.parent):
            if ou.is_dir():
                trouves = sorted(ou.glob("hauteurs_calibration*.txt"))
                if trouves:
                    return trouves[0]
        return None

    @classmethod
    def lire_hauteurs(cls, dossier):
        """Lit hauteurs_calibration.txt : dict ou None s'il n'y en a pas.

        Clés : fichier, date, z_init, pas, z_final, nb_plans, z_table (colonne Z du tableau,
        ou None), mire (ncx, ncy, sqr) ou None. Les valeurs absentes du fichier valent None.
        """
        f = cls.fichier_hauteurs(dossier)
        if f is None:
            return None
        texte = f.read_text(encoding="utf-8", errors="replace")

        def valeur(etiquette, conv=float):
            m = re.search(rf"^{etiquette}[^:\n]*:\s*([-+0-9.,]+)", texte, re.M)
            return conv(m.group(1).replace(",", ".")) if m else None

        date = re.search(r"^Date de calibration\s*:\s*(\S+)", texte, re.M)
        mire = re.search(r"^Mire[^:\n]*:\s*(\d+)\s*x\s*(\d+)[^0-9]+([0-9.,]+)\s*mm", texte, re.M)
        z_table = [float(m.group(1)) for m in
                   re.finditer(r"^\s*\d+\s+([-+0-9.]+)\s+[-+0-9.]+\s+\S+\.tiff?", texte, re.M | re.I)]
        return {"fichier": f,
                "date": date.group(1) if date else None,
                "z_init": valeur("Hauteur de départ"),
                "pas": valeur("Pas"),
                "z_final": valeur("Hauteur finale"),
                "nb_plans": valeur("Nombre de plans", lambda x: int(float(x))),
                "z_table": z_table or None,
                "mire": (int(mire.group(1)), int(mire.group(2)), float(mire.group(3).replace(",", ".")))
                if mire else None}

    def noter_calcul(self, method, pform, iterations):
        """Ajoute « Calcul <date> : <méthode>, degré …» à la fin de hauteurs_calibration.txt."""
        f = self.fichier_hauteurs(self.path_images)
        if f is None:
            return
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(f"Calcul {time.strftime('%Y-%m-%d %H:%M')} : {method}, degré {pform}, "
                     f"{iterations} itérations -> {self.results_dir}\n")

    # ----- préparation des données -----

    def move_metadata(self):
        """Déplace les metadata.csv des sous-dossiers caméra vers path_images.

        video_extenso_left/metadata.csv  ->  metadata_left.csv
        video_extenso_right/metadata.csv ->  metadata_right.csv
        """
        moved = 0
        for sub in self.path_images.iterdir():
            meta = sub / "metadata.csv"
            if sub.is_dir() and meta.exists():
                side = sub.name.split("_")[-1]
                meta.replace(self.path_images / f"metadata_{side}.csv")
                print(f"metadata déplacé depuis {sub.name}")
                moved += 1
        if not moved:
            print("Aucun fichier metadata.csv à déplacer")

    # ----- point d'entrée unique -----

    def run(self, method, pform, iterations):
        """Lance la méthode choisie ('Lagrange', 'Soloff' ou 'Zernike')."""
        if method not in self.METHODS:
            raise ValueError(f"Méthode inconnue : {method}")
        print(f"\n{self.date}\n#####\n{method} - début de la calibration\n#####")
        res = {"Lagrange": self.lagrange, "Soloff": self.soloff, "Zernike": self.zernike}[method](pform, iterations)
        self.noter_calcul(method, pform, iterations)
        return res

    # ----- méthodes de calibration -----

    def lagrange(self, l_pform, iterations=10):
        """Retourne les constantes de Lagrange (et les sauve en .npy)."""
        out = self._prepare(f"Lpform_{l_pform}")
        L_constants, _mag = pcs.Lagrange_calibration(
            z_list=self.z_list, Lagrange_pform=l_pform, plotting=False,
            iterations=iterations, **self._cdict(out))
        np.save(out / "L_constants.npy", L_constants)
        self._plot_and_save_3d(out, "Lagrange")
        return L_constants

    def soloff(self, spform, iterations=8):
        """spform parmi 111, 221, 222, 332, 333, 443, 444, 554, 555.
        Retourne (S0, S)."""
        out = self._prepare(f"Spform_{spform}")
        S0, S, _ = pcs.Soloff_calibration(
            z_list=self.z_list, Soloff_pform=spform, iterations=iterations,
            **self._cdict(out))
        np.save(out / "S_constants0.npy", S0)
        np.save(out / "S_constants.npy", S)
        self._plot_and_save_3d(out, "Soloff")
        return S0, S

    def zernike(self, nZ, iterations=9):
        """Retourne les constantes de Zernike A."""
        out = self._prepare(f"nZ_{nZ}")
        A, _ = pcs.Zernike_calibration(
            z_list=self.z_list, Zernike_pform=nZ, iterations=iterations,
            plotting=False, **self._cdict(out))
        np.save(out / "A_Zernike.npy", A)
        self._plot_and_save_3d(out, "Zernike")
        return A

    # ----- helpers internes -----

    def _prepare(self, tag):
        out = self.results_dir / tag
        out.mkdir(parents=True, exist_ok=True)
        return out

    def _cdict(self, out):
        """Dictionnaire attendu par les fonctions de calibration Pycaso."""
        return {
            "cam1_folder": str(self.path_images / self.left_subfolder),
            "cam2_folder": str(self.path_images / self.right_subfolder),
            "name": "calibration",
            "saving_folder": str(out) + "/",
            "ncx": self.NCX, "ncy": self.NCY, "sqr": self.SQR,
        }


    def _plot_and_save_3d(self, out, method_name):
        """Trace les coordonnées 3D calculées par Pycaso et sauve la figure."""
        coord_dir = out / "3D_coordinates"
        target = coord_dir / f"3D_coordinates_{method_name}.npy"
        if not target.exists():
            found = sorted(coord_dir.glob("*.npy"))
            if not found:
                print(f"Aucune coordonnée 3D trouvée dans {coord_dir}")
                return None
            target = found[0]
        print(f"\nChargement des coordonnées 3D : {target}\n")
        coord = np.load(target)

        ax = plt.figure().add_subplot(111, projection="3d")
        ax.scatter(coord[0], coord[1], coord[2])
        ax.set_xlabel("X"); ax.set_ylabel("Y"); ax.set_zlabel("Z")
        ax.set_title(f"{method_name} - {self.date}")
        plt.savefig(coord_dir / f"Coord3D_{method_name}")
        if self.show_plot:
            plt.show()
        else:
            plt.close()
        return coord