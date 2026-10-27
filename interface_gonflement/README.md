# Interface de pilotage des essais de gonflement

```
python lancer_interface.py        # depuis la racine du dépôt
```

Dépendances : celles du dépôt (crappy, pymodbus 3.0.2 / 3.8.6 / 3.9.0, pyserial,
pyftdi, ximea, numpy, opencv) + `matplotlib` et `tkinter` (`sudo apt install python3-tk`).

Ordre des onglets : Calibration, Essai, Matériel.

## Onglet Essai

Trois modes de pilotage, tous commandent le débit de l'Alicat :

| Mode | Consigne | Régulation | Pause |
|---|---|---|---|
| **Débit** | mL/min, rampe en s, attente, palier | boucle ouverte | débit coupé |
| **Pression** | valeur + vitesse de montée (/s), palier | PI → débit | maintien en pression |
| **Déformation** | % visé + vitesse (%/s), palier | PI (+ anticipation) → débit | maintien en déformation |

La déformation est mesurée par **stéréo-corrélation 3D** (par défaut, modèle
**Zernike** de Pycaso, ou Lagrange), ou en 2D par le VideoExtenso :

1. les deux VideoExtenso suivent les taches (jusqu'à 4) sur chaque caméra ;
2. les images gauche/droite d'une même impulsion FT232R sont associées ;
3. à la première image, les taches de droite (tournées de 180°, caméras en
   miroir) sont appariées à celles de gauche (algorithme hongrois) ;
4. chaque paire est reconstruite en 3D par
   `pcs.Zernike_identification(gauche, droite, A_Zernike, degré, taille caméras)` ;
5. la déformation est l'allongement des distances 3D entre taches :
   `exx` / `eyy` (taches extrêmes selon X / Y de la mire), `moyenne`, `max`,
   `toutes` (moyenne de toutes les paires, adaptée au gonflement équibiaxial).
   Le déplacement hors plan moyen `uz` est aussi enregistré.

Le fichier de constantes est `<date>/results_calib/nZ_<degré>/A_Zernike.npy`
(degré lu dans le nom du dossier). Il est rempli automatiquement après un calcul
de calibration Zernike, ou via « Prendre la dernière calibration ». Si la
déformation n'arrive plus (taches perdues), le débit est coupé après le délai
« Coupure sans mesure ».

Code : `stereo_3d.py` (bloc `StereoDeformation`). `PolyZernike.py` et
`tridicalddef.py` ne sont plus utilisés.

**Pendant l'essai** : nouvelle consigne, nouvelle vitesse, pause/reprise,
« Terminer le profil », courbes et valeurs en direct.

**Après l'essai** : « Relancer le même essai » refait un essai avec exactement
les mêmes paramètres, dans un nouveau dossier `Mesure_0000N`.

**Sécurité** (dans le bloc crappy, donc active même si l'interface plante) :
pression max (coupure définitive), débit max, variation max du débit, durée max.
**Arrêter** = arrêt propre (débit à 0, fermeture des appareils) ;
**ARRÊT D'URGENCE** = débit à 0 et processus tué, puis consigne 0 renvoyée
directement à l'Alicat.

Données dans `<dossier de l'essai>/Mesure[_0000N]/`. Le dossier de l'essai se choisit
en parcourant le PC (bouton « … » de l'onglet Essai) ; laissé vide, c'est
`<racine>/<date>/<échantillon>`. Mêmes fichiers que
`alicat_flow_crappy_V3.py` (`data_ali.txt`, `data_ver.txt`, `data_vel.txt`,
images `video_extenso_left|right/`) + `data_stereo_3d.txt` (déformations 3D, uz, points 3D) + `data_pilotage_<mode>.txt` (cible,
consigne, mesure, commande, état) + `parametres_essai.json`.

## Onglet Calibration

Mêmes paramètres et valeurs par défaut que les programmes du dépôt :

1. **Réglage** (`reglage_hauteur_*.py`) : réglage initial (origine, aperçu des
   caméras, puis Z = 20 et 120 mm), début d'essai (Z = 70), réinitialiser
   (Z = 120), origine seule, aperçu seul, test des caméras, aller à un Z.
2. **Essai et plans z** : dossier racine (choisi en parcourant le PC), date
   (aujourd'hui), nom de l'essai (`Mvt_Rigide` comme `calib_crappy_V2`). Les images
   vont dans `<racine>/<date>/<nom>/Mesure` (puis `Mesure_00001`… s'il est déjà
   rempli), avec `video_extenso_left/` et `video_extenso_right/`. Plans donnés par
   **Z départ, Z fin (incluse) et pas** : 70 → 32 par 2 = 20 plans, comme avant.
   « Images pour le calcul » suit ce dossier (modifiable pour un ancien essai) ;
   résultats dans `<racine>/<date>/<nom>/results_calib`.
3. **Acquisition** (`calib_crappy_V2.py`) : expositions 28757 µs (gauche) et
   41389 µs (droite), 1 + pas/0,6 s par plan, **graphe de la hauteur du plateau**
   (Grapher crappy, option). La mémoire USB des caméras est vérifiée avant le
   lancement (mot de passe sudo demandé si besoin, sans quoi les caméras ne
   renvoient aucune image) et le nombre d'images enregistrées est affiché à la
   fin. Document `hauteurs_calibration.txt` (et `.csv`) écrit à chaque
   acquisition ; bouton pour le générer sans acquisition. En simulation, des
   images de synthèse de la mire ChArUco sont créées (calculables par Pycaso).
4. **Méthode** (`Pycaso/calibration_gui.py`) : Lagrange degré 4 / 10 itérations,
   Soloff 332 / 8, Zernike ordre 6 / 9 ; changer de méthode remet ces valeurs.
   Options metadata et nuage 3D, mire 12 × 12 carrés de 7,5 mm. Un résultat
   Zernike ou Lagrange est repris automatiquement pour le pilotage 3D.

## Caméras : une seule répond

Avant chaque essai ou acquisition réels, l'interface vérifie la mémoire USB,
cherche les processus restés ouverts (essai, aperçu, xiCamTool) qui gardent une
caméra, propose de les arrêter, puis ouvre chaque caméra et lit une image dans un
processus séparé coupé au bout de 20 s. Si une caméra ne répond pas, elle est
nommée et l'essai n'est pas lancé (sauf choix contraire). Toutes les lectures
d'image ont un délai d'attente borné, l'aperçu reste fermable si une caméra ne
répond pas, et le bouton « Libérer les caméras » (onglet Matériel) remplace le
pkill. Si une caméra reste bloquée malgré tout : la débrancher et la rebrancher.

## Onglet Matériel

Ports, numéros de série, expositions, URL du FT232R, dossier racine, ports UDP.
Les programmes sont lancés avec le Python qui a ouvert l'interface.
Outils : détection des ports, libération de la mémoire USB des caméras (sudo),
débit à 0. **Mode simulation** : ballon simulé vu par deux caméras virtuelles avec un étalonnage Zernike synthétique (toute la chaîne 3D tourne), aucun matériel — pour prendre
l'interface en main et dégrossir les gains.

## À vérifier au premier essai réel

- **Pleine échelle** : la commande envoyée est `débit / pleine_échelle`, comme
  dans `alicat_flow_crappy_V3.py` (13.2/1000). Vérifier que l'Alicat affiche bien
  le débit demandé.
- **Gains PI** (pression, déformation) : réglés sur le ballon simulé seulement.
  Commencer avec une vitesse lente et un Ki faible.
- **Unité de pression** : celle configurée sur le débitmètre (absolue par défaut).
- **Stéréo 3D** : au démarrage, la console affiche l'appariement gauche→droite et
  les points 3D initiaux (dispersion en z attendue faible, l'échantillon est plat).
  Sélectionner les mêmes taches sur les deux caméras dans les fenêtres VideoExtenso.
  Si l'appariement est signalé douteux, vérifier l'option « Caméra droite en miroir ».

## Fichiers

```
lancer_interface.py              point d'entrée
interface_gonflement/
  app.py                 fenêtre principale, console, sous-processus, arrêts
  onglet_essai.py        onglet Essai (paramètres, pilotage en direct)
  onglet_calibration.py  onglet Calibration
  onglet_materiel.py     onglet Matériel (ports, thème, outils)
  courbes.py             courbes en direct
  widgets.py             formulaire lié aux réglages, colonne défilante, info-bulles
  theme.py               thèmes sombre (Nord) et clair (sable)
  lancer_essai.py        construit le graphe crappy de l'essai (utilisable seul)
  blocs_pilotage.py      contrôleurs débit / pression / déformation, flux UDP
  stereo_3d.py           stéréo-corrélation 3D Zernike/Lagrange temps réel
  simulation.py          débitmètre, ballon et banc stéréo simulés
  lancer_calibration.py  acquisition + calcul de calibration
  outils_machine.py      origine, aller à Z, aperçu, test caméras, débit à 0, ports
  reglages.py            valeurs par défaut, reglages_utilisateur.json
```

Thème : onglet Matériel → « Thème » (sombre ou clair), appliqué immédiatement.
