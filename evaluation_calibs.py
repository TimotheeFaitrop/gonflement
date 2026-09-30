import numpy as np
import matplotlib.pyplot as plt



toto_L = np.load("/home/tfaitrop/Documents/Experimental/Gonflement/Machine_gonflement_1/2026_04_13/Results_Calib/Lpform_4/3D_coordinates/3D_coordinates_Lagrange.npy")
toto_S = np.load("/home/tfaitrop/Documents/Experimental/Gonflement/Machine_gonflement_1/2026_04_13/Results_Calib/Spform_555/3D_coordinates/3D_coordinates_Soloff.npy")
toto_Z = np.load("/home/tfaitrop/Documents/Experimental/Gonflement/Machine_gonflement_1/2026_04_13/Results_Calib/nZ_12/3D_coordinates/3D_coordinates_Zernike.npy")




x_L, y_L, z_L = [],[],[]
x_S, y_S, z_S = [],[],[]
x_Z, y_Z, z_Z = [],[],[]


for i in range(len(toto_L[0])):
    x_L.append(toto_L[0][i])
    y_L.append(toto_L[1][i])
    z_L.append(toto_L[2][i])

for i in range(len(toto_S[0])):
    x_S.append(toto_S[0][i])
    y_S.append(toto_S[1][i])
    z_S.append(toto_S[2][i])

for i in range(len(toto_Z[0])):
    x_Z.append(toto_Z[0][i])
    y_Z.append(toto_Z[1][i])
    z_Z.append(toto_Z[2][i])




ax = plt.figure().add_subplot(111,projection='3d')
ax.scatter(x_L, y_L, z_L, label = "Lagrange")
ax.scatter(x_L, y_S, z_S, label = "Soloff")
ax.scatter(x_Z, y_Z, z_Z, label = "Zernike")
ax.set_xlabel('X')
ax.set_ylabel('Y')
ax.set_zlabel('Z')
plt.legend()
plt.title("Points de calibration")
plt.show(block=False)

z_diff_LS, z_diff_LZ, z_diff_ZS = [],[],[]


for i in range(len(toto_L[0])):
    z_diff_LS.append(toto_L[2][i]-toto_S[2][i])

aaa = len(toto_S[0])

for i in range(aaa):
    z_diff_LZ.append(toto_L[2][i]-toto_Z[2][i])

for i in range(len(toto_Z[0])):
    z_diff_ZS.append(toto_Z[2][i] - toto_S[2][i])


ax = plt.figure().add_subplot(111,projection='3d')
#ax.scatter(x_L, y_L, z_diff_LS, label ="Lagrange - Soloff")
ax.scatter(x_S, y_S, z_diff_LZ, label = "Lagrange - Zernike")
#ax.scatter(x_Z, y_Z, z_diff_ZS, label ="Zernike - Soloff")
ax.set_xlabel('X')
ax.set_ylabel('Y')
ax.set_zlabel('Z')
plt.legend()
plt.title("Différence entre chaque modèle")
plt.show(block=False)



diff_z_L=z_L
diff_z_S=z_S
diff_z_Z=z_Z

X_consigne=[]
Y_consigne=[]
Z_consigne=[]

for k in range(220):
    for i in range(11):
        X_consigne.append(82.5-i*7.5)


for k in range (20):
    for j in range(11):
        for i in range(11):
            Y_consigne.append(7.5*(j+1))


for i in range(len(diff_z_L)):
    consigne = 70 - 2* i//121
    if consigne%2==1:
        consigne = consigne + 1
    Z_consigne.append(consigne)


for k in range(len(diff_z_L)):
    """print(diff_z_L[k])
    print(Z_consigne[k])"""
    diff_z_L[k]-=Z_consigne[k]
    diff_z_S[k]-=Z_consigne[k]
    diff_z_Z[k]-=Z_consigne[k]



ax = plt.figure().add_subplot(111,projection='3d')
ax.scatter(x_L, y_L, diff_z_L, label = "Diff consigne Lagrange")
ax.scatter(x_S, y_S, diff_z_S, label = "Diff consigne Soloff")
ax.scatter(x_Z, y_Z, diff_z_Z, label = "Diff consigne Zernike")
ax.set_xlabel('X')
ax.set_ylabel('Y')
ax.set_zlabel('Z')
plt.legend()
plt.title("Différence par rapport à la consigne")
plt.show()


def plot_boxplot_by_value(z_consigne, diff_z, label, ax, label_abs):
    z_consigne = np.array(z_consigne)
    diff_z = np.array(diff_z)
    
    unique_vals = np.sort(np.unique(z_consigne))
    grouped = [diff_z[z_consigne == val] for val in unique_vals]

    ax.boxplot(grouped, tick_labels=[f"{v:.1f}" for v in unique_vals])
    ax.axhline(0, color='red', linewidth=0.8, linestyle='--')
    ax.set_ylabel("Différence Z consigne/mesure")
    ax.set_title(label)
    
    ax.set_xlabel(label_abs)
    ax.tick_params(axis='x', rotation=45)



fig, axes = plt.subplots(1, 3, figsize=(15, 5))
plot_boxplot_by_value(np.array(X_consigne), np.array(diff_z_L), "Lagrange", axes[0], label_abs="X consigne")
plot_boxplot_by_value(np.array(X_consigne), np.array(diff_z_S), "Soloff",   axes[1], label_abs="X consigne")
plot_boxplot_by_value(np.array(X_consigne), np.array(diff_z_Z), "Zernike",  axes[2], label_abs="X consigne")

plt.suptitle("Boxplot par valeur de X consigne")
plt.tight_layout()
plt.show()

fig, axes = plt.subplots(1, 3, figsize=(15, 5))
plot_boxplot_by_value(np.array(Y_consigne), np.array(diff_z_L), "Lagrange", axes[0], label_abs="Y consigne")
plot_boxplot_by_value(np.array(Y_consigne), np.array(diff_z_S), "Soloff",   axes[1], label_abs="Y consigne")
plot_boxplot_by_value(np.array(Y_consigne), np.array(diff_z_Z), "Zernike",  axes[2], label_abs="Y consigne")

plt.suptitle("Boxplot par valeur de Y consigne")
plt.tight_layout()
plt.show()

fig, axes = plt.subplots(1, 3, figsize=(15, 5))
plot_boxplot_by_value(np.array(Z_consigne), np.array(diff_z_L), "Lagrange", axes[0], label_abs="Z consigne")
plot_boxplot_by_value(np.array(Z_consigne), np.array(diff_z_S), "Soloff",   axes[1], label_abs="Z consigne")
plot_boxplot_by_value(np.array(Z_consigne), np.array(diff_z_Z), "Zernike",  axes[2], label_abs="Z consigne")

plt.suptitle("Boxplot par valeur de Z consigne")
plt.tight_layout()
plt.show()


