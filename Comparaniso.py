import numpy as np
from scipy.optimize import least_squares
from scipy.interpolate import Rbf
from matplotlib.patches import Ellipse
import matplotlib.pyplot as plt
from glob import glob


ax = plt.axes()
ax.set_xlabel('Z',fontsize=15)
ax.set_ylabel('b/a',fontsize=15)
inter_PER = np.linspace(0.55, 0.8, 100)

theta0 = [1, 1]

def flin(theta, x):
  return theta[0]*x + theta[1]

def fun(theta,PER,Lr):
  return flin(theta, np.array(PER)) - np.array(Lr)

def fit_ellipse(x,y):
    x = x[:,np.newaxis]
    y = y[:,np.newaxis]
    D =  np.hstack((x*x, x*y, y*y, x, y, np.ones_like(x)))
    S = np.dot(D.T,D)
    C = np.zeros([6,6])
    C[0,2] = C[2,0] = 2; C[1,1] = -1
    E, V =  np.linalg.eig(np.dot(np.linalg.inv(S), C))
    n = np.argmax(np.abs(E))
    a = V[:,n]
    return a


def f_aniso(date,
            sample,
            form,
            method,
            version = '',
            P1 = 228):


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


    X3d = np.loadtxt(fname=f'./{date}/{sample}/{polform}/X3d.txt', delimiter=' ')[:ip+1]
    Y3d = np.loadtxt(fname=f'./{date}/{sample}/{polform}/Y3d.txt', delimiter=' ')[:ip+1]
    Z3d = np.loadtxt(fname=f'./{date}/{sample}/{polform}/Z3d.txt', delimiter=' ')[:ip+1]

    print(len(X3d),len(Y3d),len(Z3d))
    X0min = min(X3d[0])
    X0max = max(X3d[0])
    Y0min = min(Y3d[0])
    Y0max = max(Y3d[0])
    Zmin = min(Z3d[ip])
    Zmax = max(Z3d[ip])

    cx = (X0max-X0min)/2 + X0min
    cy = (Y0max-Y0min)/2 + Y0min

    Xmesh, Ymesh = np.meshgrid(np.linspace(X0min, X0max, 200), np.linspace(Y0min, Y0max, 200), indexing='xy')
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


    Xmeshc = Xmesh.copy()
    Ymeshc = Ymesh.copy()
    c=0
    a = np.where((Xmesh-Xmesh[100][100])**2 + (Ymesh-Ymesh[100][100])**2 > ((X0max-X0min)/2)**2)
    for i in range(len(Xmesh)):
        for j in range(len(Ymesh)):
            if ((Xmesh[i][j]-Xmesh[100][100])**2 + (Ymesh[i][j]-Ymesh[100][100])**2) > ((X0max-X0min)/2)**2:
                Xmeshc[i][j] = 'nan'
                Ymeshc[i][j] = 'nan'
                c+=1

    XXc = []
    YYc = []
    ZZc = []

    for i in range(len(Rbfx)):
        XXc.append(Rbfx[i](Xmeshc, Ymeshc))
        YYc.append(Rbfy[i](Xmeshc, Ymeshc))
        ZZc.append(Rbfz[i](Xmeshc, Ymeshc))

    #Calcul des vecteurs déplacements
    Uxc = []
    Uyc = []
    Uzc = []

    for i in range(len(XXc)):
        Uxc.append(XXc[i] - XXc[0])
        Uyc.append(YYc[i] - YYc[0])
        Uzc.append(ZZc[i] - ZZc[0])

    x0 = XXc[0][~np.isnan(XXc[0])]
    y0 = YYc[0][~np.isnan(YYc[0])]
    z0 = ZZc[0][~np.isnan(ZZc[0])]
    xp = XXc[ip][~np.isnan(XXc[ip])]
    yp = YYc[ip][~np.isnan(YYc[ip])]
    zp = ZZc[ip][~np.isnan(ZZc[ip])]

    Upx = xp-x0
    Upy = yp-y0
    Upz = zp-z0
    if method != 'Soloff' :
        Upz=-Upz


    PER = [i for i in np.arange(0.55, 1.05, 0.05)]
    Lr = []
    PER2 = []
    Lstd = []
    for per in PER:
        print(per)
        try:
            w = np.where(np.round(Upz,1)==np.round(per*max(Upz),1))
            res = fit_ellipse(xp[w], yp[w])
            a = (-np.sqrt(2*(res[0]*res[4]**2 + res[2]*res[3]**2 - res[1]*res[3]*res[4] + (res[1]**2 - 4*res[0]*res[2])*res[5])*((res[0]+res[2]) + np.sqrt((res[0]-res[2])**2 + res[1]**2))))/(res[1]**2 - 4*res[0]*res[2])
            b = (-np.sqrt(2*(res[0]*res[4]**2 + res[2]*res[3]**2 - res[1]*res[3]*res[4] + (res[1]**2 - 4*res[0]*res[2])*res[5])*((res[0]+res[2]) - np.sqrt((res[0]-res[2])**2 + res[1]**2))))/(res[1]**2 - 4*res[0]*res[2])
            x0 = (2*res[2]*res[3] - res[1]*res[4])/(res[1]**2 - 4*res[0]*res[2])
            y0 = (2*res[0]*res[4] - res[1]*res[3])/(res[1]**2 - 4*res[0]*res[2])
            teh = np.arctan((res[2] - res[0] - np.sqrt((res[0] - res[2])**2 + res[1]**2))/res[1])
            print('aniso:', min(b/a, a/b))
            print('angle:', teh*180/np.pi)
            Lr.append(min(b/a, a/b))
            Lstd.append(np.std(b/a))
            PER2.append(per)
            #fig, ax = plt.subplots(subplot_kw={'aspect': 'equal'})
            e = Ellipse(xy = [x0, y0], width = 2*a, height = 2*b, angle = 180*teh/np.pi, facecolor='white', edgecolor='b', linewidth=12)
            #ax.add_artist(e)
            #plt.scatter(xp[w], yp[w], c='r', linewidths=0.02)
            #ax.set_xlabel('x (mm)')
            #ax.set_ylabel('y (mm)')
            #plt.xlim(10,80)
            #plt.ylim(10,80)
            #plt.show()
        except np.linalg.LinAlgError :
            print('Pas de correspondance')

    PER=PER2
    return PER,Lr

