import numpy as np
from scipy.interpolate import Rbf
import matplotlib.pyplot as plt
import os
from glob import glob
from math import *
from scipy.optimize import least_squares


def printDome(date,
              sample,
              polform,
              P1,
              version = ''):

        #Récupération de la pression à chaque image
    dossier_images = f'./{date}/{sample}/video_extenso_left{version}/'
    Limage = sorted(glob(dossier_images + '0*'))
    if not Limage:
        raise FileNotFoundError(f"Aucune image dans {dossier_images} : "
                                "ce script a besoin des images pour dater chaque dôme.")
    Ltime2 = [float(os.path.basename(f).split('_')[1].split('.t')[0]) for f in Limage]

    data = np.loadtxt(f'./{date}/{sample}/data_ali{version}.txt', delimiter=',', skiprows=1)
    Tp, Pp = data[:,0], data[:,1] - data[0,1]

    #Récupération de l'indice où Press = P1
    Press = np.interp(Ltime2, Tp, Pp)
    au_dessus = np.where(Press >= P1)[0]
    if len(au_dessus) == 0:
        raise ValueError(f"{sample} : la pression ne dépasse jamais P1 = {P1} "
                         f"(maximum atteint : {Press.max():.1f}).")
    ip = au_dessus[0]

    nb_lignes = len(np.loadtxt(f'./{date}/{sample}/{polform}/Z3d.txt', delimiter=' '))
    if ip >= nb_lignes:
        raise IndexError(f"{sample} : image {ip} demandée, mais X3d n'a que {nb_lignes} lignes "
                         "(detect3D n'a traité qu'une partie des images).")

    X3d = np.loadtxt(fname=f'./{date}/{sample}/{polform}/X3d.txt', delimiter=' ')[ip]
    Y3d = np.loadtxt(fname=f'./{date}/{sample}/{polform}/Y3d.txt', delimiter=' ')[ip]
    Z3d = np.loadtxt(fname=f'./{date}/{sample}/{polform}/Z3d.txt', delimiter=' ')[ip]

    Z3d0 = np.loadtxt(fname=f'./{date}/{sample}/{polform}/Z3d.txt', delimiter=' ')[0]
    Z3d -= Z3d0
    fig = plt.figure(figsize=(16,9))
    ax = plt.axes(projection='3d')
    ax.grid(visible=True,
            color='grey',
            linestyle='-.',
            linewidth=0.3,
            alpha=0.2)
    #ax.set_xlabel('X')
    #ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    #ax.set_xlim(10,90)
    #ax.set_ylim(0,90)
    ax.set_zlim(min(Z3d),35)
    my_cmap = plt.get_cmap('viridis')
    sctt = ax.scatter3D(X3d,Y3d,Z3d, alpha=0.8, s=50, c=Z3d, cmap=my_cmap)
    plt.title('Dôme de gonflement - '+f'{sample}')
    fig.colorbar(sctt, ax=ax, shrink=0.5, aspect=5)
    os.makedirs('./data/Dômes/Soloff/Toux/', exist_ok=True)
    plt.savefig('./data/Dômes/Soloff/Toux/' + f'{sample}.svg')
    #plt.show()

P1 = 143.5

date = '26-06'
sample = 'P7_30j'
polform = 'Spform_555'
method='Soloff'

printDome(date,sample,polform,P1)


date = '25-06'
sample = 'P7_21j'
polform = 'Spform_555'
method='Soloff'


printDome(date,sample,polform,P1)


date = '20-06'
sample = 'P7_21j'
polform = 'Spform_555'
method='Soloff'


printDome(date,sample,polform,P1)



