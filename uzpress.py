import numpy as np
from scipy.interpolate import Rbf
import matplotlib.pyplot as plt
from glob import glob
from math import *
from scipy.optimize import least_squares


X3d = np.loadtxt(fname='./2023_08_29/40d_cd/SC37_40/X3d_SC37_40.txt', delimiter=' ')
Y3d = np.loadtxt(fname='./2023_08_29/40d_cd/SC37_40/Y3d_SC37_40.txt', delimiter=' ')
Z3d = np.loadtxt(fname='./2023_08_29/40d_cd/SC37_40/Z3d_SC37_40.txt', delimiter=' ')


#Création du maillage
X0min = min(X3d[0])
X0max = max(X3d[0])
Y0min = min(Y3d[0])
Y0max = max(Y3d[0])

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

Uzmax = [Uz[i][50][50] for i in range(len(Uz))]


#Récupération de la pression à chaque image
sili = 'SC37_40'
tricot = '4DFIXNR'
Limage = sorted(glob('./2023_08_29/40d_cd/SC37_40/gonfconti_L_'+sili+'/' + '0*'))
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

Tp = np.loadtxt('./2023_08_29/40d_cd/SC37_40/press_'+sili, delimiter=',', skiprows=1)[:,0]
Pp = np.loadtxt('./2023_08_29/40d_cd/SC37_40/press_'+sili, delimiter=',', skiprows=1)[:,1]

Rbfpress = Rbf(Tp, Pp)
Press = Rbfpress(Ltime2)


#plot pression=f(uzmax)
#ax = plt.axes()
#ax.set_xlabel('Uzmax (mm)')
#ax.set_ylabel('Pressure (mbar)')
plt.plot(Uzmax[10:-160], Press[10:-160], label=sili)
#plt.legend()
#plt.show() 
