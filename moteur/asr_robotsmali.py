"""Intégration ASR (Architecture_Technique_NGONI_NANA.docx, section 3.2).

Modèle retenu : RobotsMali/soloni-114m-tdt-ctc-v3 (backend NVIDIA NeMo),
~0,3 s par phrase mesuré sur CPU, 69% de montants exacts sur le corpus réel
vérifié (voir COMPARAISON_MODELES.md). Réutilise directement le chargement
déjà écrit et testé dans asr_test/scripts/transcrire.py plutôt que de le
dupliquer.

Dépendance lourde et volontairement optionnelle : `nemo-toolkit[asr]` n'est
pas dans requirements.txt par défaut (voir ce fichier). Rien dans ce module
ne l'importe tant que `obtenir_transcripteur()` n'est pas appelé, pour que le
reste du moteur (agent_vocal, api) reste testable sans cette installation.
"""
import sys
from pathlib import Path
from typing import Callable

_SCRIPTS = Path(__file__).resolve().parent.parent / "asr_test" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

MODELE_PAR_DEFAUT = "RobotsMali/soloni-114m-tdt-ctc-v3"


def obtenir_transcripteur(modele: str = MODELE_PAR_DEFAUT) -> Callable[[str], str]:
    """Charge le pipeline NeMo et renvoie transcrire(chemin_audio) -> texte.

    Chargement paresseux et unique : le modèle met plusieurs secondes à
    charger, à ne faire qu'une fois par processus (ex. au démarrage de
    l'API Gateway), pas à chaque appel.
    """
    from transcrire import charger_pipeline_nemo  # noqa: E402

    return charger_pipeline_nemo(modele)
