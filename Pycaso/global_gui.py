"""Post-traitement complet d'un essai : calibration -> ... -> pression, depuis une seule fenêtre.

Usage depuis un script placé à côté du dossier Pycaso/ :
    from Pycaso.chaine_gui import run_chaine_gui
    run_chaine_gui()

La fenêtre demande le dossier des images de calibration et le dossier de l'essai, regarde ce qui
est déjà fait (calibration calculée, Lp_final.npy, photos planes, reconstructions, data_ali.txt)
et coche en conséquence les étapes à exécuter ; on peut tout changer avant de lancer.
Chaque étape ouvre ensuite sa fenêtre habituelle, chemins déjà remplis (ou tourne avec les valeurs
par défaut si « Ouvrir les réglages de chaque étape » est décoché). La retouche (5) tourne en boucle
avec la revue des figures de la reconstruction (4) tant qu'on veut retirer des taches. À la fin,
la fenêtre principale revient, mise à jour : on peut relancer une partie de la chaîne (par
exemple une autre calibration, sans refaire la détection ni la correction).
"""

import os
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import ttk, messagebox, filedialog

from Pycaso.global_class import ETAPES, EtatEssai, source_vers_methode
from Pycaso.style_gui import Style

DOSSIER_PARCOURIR = "../../Expériences"
OK, ANNULE = "ok", "annule"


# ----- petites fenêtres entre les étapes -----

def _choisir(titre, message, boutons, defaut=0, couleur=None):
    """Fenêtre modale (thème commun) avec plusieurs boutons ; renvoie l'indice choisi (None si fermée)."""
    root = tk.Tk()
    root.title(titre)
    root.resizable(False, False)
    Style.appliquer(root)
    root.attributes("-topmost", True)
    choix = {"i": None}

    def choisir(i):
        choix["i"] = i
        root.destroy()

    cadre = ttk.Frame(root, padding=14)
    cadre.grid()
    ttk.Label(cadre, text=message, justify="left", wraplength=620,
              foreground=couleur or Style.TEXTE).grid(row=0, column=0, columnspan=len(boutons), sticky="w")
    fb = ttk.Frame(cadre)
    fb.grid(row=1, column=0, sticky="e", pady=(14, 0))
    for i, lib in enumerate(boutons):
        b = ttk.Button(fb, text=lib, command=lambda i=i: choisir(i))
        b.grid(row=0, column=i, padx=(6, 0))
        if i == defaut:
            b.focus_set()
    root.bind("<Return>", lambda _e: choisir(defaut))
    root.bind("<Escape>", lambda _e: root.destroy())
    root.mainloop()
    return choix["i"]


# ----- fenêtre principale -----

