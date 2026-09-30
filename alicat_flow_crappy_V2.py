
#requirements: pip install pymodbus==3.0.2

import crappy
import time
import pymodbus
from pymodbus.client.serial import ModbusSerialClient
from pymodbus.payload import BinaryPayloadBuilder, BinaryPayloadDecoder
from pymodbus.constants import Endian
import struct
import ft232R
import os
import pathlib
import subprocess
from crappy.blocks import VideoExtenso
from crappy.camera.meta_camera.camera_setting import camera_scale_setting

class FixedVideoExtenso(VideoExtenso):
    """VideoExtenso qui contourne l'erreur 'bounds equal' des caméras XiAPI."""

    def prepare(self) -> None:
        # Sauvegarde du constructeur original
        original_init = camera_scale_setting.CameraScaleSetting.__init__

        def patched_init(self, name, lowest, highest, getter=None, setter=None,
                         default=None, step=None):
            # Ajustement des bornes égales
            if lowest == highest:
                if isinstance(lowest, int):
                    highest = lowest + 1
                else:
                    highest = lowest + 1e-6
                print(f"[FixedVideoExtenso] bounds equal for '{name}', "
                      f"adjusted highest to {highest}")
            original_init(self, name, lowest, highest, getter, setter,
                          default, step)

        # Remplacement temporaire
        camera_scale_setting.CameraScaleSetting.__init__ = patched_init

        try:
            super().prepare()
        finally:
            # Restauration après la préparation
            camera_scale_setting.CameraScaleSetting.__init__ = original_init




if pymodbus.__version__=='3.0.2': ##version à modifier

  class Flow_controller_alicat(crappy.inout.InOut):

    def __init__(self,
                port="/dev/ttyUSB0",
                startbit=1,
                databits=8,
                parity="N",
                stopbits=1,
                errorcheck="crc",
                baudrate=115200,
                method="RTU",
                timeout=3,
                press='absolue',
                svp=[]):

      crappy.inout.InOut.__init__(self)
      self.port = port
      self.startbit = startbit
      self.databits = databits
      self.parity = parity
      self.stopbits = stopbits
      self.errorcheck = errorcheck
      self.baudrate = baudrate
      self.method = method
      self.timeout = timeout
      self.press = press
      self.svp = svp
      self.address_list = {#Dict that contains the registers' adress and count associated to the information you want to get
              "Pressure": [1202,2],
              "Temperature": [1204,2],
              "Volumetric_flow": [1206,2],
              "Mass_flow": [1208,2]}

    def open(self):

      self.client = ModbusSerialClient(port=self.port,
                                      startbit=self.startbit,
                                      databits=self.databits,
                                      parity=self.parity,
                                      stopbits=self.stopbits,
                                      errorcheck=self.errorcheck,
                                      baudrate=self.baudrate,
                                      method=self.method,
                                      timeout=self.timeout)
      self.client.connect()
      if self.press == 'relative':
        response = self.client.read_holding_registers(address=self.address_list['Pressure'][0], count=self.address_list['Pressure'][1], unit=1)
        decoder = BinaryPayloadDecoder.fromRegisters(response.registers, byteorder=Endian.Big, wordorder=Endian.Big)
        self.P0 = decoder.decode_32bit_float()

    def get_data(self):

      data = []
      if self.svp:
        for i in self.svp:
          response = self.client.read_holding_registers(address=self.address_list[i][0], count=self.address_list[i][1], unit=1)
          decoder = BinaryPayloadDecoder.fromRegisters(response.registers, byteorder=Endian.Big, wordorder=Endian.Big)
          value = decoder.decode_32bit_float()
          if i == 'Pressure' and self.press == 'relative':
            data.append(value-self.P0)
          else:
  #        print(i, value)
            data.append(value)
        return [time.time()] + data

    def set_cmd(self, cmd):

      if cmd == None:
        pass
      else:
        builder = BinaryPayloadBuilder(byteorder=Endian.Big, wordorder=Endian.Big)
        builder.add_32bit_float(cmd)
        payload = builder.build()
        self.client.write_registers(address=1009, values=payload, count=2, unit= 1, skip_encode = True)

    def close(self):

      builder = BinaryPayloadBuilder(byteorder=Endian.Big, wordorder=Endian.Big)
      builder.add_32bit_float(0)
      payload = builder.build()
      self.client.write_registers(address=1009, values=payload, count=2, unit= 1, skip_encode = True)
      self.client.close()


