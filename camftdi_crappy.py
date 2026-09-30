#echo 0|sudo tee /sys/module/usbcore/parameters/usbfs_memory_mb

import crappy
import time
import ft232R
import os
import pathlib
import subprocess
import imageio.v3 as iio
from crappy.blocks.meta_block.block import Block
from crappy import start
from datetime import datetime
from ximea import xiapi
import csv

class DualXiAPICamera(Block):
    def __init__(self, serial_right, serial_left, save_folder_right, save_folder_left,
                 exposure_right=41389, exposure_left=28757, trigger='Free run',
                 timeout=5000, **kwargs):

        super().__init__(**kwargs)
        self.serial_right = serial_right
        self.serial_left = serial_left
        self.save_folder_right = save_folder_right
        self.save_folder_left = save_folder_left
        self.exposure_right = exposure_right
        self.exposure_left = exposure_left
        self.trigger = trigger
        self.timeout = timeout

        self.done = False

        # Fichiers CSV pour stocker les timestamps
        self.csv_file_right = os.path.join(self.save_folder_right, "metadata.csv")
        self.csv_file_left  = os.path.join(self.save_folder_left, "metadata.csv")

    def prepare(self):
        os.makedirs(self.save_folder_right, exist_ok=True)
        os.makedirs(self.save_folder_left, exist_ok=True)

        # Créer le CSV si nécessaire
        for csv_file in [self.csv_file_right, self.csv_file_left]:
            if not os.path.exists(csv_file):
                with open(csv_file, mode='w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['filename', 'date', 'time'])

        # Caméra droite
        self.cam_right = xiapi.Camera()
        self.cam_right.open_device_by_SN(self.serial_right)
        self.cam_right.set_exposure(self.exposure_right)
        self.cam_right.set_trigger_source('XI_TRG_EDGE_RISING' if self.trigger=='Hardware' else 'XI_TRG_OFF')
        self.cam_right.start_acquisition()
        self.img_right = xiapi.Image()

        # Caméra gauche
        self.cam_left = xiapi.Camera()
        self.cam_left.open_device_by_SN(self.serial_left)
        self.cam_left.set_exposure(self.exposure_left)
        self.cam_left.set_trigger_source('XI_TRG_EDGE_RISING' if self.trigger=='Hardware' else 'XI_TRG_OFF')
        self.cam_left.start_acquisition()
        self.img_left = xiapi.Image()

    def loop(self):
        if self.done:
            return

        # Acquisition
        if self.trigger == 'Hardware':
            self.cam_right.get_image(self.img_right, timeout=self.timeout)
            self.cam_left.get_image(self.img_left, timeout=self.timeout)
        else:
            self.cam_right.get_image(self.img_right, timeout=self.timeout)
            self.cam_left.get_image(self.img_left, timeout=self.timeout)

        # Récupération des données
        data_right = self.img_right.get_image_data_numpy()
        data_left  = self.img_left.get_image_data_numpy()

        timestamp = time.time()
        dt_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))

        filename_right = os.path.join(self.save_folder_right, f"image_right_{int(timestamp)}.tiff")
        filename_left  = os.path.join(self.save_folder_left, f"image_left_{int(timestamp)}.tiff")

        # Sauvegarde images
        iio.imwrite(filename_right, data_right)
        iio.imwrite(filename_left, data_left)

        # Sauvegarde timestamps dans CSV
        with open(self.csv_file_right, mode='a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([filename_right, dt_str.split()[0], dt_str.split()[1]])

        with open(self.csv_file_left, mode='a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([filename_left, dt_str.split()[0], dt_str.split()[1]])

        print(f"Images prises et CSV mis à jour: {dt_str}")

        # Marque comme terminé
        self.done = True

    def finish(self):
        self.cam_right.stop_acquisition()
        self.cam_right.close_device()
        self.cam_left.stop_acquisition()
        self.cam_left.close_device()



if __name__ == "__main__":
  
  
  subprocess.run(
    ["sudo", "tee", "/sys/module/usbcore/parameters/usbfs_memory_mb"],
    input=b"0\n",
    )
  
  date = time.strftime("%Y_%m_%d")  #"2025_07_21"
  sample= "Pro_Grip"
  saving_folder=f'./{date}/{sample}/'
  if os.path.exists(saving_folder) :
    ()
  else :
    P = pathlib.Path(saving_folder)
    pathlib.Path.mkdir(P, parents = True)

  """try:
  	cam_R = crappy.blocks.Camera(camera="XiAPI", 
		                             config=False,
		                             save_images=True,
		                             save_folder=saving_folder+"matrix_calibR/",
		                             img_shape=(2048,2048), 
		                             img_dtype='uint8',
		                             **{"serial_number": "14482450",
		                                "exposure_time_us": 38726,
		                                "trigger": "Hardware"})
  	print("Camera 14482450 connected")
  	
  except Exception as e :
  	print("Camera 14482450 is unavailable, so the calibration stopped")
  	print(e)
  	sys.exit()
  	print("Wait 1s")

  try:                                                                                           
  	cam_L = crappy.blocks.Camera(camera="XiAPI", 
                               config=False,
                               save_images=True,                               
                               save_folder=saving_folder+"matrix_calibL/",
                               img_shape=(2048,2048), 
                               img_dtype='uint8', 
                               **{"serial_number": "32482550",
                                  "exposure_time_us": 24339,
                                  "trigger": "Hardware"})
  	print("Camera 32482550 connected")
  	
  except Exception as e :
  	print("Camera 32482550 is unavailable, so the calibration stopped")
  	print(e)
  	sys.exit()"""

  serial_right = "14482450"
  serial_left  = "32482550"
  save_folder_right = os.path.join(saving_folder, "matrix_calibR")
  save_folder_left  = os.path.join(saving_folder, "matrix_calibL")

  camera_block = DualXiAPICamera(
      serial_right=serial_right,
      serial_left=serial_left,
      save_folder_right=save_folder_right,
      save_folder_left=save_folder_left,
      exposure_right=38726,
      exposure_left=24339,
      trigger='Hardware',  # ou 'Hardware' si tu as un trigger externe
  )
                                                                                             
  ftdi = crappy.blocks.IOBlock('Ft232r', cmd_labels=['cmd'], spam=False, direction=0b00000100, URL='ftdi://ftdi:232:FTU7DIHC/1')

  gen_ft = crappy.blocks.Generator([{'type': 'Cyclic', 
                                     'value1': 1, 'condition1': 'delay=0.05',
                                     'value2': 0, 'condition2': 'delay=0.05', 'cycles': 1}], cmd_label='cmd')
                                     
#  gen_ft2 = crappy.blocks.Generator([{'type': 'Constant',
#                                     'value': 1,
#                                     'condition': 'delay=0.5'}], freq=10, spam=True)                                   

  crappy.link(gen_ft, ftdi)
  crappy.start()

