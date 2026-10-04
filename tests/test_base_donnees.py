import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from moteur import base_donnees as db  # noqa: E402


@pytest.fixture
def bd():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = db.get_session_factory(engine)
    session = SessionLocal()
    coop = db.Cooperative(nom="ABIC Dioïla")
    session.add(coop)
    session.commit()
    u = db.Utilisatrice(code_anonyme="L01", telephone_hash="x", cooperative_id=coop.id)
    session.add(u)
    session.commit()
    session.refresh(u)
    session.utilisatrice_id = u.id  # commodité de test
    return session


def test_enregistrer_vente_puis_depense_calcule_le_capital(bd):
    db.enregistrer_transaction(bd, utilisatrice_id=bd.utilisatrice_id, type_="vente",
                                champs={"article": "mouton", "quantite": 3, "montant_fcfa": 250_000,
                                        "unite_dite": "dorome"})
    db.enregistrer_transaction(bd, utilisatrice_id=bd.utilisatrice_id, type_="depense",
                                champs={"article": "transport", "montant_fcfa": 750, "unite_dite": "dorome"})

    assert db.calculer_capital(bd, bd.utilisatrice_id) == 250_000 - 750


def test_vente_diminue_le_stock_et_depense_l_augmente(bd):
    db.enregistrer_transaction(bd, utilisatrice_id=bd.utilisatrice_id, type_="depense",
                                champs={"article": "mil", "quantite": 5, "montant_fcfa": 25_000})
    assert db.consulter_stock(bd, bd.utilisatrice_id, "mil").quantite_actuelle == 5

    db.enregistrer_transaction(bd, utilisatrice_id=bd.utilisatrice_id, type_="vente",
                                champs={"article": "mil", "quantite": 2, "montant_fcfa": 10_000})
    assert db.consulter_stock(bd, bd.utilisatrice_id, "mil").quantite_actuelle == 3


def test_dette_client_nouvelle_puis_paiement_partiel(bd):
    db.enregistrer_mouvement_client(bd, utilisatrice_id=bd.utilisatrice_id,
                                     nom_client="mariam", montant_fcfa=2500, est_un_paiement=False)
    assert db.consulter_client(bd, bd.utilisatrice_id, "mariam").montant_du == 2500

    db.enregistrer_mouvement_client(bd, utilisatrice_id=bd.utilisatrice_id,
                                     nom_client="mariam", montant_fcfa=1000, est_un_paiement=True)
    assert db.consulter_client(bd, bd.utilisatrice_id, "mariam").montant_du == 1500


def test_consulter_stock_inexistant_renvoie_none(bd):
    assert db.consulter_stock(bd, bd.utilisatrice_id, "savon") is None