# requirements: pip install pymodbus==3.8.6

if pymodbus.__version__=='3.8.6':

  class Flow_controller_alicat(crappy.inout.InOut):

      def __init__(self,
                  port="/dev/ttyUSB0",
                  startbit=1,
                  databits=8,
                  parity="N",
                  stopbits=1,
                  errorcheck="crc",
                  baudrate=115200,
                  method="RTU",
                  timeout=3,
                  press='absolue',
                  svp=[]):

          crappy.inout.InOut.__init__(self)
          self.port = port
          self.startbit = startbit
          self.databits = databits
          self.parity = parity
          self.stopbits = stopbits
          self.errorcheck = errorcheck
          self.baudrate = baudrate
          self.timeout = timeout
          self.press = press
          self.svp = svp
          self.address_list = {  # Dict that contains the registers' address and count associated with the information you want to get
              "Pressure": [1202, 2],
              "Temperature": [1204, 2],
              "Volumetric_flow": [1206, 2],
              "Mass_flow": [1208, 2]
          }

      def open(self):
          # Initialize the ModbusSerialClient without the 'method' argument
          self.client = ModbusSerialClient(
              port=self.port,
              baudrate=self.baudrate,
              stopbits=self.stopbits,
              parity=self.parity,
              timeout=self.timeout
          )

          # Connect to the device
          if not self.client.connect():
              raise Exception(f"Unable to connect to the Modbus device at {self.port}")

          if self.press == 'relative':
              response = self.client.read_holding_registers(address=self.address_list['Pressure'][0],
                                                            count=self.address_list['Pressure'][1], unit=1)
              print(response)
              decoder = BinaryPayloadDecoder.fromRegisters(response.registers, byteorder="big", wordorder="big")
              self.P0 = decoder.decode_32bit_float()

      def get_data(self):
          data = []
          if self.svp:
              for i in self.svp:
                  response = self.client.read_holding_registers(address=self.address_list[i][0],
                                                                count=self.address_list[i][1])
                  decoder = BinaryPayloadDecoder.fromRegisters(response.registers, byteorder="big", wordorder="big")
                  value = decoder.decode_32bit_float()

                  if i == 'Pressure' and self.press == 'relative':
                      data.append(value - self.P0)
                  else:
                      data.append(value)

          return [time.time()] + data

      def set_cmd(self, cmd):
          if cmd is None:
              pass
          else:
              builder = BinaryPayloadBuilder(byteorder="big", wordorder="big")
              builder.add_32bit_float(cmd)
              payload = builder.build()
              self.client.write_registers(address=1009, values=payload)

      def close(self):
          builder = BinaryPayloadBuilder(byteorder="big", wordorder="big")
          builder.add_32bit_float(0)
          payload = builder.build()
          self.client.write_registers(address=1009, values=payload)
          self.client.close()


