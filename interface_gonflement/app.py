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
import os
import signal
import socket
import subprocess
import sys
import threading
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
            if code is not None and code < 0 and -code in (signal.SIGSEGV, signal.SIGABRT, signal.SIGBUS):
                self.log(f"« {nom} » a planté ({signal.Signals(-code).name}) : plantage dans du "
                         "code C (bibliothèque caméra xiAPI, libusb, pilote série…). La pile Python "
                         "du crash est juste au-dessus (« Fatal Python error »). Si les caméras sont en "
                         "cause : « Libérer les caméras », attendre quelques secondes, ou les "
                         "débrancher/rebrancher.", "erreur")
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

    # ------------------------------------------------------------------ caméras
    SCRIPTS = ("lancer_essai.py", "lancer_calibration.py", "outils_machine.py")

    # fabricants USB du banc : Ximea (caméras) et FTDI (FT232R du déclenchement)
    FABRICANTS_USB = {"20f7": "caméra Ximea", "0403": "FT232R"}

    @staticmethod
    def _peripheriques_usb():
        """{'/dev/bus/usb/BBB/DDD': fabricant} pour les caméras et le FT232R branchés."""
        out = {}
        for d in Path("/sys/bus/usb/devices").glob("*"):
            try:
                vendeur = (d / "idVendor").read_text().strip()
                if vendeur in Application.FABRICANTS_USB:
                    bus = int((d / "busnum").read_text())
                    dev = int((d / "devnum").read_text())
                    out[f"/dev/bus/usb/{bus:03d}/{dev:03d}"] = Application.FABRICANTS_USB[vendeur]
            except (OSError, ValueError):
                pass
        return out

    @staticmethod
    def _tient_les_cameras(pid, usb):
        """Vrai si le processus a chargé la bibliothèque Ximea (libm3api / xiapi) ou a
        ouvert une caméra ou le FT232R : c'est lui qui les garde, quel que soit son
        nom (sous-processus crappy, ancien script lancé dans un terminal…)."""
        proc = Path(f"/proc/{pid}")
        try:
            maps = (proc / "maps").read_text(errors="ignore")
            if "libm3api" in maps or "xiapi" in maps.lower():
                return True
            for fd in (proc / "fd").iterdir():
                if os.readlink(fd) in usb:
                    return True
        except OSError:          # processus fini, ou d'un autre utilisateur
            pass
        return False

    def processus_restants(self):
        """Processus qui gardent les caméras (essai, calibration ou aperçu précédent,
        sous-processus crappy, xiCamTool, script lancé à la main), hors interface et
        hors tâche en cours. C'est ce qu'un pkill arrêtait."""
        actifs = set()
        if self.proc is not None and self.proc.vivant():
            actifs.add(self.proc.p.pid)
        moi = os.getpid()
        usb = self._peripheriques_usb()
        restes = {}
        r = subprocess.run(["ps", "-eo", "pid=,pgid=,args="], capture_output=True, text=True)
        for ligne in r.stdout.splitlines():
            champs = ligne.split(None, 2)
            if len(champs) < 3:
                continue
            pid, pgid, cmd = int(champs[0]), int(champs[1]), champs[2]
            if pid == moi or pgid in actifs or pgid == os.getpgid(moi):
                continue
            args = cmd.split()
            exe = Path(args[0]).name
            nos_scripts = exe.startswith("python") and any(
                Path(x).name in self.SCRIPTS and Path(x).parent.name == "interface_gonflement"
                for x in args[1:4])
            if nos_scripts or exe.startswith("xiCamTool") or self._tient_les_cameras(pid, usb):
                restes[pid] = cmd
        return restes

    def liberer_cameras(self, restes=None):
        """Arrête les processus qui gardent les caméras (SIGTERM, puis SIGKILL 2 s après)."""
        if restes is None:          # bouton « Libérer les caméras » : on montre avant d'arrêter
            restes = self.processus_restants()
            if not restes:
                self.log("Aucun processus ne garde les caméras ni le FT232R : ils sont libres. "
                         "Si une caméra ne répond toujours pas, la débrancher et la rebrancher.",
                         "info")
                return
            if not messagebox.askyesno("Libérer les caméras", "Processus qui gardent les "
                                       "caméras ou le FT232R :\n\n" + "\n".join(
                                           f"{p} : {c[:80]}" for p, c in restes.items())
                                       + "\n\nLes arrêter ?"):
                return
        for pid, cmd in restes.items():
            self.log(f"Arrêt du processus resté ouvert {pid} : {cmd[:90]}", "alerte")
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        time.sleep(2)
        for pid in restes:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def preparer_cameras(self, suite):
        """Avant un essai ou une acquisition réels : mémoire USB, processus restés
        ouverts, puis test d'ouverture et de lecture de chaque caméra (dans un
        processus séparé, coupé au bout de 20 s si une caméra est bloquée)."""
        if self.v("materiel.simulation").get():
            return suite()
        if not self.verifier_memoire_usb():
            return
        restes = self.processus_restants()
        if restes:
            if not messagebox.askyesno("Caméras occupées", (
                    f"{len(restes)} processus d'un essai ou d'un aperçu précédent sont "
                    "encore ouverts et peuvent bloquer une caméra :\n\n"
                    + "\n".join(c[:80] for c in restes.values())
                    + "\n\nLes arrêter ?")):
                return
            self.liberer_cameras(restes)
        m = self.reglages["materiel"]
        cmd = [self.python(), "-u", str(self.ICI / "outils_machine.py"), "test_cameras",
               m["sn_gauche"], m["sn_droite"]]
        self.log("Vérification des deux caméras…", "info")
        self.lbl_proc.configure(text="Vérification des caméras…")

        def tache():
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=20,
                                   env={**os.environ, "PYTHONFAULTHANDLER": "1"},
                                   cwd=str(self.ICI.parent), start_new_session=True)
                sortie, code = (r.stdout + r.stderr).strip(), r.returncode
            except subprocess.TimeoutExpired as e:
                sortie = ((e.stdout or b"").decode(errors="ignore") if isinstance(e.stdout, bytes)
                          else (e.stdout or "")).strip()
                sortie += "\nBLOQUÉ : la dernière caméra testée ne répond plus."
                code = -1
            self.after(0, lambda: fin(sortie, code))

        def fin(sortie, code):
            self.lbl_proc.configure(text="Aucune tâche en cours")
            for l in sortie.splitlines():
                self.log(l)
            if code == 0:
                # laisse au pilote USB le temps de rendre les caméras avant de les rouvrir
                return self.after(2000, suite)
            conseil = ("Une caméra ne répond pas. Le plus souvent : un programme la garde "
                       "ouverte (xiCamTool, essai précédent : bouton « Libérer les caméras »), "
                       "ou elle est dans un état USB bloqué : la débrancher et la rebrancher. "
                       "Vérifier aussi les numéros de série (onglet Matériel).")
            if messagebox.askyesno("Caméra indisponible", f"{sortie}\n\n{conseil}\n\n"
                                   "Lancer quand même ?", icon="warning"):
                suite()
        threading.Thread(target=tache, daemon=True).start()

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


def main(plantage_precedent=""):
    app = Application()
    if plantage_precedent:
        app.log("Le lancement précédent de l'interface a planté. Pile Python au moment du "
                "crash (plantages.log) :", "erreur")
        for ligne in plantage_precedent.splitlines()[-40:]:
            app.log("   " + ligne, "erreur")
    app.mainloop()


if __name__ == "__main__":
    main()
