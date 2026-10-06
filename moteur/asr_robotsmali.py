"""Intégration ASR (Architecture_Technique_NGONI_NANA.docx, section 3.2).

Modèle retenu : RobotsMali/soloni-be-kalan-v0 (backend NVIDIA NeMo, même
famille et même licence CC-BY-4.0 que soloni-114m-tdt-ctc-v3, publié par
RobotsMali début octobre 2026). ~0,3 s par phrase sur CPU. Testé en direct
sur le pipeline complet (ASR + moteur) du projet le 2026-10-06 contre
soloni-114m-tdt-ctc-v3 : 82 % d'intention correcte et 76 % de montant exact
sur les 60 phrases réelles vérifiées, contre 78 %/71 % pour v3 (voir
asr_test/results/pipeline_complet_bekalan.md). Réutilise directement le
chargement déjà écrit et testé dans asr_test/scripts/transcrire.py plutôt
que de le dupliquer.

Dépendance lourde et volontairement optionnelle : `nemo-toolkit[asr]` n'est
pas dans requirements.txt par défaut (voir ce fichier). Rien dans ce module
ne l'importe tant que `obtenir_transcripteur()` n'est pas appelé, pour que le
reste du moteur (agent_vocal, api) reste testable sans cette installation.
"""
import subprocess
import sys
from pathlib import Path
from typing import Callable

_SCRIPTS = Path(__file__).resolve().parent.parent / "asr_test" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

MODELE_PAR_DEFAUT = "RobotsMali/soloni-be-kalan-v0"


def convertir_en_wav(chemin_entree: str, chemin_sortie: str) -> str:
    """Convertit n'importe quel format audio (ex. webm/opus d'un enregistrement
    navigateur) en WAV 16 kHz mono, le format attendu par le modèle. Nécessite
    ffmpeg sur le PATH.
    """
    subprocess.run(
        ["ffmpeg", "-y", "-i", chemin_entree, "-ar", "16000", "-ac", "1", chemin_sortie],
        check=True, capture_output=True,
    )
    return chemin_sortie


def obtenir_transcripteur(modele: str = MODELE_PAR_DEFAUT) -> Callable[[str], str]:
    """Charge le pipeline NeMo et renvoie transcrire(chemin_audio) -> texte.

    Chargement paresseux et unique : le modèle met plusieurs secondes à
    charger, à ne faire qu'une fois par processus (ex. au démarrage de
    l'API Gateway), pas à chaque appel.
    """
    from transcrire import charger_pipeline_nemo  # noqa: E402

    return charger_pipeline_nemo(modele)
