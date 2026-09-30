import matplotlib.pyplot as plt	
import matplotlib.patches as mpatches
import numpy as np
from skimage.filters import threshold_otsu, difference_of_gaussians
from skimage.measure import label, regionprops
from skimage.segmentation import clear_border
from skimage.util import invert
from glob import glob
import os
import pathlib
import cv2
import math
from math import *

plt.close('all')

############################################ DETECTION ANNIE ############################################
############################### Parameters

def CoordCam(path=str, mask=str):
  Liste_image  = sorted(glob(path+"0*")) #list of image
  Liste_image = Liste_image[:]
  Mask = path + mask # mask defined from the first image
  First_img = 1
  Last_img = 2000
  impair_coeff = 1. # impairs the thresh level for global binarization of spots
  Min_area = 10 #used to delete small and fake detected spots
  pix = 10 # pixel margin to the ZOI bounding box
  try:
    image = plt.imread(Liste_image[0])[:,:,0]
    im_mask = plt.imread(Mask)[:,:,0]/255.
  except IndexError:
    image = plt.imread(Liste_image[0])
    im_mask = plt.imread(Mask)[:,:,0]/255.
  ################################ First step : spotting the nodes
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
  vire = np.where((areas <150)|(areas>1800)) # je vire les points trop petits et les trop gros
  boundbox=np.delete(boundbox,vire)
  bar=np.delete(bar,vire)
  areas=np.delete(areas,vire)
  barx = np.delete(barx, vire)
  bary = np.delete(bary, vire)
  ##### Visual checking
  fig, ax = plt.subplots()
  ax.imshow(image, cmap = 'gray')
  for i in range(0,len(boundbox)): # for each ZOI
    gx,gy = bar[i] # barycenter coordinate of each ZOI
    minr, minc, maxr, maxc=boundbox[i] # bbox of each ZOI
    ax.plot(gy,gx, 'ro', markersize=6)
    minr, minc, maxr, maxc = boundbox[i]
    rect = mpatches.Rectangle((minc, minr), maxc - minc, maxr - minr,
                                fill=False, edgecolor='red', linewidth=2)
    ax.add_patch(rect)
  all_px=np.vstack([barx]) # je cree des tableaux dans lequel je stocke les positions en X et en Y
  all_py=np.vstack([bary])
  plt.show()
  return all_px, all_py 	

def f(all_pxl, all_pyl, all_pxr, all_pyr):
  LA_allp = []
  for i in range(len(all_pxl)):
    A_allp = np.zeros((2,len(all_pxl[0]),2))
    for j in range(len(all_pxl[0])):
      A_allp[0][j][0] = all_pyl[i][j]
      A_allp[0][j][1] = all_pxl[i][j]
      A_allp[1][j][0] = all_pyr[i][j]
      A_allp[1][j][1] = all_pxr[i][j]
    LA_allp.append(A_allp)
  return LA_allp
  
# Perspective transformation function
def RtoL_transfo_Matrix(leftpoints, rightpoints):
  pts1 = np.float32([list(rightpoints[0]), list(rightpoints[1]), list(rightpoints[2]), list(rightpoints[3])])
  pts2 = np.float32([list(leftpoints[0]), list(leftpoints[1]), list(leftpoints[2]), list(leftpoints[3])])  
  M = cv2.getPerspectiveTransform(pts1, pts2)
  return M



if __name__ == '__main__' :  


    date = "2025_06_26"



    #all_pxl, all_pyl = CoordCam(f'./{date}/matrix_calibL/', 'maskL_calib.tiff')
    #all_pxr, all_pyr = CoordCam(f'./{date}/matrix_calibR/', 'maskR_calib.tiff')

    all_pxl, all_pyl = CoordCam(f'./{date}/matrix_calibL/', 'maskL.tiff')
    all_pxr, all_pyr = CoordCam(f'./{date}/matrix_calibR/', 'maskR.tiff')

    print(all_pxl, all_pyl, all_pxr, all_pyr)
    Lp = f(all_pxl, all_pyl, all_pxr, all_pyr)

    Template = cv2.imread(saving_folder + 'Template_L.tiff') #Template Gimp à partir de l'image de gauche
    Y_template,X_template = 925,925 #Constantes à modifier en fonction des coordonnées du Template

    Img = cv2.imread(saving_folder + 'Template_R.tiff') #Image de la caméra de droite

    #On fait correspondre le template sur l'image de droite et on observe le décalage entre les deux images
    result = cv2.matchTemplate(Img, Template, cv2.TM_CCOEFF)
    (minVal, maxVal, minLoc, maxLoc) = cv2.minMaxLoc(result)
    (start,startX) = maxLoc
    print(maxLoc)
    CoordTemplate = (Y_template, X_template, Y_template + Template.shape[0], X_template + Template.shape[1])
    print(CoordTemplate)
    Diff = (CoordTemplate[0] - maxLoc[0],CoordTemplate[1] - maxLoc[1])
    print(Diff)

    xr,yr = [],[]
    for i in range(len(Lp[0][0])):
        xr.append(Lp[0][1][i][1])
        yr.append(Lp[0][1][i][0])

    xl,yl=[],[]
    for i in range(len(Lp[0][0])):
        xl.append(Lp[0][0][i][1])
        yl.append(Lp[0][0][i][0])


    # On applique le delta aux coordonnées de droite
    xr2,yr2 = [],[]
    for i in range(N):
        yr2.append(yr[i] + Diff[0])
        xr2.append(xr[i] + Diff[1])


    fig,ax=plt.subplots()
    ax.plot(xr2,yr2,'bo'),ax.plot(xl,yl,'ro')
    plt.show()



#M = RtoL_transfo_Matrix(Lpc[0][0], Lpc[0][1])

#np.save(f'./{date}/transfomatrix', M)
#np.save(f'./{date}/{sample}/transfomatrix', M)
