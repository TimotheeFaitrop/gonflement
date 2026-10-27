"""Courbes en direct : pression, débit, déformation (matplotlib dans Tk)."""

import collections
import math
import tkinter as tk
from tkinter import ttk

try:
    from . import theme
except ImportError:
    import theme

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
except Exception:  # matplotlib absent : pas de courbes
    Figure = None

SERIES = ("press", "volumetric_flow", "debit_cmd", "cible", "eps")


class Courbes(ttk.Frame):

    def __init__(self, parent, P):
        super().__init__(parent)
        self.P = P
        self.donnees = collections.defaultdict(lambda: collections.deque(maxlen=50000))
        self.mode, self.pmax = "debit", None
        if Figure is None:
            ttk.Label(self, text="matplotlib introuvable : pas de courbes en direct").pack(pady=40)
            return
        self.fig = Figure(figsize=(8, 6), dpi=100)
        self.axes = self.fig.subplots(3, 1, sharex=True)
        self.fig.subplots_adjust(left=0.09, right=0.98, top=0.97, bottom=0.08, hspace=0.12)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        barre = ttk.Frame(self)
        barre.pack(fill="x", pady=(4, 0))
        ttk.Label(barre, text="Fenêtre affichée").pack(side="left", padx=4)
        self.fenetre = tk.StringVar(value="Tout")
        ttk.Combobox(barre, textvariable=self.fenetre, state="readonly", width=8,
                     values=["Tout", "60 s", "300 s", "900 s"]).pack(side="left")
        ttk.Button(barre, text="Effacer les courbes", command=self.effacer).pack(side="right")
        self.preparer()
        self.after(500, self._rafraichir)

    def preparer(self, mode=None, pmax=None, P=None):
        """(Re)crée les axes pour un mode de pilotage ; garde les données."""
        if Figure is None:
            return
        self.mode = mode or self.mode
        self.pmax = pmax if pmax is not None else self.pmax
        self.P = P or self.P
        C = theme.couleurs_courbes(self.P)
        a1, a2, a3 = self.axes
        for a in self.axes:
            a.clear()
        a1.set_ylabel("Pression")
        a2.set_ylabel("Débit (mL/min)")
        a3.set_ylabel("Déformation (%)")
        a3.set_xlabel("Temps (s)")
        self.lignes = {
            "press": a1.plot([], [], color=C["pression"], lw=1.8, label="mesure")[0],
            "volumetric_flow": a2.plot([], [], color=C["debit"], lw=1.8, label="mesuré")[0],
            "debit_cmd": a2.plot([], [], color=C["cmd"], lw=1.2, ls="--", label="commandé")[0],
            "eps": a3.plot([], [], color=C["eps"], lw=1.8, label="mesure")[0]}
        if self.mode != "debit":
            ax = a1 if self.mode == "pression" else a3
            self.lignes["cible"] = ax.plot([], [], color=C["cible"], ls=":", lw=1.6,
                                           label="cible")[0]
        self.ligne_pmax = None
        if self.pmax is not None:
            self.ligne_pmax = a1.axhline(self.pmax, color=C["limite"], lw=1, ls="--",
                                         label="P max")
        theme.styler_figure(self.fig, self.axes, self.P)
        for a in self.axes:
            leg = a.legend(loc="upper left", fontsize=8, frameon=False)
            for t in leg.get_texts():
                t.set_color(self.P["doux"])
        self._tracer()

    def ajouter(self, paquet):
        if "t" not in paquet:
            return
        self.donnees["t"].append(paquet["t"])
        for k in SERIES:
            self.donnees[k].append(paquet.get(k, math.nan))

    def effacer(self):
        self.donnees.clear()
        self.preparer()

    def _rafraichir(self):
        try:
            self._tracer()
        finally:
            self.after(500, self._rafraichir)

    def _tracer(self):
        t = list(self.donnees["t"])
        if t:
            i0 = 0
            if self.fenetre.get() != "Tout":
                tmin = t[-1] - float(self.fenetre.get().split()[0])
                while i0 < len(t) and t[i0] < tmin:
                    i0 += 1
            for k, ligne in self.lignes.items():
                ligne.set_data(t[i0:], list(self.donnees[k])[i0:])
            self._echelle_pression([p for p in list(self.donnees["press"])[i0:]
                                    if not math.isnan(p)])
            for a in self.axes:
                a.relim(visible_only=True)
                a.autoscale_view()
        self.canvas.draw_idle()

    def _echelle_pression(self, p):
        """Ligne P max visible seulement quand la pression s'en approche, sinon
        elle écraserait l'échelle."""
        if self.ligne_pmax is None or not p:
            return
        bas = min(p)
        self.ligne_pmax.set_visible(max(p) >= bas + 0.6 * (self.pmax - bas))
