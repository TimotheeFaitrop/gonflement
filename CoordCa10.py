import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from skimage.filters import threshold_otsu, difference_of_gaussians
from skimage.measure import label, regionprops
from skimage.segmentation import clear_border
from skimage.util import invert
from glob import glob
import os
import sys
import pathlib
from math import *
import math
import pandas as pd
#import trackpy
import time
#import cv2
#from scipy.spatial import KDTree
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist

import errno


def return_num(s: str):
  try:
    num = int((s.split('/')[-1]).split("_")[0])
    return num
  except:
    num = 99999
    return num


def CoordCam(path=str, mask=str, savefile=str, rotate180=False, graph_verification=False, w_spots = False):
    # Créer le dossier de sauvegarde si nécessaire
    if not os.path.exists(savefile):
        P = pathlib.Path(savefile)
        pathlib.Path.mkdir(P, parents=True)

    # Liste des images
    Liste_image = sorted(glob(path+"[0-9]*"),key=return_num)
    Mask = path + mask

    #Liste des points trouvés
    list_nb_pts=[]

    # Paramètres
    global pix, taille_min_pix, taille_max_pix, max_images_a_considerer



    # Charger la première image
    image_raw = plt.imread(Liste_image[0])

    # Rotation si nécessaire
    if rotate180:
        image_raw = np.rot90(image_raw, 2)  # Rotation 180°

    if image_raw.ndim == 3:
        image = image_raw[:,:,0]
        ndimm = 3
    else:
        image = image_raw
        ndimm = 2

    # Charger le masque
    mask_raw = plt.imread(Mask)
    if mask_raw.ndim == 3:
        im_mask = mask_raw[:,:,0]/255.
    else:
        im_mask = mask_raw/255.

    # Rotation du masque si nécessaire
    if rotate180:
        im_mask = np.rot90(im_mask, 2)

    # First step : spotting the nodes
    if w_spots:
        img = difference_of_gaussians(image, 5, 6)
    else:
        img = invert(difference_of_gaussians(image, 5, 6))

    thresh = threshold_otsu(img[np.where(im_mask == 1)])
    imgb = img>thresh
    imgb[np.where(im_mask ==0)] = 0
    
    #plt.figure(); plt.imshow(imgb);plt.show()
    ################################ Labellization and ZOI detection
    label_img=label(255.*imgb) ### Labellization on binarized invariant minus 2 pixel of borders
    regions = regionprops((label_img))  ### identification of region props in all ROI
    boundbox=np.zeros_like(regions)
    barx=np.zeros_like(regions)
    bary=np.zeros_like(regions)
    bar = np.zeros_like(regions)
    areas=np.zeros_like(regions)
    for i, region in enumerate(regions): # save number of label, initial bbox and barycenter coordinates in vectors
        boundbox[i]=region.bbox
        barx[i], bary[i]=region.centroid
        areas[i]=region.area
        bar[i] = region.centroid

    keep_indices = (areas >= taille_min_pix) & (areas <= taille_max_pix)
    boundbox = boundbox[keep_indices]  # Garde seulement les lignes correspondantes
    bar = bar[keep_indices]
    areas = areas[keep_indices]
    barx = barx[keep_indices]
    bary = bary[keep_indices]

    ##### Visual checking
    fig, ax = plt.subplots()
    ax.imshow(image, cmap = 'gray')
    ax.set_title(f"Image 0 - Spots détectés")
    for i in range(0,len(boundbox)): # for each ZOI
        gx,gy = bar[i] # barycenter coordinate of each ZOI
        minr, minc, maxr, maxc=boundbox[i] # bbox of each ZOI
        ax.plot(gy,gx, 'ro', markersize=1)
        minr, minc, maxr, maxc = boundbox[i]
        rect = mpatches.Rectangle((minc, minr), maxc - minc, maxr - minr,
                                    fill=False, edgecolor='red', linewidth=1)
        ax.add_patch(rect)
    ax.set_axis_off()
    plt.savefig(os.path.join(savefile, f'img_000000.svg'))
    all_px=np.vstack([barx]) # je cree des tableaux dans lequel je stocke les positions en X et en Y
    all_py=np.vstack([bary])
    # plt.show()

    """if rotate180:
        im_mask = np.rot90(im_mask, 2)

    ################################ Première étape : détection des spots
    if w_spots:
        img = invert(difference_of_gaussians(image, 5, 6))
    else:
        img = difference_of_gaussians(image, 5, 6)

    thresh = threshold_otsu(img[np.where(im_mask == 1)])
    imgb = img > thresh
    imgb[np.where(im_mask ==0)] = 0

    # Inverser pour avoir les spots en True
    imgb = 1 - imgb.astype(int)
    imgb = imgb.astype(bool)

    #plt.imshow(img, cmap='gray'); plt.title("DoG inversé"); plt.show()
    #plt.imshow(imgb, cmap='gray'); plt.title("Binaire final"); plt.show()


    ################################ Labellisation et détection des ZOI
    label_img = label(255. * imgb)
    regions = regionprops(label_img)

    # Créer les tableaux pour stocker les informations
    n_regions = len(regions)
    boundbox = np.zeros((n_regions, 4), dtype=float)  # IMPORTANT: initialisation correcte
    barx = np.zeros(n_regions, dtype=float)  # coordonnées Y (lignes)
    bary = np.zeros(n_regions, dtype=float)  # coordonnées X (colonnes)
    areas = np.zeros(n_regions, dtype=float)

    # Remplir les tableaux avec les propriétés des régions
    for i, region in enumerate(regions):
        # ICI: boundbox[i] reçoit les 4 valeurs de la bbox
        boundbox[i] = region.bbox  # (min_row, min_col, max_row, max_col)

        # Centroid donne (centre_y, centre_x)
        centroid_y, centroid_x = region.centroid
        barx[i] = centroid_y  # ligne = y
        bary[i] = centroid_x  # colonne = x

        areas[i] = region.area

    # Filtrer les régions par taille
    keep_indices = (areas >= taille_min_pix) & (areas <= taille_max_pix)
    boundbox = boundbox[keep_indices]  # Garde seulement les lignes correspondantes
    barx = barx[keep_indices]
    bary = bary[keep_indices]
    areas = areas[keep_indices]

    print(boundbox)

    ##### Initialiser les tableaux de suivi

    fig, ax = plt.subplots()
    ax.imshow(image_raw, cmap = 'gray')
    for i in range(0,len(boundbox)): # for each ZOI
        gx,gy = barx[i], bary[i] # barycenter coordinate of each ZOI
        minr, minc, maxr, maxc=boundbox[i] # bbox of each ZOI
        ax.plot(gy,gx, 'ro', markersize=1)
        #minr, minc, maxr, maxc = boundbox[i]
        #rect = mpatches.Rectangle((minc, minr), maxc - minc, maxr - minr,
                                    #fill=False, edgecolor='red', linewidth=2)
        #ax.add_patch(rect)
    if graph_verification:
        plt.show()
    else:
        plt.savefig(os.path.join(savefile, f'img_000000.svg'))
    all_px = barx.reshape(1, -1)  # Forme: (1, n_regions)
    all_py = bary.reshape(1, -1)"""


    for j in np.arange(1, min(len(Liste_image), max_images_a_considerer), 1):
        print(f"\n--- Traitement image {j} ---")
        print(Liste_image[j])


        if ndimm==3:
                image = plt.imread(Liste_image[j])[:,:,0]
        else:
                image = plt.imread(Liste_image[j])

        # Rotation si nécessaire
        if rotate180:
            image = np.rot90(image, 2)

        if w_spots:
            img = difference_of_gaussians(image, 5, 6)
        else:
            img = invert(difference_of_gaussians(image, 5, 6))       

        fig, ax = plt.subplots()
        ax.imshow(img, cmap='gray')
        ax.set_title(f"Image {j} - Suivi des spots")

        for i in range(len(areas)):
            '''
            Using previous image information, we loop over every previous regions.
            Previous bbox are increased and binarized to detect the main spot.
            '''
            if math.isnan(boundbox[i][0]):
                '''
                if a spot has disappeared (out of the frame...)
                barycenter and bbox are set to 'nan' . They are excluded from
                computation at this step.
                New values are set to 'nan' as well
                '''
                barx[i] = np.float('nan')
                bary[i] = np.float('nan')
                boundbox[i] = (np.float('nan'), np.float('nan'), np.float('nan'),np.float('nan'))
            
            else :

                minr, minc, maxr, maxc = boundbox[i] # bbox of each ZOI
                if minr < pix:
                    minr = pix
                if minc < pix:
                    minc = pix
                invar_ZOI = (img[minr-pix:maxr+pix, minc-pix:maxc+pix])
                #if invar_ZOI.ndim == 3:
                    #invar_ZOI = rgb2gray(invar_ZOI)

                thresh = threshold_otsu(invar_ZOI)
                invar_ZOI = invar_ZOI>thresh
                label_img = label(255.*invar_ZOI)
                regions = regionprops((label_img))
                area = [region.area for region in regions]
                if area:
                    '''difference_of_gaussians
                    if spots are detected in the ZOI, the bigger one is selected.
                    Barycenters and bounding box of this spot are then updated
                    '''
                    roi_index = np.where(area==max(area))[0][0]
                    px,py = regions[roi_index].centroid # X,Y coordin. in local ZOI
                    ppx = minr-pix+px # compute X coordinate in global image
                    ppy = minc-pix+py # compute Y coordinate in global image
                    minrr, mincc, maxrr, maxcc = regions[roi_index].bbox
                    boundbox[i] = (minrr+minr-pix, mincc+minc-pix, maxrr+minr-pix, maxcc+minc-pix) # update bbox
                    barx[i] = ppx # update X barycenter coordinate
                    bary[i] = ppy # update Y barycenter coordinate
                    ax.plot(ppy, ppx, 'ro', markersize=1)

                                        # Tracer la ZOI de recherche (rectangle bleu)
                    rect_zoi = mpatches.Rectangle(
                        (minc, minr),
                        maxc - minc,
                        maxr - minr,
                        fill=False, edgecolor='red', linewidth=1, alpha=0.3
                    )
                    ax.add_patch(rect_zoi)

                else:
                    '''
                    if no spot is detected, boundbox and barycenter coordinates
                    are set to 'nan'
                    '''
                    boundbox[i]=(np.float('nan'),np.float('nan'), np.float('nan'),np.float( 'nan'))
                    barx[i]=np.float('nan')
                    bary[i]=np.float('nan')
                ax.axis('off')
                ax.plot(ppy,ppx,'ro', markersize=2)
        # plt.show()
        plt.savefig(savefile + 'img_%06d.svg'%j,dpi=150)
        plt.close()
        all_px = np.vstack([all_px, barx])
        ## add updated X coord of all ZOI to previous ones
        all_py = np.vstack([all_py, bary])

    """
    ##### Deuxième étape : suivi sur les images suivantes
    for j in range(1,min(len(Liste_image),max_images_a_considerer),1):
        print(f"\n--- Traitement image {j} ---")
        print(Liste_image[j])

        # Charger l'image courante
        image_current = plt.imread(Liste_image[j])

        # Rotation si nécessaire
        if rotate180:
            image_current = np.rot90(image_current, 2)

        if ndimm == 3:
            image_current = image_current[:,:,0]

        # Prétraitement

        # ig, ax = plt.subplots(figsize=(10, 10))
        # ax.imshow(image_current, cmap='gray')
        # ax.set_title(f"Image {j} - image init 0")
        # plt.show()

        if w_spots:
            img_processed = invert(difference_of_gaussians(image_current, 5, 6))
        else:
            img_processed = difference_of_gaussians(image_current, 5, 6)
        # ig, ax = plt.subplots(figsize=(10, 10))
        # ax.imshow(img_processed, cmap='gray')
        # ax.set_title(f"Image {j} - diff de gauss invers 1")
        # plt.show()

        img_processed = img_processed>thresh
        # ig, ax = plt.subplots(figsize=(10, 10))
        # ax.imshow(img_processed, cmap='gray')
        # ax.set_title(f"Image {j} - thresh 2")
        # plt.show()

        img_processed = 1 - img_processed.astype(int)
        # ig, ax = plt.subplots(figsize=(10, 10))
        # ax.imshow(img_processed, cmap='gray')
        # ax.set_title(f"Image {j} - inver 3")
        # plt.show()

        img_processed[np.where(im_mask ==0)] = 0
        ig, ax = plt.subplots(figsize=(10, 10))
        ax.imshow(img_processed, cmap='gray')
        ax.set_title(f"Image {j} - raz 4")
        plt.show()


        img_processed = img_processed.astype(bool)

        # Figure pour le suivi
        fig, ax = plt.subplots(figsize=(10, 10))
        ax.imshow(image_current, cmap='gray')
        ax.set_title(f"Image {j} - Suivi des spots")
        spots_trouves = 0

        for i in range(len(boundbox)):
            # Vérifier si le spot était déjà perdu
            if np.any(np.isnan(boundbox[i])):
                continue

            # Récupérer la bbox précédente
            minr, minc, maxr, maxc = boundbox[i]


            # Étendre la ZOI avec la marge 'pix'
            h, w = img_processed.shape
            minr_ext = max(0, int(minr))
            minc_ext = max(0, int(minc))
            maxr_ext = min(h, int(maxr))
            maxc_ext = min(w, int(maxc))

            if maxr_ext-minr_ext < pix:
                center_r = (maxr_ext+minr_ext)//2
                minr_ext = max(0, center_r - pix//2)
                maxr_ext = min(h, center_r + pix//2)

            if maxc_ext-minc_ext < pix:
                center_c = (maxc_ext+minc_ext)//2
                minc_ext = max(0, center_c - pix//2)
                maxc_ext = min(w, center_c + pix//2)


            # Extraire la ZOI étendue
            zoi = img_processed[minr_ext:maxr_ext, minc_ext:maxc_ext]

            if zoi.size == 0:
                # Marquer comme perdu
                boundbox[i] = [np.nan, np.nan, np.nan, np.nan]
                barx[i] = np.nan
                bary[i] = np.nan
                continue

            # Binarisation locale
            try:
                thresh_local = threshold_otsu(zoi)
                zoi_bin = zoi > thresh_local

                # Labellisation dans la ZOI
                label_zoi = label(255. * zoi_bin)
                regions_zoi = regionprops(label_zoi)


                if regions_zoi:
                    # Prendre la plus grande région
                    areas_zoi = [r.area for r in regions_zoi]
                    idx_max = np.argmax(areas_zoi)
                    region_zoi = regions_zoi[idx_max]

                    # Mettre à jour le centroid
                    centroid_y_local, centroid_x_local = region_zoi.centroid

                    # Convertir en coordonnées globales
                    centroid_y_global =  centroid_y_local + minr_ext
                    centroid_x_global =  centroid_x_local + minc_ext

                    # Mettre à jour la bbox (coordonnées globales)
                    minr_local, minc_local, maxr_local, maxc_local = region_zoi.bbox
                    boundbox[i] = [
                        minr_ext + minr_local,
                        minc_ext + minc_local,
                        minr_ext + maxr_local,
                        minc_ext + maxc_local
                    ]

                    barx[i] = centroid_y_global  # y
                    bary[i] = centroid_x_global  # x

                    # Tracer le spot trouvé
                    ax.plot(centroid_x_global, centroid_y_global, 'ro', markersize=3)

                    # Tracer la ZOI de recherche (rectangle bleu)
                    rect_zoi = mpatches.Rectangle(
                        (minc_ext, minr_ext),
                        maxc_ext - minc_ext,
                        maxr_ext - minr_ext,
                        fill=False, edgecolor='blue', linewidth=1, alpha=0.3
                    )
                    ax.add_patch(rect_zoi)

                    spots_trouves += 1

                else:
                    # Aucune région trouvée
                    boundbox[i] = [np.nan, np.nan, np.nan, np.nan]
                    barx[i] = np.nan
                    bary[i] = np.nan

            except:
                # En cas d'erreur (par ex., image uniforme)
                boundbox[i] = [np.nan, np.nan, np.nan, np.nan]
                barx[i] = np.nan
                bary[i] = np.nan


        # Configuration finale du graphique
        ax.set_xlim(0, w)
        ax.set_ylim(h, 0)
        ax.set_xlabel('Colonne (x)')
        ax.set_ylabel('Ligne (y)')
        ax.set_title(f"Image {j} - {spots_trouves}/{len(boundbox)} spots trouvés")
        plt.tight_layout()
        plt.savefig(os.path.join(savefile, f'img_{j:06d}.svg'), dpi=150, bbox_inches='tight')
        #plt.show()
        plt.close()

        # Mise à jour des historiques
        all_px = np.vstack([all_px, barx])
        all_py = np.vstack([all_py, bary])
        list_nb_pts.append(spots_trouves)


    print(f"\n=== RÉSUMÉ ===")
    print(f"Nombre total d'images traitées: {all_px.shape[0]}")
    print(f"Nombre de spots suivis: {all_px.shape[1]}")

    # Vérifier combien de points restent à la fin
    non_nan_at_end = np.sum(~np.isnan(all_px[-1]))
    print(f"dont {non_nan_at_end} restants à la fin")

    return all_px, all_py, list_nb_pts"""
    return all_px, all_py, list_nb_pts

