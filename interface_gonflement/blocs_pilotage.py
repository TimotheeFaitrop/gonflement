"""Blocs crappy de pilotage du gonflement.

Trois contrôleurs partagent la même mécanique (classe `_Pilotage`) :
  * une cible qui monte en rampe vers la consigne (vitesse réglable),
  * un palier de durée réglable, puis la fin du profil (débit coupé),
  * la sécurité pression max / durée max / débit max / variation max,
  * la réception de commandes de l'interface en UDP (nouvelle consigne,
    pause, reprise, arrêt, urgence).

Tous travaillent en mL/min et envoient au débitmètre `cmd = débit / pleine_échelle`
(même convention que alicat_flow_crappy_V3 : 13.2/1000 pour 13.2 mL/min).

  PilotageDebit       : consigne de débit (mL/min)
  PilotagePression    : consigne de pression, régulateur PI sur le débit
  PilotageDeformation : consigne de déformation (%), PI + anticipation

`FluxInterface` renvoie les mesures à l'interface en UDP pour les courbes.
Le matériel simulé (débitmètre, caméras) est dans simulation.py.
"""

import json
import math
import socket
import time

import crappy

# Codes d'état envoyés sous le label 'etat'
ATTENTE, RAMPE, PALIER, FIN, PAUSE, SECURITE, TENSION = 0, 1, 2, 3, 4, 5, 6
NOMS_ETATS = {TENSION: "mise en tension", ATTENTE: "attente", RAMPE: "rampe", PALIER: "palier",
              FIN: "fin du profil", PAUSE: "pause", SECURITE: "SÉCURITÉ"}


# --------------------------------------------------------------------------
# Déformation : choix des labels selon la source
# --------------------------------------------------------------------------
class EstimateurDeformation:
    """Calcule une déformation scalaire (%) à partir des labels reçus.

    source 2D  : labels VideoExtenso exx_r / eyy_r / exx_l / eyy_l (déjà en %)
    source 3D  : label 'eps_3d' (%) sorti par stereo_3d.StereoDeformation
                 (stéréo-corrélation Pycaso, composante choisie dans ce bloc)
    simulation : labels exx_sim / eyy_sim de AlicatSimule (en %)
    """

    def __init__(self, source="2D", composante="exx", camera="moyenne"):
        self.source = source
        self.composante = composante
        self.camera = camera

    @property
    def labels(self):
        if self.source == "3D":
            return ["eps_3d"]
        if self.source == "sim":
            return ["exx_sim", "eyy_sim"]
        cams = {"droite": ["r"], "gauche": ["l"]}.get(self.camera, ["r", "l"])
        return [f"{c}_{s}" for s in cams for c in ("exx", "eyy")]

    def calcule(self, donnees):
        """Renvoie la déformation en % ou None si les données manquent."""
        if self.source == "3D":
            return _num(donnees.get("eps_3d"))

        if self.source == "sim":
            paires = [(_num(donnees.get("exx_sim")), _num(donnees.get("eyy_sim")))]
        else:
            cams = {"droite": ["r"], "gauche": ["l"]}.get(self.camera, ["r", "l"])
            paires = [(_num(donnees.get(f"exx_{s}")), _num(donnees.get(f"eyy_{s}")))
                      for s in cams]
        valeurs = []
        for exx, eyy in paires:
            if exx is None or eyy is None:
                continue
            valeurs.append({"exx": exx, "eyy": eyy, "moyenne": (exx + eyy) / 2,
                            "toutes": (exx + eyy) / 2,
                            "max": max(exx, eyy)}[self.composante])
        if not valeurs:
            return None
        return sum(valeurs) / len(valeurs)


def _num(v):
    """Convertit en float si possible (crappy peut envoyer des listes)."""
    if isinstance(v, (list, tuple)):
        v = v[-1] if v else None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


