import numpy as np
from scipy.interpolate import Rbf
import matplotlib.pyplot as plt
from glob import glob
from math import *
from scipy.optimize import least_squares

date = '2025_07_07'
sample= "SC37_20_P7_30j"
tricot='None'
nZ = 10
l_pform = 5
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

Im3d = []
for i in range(len(XX)):
  Im3d.append(np.stack((XX[i], YY[i], ZZ[i]), axis=-1))


#Calcul des vecteurs déplacements  
Ux = []
Uy = []
Uz = []
for i in range(len(XX)):
  Ux.append(XX[i] - XX[0])
  Uy.append(YY[i] - YY[0])
  Uz.append(ZZ[i] - ZZ[0])


##Calcul du tenseur gradient de la transformation

#Calcul de F1  
Fxx = []
Fyy = []
Fxy = []
Fyx = []
Fzx = []
Fzy = []
for i in range(len(XX)):
  Fxx.append(np.gradient(XX[i], (Xmesh[0][1]-Xmesh[0][0]), axis=1))
  Fyy.append(np.gradient(YY[i], (Ymesh[1][0]-Ymesh[0][0]), axis=0))
  Fxy.append(np.gradient(XX[i], (Ymesh[1][0]-Ymesh[0][0]), axis=0))
  Fyx.append(np.gradient(YY[i], (Xmesh[0][1]-Xmesh[0][0]), axis=1))
  Fzx.append(np.gradient(ZZ[i], (Xmesh[0][1]-Xmesh[0][0]), axis=1))
  Fzy.append(np.gradient(ZZ[i], (Ymesh[1][0]-Ymesh[0][0]), axis=0))

F1 = []
for i in range(len(Fxx)):
  A = np.zeros((100,100,3,2))
  A[:,:,0,0] = Fxx[i]
  A[:,:,0,1] = Fxy[i]
  A[:,:,1,0] = Fyx[i]
  A[:,:,1,1] = Fyy[i]
  A[:,:,2,0] = Fzx[i]
  A[:,:,2,1] = Fzy[i]
  F1.append(A)

      
#Calcul de U1 = sqrt(tF1*F1)
U1 = []
for i in range(len(F1)):
  A = np.zeros((100,100,2,2))
  A = np.matmul(F1[i].transpose(0,1,3,2), F1[i])
  D, P = np.linalg.eig(A)
  D = np.sqrt(D)
  RD = np.zeros((100,100,2,2))
  RD[:,:,0,0] = D[:,:,0]
  RD[:,:,1,1] = D[:,:,1]
  Pinv = np.linalg.inv(P)
  U1.append(np.matmul(np.matmul(P, RD), Pinv))
  

#Calcul du déterminant de U1
detU1 = []
for i in range(len(U1)):
  detU1.append(np.linalg.det(U1[i]))


#Calcul des normales en chaque point
N = []
for i in range(len(Im3d)):
  Nord = np.zeros((100,100,3))
  Sud = np.zeros((100,100,3))
  Est = np.zeros((100,100,3))
  Ouest = np.zeros((100,100,3))
  Nord[1:,:] = Im3d[i][:-1,:]
  Sud[:-1,:] = Im3d[i][1:,:]
  Est[:,:-1] = Im3d[i][:,1:]
  Ouest[:,1:] = Im3d[i][:,:-1]
  Vn = Nord - Im3d[i]
  Vn[0,:] = np.zeros((100,3))
  Vs = Sud - Im3d[i]
  Vs[-1,:] = np.zeros((100,3))
  Ve = Est - Im3d[i]
  Ve[:,-1] = np.zeros((100,3))
  Vo = Ouest - Im3d[i]
  Vo[:,0] = np.zeros((100,3))
  N1 = np.cross(Ve, Vn)
  N2 = np.cross(Vn, Vo)
  N3 = np.cross(Vo, Vs)
  N4 = np.cross(Vs, Ve)
  Npnorm1 = np.linalg.norm(np.stack((N1, N1, N1), axis=-1), axis=-2)
  Npnorm2 = np.linalg.norm(np.stack((N2, N2, N2), axis=-1), axis=-2)
  Npnorm3 = np.linalg.norm(np.stack((N3, N3, N3), axis=-1), axis=-2)
  Npnorm4 = np.linalg.norm(np.stack((N4, N4, N4), axis=-1), axis=-2)
  N0i = ((N1/Npnorm1)+(N2/Npnorm2)+(N3/Npnorm3)+(N4/Npnorm4))/4
  N0i[0,:] = ((N3[0,:]/Npnorm3[0,:])+(N4[0,:]/Npnorm4[0,:]))/2
  N0i[-1,:] = ((N1[-1,:]/Npnorm1[-1,:])+(N2[-1,:]/Npnorm2[-1,:]))/2
  N0i[:,0] = ((N1[:,0]/Npnorm1[:,0])+(N4[:,0]/Npnorm4[:,0]))/2
  N0i[:,-1] = ((N2[:,-1]/Npnorm2[:,-1])+(N3[:,-1]/Npnorm3[:,-1]))/2
  N0i[0][0] = N4[0][0]/Npnorm4[0][0]
  N0i[0][-1] = N3[0][-1]/Npnorm3[0][-1]
  N0i[-1][0] = N1[-1][0]/Npnorm1[-1][0]
  N0i[-1][-1] = N2[-1][-1]/Npnorm2[-1][-1]
  N.append(N0i)