def f(all_pxl, all_pyl, all_pxr, all_pyr):
  LA_allp = []
  print("PXL", len(all_pxl[0]))
  print("PYL", len(all_pyl[0]))
  print("PXR", len(all_pxr[0]))
  print("PYR", len(all_pyr[0]))

  for i in range(len(all_pyl)):
    A_allp = np.zeros((2,len(all_pyl[0]),2))
    for j in range(len(all_pyl[0])):
      A_allp[0][j][0] = all_pyl[i][j]
      A_allp[0][j][1] = all_pxl[i][j]
      A_allp[1][j][0] = all_pyr[i][j]
      A_allp[1][j][1] = all_pxr[i][j]
    LA_allp.append(A_allp)
  return LA_allp


def f_optimized(all_pxl, all_pyl, all_pxr, all_pyr, mapping=None):
    """
    Combine les coordonnées des deux caméras.
    Si mapping est fourni, organise selon l'appariement.
    Sinon, remplit avec NaN pour gérer les nombres différents de points.
    """
    # Convertir en tableaux numpy 2D si nécessaire
    all_pxl = np.array(all_pxl) if isinstance(all_pxl, list) else all_pxl
    all_pyl = np.array(all_pyl) if isinstance(all_pyl, list) else all_pyl
    all_pxr = np.array(all_pxr) if isinstance(all_pxr, list) else all_pxr
    all_pyr = np.array(all_pyr) if isinstance(all_pyr, list) else all_pyr

    print(f"Shapes dans f_optimized: all_pxl={all_pxl.shape}, all_pyl={all_pyl.shape}, all_pxr={all_pxr.shape}, all_pyr={all_pyr.shape}")

    n_frames = all_pxl.shape[0]

    if mapping is not None:
        # Utiliser le mapping d'appariement
        n_pairs = len(mapping)
        LA_allp = []

        for i in range(n_frames):
            A_allp = np.full((2, n_pairs, 2), np.nan)  # Remplir avec NaN par défaut

            pair_idx = 0
            for idx_g, idx_d in mapping.items():
                # Vérifier que les indices sont valides et que les points ne sont pas NaN
                if (idx_g < all_pxl.shape[1] and
                    idx_d < all_pxr.shape[1] and
                    not np.isnan(all_pxl[i, idx_g]) and
                    not np.isnan(all_pxr[i, idx_d])):

                    A_allp[0, pair_idx, 0] = all_pyl[i, idx_g]  # x gauche
                    A_allp[0, pair_idx, 1] = all_pxl[i, idx_g]  # y gauche
                    A_allp[1, pair_idx, 0] = all_pyr[i, idx_d]  # x droite
                    A_allp[1, pair_idx, 1] = all_pxr[i, idx_d]  # y droite

                pair_idx += 1

            LA_allp.append(A_allp)
    else:
        # Sans mapping: utiliser tous les points avec NaN pour les points manquants
        n_points_max = max(all_pxl.shape[1], all_pxr.shape[1])
        LA_allp = []

        for i in range(n_frames):
            A_allp = np.full((2, n_points_max, 2), np.nan)  # Remplir avec NaN par défaut

            # Remplir caméra gauche
            for j in range(all_pxl.shape[1]):
                if not np.isnan(all_pxl[i, j]):  # Ne remplir que si le point existe
                    A_allp[0, j, 0] = all_pyl[i, j]  # x gauche
                    A_allp[0, j, 1] = all_pxl[i, j]  # y gauche

            # Remplir caméra droite
            for j in range(all_pxr.shape[1]):
                if not np.isnan(all_pxr[i, j]):  # Ne remplir que si le point existe
                    A_allp[1, j, 0] = all_pyr[i, j]  # x droite
                    A_allp[1, j, 1] = all_pxr[i, j]  # y droite

            LA_allp.append(A_allp)
    # LA_allp = [(np.array(frame[0]), np.array(frame[1])) for frame in LA_allp]
    return LA_allp

