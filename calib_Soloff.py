import matplotlib.pyplot as plt
from glob import glob
import time
import numpy as np
import cv2
from Pycaso import pattern
from Pycaso import data_library as data
from Pycaso import pycaso as pcs
from Pycaso import solve_library as solvel
import shutil
import os


def move_metadata(mesure_path : str):

	""" Automatically move the metadata files form the images folders to their parent folder 
	
	Args:
	  mesure_path : str
	  		Path to access the Mesure folder, where there are two subfolders
	"""
	
	for subfolder in os.listdir(mesure_path):
		
		path_subfolder = os.path.join(mesure_path, subfolder)
		
		if os.path.isdir(path_subfolder):
		
			camera_side = subfolder.split("_")[-1]
			
			for file in os.listdir(path_subfolder):

				if file=="metadata.csv":
				

					new_filename = "metadata_" + camera_side + ".csv" 
					former_path = os.path.join(path_subfolder, "metadata.csv")
					destination_path = os.path.join(mesure_path, new_filename)
					
					shutil.move(former_path, destination_path)
					print(f"The metadata file was moved from the {camera_side} to the parent folder")
					break
					
		else:
			print("No metadata file found")
					


def calib_Soloff (spform : int,
                  date : str,
                  path_images: str,
                  z_list : list) :


  """ Calibration by Soloff method and 3D plotting of the calibration

  Args :
    spform : int
        Polynomial degree of the Soloff polynome
    date : str
        Date of the test
    path_images : str, optional
      		Allows to select a particular series of images to use from the calibration
    z_list : str
          Known list of the heights used for calibration
    
  """

  saving_folder = f'./{date}/Results_Calib/Spform_{spform}/'

  #Dictionnary ot the calibration, with the calibration folders, and the ChAruCo dimensions
  calibration_dict = {
    'cam1_folder' : os.path.join(path_images, 'video_extenso_right'),
    'cam2_folder' : os.path.join(path_images, 'video_extenso_left'),
    'name' : 'calibration',
    'saving_folder' : saving_folder,
    'ncx' : 12,
    'ncy' : 12,
    'sqr' : 7.5}  #in mm

  """right_reversed_npy = os.path.join(path_images, "right_reversed.npy")
  to_reverse = not os.path.exists(right_reversed_npy)

  if to_reverse : #we only have to reverse the images if the right_reversed.npy file was not created yet (as a proof)
    #reverse the right images, cameras are in mirror
    Liste_image  = sorted(glob(os.path.join(path_images, 'video_extenso_right/'+"0*")))
    #print(Liste_image) 
    for image in Liste_image:
      img = cv2.imread(image)
      img = cv2.rotate(img,cv2.ROTATE_180)
      cv2.imwrite(image,img)
    print("Rotating the pictures by 180°")
    np.save(right_reversed_npy, True)
  else:
    print("No need to reverse the images")"""
      


  print('')
  print(date)
  print('#####       ')
  print('Soloff method - Start calibration')
  print('#####       ')

  #calibration : Soloff constants, magnification
  S_constants0, S_constants, Mag = pcs.Soloff_calibration(z_list = z_list,
                                                          Soloff_pform = spform,
                                                          iterations = 8,
                                                          **calibration_dict)

  coord=load_coordinates(saving_folder+"3D_coordinates/")

  #display the coordinates in the 3D space
  xc=[]
  yc=[]
  zc=[]
  for i in range(len(coord[0])):
    xc.append(coord[0][i])
    yc.append(coord[1][i])
    zc.append(coord[2][i])
  ax = plt.figure().add_subplot(111,projection='3d')
  ax.scatter(xc,yc,zc)
  ax.set_xlabel('X')
  ax.set_ylabel('Y')
  ax.set_zlabel('Z')
  plt.savefig(f'./{date}/Results_Calib/Spform_{spform}/3D_coordinates/'+'Coord3D')
  plt.show()


  np.save(saving_folder+'S_constants0.npy', S_constants0)
  np.save(saving_folder+'S_constants.npy', S_constants)



def load_coordinates(saving_folder, filename="3D_coordinates_Soloff.npy"):
    # dossier du jour
    target_dir = saving_folder
    os.makedirs(target_dir, exist_ok=True)

    target_path = os.path.join(target_dir, filename)
    print(f"\n\nCalling the 3D file from {target_path}\n")

    """# emplacement *fixe* du fichier de référence
    reference_path = os.path.join("/home/essais/Code_Tim/dossier_ref_3d_coordinates", filename)


    # 1. vérifier si le fichier existe déjà dans le dossier du jour
    if not os.path.exists(target_path):
      shutil.copy(reference_path, target_path)
      print(f"3D_coordinates file did not exist, it was copied from the reference folder: {reference_path}")"""
        
    # 3. charger normalement
    return np.load(target_path)
    
    
    
    

if __name__ == "__main__":

    date = "2026_04_13" #time.strftime("%Y_%m_%d") #"2025_12_09"
    spform = 555  #polynomial degree
    image_path = f"{date}/Mvt_Rigide_venv/Mesure"
    move_metadata(image_path)


   # Create the list of z plans
    z_list = []
    for i in range(20) :
      z_list.append(70 -2*i)
    z_list = np.array(z_list)
    print(z_list)


    calib_Soloff(spform, date, image_path, z_list)
    
    
    
