import sys
from datetime import datetime, timedelta, timezone
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


def test_dette_fournisseur_nouvelle_puis_paiement_partiel(bd):
    """Item 5/6 du menu (2026-11-17) : symétrique de test_dette_client..., mais

    côté fournisseur (ce que l'utilisatrice doit, pas ce qu'on lui doit).
    """
    db.enregistrer_mouvement_fournisseur(bd, utilisatrice_id=bd.utilisatrice_id,
                                          nom_fournisseur="fanta_grossiste", montant_fcfa=5000,
                                          est_un_paiement=False)
    assert db.consulter_fournisseur(bd, bd.utilisatrice_id, "fanta_grossiste").montant_du == 5000

    db.enregistrer_mouvement_fournisseur(bd, utilisatrice_id=bd.utilisatrice_id,
                                          nom_fournisseur="fanta_grossiste", montant_fcfa=2000,
                                          est_un_paiement=True)
    assert db.consulter_fournisseur(bd, bd.utilisatrice_id, "fanta_grossiste").montant_du == 3000
    assert db.total_du_aux_fournisseurs(bd, bd.utilisatrice_id) == 3000


def test_dette_fournisseur_augmente_le_capital(bd):
    """Une dette fournisseur ajoute au capital (formule de l'architecture,

    voir calculer_capital) : contre-intuitif au premier regard (on doit de
    l'argent), mais c'est la formule documentée depuis le début de ce
    module - l'argent emprunté au fournisseur reste disponible tant qu'il
    n'est pas remboursé.
    """
    db.enregistrer_mouvement_fournisseur(bd, utilisatrice_id=bd.utilisatrice_id, nom_fournisseur="grossiste",
                                          montant_fcfa=5000, est_un_paiement=False)
    assert db.calculer_capital(bd, bd.utilisatrice_id) == 5000


def test_enregistrer_mouvement_stock_initial_puis_reapprovisionnement(bd):
    """Item 8 du menu (2026-11-17) : la 1re déclaration pour un article

    REMPLACE (stock initial), les suivantes s'AJOUTENT (réapprovisionnement) -
    voir enregistrer_mouvement_stock.
    """
    ligne, est_initial = db.enregistrer_mouvement_stock(bd, utilisatrice_id=bd.utilisatrice_id,
                                                         article="riz", quantite=50)
    assert est_initial is True
    assert ligne.quantite_actuelle == 50

    ligne, est_initial = db.enregistrer_mouvement_stock(bd, utilisatrice_id=bd.utilisatrice_id,
                                                         article="riz", quantite=20)
    assert est_initial is False
    assert ligne.quantite_actuelle == 70


def test_bilan_utilisatrice_agrege_tout(bd):
    """Écran "bilan" de l'application mobile (lecture seule) : capital, totaux,

    dernières transactions, dettes clients actives, stock.
    """
    db.enregistrer_transaction(bd, utilisatrice_id=bd.utilisatrice_id, type_="vente",
                                champs={"article": "mil", "quantite": 2, "montant_fcfa": 10_000})
    db.enregistrer_transaction(bd, utilisatrice_id=bd.utilisatrice_id, type_="depense",
                                champs={"article": "transport", "montant_fcfa": 750})
    db.enregistrer_mouvement_client(bd, utilisatrice_id=bd.utilisatrice_id,
                                     nom_client="mariam", montant_fcfa=2500, est_un_paiement=False)
    # Client soldé (montant_du == 0) : ne doit pas apparaitre dans les dettes actives.
    db.enregistrer_mouvement_client(bd, utilisatrice_id=bd.utilisatrice_id,
                                     nom_client="fanta", montant_fcfa=1000, est_un_paiement=False)
    db.enregistrer_mouvement_client(bd, utilisatrice_id=bd.utilisatrice_id,
                                     nom_client="fanta", montant_fcfa=1000, est_un_paiement=True)

    bilan = db.bilan_utilisatrice(bd, bd.utilisatrice_id)

    assert bilan["capital"] == 10_000 - 750 - 2500
    assert bilan["total_ventes"] == 10_000
    assert bilan["total_depenses"] == 750
    assert len(bilan["transactions"]) == 2
    assert {d["nom"] for d in bilan["dettes_clients"]} == {"mariam"}
    assert bilan["stock"][0]["article"] == "mil"
    assert bilan["stock"][0]["quantite"] == -2  # vente de 2, jamais approvisionne dans ce test


def test_bilan_utilisatrice_sans_transaction_reste_coherent(bd):
    """Une utilisatrice toute neuve ne doit jamais faire planter le bilan."""
    bilan = db.bilan_utilisatrice(bd, bd.utilisatrice_id)
    assert bilan == {
        "capital": 0, "total_ventes": 0, "total_depenses": 0,
        "transactions": [], "dettes_clients": [], "dettes_fournisseurs": [], "stock": [],
    }


def test_consulter_stock_inexistant_renvoie_none(bd):
    assert db.consulter_stock(bd, bd.utilisatrice_id, "savon") is None


def test_expirer_sessions_anciennes_marque_les_vieilles_incompletes(bd):
    # Une utilisatrice qui raccroche en plein milieu d'une confirmation laisse
    # une session "incomplete" en base pour toujours si rien ne la nettoie
    # (voir agent_vocal.py, appelé à chaque nouvelle session).
    vieille = db.SessionAppel(utilisatrice_id=bd.utilisatrice_id, canal="voix", statut="incomplete")
    vieille.date_debut = datetime.now(timezone.utc) - timedelta(minutes=60)
    recente = db.SessionAppel(utilisatrice_id=bd.utilisatrice_id, canal="voix", statut="incomplete")
    bd.add_all([vieille, recente])
    bd.commit()
    bd.refresh(vieille)
    bd.refresh(recente)

    expirees = db.expirer_sessions_anciennes(bd, minutes=30)

    assert expirees == [vieille.id]
    assert bd.get(db.SessionAppel, vieille.id).statut == "expiree"
    assert bd.get(db.SessionAppel, recente.id).statut == "incomplete"
