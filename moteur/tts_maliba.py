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

import numpy as np
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

    " : " (menu_principal, messages_bambara.py : "Kelen : feere.") est
    d'abord traité comme une frontière lui aussi - le modèle distant ne
    marque quasiment aucune pause sur un simple ":" (constaté en test réel,
    2026-11-16 : "un vente, deux achat, trois capital" dit d'une traite,
    sans qu'on ait le temps de suivre). Uniquement pour la synthèse : le
    texte affiché à l'écran (voir ajouterAuFil, web/index.html) garde lui le
    ":" d'origine, pour rester "Kelen : feere." sur une seule ligne visible.

    Une seule "phrase" renvoyée si `texte` n'en contient qu'une (cas normal,
    la grande majorité des messages) - `syntheser_par_phrases` ci-dessous ne
    paie alors aucun coût supplémentaire (voir son docstring).
    """
    texte_normalise = texte.replace(" : ", ". ")
    return [m for m in re.split(r"(?<=\.)\s+", texte_normalise.strip()) if m]


def _fondu(echantillons: np.ndarray, n: int, sens: str) -> np.ndarray:
    """Applique un fondu lineaire sur les `n` premiers ("entree") ou derniers
    ("sortie") echantillons - evite le "clic" d'un raccord brut entre deux
    fragments synthetises separement (constate en test reel, 2026-11-16 :
    "il n'y a pas de fondu, c'est bizarre" sur les raccords phrase par
    phrase). N'arrange pas l'intonation de chaque fragment (toujours celle
    d'une phrase isolee), seulement la coupure elle-meme.
    """
    n = min(n, len(echantillons))
    if n == 0:
        return echantillons
    rampe = np.linspace(0.0, 1.0, n, dtype=np.float32)
    echantillons = echantillons.astype(np.float32)
    if sens == "entree":
        echantillons[:n] *= rampe
    else:
        echantillons[-n:] *= rampe[::-1]
    return echantillons


def syntheser_par_phrases(
    syntheser: Callable[[str], str], texte: str, pause_ms: int = 700, fondu_ms: int = 25
) -> str:
    """Synthétise `texte` phrase par phrase (en parallèle) et recolle les
    audios avec un vrai silence (+ un fondu sur chaque raccord) entre chaque.

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

    `pause_ms` : 450ms (défaut initial, choisi au jugé) -> 2000ms
    (2026-11-17, calé sur le rythme mesuré des 5 enregistrements humains du
    script à 9 phrases COMPLÈTES, "appuyez sur 1 pour enregistrer une
    vente...", 2,2s médian entre deux énumérations) -> 700ms (2026-11-17,
    même jour, suite au retour "on a l'impression que ça dure" en test
    téléphone réel sur le menu effectivement annoncé par l'app). Les deux
    textes ne se ressemblent pas : le menu vocal réel (menu_principal(),
    messages_bambara.py) n'énonce QUE des paires chiffre-mot-clé courtes
    ("Kelen : feere"), pas les phrases complètes du script mesuré - la pause
    2,2s mesurée sur de longues phrases devient disproportionnée une fois
    appliquée à 8 raccords entre segments de 1-2 mots (9 phrases dans
    "I ni ce... Kelen : feere. Fila : sara. Saba : jagokun. Kononton :
    bolo.", chaque ":" comptant comme une frontière - voir
    `_decouper_phrases`), d'où ~16s de silence pur ajoutés à un message de
    quelques secondes de parole. 700ms est un compromis au jugé (pas
    remesuré sur ce texte court précisément) : assez pour ne pas reproduire
    le bug du 450ms ("ça part tellement vite, on n'arrive pas à suivre" sur
    les anciennes énumérations), sans réintroduire la lenteur du 2000ms -
    à reconfirmer au prochain retour d'écoute.

    `fondu_ms` suppose du mono 16 bits (nchannels=1, sampwidth=2) : format
    constaté sur chaque appel réel à ce Space à ce jour. Si ça changeait un
    jour, le fondu serait silencieusement ignoré (voir le `if` plus bas),
    pas une erreur - un raccord un peu plus sec plutôt qu'un plantage.
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
    n_fondu = parametres.framerate * fondu_ms // 1000
    mono_16bits = parametres.nchannels == 1 and parametres.sampwidth == 2

    chemin_sortie = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    with wave.open(chemin_sortie, "wb") as sortie:
        sortie.setparams(parametres)
        for i, chemin in enumerate(chemins):
            with wave.open(chemin, "rb") as entree:
                trame = entree.readframes(entree.getnframes())
            if mono_16bits:
                echantillons = np.frombuffer(trame, dtype=np.int16).copy()
                if i > 0:
                    echantillons = _fondu(echantillons, n_fondu, "entree")
                if i < len(chemins) - 1:
                    echantillons = _fondu(echantillons, n_fondu, "sortie")
                trame = echantillons.astype(np.int16).tobytes()
            sortie.writeframes(trame)
            if i < len(chemins) - 1:
                sortie.writeframes(silence)
    return chemin_sortie
