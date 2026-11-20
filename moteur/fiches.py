"""Génère en PDF les fiches papier réelles (documentation Fadima, 2026-11-17)

à partir des données déjà enregistrées par la voix, pour que l'application
puisse produire un document imprimable fidèle à ce que l'utilisatrice connaît
déjà sur papier : Journal (cashbook), Ventes à Crédit par client (Fiche 11),
Achats à Crédit par fournisseur (Fiche 12), Carte de stock par article,
Suivi des remboursements SFD (Fiche 5).

Chaque fonction renvoie les octets du PDF (bytes), prêts à être renvoyés tels
quels par une route API (voir moteur/api.py, StreamingResponse). Les soldes
("reste à payer", "stock restant", "solde") sont toujours calculés ici, à la
lecture, par somme cumulative triée par date - jamais stockés en double dans
la base (même principe que base_donnees.calculer_capital/bilan_utilisatrice).

Deux colonnes des fiches papier n'ont aucune donnée source dans ce projet et
sont donc des placeholders documentés, pas des données réelles : le "Numéro
de bon" de la carte de stock (numéro de ligne séquentiel à la place) et le
"N° reçu SFD" du suivi des remboursements (toujours "-"). À signaler à
Fadima/l'équipe terrain plutôt qu'à inventer un numéro.
"""
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from moteur import base_donnees as db

_STYLES = getSampleStyleSheet()

_STYLE_TABLE = TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
])


def _rendre(titre: str, lignes_entete: list[str], colonnes: list[str], lignes: list[list[str]]) -> bytes:
    """Mise en page commune : titre, quelques lignes d'en-tête, un tableau.

    Reproduit la structure visuelle des fiches photographiées (un en-tête
    court suivi d'une grille à bordures), sans dupliquer cette mécanique
    dans chacune des 5 fonctions generer_pdf_*.
    """
    tampon = io.BytesIO()
    doc = SimpleDocTemplate(tampon, pagesize=A4, title=titre,
                             topMargin=15 * mm, bottomMargin=15 * mm)
    elements = [Paragraph(titre, _STYLES["Title"]), Spacer(1, 4 * mm)]
    for ligne in lignes_entete:
        elements.append(Paragraph(ligne, _STYLES["Normal"]))
    elements.append(Spacer(1, 6 * mm))
    table = Table([colonnes] + lignes, repeatRows=1)
    table.setStyle(_STYLE_TABLE)
    elements.append(table)
    doc.build(elements)
    return tampon.getvalue()


def _fcfa(montant) -> str:
    return f"{montant:,}".replace(",", " ") if montant not in (None, "") else ""


def generer_pdf_journal(bd, utilisatrice_id: int) -> bytes:
    """Fiche "Journal" (cashbook) : tout l'historique vente/dépense, solde

    cumulatif calculé ici (part de 0, pas du capital initial - la fiche
    papier ne mentionne pas de capital de départ).
    """
    transactions = db.ligne_journal(bd, utilisatrice_id)
    lignes = []
    solde = 0
    for t in transactions:
        recette = t.montant_fcfa if t.type == "vente" else None
        depense = t.montant_fcfa if t.type == "depense" else None
        solde += (t.montant_fcfa if t.type == "vente" else -t.montant_fcfa)
        lignes.append([
            t.date.strftime("%d/%m/%Y") if t.date else "",
            str(t.id),
            t.article or "",
            _fcfa(recette),
            _fcfa(depense),
            _fcfa(solde),
        ])
    return _rendre("Journal", [], ["Date", "N° Pièce", "Libellé", "Recettes", "Dépenses", "Solde"], lignes)