def Z_const(PER, Lr, Z1):
    DiffUz = []
    for i in range(len(PER)):
        DiffUz.append(PER[i] - Z1)
    ip = np.where(np.diff(np.sign(DiffUz)))[0][0]
    return Lr[ip]

date = '2025_07_03'
sample = 'SC37_20_P7NR'
polform = 'Spform_555'
method = 'Soloff'

PER1,Lr1 = f_aniso(date,sample,polform,method)
#res = least_squares(fun, theta0, args=(PER1,Lr1))
plt.scatter(PER1, Lr1, label='P7 non résorbé',c='darkgreen')
##plt.plot(inter_PER, flin(res.x, inter_PER))

date = '2025_06_04'
sample = 'SC37_20_P7NR'
polform = 'Spform_555'
method='Soloff'
PER1,Lr1 = f_aniso(date,sample,polform,method)
res = least_squares(fun, theta0, args=(PER1,Lr1))
plt.scatter(PER1, Lr1, label=f'{sample}_pente={np.round(res.x[0],3)}')
#plt.plot(inter_PER, flin(res.x, inter_PER))



date = '2025_07_02'
sample = 'SC37_20_P7_8j'
polform = 'Spform_555'
method = 'Soloff'
PER2,Lr2 = f_aniso(date,sample,polform,method)
res = least_squares(fun, theta0, args=(PER2,Lr2))
plt.scatter(PER2, Lr2, label=f'{sample}_pente={np.round(res.x[0],3)}')
#plt.plot(inter_PER, flin(res.x, inter_PER))

date = '2025_06_13'
sample = 'SC37_20_P7_8j'
polform = 'Spform_555'
method='Soloff'
PER2,Lr2 = f_aniso(date,sample,polform,method)
res = least_squares(fun, theta0, args=(PER2,Lr2))
plt.scatter(PER2, Lr2, label=f'{sample}_pente={np.round(res.x[0],3)}')
#plt.plot(inter_PER, flin(res.x, inter_PER))

