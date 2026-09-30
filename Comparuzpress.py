import numpy as np
from scipy.interpolate import Rbf
import matplotlib.pyplot as plt
from glob import glob
from math import *
from scipy.optimize import least_squares



def f(date,sample,polform,method,version=''):
    X3d = np.loadtxt(fname=f'./{date}/{sample}/{polform}/X3d.txt', delimiter=' ')
    Y3d = np.loadtxt(fname=f'./{date}/{sample}/{polform}/Y3d.txt', delimiter=' ')
    Z3d = np.loadtxt(fname=f'./{date}/{sample}/{polform}/Z3d.txt', delimiter=' ')


    Création du maillage
    X0min = min(X3d[0])
    X0max = max(X3d[0])
    Y0min = min(Y3d[0])
    Y0max = max(Y3d[0])
    Zmin = min(Z3d[0])
    Zmax = max(Z3d[-1])

    Xmesh, Ymesh = np.meshgrid(np.linspace(X0min, X0max,100), np.linspace(Y0min, Y0max,100), indexing='xy')
    Ymesh = np.flip(Ymesh)

    Fonctions interpolatrices
    interpfunction = 'linear'
    Rbfx = []
    Rbfy = []
    Rbfz = []
    for i in range(len(X3d)):
        Rbfx.append(Rbf(X3d[0], Y3d[0], X3d[i], function=interpfunction))
        Rbfy.append(Rbf(X3d[0], Y3d[0], Y3d[i], function=interpfunction))
        Rbfz.append(Rbf(X3d[0], Y3d[0], Z3d[i], function=interpfunction))


    Interpolation des positions
    XX = []
    YY = []
    ZZ = []
    for i in range(len(Rbfx)):
        XX.append(Rbfx[i](Xmesh, Ymesh))
        YY.append(Rbfy[i](Xmesh, Ymesh))
        ZZ.append(Rbfz[i](Xmesh, Ymesh))


    Calcul des vecteurs déplacements
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

    Récupération de la pression à chaque image
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



    Rbfpress = Rbf(Tp, Pp)
    Press = Rbfpress(Ltime2)

    return Press,Uzmax,sample



def UzConst(date,sample,polform,method,Uz1=20,version=''):

    Press,Uzmax,sample = f(date,sample,polform,method,version)

    #Récupération de l'indice où Uzmax = Uzmax1
    DiffUz = []
    for i in range(len(Uzmax)):
        DiffUz.append(Uzmax[i] - Uz1)
    ip = np.where(np.diff(np.sign(DiffUz)))[0][0]

    P = Press[ip] - Press[0]

    return P,sample



def PConst(date,sample,polform,method,P1=10,version=''):

    Press,Uzmax,sample = f(date,sample,polform,method,version)

    #Récupération de l'indice où pression = P1
    DiffP = Press - P1
    print(np.where(np.diff(np.sign(DiffP))))
    ip = np.where(np.diff(np.sign(DiffP)))[0][0]

    return Uzmax[ip],sample

## Graphiques Pression_Uzmax ###


fig,ax=plt.subplots()
plt.xlim(0,40)
plt.ylim(0,300)
ax.set_xlabel('Déplacement max (mm)',fontsize=15)
ax.set_ylabel('Pressure (mbar)',fontsize=15)


date = '2025_07_03'
sample = 'SC37_20_P7NR'
polform = 'Spform_555'
method='Soloff'


Press1,Uzmax1,sample1=f(date,sample,polform,method)
Press1,Uzmax1 = Press1[5:] - Press1[5], Uzmax1[5:] - Uzmax1[5]
plt.plot(Uzmax1,Press1,label='P7 non-résorbé',c='darkgreen')


date = '2025_06_16'
sample = 'SC37_20_P7_8j'
polform = 'Spform_555'
method='Soloff'

Press2,Uzmax2,sample2=f(date,sample,polform,method)
plt.plot(Uzmax2,Press2[:],label='P7 8j',c='forestgreen')


date = '2025_06_10'
sample = 'SC37_20_P7_16j'
polform = 'Spform_555'
method='Soloff'

Press3,Uzmax3,sample3=f(date,sample,polform,method)
plt.plot(Uzmax3,Press3[:],label='P7 16j',c='limegreen')


date = '2025_06_18'
sample = 'SC37_20_P7_21j'
polform = 'Spform_555'
method='Soloff'
Press4,Uzmax4,sample4=f(date,sample,polform,method)
plt.plot(Uzmax4,Press4[:],label='P7 21j',c='lime')


