import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from moteur import base_donnees as db  # noqa: E402
from moteur import fiches  # noqa: E402


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
    session.utilisatrice_id = u.id
    return session


def _est_un_pdf_valide(contenu: bytes) -> bool:
    return contenu.startswith(b"%PDF") and len(contenu) > 0


def test_generer_pdf_journal(bd):
    db.enregistrer_transaction(bd, utilisatrice_id=bd.utilisatrice_id, type_="vente",
                                champs={"article": "mil", "quantite": 2, "montant_fcfa": 10_000})
    db.enregistrer_transaction(bd, utilisatrice_id=bd.utilisatrice_id, type_="depense",
                                champs={"article": "transport", "montant_fcfa": 750})

    contenu = fiches.generer_pdf_journal(bd, bd.utilisatrice_id)
    assert _est_un_pdf_valide(contenu)


def test_generer_pdf_journal_sans_transaction(bd):
    """Une utilisatrice toute neuve ne doit jamais faire planter la génération."""
    contenu = fiches.generer_pdf_journal(bd, bd.utilisatrice_id)
    assert _est_un_pdf_valide(contenu)


def test_generer_pdf_vente_credit(bd):
    db.enregistrer_mouvement_client(bd, utilisatrice_id=bd.utilisatrice_id, nom_client="mariam",
                                     montant_fcfa=2500, est_un_paiement=False, libelle="Vente à crédit : riz")
    db.enregistrer_mouvement_client(bd, utilisatrice_id=bd.utilisatrice_id, nom_client="mariam",
                                     montant_fcfa=1000, est_un_paiement=True, libelle="Paiement reçu")

    contenu = fiches.generer_pdf_vente_credit(bd, bd.utilisatrice_id, "mariam")
    assert _est_un_pdf_valide(contenu)


def test_generer_pdf_achat_credit(bd):
    db.enregistrer_mouvement_fournisseur(bd, utilisatrice_id=bd.utilisatrice_id, nom_fournisseur="fanta",
                                          montant_fcfa=5000, est_un_paiement=False,
                                          libelle="Achat à crédit : sac riz")

    contenu = fiches.generer_pdf_achat_credit(bd, bd.utilisatrice_id, "fanta")
    assert _est_un_pdf_valide(contenu)


def test_generer_pdf_carte_stock(bd):
    db.enregistrer_mouvement_stock(bd, utilisatrice_id=bd.utilisatrice_id, article="riz", quantite=50)
    db.enregistrer_transaction(bd, utilisatrice_id=bd.utilisatrice_id, type_="vente",
                                champs={"article": "riz", "quantite": 10, "montant_fcfa": 20_000})

    contenu = fiches.generer_pdf_carte_stock(bd, bd.utilisatrice_id, "riz")
    assert _est_un_pdf_valide(contenu)


def test_generer_pdf_sfd(bd):
    db.declarer_pret_sfd(bd, utilisatrice_id=bd.utilisatrice_id, nom_sfd="soro",
                          montant_total_fcfa=25_000, duree_mois=6, echeance_mensuelle_fcfa=5_000)
    db.enregistrer_paiement_sfd(bd, utilisatrice_id=bd.utilisatrice_id, montant_fcfa=5_000)

    contenu = fiches.generer_pdf_sfd(bd, bd.utilisatrice_id)
    assert _est_un_pdf_valide(contenu)


def test_generer_pdf_sfd_sans_declaration(bd):
    """Aucun prêt déclaré : la fiche doit quand même se générer (échéancier vide)."""
    contenu = fiches.generer_pdf_sfd(bd, bd.utilisatrice_id)
    assert _est_un_pdf_valide(contenu)
