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


def test_mouvement_client_garde_un_historique_ligne_par_ligne(bd):
    """Fiche 11 "Ventes à Crédit" (2026-11-17) : il faut pouvoir reconstituer

    chaque ligne (date/libellé/montant/payé), pas seulement le solde final.
    """
    db.enregistrer_mouvement_client(bd, utilisatrice_id=bd.utilisatrice_id, nom_client="mariam",
                                     montant_fcfa=2500, est_un_paiement=False, libelle="Vente à crédit : riz")
    db.enregistrer_mouvement_client(bd, utilisatrice_id=bd.utilisatrice_id, nom_client="mariam",
                                     montant_fcfa=1000, est_un_paiement=True, libelle="Paiement reçu")

    lignes = db.ligne_mouvements_client(bd, bd.utilisatrice_id, "mariam")
    assert len(lignes) == 2
    assert lignes[0].montant_fcfa == 2500 and lignes[0].est_un_paiement is False
    assert lignes[0].libelle == "Vente à crédit : riz"
    assert lignes[1].montant_fcfa == 1000 and lignes[1].est_un_paiement is True


def test_mouvement_client_inexistant_renvoie_une_liste_vide(bd):
    assert db.ligne_mouvements_client(bd, bd.utilisatrice_id, "personne") == []


def test_mouvement_fournisseur_garde_un_historique_ligne_par_ligne(bd):
    """Symétrique côté Fournisseur (Fiche 12 "Achats à Crédit")."""
    db.enregistrer_mouvement_fournisseur(bd, utilisatrice_id=bd.utilisatrice_id, nom_fournisseur="fanta",
                                          montant_fcfa=5000, est_un_paiement=False,
                                          libelle="Achat à crédit : sac riz")
    db.enregistrer_mouvement_fournisseur(bd, utilisatrice_id=bd.utilisatrice_id, nom_fournisseur="fanta",
                                          montant_fcfa=2000, est_un_paiement=True, libelle="Paiement fournisseur")

    lignes = db.ligne_mouvements_fournisseur(bd, bd.utilisatrice_id, "fanta")
    assert len(lignes) == 2
    assert lignes[0].montant_fcfa == 5000 and lignes[0].est_un_paiement is False
    assert lignes[1].montant_fcfa == 2000 and lignes[1].est_un_paiement is True


def test_mouvement_stock_garde_un_historique_depuis_stock_ecriture(bd):
    """Item 8 du menu : chaque déclaration/réapprovisionnement laisse une trace."""
    db.enregistrer_mouvement_stock(bd, utilisatrice_id=bd.utilisatrice_id, article="riz", quantite=50)
    db.enregistrer_mouvement_stock(bd, utilisatrice_id=bd.utilisatrice_id, article="riz", quantite=20)

    lignes = db.ligne_mouvements_stock(bd, bd.utilisatrice_id, "riz")
    assert len(lignes) == 2
    assert [l.quantite_entree for l in lignes] == [50, 20]
    assert all(l.quantite_sortie == 0 for l in lignes)


def test_mouvement_stock_garde_un_historique_depuis_vente_et_depense(bd):
    """Une vente/dépense ordinaire (items 1/2) doit aussi laisser une trace

    dans MouvementStock, pas seulement dans Stock.quantite_actuelle -
    sinon la carte de stock PDF raterait silencieusement ces mouvements.
    """
    db.enregistrer_transaction(bd, utilisatrice_id=bd.utilisatrice_id, type_="depense",
                                champs={"article": "mil", "quantite": 5, "montant_fcfa": 25_000})
    db.enregistrer_transaction(bd, utilisatrice_id=bd.utilisatrice_id, type_="vente",
                                champs={"article": "mil", "quantite": 2, "montant_fcfa": 10_000})

    lignes = db.ligne_mouvements_stock(bd, bd.utilisatrice_id, "mil")
    assert len(lignes) == 2
    assert lignes[0].quantite_entree == 5 and lignes[0].quantite_sortie == 0
    assert lignes[1].quantite_entree == 0 and lignes[1].quantite_sortie == 2


def test_ligne_journal_ne_garde_que_vente_et_depense_triees_par_date(bd):
    db.enregistrer_transaction(bd, utilisatrice_id=bd.utilisatrice_id, type_="vente",
                                champs={"article": "mil", "quantite": 2, "montant_fcfa": 10_000})
    db.ajouter_au_capital(bd, utilisatrice_id=bd.utilisatrice_id, montant_fcfa=5000)
    db.enregistrer_transaction(bd, utilisatrice_id=bd.utilisatrice_id, type_="depense",
                                champs={"article": "transport", "montant_fcfa": 750})

    lignes = db.ligne_journal(bd, bd.utilisatrice_id)
    assert [l.type for l in lignes] == ["vente", "depense"]


