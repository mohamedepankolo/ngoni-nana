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
import re
import tempfile
import wave
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from dotenv import load_dotenv

load_dotenv()  # lit HF_TOKEN depuis .env si ce module est utilisé hors de api.py

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


def _decouper_phrases(texte: str) -> list[str]:
    """Découpe sur les frontières de phrase (point suivi d'espace).

    Une seule "phrase" renvoyée si `texte` n'en contient qu'une (cas normal,
    la grande majorité des messages) - `syntheser_par_phrases` ci-dessous ne
    paie alors aucun coût supplémentaire (voir son docstring).
    """
    return [m for m in re.split(r"(?<=\.)\s+", texte.strip()) if m]


def syntheser_par_phrases(syntheser: Callable[[str], str], texte: str, pause_ms: int = 450) -> str:
    """Synthétise `texte` phrase par phrase (en parallèle) et recolle les
    audios avec un vrai silence entre chaque.

    Nécessaire pour les messages à plusieurs phrases (le menu principal à 6
    choix notamment) : le modèle distant ne ralentit pas assez tout seul
    entre des phrases collées dans un seul appel - constaté en test réel sur
    téléphone (2026-11-16, "ça part tellement vite, on n'arrive pas à
    suivre"). Un seul appel à `syntheser` (donc AUCUN coût de latence
    ajouté) si `texte` ne contient qu'une seule phrase, ce qui est le cas de
    la grande majorité des messages (toutes les confirmations, par
    exemple) : seuls les messages à plusieurs phrases paient le coût de
    plusieurs appels distants (en parallèle, pas en série, pour limiter ce
    coût - voir ThreadPoolExecutor ci-dessous).
    """
    phrases = _decouper_phrases(texte)
    if len(phrases) <= 1:
        return syntheser(texte)

    with ThreadPoolExecutor(max_workers=len(phrases)) as executeur:
        chemins = list(executeur.map(syntheser, phrases))

    with wave.open(chemins[0], "rb") as premier:
        parametres = premier.getparams()
    octets_par_ms = parametres.framerate * parametres.sampwidth * parametres.nchannels // 1000
    silence = b"\x00" * (octets_par_ms * pause_ms)

    chemin_sortie = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    with wave.open(chemin_sortie, "wb") as sortie:
        sortie.setparams(parametres)
        for i, chemin in enumerate(chemins):
            with wave.open(chemin, "rb") as entree:
                sortie.writeframes(entree.readframes(entree.getnframes()))
            if i < len(chemins) - 1:
                sortie.writeframes(silence)
    return chemin_sortie
