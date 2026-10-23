"""Paramètres de CoordCam.py : c'est le seul fichier à modifier d'un essai à l'autre."""

# --- Essai à traiter -------------------------------------------------------
date = "2026_04_13"
sample = "gonflement"
mesure = "mesure"           # sous-dossier qui contient video_extenso_left et video_extenso_right

# --- Reprise ---------------------------------------------------------------
# False : détecte et suit les taches (long). True : relit les résultats déjà enregistrés.
gauche_calculated = False
droite_calculated = False

# --- Détection et suivi des taches -----------------------------------------
pix = 20                        # marge (px) autour d'une tache pour la retrouver à l'image suivante
                                # (doit rester inférieure à la moitié de l'écart entre taches)
taille_min_pix = 100            # aire minimale d'une tache (px)
taille_max_pix = 1000           # aire maximale d'une tache (px)
max_images_a_considerer = 82    # nombre d'images traitées + 1
w_spots = False                 # True si les taches sont blanches sur fond sombre
figures_suivi = True            # enregistre une figure .svg par image (lent) dans ROI_left / ROI_right

# --- Appariement des deux caméras ------------------------------------------
l_pform = 4                     # degré de l'étalonnage Lagrange (Results_Calib/Lpform_<l_pform>)
rayon_recherche = 150.0         # rayon (px) où chercher la tache correspondante sur l'autre caméra
tolerance_plan = 1.0            # écart maximal (mm) au plan de l'échantillon pour accepter une paire

# --- Affichage --------------------------------------------------------------
afficher_figures = True         # ouvre la figure de vérification de l'appariement à la fin