date = '2025_06_16'
sample = 'SC37_20_P7_8j'
polform = 'Spform_555'
method='Soloff'
PER2,Lr2 = f_aniso(date,sample,polform,method)
#res = least_squares(fun, theta0, args=(PER2,Lr2))
plt.scatter(PER2, Lr2, label='P7 8j',c='forestgreen')
#plt.plot(inter_PER, flin(res.x, inter_PER))


date = '2025_06_18'
sample = 'SC37_20_P7_16j'
polform = 'Spform_555'
method='Soloff'

PER3,Lr3 = f_aniso(date,sample,polform,method)
res = least_squares(fun, theta0, args=(PER3,Lr3))
plt.scatter(PER3, Lr3, label=f'{sample}_pente={np.round(res.x[0],3)}')
#plt.plot(inter_PER, flin(res.x, inter_PER))


date = '2025_06_10'
sample = 'SC37_20_P7_16j'
polform = 'Spform_555'
method='Soloff'
PER3,Lr3 = f_aniso(date,sample,polform,method)
#res = least_squares(fun, theta0, args=(PER3,Lr3))
plt.scatter(PER3, Lr3, label='P7 16j',c='limegreen')
#plt.plot(inter_PER, flin(res.x, inter_PER))

date = '2025_06_17'
sample = 'SC37_20_P7_16j'
polform = 'Spform_555'
method='Soloff'
PER3,Lr3 = f_aniso(date,sample,polform,method)
res = least_squares(fun, theta0, args=(PER3,Lr3))
plt.scatter(PER3, Lr3, label=f'{sample}_pente={np.round(res.x[0],3)}')
#plt.plot(inter_PER, flin(res.x, inter_PER))


date = '2025_06_20'
sample = 'SC37_20_P7_21j'
polform = 'Spform_555'
method='Soloff'

PER4,Lr4 = f_aniso(date,sample,polform,method)
#res = least_squares(fun, theta0, args=(PER4,Lr4))
plt.scatter(PER4, Lr4, label='P7 21j',c='lightgreen')
#plt.plot(inter_PER, flin(res.x, inter_PER))


date = '2025_07_01'
sample = 'SC37_20_P7_30j'
polform = 'Spform_555/Jumping'
method='Soloff'

PER5,Lr5 = f_aniso(date,sample,polform,method,version='_00001')
#res = least_squares(fun, theta0, args=(PER5,Lr5))
plt.scatter(PER5, Lr5, label='P7 30j',c='lime')
#plt.plot(inter_PER, flin(res.x, inter_PER))

date = '2025_07_07'
sample = 'SC37_20'
polform = 'Spform_555'
method='Soloff'

PER6,Lr6 = f_aniso(date,sample,polform,method)
#res = least_squares(fun, theta0, args=(PER6,Lr6))
plt.scatter(PER6, Lr6, label='Silicone',c='blue')
###plt.plot(inter_PER, flin(res.x, inter_PER))


date = '2025_07_21'
sample = 'Pro_Grip'
polform = 'Spform_555'
method='Soloff'

PER7,Lr7 = f_aniso(date,sample,polform,method)
#res = least_squares(fun, theta0, args=(PER7,Lr7))
plt.scatter(PER7, Lr7, label='Pro_Grip',c='red')

plt.legend()
plt.title("Anisotropie -Press = 228 mbar")
plt.show()



######## Comparaison à hauteur constante #########

Z1 = 0.75
Lr = []
Samples = ['P7 non-résorbé','P7 8j','P7 16j', 'P7 21j', 'P7 30j','Silicone','Pro_Grip']


date = '2025_07_03'
sample = 'SC37_20_P7NR'
polform = 'Spform_555'
method = 'Soloff'

PER1,Lr1 = f_aniso(date,sample,polform,method)
Lr.append(Z_const(PER1,Lr1,Z1))

date = '2025_06_16'
sample = 'SC37_20_P7_8j'
polform = 'Spform_555'
method='Soloff'

PER2,Lr2 = f_aniso(date,sample,polform,method)
Lr.append(Z_const(PER2,Lr2,Z1))

#date = '2025_06_05'
#sample = 'SC37_20_P7_8j'
#polform = 'Spform_555'
#method = 'Soloff'

