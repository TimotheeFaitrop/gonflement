import numpy as np
from scipy.interpolate import Rbf
import matplotlib.pyplot as plt
from glob import glob
from math import *
from scipy.optimize import least_squares

date = '2025_06_18'
sample= "SC37_20_P7_21j"
nZ = 10
l_pform = 4
spform=555

method_dict = {'Zernike','Lagrange','Soloff'}
method = input('Choisir une methode\n')
if not method in method_dict:
   raise AssertionError('Erreur, choisir parmi' + str(method_dict))

if method == 'Lagrange':
   polform = f'Lpform_{l_pform}'

if method == 'Zernike':
   polform = f'nZ_{nZ}'

if method == 'Soloff':
   polform = f'Spform_{spform}'

X3d = np.loadtxt(fname=f'./{date}/{sample}/{polform}/X3d.txt', delimiter=' ')
Y3d = np.loadtxt(fname=f'./{date}/{sample}/{polform}/Y3d.txt', delimiter=' ')
Z3d = np.loadtxt(fname=f'./{date}/{sample}/{polform}/Z3d.txt', delimiter=' ')


#Création du maillage
X0min = min(X3d[0])
X0max = max(X3d[0])
Y0min = min(Y3d[0])
Y0max = max(Y3d[0])
Zmin = min(Z3d[0])
Zmax = max(Z3d[-1])

Xmesh, Ymesh = np.meshgrid(np.linspace(X0min, X0max,100), np.linspace(Y0min, Y0max,100), indexing='xy')
Ymesh = np.flip(Ymesh)

#Fonctions interpolatrices
interpfunction = 'linear'
Rbfx = []
Rbfy = []
Rbfz = []
for i in range(len(X3d)):
  Rbfx.append(Rbf(X3d[0], Y3d[0], X3d[i], function=interpfunction))
  Rbfy.append(Rbf(X3d[0], Y3d[0], Y3d[i], function=interpfunction))
  Rbfz.append(Rbf(X3d[0], Y3d[0], Z3d[i], function=interpfunction))


#Interpolation des positions  
XX = []
YY = []
ZZ = []
for i in range(len(Rbfx)):
  XX.append(Rbfx[i](Xmesh, Ymesh))
  YY.append(Rbfy[i](Xmesh, Ymesh))
  ZZ.append(Rbfz[i](Xmesh, Ymesh))


#Calcul des vecteurs déplacements  
Ux = []
Uy = []
Uz = []
for i in range(len(XX)):
  Ux.append(XX[i] - XX[0])
  Uy.append(YY[i] - YY[0])
  Uz.append(ZZ[i] - ZZ[0])

Uzmax = [np.max(Uz[i]) for i in range(len(Uz))]
if method != 'Soloff' :
  Uzmax=[np.max(-Uz[i]) for i in range(len(Uz))]

#Récupération de la pression à chaque image
Limage = sorted(glob(f'./{date}/{sample}/video_extenso_left/' + '0*'))
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

Tp = np.loadtxt(f'./{date}/{sample}/data_ali.txt', delimiter=',', skiprows=1)[:,0]
Pp = np.loadtxt(f'./{date}/{sample}/data_ali.txt', delimiter=',', skiprows=1)[:,1]
Pp=Pp-Pp[0]



Rbfpress = Rbf(Tp, Pp)
Press = Rbfpress(Ltime2)



#plot pression=f(uzmax)
ax = plt.axes()
ax.set_xlabel('Uzmax (mm)')
ax.set_ylabel('Pressure (mbar)')
plt.plot(Uzmax[:], Press[:], label=sample)
plt.legend(fontsize=10)
plt.savefig(f'./{date}/{sample}/{polform}/'+'Pression_Uz')
plt.show()
