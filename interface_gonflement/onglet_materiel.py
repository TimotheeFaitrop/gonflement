"""Onglet Matériel : ports, caméras, imprimante, fichiers, thème et outils."""

import subprocess
import threading
from tkinter import simpledialog, ttk

try:
    from .theme import PALETTES
    from .widgets import CadreDefilant
except ImportError:
    from theme import PALETTES
    from widgets import CadreDefilant


class OngletMateriel(ttk.Frame):

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = a = app
        col = CadreDefilant(self, largeur=680, fond=a.P["fond"])
        col.pack(side="left", fill="both", expand=True)
        g = col.interieur

        f = a.cadre(g, "Mode et apparence")
        a.case(f, 0, "Mode simulation (ballon et caméras simulés : aucun matériel piloté)",
               "materiel.simulation", commande=a.maj_bandeau)
        a.choix(f, 1, "Thème", "materiel.theme", list(PALETTES), commande=a.changer_theme)

        f = a.cadre(g, "Débitmètre Alicat (Modbus RTU)")
        a.champ(f, 0, "Port série", "materiel.port_alicat", largeur=18)
        a.champ(f, 1, "Débit en bauds", "materiel.baud_alicat")
        a.champ(f, 2, "Pleine échelle", "materiel.pleine_echelle", "mL/min",
                aide="Débit pour une commande de 1 (alicat_flow_crappy_V3 : 13.2/1000)")
        a.case(f, 3, "Pression relative (soustrait la pression lue au démarrage)",
               "materiel.pression_relative")

        f = a.cadre(g, "Caméras Ximea et déclenchement")
        a.champ(f, 0, "N° de série gauche", "materiel.sn_gauche", largeur=14)
        a.champ(f, 1, "N° de série droite", "materiel.sn_droite", largeur=14)
        a.champ(f, 2, "Exposition gauche (essai)", "materiel.expo_gauche", "µs")
        a.champ(f, 3, "Exposition droite (essai)", "materiel.expo_droite", "µs")
        a.champ(f, 4, "Taille d'image", "materiel.taille_image", "px")
        a.champ(f, 5, "URL du FT232R", "materiel.url_ftdi", largeur=30)

        f = a.cadre(g, "Imprimante 3D (plateau)")
        a.champ(f, 0, "Port série", "materiel.port_imprimante", largeur=18)

        f = a.cadre(g, "Fichiers et communication")
        a.chemin_choisi(f, 0, "Dossier des expériences", "materiel.dossier_racine",
                        dossier=True, largeur=40)
        a.note(f, 1, "Relatif à la racine du dépôt s'il n'est pas absolu.")
        a.champ(f, 2, "Interpréteur Python", "materiel.python", largeur=40)
        a.champ(f, 3, "Port UDP mesures", "materiel.port_udp_donnees")
        a.champ(f, 4, "Port UDP commandes", "materiel.port_udp_commandes")

        f = a.cadre(g, "Outils")
        b = ttk.Frame(f)
        b.pack(fill="x", padx=4, pady=4)
        for texte, cmd in (("Détecter les ports", lambda: a.outil("Ports", "ports")),
                           ("Libérer la mémoire USB (sudo)", self.memoire_usb),
                           ("Couper le débit (Alicat → 0)", self.debit_zero),
                           ("Enregistrer les réglages", lambda: a.sauver_reglages(False))):
            ttk.Button(b, text=texte, command=cmd).pack(side="left", padx=3)
        ttk.Label(f, style="Petit.TLabel", wraplength=620, text=(
            "Réglages aussi enregistrés à chaque lancement et à la fermeture "
            "(interface_gonflement/reglages_utilisateur.json).")).pack(anchor="w", padx=8, pady=4)

    def memoire_usb(self):
        """echo 0 | sudo tee /sys/module/usbcore/parameters/usbfs_memory_mb"""
        mdp = simpledialog.askstring("sudo", "Mot de passe sudo :", show="*", parent=self)
        if mdp is None:
            return
        try:
            r = subprocess.run(["sudo", "-S", "-p", "", "tee",
                                "/sys/module/usbcore/parameters/usbfs_memory_mb"],
                               input=(mdp + "\n0\n").encode(), capture_output=True, timeout=15)
            if r.returncode == 0:
                self.app.log("Mémoire USB des caméras libérée (usbfs_memory_mb = 0)", "info")
            else:
                self.app.log("Échec : " + r.stderr.decode(errors="ignore").strip(), "erreur")
        except (OSError, subprocess.SubprocessError) as e:
            self.app.log(f"Échec : {e}", "erreur")

    def debit_zero(self, attendre=False):
        """Consigne 0 écrite directement dans l'Alicat (hors essai, ou après un kill)."""
        a = self.app
        if not a.sauver_reglages() or a.reglages["materiel"]["simulation"]:
            return
        if a.proc is not None and a.proc.vivant() and not attendre:
            return a.log("Un essai utilise le débitmètre : utiliser Arrêter / Urgence", "alerte")
        m = a.reglages["materiel"]
        cmd = [a.python(), "-u", str(a.ICI / "outils_machine.py"), "debit_zero",
               m["port_alicat"], str(m["baud_alicat"])]

        def tache():
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=20,
                                   cwd=str(a.ICI.parent))
                msg = (r.stdout + r.stderr).strip() or "Débit → 0"
            except (OSError, subprocess.SubprocessError) as e:
                msg = f"Débit → 0 impossible : {e}"
            a.after(0, lambda: a.log(msg))
        threading.Thread(target=tache, daemon=True).start()
