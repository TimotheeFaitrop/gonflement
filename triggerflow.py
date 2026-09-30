import crappy
import time

class Trigger(crappy.blocks.Block):

  def __init__(self,
               cmd_labels: list) -> None:
               
    crappy.blocks.Block.__init__(self)
    self.cmd_labels = cmd_labels
    self.out = {}

  
  def begin(self):
  
    self.out['cmd'] = 1
    self.out['path_id'] = 0
    self.out['pcmd'] = 500
    self.out['fcmd'] = 0
    self.send(self.out)

  
  def prepare(self) -> None:
    
    self.values = {}
    for label in self.cmd_labels:
      self.values[label] = None 
      
     
  def loop(self):


    self.get_data()
    if (self.values['zcmd'] - self.values['ztri']) > 1:
      self.out['fcmd'] = 0.09
      self.out['cmd'] = 0
      self.out['pcmd'] = 500
      self.send(self.out)
      time.sleep(0.5)
      self.out['fcmd'] = 0.09
      self.out['cmd'] = 1
      self.out['pcmd'] = 500
      self.send(self.out)            
    elif (self.values['zcmd'] - self.values['ztri']) < -1: 
      self.out['fcmd'] = 0
      self.out['cmd'] = 0
      self.out['pcmd'] = 0
      self.send(self.out)
      time.sleep(0.5)
      self.out['fcmd'] = 0
      self.out['cmd'] = 1
      self.out['pcmd'] = 0
      self.send(self.out)
    else:
      print('okboooooooomCbueeeennnnoooooooo')
      self.out['path_id'] += 1
      self.out['cmd'] = 0
      self.out['pcmd'] = 500
      self.out['fcmd'] = 0
      self.send(self.out)
      time.sleep(0.5)
      self.out['cmd'] = 1
      self.send(self.out)       

      
  def get_data(self) -> None:
    """Receives data from the upstream links."""

    for link in self.inputs:
      # Receiving data from each link, non-blocking to prevent accumulation
      data = link.recv_last()
#      print(data)
      # Processing only the valid labels
      if data is not None:
        # Saving the other values
        for label in self.cmd_labels:
           if label in data.keys():
             self.values[label] = data[label]
             
    
class Triggercamz(crappy.blocks.Block):

  def __init__(self,
               cmd_labels: list) -> None:
               
    crappy.blocks.Block.__init__(self)
    self.cmd_labels = cmd_labels
    self.out = {}

  
  def begin(self):
  
    self.out['cmd'] = 1
    self.out['path_id'] = 0
    self.send(self.out)

  
  def prepare(self) -> None:
    
    self.values = {}
    for label in self.cmd_labels:
      self.values[label] = None 
      
     
  def loop(self):

#    print(self, 'en attente')
    self.get_data()
#    print(self, 'recu')
#    print(self, self.values)
    if (self.values['zcmd'] - self.values['ztri']) > 1 or (self.values['zcmd'] - self.values['ztri']) < -1:
      self.out['cmd'] = 0
      self.send(self.out)
#      time.sleep(0.03)
      self.out['cmd'] = 1
      self.send(self.out)
#      print(self.out)
#      print(self, 'envoyé')            
    else:
      print('okboooooooomCbueeeennnnoooooooo')
      self.out['path_id'] += 1
      self.out['cmd'] = 0
      self.send(self.out)
#      time.sleep(0.03)
      self.out['cmd'] = 1
      self.send(self.out)  


  def get_data(self) -> None:
    """Receives data from the upstream links."""

    for link in self.inputs:
      # Receiving data from each link, non-blocking to prevent accumulation
      data = link.recv_last()
#      print(data)
      # Processing only the valid labels
      if data is not None:
        # Saving the other values
        for label in self.cmd_labels:
           if label in data.keys():
             self.values[label] = data[label]
#        print(self.values)


class Triggercamexx(crappy.blocks.Block):

  def __init__(self,
               cmd_labels: list) -> None:
               
    crappy.blocks.Block.__init__(self)
    self.cmd_labels = cmd_labels
    self.out = {}

  
  def begin(self):
  
    self.out['cmd'] = 1
    self.out['path_id'] = 0
    self.send(self.out)

  
  def prepare(self) -> None:
    
    self.values = {}
    for label in self.cmd_labels:
      self.values[label] = None
    self.i = 2 #le temps de résoudre pb inout   
      
     
  def loop(self):

    data = self.recv_all_data()
    for label in self.cmd_labels:
       if label in data.keys():
         self.values[label] = data[label]
    if self.values['exxcmd'] is None or self.values['triexx'] is None:
      return  

    if (float(self.values['exxcmd'][0]) - float(self.values['triexx'][0])) > float(self.values['exxcmd'][0])*5/100 or (float(self.values['exxcmd'][0]) - float(self.values['triexx'][0])) < -float(self.values['exxcmd'][0])*5/100:
#      self.out['cmd'] = 1      # le temps de résoudre pb inout
      self.out['cmd'] = self.i  #le temps de résoudre pb inout
      self.send(self.out)
      self.i +=1                #le temps de résoudre pb inout
#      print(self.out)

    else:
      print('okboooooooomCbueeeennnnoooooooo')
      self.out['path_id'] += 1
#      self.out['cmd'] = 1      #le temps de résoudre pb inout
      self.out['cmd'] = self.i  #le temps de résoudre pb inout
      self.send(self.out)
      self.i +=1                #le temps de résoudre pb inout      
    for label in self.cmd_labels:
      self.values[label] = None 