date = '2025_06_26'
sample = 'SC37_20_P7_30j'
polform = 'Spform_555/Max'
method='Soloff'


Press5,Uzmax5,sample5=f(date,sample,polform,method,'_00002')
plt.plot(Uzmax5[:],Press5[:],label='P7 30j',c='lawngreen')

date = '2025_07_07'
sample = 'SC37_20'
polform = 'Spform_555'
method='Soloff'


Press6,Uzmax6,sample6=f(date,sample,polform,method)
plt.plot(Uzmax6[:],Press6[:],label='Silicone',c='blue')



date = '2025_07_21'
sample = 'Pro_Grip'
polform = 'Spform_555'
method='Soloff'


Press8,Uzmax8,sample8=f(date,sample,polform,method)
plt.plot(Uzmax8,Press8[:],label=sample8,c='red')

plt.legend(fontsize=12)
plt.show()



# Comparaison de la pression à Uzmax constant

Uz1 = 10

date = '2025_07_03'
sample = 'SC37_20_P7NR'
polform = 'Spform_555'
method='Soloff'

P1, sample1 = UzConst(date,sample,polform,method,Uz1)


date = '2025_07_02'
sample = 'SC37_20_P7_8j'
polform = 'Spform_555'
method='Soloff'

P2,sample2 = UzConst(date,sample,polform,method,Uz1)


date = '2025_06_17'
sample = 'SC37_20_P7_16j'
polform = 'Spform_555'
method='Soloff'


P3,sample3 = UzConst(date,sample,polform,method,Uz1)


date = '2025_06_18'
sample = 'SC37_20_P7_21j'
polform = 'Spform_555'
method='Soloff'

P4,sample4 = UzConst(date,sample,polform,method,Uz1)


date = '2025_07_07'
sample = 'SC37_20_P7_30j'
polform = 'Spform_555'
method='Soloff'

P5,sample5 = UzConst(date,sample,polform,method,Uz1)

date = '2025_07_07'
sample = 'SC37_20'
polform = 'Spform_555'
method='Soloff'

P6,sample6 = UzConst(date,sample,polform,method,Uz1)

Puz10 = [P1,P2,P3,P4,P5,P6]



Uz1=15

date = '2025_07_03'
sample = 'SC37_20_P7NR'
polform = 'Spform_555'
method='Soloff'

P1, sample1 = UzConst(date,sample,polform,method,Uz1)


date = '2025_07_02'
sample = 'SC37_20_P7_8j'
polform = 'Spform_555'
method='Soloff'

P2,sample2 = UzConst(date,sample,polform,method,Uz1)


date = '2025_06_17'
sample = 'SC37_20_P7_16j'
polform = 'Spform_555'
method='Soloff'


P3,sample3 = UzConst(date,sample,polform,method,Uz1)


date = '2025_06_18'
sample = 'SC37_20_P7_21j'
polform = 'Spform_555'
method='Soloff'

P4,sample4 = UzConst(date,sample,polform,method,Uz1)


date = '2025_07_07'
sample = 'SC37_20_P7_30j'
polform = 'Spform_555'
method='Soloff'

P5,sample5 = UzConst(date,sample,polform,method,Uz1)

date = '2025_07_07'
sample = 'SC37_20'
polform = 'Spform_555'
method='Soloff'

P6,sample6 = UzConst(date,sample,polform,method,Uz1)

Puz15 = [P1,P2,P3,P4,P5,P6]



Uz1=20

date = '2025_07_03'
sample = 'SC37_20_P7NR'
polform = 'Spform_555'
method='Soloff'

P1, sample1 = UzConst(date,sample,polform,method,Uz1)


date = '2025_07_02'
sample = 'SC37_20_P7_8j'
polform = 'Spform_555'
method='Soloff'

P2,sample2 = UzConst(date,sample,polform,method,Uz1)


date = '2025_06_17'
sample = 'SC37_20_P7_16j'
polform = 'Spform_555'
method='Soloff'


P3,sample3 = UzConst(date,sample,polform,method,Uz1)


date = '2025_06_18'
sample = 'SC37_20_P7_21j'
polform = 'Spform_555'
method='Soloff'

P4,sample4 = UzConst(date,sample,polform,method,Uz1)


date = '2025_07_07'
sample = 'SC37_20_P7_30j'
polform = 'Spform_555'
method='Soloff'

P5,sample5 = UzConst(date,sample,polform,method,Uz1)

date = '2025_07_07'
sample = 'SC37_20'
polform = 'Spform_555'
method='Soloff'

P6,sample6 = UzConst(date,sample,polform,method,Uz1)

Puz20 = [P1,P2,P3,P4,P5,P6]

