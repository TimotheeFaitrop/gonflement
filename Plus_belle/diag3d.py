import numpy as np
dossier = r"2026_04_13\gonflement\Lpform_4"     # ← votre date, sample et méthode
X = np.loadtxt(dossier + r"\X3d.txt")
Y = np.loadtxt(dossier + r"\Y3d.txt")
Z = np.loadtxt(dossier + r"\Z3d.txt")
print("image | points valides | X min-max | Y min-max | Z min-max (mm)")
for i in range(len(X)):
    ok = ~np.isnan(X[i])
    if ok.any():
        print(f"{i:5d} | {ok.sum():4d} / {len(X[i])} | "
              f"{np.nanmin(X[i]):7.1f} {np.nanmax(X[i]):7.1f} | "
              f"{np.nanmin(Y[i]):7.1f} {np.nanmax(Y[i]):7.1f} | "
              f"{np.nanmin(Z[i]):7.1f} {np.nanmax(Z[i]):7.1f}")
    else:
        print(f"{i:5d} | 0 / {len(X[i])}")