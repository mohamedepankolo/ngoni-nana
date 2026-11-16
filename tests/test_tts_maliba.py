"""Tests de syntheser_par_phrases (tts_maliba.py) : decoupage + recollage
avec silence, sans dependre du reseau (le "syntheser" injecte est un faux
qui ecrit un petit wav silencieux, pas un vrai appel au Space distant)."""
import wave

import pytest

from moteur.tts_maliba import _decouper_phrases, syntheser_par_phrases


def _ecrire_wav(chemin, duree_s: float, framerate=16000, sampwidth=2, nchannels=1):
    with wave.open(str(chemin), "wb") as w:
        w.setnchannels(nchannels)
        w.setsampwidth(sampwidth)
        w.setframerate(framerate)
        w.writeframes(b"\x00" * int(framerate * sampwidth * nchannels * duree_s))


def test_decouper_phrases_une_seule_phrase_reste_seule():
    assert _decouper_phrases("I ni ce, aw bisimila.") == ["I ni ce, aw bisimila."]


def test_decouper_phrases_plusieurs_phrases():
    texte = "I ni ce. Fila sara."
    assert _decouper_phrases(texte) == ["I ni ce.", "Fila sara."]


def test_decouper_phrases_coupe_aussi_sur_le_deux_points():
    # "Kelen : feere." (menu_principal, messages_bambara.py) doit devenir 2
    # phrases pour la synthese (voir docstring) - le texte affiche a l'ecran,
    # lui, garde le ":" (voir ajouterAuFil, web/index.html), inchange ici.
    texte = "Kelen : feere. Fila : sara."
    assert _decouper_phrases(texte) == ["Kelen.", "feere.", "Fila.", "sara."]


def test_syntheser_par_phrases_une_seule_phrase_appelle_syntheser_une_fois(tmp_path):
    chemin_unique = tmp_path / "unique.wav"
    _ecrire_wav(chemin_unique, 1.0)
    appels = []

    def faux_syntheser(texte):
        appels.append(texte)
        return str(chemin_unique)

    resultat = syntheser_par_phrases(faux_syntheser, "Une seule phrase.")

    assert appels == ["Une seule phrase."]
    assert resultat == str(chemin_unique)  # aucun recollage, le chemin d'origine est renvoye tel quel


def test_syntheser_par_phrases_plusieurs_phrases_recolle_avec_silence(tmp_path):
    def faux_syntheser(texte):
        chemin = tmp_path / f"{hash(texte)}.wav"
        _ecrire_wav(chemin, 1.0)
        return str(chemin)

    texte = "I ni ce. Fila sara. Saba jagokun."
    chemin_sortie = syntheser_par_phrases(faux_syntheser, texte, pause_ms=500)

    with wave.open(chemin_sortie, "rb") as w:
        duree = w.getnframes() / w.getframerate()

    # 3 phrases d'1s + 2 pauses de 0.5s entre elles = 4s
    assert duree == pytest.approx(4.0, abs=0.01)


def test_syntheser_par_phrases_sans_phrase_appelle_quand_meme_syntheser(tmp_path):
    # Un texte vide/sans point final reste une "seule phrase" (voir
    # _decouper_phrases) : ne doit jamais planter plutot que de ne rien
    # synthetiser du tout.
    chemin_unique = tmp_path / "vide.wav"
    _ecrire_wav(chemin_unique, 0.5)
    resultat = syntheser_par_phrases(lambda t: str(chemin_unique), "Sans point final")
    assert resultat == str(chemin_unique)