def f_matched(all_pxl, all_pyl, all_pxr_corr, all_pyr_corr, mapping):
    """
    mapping : dict { idxL -> idxR } issu de register_and_match
    """
    pairs = list(mapping.items())   # [(idxL, idxR), ...]
    print(pairs)
    n_frames = len(all_pyl)
    n_pairs  = len(pairs)

    print("Nombre de frames :", n_frames)
    print("Nombre de paires appariées :", n_pairs)

    LA_allp = []
    for i in range(n_frames):
        A_allp = np.zeros((2, n_pairs, 2))
        for k, (idxL, idxR) in enumerate(pairs):
            A_allp[0][k][0] = all_pyl[i][idxL]       # y gauche
            A_allp[0][k][1] = all_pxl[i][idxL]       # x gauche
            A_allp[1][k][0] = all_pyr_corr[i][idxR]  # y droite (corrigé)
            A_allp[1][k][1] = all_pxr_corr[i][idxR]  # x droite (corrigé)
        LA_allp.append(A_allp)

    return LA_allp



# Convertir en tableaux numpy 2D si nécessaire
def ensure_2d_array(arr):
    if isinstance(arr, list):
        # C'est une liste de tableaux 1D, convertir en tableau 2D
        arr = np.array(arr)
    elif isinstance(arr, np.ndarray):
        if arr.ndim == 1:
            # C'est un tableau 1D, le convertir en 2D (1, n)
            arr = arr.reshape(1, -1)
        elif arr.ndim == 2:
            # Déjà 2D, rien à faire
            pass
    return arr

