import crappy
import time
import numpy as np
from Pycaso import pycaso as pcs

def RtoL_transfo(rightpoints, matrix):
  Rightp = []
  for i in range(len(rightpoints)):
    vect = list(rightpoints[i])
    vect.append(1)
    vectp = np.dot(matrix, vect)
    vectp = list(vectp)
    vectp[0] = vectp[0]/vectp[2]
    vectp[1] = vectp[1]/vectp[2]
    del vectp[2]
    Rightp.append(vectp)
  return np.array(Rightp) 


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


class Direct_Polynome(dict) :
  def __init__(self, _dict_):
    self._dict_ = _dict_
    self.polynomial_form = _dict_['polynomial_form']

  def pol_form (self, Xl, Xr) :
    """Create the matrix M = f(Xl,Xr) with f the polynomial function of 
    degree n
  
    Args:
       Xl : numpy.ndarray
           Left detected points  Xl(Xl1, Xl2)
       Xr : numpy.ndarray
           Right detected points  Xr(Xr1, Xr2)
             
    Returns:
       M : numpy.ndarray
           M = f(Xl,Xr)
    """
    polynomial_form = self.polynomial_form
    Xl1, Xl2 = Xl
    Xr1, Xr2 = Xr
      
    n = len(Xl1)
    if   polynomial_form == 1 :
      M = np.asarray ([np.ones((n)),   Xl1,           Xl2,            Xr1,            Xr2])

    elif polynomial_form == 2 :
      Xl12 = Xl1 * Xl1
      Xl22 = Xl2 * Xl2
      Xr12 = Xr1 * Xr1
      Xr22 = Xr2 * Xr2
      M = np.asarray ([np.ones((n)),   Xl1,           Xl2,            Xr1,            Xr2,
                       Xl12,           Xl1*Xl2,       Xl1*Xr1,        Xl1*Xr2,        Xl22,
                       Xl2*Xr1,        Xl2*Xr2,       Xr12,           Xr1*Xr2,        Xr22])

    elif polynomial_form == 3 :
      Xl12 = Xl1 * Xl1
      Xl13 = Xl1 * Xl1 * Xl1
      Xl22 = Xl2 * Xl2
      Xl23 = Xl2 * Xl2 * Xl2
      Xr12 = Xr1 * Xr1
      Xr13 = Xr1 * Xr1 * Xr1
      Xr22 = Xr2 * Xr2
      Xr23 = Xr2 * Xr2 * Xr2
      M = np.asarray ([np.ones((n)),   Xl1,           Xl2,            Xr1,            Xr2,
                       Xl12,           Xl1*Xl2,       Xl1*Xr1,        Xl1*Xr2,        Xl22,
                       Xl2*Xr1,        Xl2*Xr2,       Xr12,           Xr1*Xr2,        Xr22,
                       Xl13,           Xl12*Xl2,      Xl12*Xr1,       Xl12*Xr2,       Xl1*Xl22,
                       Xl1*Xl2*Xr1,    Xl1*Xl2*Xr2,   Xl1*Xr12,       Xl1*Xr1*Xr2,    Xl1*Xr22,
                       Xl23,           Xl22*Xr1,      Xl22*Xr2,       Xl2*Xr12,       Xl2*Xr1*Xr2,    
                       Xl2*Xr22,       Xr13,          Xr12*Xr2,       Xr1*Xr22,       Xr23])

    elif polynomial_form == 4 :
      Xl12 = Xl1 * Xl1
      Xl13 = Xl1 * Xl1 * Xl1
      Xl14 = Xl1 * Xl1 * Xl1 * Xl1
      Xl22 = Xl2 * Xl2
      Xl23 = Xl2 * Xl2 * Xl2
      Xl24 = Xl2 * Xl2 * Xl2 * Xl2
      Xr12 = Xr1 * Xr1
      Xr13 = Xr1 * Xr1 * Xr1
      Xr14 = Xr1 * Xr1 * Xr1 * Xr1
      Xr22 = Xr2 * Xr2
      Xr23 = Xr2 * Xr2 * Xr2
      Xr24 = Xr2 * Xr2 * Xr2 * Xr2
      M = np.asarray ([np.ones((n)),   Xl1,           Xl2,            Xr1,            Xr2,
                       Xl12,           Xl1*Xl2,       Xl1*Xr1,        Xl1*Xr2,        Xl22,
                       Xl2*Xr1,        Xl2*Xr2,       Xr12,           Xr1*Xr2,        Xr22,
                       Xl13,           Xl12*Xl2,      Xl12*Xr1,       Xl12*Xr2,       Xl1*Xl22,
                       Xl1*Xl2*Xr1,    Xl1*Xl2*Xr2,   Xl1*Xr12,       Xl1*Xr1*Xr2,    Xl1*Xr22,
                       Xl23,           Xl22*Xr1,      Xl22*Xr2,       Xl2*Xr12,       Xl2*Xr1*Xr2,    
                       Xl2*Xr22,       Xr13,          Xr12*Xr2,       Xr1*Xr22,       Xr23,
                       Xl14,           Xl13*Xl2,      Xl13*Xr1,       Xl13*Xr2,       Xl12*Xl22,
                       Xl12*Xl2*Xr1,   Xl12*Xl2*Xr2,  Xl12*Xr12,      Xl12*Xr1*Xr2,   Xl12*Xr22,
                       Xl1*Xl23,       Xl1*Xl22*Xr1,  Xl1*Xl22*Xr2,   Xl1*Xl2*Xr12,   Xl1*Xl2*Xr1*Xr2,
                       Xl1*Xl2*Xr22,   Xl1*Xr13,      Xl1*Xr12*Xr2,   Xl1*Xr1*Xr22,   Xl1*Xr23,
                       Xl24,           Xl23*Xr1,      Xl23*Xr2,       Xl22*Xr12,      Xl22*Xr1*Xr2,
                       Xl22*Xr22,      Xl2*Xr13,      Xl2*Xr12*Xr2,   Xl2*Xr1*Xr22,   Xl2*Xr23,
                       Xr14,           Xr13*Xr2,      Xr12*Xr22,      Xr1*Xr23,       Xr24])

    return (M)


