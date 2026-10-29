"""Lance l'interface de pilotage des essais de gonflement.

    python lancer_interface.py

En cas de plantage brutal (« Segmentation fault »), la pile Python au moment du
crash est écrite dans interface_gonflement/plantages.log ; elle est affichée dans
la console de l'interface au lancement suivant.
"""
import faulthandler
from pathlib import Path

JOURNAL = Path(__file__).resolve().parent / "interface_gonflement" / "plantages.log"

if __name__ == "__main__":
    precedent = JOURNAL.read_text(errors="ignore").strip() if JOURNAL.exists() else ""
    journal = open(JOURNAL, "w", buffering=1)
    faulthandler.enable(file=journal, all_threads=True)
    from interface_gonflement.app import main
    main(plantage_precedent=precedent)
