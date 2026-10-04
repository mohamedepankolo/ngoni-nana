import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "asr_test" / "scripts"))

from moteur import base_donnees as db  # noqa: E402
from moteur.agent_vocal import AgentVocal  # noqa: E402


@pytest.fixture
def agent():
    """Une base SQLite en mémoire, partagée entre toutes les sessions SQLAlchemy du test
    (StaticPool + une seule connexion), avec une utilisatrice de test déjà créée.
    """
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = db.get_session_factory(engine)

    bd = SessionLocal()
    coop = db.Cooperative(nom="ABIC Dioïla", site="Dioïla")
    bd.add(coop)
    bd.commit()
    utilisatrice = db.Utilisatrice(code_anonyme="L01", telephone_hash="x", cooperative_id=coop.id)
    bd.add(utilisatrice)
    bd.commit()
    bd.refresh(utilisatrice)

    a = AgentVocal(session_factory=SessionLocal)
    a.utilisatrice_id = utilisatrice.id  # commodité pour les tests, pas utilisé par AgentVocal lui-même
    return a


def test_parcours_vente_complet_jusqu_a_l_enregistrement(agent):
    """Cas 2 du parcours : vente, confirmation, écriture, capital mis à jour."""
    sid = agent.demarrer_session(agent.utilisatrice_id)

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "n ye saga saba feere wa bi duuru")
    assert r["contrat"]["action"] == "demander_confirmation"
    assert r["contrat"]["confiance"] == "haute"
    assert "?" in r["message"]

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "owo")  # "oui"
    assert r["contrat"]["action"] == "enregistrer"
    assert "enregistré" in r["message"]

    bd = agent._session_factory()
    transactions = bd.query(db.Transaction).filter_by(utilisatrice_id=agent.utilisatrice_id).all()
    assert len(transactions) == 1
    assert transactions[0].montant_fcfa == 250_000

    capital = db.calculer_capital(bd, agent.utilisatrice_id)
    assert capital == 250_000

    session_bd = bd.get(db.SessionAppel, sid)
    assert session_bd.statut == "complete"


def test_rien_n_est_ecrit_si_lutilisatrice_dit_non(agent):
    sid = agent.demarrer_session(agent.utilisatrice_id)
    agent.traiter_texte(sid, agent.utilisatrice_id, "n ye saga saba feere wa bi duuru")
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "ayi")  # "non"

    assert r["contrat"]["action"] != "enregistrer"
    bd = agent._session_factory()
    assert bd.query(db.Transaction).count() == 0


def test_consultation_capital_ne_demande_pas_de_confirmation(agent):
    """Cas 4 : une consultation pure répond directement, pas de 'c'est bien ça ?'."""
    sid = agent.demarrer_session(agent.utilisatrice_id)
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "n ka jagokun ye waa tan ye")

    assert r["contrat"]["intention"] == "capital"
    assert "francs" in r["message"]
    bd = agent._session_factory()
    assert bd.get(db.SessionAppel, sid).statut == "complete"


def test_escalade_apres_trois_incomprehensions(agent):
    sid = agent.demarrer_session(agent.utilisatrice_id)
    for _ in range(2):
        r = agent.traiter_texte(sid, agent.utilisatrice_id, "bruit")
        assert r["contrat"]["action"] == "reformuler"
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "bruit")
    assert r["contrat"]["action"] == "escalade_humaine"
    assert "animatrice" in r["message"]


def test_client_nouvelle_dette_declaree_augmente_le_solde(agent):
    """P13 : "Awa me doit 10000 francs" sans "sara" = nouvelle dette, pas un paiement."""
    sid = agent.demarrer_session(agent.utilisatrice_id)
    agent.traiter_texte(sid, agent.utilisatrice_id, "n ka waa fila juru bɛ awa la")
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "owo")

    assert r["contrat"]["action"] == "enregistrer"
    bd = agent._session_factory()
    client = db.consulter_client(bd, agent.utilisatrice_id, "awa")
    assert client.montant_du == 10_000


def test_client_paiement_recu_reduit_la_dette(agent):
    """P14b : "sara" aux côtés de "juru" = un paiement reçu, qui réduit la dette."""
    bd = agent._session_factory()
    db.enregistrer_mouvement_client(bd, utilisatrice_id=agent.utilisatrice_id,
                                     nom_client="fanta", montant_fcfa=10_000, est_un_paiement=False)

    sid = agent.demarrer_session(agent.utilisatrice_id)
    agent.traiter_texte(sid, agent.utilisatrice_id, "Fanta ye kɛmɛ wolonwula sara, n ka juru la")
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "owo")

    assert r["contrat"]["action"] == "enregistrer"
    client = db.consulter_client(bd, agent.utilisatrice_id, "fanta")
    assert client.montant_du == 10_000 - 3_500