# Fonction pour appliquer la rotation inverse
def apply_inverse_rotation_180(coord_x, coord_y, img_h, img_w):
    """Applique la rotation inverse de 180° aux coordonnées."""
    # Les coordonnées ont été obtenues dans une image tournée de 180°
    # Pour les ramener dans le repère original, on applique à nouveau une rotation de 180°
    # (car deux rotations de 180° s'annulent)
    coord_x_orig = img_w - coord_x - 1
    coord_y_orig = img_h - coord_y - 1
    return coord_x_orig, coord_y_orig



def estimate_translation_by_voting(L, R, bin_size=5.0):
    """
    Dominant translation t such that R + t ≈ L, without any correspondences.
    L, R : (N, 2) and (M, 2) arrays of (x, y) points.
    """
    dx = (L[:, 0][:, None] - R[:, 0][None, :]).ravel()
    dy = (L[:, 1][:, None] - R[:, 1][None, :]).ravel()

    nx = max(1, int((dx.max() - dx.min()) / bin_size))
    ny = max(1, int((dy.max() - dy.min()) / bin_size))

    H, xe, ye = np.histogram2d(dx, dy, bins=[nx, ny])
    i, j = np.unravel_index(H.argmax(), H.shape)
    tx = 0.5 * (xe[i] + xe[i + 1])
    ty = 0.5 * (ye[j] + ye[j + 1])
    return np.array([tx, ty])