if pymodbus.__version__=='3.9.0':


  class Flow_controller_alicat(crappy.inout.InOut):

    def __init__(self,
                 port="/dev/ttyUSB0",
                 startbit=1,
                 databits=8,
                 parity="N",
                 stopbits=1,
                 errorcheck="crc",
                 baudrate=115200,
                 timeout=3,
                 press='absolue',
                 svp=[]):

        crappy.inout.InOut.__init__(self)
        self.port = port
        self.startbit = startbit
        self.databits = databits
        self.parity = parity
        self.stopbits = stopbits
        self.errorcheck = errorcheck
        self.baudrate = baudrate
        self.timeout = timeout
        self.press = press
        self.svp = svp
        self.address_list = {
            "Pressure": [1202, 2],
            "Temperature": [1204, 2],
            "Volumetric_flow": [1206, 2],
            "Mass_flow": [1208, 2]
        }

    def open(self):
        self.client = ModbusSerialClient(
            port=self.port,
            baudrate=self.baudrate,
            stopbits=self.stopbits,
            parity=self.parity,
            timeout=self.timeout
        )

        if not self.client.connect():
            raise Exception(f"Unable to connect to the Modbus device at {self.port}")

        if self.press == 'relative':
            response = self.client.read_holding_registers(
                address=self.address_list['Pressure'][0],
                count=self.address_list['Pressure'][1],
                unit=1
            )
            if not response.isError():
                self.P0 = self._decode_float(response.registers)
            else:
                raise Exception("Erreur lors de la lecture de la pression initiale")

    def get_data(self):
        data = []
        if self.svp:
            for i in self.svp:
                response = self.client.read_holding_registers(
                    address=self.address_list[i][0],
                    count=self.address_list[i][1])
                if not response.isError():
                    value = self._decode_float(response.registers)
                    if i == 'Pressure' and self.press == 'relative':
                        data.append(value - self.P0)
                    else:
                        data.append(value)
                else:
                    data.append(None)  # En cas d'erreur
        return [time.time()] + data

    def set_cmd(self, cmd):
        if cmd is not None:
            registers = self._encode_float(cmd)
            self.client.write_registers(address=1009, values=registers
                                        )

    def close(self):
        zero_cmd = 0.0
        registers = self._encode_float(zero_cmd)
        self.client.write_registers(address=1009, values=registers
                                    )
        self.client.close()

    def _decode_float(self, registers, byte_order='big', word_order='big'):
      # Changer l'ordre des mots (registres) si nécessaire
      if word_order == 'little':
          registers = registers[::-1]

      # Convertir les registres en bytes
      byte_data = b''.join(struct.pack('>H', reg) for reg in registers)

      # Changer l'ordre des bytes si nécessaire
      if byte_order == 'little':
          byte_data = byte_data[::-1]

      # Décode les bytes en float
      return struct.unpack('>f', byte_data)[0]


    def _encode_float(self, value):
        """Convertit un float en une liste de registres en gérant l'endianness."""
        # Encode le float en 4 octets (format IEEE 754)
        byte_data = struct.pack('>f', value)
        # Divise les octets en 2 registres de 16 bits
        return [struct.unpack('>H', byte_data[i:i+2])[0] for i in range(0, 4, 2)]


#contrôle en pression
class PressureController(crappy.blocks.Block):

    # def __init__(self, setpoint, pression_max, Kp=0.01, Ki = 0.005):
        # super().__init__()
        # self.setpoint = setpoint
        # self.Kp = Kp
        # self.Ki = Ki
        # self.pression_max = pression_max

        # self.integral = 0
        # self.prev_error = 0
        # self.prev_cmd = 0
        # self.last_time = time.time()
    def __init__(self, setpoint, pression_max, Kp=0.01, Ki = 0.005, ramp_rate=1.0):
        super().__init__()
        self.setpoint = setpoint
        self.Kp = Kp
        self.Ki = Ki
        self.pression_max = pression_max

        self.integral = 0
        self.prev_error = 0
        self.prev_cmd = 0
        self.ramp_rate = ramp_rate   
        self.p_start = None
        self.t_start = None

    def loop(self):
        # Récupère la pression depuis flow_ali
        data = self.inputs[0].recv()
        if not data or 'press' not in data:
            return

        press = data['press']
        now = time.time()
        
        if self.p_start is None:
            self.p_start = press
            self.t_start = now

        target = min(self.setpoint,
                    self.p_start + self.ramp_rate * (now - self.t_start))

        error = target - press
        
        #dt = now - self.last_time
        #self.last_time = now

        #error = self.setpoint - press

        # PI
        #self.integral += error * dt
        #self.integral = max(min(self.integral, 100), -100)

        #cmd = self.Kp * error + self.Ki * self.integral
        cmd = self.Kp * error       

        # saturation
        cmd = max(0, min(cmd, 1))

        # sécurité
        #if press > self.pression_max:
        #    cmd = 0

        # rampe (super important en pratique)
        max_step = 0.05
        delta = cmd - self.prev_cmd
        if abs(delta) > max_step:
            cmd = self.prev_cmd + max_step * (1 if delta > 0 else -1)
        
        if press > self.pression_max:
            cmd = 0

        self.prev_cmd = cmd
        self.send({'cmd': cmd})