def generer_pdf_vente_credit(bd, utilisatrice_id: int, nom_client: str) -> bytes:
    """Fiche 11 "Ventes à Crédit", pour un client donné."""
    mouvements = db.ligne_mouvements_client(bd, utilisatrice_id, nom_client)
    lignes = []
    reste = 0
    for m in mouvements:
        reste += (-m.montant_fcfa if m.est_un_paiement else m.montant_fcfa)
        lignes.append([
            m.date.strftime("%d/%m/%Y") if m.date else "",
            m.libelle or "",
            _fcfa(m.montant_fcfa) if not m.est_un_paiement else "",
            _fcfa(m.montant_fcfa) if m.est_un_paiement else "",
            _fcfa(reste),
        ])
    return _rendre("Fiche 11 : Ventes à Crédit", [f"Nom du client : {nom_client}"],
                    ["Date", "Détails", "Valeur de la vente", "Montant payé", "Reste à payer"], lignes)


def generer_pdf_achat_credit(bd, utilisatrice_id: int, nom_fournisseur: str) -> bytes:
    """Fiche 12 "Achats à Crédit", pour un fournisseur donné."""
    mouvements = db.ligne_mouvements_fournisseur(bd, utilisatrice_id, nom_fournisseur)
    lignes = []
    reste = 0
    for m in mouvements:
        reste += (-m.montant_fcfa if m.est_un_paiement else m.montant_fcfa)
        lignes.append([
            m.date.strftime("%d/%m/%Y") if m.date else "",
            m.libelle or "",
            _fcfa(m.montant_fcfa) if not m.est_un_paiement else "",
            _fcfa(m.montant_fcfa) if m.est_un_paiement else "",
            _fcfa(reste),
        ])
    return _rendre("Fiche 12 : Achats à Crédit", [f"Nom du fournisseur : {nom_fournisseur}"],
                    ["Date", "Détails", "Montant Crédit", "Montant Payé", "Reste à payer"], lignes)


def generer_pdf_carte_stock(bd, utilisatrice_id: int, article: str) -> bytes:
    """Carte/Fiche de stock, pour un article donné.

    "Numéro de bon" : aucune donnée source dans ce projet (pas de workflow
    de bon de commande en amont) - un simple numéro de ligne séquentiel sert
    de repli documenté, pas une vraie numérotation de bon.
    """
    mouvements = db.ligne_mouvements_stock(bd, utilisatrice_id, article)
    lignes = []
    solde = 0
    for i, m in enumerate(mouvements, start=1):
        solde += (m.quantite_entree or 0) - (m.quantite_sortie or 0)
        lignes.append([
            m.date.strftime("%d/%m/%Y") if m.date else "",
            str(i),
            str(m.quantite_entree or ""),
            str(m.quantite_sortie or ""),
            str(solde),
        ])
    return _rendre("Carte de stock", [f"Article : {article}"],
                    ["Date", "Numéro de bon", "Entrée", "Sortie", "Stock (restant)"], lignes)


def generer_pdf_sfd(bd, utilisatrice_id: int) -> bytes:
    """Fiche 5 "Suivi des remboursements SFD".

    "N° reçu SFD" : aucune donnée source dans ce projet (pas de numérotation
    de reçu captée nulle part) - toujours "-", un repli documenté, pas une
    vraie donnée.
    """
    bilan = db.bilan_pret_sfd(bd, utilisatrice_id)
    utilisatrice = bd.get(db.Utilisatrice, utilisatrice_id)
    en_tete = [
        f"SFD : {bilan['nom_sfd'] or ''}",
        f"Montant total crédit : {_fcfa(bilan['montant_total_fcfa'])} FCFA",
        f"Durée : {(utilisatrice.duree_mois_sfd if utilisatrice else '') or ''} mois",
        f"Échéance mensuelle : {_fcfa((utilisatrice.echeance_mensuelle_sfd_fcfa if utilisatrice else 0))} FCFA",
    ]
    lignes = []
    for e in bilan["echeances"]:
        lignes.append([
            str(e.numero),
            e.date_prevue.strftime("%d/%m/%Y") if e.date_prevue else "",
            _fcfa(e.montant_prevu),
            e.date_reelle.strftime("%d/%m/%Y") if e.date_reelle else "",
            _fcfa(e.montant_paye),
            "-",
        ])
    return _rendre("Fiche 5 : Suivi des remboursements SFD", en_tete,
                    ["N°", "Date prévue", "Montant prévu", "Date réelle", "Montant payé", "N° reçu SFD"], lignes)