Samples = [sample1,sample2,sample3,sample4,sample5,sample6]
fig,ax = plt.subplots()
ax.scatter(range(6), Puz10,label = 'Uzmax=10')
ax.scatter(range(6), Puz15,label = 'Uzmax=15')
ax.scatter(range(6), Puz20,label = 'Uzmax=20')
ax.xaxis.set_ticks(range(6))
ax.xaxis.set_ticklabels(Samples)
ax.set_xlabel('Échantillons')
ax.set_ylabel('Pression (mbar)')
plt.legend(fontsize = 10)
plt.show()

######Pression Constante############################
P1 = 143.5
UZMAXs = []
Samples = []

date = '2025_07_03'
sample = 'SC37_20_P7NR'
polform = 'Spform_555'
method='Soloff'


Press,Uzmax,sample = f(date,sample,polform,method)
Press,Uzmax=Press[5:]-Press[5],Uzmax[5:]-Uzmax[5]
DiffP = Press - P1
ip = np.where(np.diff(np.sign(DiffP)))[0][0]
UZMAXs.append(Uzmax[ip])

date = '2025_06_16'
sample = 'SC37_20_P7_8j'
polform = 'Spform_555'
method='Soloff'


UZMAXs.append(PConst(date,sample,polform,method,P1)[0])




date = '2025_06_10'
sample = 'SC37_20_P7_16j'
polform = 'Spform_555'
method='Soloff'

UZMAXs.append(PConst(date,sample,polform,method,P1)[0])



date = '2025_06_18'
sample = 'SC37_20_P7_21j'
polform = 'Spform_555'
method='Soloff'

UZMAXs.append(PConst(date,sample,polform,method,P1)[0])



date = '2025_06_26'
sample = 'SC37_20_P7_30j'
polform = 'Spform_555/Max'
method='Soloff'

UZMAXs.append(PConst(date,sample,polform,method,P1,'_00002')[0])

date = '2025_07_07'
sample = 'SC37_20'
polform = 'Spform_555'
method='Soloff'

UZMAXs.append(PConst(date,sample,polform,method,P1)[0])


date = '2025_07_21'
sample = 'Pro_Grip'
polform = 'Spform_555'
method='Soloff'

UZMAXs.append(PConst(date,sample,polform,method,P1,'')[0])

date = '2025_06_04'
sample = 'SC37_20_P7NR'
polform = 'Spform_555'
method='Soloff'

UZMAXs.append(PConst(date,sample,polform,method,P1)[0])




date = '2025_06_05'
sample = 'SC37_20_P7_8j'
polform = 'Spform_555'
method='Soloff'

UZMAXs.append(PConst(date,sample,polform,method,P1)[0])


date = '2025_06_17'
sample = 'SC37_20_P7_16j'
polform = 'Spform_555'
method='Soloff'

UZMAXs.append(PConst(date,sample,polform,method,P1)[0])



date = '2025_07_01'
sample = 'SC37_20_P7_30j'
polform = 'Spform_555/Jumping'
method='Soloff'

UZMAXs.append(PConst(date,sample,polform,method,P1,'_00001')[0])


date = '2025_07_07'
sample = 'SC37_20_P7_30j'
polform = 'Spform_555'
method='Soloff'

Press,Uzmax,sample = f(date,sample,polform,method)
Press,Uzmax=Press[2:]-Press[2],Uzmax[2:]-Uzmax[2]
DiffP = Press - P1
ip = np.where(np.diff(np.sign(DiffP)))[0][0]
UZMAXs.append(Uzmax[ip])





Samples = ['P7 non-résorbé','P7 8j','P7 16j', 'P7 21j', 'P7 30j','Silicone','Pro_Grip']

fig,ax=plt.subplots()
ax.scatter([0],UZMAXs[0], c='darkgreen', s=80)
ax.scatter([1],UZMAXs[1], c='forestgreen', s=80)
ax.scatter([2],UZMAXs[2], c='limegreen', s=80)
ax.scatter([3],UZMAXs[3], c='lime', s=80)
ax.scatter([4],UZMAXs[4], c='lawngreen', s=80)
ax.scatter([5],UZMAXs[5], c='blue', s=80)
ax.scatter([6],UZMAXs[6], c='red', s=80)

ax.xaxis.set_ticks(range(7))
ax.xaxis.set_ticklabels(Samples,fontsize=12)
ax.set_xlabel('Échantillon', fontsize=18)
ax.set_ylabel('Déplacement max (mm)',fontsize=18)
plt.title('Déplacements max, Toux')
plt.show()