def direct_identification (Xc1_identified,
                           Xc2_identified,
                           direct_A,
                           direct_polynomial_form = 3) :
  """Identification of the points detected on both cameras left and right 
  into the global 3D-space
  
  Args:
     Xc1_identified : numpy.ndarray
         Points identified on the left camera
     Xc2_identified : numpy.ndarray
         Points identified on the right camera
     direct_A : numpy.ndarray
         Constants of direct polynomial
     direct_polynomial_form : int, optional
         Polynomial form


  Returns:
     x_solution : numpy.ndarray
         Identification in the 3D space of the detected points
  """    
  # Solve by direct method
  Xl1, Xl2 = Xc1_identified[:,0], Xc1_identified[:,1]
  Xr1, Xr2 = Xc2_identified[:,0], Xc2_identified[:,1]
  Xl = np.zeros((2,len(Xl1)))
  Xr = np.zeros((2,len(Xr1)))
  Xl = Xl1, Xl2
  Xr = Xr1, Xr2
  
  M = Direct_Polynome({'polynomial_form' : direct_polynomial_form}).pol_form(Xl, Xr)
  xsolution = np.matmul(direct_A,M)
  return(xsolution)


class Tridical(crappy.blocks.Block):
  
  def __init__(self,
               direct_A_file: str,
               transfomatrix_file: str,
               p_form: int,
               label: str) -> None:

    crappy.blocks.Block.__init__(self)
    self.direct_A = np.load(direct_A_file)
    self.direct_polynome_degree = p_form
    self.M = np.load(transfomatrix_file)
    self.label = label   
    self.cmd_labels = ['tl(s)', 'tr(s)','pix_l', 'pix_r']


  def prepare(self):

    self.values = {}
    for label in self.cmd_labels:
      self.values[label] = None
    self.l0x = 0
    self.stockx = []
    self.stocky = []
    self.stockz = []
    self.stockexx = []
    self.stockt = []
    self.Lid = []
    self.nbloop = 0
    
       
  def loop(self):

    data = self.recv_all_data()
    for label in self.cmd_labels:
      if label in data.keys():
        self.values[label] = data[label]
    if self.values['pix_l'] is None or self.values['pix_r'] is None:
      return    
      
    Lp = f([np.array(self.values['pix_l'][0])[:,0]], [np.array(self.values['pix_l'][0])[:,1]], [np.array(self.values['pix_r'][0])[:,0]], [np.array(self.values['pix_r'][0])[:,1]])
    np.save('./Lp.npy',Lp)

    if self.nbloop == 0:
      Lrp = RtoL_transfo(Lp[0][1], self.M)
      Lfalse = []
      for j in range(len(Lrp)):
        if Lp[0][0][j][0] - Lrp[j][0] > 130 or Lp[0][0][j][0] - Lrp[j][0] < 100:
          Lfalse.append([Lrp[j], j])
      print(len(Lfalse))
      for j in range(len(Lfalse)):
          for k in range(len(Lfalse)):
            if Lp[0][0][Lfalse[j][1]][0] - Lfalse[k][0][0] > 100 and Lp[0][0][Lfalse[j][1]][0] - Lfalse[k][0][0] < 130:
              if abs(Lp[0][0][Lfalse[j][1]][1] - Lfalse[k][0][1]) < 7:
                self.Lid.append([Lfalse[j][1], Lfalse[k][1]]) 
      print(len(self.Lid))
      self.nbloop = 1
        
    for i in range(len(Lp)):
      Rightbuff = Lp[i][1].copy()
      for j in range(len(self.Lid)):
        Lp[i][1][self.Lid[j][0]] = Rightbuff[self.Lid[j][1]]

    out = {}
    for i in range(len(Lp)):
      Left, Right = Lp[i]
      xdirect_solution = pcs.Lagrange_identification(Left,
                                                     Right,
                                                     self.direct_A,
                                                     self.direct_polynome_degree)
      x,y,z = xdirect_solution
    self.stockx.append(y)
    self.stocky.append(x)
    self.stockz.append(z)       #ATTENTION ON A ECHANGE X ET Y MINCE MINCE MINCE
    print(x)
    print(y)
    print(z)
    self.l0x = max(self.stockx[0]) - min(self.stockx[0])
#    print(f'l0x: {self.l0x}')
    exx = (max(y) - min(y))/self.l0x -1
    print(f'exx: {exx}')
    out[self.label] = float(exx)
    out['t(s)'] = float(self.values['tr(s)'][0])
    self.stockexx.append(float(exx))
    self.stockt.append(float(self.values['tr(s)'][0]))
    if len(self.stockexx) > 1:
      out['dexx'] = ((self.stockexx[-1] - self.stockexx[-2])/(self.stockt[-1]-self.stockt[-2]))
    else:
      out['dexx'] = 0
    print(f'dexx: {out["dexx"]}')
    out['ztrid'] = z[-1]
    self.send(out)
    for label in self.cmd_labels:
      self.values[label] = None


