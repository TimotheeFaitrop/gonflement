#echo 0|sudo tee /sys/module/usbcore/parameters/usbfs_memory_mb

import crappy
import tridicalddef
import ft232R
import triggerflow
import alicat_flow_crappy
import PolyZernike
import numpy as np

date='2025_04_28'
nZ=8
Lpform=4
method_dict={'Zernike','Lagrange','Soloff'}
method=input('Choose a method\n')
if not method in method_dict:
   raise AssertionError('Wrong method, choose among ' + str(method_dict))
if method=='Lagrange':
   data_folder = f'./{date}/Lpform_{Lpform}/results_calib/'

if method=='Zernike':
   data_folder = f'./{date}/nZ_{nZ}/results_calib/'


if __name__ == "__main__":
  
  ver = crappy.blocks.VideoExtenso(camera='XiAPI',
                                   config=True, 
                                   save_images=True,
                                   save_folder=f'./{date}/video_extenso_right/',
                                   img_shape=(2048,2048),
                                   img_dtype='uint8',
                                   labels=['tr(s)', 'meta_r', 'pix_r', 'eyy_r', 'exx_r'],
                                   white_spots=False,
                                   **{"serial_number": "14482450",
                                      "exposure_time_us": 56229,
                                      "trigger": "Hdw after config",
                                      'timeout':100000})

  vel = crappy.blocks.VideoExtenso(camera='XiAPI', 
                                   config=True,
                                   save_images=True,
                                   save_folder=f'./{date}/video_extenso_left/',
                                   img_shape=(2048,2048),
                                   img_dtype='uint8',
                                   labels=['tl(s)', 'meta_l', 'pix_l', 'eyy_l', 'exx_l'],
                                   white_spots=False,
                                   **{"serial_number": "32482550",
                                      "exposure_time_us": 50000,
                                      "trigger": "Hdw after config",
                                      'timeout':100000})
                                   
  ftdi = crappy.blocks.IOBlock('Ft232r', cmd_labels=['cmd'], spam=False, direction=0b00000100, URL='ftdi://ftdi:232:FTU7DIHC/1')
  
  flow_ali = crappy.blocks.IOBlock('Flow_controller_alicat',
                                   port = "/dev/ttyUSB1",
                                   startbit = 1,
                                   databits = 8,
                                   parity = "N",
                                   stopbits = 1,
                                   errorcheck = "crc",
                                   baudrate = 9600,
                                   #method="RTU",
                                   timeout = 30,
                                   svp = ['Pressure','Mass_flow'],
                                   cmd_labels = ['flowcmd'],
                                   labels = ['t(s)', 'press', 'mass_flow'])
  if method == 'Lagrange':
   trid = tridicalddef.Tridical(direct_A_file = data_folder+'L_constants.npy',
                               transfomatrix_file = f'./{date}/transfomatrix.npy',
                               p_form = Lpform,
                               label = 'triexx')

  elif method == 'Zernike':
    trid = PolyZernike.ControlZernike(Zernikecoeffs = np.load(data_folder+'A_Zernike.npy'),
                               matrix_file = f'./{date}/transfomatrix.npy',
                               label = 'triexx',
                               pform=nZ)
                            
  trigcam = triggerflow.Triggercamexx(cmd_labels=['triexx', 'exxcmd'])
  
  gen_exx = crappy.blocks.Generator([{'type': 'Constant',
                                      'value': 0.15,
                                      'condition': 'path_id>1'}], cmd_label='exxcmd', spam=True)

  #gen_flow = crappy.blocks.Generator([{'type': 'Constant',
                                        #'value': 0.1,
                                        #'condition': 'delay=20'}], cmd_label='flowcmd', spam=True)
  
  gen_dexx = crappy.blocks.Generator([{'type': 'Constant',
                                     'value': 0.1,
                                     'condition':'delay=20'}], cmd_label='dexxcmd', spam=True)
                                   
  p = 800
  i = 100
  d = 0
  
  pid = crappy.blocks.PID(kp=p,
                          ki=i,
                          kd=d,
                          out_max=200,
                          out_min=0,
                          setpoint_label='dexxcmd',
                          input_label='dexx',
                          labels=['t(s)', 'flowcmd'])
    
  rec_tridexx = crappy.blocks.Recorder(file_name = f'./{date}/defexxsvp.txt')
  
  rec_pid = crappy.blocks.Recorder(file_name = f'./{date}/pid.txt')
  
  rec_ali = crappy.blocks.Recorder(file_name = f'./{date}/ali.txt')

  crappy.link(gen_exx, trigcam)
  crappy.link(trid, trigcam)
  crappy.link(trigcam, ftdi)
  crappy.link(trigcam, gen_exx)
  
  crappy.link(vel, trid)
  crappy.link(ver, trid)
  
  crappy.link(gen_dexx, pid)
  crappy.link(trid, pid)
  crappy.link(pid, flow_ali)
  #crappy.link(gen_flow, flow_ali)
  
  crappy.link(trid, rec_tridexx)
  crappy.link(pid, rec_pid)
  #crappy.link(flow_ali, rec_ali)


  crappy.start()
  
