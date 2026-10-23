"""Calibration stéréo (Lagrange / Soloff / Zernike) basée sur Pycaso."""

import importlib.util
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

    def __init__(self, date, path_images, z_list,
                 left_subfolder="video_extenso_left",
                 right_subfolder="video_extenso_right",
                 reverse=True, show_plot=True):
        self.date = date
        self.path_images = Path(path_images)
        self.z_list = np.asarray(z_list)
        self.left_subfolder = left_subfolder
        self.right_subfolder = right_subfolder
        self.reverse = reverse
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
        keys = ("date", "path_images", "z_list", "reverse", "show_plot")
        return cls(**{k: params[k] for k in keys if k in params})

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
        print(f"\n{self.date}\n#####\n{method} - début de la calibration\n#####")
        if method == "Lagrange":
            return self.lagrange(pform, iterations)
        if method == "Soloff":
            return self.soloff(pform, iterations)
        if method == "Zernike":
            return self.zernike(pform, iterations)
        raise ValueError(f"Méthode inconnue : {method}")

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
        self._reverse_right_images_if_needed()
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

    def _reverse_right_images_if_needed(self):
        """Tourne les images droite de 180° une seule fois (fichier témoin).

        ATTENTION : les .tiff d'origine sont écrasés.
        """
        if not self.reverse:
            return
        flags = [self.path_images / "right_reversed.flag",
                 self.path_images / "right_reversed.npy"]  # ancien témoin
        if any(f.exists() for f in flags):
            print("Images droite déjà retournées (témoin trouvé)")
            return

        right_dir = self.path_images / self.right_subfolder
        images = sorted(glob(str(right_dir / "0*")))
        for p in images:
            img = cv2.imread(p, cv2.IMREAD_UNCHANGED)  # garde le 16 bits
            if img is None:
                raise IOError(f"Impossible de lire {p}")
            cv2.imwrite(p, cv2.rotate(img, cv2.ROTATE_180))
        flags[0].touch()
        print(f"{len(images)} images retournées dans {right_dir}")

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