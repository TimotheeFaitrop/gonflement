"""Exclusion manuelle de taches aberrantes, choisies sur un affichage interactif.

Certaines taches restent aberrantes même sous les seuils automatiques : on connaît la forme
réelle de l'échantillon, et un point qui s'en écarte visiblement est faux. Cet outil affiche
une reconstruction image par image (vue de dessus, profils selon x et selon y) et permet de sélectionner ces
taches à la souris pour les exclure. Une tache exclue l'est sur toutes les images.

Enregistrement (indices des taches dans Lp_final.npy, donc valables pour toutes les méthodes
et pour les reconstructions corrigées par l'état plat) :
    <essai>/reconstruction/<source>/taches_exclues.json   pour cette reconstruction seulement
    <essai>/reconstruction/taches_exclues.json            pour toutes les reconstructions de l'essai
                                                          (option « toutes les reconstructions »)
Taches exclues d'une reconstruction = (communes ∪ propres) − rétablies dans cette reconstruction.

Les exclusions sont appliquées au chargement par la déformation et l'anisotropie (option
exclusions_manuelles) et dans les figures de la reconstruction.
"""
import json
import time
from pathlib import Path

import numpy as np

FICHIER = "taches_exclues.json"
SOUS_DOSSIER_RECONSTRUCTION = "reconstruction"
FICHIER_CORRECTION = "correction_infos.json"      # écrit par la correction ; donne les indices de Lp_final
FICHIERS_3D = ("X3d.txt", "Y3d.txt", "Z3d.txt")

# Éditeur en thème sombre, mêmes couleurs que les fenêtres tkinter (Pycaso/style_gui.py).
# Seule la fenêtre de l'éditeur est concernée : les figures enregistrées ailleurs restent claires.
try:
    from Pycaso.style_gui import Style as _S
    _FOND, _AXES, _TEXTE, _GRILLE, _BOUTON, _SURVOL = _S.FOND, _S.CHAMP, _S.TEXTE, _S.BORD, _S.BOUTON, _S.SURVOL
except ImportError:
    _FOND, _AXES, _TEXTE, _GRILLE, _BOUTON, _SURVOL = "#1b2433", "#26324a", "#d6deeb", "#3a4a66", "#2c3b57", "#36507a"
_RC_SOMBRE = {"figure.facecolor": _FOND, "axes.facecolor": _AXES, "axes.edgecolor": _GRILLE,
              "axes.labelcolor": _TEXTE, "axes.titlecolor": _TEXTE, "text.color": _TEXTE,
              "xtick.color": _TEXTE, "ytick.color": _TEXTE, "legend.facecolor": _FOND,
              "legend.edgecolor": _GRILLE, "legend.labelcolor": _TEXTE, "savefig.facecolor": _FOND}


