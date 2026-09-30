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


def detect3D_Zernike (nZ : int,
                      date : str,
                      sample : str,
                      P_graph : int = 0) -> (list,
                                             list,
                                             list):

        """Identification of the points detected on both cameras cam1 and cam2
        into the global 3D-space using Zernike method

    Args:
        nZ : int
            Polynomial degree of the Zernike polynome
        date : str
            Date of the test
        sample : str
            Type of sample (silicone + mesh + resorption)
        P_graph : int, optional
            State of the sample during the test which will be plotted

    Returns:
        Lx3d : list
            X Coordinates of the points in the 3d space, for each step of the test
        Ly3d : list
            Y Coordinates of the points in the 3d space, for each step of the test
        Lz3d : list
            Z Coordinates of the points in the 3d space, for each step of the test
    """

        data_folder = f'./{date}/Results_Calib/nZ_{nZ}/'
        saving_folder = f'./{date}/{sample}/'

        #Dictionnary ot the calibration, with the calibration folders, and the ChAruCo dimensions
        calibration_dict = {
        'cam1_folder' : f'./{date}/{sample}/{sub_sample}/video_extenso_left/',
        'cam2_folder' : f'./{date}/{sample}/{sub_sample}/video_extenso_right/',
        'name' : 'calibration',
        'saving_folder' : data_folder,
        'ncx' : 12,
        'ncy' : 12,
        'sqr' : 7.5}  #in mm

        if os.path.exists(saving_folder+f'nZ_{nZ}/') :
            ()
        else :
            P = pathlib.Path(saving_folder+f'nZ_{nZ}/')
            pathlib.Path.mkdir(P, parents = True)

        A_constant = np.load(data_folder+'A_Zernike.npy')
        C_dim = data.cameras_size(**calibration_dict)

        Lx3d = []
        Ly3d = []
        Lz3d = []
        Lp = np.load(saving_folder + 'Lp_final.npy',allow_pickle=True)
        for i in range(len(Lp)):
            Left, Right= Lp[i]
            Z_solution = pcs.Zernike_identification(Left,
                                                    Right,
                                                    A_constant,
                                                    nZ,
                                                    C_dim)
            x,y,z = Z_solution
            Lx3d.append(x)
            Ly3d.append(y)
            Lz3d.append(z)


        x = Lx3d[P_graph]
        y = Ly3d[P_graph]
        z = Lz3d[P_graph]
        for i in range(len(z)):
            z[i] = 20 - z[i]

        fig=plt.figure(figsize=(16,9))
        ax=plt.axes(projection='3d')
        ax.grid(visible=True,
                color='grey',
                linestyle='-.',
                linewidth=0.3,
                alpha=0.2)
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')
        #ax.set_zlim((20,75))
        #ax.set_xlim((20,100))
        #ax.set_ylim((20,100))
        ax.set_zlim(-50,-65)

        #ax.set_zlim(min(Lz3d[0]), max(Lz3d[0]-Lz3d[P_graph]))
        my_cmap = plt.get_cmap('viridis')
        sctt = ax.scatter3D(x,y,z, alpha=0.8, c=z, cmap=my_cmap)
        plt.title('Results')
        fig.colorbar(sctt, ax=ax, shrink=0.5, aspect=5)
        plt.savefig(saving_folder + f'nZ_{nZ}/'+f'Déplacement_{P_graph}-{len(Lx3d)}')
        plt.show()


        np.savetxt(saving_folder + f'nZ_{nZ}/X3d.txt', Lx3d)
        np.savetxt(saving_folder + f'nZ_{nZ}/Y3d.txt', Ly3d)
        np.savetxt(saving_folder + f'nZ_{nZ}/Z3d.txt', Lz3d)

        return Lx3d, Ly3d, Lz3d


if __name__ == '__main__' :

    date =  "2026_04_13" #time.strftime("%Y_%m_%d")  #'2025_07_21'
    sample = 'gonflement'
    sub_sample = "mesure"
    nZ = 12


    for frame in range(0,100,20): #range(4):
        print("Frame: ", frame)
        Lx3d, Ly3d, Lz3d = detect3D_Zernike(nZ, date, sample, frame)

