"""Lecture / écriture d'images OpenCV avec des chemins accentués sous Windows.

Sous Windows, cv2.imread et cv2.imwrite ne savent pas ouvrir un chemin non ASCII
(ex. « Données ») : imread renvoie None (« can't open/read file ») et imwrite
échoue sans rien dire. On passe par numpy (np.fromfile / tofile), qui gère
l'Unicode, et cv2.imdecode / imencode.

    import compat_cv2; compat_cv2.installer()
remplace cv2.imread / cv2.imwrite pour tout le processus (y compris dans Pycaso).
Sans effet hors Windows.
"""

import os

import cv2
import numpy as np

_imread, _imwrite = cv2.imread, cv2.imwrite


def imread(chemin, flags=cv2.IMREAD_COLOR):
    try:
        data = np.fromfile(str(chemin), dtype=np.uint8)
    except OSError:
        return None
    return cv2.imdecode(data, flags) if data.size else None


def imwrite(chemin, img, params=None):
    ext = os.path.splitext(str(chemin))[1] or ".png"
    ok, buf = cv2.imencode(ext, img, list(params or []))
    if ok:
        buf.tofile(str(chemin))
    return ok


def installer(forcer=False):
    if os.name == "nt" or forcer:
        cv2.imread, cv2.imwrite = imread, imwrite
