import sys
from pathlib import Path

# montants.py vit dans asr_test/scripts (pas encore un package pip-installable) ;
# on l'ajoute au chemin d'import dès que `moteur` est chargé, pour que les
# modules de ce package puissent faire `from montants import ...` directement.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "asr_test" / "scripts"))