def hungarian_match(L, R, max_distance):
    """Optimal one-to-one matching with a distance gate."""
    L = np.array(L, dtype=float)
    R = np.array(R, dtype=float)
    C = cdist(L, R)
    ri, ci = linear_sum_assignment(C)
    keep = C[ri, ci] <= max_distance
    return ri[keep], ci[keep], C[ri[keep], ci[keep]]


def fit_affine(src, dst):
    """Least-squares affine: dst ≈ src @ A.T + t. Returns (A, t)."""

    src = np.array(src, dtype=float)
    dst = np.array(dst, dtype=float)

    n = len(src)
    X = np.hstack([src, np.ones((n, 1))])          # (n, 3)
    M, *_ = np.linalg.lstsq(X, dst, rcond=None)    # (3, 2)
    A = M[:2].T                                    # (2, 2)
    t = M[2]                                       # (2,)
    return A, t


def fit_homography(src, dst):
    """DLT homography, returns 3x3 H mapping src -> dst."""
    A = []
    for (x, y), (xp, yp) in zip(src, dst):
        A.append([-x, -y, -1,  0,  0,  0,  x*xp, y*xp, xp])
        A.append([ 0,  0,  0, -x, -y, -1,  x*yp, y*yp, yp])
    _, _, Vt = np.linalg.svd(np.asarray(A))
    H = Vt[-1].reshape(3, 3)
    return H / H[2, 2]


