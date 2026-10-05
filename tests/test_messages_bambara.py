import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "asr_test" / "scripts"))

from moteur import messages_bambara as msg  # noqa: E402

# Ces tests vérifient la structure (les bons nombres/mots apparaissent au bon
# endroit), pas la grammaire bambara elle-même : aucun test automatique ne
# peut garantir qu'une phrase est correcte ou naturelle pour une locutrice.
# Voir la réserve en tête de moteur/messages_bambara.py.


def test_confirmation_vente_contient_les_bons_nombres_et_larticle():
    message = msg.confirmation_vente({"article": "saga", "quantite": 3, "montant_fcfa": 250_000})
    assert "saga" in message
    assert "saba" in message  # 3, voir nombres_bambara
    assert "waa bi duuru" in message  # 250000 / 5 = 50000 dɔrɔmɛ
    assert message.endswith("wa?")


def test_confirmation_client_distingue_dette_et_paiement():
    dette = msg.confirmation_client({"client": "awa", "montant_fcfa": 10_000, "est_un_paiement": False})
    paiement = msg.confirmation_client({"client": "awa", "montant_fcfa": 10_000, "est_un_paiement": True})
    assert "juru" in dette and "juru" not in paiement
    assert dette != paiement


def test_reponse_capital_contient_jagokun_et_le_montant():
    assert "jagokun" in msg.reponse_capital(250_000)
    assert "waa bi duuru" in msg.reponse_capital(250_000)


def test_reponse_stock_signale_le_seuil_bas():
    normal = msg.reponse_stock("ɲɔ", 10, seuil_bas=False)
    bas = msg.reponse_stock("ɲɔ", 2, seuil_bas=True)
    assert "dɔgɔ" not in normal
    assert "dɔgɔ" in bas


def test_reformulation_1re_tentative_differente_de_la_2e():
    assert msg.reformulation(1) != msg.reformulation(2)
    # la 2e propose les vrais mots-clés reconnus par le moteur, pas leur
    # traduction française (voir dictionnaire_mots_cles.MOTS_CLES)
    assert "feere" in msg.reformulation(2)
