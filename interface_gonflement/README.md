# Interface de pilotage des essais de gonflement

```
python lancer_interface.py        # depuis la racine du dépôt
```

Dépendances : celles du dépôt (crappy, pymodbus 3.0.2 / 3.8.6 / 3.9.0, pyserial,
pyftdi, ximea, numpy, opencv) + `matplotlib` et `tkinter` (`sudo apt install python3-tk`).

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

**Sécurité** (dans le bloc crappy, donc active même si l'interface plante) :
pression max (coupure définitive), débit max, variation max du débit, durée max.
**Arrêter** = arrêt propre (débit à 0, fermeture des appareils) ;
**ARRÊT D'URGENCE** = débit à 0 et processus tué, puis consigne 0 renvoyée
directement à l'Alicat.

Données dans `<racine>/<date>/<échantillon>/Mesure[_0000N]/` : mêmes fichiers que
`alicat_flow_crappy_V3.py` (`data_ali.txt`, `data_ver.txt`, `data_vel.txt`,
images `video_extenso_left|right/`) + `data_stereo_3d.txt` (déformations 3D, uz, points 3D) + `data_pilotage_<mode>.txt` (cible,
consigne, mesure, commande, état) + `parametres_essai.json`.

## Onglet Calibration

1. **Réglage** : origine Z, aller à une hauteur (20 / 70 / 120 mm), aperçu des deux
   caméras avec réticule, test des caméras.
2. **Acquisition** : reprend `calib_crappy_V2.py` (plateau descendu plan par plan,
   déclenchement FT232R à l'arrivée). Images dans `<racine>/<date>/calib/`, avec
   `z_list.json`.
3. **Calcul** : `Pycaso.calibration_class.Calibration` (Lagrange / Soloff /
   Zernike), dossier pré-rempli après l'acquisition. Les hauteurs sont relues
   dans `z_list.json`.

## Onglet Matériel

Ports, numéros de série, expositions, URL du FT232R, dossier racine, ports UDP.
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
