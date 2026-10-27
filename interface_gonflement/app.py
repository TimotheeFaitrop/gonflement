"""Interface Tkinter des essais de gonflement.

Lancement depuis la racine du dépôt :   python lancer_interface.py

Fenêtre principale : bandeau (simulation / matériel réel), trois onglets et la
console du bas. Chaque action matérielle tourne dans un sous-processus (crappy a
besoin de son propre processus principal) ; l'essai renvoie ses mesures en UDP
(FluxInterface) et reçoit les commandes de l'interface en UDP.

  onglet_essai.py        pilotage débit / pression / déformation, courbes
  onglet_calibration.py  plateau, acquisition de la mire, calcul Pycaso
  onglet_materiel.py     ports, caméras, thème, outils
  widgets.py, theme.py, courbes.py : briques communes
"""

import json
import signal
import socket
import subprocess
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk

try:
    from . import reglages as rg, theme
    from .onglet_calibration import OngletCalibration
    from .onglet_essai import OngletEssai
    from .onglet_materiel import OngletMateriel
    from .widgets import Bulle, Formulaire, Processus
except ImportError:
    import reglages as rg
    import theme
    from onglet_calibration import OngletCalibration
    from onglet_essai import OngletEssai
    from onglet_materiel import OngletMateriel
    from widgets import Bulle, Formulaire, Processus


