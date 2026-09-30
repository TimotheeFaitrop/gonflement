import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import cv2
import os
import pathlib
from math import *
from Pycaso import solve_library as solvel
from Pycaso import data_library as data
from Pycaso import pycaso as pcs
import time


def detect3D_Soloff (spform : int,
                     date : str,
                     sample : str,
                     P_graph : int = 0) -> (list,
                                            list,
                                            list):

      """Identification of the points detected on both cameras cam1 and cam2
      into the global 3D-space using Soloff method

      Args:
        spform : int
           Polynomial degree of the Soloff polynome
        date : str
           Date of the test
        sample : str
           Type of sample (silicone + mesh + resorption)
        P_graph : int,optional
            State of the sample during the test which will be plotted

      Returns:
        Lx3d : list
            X Coordinates of the points in the 3d space, for each step of the test
        Ly3d : list
            Y Coordinates of the points in the 3d space, for each step of the test
        Lz3d : list
            Z Coordinates of the points in the 3d space, for each step of the test
      """

      data_folder = f'./{date}/Results_Calib/Spform_{spform}/'
      saving_folder = f'./{date}/{sample}/'

      if os.path.exists(saving_folder+f'Spform_{spform}/') :
          ()
      else :
          P = pathlib.Path(saving_folder+f'Spform_{spform}/')
          pathlib.Path.mkdir(P, parents = True)

      S_constants0 = np.load(data_folder+'S_constants0.npy')
      S_constants = np.load(data_folder+'S_constants.npy')

      Lx3d = []
      Ly3d = []
      Lz3d = []
      Lp = np.load(saving_folder + 'Lp_final.npy',allow_pickle=True)
      for i in range(len(Lp)):
        Left, Right = Lp[i]
        xSoloff_solution = pcs.Soloff_identification (Left,
                                                      Right,
                                                      S_constants0,
                                                      S_constants,
                                                      Soloff_pform = spform,
                                                      method = 'curve_fit')
        x,y,z = xSoloff_solution
        Lx3d.append(x)
        Ly3d.append(y)
        Lz3d.append(z)

      x = Lx3d[P_graph]
      y = Ly3d[P_graph]
      if P_graph != 0:
        z = Lz3d[P_graph]-Lz3d[0]
      else:
        z = Lz3d[P_graph]
      fig = plt.figure(figsize=(16,9))
      ax = plt.axes(projection='3d')
      ax.grid(visible=True,
              color='grey',
              linestyle='-.',
              linewidth=0.3,
              alpha=0.2)
      ax.set_xlabel('X')
      ax.set_ylabel('Y')
      ax.set_zlabel('Z')
      # ax.set_zlim(min(Lz3d[0]),max(Lz3d[-1]))
      ax.set_zlim(-50,-70)

      my_cmap = plt.get_cmap('viridis')
      sctt = ax.scatter3D(x,y,z, alpha=0.8, c=z, cmap=my_cmap)
      plt.title('Results')
      fig.colorbar(sctt, ax=ax, shrink=0.5, aspect=5)
      #plt.savefig(saving_folder + f'Spform_{spform}/'+f'Déplacement_{P_graph}-{len(Lx3d)}')
      plt.show()

      #np.savetxt(saving_folder + f'Spform_{spform}/X3d.txt', Lx3d)
      #np.savetxt(saving_folder + f'Spform_{spform}/Y3d.txt', Ly3d)
      #np.savetxt(saving_folder + f'Spform_{spform}/Z3d.txt', Lz3d)

      return Lx3d, Ly3d, Lz3d


if __name__ == '__main__' :  

  date =  "2026_04_13" #time.strftime("%Y_%m_%d")  #'2025_07_21'
  sample = 'gonflement'
  spform = 555
  
  
  for frame in range(0,100,20): #range(4):
    print("Frame: ", frame)
    Lx3d, Ly3d, Lz3d = detect3D_Soloff(spform, date, sample, frame)