class ExclusionsTaches:
    """Lecture, écriture et application des taches exclues d'une reconstruction."""

    def __init__(self, dossier_essai, source):
        self.dossier_essai = str(dossier_essai)
        self.source = source

    # ----- chemins -----

    @property
    def dossier_reconstruction(self):
        return Path(self.dossier_essai) / SOUS_DOSSIER_RECONSTRUCTION

    @property
    def dossier_source(self):
        return self.dossier_reconstruction / self.source

    @property
    def fichier_propre(self):
        return self.dossier_source / FICHIER

    @property
    def fichier_commun(self):
        return self.dossier_reconstruction / FICHIER

    # ----- correspondance colonnes <-> taches de Lp_final -----

    def indices_essai(self, nb_colonnes):
        """Indice dans Lp_final.npy de chaque colonne de X3d (différent pour une source corrigée)."""
        f = self.dossier_source / FICHIER_CORRECTION
        if f.is_file():
            with open(f, encoding="utf-8") as fh:
                indices = json.load(fh).get("indices_essai")
            if indices is not None and len(indices) == nb_colonnes:
                return np.asarray(indices, dtype=int)
        return np.arange(nb_colonnes)

    # ----- lecture -----

    @staticmethod
    def _lire(fichier):
        if not Path(fichier).is_file():
            return {}
        with open(fichier, encoding="utf-8") as fh:
            return json.load(fh)

    def lire(self):
        """(communes, propres, rétablies) : ensembles d'indices de Lp_final."""
        commun = self._lire(self.fichier_commun)
        propre = self._lire(self.fichier_propre)
        return (set(commun.get("exclues", [])), set(propre.get("exclues", [])),
                set(propre.get("retablies", [])))

    def exclues_essai(self):
        """Indices de Lp_final exclus pour cette reconstruction."""
        communes, propres, retablies = self.lire()
        return (communes | propres) - retablies

    def masque_colonnes(self, nb_colonnes):
        """Booléen par colonne de X3d : True si la tache est exclue."""
        exclues = self.exclues_essai()
        if not exclues:
            return np.zeros(nb_colonnes, dtype=bool)
        return np.isin(self.indices_essai(nb_colonnes), sorted(exclues))

    def appliquer(self, *tableaux):
        """Met à NaN les colonnes exclues des tableaux (images, taches) ; renvoie le nombre de taches exclues."""
        masque = self.masque_colonnes(tableaux[0].shape[1])
        for t in tableaux:
            t[:, masque] = np.nan
        return int(masque.sum())

    def resume(self):
        """Texte court : nombre de taches exclues (propres, communes, rétablies)."""
        communes, propres, retablies = self.lire()
        total = len((communes | propres) - retablies)
        if not (communes or propres or retablies):
            return "aucune tache exclue"
        morceaux = [f"{total} tache(s) exclue(s)"]
        if communes:
            morceaux.append(f"{len(communes)} pour toutes les reconstructions")
        if propres:
            morceaux.append(f"{len(propres)} pour celle-ci seulement")
        if retablies:
            morceaux.append(f"{len(retablies)} commune(s) rétablie(s) ici")
        return " ; ".join(morceaux)

    # ----- écriture -----

    def enregistrer(self, exclues, pour_toutes=False):
        """Enregistre la sélection (indices de Lp_final) de cette reconstruction.

        pour_toutes=False : seules les différences avec la liste commune sont écrites pour cette
        reconstruction (taches en plus, taches communes rétablies). pour_toutes=True : la sélection
        devient la liste commune, et la liste propre de cette reconstruction est supprimée.
        """
        exclues = set(int(i) for i in exclues)
        communes, _, _ = self.lire()
        date = time.strftime("%Y-%m-%d %H:%M")
        if pour_toutes:
            self._ecrire(self.fichier_commun, {"exclues": sorted(exclues), "date": date,
                                               "depuis": self.source})
            if self.fichier_propre.is_file():
                self.fichier_propre.unlink()
        else:
            propres, retablies = exclues - communes, communes - exclues
            if propres or retablies:
                self._ecrire(self.fichier_propre, {"exclues": sorted(propres), "retablies": sorted(retablies),
                                                   "date": date})
            elif self.fichier_propre.is_file():
                self.fichier_propre.unlink()

    @staticmethod
    def _ecrire(fichier, contenu):
        Path(fichier).parent.mkdir(parents=True, exist_ok=True)
        with open(fichier, "w", encoding="utf-8") as fh:
            json.dump(contenu, fh, indent=1, ensure_ascii=False)


