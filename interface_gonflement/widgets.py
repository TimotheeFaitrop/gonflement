"""Briques communes de l'interface : sous-processus, colonne défilante,
info-bulle et formulaire lié aux réglages (reglages.DEFAUTS)."""

import os
import queue
import signal
import subprocess
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from . import reglages as rg
except ImportError:
    import reglages as rg

ICI = Path(__file__).resolve().parent


class Processus:
    """Sous-processus dont la sortie est relue ligne à ligne par la boucle Tk."""

    def __init__(self, nom, cmd, sur_ligne, sur_fin):
        self.nom, self.sur_ligne, self.sur_fin = nom, sur_ligne, sur_fin
        self.q = queue.Queue()
        self.t_mort, self.fini = None, False
        self.p = subprocess.Popen(
            cmd, cwd=str(ICI.parent), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, text=True, bufsize=1, start_new_session=True,
            env={**os.environ, "PYTHONUNBUFFERED": "1"})
        threading.Thread(target=self._lire, daemon=True).start()

    def _lire(self):
        for ligne in self.p.stdout:
            self.q.put(ligne.rstrip("\n"))
        self.p.wait()
        self.q.put(None)

    def vider(self):
        """Transmet les lignes reçues ; renvoie False quand le processus est fini.

        La fin est détectée sur le processus principal, pas seulement sur la
        fermeture de sa sortie : des sous-processus de crappy (caméras, fenêtres
        VideoExtenso, Grapher) peuvent garder la sortie ouverte après la fin de
        l'essai. Ils sont alors arrêtés pour libérer caméras et ports série."""
        try:
            while True:
                ligne = self.q.get_nowait()
                if ligne is None:
                    return self._terminer()
                self.sur_ligne(ligne)
        except queue.Empty:
            pass
        if self.p.poll() is None:
            return True
        if self.t_mort is None:
            self.t_mort = time.monotonic()      # laisse arriver les dernières lignes
        elif time.monotonic() - self.t_mort > 1.5:
            self.signal(signal.SIGTERM)          # restes du groupe de processus
            threading.Timer(3, self.signal, (signal.SIGKILL,)).start()
            return self._terminer()
        return True

    def _terminer(self):
        if not self.fini:
            self.fini = True
            self.sur_fin(self.p.returncode)
        return False

    def vivant(self):
        return self.p.poll() is None

    def signal(self, sig):
        try:
            os.killpg(self.p.pid, sig)
        except (ProcessLookupError, PermissionError):
            pass


class CadreDefilant(ttk.Frame):
    """Colonne avec barre de défilement ; les widgets vont dans `.interieur`."""

    def __init__(self, parent, largeur=400, fond="#2e3440"):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, width=largeur, highlightthickness=0, bg=fond)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.interieur = ttk.Frame(self.canvas)
        self.interieur.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.interieur, anchor="nw")
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.bind("<Enter>", lambda e: self._molette(True))
        self.bind("<Leave>", lambda e: self._molette(False))

    def _molette(self, actif):
        evts = {"<MouseWheel>": lambda e: -1 if e.delta > 0 else 1,
                "<Button-4>": lambda e: -1, "<Button-5>": lambda e: 1}
        for sequence, sens in evts.items():
            if actif:
                self.canvas.bind_all(sequence, lambda e, s=sens: self.canvas.yview_scroll(
                    s(e), "units"))
            else:
                self.canvas.unbind_all(sequence)


class Bulle:
    """Info-bulle au survol."""
    couleurs = ("#ebcb8b", "#2e3440")

    def __init__(self, widget, texte):
        self.w, self.texte, self.tip = widget, texte, None
        widget.bind("<Enter>", self._montrer, add="+")
        widget.bind("<Leave>", self._cacher, add="+")

    def _montrer(self, _):
        self.tip = tk.Toplevel(self.w)
        self.tip.wm_overrideredirect(True)
        self.tip.geometry(f"+{self.w.winfo_rootx() + 20}+"
                          f"{self.w.winfo_rooty() + self.w.winfo_height() + 4}")
        tk.Label(self.tip, text=self.texte, bg=self.couleurs[0], fg=self.couleurs[1],
                 wraplength=320, justify="left", padx=6, pady=3).pack()

    def _cacher(self, _):
        if self.tip:
            self.tip.destroy()
            self.tip = None