def apply_homography(pts, H):
    ones = np.ones((len(pts), 1))
    p = np.hstack([pts, ones]) @ H.T
    return p[:, :2] / p[:, 2:3]


def register_and_match(L, R,
                       coarse_bin=5.0,
                       gates=(80.0, 30.0, 10.0),
                       model='affine'):
    """
    Robust stereo-marker registration and pair matching using only numpy + scipy.

    L, R  : (N, 2) / (M, 2) point sets already roughly in the same frame
            (e.g. `all_pxl[0]` + `all_pyl[0]`  and  `all_pxr_corr[0]` + `all_pyr_corr[0]`)
    gates : progressively tighter distance thresholds (pixels) for the iterations.
    model : 'affine' (6 dof) or 'projective' (8 dof).

    Returns
    -------
    row_idx, col_idx : indices into L and R of matched pairs
    residuals        : residual distances of matched pairs (after registration)
    T                : final transform that takes R -> L frame
                       ((A, t) if model='affine', H if model='projective')
    R_aligned        : R mapped into L frame
    """
    # ---- (1) coarse translation
    t0 = estimate_translation_by_voting(L, R, bin_size=coarse_bin)
    R_cur = R + t0
    T = ('affine', np.eye(2), t0)    # running transform

    # ---- (2-3) iterate Hungarian + re-fit
    for gate in gates:
        ri, ci, _ = hungarian_match(L, R_cur, max_distance=gate)
        if len(ri) < (4 if model == 'projective' else 3):
            break  # not enough inliers to re-fit, stop refining
        if model == 'affine':
            A, t = fit_affine(R[ci], L[ri])        # fit on ORIGINAL R, not R_cur
            R_cur = R @ A.T + t
            T = ('affine', A, t)
        else:
            H = fit_homography(R[ci], L[ri])
            R_cur = apply_homography(R, H)
            T = ('projective', H)

    # ---- final matching with the tightest gate
    ri, ci, res = hungarian_match(L, R_cur, max_distance=gates[-1])
    return ri, ci, res, T, R_cur


##Identification des points
date = "2026_04_13" # time.strftime("%Y_%m_%d")  # "2025_07_21"
sample= "gonflement" 
mesure = "mesure" 
saving_folder= f'./{date}/{sample}/'
saving_folder_images = f'./{date}/{sample}/{mesure}/'
gauche_calculated = True
droite_calculated = True
pix = 40  # pixel margin to the ZOI bounding box
taille_min_pix = 100
taille_max_pix = 1000
max_images_a_considerer = 82 # faire +1 pour avoir le nombre exact voulu
w_spots = False


if gauche_calculated:
    try:
        all_pxl = np.load(saving_folder + 'all_pxl.npy', allow_pickle=True)
    except:
        raise FileNotFoundError(
            errno.ENOENT, os.strerror(errno.ENOENT), saving_folder + 'all_pxl.npy')
    try:
        all_pyl = np.load(saving_folder + 'all_pyl.npy', allow_pickle=True)
    except:
        raise FileNotFoundError(
            errno.ENOENT, os.strerror(errno.ENOENT), saving_folder + 'all_pyl.npy')
    try:
        nb_pts_g = np.load(saving_folder + 'points_spotted_left.npy', allow_pickle=True)
        nb_pts_g = nb_pts_g.tolist()
    except:
        raise FileNotFoundError(
            errno.ENOENT, os.strerror(errno.ENOENT), saving_folder + 'points_spotted_left.npy')
    print("All files loaded for the left camera")

else:
    # Caméra gauche: pas de rotation
    if not os.path.isfile(saving_folder+f'{mesure}/video_extenso_left/maskL.tiff'):
        raise FileNotFoundError(
            errno.ENOENT, os.strerror(errno.ENOENT), saving_folder + f'{mesure}/video_extenso_left/maskL.tiff')
    print("\n\nSearching points for the left images")
    all_pxl, all_pyl, nb_pts_g = CoordCam(saving_folder_images+'video_extenso_left/',
                                          'maskL.tiff',
                                          saving_folder+'ROI_left/',
                                          rotate180=False,
                                          graph_verification=False,
                                          w_spots=w_spots)
    np.save(saving_folder + 'all_pxl.npy', all_pxl)
    np.save(saving_folder + 'all_pyl.npy', all_pyl)
    np.save(saving_folder + 'points_spotted_left.npy', np.array(nb_pts_g))


