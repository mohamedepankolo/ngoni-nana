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
    assert "sɛbɛnna" in r["message"]  # "c'est enregistré", en bambara (messages_bambara.py)

    bd = agent._session_factory()
    transactions = bd.query(db.Transaction).filter_by(utilisatrice_id=agent.utilisatrice_id).all()
    assert len(transactions) == 1
    assert transactions[0].montant_fcfa == 250_000

    capital = db.calculer_capital(bd, agent.utilisatrice_id)
    assert capital == 250_000

    session_bd = bd.get(db.SessionAppel, sid)
    assert session_bd.statut == "complete"


def test_bruit_asr_pendant_la_confirmation_ne_corrompt_pas_larticle(agent):
    """Régression réelle (2026-10-09) : une utilisatrice confirme "oui" plusieurs

    fois de suite et entend toujours "la même question". Cause : un mot bruit
    de l'ASR (ni "oui" ni "non" reconnu, voir reconnaitre_confirmation) était
    traité comme une correction directe de l'article (cas 9), l'écrasant
    silencieusement avec du bruit et redemandant confirmation avec le nouveau
    (faux) article - d'où l'impression de boucle infinie, et un risque réel
    d'enregistrer la mauvaise marchandise si l'utilisatrice finit par dire un
    "oui" reconnu. Seul un nombre explicitement redit doit valoir correction
    directe (cas 9) ; un mot isolé sans chiffre doit juste redemander oui/non,
    sans toucher aux champs déjà confirmés.
    """
    sid = agent.demarrer_session(agent.utilisatrice_id)
    agent.traiter_texte(sid, agent.utilisatrice_id, "n ye saga saba feere wa bi duuru")

    # "wo" : ni oui/non reconnu, ni mot-clé, ni nombre - un mot de bruit plausible.
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "wo")
    assert r["contrat"]["action"] == "demander_confirmation"
    assert r["contrat"]["champs"]["article"] == "saga"  # inchangé, pas "wo"
    assert "saga" in r["message"]

    # Confirmer pour de vrai doit encore marcher, avec les bonnes valeurs d'origine.
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "owo")
    assert r["contrat"]["action"] == "enregistrer"
    bd = agent._session_factory()
    transactions = bd.query(db.Transaction).filter_by(utilisatrice_id=agent.utilisatrice_id).all()
    assert len(transactions) == 1
    assert transactions[0].article == "saga"
    assert transactions[0].montant_fcfa == 250_000


def test_bruit_repete_pendant_la_confirmation_finit_par_escalader(agent):
    # Sans escalade, du bruit ASR repete indefiniment ferait boucler
    # l'utilisatrice sans fin (c'est exactement le symptome rapporte).
    sid = agent.demarrer_session(agent.utilisatrice_id)
    agent.traiter_texte(sid, agent.utilisatrice_id, "n ye saga saba feere wa bi duuru")

    for _ in range(2):
        r = agent.traiter_texte(sid, agent.utilisatrice_id, "wo")
        assert r["contrat"]["action"] == "demander_confirmation"
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "wo")
    assert r["contrat"]["action"] == "escalade_humaine"


def test_redire_un_montant_sans_dire_non_corrige_quand_meme(agent):
    """Cas 9 : l'utilisatrice redit directement un nombre sans dire "non" d'abord."""
    sid = agent.demarrer_session(agent.utilisatrice_id)
    agent.traiter_texte(sid, agent.utilisatrice_id, "n ye saga saba feere wa bi duuru")

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "waa bi duuru")  # un nouveau montant, redit directement
    assert r["contrat"]["action"] == "demander_confirmation"
    assert r["contrat"]["confiance"] == "haute"


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
    assert "jagokun" in r["message"]  # "capital", en bambara (messages_bambara.reponse_capital)
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