class Formulaire:
    """Mixin : une variable Tk par réglage, champs de saisie et relecture typée.

    Les clés sont les chemins de reglages.DEFAUTS, ex. "essai.debit.consigne".
    Les nombres sont saisis en texte (la virgule décimale est acceptée).
    """

    def creer_vars(self, d, chemin=()):
        for k, v in d.items():
            c = chemin + (k,)
            if isinstance(v, dict):
                self.creer_vars(v, c)
            elif isinstance(v, bool):
                self.vars[".".join(c)] = tk.BooleanVar(value=v)
            else:
                self.vars[".".join(c)] = tk.StringVar(value=str(v))

    def v(self, cle):
        return self.vars[cle]

    def collecter(self):
        """Relit tous les champs. Lève ValueError avec le nom du champ fautif."""
        def remplir(d, chemin):
            out = {}
            for k, defaut in d.items():
                c = chemin + (k,)
                if isinstance(defaut, dict):
                    out[k] = remplir(defaut, c)
                    continue
                brut = self.vars[".".join(c)].get()
                if isinstance(defaut, bool):
                    out[k] = bool(brut)
                elif isinstance(defaut, (int, float)):
                    try:
                        x = float(str(brut).replace(",", ".").strip())
                    except ValueError:
                        raise ValueError(f"Valeur numérique invalide pour "
                                         f"« {'.'.join(c)} » : {brut!r}")
                    out[k] = int(x) if isinstance(defaut, int) and x.is_integer() else x
                else:
                    out[k] = str(brut).strip()
            return out
        return remplir(rg.DEFAUTS, ())

    def nombre(self, cle, defaut=None):
        try:
            return float(self.v(cle).get().replace(",", "."))
        except ValueError:
            return defaut

    def sauver_reglages(self, silencieux=True):
        try:
            self.reglages = self.collecter()
            rg.sauver(self.reglages)
            if not silencieux:
                self.log("Réglages enregistrés", "info")
            return True
        except ValueError as e:
            messagebox.showerror("Réglage invalide", str(e))
            return False

    def chemin(self, p):
        p = Path(p)
        return p if p.is_absolute() else (ICI.parent / p).resolve()

    # ---- champs (grille à 3 colonnes : libellé, saisie, unité)
    def champ(self, parent, ligne, texte, cle, unite="", largeur=10, aide=None):
        ttk.Label(parent, text=texte).grid(row=ligne, column=0, sticky="w", padx=8, pady=3)
        e = ttk.Entry(parent, textvariable=self.v(cle), width=largeur)
        e.grid(row=ligne, column=1, sticky="w", padx=4, pady=3)
        if unite:
            ttk.Label(parent, text=unite, style="Petit.TLabel").grid(
                row=ligne, column=2, sticky="w", padx=2)
        if aide:
            Bulle(e, aide)
        return e

    def choix(self, parent, ligne, texte, cle, valeurs, largeur=12, commande=None):
        ttk.Label(parent, text=texte).grid(row=ligne, column=0, sticky="w", padx=8, pady=3)
        c = ttk.Combobox(parent, textvariable=self.v(cle), values=valeurs,
                         width=largeur, state="readonly")
        c.grid(row=ligne, column=1, columnspan=2, sticky="w", padx=4, pady=3)
        if commande:
            c.bind("<<ComboboxSelected>>", lambda e: commande())
        return c

    def case(self, parent, ligne, texte, cle, commande=None):
        b = ttk.Checkbutton(parent, text=texte, variable=self.v(cle), command=commande)
        b.grid(row=ligne, column=0, columnspan=3, sticky="w", padx=8, pady=3)
        return b

    def note(self, parent, ligne, texte, largeur=360):
        lbl = ttk.Label(parent, text=texte, style="Petit.TLabel", wraplength=largeur)
        lbl.grid(row=ligne, column=0, columnspan=4, sticky="w", padx=8, pady=(0, 4))
        return lbl

    def chemin_choisi(self, parent, ligne, texte, cle, dossier=False, largeur=26,
                      types=(("Numpy", "*.npy"),)):
        """Champ de chemin avec bouton « … » (fichier ou dossier)."""
        ttk.Label(parent, text=texte).grid(row=ligne, column=0, sticky="w", padx=8, pady=3)
        f = ttk.Frame(parent)
        f.grid(row=ligne, column=1, columnspan=3, sticky="ew", padx=4, pady=3)
        ttk.Entry(f, textvariable=self.v(cle), width=largeur).pack(
            side="left", fill="x", expand=True)

        def parcourir():
            init = self._dossier_initial(cle)
            p = (filedialog.askdirectory(initialdir=init) if dossier else
                 filedialog.askopenfilename(initialdir=init,
                                            filetypes=list(types) + [("Tous", "*")]))
            if p:
                self.v(cle).set(p)
        ttk.Button(f, text="…", width=3, command=parcourir).pack(side="left", padx=3)

    def _dossier_initial(self, cle):
        p = self.chemin(self.v(cle).get() or self.v("materiel.dossier_racine").get())
        while not p.is_dir() and p != p.parent:
            p = p.parent
        return str(p) if p.is_dir() else str(ICI.parent)

    def cadre(self, parent, titre, **pack):
        f = ttk.LabelFrame(parent, text=titre, padding=(4, 4))
        f.pack(fill="x", padx=8, pady=5, **pack)
        return f