#contrôle débit
class FlowController(crappy.blocks.Block):

    def __init__(self, setpoint, pression_max):
        super().__init__()
        self.setpoint = setpoint
        self.pression_max = pression_max

        self.integral = 0
        self.prev_error = 0
        self.prev_cmd = 0
        self.last_time = time.time()


    def loop(self):
        # Récupère le débit depuis flow_ali
        data = self.inputs[0].recv()
        if not data or 'volumetric_flow' not in data or 'press' not in data:
            return

        v_flow = data['volumetric_flow']
        press = data['press']

        if press > self.pression_max:
            cmd = 0


        self.send({'cmd': self.setpoint})

if __name__ == "__main__":

    print(crappy.__file__)
    pression_max = 1500

    pression_consigne = 1111
    Kp_press = 0.005
    Ki_press = 0
    ramp_rate = 1.4

    debit_consigne = 13.2/1000 #en fraction de 1000 mL/min
    Kp_debit = 0
    Ki_debit = 0

    duree_max = 1800 #en s

    control_type = "volum_flow" # "pressure" ou "volum_flow"


    date = time.strftime("%Y_%m_%d")  #"2025_07_21"
    sample= "Pro_Grip"

    saving_folder=f'./{date}/{sample}/Mesure/'

    if os.path.exists(saving_folder) :
        ()
    else :
        P = pathlib.Path(saving_folder)
        pathlib.Path.mkdir(P, parents = True)


    subprocess.run(
		["sudo", "tee", "/sys/module/usbcore/parameters/usbfs_memory_mb"],
		input=b"0\n",
		check = True
		)

    stop = crappy.blocks.StopButton()

    flow_ali = crappy.blocks.IOBlock('Flow_controller_alicat',
                                    port="/dev/ttyUSB1",
                                    startbit=1,
                                    databits=8,
                                    parity="N",
                                    stopbits=1,
                                    errorcheck="crc",
                                    baudrate=9600,
                                    #method="RTU",
                                    timeout=30,
                                    svp=['Pressure', 'Volumetric_flow','Mass_flow'],
                                    cmd_labels=['cmd'],
                                    labels=['t(s)', 'press','volumetric_flow','mass_flow'])


    """ver = crappy.blocks.VideoExtenso(camera='XiAPI',
                                    config=True,
                                    save_images=True,
                                    save_folder=f'./{date}/{sample}/video_extenso_right/',
                                    img_shape=(2048,2048),
                                    img_dtype='uint8',
                                    labels=['tr(s)', 'meta_r', 'pix_r', 'eyy_r', 'exx_r'],
                                    white_spots=False,
                                    **{"serial_number": "14482450",
                                        "exposure": 41389,
                                        "trigger": "Hdw after config"})

    vel = crappy.blocks.VideoExtenso(camera='XiAPI',
                                    config=True,
                                    save_images=True,
                                    save_folder=f'./{date}/{sample}/video_extenso_left/',
                                    img_shape=(2048,2048),
                                    img_dtype='uint8',
                                    labels=['tl(s)', 'meta_l', 'pix_l', 'eyy_l', 'exx_l'],
                                    white_spots=False,
                                    **{"serial_number": "32482550",
                                        "exposure": 31740,
                                        "trigger": "Hdw after config"})"""

    ver = FixedVideoExtenso(camera='XiAPI',
                            config=True,
                            save_images=True,
                            save_folder=f'./{date}/{sample}/Mesure/video_extenso_right/',
                            img_shape=(2048,2048),
                            img_dtype='uint8',
                            labels=['tr(s)', 'meta_r', 'pix_r', 'eyy_r', 'exx_r'],
                            white_spots=False,
                            **{"serial_number": "14482450",
                            "exposure": 41389,
                            "trigger": "Hdw after config"})

    vel = FixedVideoExtenso(camera='XiAPI',
                            config=True,
                            save_images=True,
                            save_folder=f'./{date}/{sample}/Mesure/video_extenso_left/',
                            img_shape=(2048,2048),
                            img_dtype='uint8',
                            labels=['tl(s)', 'meta_l', 'pix_l', 'eyy_l', 'exx_l'],
                            white_spots=False,
                            **{"serial_number": "32482550",
                            "exposure": 31740,
                            "trigger": "Hdw after config"})




    ftdi = crappy.blocks.IOBlock('Ft232r', cmd_labels=['cmd'], spam=False, direction=0b00000100, URL='ftdi://ftdi:232:FTU7DIHC/1')

    gen_ft = crappy.blocks.Generator([{'type': 'Cyclic',
                                    'value1': 0, 'condition1': 'delay=0.1',
                                    'value2': 1, 'condition2': 'delay=0.3', 'cycles': duree_max/0.4}], cmd_label='cmd')

    if control_type == "pressure":

        controller = PressureController(setpoint=pression_consigne, pression_max=pression_max, Kp=Kp_press, Ki=Ki_press, ramp_rate=ramp_rate)

        crappy.link(flow_ali, controller)
        crappy.link(controller, flow_ali)

        rec_pression = crappy.blocks.Recorder(file_name=f'./{date}/{sample}/Mesure/tests_pression/data_p_{pression_consigne}_{Kp_press}_{Ki_press}_r{ramp_rate}.txt', labels=['t(s)','press','volumetric_flow'])
        crappy.link(flow_ali, rec_pression)


    if control_type == "volum_flow":

        controller = FlowController(setpoint=debit_consigne, pression_max=pression_max)

        crappy.link(flow_ali, controller)
        crappy.link(controller, flow_ali)

        rec_pression = crappy.blocks.Recorder(file_name=f'./{date}/{sample}/Mesure/tests_debit/data_d_{debit_consigne}.txt', labels=['t(s)','press'])
        crappy.link(flow_ali, rec_pression)


    rec_ali = crappy.blocks.Recorder(file_name=f'./{date}/{sample}/Mesure/data_ali.txt')
    crappy.link(flow_ali, rec_ali)

    rec_ver = crappy.blocks.Recorder(file_name=f'./{date}/{sample}/Mesure/data_ver.txt',
                                     labels=['tr(s)','pix_r','exx_r','eyy_r'])
    crappy.link(ver, rec_ver)

    rec_vel = crappy.blocks.Recorder(file_name=f'./{date}/{sample}/Mesure/data_vel.txt',
                                     labels=['tl(s)','pix_l','exx_l','eyy_l'])
    crappy.link(vel, rec_vel)

    crappy.link(gen_ft, ftdi)
    """crappy.link(gen_flow, flow_ali)"""




    graph_press = crappy.blocks.Grapher(('t(s)', 'press'))
    crappy.link(flow_ali, graph_press)

    graph_debit = crappy.blocks.Grapher(('t(s)', 'volumetric_flow'))
    crappy.link(flow_ali, graph_debit)

    graph_ver = crappy.blocks.Grapher(('tr(s)', 'exx_r'),('tr(s)', 'eyy_r'))
    crappy.link(ver, graph_ver)

    graph_vel = crappy.blocks.Grapher(('tl(s)', 'exx_l'),('tl(s)', 'eyy_l'))
    crappy.link(vel, graph_vel)



    crappy.start()
