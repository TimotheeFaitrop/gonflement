"""Interface tkinter de la calibration stéréo.

Usage depuis un script :
    from Pycaso.calibration_gui import run_calibration_gui
    run_calibration_gui()
"""

import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

import numpy as np

try:  # import depuis un script extérieur : from Pycaso.calibration_gui import ...
    from .calibration_class import Calibration
except ImportError:  # exécution directe : python calibration_gui.py
    from calibration_class import Calibration

SOLOFF_FORMS = ["111", "221", "222", "332", "333", "443", "444", "554", "555"]
# méthode : (valeurs proposées pour le degré, degré par défaut, itérations par défaut)
METHOD_DEFAULTS = {
    "Lagrange": ([str(i) for i in range(1, 9)], "4", 10),
    "Soloff":   (SOLOFF_FORMS, "332", 8),
    "Zernike":  ([str(i) for i in range(2, 16)], "6", 9),
}


def _default_path(date):
    return f"../../Expériences/{date}/calib"


def ask_parameters():
    """Ouvre la fenêtre et renvoie un dict de paramètres, ou None si annulé."""
    root = tk.Tk()
    root.title("Calibration stéréo - Pycaso")
    root.resizable(False, False)
    _setup_style(root)
    result = {}

    today = time.strftime("%Y_%m_%d")
    v = {
        "date": tk.StringVar(value=today),
        "path_images": tk.StringVar(value=_default_path(today)),
        "method": tk.StringVar(value="Lagrange"),
        "pform": tk.StringVar(value="4"),
        "iterations": tk.IntVar(value=10),
        "z_start": tk.DoubleVar(value=70),
        "z_step": tk.DoubleVar(value=2),
        "n_planes": tk.IntVar(value=20),
        "move_metadata": tk.BooleanVar(value=False),
        "show_plot": tk.BooleanVar(value=True),
    }
    pad = {"padx": 6, "pady": 3}

    # --- Essai ---
    f = ttk.LabelFrame(root, text="Essai")
    f.grid(row=0, column=0, sticky="ew", **pad)
    ttk.Label(f, text="Date (AAAA_MM_JJ)").grid(row=0, column=0, sticky="w", **pad)
    ttk.Entry(f, textvariable=v["date"], width=14).grid(row=0, column=1, sticky="w", **pad)

    ttk.Label(f, text="Dossier images calib").grid(row=1, column=0, sticky="w", **pad)
    ttk.Entry(f, textvariable=v["path_images"], width=42).grid(row=1, column=1, **pad)
    ttk.Button(f, text="…", width=3,
               command=lambda: _browse(v["path_images"])).grid(row=1, column=2, **pad)

    ttk.Label(f, text="Résultats dans").grid(row=2, column=0, sticky="w", **pad)
    out_label = ttk.Label(f, foreground="gray", wraplength=330)
    out_label.grid(row=2, column=1, columnspan=2, sticky="w", **pad)

    def update_out(*_):
        p = v["path_images"].get().strip()
        out_label.configure(
            text=str(Path(p).parent / Calibration.RESULTS_FOLDER) if p else "—")
    v["path_images"].trace_add("write", update_out)
    update_out()

    # le chemin images suit la date tant que l'utilisateur ne l'a pas modifié
    last_auto = {"path": v["path_images"].get()}

    def on_date_change(*_):
        if v["path_images"].get() == last_auto["path"]:
            new = _default_path(v["date"].get())
            v["path_images"].set(new)
            last_auto["path"] = new
    v["date"].trace_add("write", on_date_change)

    # --- Méthode ---
    f = ttk.LabelFrame(root, text="Méthode")
    f.grid(row=1, column=0, sticky="ew", **pad)
    ttk.Label(f, text="Méthode").grid(row=0, column=0, sticky="w", **pad)
    cb_method = ttk.Combobox(f, textvariable=v["method"], state="readonly",
                             values=list(METHOD_DEFAULTS), width=12)
    cb_method.grid(row=0, column=1, sticky="w", **pad)

    lbl_pform = ttk.Label(f, text="Degré (Lpform)")
    lbl_pform.grid(row=1, column=0, sticky="w", **pad)
    cb_pform = ttk.Combobox(f, textvariable=v["pform"], width=12,
                            values=METHOD_DEFAULTS["Lagrange"][0])
    cb_pform.grid(row=1, column=1, sticky="w", **pad)

    ttk.Label(f, text="Itérations").grid(row=2, column=0, sticky="w", **pad)
    ttk.Spinbox(f, from_=1, to=12, textvariable=v["iterations"],
                width=6).grid(row=2, column=1, sticky="w", **pad)

    labels = {"Lagrange": "Degré (Lpform)", "Soloff": "Forme (aab)",
              "Zernike": "Ordre (nZ)"}

    def on_method_change(*_):
        m = v["method"].get()
        values, default, it = METHOD_DEFAULTS[m]
        cb_pform.configure(values=values,
                           state="readonly" if m == "Soloff" else "normal")
        v["pform"].set(default)
        v["iterations"].set(it)
        lbl_pform.configure(text=labels[m])
    cb_method.bind("<<ComboboxSelected>>", on_method_change)

    # --- Plans z ---
    f = ttk.LabelFrame(root, text="Plans z (mm)")
    f.grid(row=2, column=0, sticky="ew", **pad)
    for i, (txt, key) in enumerate([("z départ", "z_start"), ("pas", "z_step"),
                                    ("nb plans", "n_planes")]):
        ttk.Label(f, text=txt).grid(row=0, column=2 * i, sticky="w", **pad)
        ttk.Entry(f, textvariable=v[key], width=7).grid(row=0, column=2 * i + 1, **pad)
    z_preview = ttk.Label(f, foreground="gray", wraplength=420)
    z_preview.grid(row=1, column=0, columnspan=6, sticky="w", **pad)

    def build_z():
        z = v["z_start"].get() - v["z_step"].get() * np.arange(v["n_planes"].get())
        return z.astype(int) if np.allclose(z, np.round(z)) else z

    def update_preview(*_):
        try:
            z = build_z()
            z_preview.configure(text=f"{z[0]} → {z[-1]}  ({len(z)} plans)")
        except (tk.TclError, IndexError):
            z_preview.configure(text="valeurs invalides")
    for key in ("z_start", "z_step", "n_planes"):
        v[key].trace_add("write", update_preview)
    update_preview()

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
            time.strptime(v["date"].get(), "%Y_%m_%d")
        except ValueError:
            messagebox.showerror("Erreur", "Date attendue au format AAAA_MM_JJ")
            return
        try:
            params = {k: var.get() for k, var in v.items()}
            params["z_list"] = build_z()
            params["pform"] = int(params["pform"])
        except (tk.TclError, ValueError):
            messagebox.showerror("Erreur", "Un des champs numériques est invalide")
            return
        if not Path(params["path_images"]).is_dir():
            if not messagebox.askyesno(
                    "Dossier introuvable",
                    f"{params['path_images']} n'existe pas.\nContinuer quand même ?"):
                return
        for k in ("z_start", "z_step", "n_planes"):
            params.pop(k)
        result.update(params)
        root.destroy()

    # rappel de la mire utilisée (fixée dans calibration_class.py, non modifiable ici)
    ttk.Label(root, foreground="gray",
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


def _setup_style(root):
    """Thème 'clam' + cases à cocher bien lisibles : vert avec coche si cochée,
    blanc vide sinon."""
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TCheckbutton", indicatorsize=16, indicatormargin=(2, 2, 8, 2),
                    indicatorbackground="white", indicatorforeground="white",
                    upperbordercolor="#555555", lowerbordercolor="#555555")
    style.map("TCheckbutton",
              indicatorbackground=[("disabled", "#dddddd"),
                                   ("pressed", "#a5d6a7"),
                                   ("selected", "#2e7d32")],
              indicatorforeground=[("selected", "white")],
              foreground=[("selected", "black"), ("!selected", "#666666")])


def _browse(var):
    d = filedialog.askdirectory(initialdir=var.get() or ".")
    if d:
        var.set(d)


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