import numpy as np
dossier = r"2026_04_13\gonflement"                 # ← votre date et sample
methode = r"Lpform_4"
X = np.loadtxt(dossier + "\\" + methode + r"\X3d.txt")
Y = np.loadtxt(dossier + "\\" + methode + r"\Y3d.txt")
Z = np.loadtxt(dossier + "\\" + methode + r"\Z3d.txt")

# Boîte plausible : autour de l'état initial, le dôme peut monter de 50 mm
xmin, xmax = np.nanmin(X[0]) - 10, np.nanmax(X[0]) + 10
ymin, ymax = np.nanmin(Y[0]) - 10, np.nanmax(Y[0]) + 10
zmin, zmax = np.nanmin(Z[0]) - 5,  np.nanmax(Z[0]) + 50
aberrant = (X < xmin) | (X > xmax) | (Y < ymin) | (Y > ymax) | (Z < zmin) | (Z > zmax)

print("Points aberrants par image :", aberrant.sum(axis=1).tolist())
print("Numéros des points aberrants à la dernière image :", np.where(aberrant[-1])[0].tolist())
premiere = [int(np.argmax(aberrant[:, j])) if aberrant[:, j].any() else None for j in range(X.shape[1])]
print("Image où chaque point devient aberrant :", {j: p for j, p in enumerate(premiere) if p is not None})

# Écart entre taches voisines sur l'image gauche, en pixels
px = np.load(dossier + r"\all_pxl.npy", allow_pickle=True)[0].astype(float)
py = np.load(dossier + r"\all_pyl.npy", allow_pickle=True)[0].astype(float)
ok = ~np.isnan(px)
P = np.column_stack([px[ok], py[ok]])
d = np.sqrt(((P[:, None] - P[None]) ** 2).sum(-1)); np.fill_diagonal(d, np.inf)
print(f"Distance à la tache la plus proche (px) : min {d.min(1).min():.0f}, médiane {np.median(d.min(1)):.0f}")