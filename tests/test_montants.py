import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "asr_test" / "scripts"))

from montants import extraire_nombres, nombre_principal, normaliser  # noqa: E402


@pytest.mark.parametrize("texte, attendu", [
    ("Mariam ka jɛnɛ ye 2500 francs", [2500]),
    ("2 500 FCFA", [2500]),
    ("kɛmɛ duuru", [500]),
    ("waa fila ni kɛmɛ duuru", [2500]),
    ("waa tan ni duuru", [15000]),
    ("kɛmɛ fila ni bi duuru", [250]),
    ("kɛmɛ bi saba ni naani", [3400]),
    ("waa bi duuru ni kɛmɛ duuru", [50500]),
    ("waa bi duuru", [50000]),
    ("waa kɛmɛ fila", [200000]),
    ("dɔrɔmɛ waa saba", [3000]),
    ("bi saba ni seegin", [38]),
    ("mugan", [20]),
])
def test_nombres(texte, attendu):
    assert extraire_nombres(texte) == attendu


def test_graphies_francisees():
    # Exemple du cahier des charges : 3 moutons vendus 50 000 dɔrɔmɛ (250 000 FCFA)
    phrase = "Saga dourou fereli be bin wa bi dourou ma, i son na wah"
    assert extraire_nombres(phrase) == [5, 50000]
    assert nombre_principal(phrase) == 50000


def test_mots_courants_ne_sont_pas_des_nombres():
    # "wa" (question), "bi" (aujourd'hui), "ba" seuls ne valent rien
    assert extraire_nombres("i son na wa") == []
    assert extraire_nombres("n ye fereli kɛ bi") == []
    assert extraire_nombres("a ba ye") == []


def test_variante_dou():
    # "dou" : troncature de dourou/duuru observée en sortie ASR (RobotsMali)
    assert extraire_nombres("wa bi dou") == [50000]


def test_mots_colles():
    # Sans pause audible, l'ASR peut fusionner deux mots numéraux en un seul
    # token (observé : FarmRadioInternational/bambara-whisper-asr a
    # transcrit "wa bi" en "biwa" dans "wa bi dourou").
    assert extraire_nombres("biwa bi duuru") == [50000]
    assert extraire_nombres("kemebi saba") == [3000]  # "kɛmɛ" + "bi saba" collés


def test_pronom_ne_colle_a_un_numeral():
    # "nɛkɛmɛ duuru" pour "ne kɛmɛ duuru" (500) : observé deux fois en test
    # réel, pipeline complet ASR + moteur (RobotsMali, 2026-10-06), même
    # locutrice, phrases différentes.
    assert extraire_nombres("nɛkɛmɛ duuru bɛ mariama na") == [500]
    assert extraire_nombres("nɛkɛmɛ wolonwula jurumu") == [700]
    # Un mot qui commence juste par "ne" sans rapport ne doit rien casser.
    assert extraire_nombres("nebɛ taa") == []


def test_normaliser():
    assert normaliser("Kɛmɛ DUURU, ɲɔgɔn!") == "keme duuru nyogon"
