import numpy as np
dossier = r"2026_04_13\gonflement"      # ← votre date et sample
methode = r"nZ_12"
X = np.loadtxt(dossier + "\\" + methode + r"\X3d.txt")
Y = np.loadtxt(dossier + "\\" + methode + r"\Y3d.txt")
Z = np.loadtxt(dossier + "\\" + methode + r"\Z3d.txt")

ok0 = ~np.isnan(Z[0])
cx, cy = np.nanmean(X[0]), np.nanmean(Y[0])
centre = np.nanargmin((X[0] - cx)**2 + (Y[0] - cy)**2)   # point le plus proche du centre
print(f"{len(Z)} images traitées ; point central n°{centre}")
print("image | Uz centre | Uz min | Uz max (mm, points plausibles)")
for i in list(range(0, len(Z), max(1, len(Z)//10))) + [len(Z) - 1]:
    Uz = Z[i] - Z[0]
    plausible = ok0 & (np.abs(Uz) < 60) & (np.abs(X[i] - X[0]) < 30) & (np.abs(Y[i] - Y[0]) < 30)
    print(f"{i:5d} | {Uz[centre]:8.2f} | {np.nanmin(Uz[plausible]):7.2f} | {np.nanmax(Uz[plausible]):7.2f}")