class ChaineGUI:
    """Choix des dossiers et des étapes ; renvoie un dict de choix, ou None (Quitter)."""

    def __init__(self, calib="", essai="", bilan=None):
        self.result = None
        self.root = tk.Tk()
        self.root.title("Post-traitement complet")
        self.root.resizable(False, False)
        Style.appliquer(self.root)
        if not calib:
            from Pycaso.calibration_gui import _calib_recente
            calib = _calib_recente()
        if not essai:
            from Pycaso.detection_spots_gui import _essai_recent
            essai = _essai_recent(DOSSIER_PARCOURIR, "")
        self.v = {"calib": tk.StringVar(value=calib), "essai": tk.StringVar(value=essai),
                  "regler": tk.BooleanVar(value=True)}
        self.etapes = {i: tk.BooleanVar(value=False) for i in ETAPES}
        self._construire(bilan)
        for k in ("calib", "essai"):
            self.v[k].trace_add("write", self._maj)
        for i in (1, 2, 3):
            self.etapes[i].trace_add("write", lambda *_, i=i: self._dependances(i))
        self._maj()

    def ask(self):
        self.root.mainloop()
        return self.result

    def _construire(self, bilan):
        pad = Style.PAD
        f = ttk.LabelFrame(self.root, text="Dossiers")
        f.grid(row=0, column=0, sticky="ew", **pad)
        self.lbl = {}
        for r, (cle, lib, titre) in enumerate((("calib", "Images de calibration", "Dossier des images de calibration"),
                                                ("essai", "Essai", "Dossier de l'essai"))):
            ttk.Label(f, text=lib).grid(row=2 * r, column=0, sticky="w", **pad)
            ttk.Entry(f, textvariable=self.v[cle], width=70).grid(row=2 * r, column=1, sticky="w", **pad)
            ttk.Button(f, text="…", width=3, command=lambda c=cle, t=titre: self._parcourir(c, t)).grid(
                row=2 * r, column=2, **pad)
            self.lbl[cle] = ttk.Label(f, wraplength=760, justify="left")
            self.lbl[cle].grid(row=2 * r + 1, column=1, columnspan=2, sticky="w", padx=6)

        f = ttk.LabelFrame(self.root, text="Étapes à exécuter (cochées d'après ce qui est déjà fait)")
        f.grid(row=1, column=0, sticky="ew", **pad)
        self.cases, self.etats = {}, {}
        for i, nom in ETAPES.items():
            self.cases[i] = ttk.Checkbutton(f, text=f"{i}. {nom}", variable=self.etapes[i])
            self.cases[i].grid(row=i, column=0, sticky="w", **pad)
            self.etats[i] = ttk.Label(f, wraplength=560, justify="left")
            self.etats[i].grid(row=i, column=1, sticky="w", **pad)
        ttk.Label(f, foreground=Style.GRIS, text="5 tourne en boucle avec la revue des figures de 4 tant que vous "
                  "voulez retirer des taches.").grid(row=9, column=0, columnspan=2, sticky="w", **pad)

        f = ttk.LabelFrame(self.root, text="Options")
        f.grid(row=2, column=0, sticky="ew", **pad)
        ttk.Checkbutton(f, text="Ouvrir la fenêtre de réglages de chaque étape, chemins déjà remplis "
                                "(sinon : valeurs par défaut des classes)",
                        variable=self.v["regler"]).grid(row=0, column=0, sticky="w", **pad)

        if bilan:
            f = ttk.LabelFrame(self.root, text="Dernier passage")
            f.grid(row=3, column=0, sticky="ew", **pad)
            for k, (i, texte, couleur) in enumerate(bilan):
                ttk.Label(f, text=f"{i}. {ETAPES[i]} : {texte}", foreground=couleur, wraplength=760,
                          justify="left").grid(row=k, column=0, sticky="w", padx=6, pady=1)

        fb = ttk.Frame(self.root)
        fb.grid(row=4, column=0, sticky="e", **pad)
        ttk.Button(fb, text="Quitter", command=self.root.destroy).grid(row=0, column=0, **pad)
        ttk.Button(fb, text="Lancer les étapes cochées", command=self._on_ok).grid(row=0, column=1, **pad)
        self.root.bind("<Return>", lambda _e: self._on_ok())
        self.root.bind("<Escape>", lambda _e: self.root.destroy())

    def _parcourir(self, cle, titre):
        actuel = self.v[cle].get().strip()
        depart = actuel if os.path.isdir(actuel) else (DOSSIER_PARCOURIR if os.path.isdir(DOSSIER_PARCOURIR) else ".")
        d = filedialog.askdirectory(initialdir=depart, parent=self.root, title=titre)
        if d:
            rel = os.path.relpath(d)
            self.v[cle].set(d if rel.startswith("..") else rel)

    # ----- état des dossiers -----

    def _etat(self, i, texte, couleur, cocher=None, actif=True):
        self.etats[i].configure(text=texte, foreground=couleur)
        self.cases[i].state(["!disabled"] if actif else ["disabled"])
        if cocher is not None:
            self.etapes[i].set(cocher and actif)

    def _maj(self, *_):
        """Recalcule l'état des dossiers et coche les étapes qui restent à faire."""
        e = EtatEssai(self.v["calib"].get().strip(), self.v["essai"].get().strip())
        self.e = e
        self.photos_ok = False

        # 1. calibration
        ph = e.photos_calib()
        etal = e.etalonnages()
        noms = ", ".join(f"{d.name}" for _, _, d in etal)
        if ph:
            self.lbl["calib"].configure(text=f"✔ {ph[0]} photos à gauche, {ph[1]} à droite ; résultats dans "
                                             f"{e.resultats_calib}", foreground=Style.VERT)
        else:
            self.lbl["calib"].configure(text="✘ video_extenso_left / video_extenso_right introuvables",
                                        foreground=Style.ROUGE)
        if etal:
            self._etat(1, f"✔ déjà calculée : {noms} (la plus récente sera utilisée sans réglages)", Style.VERT,
                       cocher=False, actif=bool(ph))
        elif ph:
            self._etat(1, "à faire", Style.ORANGE, cocher=True)
        else:
            self._etat(1, "✘ impossible : dossier de calibration invalide", Style.ROUGE, cocher=False, actif=False)

        # 2. détection
        if not e.essai_valide():
            self.lbl["essai"].configure(text="✘ video_extenso_left / video_extenso_right introuvables",
                                        foreground=Style.ROUGE)
            for i in range(2, 9):
                self._etat(i, "✘ dossier d'essai invalide", Style.ROUGE, cocher=False, actif=i >= 4 and
                           bool(e.dossier_essai and e.dossier_essai.is_dir()))
            return
        self.lbl["essai"].configure(text=f"✔ {e.dossier_essai.resolve()}", foreground=Style.VERT)
        if e.lp_final.is_file():
            self._etat(2, "✔ Lp_final.npy présent : inutile de refaire, sauf changement de réglages",
                       Style.VERT, cocher=False)
        else:
            self._etat(2, "à faire (pas de Lp_final.npy)", Style.ORANGE, cocher=True)

        # 3. correction par l'état plat
        g, d = e.photos_planes()
        self.photos_ok = bool(g and d)
        if not self.photos_ok:
            manque = " et ".join(n for n, p in (("photo_init_L", g), ("photo_init_R", d)) if p is None)
            self._etat(3, f"photos planes non détectées ({manque} absente) : étape impossible",
                       Style.GRIS, cocher=False, actif=False)
        elif e.correction_a_jour():
            self._etat(3, f"✔ photos planes détectées ({g.name}, {d.name}) ; correction déjà faite",
                       Style.VERT, cocher=False)
        else:
            perime = " (l'ancienne est plus vieille que Lp_final.npy)" if e.lp_corrige.is_file() else ""
            self._etat(3, f"photos planes détectées ({g.name}, {d.name}) : correction à faire{perime}",
                       Style.ORANGE, cocher=True)

        # 4. reconstruction
        recs = e.reconstructions()
        if recs:
            plus_recente, date = recs[0]
            reference = max([p.stat().st_mtime for p in (e.lp_final, e.lp_corrige) if p.is_file()]
                            + [max((f.stat().st_mtime for f in dd.iterdir()), default=0) for _, _, dd in etal[:1]])
            a_refaire = date < reference
            self._etat(4, f"existantes : {', '.join(n for n, _ in recs)}"
                          + (" ; ⚠ plus anciennes que les données d'entrée" if a_refaire else ""),
                       Style.ORANGE if a_refaire else Style.VERT, cocher=a_refaire)
            self._etat(5, f"{plus_recente} : {e.exclusions(plus_recente)}", Style.TEXTE, cocher=True)
        else:
            self._etat(4, "à faire (aucune reconstruction)", Style.ORANGE, cocher=True)
            self._etat(5, "après la reconstruction", Style.TEXTE, cocher=True)
        self._etat(6, "champs F, E, LE... sur la reconstruction retenue", Style.TEXTE, cocher=True)
        self._etat(7, "ellipses de niveau sur la reconstruction retenue", Style.TEXTE, cocher=True)
        pression = e.fichier_pression()
        if pression:
            self._etat(8, f"✔ {pression.name} trouvé", Style.VERT, cocher=True)
        else:
            self._etat(8, "data_ali.txt absent du dossier de l'essai (on pourra choisir un autre fichier "
                          "dans les réglages)", Style.ORANGE, cocher=False)
        self._dependances(1)

    def _dependances(self, i):
        """Refaire une étape amont rend les suivantes nécessaires : 2 -> 3 (si photos planes), 1, 2, 3 -> 4."""
        if not hasattr(self, "photos_ok"):
            return
        if i == 2 and self.etapes[2].get() and self.photos_ok:
            self.etapes[3].set(True)
        if any(self.etapes[k].get() for k in (1, 2, 3)) and "disabled" not in self.cases[4].state():
            self.etapes[4].set(True)

    def _on_ok(self):
        etapes = [i for i, v in self.etapes.items() if v.get()]
        erreurs = []
        if not etapes:
            erreurs.append("Aucune étape cochée")
        e = self.e
        if 1 in etapes and not e.photos_calib():
            erreurs.append("Calibration : dossier des images de calibration invalide")
        if any(i in etapes for i in (2, 3)) and not e.essai_valide():
            erreurs.append("Dossier d'essai invalide (video_extenso_left / _right introuvables)")
        if 4 in etapes and 1 not in etapes and not e.etalonnages():
            erreurs.append("Reconstruction : aucune calibration calculée ; cocher l'étape 1")
        if any(i in etapes for i in (4, 5, 6, 7, 8)) and 2 not in etapes and not e.lp_final.is_file() \
                and 4 in etapes:
            erreurs.append("Reconstruction : pas de Lp_final.npy ; cocher l'étape 2")
        if any(i in etapes for i in (5, 6, 7, 8)) and 4 not in etapes and not e.reconstructions():
            erreurs.append("Aucune reconstruction : cocher l'étape 4")
        if erreurs:
            messagebox.showerror("Lancement impossible", "\n".join(erreurs), parent=self.root)
            return
        self.result = {"calib": self.v["calib"].get().strip(), "essai": self.v["essai"].get().strip(),
                       "etapes": etapes, "regler": self.v["regler"].get()}
        self.root.destroy()


