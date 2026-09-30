import pycaso as pcs
import crappy
import numpy as np
#import data_library as data


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



class ControlZernike(crappy.blocks.Block):
  def __init__(self,
                Zernikecoeffs : np.ndarray,
                matrix_file: str,
                label : str,
                pform : int):

    """Block qui identifie par la méthode de Zernike la position des points sur l'éprouvette

    Args:
        Zernikecoeffs : np.ndarray
            constante du polynôme de Zernike
        matrix_file: str
            chemin jusqu'au fichier de la matrice d'interpolation de Zernike M : np.ndarray
        label : str
            label des commandes à sortir du block
        pform : int
            degré du polynome de Zernike


    Returns :
        une indication pour un block PID
    """

    crappy.blocks.Block.__init__(self)
    self.coeffs = Zernikecoeffs
    self.nZ = pform
    self.M = np.load(matrix_file)
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



    for i in range(len(Lp)):
      Left, Right = Lp[i]
      zernike_solution = pcs.Zernike_identification (Left,
                                                      Right,
                                                      self.coeffs,
                                                      self.nZ)
      x,y,z = zernike_solution
    self.stockx.append(x)
    self.stocky.append(y)
    self.stockz.append(z)
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