def test_lister_tiers_renvoie_clients_fournisseurs_et_articles_connus(bd):
    db.enregistrer_mouvement_client(bd, utilisatrice_id=bd.utilisatrice_id, nom_client="mariam",
                                     montant_fcfa=2500, est_un_paiement=False)
    db.enregistrer_mouvement_fournisseur(bd, utilisatrice_id=bd.utilisatrice_id, nom_fournisseur="fanta",
                                          montant_fcfa=5000, est_un_paiement=False)
    db.enregistrer_mouvement_stock(bd, utilisatrice_id=bd.utilisatrice_id, article="riz", quantite=50)

    tiers = db.lister_tiers(bd, bd.utilisatrice_id)
    assert tiers == {"clients": ["mariam"], "fournisseurs": ["fanta"], "articles": ["riz"]}


def test_declarer_pret_sfd_pre_cree_tout_lecheancier(bd):
    """Item 10 : la déclaration pré-crée duree_mois lignes d'échéancier,

    chacune avec sa date prévue déjà calculée (pas de reconnaissance de
    date parlée dans ce projet).
    """
    db.declarer_pret_sfd(bd, utilisatrice_id=bd.utilisatrice_id, nom_sfd="soro",
                          montant_total_fcfa=25_000, duree_mois=6, echeance_mensuelle_fcfa=5_000)

    utilisatrice = bd.get(db.Utilisatrice, bd.utilisatrice_id)
    assert utilisatrice.nom_sfd == "soro"
    assert utilisatrice.montant_total_sfd_fcfa == 25_000

    lignes = (bd.query(db.EcheanceSfd).filter_by(utilisatrice_id=bd.utilisatrice_id)
              .order_by(db.EcheanceSfd.numero.asc()).all())
    assert [l.numero for l in lignes] == [1, 2, 3, 4, 5, 6]
    assert all(l.montant_prevu == 5_000 and l.date_reelle is None for l in lignes)
    assert lignes[0].date_prevue < lignes[1].date_prevue < lignes[5].date_prevue


def test_declarer_pret_sfd_remplace_lancien_echeancier(bd):
    """Une nouvelle déclaration repart d'un programme propre (même principe

    que capital_initial), pas d'un mélange de deux échéanciers.
    """
    db.declarer_pret_sfd(bd, utilisatrice_id=bd.utilisatrice_id, nom_sfd="soro",
                          montant_total_fcfa=25_000, duree_mois=6, echeance_mensuelle_fcfa=5_000)
    db.declarer_pret_sfd(bd, utilisatrice_id=bd.utilisatrice_id, nom_sfd="kafo jiginew",
                          montant_total_fcfa=100_000, duree_mois=3, echeance_mensuelle_fcfa=35_000)

    utilisatrice = bd.get(db.Utilisatrice, bd.utilisatrice_id)
    assert utilisatrice.nom_sfd == "kafo jiginew"
    lignes = bd.query(db.EcheanceSfd).filter_by(utilisatrice_id=bd.utilisatrice_id).all()
    assert len(lignes) == 3
    assert all(l.montant_prevu == 35_000 for l in lignes)


def test_enregistrer_paiement_sfd_remplit_la_prochaine_echeance_impayee(bd):
    db.declarer_pret_sfd(bd, utilisatrice_id=bd.utilisatrice_id, nom_sfd="soro",
                          montant_total_fcfa=25_000, duree_mois=6, echeance_mensuelle_fcfa=5_000)

    ligne = db.enregistrer_paiement_sfd(bd, utilisatrice_id=bd.utilisatrice_id, montant_fcfa=5_000)
    assert ligne.numero == 1
    assert ligne.montant_paye == 5_000
    assert ligne.date_reelle is not None

    ligne2 = db.enregistrer_paiement_sfd(bd, utilisatrice_id=bd.utilisatrice_id, montant_fcfa=5_000)
    assert ligne2.numero == 2  # la première échéance est déjà payée, on passe à la suivante


def test_enregistrer_paiement_sfd_sans_echeancier_nest_pas_perdu(bd):
    """Aucune déclaration SFD existante : le paiement est quand même

    enregistré (ligne supplémentaire), jamais perdu silencieusement.
    """
    ligne = db.enregistrer_paiement_sfd(bd, utilisatrice_id=bd.utilisatrice_id, montant_fcfa=5_000)
    assert ligne.numero == 1
    assert ligne.montant_paye == 5_000


def test_bilan_pret_sfd_calcule_le_reste_a_payer_et_la_prochaine_echeance(bd):
    db.declarer_pret_sfd(bd, utilisatrice_id=bd.utilisatrice_id, nom_sfd="soro",
                          montant_total_fcfa=25_000, duree_mois=6, echeance_mensuelle_fcfa=5_000)
    db.enregistrer_paiement_sfd(bd, utilisatrice_id=bd.utilisatrice_id, montant_fcfa=5_000)

    bilan = db.bilan_pret_sfd(bd, bd.utilisatrice_id)
    assert bilan["reste_a_payer_fcfa"] == 20_000
    assert bilan["prochaine_echeance_fcfa"] == 5_000


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
