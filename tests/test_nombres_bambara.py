import csv
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "asr_test" / "scripts"))

from montants import extraire_nombres  # noqa: E402
from moteur.nombres_bambara import nombre_en_bambara  # noqa: E402


@pytest.mark.parametrize("n, attendu", [
    (3, "saba"),
    (15, "tan ni duuru"),
    (20, "mugan"),
    (34, "bi saba ni naani"),
    (50, "bi duuru"),
    (100, "kɛmɛ"),
    (250, "kɛmɛ fila ni bi duuru"),
    (500, "kɛmɛ duuru"),
    (1000, "waa kelen"),
    (2500, "waa fila ni kɛmɛ duuru"),
    (15000, "waa tan ni duuru"),
    (50000, "waa bi duuru"),
])
def test_valeurs_connues(n, attendu):
    assert nombre_en_bambara(n) == attendu


@pytest.mark.parametrize("n", [1, 5, 9, 10, 11, 19, 21, 30, 45, 60, 99, 100, 101,
                                199, 300, 999, 1000, 1001, 1500, 3400, 10000,
                                12500, 25000, 125000, 250000 // 5, 999000])
def test_aller_retour_avec_le_parseur(n):
    """Ce que nombre_en_bambara() écrit doit se reparser à la même valeur avec
    extraire_nombres() (montants.py) : la garantie la plus solide qu'on puisse
    avoir sans personne bambaraphone sous la main, puisque les deux fonctions
    partagent exactement la même grammaire.
    """
    assert extraire_nombres(nombre_en_bambara(n)) == [n]


def test_aller_retour_sur_les_montants_reels_du_corpus():
    chemin = RACINE / "asr_test" / "corpus" / "phrases_reelles.csv"
    with open(chemin, encoding="utf-8") as f:
        montants = [int(l["montant_fcfa"]) // 5 for l in csv.DictReader(f) if l["montant_fcfa"]]
    assert montants, "le corpus ne devrait pas être vide"
    for dorome in set(montants):
        assert extraire_nombres(nombre_en_bambara(dorome)) == [dorome]