if droite_calculated:
    try:
        all_pxr = np.load(saving_folder + 'all_pxr.npy', allow_pickle=True)
    except:
        raise FileNotFoundError(
            errno.ENOENT, os.strerror(errno.ENOENT), saving_folder + 'all_pxr.npy')
    try:
        all_pyr = np.load(saving_folder + 'all_pyr.npy', allow_pickle=True)
    except:
        raise FileNotFoundError(
            errno.ENOENT, os.strerror(errno.ENOENT), saving_folder + 'all_pyr.npy')
    try:
        nb_pts_d = np.load(saving_folder + 'points_spotted_right.npy', allow_pickle=True)
        nb_pts_d = nb_pts_d.tolist()
    except:
        raise FileNotFoundError(
            errno.ENOENT, os.strerror(errno.ENOENT), saving_folder + 'points_spotted_right.npy')
    print("All files loaded for the right camera")
else:
    if not os.path.isfile(saving_folder+f'{mesure}/video_extenso_right/maskR.tiff'):
        raise FileNotFoundError(
            errno.ENOENT, os.strerror(errno.ENOENT), saving_folder + f'{mesure}/video_extenso_right/maskR.tiff')
    # Caméra droite: avec rotation de 180° pour le traitement
    print("\n\nSearching points for the right images")
    all_pxr, all_pyr, nb_pts_d = CoordCam(saving_folder_images+'video_extenso_right/',
                                          'maskR.tiff',
                                          saving_folder+'ROI_right/',
                                          rotate180=False,
                                          graph_verification=False,
                                          w_spots=w_spots)
    np.save(saving_folder + 'all_pxr.npy', all_pxr)
    np.save(saving_folder + 'all_pyr.npy', all_pyr)
    np.save(saving_folder + 'points_spotted_right.npy', np.array(nb_pts_d))



indices_g = range(len(nb_pts_g))
indices_d = range(len(nb_pts_d))

plt.figure()
plt.plot(indices_g, nb_pts_g,'o-', label='Cam gauche')
plt.plot(indices_d, nb_pts_d,'s-', label='Cam droite')
_,_,_,ymax = plt.axis()
ax = plt.gca()
ax.set_ylim([0, ymax])
plt.xlabel("Frame")
plt.ylabel("Nb de points trouvés")
plt.legend()
plt.savefig(os.path.join(saving_folder, f"Number_points_spotted_{max(len(nb_pts_g),len(nb_pts_d))}_iterations.svg"))
plt.close()

print("all_pxr shape :", all_pxr.shape)
print("all_pyr shape :", all_pyr.shape)


# Relire les données pour être sûr
all_pyl = np.load(saving_folder + 'all_pyl.npy', allow_pickle=True)
all_pxl = np.load(saving_folder + 'all_pxl.npy', allow_pickle=True)
all_pyr = np.load(saving_folder + 'all_pyr.npy', allow_pickle=True)
all_pxr = np.load(saving_folder + 'all_pxr.npy', allow_pickle=True)
print(f"Nombre de frames: {len(all_pyl)}")


all_pxl = ensure_2d_array(all_pxl)
all_pyl = ensure_2d_array(all_pyl)
all_pxr = ensure_2d_array(all_pxr)
all_pyr = ensure_2d_array(all_pyr)


# ======================================================
# CORRECTION DES COORDONNÉES ET APPARIEMENT
# ======================================================
print("\n=== VÉRIFICATION DES COORDONNÉES ===")

# Obtenir les dimensions de l'image de droite (originale)
sample_img = plt.imread(sorted(glob(saving_folder_images+'video_extenso_right/[0-9]*'))[0])
h, w = sample_img.shape[:2]
print(f"Dimensions image droite: {h} x {w}")

# Étape 1: Créer des copies corrigées des coordonnées droites
print("Création de copies corrigées des coordonnées droites...")

# Créer des copies
all_pxr_corr = all_pxr.copy()
all_pyr_corr = all_pyr.copy()


plt.figure()
plt.scatter(all_pyl[0], all_pxl[0], s=10, c='red', alpha=0.7, label='Cam gauche')
plt.scatter(all_pyr[0], all_pxr[0], s=10, c='blue', alpha=0.7, label='Cam droite')
plt.legend()
plt.title("Py et Px non corrigés")
plt.show()


# Appliquer la correction de rotation inverse
for i in range(all_pxr_corr.shape[0]):
    for j in range(all_pxr_corr.shape[1]):
        if not np.isnan(all_pxr_corr[i, j]) and not np.isnan(all_pyr_corr[i, j]):
            all_pxr_corr[i, j], all_pyr_corr[i, j] = apply_inverse_rotation_180(
                all_pxr_corr[i, j], all_pyr_corr[i, j], h, w)

