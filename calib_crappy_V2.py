import crappy
import time
import moteur
import ft232R
import os 
from glob import glob
import numpy as np
from ximea import xiapi
import sys
import time
import subprocess
from crappy.blocks import Block
import imageio.v3 as iio
import csv
from datetime import datetime


class DualXiAPICamera(Block):
    def __init__(self, serial_right, serial_left, save_folder_right, save_folder_left,
                 exposure_right=41389, exposure_left=28757, trigger='Free run',
                 timeout=5000, **kwargs):
        """
        trigger : 'Free run' (continu) ou 'Hardware' (attend un signal externe)
        timeout : temps d'attente max en ms pour un trigger (évite le blocage)
        """
        super().__init__(**kwargs)
        self.serial_right = serial_right
        self.serial_left = serial_left
        self.save_folder_right = save_folder_right
        self.save_folder_left = save_folder_left
        self.exposure_right = exposure_right
        self.exposure_left = exposure_left
        self.trigger = trigger
        self.timeout = timeout
        self.counter_right = 0
        self.counter_left = 0
        self.t_start = None

    def prepare(self):
        os.makedirs(self.save_folder_right, exist_ok=True)
        os.makedirs(self.save_folder_left, exist_ok=True)

        # Caméra droite
        self.cam_right = xiapi.Camera()
        self.cam_right.open_device_by_SN(self.serial_right)
        self.cam_right.set_exposure(self.exposure_right)
        if self.trigger == 'Hardware':
            self.cam_right.set_trigger_source('XI_TRG_EDGE_RISING')
            # Optionnel : s'assurer que le mode GPI est correct
            # self.cam_right.set_gpi_mode('XI_GPI_TRIGGER')
        else:
            self.cam_right.set_trigger_source('XI_TRG_OFF')
        self.cam_right.start_acquisition()
        self.img_right = xiapi.Image()

        # Caméra gauche
        self.cam_left = xiapi.Camera()
        self.cam_left.open_device_by_SN(self.serial_left)
        self.cam_left.set_exposure(self.exposure_left)
        if self.trigger == 'Hardware':
            self.cam_left.set_trigger_source('XI_TRG_EDGE_RISING')
        else:
            self.cam_left.set_trigger_source('XI_TRG_OFF')
        self.cam_left.start_acquisition()
        self.img_left = xiapi.Image()

        # CSV caméra droite
        self.csv_right_path = os.path.join(self.save_folder_right, "metadata.csv")
        self.csv_right_file = open(self.csv_right_path, mode='w', newline='')
        self.csv_right_writer = csv.writer(self.csv_right_file)
        self.csv_right_writer.writerow(["id", "timestamp_epoch", "elapsed_s", "datetime_iso", "subsec"])

        # CSV caméra gauche
        self.csv_left_path = os.path.join(self.save_folder_left, "metadata.csv")
        self.csv_left_file = open(self.csv_left_path, mode='w', newline='')
        self.csv_left_writer = csv.writer(self.csv_left_file)
        self.csv_left_writer.writerow(["id", "timestamp_epoch", "elapsed_s", "datetime_iso", "subsec"])


    def loop(self):

      if self.t_start is None :
        self.t_start = time.time()

      if self.trigger == 'Hardware':
        self.cam_right.get_image(self.img_right, timeout=self.timeout)
        self.cam_left.get_image(self.img_left, timeout=self.timeout)
      else:
        self.cam_right.get_image(self.img_right)
        self.cam_left.get_image(self.img_left)

      data_right = self.img_right.get_image_data_numpy()
      data_left = self.img_left.get_image_data_numpy()

      elapsed = time.time()-self.t_start

      timestamp = time.time()

      # format datetime lisible
      dt = datetime.fromtimestamp(timestamp)
      datetime_iso = dt.isoformat()

      # subsecond (équivalent SubSecTimeOriginal)
      subsec = f"{dt.microsecond:06d}"

      filename_right = os.path.join(self.save_folder_right, f"{self.counter_right:06d}__{elapsed:.3f}.tiff")
      filename_left = os.path.join(self.save_folder_left, f"{self.counter_left:06d}__{elapsed:.3f}.tiff")

      print(f"Picture {self.counter_right:06d} taken")
      iio.imwrite(filename_right, data_right)
      iio.imwrite(filename_left, data_left)

      # écrire CSV droite
      self.csv_right_writer.writerow([
          self.counter_right,
          timestamp,
          elapsed,
          datetime_iso,
          subsec
      ])

      # écrire CSV gauche
      self.csv_left_writer.writerow([
          self.counter_left,
          timestamp,
          elapsed,
          datetime_iso,
          subsec
      ])


      self.counter_right += 1
      self.counter_left += 1

      self.send({'t(s)': time.time()})


    def finish(self):
        self.cam_right.stop_acquisition()
        self.cam_right.close_device()
        self.cam_left.stop_acquisition()
        self.cam_left.close_device()
        self.csv_right_file.close()
        self.csv_left_file.close()