#print(N)
  
#Calcul de F2
F2 = []
for i in range(len(N)):
  detU1p = np.stack((detU1[i], detU1[i], detU1[i]), axis=-1)
  F2.append(N[i]/detU1p)


#Calcul de F
F = []
for i in range(len(F2)):
  A = np.zeros((100, 100, 3, 3))
  A[:,:,:,-1] = F2[i][:][:]
  A[:,:,:,:2] = F1[i][:][:]
  F.append(A)

  
#Calcul du tenseur de Green-Lagrange
Id = []
for i in range(len(F)):
  A = np.zeros((100, 100, 3, 3))
  A[:,:,:] = np.identity(3)
  Id.append(A)

E = []
for i in range(len(F)):
  E.append(0.5*(np.matmul(F[i].transpose(0,1,3,2), F[i]) - Id[i]))


#Calcul du tenseur de Hencky version abaqus
LE = []
for i in range(len(F)):
  A = np.zeros((100,100,3,3))
  A = np.matmul(F[i], F[i].transpose(0,1,3,2))
  D, P = np.linalg.eig(A)
  D = np.log(D)
  RD = np.zeros((100,100,3,3))
  RD[:,:,0,0] = D[:,:,0]
  RD[:,:,1,1] = D[:,:,1]
  RD[:,:,2,2] = D[:,:,2]
  Pinv = np.linalg.inv(P)
  LE.append(0.5*(np.matmul(np.matmul(P, RD), Pinv)))
  

#Calcul du tenseur de Hencky
H = []
for i in range(len(F)):
  A = np.zeros((100,100,3,3))
  A = np.matmul(F[i].transpose(0,1,3,2), F[i])
  D, P = np.linalg.eig(A)
  D = np.log(D)
  RD = np.zeros((100,100,3,3))
  RD[:,:,0,0] = D[:,:,0]
  RD[:,:,1,1] = D[:,:,1]
  RD[:,:,2,2] = D[:,:,2]
  Pinv = np.linalg.inv(P)
  H.append(0.5*(np.matmul(np.matmul(P, RD), Pinv)))


#Calcul du tenseur de Cauchy-Green droit
C = []
for i in range(len(F)):
  C.append(np.matmul(F[i].transpose(0,1,3,2), F[i]))


#Calcul du premier invariant des déformations
I1 = []
for i in range(len(C)):
  I1.append(np.trace(C[i], axis1=-2, axis2=-1))
  

#Calcul du second invariant des déformations
I2 = []
for i in range(len(C)):
  I2.append(0.5*(np.trace(C[i], axis1=-2, axis2=-1)**2 - np.trace(np.matmul(C[i], C[i]), axis1=-2, axis2=-1)))


##PLOTS
P = 133
#plot 3D
x = X3d[P]
y = Y3d[P]
z = Z3d[P]-Z3d[0]
fig = plt.figure(figsize = (16, 9))
ax = plt.axes(projection ="3d")
ax.grid(visible = True, color ='grey',
   linestyle ='-.', linewidth = 0.3,
   alpha = 0.2)
my_cmap = plt.get_cmap('viridis')
sctt = ax.scatter3D(x, y, z,
		  alpha = 0.8,
		  c = z,
		  cmap = my_cmap)
plt.title("Results")
ax.set_xlabel('x (mm)', fontweight ='bold')
ax.set_ylabel('y (mm)', fontweight ='bold')
ax.set_zlabel('z (mm)', fontweight ='bold')
fig.colorbar(sctt, ax = ax, shrink = 0.5, aspect = 5)
plt.show()


##plots carto tenseur

for j in range(3):

#F[i][:,:,k,l] i correspond à un certain instant, k=(0 pour x, 1 pour y, 2 pour z), l=(0 pour x, 1 pour y, 2 pour z)

  plt.imshow(F[P][:,:,j,j])
  plt.colorbar()
  plt.show()

  #plots carto tenseur en retirant les bords
  a = np.where((Xmesh-Xmesh[50][50])**2 + (Ymesh-Ymesh[50][50])**2 > ((X0max-X0min)/2)**2)
  for i in range(len(a[0])):
    F[P][a[0][i]][a[1][i]][j][j]= 'nan'
  plt.imshow(F[P][:,:,j,j])
  plt.colorbar()
  plt.savefig(f'./{date}/{sample}/{polform}/'+f'TenseurF{j}{j}_{P}-{len(X3d)}')
  plt.show()