# --------------------------------------------------------------------------
# Réception des commandes de l'interface
# --------------------------------------------------------------------------
class _RecepteurUDP:
    def __init__(self, port):
        self.port = port
        self.sock = None

    def ouvrir(self):
        if not self.port:
            return
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", int(self.port)))
        self.sock.setblocking(False)

    def messages(self):
        out = []
        while self.sock is not None:
            try:
                brut, _ = self.sock.recvfrom(4096)
            except (BlockingIOError, OSError):
                break
            try:
                out.append(json.loads(brut.decode()))
            except ValueError:
                pass
        return out

    def fermer(self):
        if self.sock is not None:
            self.sock.close()
            self.sock = None


# --------------------------------------------------------------------------
# Base commune des contrôleurs
# --------------------------------------------------------------------------
class _Pilotage(crappy.blocks.Block):

    def __init__(self, consigne, vitesse, duree_palier=0.0, attente=0.0,
                 pleine_echelle=1000.0, debit_max=200.0, vitesse_cmd_max=100.0,
                 pression_max=1500.0, duree_max=1800.0, arret_auto=True,
                 port_commandes=None, label_pression="press", freq=50,
                 estimateur=None):
        super().__init__()
        self.freq = freq
        self.consigne = float(consigne)
        self.vitesse = float(vitesse)            # unité de consigne / s ; <=0 : échelon
        self.duree_palier = float(duree_palier)  # 0 : palier infini
        self.attente = float(attente)
        self.fs = float(pleine_echelle)
        self.debit_max = float(debit_max)
        self.vitesse_cmd_max = float(vitesse_cmd_max)
        self.pression_max = float(pression_max)
        self.duree_max = float(duree_max)
        self.arret_auto = bool(arret_auto)
        self.label_pression = label_pression
        self.estimateur = estimateur
        self.labels = ["t(s)", "cmd", "debit_cmd", "cible", "consigne",
                       "mesure", "etat"]
        self._udp = _RecepteurUDP(port_commandes)

    # ---- cycle de vie crappy
    def prepare(self):
        self._udp.ouvrir()
        self.dernier = {}            # dernières valeurs reçues, tous labels
        self.t_debut = None          # début du profil (première mesure valide)
        self.t_prec = None
        self.temps_profil = 0.0      # n'avance pas pendant la pause
        self.cible = None
        self.t_palier = None
        self.t_fin = None
        self.en_pause = False
        self.securite = False
        self.debit = 0.0             # mL/min envoyé
        self.etat = ATTENTE
        self.mesure = None

    def loop(self):
        nouveau = self.recv_last_data(fill_missing=False)
        self.dernier.update(nouveau)
        maintenant = time.time()
        self._traiter_commandes()

        pression = _num(self.dernier.get(self.label_pression))
        if pression is not None and pression > self.pression_max and not self.securite:
            self.securite = True
            self.log(30, f"SÉCURITÉ : pression {pression:.1f} > {self.pression_max} "
                         f"-> débit coupé")
            self.t_fin = maintenant

        if self.t_debut is None:
            if self._pret(nouveau):
                self.t_debut = maintenant
                self.t_prec = maintenant
                self.cible = self._cible_initiale()
                self.log(20, f"Début du profil, cible initiale = {self.cible:.3f}")
            self._envoyer(0.0, maintenant)
            return

        dt = max(0.0, maintenant - self.t_prec)
        self.t_prec = maintenant
        if not self.en_pause:
            self.temps_profil += dt

        if self.securite:
            self.etat = SECURITE
            debit = 0.0
        elif self.duree_max > 0 and maintenant - self.t_debut > self.duree_max:
            if self.etat != FIN:
                self.log(20, "Durée maximale atteinte")
                self.t_fin = maintenant
            self.etat = FIN
            debit = 0.0
        elif self.etat == FIN:
            debit = 0.0
        elif self.temps_profil < self.attente:
            self.etat = ATTENTE
            debit = 0.0
        else:
            if not self.en_pause:
                self._avancer_cible(dt, maintenant)
            debit = self._calcul_debit(dt, nouveau, maintenant)
            if self.etat == FIN:
                debit = 0.0
            elif self.en_pause:
                self.etat = PAUSE

        self._envoyer(debit, maintenant, dt)

        if (self.arret_auto and self.t_fin is not None
                and maintenant - self.t_fin > 2.0):
            self.log(20, "Fin de l'essai : arrêt automatique")
            self.stop()

    def finish(self):
        self._udp.fermer()

    # ---- profil de consigne
    def _avancer_cible(self, dt, maintenant):
        if self.cible is None:
            return
        ecart = self.consigne - self.cible
        if self.vitesse <= 0:
            self.cible = self.consigne
        else:
            pas = self.vitesse * dt
            self.cible = self.consigne if abs(ecart) <= pas else \
                self.cible + math.copysign(pas, ecart)
        if self.cible == self.consigne:
            if self.t_palier is None:
                self.t_palier = maintenant
                self.log(20, "Consigne atteinte : palier")
            self.etat = PALIER
            if self.duree_palier > 0 and maintenant - self.t_palier >= self.duree_palier:
                self.log(20, "Fin du palier")
                self.etat = FIN
                self.t_fin = maintenant
        else:
            self.t_palier = None
            self.etat = RAMPE

    def _vitesse_cible(self):
        """Vitesse instantanée de la cible (pour l'anticipation)."""
        if self.etat == RAMPE and not self.en_pause and self.vitesse > 0:
            return math.copysign(self.vitesse, self.consigne - self.cible)
        return 0.0

    # ---- envoi
    def _envoyer(self, debit, maintenant, dt=0.0):
        debit = max(0.0, min(debit, self.debit_max))
        if debit > 0 and dt > 0 and self.vitesse_cmd_max > 0:
            pas = self.vitesse_cmd_max * dt
            debit = min(debit, self.debit + pas)   # limitation à la montée seulement
        if self.securite or self.etat == FIN:
            debit = 0.0
        self.debit = debit
        self.send({"t(s)": maintenant - self.t0,
                   "cmd": debit / self.fs,
                   "debit_cmd": debit,
                   "cible": float("nan") if self.cible is None else self.cible,
                   "consigne": self.consigne,
                   "mesure": float("nan") if self.mesure is None else self.mesure,
                   "etat": self.etat, **self._donnees_sup()})

    def _donnees_sup(self):
        return {}

    # ---- commandes de l'interface
    def _traiter_commandes(self):
        for msg in self._udp.messages():
            action = msg.get("action")
            if action == "consigne":
                try:
                    v = float(msg["valeur"])
                except (KeyError, TypeError, ValueError):
                    continue
                self.log(20, f"Nouvelle consigne : {v}")
                self.consigne = v
                if self.etat in (PALIER, FIN) and not self.securite:
                    self.etat = RAMPE
                    self.t_fin = None
                    self.t_palier = None
            elif action == "vitesse":
                try:
                    self.vitesse = float(msg["valeur"])
                    self.log(20, f"Nouvelle vitesse de rampe : {self.vitesse}")
                except (KeyError, TypeError, ValueError):
                    pass
            elif action == "pause":
                self.en_pause = True
                self.log(20, "Pause")
            elif action == "reprendre":
                self.en_pause = False
                self.log(20, "Reprise")
            elif action == "fin":
                self.log(20, "Fin du profil demandée")
                self.etat = FIN
                self.t_fin = time.time()
            elif action in ("stop", "urgence"):
                self.log(30, f"Arrêt demandé par l'interface ({action})")
                self.securite = action == "urgence"
                self.etat = FIN
                self._envoyer(0.0, time.time())
                self.stop()

    # ---- à surcharger
    def _pret(self, nouveau):
        return self.label_pression in self.dernier

    def _cible_initiale(self):
        return 0.0

    def _calcul_debit(self, dt, nouveau, maintenant):
        raise NotImplementedError


