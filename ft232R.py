from pyftdi.ftdi import Ftdi
from pyftdi.gpio import GpioAsyncController
import crappy
import time

class Ft232r(crappy.inout.InOut):
  """InOut class for ft232r"""

  def __init__(self, direction: int= 0b1111, URL: str= 'ftdi:///1') -> None:
    crappy.inout.InOut.__init__(self)
    self.direction = direction
    self.url = URL

  def open(self) -> None:
    """Connect with the ft232r, set the direction and write 0 on all bytes.
    Returns:
      void return function.
    """

    self.gpio = GpioAsyncController()
    self.gpio.open_from_url(self.url, self.direction)
    print(self.gpio.is_connected)
    print(self.gpio.direction)
    self.gpio.write(int(0b0000))

#  def get_data(self):
#    value = bin(self.gpio.read())[-4:]
#    direc = bin(self.get_direction())[-4:]
#    for i in range(4):
#      if int(direc[i]) == 0 and int(value[i]) == 0 :
#        return('bit input '+str(i+1)+' vaut 0')
#      elif int(direc[i]) == 0 and int(value[i]) == 1:         
#        return('bit input '+str(i+1)+' vaut 1')
#      elif int(direc[i]) == 1 and int(value[i]) == 0:
#        return('bit output '+str(i+1)+' vaut 0')
#      elif int(direc[i]) == 1 and int(value[i]) == 1:
#       return('bit output '+str(i+1)+' vaut 1')     

  def set_cmd(self, cmd) -> None:
    """Send a pulse
    Args:
      cmd: int
        0 to send nothing 
        1 to send a pulse
    Returns:
      void return function.
    """ 
    
    #if cmd == 1: #on change le temps de regler des bugs crappy (encore pinaise)
    if cmd>0:
      self.gpio.write(0b0100)
      print(1)
      self.gpio.write(0b000)
      print(0)


  def close(self) -> None:
    """Closes properly the ft232r.
    Returns:
      void return function.      
    """

    self.gpio.close()

  def get_direction(self) -> int:
    """Show if the bytes are set to 1 (output) or 0 (input). 
    Returns:
      direction: int
    """

#    print(bin(self.gpio.direction)) 
    return(self.gpio.direction)

  def set_direction(self, pins:int, pdirection:int) -> None:
    """Write a new direction on each byte.
    Args: 
      pins: int
        The bytes you want to modify the direction.
      pdirection: int
        The new direction you want to set.
    Returns:
      void return function
    """

    self.gpio.set_direction(pins, pdirection)
    self.direction = self.get_direction()

