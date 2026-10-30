"""Interface tkinter de la calibration stéréo.

Usage depuis un script :
    from Pycaso.calibration_gui import run_calibration_gui
    run_calibration_gui()

Les hauteurs (z initial, z final, pas) sont lues dans hauteurs_calibration.txt, écrit par
l'acquisition dans le dossier des images de calibration, et recopiées dans les champs dès que
ce dossier est choisi. Elles restent modifiables à la main.
"""

import os
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

try:  # import depuis un script extérieur : from Pycaso.calibration_gui import ...
    from .calibration_class import Calibration
    from .style_gui import Style
except ImportError:  # exécution directe : python calibration_gui.py
    from calibration_class import Calibration
    from style_gui import Style

SOLOFF_FORMS = ["111", "221", "222", "332", "333", "443", "444", "554", "555"]
# méthode : (valeurs proposées pour le degré, degré par défaut, itérations par défaut)
METHOD_DEFAULTS = {
    "Lagrange": ([str(i) for i in range(1, 9)], "4", 10),
    "Soloff":   (SOLOFF_FORMS, "332", 8),
    "Zernike":  ([str(i) for i in range(2, 16)], "6", 9),
}
LABELS_PFORM = {"Lagrange": "Degré (Lpform)", "Soloff": "Forme (aab)", "Zernike": "Ordre (nZ)"}

# dossier où l'explorateur « … » commence, et où l'on cherche la dernière calibration
DOSSIER_PARCOURIR = "../../Expériences"
SOUS_DOSSIERS_CAMERAS = ("video_extenso_left", "video_extenso_right")


def _calib_recente(racine=DOSSIER_PARCOURIR):
    """Dossier contenant le hauteurs_calibration*.txt le plus récent (jusqu'à 4 niveaux sous racine)."""
    r = Path(racine).expanduser()
    fichiers = []
    for profondeur in range(1, 5):
        fichiers += r.glob("*/" * profondeur + "hauteurs_calibration*.txt")
    if not fichiers:
        return ""
    return str(max(fichiers, key=lambda f: f.stat().st_mtime).parent)


def _dossier_depart(prefere, secours="."):
    """prefere s'il existe ; sinon le premier dossier existant en remontant depuis secours."""
    for d in (secours, prefere):
        d = os.path.abspath(os.path.expanduser(d or "."))
        while not os.path.isdir(d) and os.path.dirname(d) != d:
            d = os.path.dirname(d)
        if os.path.isdir(d) and d != os.path.dirname(d):
            return d
    return os.path.abspath(".")


def _nb_images(dossier):
    """Nombre de photos dans chaque sous-dossier caméra (None si absent)."""
    res = []
    for sous in SOUS_DOSSIERS_CAMERAS:
        d = Path(dossier) / sous
        res.append(len([f for f in d.glob("[0-9]*") if f.is_file()]) if d.is_dir() else None)
    return res


