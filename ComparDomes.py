import numpy as np
from scipy.interpolate import Rbf
import matplotlib.pyplot as plt
from glob import glob
from math import *
from scipy.optimize import least_squares


def printDome(date,
              sample,
              polform,
              P1,
              version = ''):

    #Récupération de la pression à chaque image
    Limage = sorted(glob(f'./{date}/{sample}/video_extenso_left{version}/' + '0*'))
    Lname = []
    for i in range(len(Limage)):
        Lname.append(Limage[i].split('/')[-1])
    Lnum = []
    Ltime = []
    for i in range(len(Lname)):
        Lnum.append(Lname[i].split('_')[0])
        Ltime.append(Lname[i].split('_')[1])
    Ltime2 = []
    for i in range(len(Ltime)):
        Ltime2.append(float(Ltime[i].split('.t')[0]))

    Tp = np.loadtxt(f'./{date}/{sample}/data_ali{version}.txt', delimiter=',', skiprows=1)[:,0]
    Pp = np.loadtxt(f'./{date}/{sample}/data_ali{version}.txt', delimiter=',', skiprows=1)[:,1]
    Pp=Pp-Pp[0]


    #Récupération de l'indice où Press = P1
    Rbfpress = Rbf(Tp, Pp)
    Press = Rbfpress(Ltime2)
    DiffP = Press - P1
    ip = np.where(np.diff(np.sign(DiffP)))[0][0]

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
    plt.savefig('./data/Dômes/Soloff/Toux/' + f'{sample}.svg')
    #plt.show()

P1 = 143.5

date = '2025_06_04'
sample = 'SC37_20_P7NR'
polform = 'Spform_555'
method='Soloff'

printDome(date,sample,polform,P1)


date = '2025_06_05'
sample = 'SC37_20_P7_8j'
polform = 'Spform_555'
method='Soloff'


printDome(date,sample,polform,P1)


date = '2025_06_17'
sample = 'SC37_20_P7_16j'
polform = 'Spform_555'
method='Soloff'


printDome(date,sample,polform,P1)


date = '2025_06_18'
sample = 'SC37_20_P7_21j'
polform = 'Spform_555'
method='Soloff'


printDome(date,sample,polform,P1)


date = '2025_07_01'
sample = 'SC37_20_P7_30j'
polform = 'Spform_555/Jumping'
method='Soloff'


printDome(date,sample,polform,P1,'_00001')


date = '2025_07_07'
sample = 'SC37_20'
polform = 'Spform_555'
method='Soloff'


printDome(date,sample,polform,P1)


date = '2025_07_21'
sample = 'Pro_Grip'
polform = 'Spform_555'
method='Soloff'

printDome(date,sample,polform,P1)
