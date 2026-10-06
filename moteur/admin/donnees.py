"""Requêtes de lecture pour le dashboard admin ABIC (architecture section 3.8).

Tout en lecture seule : le dashboard ne modifie jamais directement les
transactions, le capital ou le stock (ce sont les écritures de l'agent vocal,
après confirmation, qui font foi (principe de non-perte silencieuse,
section 1). Les seules écritures d'ici concernent la gestion des comptes
(utilisatrices, relais), pas les données comptables elles-mêmes.
"""
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session as SessionSQLAlchemy

from moteur import base_donnees as db


def kpis_vue_ensemble(bd: SessionSQLAlchemy) -> dict:
    total_utilisatrices = bd.query(func.count(db.Utilisatrice.id)).scalar() or 0
    total_sessions = bd.query(func.count(db.SessionAppel.id)).scalar() or 0
    sessions_completes = (bd.query(func.count(db.SessionAppel.id))
                           .filter(db.SessionAppel.statut == "complete").scalar() or 0)
    taux_completion = round(100 * sessions_completes / total_sessions) if total_sessions else 0

    repartition = (bd.query(db.Cooperative.nom, func.count(db.Utilisatrice.id))
                   .outerjoin(db.Utilisatrice, db.Utilisatrice.cooperative_id == db.Cooperative.id)
                   .group_by(db.Cooperative.id).all())
    total_coop = sum(n for _, n in repartition) or 1
    repartition_cooperatives = [
        {"nom": nom, "nb": n, "pct": round(100 * n / total_coop)} for nom, n in repartition
    ]

    alertes_stock = (bd.query(db.Stock)
                      .filter(db.Stock.quantite_actuelle <= db.Stock.seuil_alerte).all())

    sessions_recentes = (bd.query(db.SessionAppel, db.Utilisatrice, db.Cooperative)
                          .join(db.Utilisatrice, db.SessionAppel.utilisatrice_id == db.Utilisatrice.id)
                          .outerjoin(db.Cooperative, db.Utilisatrice.cooperative_id == db.Cooperative.id)
                          .order_by(db.SessionAppel.date_debut.desc())
                          .limit(8).all())

    return {
        "total_utilisatrices": total_utilisatrices,
        "total_sessions": total_sessions,
        "taux_completion": taux_completion,
        "repartition_cooperatives": repartition_cooperatives,
        "alertes_stock": alertes_stock,
        "sessions_recentes": sessions_recentes,
    }


def lister_cooperatives(bd: SessionSQLAlchemy) -> list[db.Cooperative]:
    return bd.query(db.Cooperative).order_by(db.Cooperative.nom).all()


def lister_utilisatrices(bd: SessionSQLAlchemy, cooperative_id: int | None = None,
                           recherche: str | None = None) -> list[dict]:
    requete = (bd.query(db.Utilisatrice, db.Cooperative, func.count(db.Transaction.id))
               .outerjoin(db.Cooperative, db.Utilisatrice.cooperative_id == db.Cooperative.id)
               .outerjoin(db.Transaction, db.Transaction.utilisatrice_id == db.Utilisatrice.id)
               .group_by(db.Utilisatrice.id, db.Cooperative.id))
    if cooperative_id:
        requete = requete.filter(db.Utilisatrice.cooperative_id == cooperative_id)
    if recherche:
        requete = requete.filter(db.Utilisatrice.code_anonyme.ilike(f"%{recherche}%"))
    lignes = requete.order_by(db.Utilisatrice.date_creation.desc()).all()
    return [
        {"utilisatrice": u, "cooperative": coop, "nb_transactions": n}
        for u, coop, n in lignes
    ]


def lister_sessions(bd: SessionSQLAlchemy, cooperative_id: int | None = None,
                      statut: str | None = None, canal: str | None = None) -> list[dict]:
    requete = (bd.query(db.SessionAppel, db.Utilisatrice, db.Cooperative)
               .join(db.Utilisatrice, db.SessionAppel.utilisatrice_id == db.Utilisatrice.id)
               .outerjoin(db.Cooperative, db.Utilisatrice.cooperative_id == db.Cooperative.id))
    if cooperative_id:
        requete = requete.filter(db.Utilisatrice.cooperative_id == cooperative_id)
    if statut:
        requete = requete.filter(db.SessionAppel.statut == statut)
    if canal:
        requete = requete.filter(db.SessionAppel.canal == canal)
    lignes = requete.order_by(db.SessionAppel.date_debut.desc()).limit(200).all()

    resultat = []
    for s, u, coop in lignes:
        duree_s = None
        if s.date_fin is not None:
            debut = s.date_debut if s.date_debut.tzinfo else s.date_debut.replace(tzinfo=timezone.utc)
            fin = s.date_fin if s.date_fin.tzinfo else s.date_fin.replace(tzinfo=timezone.utc)
            duree_s = max(0, round((fin - debut).total_seconds()))
        derniere_action = (bd.query(db.JournalEvenement)
                            .filter(db.JournalEvenement.session_id == s.id)
                            .order_by(db.JournalEvenement.horodatage.desc()).first())
        resultat.append({
            "session": s, "utilisatrice": u, "cooperative": coop,
            "duree_s": duree_s,
            "derniere_action": derniere_action.etape if derniere_action else None,
        })
    return resultat


def rapport_par_cooperative(bd: SessionSQLAlchemy) -> list[dict]:
    cooperatives = lister_cooperatives(bd)
    resultat = []
    for coop in cooperatives:
        transactions = (bd.query(db.Transaction)
                         .join(db.Utilisatrice, db.Transaction.utilisatrice_id == db.Utilisatrice.id)
                         .filter(db.Utilisatrice.cooperative_id == coop.id).all())
        recettes = sum(t.montant_fcfa for t in transactions if t.type == "vente")
        depenses = sum(t.montant_fcfa for t in transactions if t.type == "depense")
        resultat.append({
            "cooperative": coop, "recettes": recettes, "depenses": depenses,
            "solde": recettes - depenses,
        })
    return resultat