class EditeurExclusions:
    """Fenêtre matplotlib : vue de dessus + profils selon x et y d'une image, sélection des taches à exclure.

    Souris :
      - clic sur une tache : l'exclut ou la rétablit ;
      - glisser (lasso) : exclut (ou rétablit, selon le mode) toutes les taches entourées ;
      - la loupe et la main de la barre d'outils servent à zoomer / se déplacer (désactiver
        l'outil pour sélectionner de nouveau).
    Clavier : ← → image précédente / suivante, u = annuler, e = enregistrer.
    Aides : « Bande » limite chaque profil aux taches d'une tranche (y fixé pour le profil selon x,
    x fixé pour le profil selon y ; positions réglables, dessinées sur la vue de dessus) ;
    « Couleur : écart » colore chaque tache par son écart au plan local de ses voisines, ce qui fait ressortir les taches qui sortent de la forme.
    """
    VOISINES = 8                                 # voisines pour la couleur « écart »

    def __init__(self, dossier_essai, source, image=-1, image_reference=0, quantite="Uz", inverser_z=None):
        self.exclusions = ExclusionsTaches(dossier_essai, source)
        d = self.exclusions.dossier_source
        manquants = [f for f in FICHIERS_3D if not (d / f).is_file()]
        if manquants:
            raise FileNotFoundError(f"{', '.join(manquants)} introuvable(s) dans {d}")
        self.X, self.Y, self.Z = (np.loadtxt(d / f, ndmin=2) for f in FICHIERS_3D)
        self.nb_images, self.nb_taches = self.X.shape
        self.image = range(self.nb_images)[image]
        self.image_reference = range(self.nb_images)[image_reference]
        self.quantite = quantite                 # "Uz" (z − z image de référence) ou "z"
        if inverser_z is None:                   # auto : le dôme doit monter
            dz = self.Z - self.Z[self.image_reference]
            inverser_z = bool(np.nanmax(-dz) > np.nanmax(dz)) if np.isfinite(dz).any() else False
        self.inverser_z = inverser_z
        self.indices_essai = self.exclusions.indices_essai(self.nb_taches)
        self.exclues = self.exclusions.masque_colonnes(self.nb_taches)       # sélection en cours (colonnes)
        self.enregistre = self.exclues.copy()
        self.historique = []
        self.mode_retablir = False
        self.pour_toutes = False
        self.cadre_complet = False
        self.bande = False
        self.couleur_ecart = False
        x0, y0 = self.X[0], self.Y[0]
        ok0 = np.isfinite(x0) & np.isfinite(y0)
        pts = np.column_stack((x0[ok0], y0[ok0]))
        from scipy.spatial import cKDTree
        self.espacement = float(np.median(cKDTree(pts).query(pts, k=2)[0][:, 1])) if len(pts) > 2 else 1.0
        self.largeur_bande = 3 * self.espacement

    # ----- données affichées -----

    def valeurs(self, n):
        """x, y, valeur verticale (z ou Uz, signe choisi) de l'image n."""
        z = self.Z[n] - (self.Z[self.image_reference] if self.quantite == "Uz" else 0)
        if self.inverser_z:
            z = -z
        return self.X[n], self.Y[n], z

    def ecart_voisines(self, x, y, z):
        """Écart de chaque tache au plan local de ses VOISINES voisines (non exclues), en mm.

        Le plan (z = a + b x + c y) est ajusté sur les voisines, sans la tache elle-même, puis
        réajusté sans les voisines qui s'en écartent nettement : la pente du dôme (bords compris)
        n'est pas prise pour un écart, et une voisine aberrante ne fausse pas le plan.
        """
        from scipy.spatial import cKDTree
        ok = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
        ref = ok & ~self.exclues
        e = np.full(len(x), np.nan)
        if ref.sum() <= self.VOISINES + 1:
            return e
        xr, yr, zr = x[ref], y[ref], z[ref]
        _, k = cKDTree(np.column_stack((xr, yr))).query(np.column_stack((x[ok], y[ok])), k=self.VOISINES + 1)
        soi = np.zeros(ok.sum(), bool)                   # la tache est sa propre 1re voisine si non exclue
        soi[ref[ok]] = True
        k = np.where(soi[:, None], k[:, 1:], k[:, :-1])
        x0, y0 = x[ok][:, None], y[ok][:, None]
        A = np.stack((np.ones_like(k, float), xr[k] - x0, yr[k] - y0), axis=-1)     # (n, k, 3)
        b = zr[k]
        poids = np.ones_like(b)
        for _ in range(2):
            Aw = A * poids[..., None]
            coef = np.linalg.solve(np.einsum("nki,nkj->nij", Aw, A) + 1e-9 * np.eye(3),
                                   np.einsum("nki,nk->ni", Aw, b)[..., None])[..., 0]
            res = np.abs(np.einsum("nki,ni->nk", A, coef) - b)
            poids = (res <= 2.5 * np.median(res, axis=1, keepdims=True) + 1e-9).astype(float)
        e[ok] = z[ok] - coef[:, 0]                        # coef[0] = plan local à l'endroit de la tache
        return e

    def _limites(self, valeurs):
        """Cadre : toutes les valeurs (cadre complet) ou cadre robuste (centiles, avec marge)."""
        v = np.concatenate([a[np.isfinite(a)] for a in valeurs]) if valeurs else np.array([0.0, 1.0])
        if not len(v):
            return -1.0, 1.0
        if self.cadre_complet:
            lo, hi = v.min(), v.max()
        else:
            lo, hi = np.percentile(v, (1, 99))
            marge = 0.3 * (hi - lo)
            lo, hi = lo - marge, hi + marge
        if hi <= lo:
            lo, hi = lo - 1, hi + 1
        pad = 0.03 * (hi - lo)
        return lo - pad, hi + pad

    # ----- interface -----

    def ouvrir(self):
        """Ouvre la fenêtre (bloquant jusqu'à sa fermeture). Renvoie les indices de Lp_final exclus."""
        import matplotlib.pyplot as plt
        with plt.rc_context(_RC_SOMBRE):          # toute la vie de la fenêtre (plt.show bloque)
            self.construire()
            plt.show()
        return sorted(self.indices_essai[self.exclues].tolist())

    def construire(self):
        import matplotlib.pyplot as plt
        from matplotlib.widgets import Button, CheckButtons, LassoSelector, RadioButtons, Slider

        self.fig = plt.figure(figsize=(18, 9))
        self.fig.canvas.manager.set_window_title(f"Exclusion de taches - {self.exclusions.source}")
        self.ax_dessus = self.fig.add_axes((0.035, 0.27, 0.30, 0.65))
        # profils : selon x (bande à y fixé) et selon y (bande à x fixé)
        self.ax_profils = {"x": self.fig.add_axes((0.41, 0.27, 0.27, 0.65)),
                           "y": self.fig.add_axes((0.715, 0.27, 0.27, 0.65))}
        self.ax_slider = self.fig.add_axes((0.06, 0.12, 0.64, 0.035))
        self.slider = Slider(self.ax_slider, "Image", 0, self.nb_images - 1, valinit=self.image, valstep=1,
                             valfmt="%d", track_color=_GRILLE)
        self.slider.on_changed(lambda v: self.changer_image(int(v)))

        # curseurs des bandes, sous chaque profil : position de la tranche (y pour le profil x, x pour le profil y)
        self.sliders_bande, self.ax_bandes = {}, {}
        for axe, (x0, autre) in {"x": (0.44, "y"), "y": (0.745, "x")}.items():
            self.ax_bandes[axe] = self.fig.add_axes((x0, 0.175, 0.22, 0.03))
            self.sliders_bande[axe] = Slider(self.ax_bandes[axe], f"Bande ({autre})", 0, 1, valinit=0.5,
                                            track_color=_GRILLE)
            self.sliders_bande[axe].on_changed(lambda _v: self.dessiner() if self.bande else None)
            self.ax_bandes[axe].set_visible(False)

        boutons = {}
        for nom, (x, w, txt) in {"prec": (0.74, 0.04, "◀"), "suiv": (0.785, 0.04, "▶"),
                                 "annuler": (0.02, 0.075, "Annuler (u)"),
                                 "tout": (0.10, 0.08, "Tout rétablir"),
                                 "cadre": (0.185, 0.085, "Cadre : robuste"),
                                 "bande": (0.275, 0.07, "Bande : non"),
                                 "couleur": (0.35, 0.10, "Couleur : hauteur"),
                                 "enregistrer": (0.875, 0.11, "Enregistrer (e)")}.items():
            y = 0.115 if nom in ("prec", "suiv") else 0.03
            boutons[nom] = Button(self.fig.add_axes((x, y, w, 0.045)), txt, color=_BOUTON, hovercolor=_SURVOL)
        boutons["prec"].on_clicked(lambda _e: self.changer_image(self.image - 1))
        boutons["suiv"].on_clicked(lambda _e: self.changer_image(self.image + 1))
        boutons["annuler"].on_clicked(lambda _e: self.annuler())
        boutons["tout"].on_clicked(lambda _e: self.modifier(np.ones(self.nb_taches, bool), retablir=True))
        boutons["cadre"].on_clicked(lambda _e: self.basculer_cadre())
        boutons["enregistrer"].on_clicked(lambda _e: self.enregistrer())
        boutons["bande"].on_clicked(lambda _e: self.basculer_bande())
        boutons["couleur"].on_clicked(lambda _e: self.basculer_couleur())
        self.boutons = boutons

        self.radio = RadioButtons(self.fig.add_axes((0.46, 0.015, 0.10, 0.075)),
                                  ("lasso : exclure", "lasso : rétablir"))
        self.radio.on_clicked(lambda lab: setattr(self, "mode_retablir", lab.endswith("rétablir")))
        self.case_toutes = CheckButtons(self.fig.add_axes((0.57, 0.015, 0.20, 0.075)),
                                        ["pour toutes les reconstructions"], [self.pour_toutes])
        self.case_toutes.on_clicked(lambda _l: setattr(self, "pour_toutes", not self.pour_toutes))
        self.texte = self.fig.text(0.035, 0.965, "", fontsize=10, va="center")

        self.lassos = [LassoSelector(ax, onselect=lambda verts, ax=ax: self.lasso(ax, verts),
                                     props={"color": "r", "linewidth": 1})
                       for ax in (self.ax_dessus, *self.ax_profils.values())]
        self.fig.canvas.mpl_connect("key_press_event", self.clavier)
        self.fig.canvas.mpl_connect("close_event", self.fermeture)
        self.dessiner(nouveaux_cadres=True)

    def position_bande(self, axe):
        """Position de la tranche du profil selon axe ('x' : y fixé ; 'y' : x fixé), en mm."""
        autre = "y" if axe == "x" else "x"
        lo, hi = self.cadres[autre]
        return lo + self.sliders_bande[axe].val * (hi - lo)

    def dans_bande(self, axe, x, y):
        """Taches visibles dans le profil selon axe (toutes si la bande est désactivée)."""
        if not self.bande:
            return np.ones(len(x), dtype=bool)
        autre = y if axe == "x" else x
        with np.errstate(invalid="ignore"):
            return np.abs(autre - self.position_bande(axe)) <= self.largeur_bande / 2

    def dessiner(self, nouveaux_cadres=False):
        x, y, z = self.valeurs(self.image)
        ok = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
        garde, exclu = ok & ~self.exclues, ok & self.exclues
        nom_z = "Uz (mm)" if self.quantite == "Uz" else "z (mm)"
        if nouveaux_cadres or not hasattr(self, "cadres"):
            vals = [self.valeurs(n) for n in range(self.nb_images)]
            self.cadres = {"x": self._limites([v[0] for v in vals]), "y": self._limites([v[1] for v in vals]),
                           "z": self._limites([v[2] for v in vals])}
        cz = self.cadres["z"]
        if self.couleur_ecart:
            couleur = self.ecart_voisines(x, y, z)
            lim = np.nanpercentile(np.abs(couleur[garde]), 99) * 1.5 if garde.any() else 1.0
            cmap, vmin, vmax = "coolwarm", -lim, lim
            nom_couleur = f"écart au plan local des {self.VOISINES} voisines (mm)"
        else:
            couleur, cmap, vmin, vmax, nom_couleur = z, "viridis", cz[0], cz[1], nom_z
        marque_exclue = "w" if self.couleur_ecart else "#ff5c5c"

        a = self.ax_dessus
        a.clear()
        sc = a.scatter(x[garde], y[garde], c=couleur[garde], s=9, cmap=cmap, vmin=vmin, vmax=vmax)
        a.scatter(x[exclu], y[exclu], s=40, marker="x", c=marque_exclue, lw=1.2)
        if self.bande:
            demi = self.largeur_bande / 2
            py, px = self.position_bande("x"), self.position_bande("y")
            a.axhspan(py - demi, py + demi, color="tab:orange", alpha=0.25, lw=0)     # tranche du profil x
            a.axvspan(px - demi, px + demi, color="#c99cff", alpha=0.25, lw=0)     # tranche du profil y
        a.set_xlim(self.cadres["x"]); a.set_ylim(self.cadres["y"]); a.set_aspect("equal", adjustable="box")
        a.set_xlabel("x (mm)"); a.set_ylabel("y (mm)"); a.set_title(f"Vue de dessus (couleur : {nom_couleur})",
                                                                     fontsize=10)
        if not hasattr(self, "barre"):
            self.barre = self.fig.colorbar(sc, ax=a, fraction=0.04, pad=0.01)
        else:
            self.barre.update_normal(sc)

        for axe, a in self.ax_profils.items():
            a.clear()
            h = x if axe == "x" else y
            b = self.dans_bande(axe, x, y)
            g, e = garde & b, exclu & b
            a.scatter(h[g], z[g], c=couleur[g], s=9, cmap=cmap, vmin=vmin, vmax=vmax)
            a.scatter(h[e], z[e], s=40, marker="x", c=marque_exclue, lw=1.2, label=f"exclues ({e.sum()})")
            a.set_xlim(self.cadres[axe]); a.set_ylim(cz)
            a.set_xlabel(f"{axe} (mm)"); a.set_ylabel(nom_z)
            autre = "y" if axe == "x" else "x"
            tranche = (f"{autre} = {self.position_bande(axe):.1f} ± {self.largeur_bande / 2:.1f} mm"
                       if self.bande else "toutes les taches")
            a.set_title(f"Profil selon {axe} ({tranche})", fontsize=10,
                        color=("tab:orange" if axe == "x" else "#c99cff") if self.bande else _TEXTE)
            a.legend(loc="upper right", fontsize=8)

        # points hors du cadre robuste : signalés
        hors = ok & ((x < self.cadres["x"][0]) | (x > self.cadres["x"][1]) | (y < self.cadres["y"][0])
                     | (y > self.cadres["y"][1]) | (z < cz[0]) | (z > cz[1]))
        modif = "" if np.array_equal(self.exclues, self.enregistre) else "   • modifications non enregistrées"
        hors_txt = f"   • {hors.sum()} tache(s) hors du cadre (bouton « Cadre »)" if hors.sum() else ""
        ref = f" − image {self.image_reference}" if self.quantite == "Uz" else ""
        self.texte.set_text(f"{self.exclusions.source} — image {self.image} / {self.nb_images - 1} — "
                            f"{ok.sum()} taches, {self.exclues.sum()} exclue(s) — z{ref}"
                            f"{' (signe inversé)' if self.inverser_z else ''}{modif}{hors_txt}")
        self.fig.canvas.draw_idle()

    # ----- actions -----

    def changer_image(self, n):
        n = int(np.clip(n, 0, self.nb_images - 1))
        if n != self.image:
            self.image = n
            if int(self.slider.val) != n:
                self.slider.set_val(n)              # rappelle changer_image, sans effet
            self.dessiner()

    def modifier(self, masque, retablir):
        """Exclut (ou rétablit) les taches du masque ; mémorise l'état précédent pour « Annuler »."""
        nouveau = self.exclues & ~masque if retablir else self.exclues | masque
        if not np.array_equal(nouveau, self.exclues):
            self.historique.append(self.exclues.copy())
            self.exclues = nouveau
            self.dessiner()

    def annuler(self):
        if self.historique:
            self.exclues = self.historique.pop()
            self.dessiner()

    def basculer_cadre(self):
        self.cadre_complet = not self.cadre_complet
        self.boutons["cadre"].label.set_text("Cadre : tout" if self.cadre_complet else "Cadre : robuste")
        self.dessiner(nouveaux_cadres=True)

    def basculer_bande(self):
        self.bande = not self.bande
        for ax in self.ax_bandes.values():
            ax.set_visible(self.bande)
        self.boutons["bande"].label.set_text("Bande : oui" if self.bande else "Bande : non")
        self.dessiner()

    def basculer_couleur(self):
        self.couleur_ecart = not self.couleur_ecart
        self.boutons["couleur"].label.set_text("Couleur : écart" if self.couleur_ecart else "Couleur : hauteur")
        self.dessiner()

    def _coordonnees(self, ax):
        """Coordonnées affichées dans la vue ax ; NaN pour les taches hors de la bande d'un profil."""
        x, y, z = self.valeurs(self.image)
        if ax is self.ax_dessus:
            return np.column_stack((x, y))
        axe = "x" if ax is self.ax_profils["x"] else "y"
        pts = np.column_stack((x if axe == "x" else y, z))
        pts[~self.dans_bande(axe, x, y)] = np.nan       # seules les taches visibles sont sélectionnables
        return pts

    def lasso(self, ax, verts):
        """Lasso : toutes les taches entourées ; un simple clic : la tache la plus proche (bascule)."""
        from matplotlib.path import Path as Chemin
        pts = self._coordonnees(ax)
        ok = np.isfinite(pts).all(axis=1)
        verts = np.asarray(verts)
        # taille du tracé en pixels : petit = clic
        ecran = ax.transData.transform(verts)
        if len(verts) < 3 or np.ptp(ecran, axis=0).max() < 6:
            if not ok.any():
                return
            clic = ax.transData.transform(verts[-1:])
            d = np.hypot(*(ax.transData.transform(np.where(ok[:, None], pts, 0)) - clic).T)
            d[~ok] = np.inf
            i = int(np.argmin(d))
            if d[i] <= 10:                         # à moins de 10 pixels
                masque = np.zeros(self.nb_taches, bool)
                masque[i] = True
                self.modifier(masque, retablir=bool(self.exclues[i]))
                print(f"Tache {i} (Lp_final : {self.indices_essai[i]}) "
                      f"{'exclue' if self.exclues[i] else 'rétablie'}")
            return
        dedans = np.zeros(self.nb_taches, bool)
        dedans[ok] = Chemin(verts).contains_points(pts[ok])
        if dedans.any():
            self.modifier(dedans, retablir=self.mode_retablir)

    def clavier(self, event):
        if event.key == "left":
            self.changer_image(self.image - 1)
        elif event.key == "right":
            self.changer_image(self.image + 1)
        elif event.key == "u":
            self.annuler()
        elif event.key == "e":
            self.enregistrer()

    def enregistrer(self):
        self.exclusions.enregistrer(self.indices_essai[self.exclues].tolist(), pour_toutes=self.pour_toutes)
        self.enregistre = self.exclues.copy()
        ou = (self.exclusions.fichier_commun if self.pour_toutes else self.exclusions.fichier_propre)
        print(f"Enregistré : {self.exclues.sum()} tache(s) exclue(s) "
              f"({'toutes les reconstructions' if self.pour_toutes else 'cette reconstruction'}) -> {ou}")
        self.dessiner()

    def fermeture(self, _event):
        if not np.array_equal(self.exclues, self.enregistre):
            print("⚠ Fenêtre fermée sans enregistrer : les dernières modifications sont perdues.")