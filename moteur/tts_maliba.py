"""Intégration TTS (Architecture_Technique_NGONI_NANA.docx, section 3.4).

Modèle envisagé : MALIBA-AI/MalianTTS (Space Gradio hébergé sur Hugging
Face). Latence mesurée en amont (hors de ce module) : ~2,25 à 4,03 s par
phrase, donc un vrai risque sur le budget de moins de 5 s (section 6 de
l'architecture) une fois la latence réseau/téléphonie ajoutée.

Licence CC-BY-NC-4.0 : usage recherche/test couvert, usage production non
confirmé à ce jour (risque R4, relancé auprès d'Isaak sans réponse). Ne pas
basculer ce module en production sans confirmation écrite de CFA/MALIBA-AI.

Nécessite `gradio_client` et un jeton Hugging Face (variable d'environnement
HF_TOKEN) : jamais codé en dur ici.
"""
import os
from typing import Callable

ESPACE_PAR_DEFAUT = "MALIBA-AI/MalianTTS"


def obtenir_synthetiseur(espace: str = ESPACE_PAR_DEFAUT) -> Callable[[str], str]:
    """Connecte le Space Gradio et renvoie syntheser(texte) -> chemin_audio.

    Connexion paresseuse (le `Client` ouvre une session réseau dès sa
    création) : à ne faire qu'une fois par processus, pas à chaque appel.
    """
    from gradio_client import Client

    client = Client(espace, token=os.environ.get("HF_TOKEN"))

    def syntheser(texte: str) -> str:
        chemin_audio, _statut = client.predict(language="bambara", text=texte, api_name="/generate_audio")
        return chemin_audio

    return syntheser