# --------------------------------------------------------------------------
class PilotageDebit(_Pilotage):
    """Consigne de débit (mL/min) en rampe puis palier.

    Pause = débit coupé (le ballon garde son volume, aux fuites près).
    """

    def _calcul_debit(self, dt, nouveau, maintenant):
        self.mesure = _num(self.dernier.get("volumetric_flow"))
        if self.en_pause:
            return 0.0
        return self.cible


# --------------------------------------------------------------------------
class _PI:
    """PI avec anti-emballement (intégration conditionnelle)."""

    def __init__(self, kp, ki, sortie_max):
        self.kp, self.ki, self.sortie_max = float(kp), float(ki), float(sortie_max)
        self.integrale = 0.0

    def __call__(self, erreur, dt, anticipation=0.0):
        sortie = anticipation + self.kp * erreur + self.integrale
        sature_haut = sortie >= self.sortie_max and erreur > 0
        sature_bas = sortie <= 0 and erreur < 0
        if not (sature_haut or sature_bas):
            self.integrale += self.ki * erreur * dt
            self.integrale = max(-self.sortie_max, min(self.integrale, self.sortie_max))
        return anticipation + self.kp * erreur + self.integrale


class PilotagePression(_Pilotage):
    """Consigne de pression atteinte en rampe (vitesse en unité/s), régulée par
    un PI qui commande le débit. Pause = la cible est gelée, la régulation
    continue (maintien en pression)."""

    def __init__(self, kp=5.0, ki=0.5, **kw):
        super().__init__(**kw)
        self._kp, self._ki = kp, ki

    def prepare(self):
        super().prepare()
        self.pi = _PI(self._kp, self._ki, self.debit_max)

    def _cible_initiale(self):
        return min(_num(self.dernier.get(self.label_pression)), self.consigne)

    def _calcul_debit(self, dt, nouveau, maintenant):
        self.mesure = _num(self.dernier.get(self.label_pression))
        if self.mesure is None:
            return 0.0
        return self.pi(self.cible - self.mesure, dt)