#PER2,Lr2 = f_aniso(date,sample,polform,method)
#Lr.append(Z_const(PER2,Lr2,Z1))

#date = '2025_06_13'
#sample = 'SC37_20_P7_8j'
#polform = 'Spform_555'
#method='Soloff'

#PER2,Lr2 = f_aniso(date,sample,polform,method)
#Lr.append(Z_const(PER2,Lr2,Z1))


date = '2025_06_10'
sample = 'SC37_20_P7_16j'
polform = 'Spform_555'
method='Soloff'

PER3,Lr3 = f_aniso(date,sample,polform,method)
Lr.append(Z_const(PER3,Lr3,Z1))


#date = '2025_06_18'
#sample = 'SC37_20_P7_21j'
#polform = 'Spform_555'
#method='Soloff'

#PER4,Lr4 = f_aniso(date,sample,polform,method)
#Lr.append(Z_const(PER4,Lr4,Z1))

date = '2025_06_20'
sample = 'SC37_20_P7_21j'
polform = 'Spform_555'
method='Soloff'

PER4,Lr4 = f_aniso(date,sample,polform,method)
Lr.append(Z_const(PER4,Lr4,Z1))


date = '2025_07_01'
sample = 'SC37_20_P7_30j'
polform = 'Spform_555/Jumping'
method='Soloff'

PER5,Lr5 = f_aniso(date,sample,polform,method,version='_00001')
Lr.append(Z_const(PER5,Lr5,Z1))

#date = '2025_06_26'
#sample = 'SC37_20_P7_30j'
#polform = 'Spform_555/Max'
#method='Soloff'

#PER5,Lr5 = f_aniso(date,sample,polform,method,version='_00002')
#Lr.append(Z_const(PER5,Lr5,Z1))


date = '2025_07_07'
sample = 'SC37_20'
polform = 'Spform_555'
method='Soloff'

PER6,Lr6 = f_aniso(date,sample,polform,method)
Lr.append(Z_const(PER6,Lr6,Z1))

date = '2025_07_21'
sample = 'Pro_Grip'
polform = 'Spform_555'
method='Soloff'

PER7,Lr7 = f_aniso(date,sample,polform,method)
Lr.append(Z_const(PER7,Lr7,Z1))

date = '2025_06_04'
sample = 'SC37_20_P7NR'
polform = 'Spform_555'
method='Soloff'

PER1,Lr1 = f_aniso(date,sample,polform,method)
Lr.append(Z_const(PER1,Lr1,Z1))


date = '2025_06_17'
sample = 'SC37_20_P7_16j'
polform = 'Spform_555'
method='Soloff'

PER3,Lr3 = f_aniso(date,sample,polform,method)
Lr.append(Z_const(PER3,Lr3,Z1))

date = '2025_06_25'
sample = 'SC37_20_P7_21j'
polform = 'Spform_555/Jumping'
method='Soloff'

PER4,Lr4 = f_aniso(date,sample,polform,method)
Lr.append(Z_const(PER4,Lr4,Z1))




date = '2025_07_07'
sample = 'SC37_20_P7_30j'
polform = 'Spform_555'
method='Soloff'

PER5,Lr5 = f_aniso(date,sample,polform,method,version='')
Lr.append(Z_const(PER5,Lr5,Z1))

fig,ax=plt.subplots()
ax.scatter([0],Lr[0], c='darkgreen', s=80)
ax.scatter([1],Lr[1], c='forestgreen', s=80)
ax.scatter([2],Lr[2], c='limegreen', s=80)
ax.scatter([3],Lr[3], c='lime', s=80)
ax.scatter([4],Lr[4], c='lawngreen', s=80)
ax.scatter([5],Lr[5], c='blue', s=80)
ax.scatter([6],Lr[6], c='red', s=80)

ax.xaxis.set_ticks(range(7))
ax.xaxis.set_ticklabels(Samples,fontsize=12)
ax.set_xlabel('Échantillon',fontsize=18)
ax.set_ylabel('b/a',fontsize=18)
ax.set_ylim(0.4,1)
plt.title(f'Anisotropie_Z=0.75*Zmax')
plt.show()
