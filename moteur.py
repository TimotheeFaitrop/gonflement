import time
import crappy
import serial


class Printer(crappy.actuator.Actuator): 
  """Actuator class for 3D print motor"""

  def __init__(self, port: str = '/dev/ttyACM0', baudrate: int = 115200) -> None:
    crappy.actuator.Actuator.__init__(self)
    self.port = port
    self.baudrate = baudrate

  def open(self) -> None:
    """Start the motor and position it at the botom
    Returns:
      void return function.
    """
    
    self.ser = serial.Serial(self.port, self.baudrate)
    self.ser.write(b'M999\r\n')
    self.abscoord()
    self.backtozero()
    self.set_position(pos=70, speed=150)
    while self.get_position() != 70:
      time.sleep(0.01)

  def set_position(self, pos: float, speed=100) -> None:
    """Move to the given coordinates with given speed 
    Args:
      pos: float
        Z value in millimeters where you want to move the plate 
      speed: int
        Speed value to move the plate
    Returns:
      void return function.
    """
    
    if speed is None:
      speed=100    
    self.ser.write(f'G0 X0 Y0 Z{pos} F{speed}'.encode())
    self.ser.write(b'\r\n')
    print(f'set_pos {pos}')
    return None

  def get_position(self) -> float:
    """Show current real time machine position of Z axe 
    Returns:
      Position: float
        Actual plate position 
    """
    
    self.ser.write(b'M114.2\r\n')
    a = str(self.ser.readlines(30))
#    print(a)
    try:
      b = a.split('Z:')
#      print(b)
      c = b[1].split('\\')
      return float(c[0])
    except:
      pass
#      print('pas possible')
  
  def stop(self) -> None:
    pass
  
  def close(self) -> None:
    """Closes properly the serial port
    Returns:
     void return function.      
    """
      
    self.ser.close()

  def abscoord(self) -> None:
    """Define the absolute positioning system. When G90 is active the machine will read all dimensions and movements from the working
     datum position
    Returns:
     void return function.
    """ 
   
    self.ser.write(b'G90\r\n')

  def relcoord(self) -> None:
    """Command the tool to move from its current position and not the datum position.
    Returns:
      void return function.
    """ 
    
    self.ser.write(b'G91\r\n')

  def backtozero(self):
    """Move to the park position
    Returns:
      void return function.
    """
  
    self.ser.write(b'G28 Z0\r\n')

  def definezero(self):
    """Set global workspace coordinate system to specified coordinates, here Z =0
    Returns:
      void return function.
    """
    
    self.ser.write(b'G92 Z0\r\n')