# ----- exécution des étapes -----

class Chaine:
    """Exécute les étapes choisies, dans l'ordre, en passant d'une étape à l'autre ce qu'il faut."""

    def __init__(self, calib, essai, etapes, regler=True):
        self.calib, self.essai, self.etapes, self.regler = calib, essai, sorted(etapes), regler
        self.e = EtatEssai(calib, essai)
        self.methode = self.degre = None        # calibration à utiliser pour la reconstruction
        self.detect = None                      # Detect3D de l'étape 4 (pour revoir ses figures)
        self.source = None                      # reconstruction utilisée par 5 à 8
        self.bilan = []

    @property
    def dossier_calib(self):
        r = self.e.resultats_calib
        return str(r) if r is not None and r.is_dir() else None

    def lancer(self):
        """Exécute les étapes ; renvoie le bilan [(étape, texte, couleur)]."""
        for k, i in enumerate(self.etapes):
            print(f"\n{'=' * 70}\n{i}. {ETAPES[i]}\n{'=' * 70}")
            try:
                res = getattr(self, f"etape_{i}")()
            except Exception as err:                   # erreur dans une étape : on demande quoi faire
                traceback.print_exc()
                self.bilan.append((i, f"✘ erreur : {err}", Style.ROUGE))
                if k + 1 < len(self.etapes):
                    c = _choisir(f"Erreur - étape {i}", f"{i}. {ETAPES[i]} : erreur\n\n{err}\n\n"
                                 "(détails dans le terminal)", ["Revenir au menu", "Continuer les étapes suivantes"],
                                 defaut=0, couleur=Style.ROUGE)
                    if c != 1:
                        break
                continue
            if res == ANNULE:
                self.bilan.append((i, "annulée", Style.ORANGE))
                if k + 1 < len(self.etapes):
                    c = _choisir(f"Étape {i} annulée", f"{i}. {ETAPES[i]} : annulée.",
                                 ["Revenir au menu", "Passer cette étape"], defaut=1)
                    if c != 1:
                        break
            else:
                self.bilan.append((i, f"✔ {res}" if isinstance(res, str) and res != OK else "✔ faite", Style.VERT))
        return self.bilan

    # ----- aides -----

    def _calibration_retenue(self):
        """(méthode, degré) : celle de l'étape 1, sinon la calibration calculée la plus récente."""
        if self.methode is None:
            etal = self.e.etalonnages()
            if etal:
                self.methode, self.degre, _ = etal[0]
        return self.methode, self.degre

    def _source(self):
        """Reconstruction utilisée par les étapes 5 à 8 : celle de l'étape 4, sinon la plus récente."""
        if self.source is None:
            recs = self.e.reconstructions()
            if not recs:
                raise FileNotFoundError(f"Aucune reconstruction dans {self.essai}/reconstruction")
            self.source = recs[0][0]
        return self.source

    @staticmethod
    def _preremplir(gui, essai, source=None, cle="dossier_essai"):
        gui.v[cle].set(essai)
        if source is not None and "source" in gui.v:
            if source in gui.cb_source.cget("values"):
                gui.v["source"].set(source)

    # ----- étapes -----

    def etape_1(self):
        from Pycaso.calibration_class import Calibration
        if self.regler:
            from Pycaso.calibration_gui import ask_parameters
            params = ask_parameters(self.calib)
            if params is None:
                return ANNULE
        else:
            lu = Calibration.lire_hauteurs(self.calib)
            if not lu or not (lu["z_table"] or None not in (lu["z_init"], lu["z_final"], lu["pas"])):
                raise FileNotFoundError("hauteurs_calibration.txt absent ou incomplet : cocher « Ouvrir la "
                                        "fenêtre de réglages » pour saisir les plans z")
            z = lu["z_table"] or Calibration.liste_z(lu["z_init"], lu["z_final"], lu["pas"])
            params = dict(path_images=self.calib, z_list=z, method="Lagrange", pform=4, iterations=10,
                          move_metadata=False, show_plot=True, date=lu["date"])
        calib = Calibration.from_params(params)
        if params.get("move_metadata"):
            calib.move_metadata()
        calib.run(params["method"], params["pform"], params["iterations"])
        self.methode, self.degre = params["method"], int(params["pform"])
        return f"{self.methode}, degré {self.degre}"

    def etape_2(self):
        from Pycaso.detection_spots_general import DetectionSpots
        if self.regler:
            from Pycaso.detection_spots_gui import DetectionSpotsGUI
            g = DetectionSpotsGUI()
            self._preremplir(g, self.essai, cle="dossier_mesure")
            det = g.ask()
            if det is None:
                return ANNULE
        else:
            det = DetectionSpots(dossier_mesure=self.essai)
        det.lancer()
        return f"{det.Lp.shape[2]} taches appariées, {det.Lp.shape[0]} images"

    def etape_3(self):
        from Pycaso.correction_class import Correction
        if self.regler:
            from Pycaso.correction_gui import CorrectionGUI
            g = CorrectionGUI()
            self._preremplir(g, self.essai)
            cor = g.ask()
            if cor is None:
                return ANNULE
        else:
            cor = Correction(dossier_essai=self.essai)
        bilan = cor.lancer()
        return f"{bilan['taches_gardees']} taches sur {bilan['taches_essai']}"

    def etape_4(self):
        from Pycaso.reconstruction_class import Detect3D
        methode, degre = self._calibration_retenue()
        etat_plat = self.e.correction_a_jour()
        if self.regler:
            from Pycaso.reconstruction_gui import Detect3DGUI
            g = Detect3DGUI(dossier_calib=self.dossier_calib)
            g.v["dossier_essai"].set(self.essai)
            g.v["etat_plat"].set(etat_plat)
            if methode:
                g.v["methode"].set(methode)
                g._maj_degres()
                g.v["degre"].set(str(degre))
            g._maj()
            det = g.ask()
            if det is None:
                return ANNULE
        else:
            if methode is None:
                raise FileNotFoundError("Aucune calibration calculée : cocher l'étape 1")
            det = Detect3D(dossier_essai=self.essai, dossier_calib=self.dossier_calib, methode=methode,
                           degre=degre, etat_plat=etat_plat)
        det.lancer()
        self.detect, self.source = det, det.dossier_sortie.name
        return self.source

    def _revoir_reconstruction(self):
        """Rouvre la fenêtre de la reconstruction (réglages précédents) puis retrace les figures.

        On peut y rechoisir les images à tracer, l'axe vertical, l'échelle de couleur... Les taches
        exclues sont retirées des figures. Rien n'est recalculé si X3d / Y3d / Z3d existent déjà pour
        la méthode et le degré choisis (sinon la reconstruction est calculée).
        Renvoie False si la fenêtre a été annulée.
        """
        import numpy as np
        from Pycaso.reconstruction_class import Detect3D
        from Pycaso.reconstruction_gui import Detect3DGUI, _ecrire_images
        det = self.detect
        if det is None or det.dossier_sortie.name != self.source:
            info = source_vers_methode(self.source)
            if info is None:
                raise ValueError(f"Reconstruction {self.source} : méthode non reconnue")
            methode, degre, plat = info
            det = Detect3D(dossier_essai=self.essai, dossier_calib=self.dossier_calib, methode=methode,
                           degre=degre, etat_plat=plat)

        # fenêtre préremplie avec les réglages de la dernière reconstruction / revue
        g = Detect3DGUI(dossier_calib=self.dossier_calib)
        g.root.title("Revoir les figures de la reconstruction (sans recalcul si elle existe)")
        g.v["dossier_essai"].set(self.essai)
        g.v["etat_plat"].set(det.etat_plat)
        g.v["methode"].set(det.methode)
        g._maj_degres()
        g.v["degre"].set(str(det.degre))
        g.v["images_a_tracer"].set(_ecrire_images(det.images_a_tracer))
        g.v["affichage_z"].set(det.affichage_z)
        for cle in ("couleurs_fixes", "inverser_z", "enregistrer_figures"):
            g.v[cle].set(bool(getattr(det, cle)))
        for cle in ("z_min", "z_bleu", "z_jaune", "z_max"):
            g.v[cle].set(f"{getattr(det, cle):g}")
        g.v["afficher_figures"].set(True)
        g._maj_couleurs()
        g._maj()
        nouveau = g.ask()
        if nouveau is None:
            return False

        if all((nouveau.dossier_sortie / f"{n}3d.txt").is_file() for n in "XYZ"):
            nouveau.X, nouveau.Y, nouveau.Z = (np.loadtxt(nouveau.dossier_sortie / f"{n}3d.txt", ndmin=2)
                                               for n in "XYZ")
            for n in nouveau.images_a_tracer:
                nouveau.tracer(n)
        else:                                  # autre méthode / degré, pas encore calculé : on le calcule
            print(f"{nouveau.dossier_sortie} absent : reconstruction calculée")
            nouveau.lancer()
        self.detect = nouveau                  # réglages gardés pour la revue suivante
        return True

    def etape_5(self):
        from Pycaso.retouche_class import EditeurExclusions
        source = self._source()
        reglages = {}
        if self.regler:
            from Pycaso.retouche_gui import SelectionGUI
            g = SelectionGUI()
            self._preremplir(g, self.essai, source)
            ed = g.ask()
            if ed is None:
                return ANNULE
            reglages = dict(image=ed.image, image_reference=ed.image_reference, quantite=ed.quantite,
                            inverser_z=ed.inverser_z)
            source = ed.exclusions.source
        else:
            ed = EditeurExclusions(self.essai, source)
        while True:
            ed.ouvrir()
            while True:
                c = _choisir("Retouche des taches", f"{source} : {ed.exclusions.resume()}.\n\nQue faire ?",
                             ["Revoir les figures de la reconstruction", "Retoucher encore", "Continuer"], defaut=2)
                if c == 0:
                    self._revoir_reconstruction()
                    continue
                break
            if c != 1:
                return ed.exclusions.resume()
            ed = EditeurExclusions(self.essai, source, **reglages)

    def _etape_calcul(self, module_gui, nom_gui, module_classe, nom_classe):
        """Étapes 6 à 8 : fenêtre préremplie (essai, reconstruction) ou valeurs par défaut."""
        import importlib
        source = self._source()
        if self.regler:
            g = getattr(importlib.import_module(module_gui), nom_gui)()
            self._preremplir(g, self.essai, source)
            obj = g.ask()
            if obj is None:
                return ANNULE
        else:
            obj = getattr(importlib.import_module(module_classe), nom_classe)(dossier_essai=self.essai, source=source)
        obj.lancer()
        return obj.source

    def etape_6(self):
        return self._etape_calcul("Pycaso.deformation_gui", "DeformationGUI", "Pycaso.deformation_class", "Deformation")

    def etape_7(self):
        return self._etape_calcul("Pycaso.anisotropie_gui", "AnisotropieGUI",
                                  "Pycaso.anisotropie_class", "Anisotropie")

    def etape_8(self):
        return self._etape_calcul("Pycaso.pression_gui", "PressionGUI", "Pycaso.pression_class", "PressionUz")


def run_chaine_gui():
    """Fenêtre principale, étapes cochées, retour à la fenêtre principale ; jusqu'à « Quitter »."""
    calib = essai = ""
    bilan = None
    while True:
        choix = ChaineGUI(calib, essai, bilan).ask()
        if choix is None:
            print("Post-traitement terminé")
            return bilan
        calib, essai = choix["calib"], choix["essai"]
        bilan = Chaine(**choix).lancer()