class Application(Formulaire, tk.Tk):
    ICI = Path(__file__).resolve().parent

    def __init__(self):
        super().__init__()
        self.title("Gonflement — pilotage des essais")
        self.geometry("1450x920")
        self.minsize(1100, 700)
        self.reglages = rg.charger()
        self.vars = {}
        self.creer_vars(self.reglages)
        self.P = theme.appliquer(self, self.reglages["materiel"]["theme"])
        Bulle.couleurs = (self.P["jaune"], self.P["fond"])
        self.proc = None
        self.sock_donnees = None
        self.sock_cmd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.bandeau = tk.Label(self, anchor="w", padx=12, pady=5,
                                font=("TkDefaultFont", 10, "bold"))
        self.bandeau.pack(fill="x")
        panneau = ttk.PanedWindow(self, orient="vertical")
        panneau.pack(fill="both", expand=True)
        self.onglets = ttk.Notebook(panneau)
        panneau.add(self.onglets, weight=5)
        panneau.add(self._console(panneau), weight=1)
        self.onglets.add(OngletCalibration(self.onglets, self), text="Calibration")
        self.essai = OngletEssai(self.onglets, self)
        self.onglets.add(self.essai, text="Essai")
        self.materiel = OngletMateriel(self.onglets, self)
        self.onglets.add(self.materiel, text="Matériel")
        self.maj_bandeau()
        self.protocol("WM_DELETE_WINDOW", self.quitter)
        self.after(100, self._boucle)

    # ------------------------------------------------------------------ console
    def _console(self, parent):
        bas = ttk.Frame(parent)
        barre = ttk.Frame(bas)
        barre.pack(fill="x", pady=(4, 2))
        ttk.Label(barre, text="Console", style="Titre.TLabel").pack(side="left", padx=8)
        self.lbl_proc = ttk.Label(barre, text="Aucune tâche en cours", style="Petit.TLabel")
        self.lbl_proc.pack(side="left", padx=12)
        ttk.Button(barre, text="Effacer", command=lambda: self.console.delete("1.0", "end")
                   ).pack(side="right", padx=4)
        self.btn_interrompre = ttk.Button(barre, text="Interrompre la tâche",
                                          command=self.arreter, state="disabled")
        self.btn_interrompre.pack(side="right", padx=4)
        self.console = scrolledtext.ScrolledText(bas, height=9, font=("TkFixedFont", 9),
                                                 relief="flat", borderwidth=0, padx=8, pady=4)
        self.console.pack(fill="both", expand=True)
        self._couleurs_console()
        return bas

    def _couleurs_console(self):
        P = self.P
        self.console.configure(background=P["console"], foreground="#d8dee9",
                               insertbackground="#d8dee9", selectbackground=P["bord"])
        for tag, coul in (("alerte", "jaune"), ("erreur", "rouge"), ("info", "vert")):
            self.console.tag_configure(tag, foreground=P[coul])

    def log(self, txt, tag=None):
        if tag is None:
            low = txt.lower()
            if "error" in low or "erreur" in low or "traceback" in low:
                tag = "erreur"
            elif "warning" in low or "attention" in low or "sécurité" in low:
                tag = "alerte"
        self.console.insert("end", txt + "\n", tag)
        n = int(self.console.index("end-1c").split(".")[0])
        if n > 5000:
            self.console.delete("1.0", f"{n - 4000}.0")
        self.console.see("end")

    # ------------------------------------------------------------------ apparence
    def maj_bandeau(self):
        simu = self.v("materiel.simulation").get()
        self.bandeau.configure(
            text="MODE SIMULATION — aucun matériel n'est piloté" if simu
            else "Matériel réel : débitmètre, caméras, FT232R",
            bg=self.P["jaune" if simu else "vert"], fg=self.P["fond"] if simu else "#1f2a1a")

    def changer_theme(self):
        self.P = theme.appliquer(self, self.v("materiel.theme").get())
        Bulle.couleurs = (self.P["jaune"], self.P["fond"])
        self._couleurs_console()
        self.maj_bandeau()
        figure = getattr(self.essai.courbes, "canvas", None)
        figure = figure.get_tk_widget() if figure else None
        pile = [self]
        while pile:
            w = pile.pop()
            if isinstance(w, tk.Canvas) and w is not figure:
                w.configure(bg=self.P["fond"])
            pile.extend(w.winfo_children())
        self.essai.courbes.preparer(P=self.P)
        self.sauver_reglages()

    # ------------------------------------------------------------------ processus
    def python(self):
        """Même Python que celui qui a lancé l'interface."""
        return sys.executable

    def occupe(self):
        if self.proc is not None and self.proc.vivant():
            messagebox.showwarning("Occupé", f"« {self.proc.nom} » est en cours.\n"
                                             "Attendre la fin ou l'interrompre.")
            return True
        return False

    def lancer(self, nom, cmd, sur_fin=None, sur_ligne=None):
        if self.occupe():
            return False
        self.log(f"===== {nom} =====", "info")

        def ligne(l):
            if sur_ligne:
                sur_ligne(l)
            self.log(l)

        def fin(code):
            self.log(f"===== {nom} terminé (code {code}) =====", "info" if code == 0 else "erreur")
            self.lbl_proc.configure(text="Aucune tâche en cours")
            self.btn_interrompre.configure(state="disabled")
            if sur_fin:
                sur_fin(code)
        try:
            self.proc = Processus(nom, cmd, ligne, fin)
        except OSError as e:
            messagebox.showerror("Lancement impossible", str(e))
            return False
        self.lbl_proc.configure(text=f"En cours : {nom}")
        self.btn_interrompre.configure(state="normal")
        return True

    def outil(self, nom, action, *args):
        """Action de outils_machine.py (origine, aller_z, apercu, ports...)."""
        if not self.sauver_reglages():
            return
        if self.reglages["materiel"]["simulation"] and action != "ports":
            return self.log(f"[simulation] {nom} : rien n'est envoyé au matériel", "alerte")
        self.lancer(nom, [self.python(), "-u", str(self.ICI / "outils_machine.py"), action]
                    + [str(x) for x in args])

    def verifier_memoire_usb(self):
        """Comme les scripts d'origine (echo 0 | sudo tee …usbfs_memory_mb) : sans ça les
        caméras Ximea 2048 x 2048 ne renvoient pas d'images. Demande le mot de passe si besoin."""
        if self.v("materiel.simulation").get():
            return True
        f = Path("/sys/module/usbcore/parameters/usbfs_memory_mb")
        try:
            if f.read_text().strip() == "0":
                return True
        except OSError:
            return True        # paramètre absent : rien à libérer
        if self.materiel.memoire_usb("La mémoire USB des caméras doit être libérée "
                                     "(usbfs_memory_mb = 0).\n"):
            return True
        return messagebox.askyesno("Mémoire USB", "Mémoire USB non libérée : les caméras "
                                   "risquent de ne renvoyer aucune image.\nContinuer quand même ?")

    def ecrire_config(self, nom):
        """Écrit les réglages (chemins absolus) pour un lanceur ; renvoie le fichier."""
        if not self.sauver_reglages():
            return None
        cfg = json.loads(json.dumps(self.reglages))
        cfg["materiel"]["dossier_racine"] = str(self.chemin(cfg["materiel"]["dossier_racine"]))
        if cfg["calibration"]["dossier_images"]:
            cfg["calibration"]["dossier_images"] = str(self.chemin(cfg["calibration"]["dossier_images"]))
        if cfg["essai"]["dossier"]:
            cfg["essai"]["dossier"] = str(self.chemin(cfg["essai"]["dossier"]))
        f = self.ICI / nom
        with open(f, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2, ensure_ascii=False)
        return f

    def _boucle(self):
        if self.proc is not None and not self.proc.vider():
            self.proc = None
        self._recevoir_mesures()
        self.after(100, self._boucle)

    # ------------------------------------------------------------------ UDP
    def ecouter_mesures(self, port):
        if self.sock_donnees is not None:
            self.sock_donnees.close()
        try:
            self.sock_donnees = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock_donnees.bind(("127.0.0.1", int(port)))
            self.sock_donnees.setblocking(False)
            return True
        except OSError as e:
            messagebox.showerror("Port UDP occupé", f"Port {port} indisponible : {e}\n"
                                                    "Le changer dans l'onglet Matériel.")
            return False

    def _recevoir_mesures(self):
        dernier = None
        for _ in range(2000):
            try:
                dernier = json.loads(self.sock_donnees.recv(65536).decode())
            except (AttributeError, BlockingIOError, OSError, ValueError):
                break
            self.essai.courbes.ajouter(dernier)
        if dernier is not None:
            self.essai.afficher(dernier)

    def commande(self, msg):
        try:
            port = int(float(self.v("materiel.port_udp_commandes").get()))
            self.sock_cmd.sendto(json.dumps(msg).encode(), ("127.0.0.1", port))
        except (OSError, ValueError) as e:
            self.log(f"Commande non envoyée : {e}", "erreur")

    # ------------------------------------------------------------------ arrêts
    def arreter(self):
        """Arrêt propre (débit à 0, fermeture des appareils), puis Ctrl+C, puis kill."""
        p = self.proc
        if p is None or not p.vivant():
            return
        if self.essai.en_cours:
            self.log("Arrêt de l'essai demandé…", "alerte")
            self.commande({"action": "stop"})
            self.after(6000, lambda: p.vivant() and p.signal(signal.SIGINT))
            self.after(14000, lambda: self._tuer(p))
        else:
            self.log(f"Interruption de « {p.nom} »", "alerte")
            p.signal(signal.SIGINT)
            self.after(5000, lambda: self._tuer(p))

    def arret_urgence(self):
        self.log("!!! ARRÊT D'URGENCE !!!", "erreur")
        self.commande({"action": "urgence"})
        p = self.proc
        if p is not None and p.vivant():
            p.signal(signal.SIGINT)
            self.after(2500, lambda: self._tuer(p, debit_zero=True))
        else:
            self.materiel.debit_zero()

    def _tuer(self, p, debit_zero=False):
        if p.vivant():
            self.log(f"« {p.nom} » ne répond pas : arrêt forcé", "erreur")
            p.signal(signal.SIGKILL)
            debit_zero = True
        if debit_zero and p.nom.startswith("Essai"):
            # le port série est libéré après le kill : on remet la consigne à 0
            self.after(800, lambda: self.materiel.debit_zero(attendre=True))

    def ouvrir(self, p):
        if not Path(p).exists():
            return messagebox.showinfo("Dossier", f"{p} n'existe pas (encore)")
        try:
            subprocess.Popen(["xdg-open", str(p)])
        except OSError:
            messagebox.showinfo("Dossier", str(p))

    def quitter(self):
        p = self.proc
        if p is not None and p.vivant():
            if not messagebox.askyesno("Quitter", f"« {p.nom} » est en cours.\nL'arrêter et quitter ?"):
                return
            self.commande({"action": "stop"})
            p.signal(signal.SIGINT)
            t0 = time.time()
            while p.vivant() and time.time() - t0 < 8:
                time.sleep(0.2)
            if p.vivant():
                p.signal(signal.SIGKILL)
        try:
            rg.sauver(self.collecter())
        except ValueError:
            pass
        self.destroy()


def main():
    Application().mainloop()


if __name__ == "__main__":
    main()
