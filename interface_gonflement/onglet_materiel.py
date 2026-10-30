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

        f = a.cadre(g, "Acquisition des images — essai")
        a.champ(f, 0, "Fréquence des images", "essai.freq_cam", "Hz",
                aide="Déclenchement des deux caméras par le FT232R")
        a.case(f, 1, "Enregistrer les images", "essai.sauver_images")
        a.case(f, 2, "Ouvrir aussi les fenêtres Grapher de crappy", "essai.graphers_crappy")

        f = a.cadre(g, "Acquisition des images — calibration")
        a.champ(f, 0, "Exposition gauche", "calibration.expo_gauche", "µs")
        a.champ(f, 1, "Exposition droite", "calibration.expo_droite", "µs")
        a.champ(f, 2, "Stabilisation avant photo", "calibration.stabilisation", "s",
                aide="Temps pendant lequel le plateau doit rester à la bonne hauteur "
                     "(position lue) avant le déclenchement des caméras")
        a.champ(f, 3, "Vitesse du plateau", "calibration.vitesse_plateau", "mm/min")
        a.case(f, 4, "Afficher le graphe de la hauteur du plateau (Grapher crappy)",
               "calibration.graphe_hauteur")
        a.note(f, 5, "Plan par plan : le plateau va à la hauteur, la position lue doit être "
                     "atteinte et stable, puis les deux caméras sont déclenchées ; on attend "
                     "les deux images avant le plan suivant. Lancement depuis l'onglet "
                     "Calibration (section 3).", 620)

        f = a.cadre(g, "Imprimante 3D (plateau)")
        a.champ(f, 0, "Port série", "materiel.port_imprimante", largeur=18)

        f = a.cadre(g, "Fichiers et communication")
        a.chemin_choisi(f, 0, "Dossier des expériences", "materiel.dossier_racine",
                        dossier=True, largeur=40)
        a.note(f, 1, "Relatif à la racine du dépôt s'il n'est pas absolu.")
        a.champ(f, 2, "Port UDP mesures", "materiel.port_udp_donnees")
        a.champ(f, 3, "Port UDP commandes", "materiel.port_udp_commandes")

        f = a.cadre(g, "Outils")
        b = ttk.Frame(f)
        b.pack(fill="x", padx=4, pady=4)
        for texte, cmd in (("Détecter les ports", lambda: a.outil("Ports", "ports")),
                           ("Libérer la mémoire USB (sudo)", self.memoire_usb),
                           ("Couper le débit (Alicat → 0)", self.debit_zero),
                           ("Libérer les caméras", lambda: a.liberer_cameras()),
                           ("Enregistrer les réglages", lambda: a.sauver_reglages(False))):
            ttk.Button(b, text=texte, command=cmd).pack(side="left", padx=3)
        ttk.Label(f, style="Petit.TLabel", wraplength=620, text=(
            "Réglages aussi enregistrés à chaque lancement et à la fermeture "
            "(interface_gonflement/reglages_utilisateur.json).")).pack(anchor="w", padx=8, pady=4)

    def memoire_usb(self, raison=""):
        """echo 0 | sudo tee /sys/module/usbcore/parameters/usbfs_memory_mb
        Renvoie True si la mémoire est libérée."""
        mdp = simpledialog.askstring("sudo", f"{raison}Mot de passe sudo :", show="*", parent=self)
        if mdp is None:
            return False
        try:
            r = subprocess.run(["sudo", "-S", "-p", "", "tee",
                                "/sys/module/usbcore/parameters/usbfs_memory_mb"],
                               input=(mdp + "\n0\n").encode(), capture_output=True, timeout=15)
            if r.returncode == 0:
                self.app.log("Mémoire USB des caméras libérée (usbfs_memory_mb = 0)", "info")
                return True
            self.app.log("Échec : " + r.stderr.decode(errors="ignore").strip(), "erreur")
        except (OSError, subprocess.SubprocessError) as e:
            self.app.log(f"Échec : {e}", "erreur")
        return False

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
