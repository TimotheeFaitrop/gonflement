"""Détection des taches sur la première image, puis suivi image par image.

Convention : px = ligne (vertical), py = colonne (horizontal), comme dans
l'ancien CoordCa10 (fichiers all_pxl.npy, all_pyl.npy, ...).
"""
import os
import glob
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from skimage.filters import threshold_otsu, difference_of_gaussians
from skimage.measure import label, regionprops
from skimage.util import invert


class SuiviTaches:
    """Détecte les taches d'une caméra sur la première image et les suit ensuite.

    Les valeurs par défaut sont dans DetectionSpots.__init__, qui crée cet objet.
    """

    def __init__(self, pix, taille_min_pix, taille_max_pix,
                 max_images_a_considerer, w_spots, figures_suivi):
        self.pix = pix
        self.taille_min_pix = taille_min_pix
        self.taille_max_pix = taille_max_pix
        self.max_images_a_considerer = max_images_a_considerer
        self.w_spots = w_spots
        self.figures_suivi = figures_suivi

    # ----- point d'entrée -----

    def suivre_camera(self, dossier_images, nom_masque, dossier_figures):
        """Détecte les taches sur la première image puis les suit sur les suivantes.

        Renvoie all_px (lignes), all_py (colonnes) de forme (images, taches),
        et le nombre de taches encore suivies à chaque image.
        """
        os.makedirs(dossier_figures, exist_ok=True)
        images = sorted(glob.glob(os.path.join(dossier_images, "[0-9]*")), key=self.numero_image)
        if not images:
            raise FileNotFoundError(f"Aucune image dans {dossier_images}")
        masque = self.lire_gris(os.path.join(dossier_images, nom_masque)) / 255.0

        image = self.lire_gris(images[0])
        centres, boites = self.detecter_taches(image, masque)
        print(f"{len(centres)} taches détectées sur la première image")
        self.figure_taches(image, centres, boites, "Image 0 - taches détectées",
                           os.path.join(dossier_figures, "img_000000.svg"))

        n_images = min(len(images), self.max_images_a_considerer)
        lignes, colonnes, nb_points = [centres[:, 0].copy()], [centres[:, 1].copy()], [len(centres)]
        for j in range(1, n_images):
            print(f"Suivi : image {j} / {n_images - 1}", end="\r")
            img = self.filtre_taches(self.lire_gris(images[j]))
            for i in range(len(centres)):
                if np.isnan(centres[i, 0]):
                    continue                                  # tache déjà perdue
                c, b = self.retrouver_tache(img, centres[i], boites[i])
                if c is None:
                    centres[i], boites[i] = np.nan, np.nan    # tache perdue pour la suite
                else:
                    centres[i], boites[i] = c, b
            lignes.append(centres[:, 0].copy())
            colonnes.append(centres[:, 1].copy())
            nb_points.append(int(np.sum(~np.isnan(centres[:, 0]))))
            if self.figures_suivi:
                self.figure_taches(img, centres, boites, f"Image {j} - suivi des taches",
                                   os.path.join(dossier_figures, f"img_{j:06d}.svg"))
        print(f"\n{nb_points[-1]} taches encore suivies sur la dernière image (sur {len(centres)})")
        return np.array(lignes), np.array(colonnes), nb_points

    # ----- détection et suivi -----

    def filtre_taches(self, image):
        """Différence de gaussiennes : fait ressortir les taches en clair."""
        dog = difference_of_gaussians(image, 5, 6)
        return dog if self.w_spots else invert(dog)

    def detecter_taches(self, image, masque):
        """Taches de la première image : centres (ligne, colonne) et boîtes englobantes."""
        img = self.filtre_taches(image)
        seuil = threshold_otsu(img[masque == 1])
        binaire = img > seuil
        binaire[masque == 0] = 0
        taches = [r for r in regionprops(label(binaire))
                  if self.taille_min_pix <= r.area <= self.taille_max_pix]
        centres = np.array([r.centroid for r in taches], dtype=float).reshape(-1, 2)
        boites = np.array([r.bbox for r in taches], dtype=float).reshape(-1, 4)
        return centres, boites

    def retrouver_tache(self, img, centre, boite):
        """Cherche la tache dans sa boîte agrandie de `pix` pixels.

        Garde la tache la plus proche de sa position précédente (et non la plus grosse),
        pour ne pas sauter sur une tache voisine. Renvoie (centre, boite) ou (None, None).
        """
        pix = self.pix
        minr, minc, maxr, maxc = (int(v) for v in boite)
        minr, minc = max(minr, pix), max(minc, pix)
        r0, c0 = minr - pix, minc - pix
        zone = img[r0:maxr + pix, c0:maxc + pix]
        if zone.size == 0:
            return None, None
        regions = regionprops(label(zone > threshold_otsu(zone)))
        if not regions:
            return None, None
        candidates = [r for r in regions if r.area >= self.taille_min_pix / 2] or regions
        prec = (centre[0] - r0, centre[1] - c0)
        r = min(candidates, key=lambda reg: (reg.centroid[0] - prec[0])**2 + (reg.centroid[1] - prec[1])**2)
        b = r.bbox
        return (np.array([r0 + r.centroid[0], c0 + r.centroid[1]]),
                np.array([r0 + b[0], c0 + b[1], r0 + b[2], c0 + b[3]], dtype=float))

    # ----- outils (ne dépendent pas des paramètres) -----

    @staticmethod
    def numero_image(chemin):
        """Numéro de l'image, lu au début de son nom (000012_4.567.tiff -> 12)."""
        try:
            return int(os.path.basename(chemin).split("_")[0])
        except ValueError:
            return 99999

    @staticmethod
    def lire_gris(chemin):
        """Image en niveaux de gris (premier canal si l'image est en couleur)."""
        image = plt.imread(chemin)
        return image[:, :, 0] if image.ndim == 3 else image

    @staticmethod
    def figure_taches(image, centres, boites, titre, fichier):
        fig, ax = plt.subplots()
        ax.imshow(image, cmap="gray")
        for (r, c), (r0, c0, r1, c1) in zip(centres, boites):
            if np.isfinite(r):
                ax.plot(c, r, "ro", markersize=1)
                ax.add_patch(mpatches.Rectangle((c0, r0), c1 - c0, r1 - r0, fill=False,
                                                edgecolor="red", linewidth=1, alpha=0.5))
        ax.set_title(titre)
        ax.set_axis_off()
        fig.savefig(fichier, dpi=150)
        plt.close(fig)