def get_unique_save_path(base_path):
	""" Creates the folder to regroup all data from one calibration
	
	Args:
		base_path : str
			Name of the desired folder at the beginning, which will be adapted to what already 
	
	"""
	
	if not os.path.exists(base_path):
		os.makedirs(base_path)
		return(base_path)
	
	if not os.listdir(base_path):
		return(base_path)
		
	counter=1
	while True:
		new_path = f"{base_path}_{counter:05d}"
		if not os.path.exists(new_path):
			os.makedirs(new_path)
			print(f"The desired path was not available, the new path is {new_path}")
			return(new_path)	
		if not(os.listdir(new_path)):
			print(f"The desired path was not available, the new path is {new_path}")
			return(new_path)			
		counter+=1
		
		
"""def test_camera(serial):
    cam = xiapi.Camera()
    try:
        cam.open_device_by_SN(serial)
        print(f"Caméra {serial} ouverte avec succès")
        time.sleep(0.5)
        cam.close_device()
        time.sleep(2)
        return True
    except xiapi.Xi_error as e:
        print(f"Erreur avec caméra {serial}:", e)
        return False"""


if __name__ == '__main__':
  date = time.strftime("%Y_%m_%d") #"2025_11_20"
  
  subprocess.run(
		["sudo", "tee", "/sys/module/usbcore/parameters/usbfs_memory_mb"],
		input=b"0\n",
		check = True
		)
  print("Emptying the buffer")

  """for sn in ["14482450", "32482550"]:
    if not test_camera(sn):
      sys.exit(f"Camera {sn} indisponible, arrêt du programme")"""


 
  
  saving_path = get_unique_save_path(f"./{date}/Mvt_Rigide/Mesure")
  print(saving_path)


  ftdi = crappy.blocks.IOBlock('Ft232r', cmd_labels=['cmd'], spam=False, direction=0b00000100, URL='ftdi://ftdi:232:FTU7DIHC/1')

  cams = DualXiAPICamera(
    serial_right="14482450",
    serial_left="32482550",
    save_folder_right=os.path.join(saving_path, "video_extenso_right/"),
    save_folder_left=os.path.join(saving_path, "video_extenso_left/"),
    exposure_right=41389,
    exposure_left=28757,
    trigger="Hardware",
    timeout=100000)


  mot = crappy.blocks.Machine([{'type': 'Printer',
                                'mode': 'position',
                                'cmd_label': 'pos',
                                'position_label': 'position',
                                'speed': 100,
                                'port': '/dev/ttyACM0'}],
                                freq=50)

  pas=-10
  time_sync = int(1 + abs(pas / 0.6)) #must be at least 1 + 3/5*max_distance, 5s pour 2mm
  print(time_sync)
  path_mot=[]

  """time_sync = 5 #must be at least 1 + max_distance / 3/5
  path_mot=[]
  pas=-2"""

  for i in range(70, 30, pas):  #ou for i in liste_valeurs:
    path_mot.append({'type': 'Constant',
                      'value': i,
                      'condition': f'delay={time_sync}'})

                      
  gen_ft = crappy.blocks.Generator([{'type': 'Cyclic',
                                    'value1': 0, 'condition1': f'delay={time_sync-1}',
                                    'value2': 1, 'condition2': 'delay=1', 'cycles': len(path_mot)}], cmd_label='cmd')

  gen_mot = crappy.blocks.Generator(path=path_mot, cmd_label='pos')

  graph_mot = crappy.blocks.Grapher(('t(s)','position'))


	
  crappy.link(gen_ft, ftdi)
  crappy.link(gen_mot, mot)
  crappy.link(mot,graph_mot)


  crappy.start()
  	
  	
  	


  
  
  
  
  
  
  
  
  

