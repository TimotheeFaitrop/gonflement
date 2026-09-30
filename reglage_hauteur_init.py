from serial import Serial
import time 
from ximea import xiapi
import cv2
import numpy as np
import tkinter as tk
import threading
import subprocess
import sys


subprocess.run(
	["sudo", "tee", "/sys/module/usbcore/parameters/usbfs_memory_mb"],
	input=b"0\n",
	check = True
	)


def send_code(dev, cmd):
	dev.write((cmd + '\r\n').encode())
	
	while True:
		line = dev.readline().decode(errors='ignore').strip()
		if line :
			print(">>", line)
		if line.lower().startswith('ok'):
			break

def ximea_available(serial=None):

	""" Tries to connect to a camera, to see if it is avaliable or not
	
	Args:
		serial : str
			  Serial number of the camera to be tested 
	
	"""
	
	cam = xiapi.Camera()
	try:
		cam.open_device_by_SN(serial)
		print(f"Testing camera {serial}") 
		time.sleep(2)
		if cam is not None:
			cam.close_device()	
		print(f"Closed camera {serial}") 
		return True
	except Exception as e:
		print(f"Camera {serial} is unavailable:", e)
		return False

def on_ok():
	global running
	running = False
	root.destroy()

def camera_loop():
	global running
	while running:
		cam_1.get_image(img_1)
		cam_2.get_image(img_2)

		frame_1 = img_1.get_image_data_numpy()
		frame_2 = img_2.get_image_data_numpy()

		display_1 = cv2.resize(frame_1, None, fx=0.33, fy=0.33, interpolation=cv2.INTER_AREA)
		display_2 = cv2.resize(frame_2, None, fx=0.33, fy=0.33, interpolation=cv2.INTER_AREA)

		cv2.imshow("Camera 1", display_1)
		cv2.imshow("Camera 2", display_2)

		cv2.waitKey(1)

	cv2.destroyAllWindows()

dev = Serial('/dev/ttyACM0', baudrate=115200)
running = True

if not ximea_available("32482550"):
	print("Camera 32482550 is unavailable, so the calibration stopped")
	sys.exit()
if not ximea_available("14482450"):
	print("Camera 14482450 is unavailable, so the calibration stopped")
	sys.exit()	




cam_1 = xiapi.Camera()
cam_1.open_device_by_SN("32482550")
cam_1.set_imgdataformat('XI_MONO8')
cam_1.set_exposure(10000) 
cam_1.start_acquisition()
img_1 = xiapi.Image()


cam_2 = xiapi.Camera()
cam_2.open_device_by_SN("14482450")
cam_2.set_imgdataformat('XI_MONO8')
cam_2.set_exposure(10000)
cam_2.start_acquisition()
img_2 = xiapi.Image()

send_code(dev, 'G28 Z0')



root = tk.Tk()
root.title("Validation")
root.geometry("200x100")

btn = tk.Button(root, text="OK", font=("Arial", 16), command=on_ok)
btn.pack(expand=True)

threading.Thread(target=camera_loop, daemon=True).start()
root.mainloop()



send_code(dev, 'G0 X0 Y0 Z20')
send_code(dev, 'G0 X0 Y0 Z120')

dev.close()


cam_1.stop_acquisition()
cam_1.close_device()

cam_2.stop_acquisition()
cam_2.close_device()

cv2.destroyAllWindows()