# --------------------------------------------------------------------------
class PilotageDeformation(_Pilotage):
    """Consigne de déformation (%) atteinte à vitesse imposée (%/s), pilotée en
    VITESSE de déformation.

    Pour une membrane gonflée, le débit fixe la vitesse de déformation :
    dε/dt ≈ Q / G, où G (mL/min par %/s) varie lentement au cours de l'essai.
    Un PI sur la position ε s'y prête mal : pendant le volume mort (cellule à
    remplir, membrane à tendre) ε ne bouge pas, l'intégrale grossit, le débit
    monte linéairement, puis la membrane réagit d'un coup et dépasse la cible.

    Ici, à chaque nouvelle mesure (fréquence des caméras) :
      1. droite des moindres carrés sur les mesures des `fenetre` dernières
         secondes -> ε filtrée et vitesse dε/dt (le bruit des taches est lissé) ;
      2. mise en tension : débit constant `debit_tension` jusqu'à ce que ε ait
         augmenté de `seuil_tension` ; la rampe part alors de la ε atteinte ;
      3. vitesse voulue r = vitesse de la rampe + (cible − ε) / tau ;
      4. débit Q = G × r, avec G réestimé en continu (volume injecté / Δε sur un
         horizon long, au moins 0,3 % de déformation, pour que le bruit des taches
         ne fasse pas varier G), donc adapté au raidissement de la membrane.
    Pause : cible gelée, r = (cible − ε)/tau maintient la déformation.
    Sans mesure pendant `timeout_mesure` s : débit coupé.
    """

    def __init__(self, debit_tension=13.2, seuil_tension=0.15, tau=8.0, fenetre=3.0,
                 timeout_mesure=5.0, **kw):
        super().__init__(**kw)
        self.debit_tension = float(debit_tension)
        self.seuil_tension = float(seuil_tension)
        self.tau = max(0.5, float(tau))
        self.fenetre = max(1.0, float(fenetre))
        self.timeout_mesure = float(timeout_mesure)
        self.labels = self.labels + ["eps", "eps_f", "vitesse_eps", "gain"]

    def prepare(self):
        super().prepare()
        from collections import deque
        self.mes = deque()              # (t, ε) mesurées, fenêtre courte (filtrage)
        self.mes_g = deque()            # (t, ε) mesurées, horizon long (gain)
        self.debits = deque()           # (t, Q appliqué), horizon long
        self.t_mesure = None
        self.debit_courant = 0.0
        self.en_tension = True
        self.t_tension = 0.0
        self.eps0 = None
        self.eps_f, self.vitesse_eps, self.G = None, 0.0, None

    # ---- profil : pas de rampe pendant la mise en tension
    def _avancer_cible(self, dt, maintenant):
        if self.en_tension:
            self.etat = TENSION
            return
        super()._avancer_cible(dt, maintenant)

    def _mesure_eps(self):
        return self.estimateur.calcule(self.dernier)

    def _pret(self, nouveau):
        if not any(l in nouveau for l in self.estimateur.labels):
            return False
        return self._mesure_eps() is not None

    def _cible_initiale(self):
        self.eps0 = self._mesure_eps()
        self.t_mesure = time.time()
        return min(self.eps0, self.consigne)

    # ---- estimation
    @property
    def horizon_gain(self):
        """Durée pour ~0,3 % de déformation à la vitesse demandée (bornée 2 fenêtres–60 s)."""
        return min(60.0, max(2 * self.fenetre, 0.3 / max(self.vitesse, 1e-3)))

    @staticmethod
    def _droite(points, maintenant, duree_min):
        """Moindres carrés sur [(t, ε)] : (ε au temps `maintenant`, pente) ;
        pente None si trop peu de points."""
        if len(points) < 3 or points[-1][0] - points[0][0] < duree_min:
            return (points[-1][1] if points else None), None
        n = len(points)
        tm = sum(t for t, _ in points) / n
        em = sum(e for _, e in points) / n
        stt = sum((t - tm) ** 2 for t, _ in points)
        pente = sum((t - tm) * (e - em) for t, e in points) / stt if stt > 0 else 0.0
        return em + pente * (maintenant - tm), pente

    def _ajuster(self, maintenant):
        """ε filtrée et dε/dt sur la fenêtre courte."""
        while self.mes and maintenant - self.mes[0][0] > self.fenetre:
            self.mes.popleft()
        return self._droite(list(self.mes), maintenant, 0.4 * self.fenetre)

    def _debit_moyen(self, maintenant, duree):
        pts = [q for t, q in self.debits if maintenant - t <= duree]
        return sum(pts) / len(pts) if pts else 0.0

    def _calcul_debit(self, dt, nouveau, maintenant):
        self.debits.append((maintenant, self.debit))
        if any(l in nouveau for l in self.estimateur.labels):
            eps = self._mesure_eps()
            if eps is not None:
                self.t_mesure = maintenant
                self.mesure = eps
                self.mes.append((maintenant, eps))
                self.mes_g.append((maintenant, eps))
                while self.mes_g and maintenant - self.mes_g[0][0] > self.horizon_gain:
                    self.mes_g.popleft()
                while self.debits and maintenant - self.debits[0][0] > self.horizon_gain:
                    self.debits.popleft()
                self.debit_courant = self._nouveau_debit(maintenant)
        if maintenant - self.t_mesure > self.timeout_mesure:
            if self.debit_courant > 0:
                self.log(30, "Plus de mesure de déformation : débit coupé")
            self.debit_courant = 0.0
        return self.debit_courant

    def _nouveau_debit(self, maintenant):
        eps_f, pente = self._ajuster(maintenant)
        self.eps_f = eps_f
        q_moy = self._debit_moyen(maintenant, self.fenetre)
        if pente is not None:
            self.vitesse_eps = pente

        if self.en_tension:
            if eps_f - self.eps0 >= self.seuil_tension:
                # la membrane se déforme : gain initial et début de la rampe à ε atteinte
                v = pente if pente and pente > 0 else self.seuil_tension / self.fenetre
                # au démarrage la pente est sous-estimée (ε vient juste de bouger) : le gain
                # est borné pour ne pas dépasser le débit de mise en tension à la vitesse visée
                self.G = min(max(q_moy, self.debit_tension) / v,
                             self.debit_tension / max(self.vitesse, 1e-3))
                self.en_tension = False
                self.cible = min(eps_f, self.consigne)
                self.etat = RAMPE
                self.mes_g.clear()           # le gain se réestime sur la membrane tendue
                self.mes_g.append((maintenant, eps_f))
                self.t_tension = maintenant
                self.log(20, f"Membrane en tension (ε = {eps_f:.3f} %) : début de la rampe, "
                             f"gain initial {self.G:.0f} mL/min par %/s")
            else:
                return self.debit_tension

        # juste après la mise en tension, la membrane continue sur sa lancée : la
        # rampe repart de la déformation atteinte plutôt que de l'attendre
        if (maintenant - self.t_tension < 3 * self.fenetre and eps_f > self.cible
                and not self.en_pause):
            self.cible = min(eps_f, self.consigne)

        # juste après la mise en tension : gain réajusté vite sur la fenêtre courte
        if (maintenant - self.t_tension < 3 * self.fenetre and pente is not None
                and pente > 0.5 * self.vitesse and q_moy > 0.5):
            g = min(max(q_moy / pente, self.G / 1.5), 1.5 * self.G)
            self.G += 0.4 * (g - self.G)
            return max(0.0, self.G * (self._vitesse_cible() + (self.cible - eps_f) / self.tau))

        # réestimation du gain sur l'horizon long, si la déformation y a assez avancé
        pts = list(self.mes_g)
        _, pente_g = self._droite(pts, maintenant, 0.5 * self.horizon_gain)
        duree_g = pts[-1][0] - pts[0][0] if pts else 0.0
        q_g = self._debit_moyen(maintenant, duree_g)
        if pente_g is not None and pente_g * duree_g > 0.1 and q_g > 0.5:
            g = min(max(q_g / pente_g, self.G / 1.5), 1.5 * self.G)
            self.G += 0.2 * (g - self.G)

        r = self._vitesse_cible() + (self.cible - eps_f) / self.tau
        return max(0.0, self.G * r)

    def _donnees_sup(self):
        nan = float("nan")
        return {"eps": nan if self.mesure is None else self.mesure,
                "eps_f": nan if self.eps_f is None else self.eps_f,
                "vitesse_eps": self.vitesse_eps,
                "gain": nan if self.G is None else self.G}


# --------------------------------------------------------------------------
# Retour des mesures vers l'interface
# --------------------------------------------------------------------------
class FluxInterface(crappy.blocks.Block):
    """Envoie en UDP (JSON) les dernières valeurs numériques reçues."""

    def __init__(self, port, estimateur=None, freq=10):
        super().__init__()
        self.port = int(port)
        self.freq = freq
        self.estimateur = estimateur

    def prepare(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.dernier = {}

    def loop(self):
        self.dernier.update(self.recv_last_data(fill_missing=False))
        paquet = {"t": time.time() - self.t0}
        for k, v in self.dernier.items():
            v = _num(v)
            if v is not None:
                paquet[k] = v
        if self.estimateur is not None and "eps" not in paquet:
            eps = self.estimateur.calcule(self.dernier)
            if eps is not None:
                paquet["eps"] = eps
        try:
            self.sock.sendto(json.dumps(paquet).encode(), ("127.0.0.1", self.port))
        except OSError:
            pass

    def finish(self):
        self.sock.close()