def ask_parameters():
    """Ouvre la fenêtre et renvoie un dict de paramètres, ou None si annulé."""
    root = tk.Tk()
    root.title("Calibration stéréo - Pycaso")
    root.resizable(False, False)
    Style.appliquer(root)
    pad = Style.PAD
    result = {}

    v = {
        "path_images": tk.StringVar(value=_calib_recente()),
        "method": tk.StringVar(value="Lagrange"),
        "pform": tk.StringVar(value="4"),
        "iterations": tk.IntVar(value=10),
        "z_init": tk.StringVar(value="120"),
        "z_final": tk.StringVar(value="10"),
        "z_step": tk.StringVar(value="2"),
        "move_metadata": tk.BooleanVar(value=False),
        "show_plot": tk.BooleanVar(value=True),
    }

    # --- Images ---
    f = ttk.LabelFrame(root, text="Images de calibration")
    f.grid(row=0, column=0, sticky="ew", **pad)
    ttk.Label(f, text="Dossier des images").grid(row=0, column=0, sticky="w", **pad)
    ttk.Entry(f, textvariable=v["path_images"], width=60).grid(row=0, column=1, sticky="w", **pad)
    ttk.Button(f, text="…", width=3, command=lambda: _browse(root, v["path_images"])).grid(
        row=0, column=2, **pad)
    lbl_images = ttk.Label(f, wraplength=640, justify="left")
    lbl_images.grid(row=1, column=0, columnspan=3, sticky="w", **pad)
    ttk.Label(f, text="Résultats dans").grid(row=2, column=0, sticky="w", **pad)
    out_label = ttk.Label(f, foreground=Style.GRIS, wraplength=560)
    out_label.grid(row=2, column=1, columnspan=2, sticky="w", **pad)

    # --- Méthode ---
    f = ttk.LabelFrame(root, text="Méthode")
    f.grid(row=1, column=0, sticky="ew", **pad)
    ttk.Label(f, text="Méthode").grid(row=0, column=0, sticky="w", **pad)
    cb_method = ttk.Combobox(f, textvariable=v["method"], state="readonly",
                             values=list(METHOD_DEFAULTS), width=12)
    cb_method.grid(row=0, column=1, sticky="w", **pad)
    lbl_pform = ttk.Label(f, text=LABELS_PFORM["Lagrange"])
    lbl_pform.grid(row=1, column=0, sticky="w", **pad)
    cb_pform = ttk.Combobox(f, textvariable=v["pform"], width=12, values=METHOD_DEFAULTS["Lagrange"][0])
    cb_pform.grid(row=1, column=1, sticky="w", **pad)
    ttk.Label(f, text="Itérations").grid(row=2, column=0, sticky="w", **pad)
    ttk.Spinbox(f, from_=1, to=12, textvariable=v["iterations"], width=6).grid(
        row=2, column=1, sticky="w", **pad)

    def on_method_change(*_):
        m = v["method"].get()
        values, default, it = METHOD_DEFAULTS[m]
        cb_pform.configure(values=values, state="readonly" if m == "Soloff" else "normal")
        v["pform"].set(default)
        v["iterations"].set(it)
        lbl_pform.configure(text=LABELS_PFORM[m])
    cb_method.bind("<<ComboboxSelected>>", on_method_change)

    # --- Plans z ---
    f = ttk.LabelFrame(root, text="Plans z (mm)")
    f.grid(row=2, column=0, sticky="ew", **pad)
    f.columnconfigure(1, weight=1)
    lz = ttk.Frame(f)
    lz.grid(row=0, column=0, sticky="w", **pad)
    for i, (txt, key) in enumerate([("z initial", "z_init"), ("z final", "z_final"), ("pas", "z_step")]):
        ttk.Label(lz, text=txt).grid(row=0, column=2 * i, sticky="w", padx=(0 if i == 0 else 16, 4))
        ttk.Entry(lz, textvariable=v[key], width=8).grid(row=0, column=2 * i + 1, sticky="w")
    z_preview = ttk.Label(f, wraplength=640, justify="left")
    z_preview.grid(row=1, column=0, columnspan=2, sticky="w", **pad)
    lbl_fichier = ttk.Label(f, foreground=Style.GRIS, wraplength=640, justify="left")
    lbl_fichier.grid(row=2, column=0, columnspan=2, sticky="w", **pad)

    etat = {"lu": None, "dossier_lu": None}      # dernières hauteurs lues dans le fichier

    def nombre(key):
        return float(v[key].get().strip().replace(",", "."))

    def build_z():
        return Calibration.liste_z(nombre("z_init"), nombre("z_final"), nombre("z_step"))

    def update_preview(*_):
        """Aperçu des plans, comparé au nombre de photos et au tableau du fichier."""
        try:
            z = build_z()
        except ValueError as err:
            msg = "valeurs invalides" if "convert" in str(err) else str(err)
            z_preview.configure(text=f"✘ {msg}", foreground=Style.ROUGE)
            return
        texte, couleur = f"{z[0]} → {z[-1]} mm, pas {nombre('z_step'):g} : {len(z)} plans", Style.VERT
        remarques = []
        nb = [n for n in _nb_images(v["path_images"].get().strip()) if n is not None]
        if nb and any(n != len(z) for n in nb):
            remarques.append(f"⚠ {' / '.join(map(str, nb))} photos (gauche / droite) pour {len(z)} plans")
        lu = etat["lu"]
        if lu and lu["z_table"] and (len(lu["z_table"]) != len(z)
                                     or max(abs(a - b) for a, b in zip(lu["z_table"], z)) > 1e-6):
            remarques.append("⚠ différent du tableau de hauteurs_calibration.txt")
        if remarques:
            texte, couleur = texte + "\n" + "\n".join(remarques), Style.ORANGE
        z_preview.configure(text=texte, foreground=couleur)

    def lire_fichier(force=False):
        """Recopie dans les champs les hauteurs de hauteurs_calibration.txt (si le dossier a changé)."""
        dossier = v["path_images"].get().strip()
        if not force and dossier == etat["dossier_lu"]:
            return
        etat["dossier_lu"] = dossier
        lu = Calibration.lire_hauteurs(dossier) if dossier else None
        etat["lu"] = lu
        if lu is None:
            lbl_fichier.configure(text=f"{Calibration.FICHIER_HAUTEURS} absent : saisir les hauteurs à la main",
                                  foreground=Style.ORANGE)
            return
        z_init, z_final, pas = lu["z_init"], lu["z_final"], lu["pas"]
        if lu["z_table"]:                                  # le tableau des plans fait foi s'il existe
            zt = lu["z_table"]
            z_init, z_final = zt[0], zt[-1]
            if pas is None and len(zt) > 1:
                pas = abs(zt[1] - zt[0])
        for key, val in (("z_init", z_init), ("z_final", z_final), ("z_step", pas)):
            if val is not None:
                v[key].set(f"{val:g}")
        texte = f"✔ hauteurs lues dans {lu['fichier']}"
        if lu["date"]:
            texte += f" (calibration du {lu['date']})"
        couleur = Style.VERT
        if lu["mire"] and lu["mire"] != (Calibration.NCX, Calibration.NCY, Calibration.SQR):
            texte += (f"\n⚠ mire du fichier : {lu['mire'][0]} × {lu['mire'][1]} carrés de {lu['mire'][2]:g} mm ; "
                      f"calibration_class.py utilise {Calibration.NCX} × {Calibration.NCY} × {Calibration.SQR:g} mm")
            couleur = Style.ORANGE
        lbl_fichier.configure(text=texte, foreground=couleur)

    def update_path(*_):
        p = v["path_images"].get().strip()
        out_label.configure(text=str(Calibration.results_dir_for(p)) if p else "—")
        nb = _nb_images(p) if p else [None, None]
        if not p or not Path(p).is_dir():
            lbl_images.configure(text="✘ dossier introuvable", foreground=Style.ROUGE)
        elif None in nb:
            manque = [s for s, n in zip(SOUS_DOSSIERS_CAMERAS, nb) if n is None]
            lbl_images.configure(text=f"✘ sous-dossier(s) absent(s) : {', '.join(manque)}", foreground=Style.ROUGE)
        else:
            lbl_images.configure(text=f"✔ {nb[0]} photos à gauche, {nb[1]} à droite", foreground=Style.VERT)
        lire_fichier()
        update_preview()

    v["path_images"].trace_add("write", update_path)
    for key in ("z_init", "z_final", "z_step"):
        v[key].trace_add("write", update_preview)
    ttk.Button(f, text="Relire le fichier", command=lambda: (lire_fichier(force=True), update_preview())).grid(
        row=0, column=1, sticky="e", **pad)
    update_path()

    # --- Options ---
    f = ttk.LabelFrame(root, text="Options")
    f.grid(row=3, column=0, sticky="ew", **pad)
    ttk.Checkbutton(f, text="Déplacer les metadata.csv vers le dossier parent",
                    variable=v["move_metadata"]).grid(row=1, column=0, sticky="w", **pad)
    ttk.Checkbutton(f, text="Afficher le nuage 3D à la fin",
                    variable=v["show_plot"]).grid(row=2, column=0, sticky="w", **pad)

    # --- Boutons ---
    def on_ok():
        try:
            z_list = build_z()
            pform = int(v["pform"].get())
            iterations = int(v["iterations"].get())
        except (tk.TclError, ValueError) as err:
            messagebox.showerror("Erreur", f"Champ numérique invalide :\n{err}", parent=root)
            return
        path = v["path_images"].get().strip()
        # fichiers nécessaires : vérifiés ici, avant de fermer la fenêtre (pas après le lancement)
        erreurs, avertissements = Calibration(path or ".", z_list).verifier(v["method"].get(), pform)
        if not path:
            erreurs.insert(0, "Dossier des images : à renseigner")
        if erreurs:
            messagebox.showerror("Lancement impossible", "\n".join(erreurs), parent=root)
            return
        if avertissements and not messagebox.askyesno(
                "Vérifier avant de lancer", "\n".join(avertissements) + "\n\nContinuer quand même ?", parent=root):
            return
        lu = etat["lu"]
        result.update(path_images=path, method=v["method"].get(), pform=pform, iterations=iterations,
                      z_list=z_list, move_metadata=v["move_metadata"].get(), show_plot=v["show_plot"].get(),
                      date=lu["date"] if lu else None)
        root.destroy()

    # rappel de la mire utilisée (fixée dans calibration_class.py, non modifiable ici)
    ttk.Label(root, foreground=Style.GRIS,
              text=f"Mire ChArUco : {Calibration.NCX} × {Calibration.NCY} carrés "
                   f"de {Calibration.SQR} mm").grid(row=4, column=0, sticky="w", **pad)

    fb = ttk.Frame(root)
    fb.grid(row=5, column=0, sticky="e", **pad)
    ttk.Button(fb, text="Annuler", command=root.destroy).grid(row=0, column=0, **pad)
    ttk.Button(fb, text="Lancer la calibration", command=on_ok).grid(row=0, column=1, **pad)
    root.bind("<Return>", lambda _e: on_ok())
    root.bind("<Escape>", lambda _e: root.destroy())

    root.mainloop()
    return result or None


def _browse(parent, var):
    """Explorateur commençant dans le dossier saisi, sinon dans DOSSIER_PARCOURIR."""
    d = filedialog.askdirectory(initialdir=_dossier_depart(DOSSIER_PARCOURIR, var.get().strip()),
                                parent=parent, title="Dossier des images de calibration")
    if d:
        rel = os.path.relpath(d)
        var.set(d if rel.startswith("..") else rel)


def run_calibration_gui():
    """Demande les paramètres via la fenêtre puis lance la calibration.

    Renvoie (résultat de la calibration, paramètres) ou None si annulé.
    """
    params = ask_parameters()
    if params is None:
        print("Calibration annulée")
        return None

    print("Paramètres :", {k: val for k, val in params.items() if k != "z_list"})
    print("z_list :", params["z_list"])

    calib = Calibration.from_params(params)
    if params["move_metadata"]:
        calib.move_metadata()
    res = calib.run(params["method"], params["pform"], params["iterations"])
    return res, params


if __name__ == "__main__":
    run_calibration_gui()