from glob import glob
from pathlib import Path
import shutil
from Pycaso import pattern
from Pycaso import data_library as data
from Pycaso import solve_library as solvel
from Pycaso import pycaso as pcs
import numpy as np
import cv2
import matplotlib.pyplot as plt


class Calibration:
    """Stereo calibration with three interchangeable methods."""

    def __init__(self, date, path_images, z_list,
                 reference_3d_folder,
                 left_subfolder="video_extenso_left",
                 right_subfolder="video_extenso_right",
                 ncx=12, ncy=12, sqr=7.5, reverse = True):
        self.date = date
        self.path_images = Path(path_images)
        self.z_list = z_list
        self.reference_3d_folder = Path(reference_3d_folder)
        self.left_subfolder = left_subfolder
        self.right_subfolder = right_subfolder
        self.ncx, self.ncy, self.sqr = ncx, ncy, sqr
        self.reverse = reverse
        self._reverse_right_images_if_needed()

    # ----- méthodes de calibration -----

    def soloff(self, spform, iterations=8):
        """
        Perform a Soloff calibration and saves the results of the calibration
        Reference :

        Inputs:
        - spform : (aab) chosen from 111, 221, 222, 332, 333, 443, 444, 554, 555
        - iterations (int) : from 1 to 12 (default 8)

        Returns:
        - 3D coordinates in saving_folder/3D_coordinates/ (computed by Pycaso)
        - S0 : np.ndarray – Constants of the 111 base polynomial.
        - S  : np.ndarray – Constants of the chosen spform (aab) polynomial.
        """

        out = self._make_output_dir(f"Spform_{spform}")
        S0, S, _ = pcs.Soloff_calibration(
            z_list=self.z_list, Soloff_pform=spform, iterations=iterations,
            **self._cdict(out))
        self._plot_and_save_3d(out, "Soloff")
        np.save(out / "S_constants0.npy", S0)
        np.save(out / "S_constants.npy",  S)
        return S0, S

    def zernike(self, nZ, iterations=9, plotting=False):
        """
        Perform a Zernike calibration and saves the results of the calibration
        Reference :

        Inputs:
        - nZ :
        - iterations (int) : from 1 to 12 (default 9)
        - plotting: bool (default False)

        Returns:
        - 3D coordinates in saving_folder/3D_coordinates/ (computed by Pycaso)
        - Zernike A (array)
        """
        out = self._make_output_dir(f"nZ_{nZ}")
        A, _ = pcs.Zernike_calibration(
            z_list=self.z_list, Zernike_pform=nZ, iterations=iterations,
            plotting=plotting, **self._cdict(out))
        self._plot_and_save_3d(out, "Zernike")
        np.save(out / "A_Zernike.npy", A)
        return A

    def lagrange(self, l_pform) :
        """
        Perform a Lagrange calibration and saves the results of the calibration
        Reference :
        Inputs:
        - lpform :

        Returns:
        - 3D coordinates in saving_folder/3D_coordinates/ (computed by Pycaso)
        - Lagrange constants (array)
        """
        out = self._make_output_dir(f"Lpform_{l_pform}")
        #calibration : Lagrange constants, magnification
        L_constants, Mag = pcs.Lagrange_calibration(z_list = self.z_list,
                                                    Lagrange_pform = l_pform,
                                                    plotting = False,
                                                    iterations = 10,
                                                    **self._cdict(out))
        self._plot_and_save_3d(out, "Lagrange")
        np.save(out / "Lagrange_constants.npy", L_constants)
        return L_constants


    # ----- helpers internes -----
    def _make_output_dir(self, tag):
        out = Path(f"{self.reference_3d_folder}/Results_Calib/{self.date}/{tag}/")
        out.mkdir(parents=True, exist_ok=True)
        return out

    def _cdict(self, out):
        """
        Creates the dictionnary used in the Pycaso function : data.pattern_detection
        """
        return {
            "cam1_folder": str(self.path_images / self.right_subfolder),
            "cam2_folder": str(self.path_images / self.left_subfolder),
            "name": "calibration",
            "saving_folder": str(out) + "/",
            "ncx": self.ncx, "ncy": self.ncy, "sqr": self.sqr,
        }

    def _reverse_right_images_if_needed(self):
        """Rotate right camera images by 180° (once, idempotent via flag file).

        WARNING: this overwrites the original .tiff files on disk.
        """
        if not self.reverse:
            print("Rotation disabled (reverse=False)")
            return

        flag = self.path_images / "right_reversed.flag"
        if flag.exists():
            print("Images already rotated (flag found)")
            return

        right_dir = self.path_images / self.right_subfolder
        images = sorted(glob(str(right_dir / "0*")))
        for p in images:
            cv2.imwrite(p, cv2.rotate(cv2.imread(p), cv2.ROTATE_180))
        flag.touch()
        print(f"Rotated {len(images)} images in {right_dir}")

    def _plot_and_save_3d(self, out, method_name):
        """
        Plots and save the 3D coordinates in the absolute basis automatically
        """
        coord_dir = out / "3D_coordinates"
        coord_dir.mkdir(parents=True, exist_ok=True)

        filename = f"3D_coordinates_{method_name}.npy"
        target = coord_dir / filename
        if not target.exists():
            shutil.copy(self.reference_3d_folder / filename, target)
        coord = np.load(target)

        ax = plt.figure().add_subplot(111, projection="3d")
        ax.scatter(coord[0], coord[1], coord[2])
        ax.set_xlabel("X"); ax.set_ylabel("Y"); ax.set_zlabel("Z")
        plt.savefig(coord_dir / f"Coord3D_{method_name}")
        plt.show()