plt.figure()
plt.scatter(all_pyl[0], all_pxl[0], s=10, c='red', alpha=0.7, label='Cam gauche')
plt.scatter(all_pyr_corr[0], all_pxr_corr[0], s=10, c='blue', alpha=0.7, label='Cam droite')
plt.legend()
plt.title("Py et Px corrigés V1")
plt.show()



# Work from the inverse-rotated coordinates (already in left-image frame)
vL = ~np.isnan(all_pxl[0].astype(float))       & ~np.isnan(all_pyl[0].astype(float))
vR = ~np.isnan(all_pxr_corr[0].astype(float))  & ~np.isnan(all_pyr_corr[0].astype(float))
"""vR = ~np.isnan(all_pxr[0].astype(float))  & ~np.isnan(all_pyr[0].astype(float))
"""

L = np.column_stack([all_pyl[0][vL], all_pxl[0][vL]])
R = np.column_stack([all_pyr_corr[0][vR], all_pxr_corr[0][vR]])

idxL_orig = np.where(vL)[0]
idxR_orig = np.where(vR)[0]

ri, ci, residuals, T, R_aligned = register_and_match(
    L, R, gates=(80.0, 30.0, 10.0), model='affine'
)

mapping = {int(idxL_orig[i]): int(idxR_orig[j]) for i, j in zip(ri, ci)}

print(mapping)
print(f"Matched pairs : {len(mapping)}")
print(f"Residuals (px): median={np.median(residuals):.2f}, "
      f"max={residuals.max():.2f}")


# 1) Overlay after registration

# img_left = plt.imread(saving_folder_images + 'video_extenso_left/' + "000000__16.065.tiff")
# plt.imshow(img_left, cmap='gray')
plt.scatter(L[:, 0],         L[:, 1],         s=12, c='red',  label='left')
plt.scatter(R_aligned[:, 0], R_aligned[:, 1], s=12, c='blue', marker='x',
            label='right → left frame')
plt.gca().invert_yaxis(); plt.axis('equal'); plt.legend()
plt.title('Post-registration overlay')

# 2) Residual histogram: tight unimodal distribution = success
plt.figure()
plt.hist(residuals, bins=40)
plt.xlabel('residual (px)'); plt.ylabel('count')
plt.title('Matching residuals (want: tight peak near 0)')

# 3) Draw each match as a segment — bad matches stand out immediately
plt.figure()
plt.scatter(L[:, 0], L[:, 1], s=8, c='k')
for i, j in zip(ri, ci):
    plt.plot([L[i, 0], R_aligned[j, 0]], [L[i, 1], R_aligned[j, 1]], 'r-', lw=0.5)
plt.gca().invert_yaxis(); plt.axis('equal')
plt.title('Matching segments')
plt.show()



# Créer Lp avec le mapping - utiliser les données corrigées pour la droite
print("\nCréation de Lp...")
# Lp = f_optimized(all_pxl, all_pyl, all_pxr, all_pyr, mapping=mapping)
# Lp = f(all_pxl, all_pyl, all_pxr, all_pyr)

Lp = f_matched(all_pxl, all_pyl, all_pxr, all_pyr, mapping)


# Vérifier Lp
print(f"\n=== VÉRIFICATION Lp ===")
print(f"Nombre de frames: {len(Lp)}")

# Vérif Lp

path = saving_folder_images+'video_extenso_right/'

Liste_image = sorted(glob(path+"[0-9]*"),key=return_num)


if len(Lp) > 0:
    Left, Right = Lp[0]
    print(f"Frame 0 - Left shape: {Left.shape}")
    print(f"Frame 0 - Right shape: {Right.shape}")

    # Compter les points non-NaN
    valid_left = np.sum(~np.isnan(Left[:, 0]))
    valid_right = np.sum(~np.isnan(Right[:, 0]))
    print(f"Points valides dans Lp[0]: {valid_left} (gauche), {valid_right} (droite)")

    if valid_left > 0:
        print("\nExemples de points dans Lp[0]:")
        for i in range(min(3, valid_left)):
            if not np.isnan(Left[i, 0]):
                print(f"  Point {i}:")
                print(f"    Gauche: x={Left[i, 0]:.1f}, y={Left[i, 1]:.1f}")
                print(f"    Droite: x={Right[i, 0]:.1f}, y={Right[i, 1]:.1f}")

# Sauvegarder Lp (avec données corrigées)
np.save(saving_folder + 'Lp_final.npy', Lp)
print(f"\nLp sauvegardé avec {len(Lp)} frames")

# Sauvegarder aussi le mapping
np.save(saving_folder + 'mapping.npy', mapping)

# Sauvegarder aussi les données corrigées pour référence
np.save(saving_folder + 'all_pxr_corr.npy', all_pxr_corr)
np.save(saving_folder + 'all_pyr_corr.npy', all_pyr_corr)
print("Données corrigées sauvegardées")

print("\n=== TRAITEMENT TERMINÉ ===")




