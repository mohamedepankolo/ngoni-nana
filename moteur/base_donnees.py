"""Base de données (Architecture_Technique_NGONI_NANA.docx, section 3.7).

Même schéma que le document d'architecture, implémenté avec SQLAlchemy.
Par défaut, utilise un fichier SQLite local (zéro configuration, pas
d'identifiants à fournir) : utile pour développer et tester sans attendre que
R1 (hébergement) soit tranché avec CFA. En production, il suffira de pointer
`DATABASE_URL` vers la base Postgres (ex. Neon, déjà retenue comme option
gratuite pour la phase de test) : le code ne change pas, seule la chaîne de
connexion change.

Règle reprise du principe "aucune perte silencieuse de donnée" (section 1 de
l'architecture) : la seule fonction qui écrit une transaction est
`enregistrer_transaction`, et elle n'est appelée par l'agent vocal qu'après
confirmation explicite (voir agent_vocal.py). Aucune autre fonction de ce
module n'écrit de transaction partielle.
"""
import calendar
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Session as SessionSQLAlchemy, sessionmaker


class Base(DeclarativeBase):
    pass


class Cooperative(Base):
    __tablename__ = "cooperatives"
    id = Column(Integer, primary_key=True)
    nom = Column(String, nullable=False)
    site = Column(String)  # Dioïla / Kolondiéba / Bamako


class Utilisatrice(Base):
    __tablename__ = "utilisatrices"
    id = Column(Integer, primary_key=True)
    code_anonyme = Column(String, unique=True, nullable=False)
    telephone_hash = Column(String, nullable=False)  # jamais le numéro en clair (section 5)
    cooperative_id = Column(Integer, ForeignKey("cooperatives.id"))
    langue = Column(String, default="bambara")
    date_creation = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    # Capital de départ, déclaré une fois par la voix ("mon capital est de
    # X") : remplacé (pas additionné) à chaque nouvelle déclaration, à la
    # différence des ajouts (voir ajouter_au_capital), qui s'accumulent.
    capital_initial = Column(Integer, default=0)
    # Crédit SFD actif (item 10 du menu, 2026-11-17 - "Fiche 5, Suivi des
    # remboursements SFD", documentation Fadima) : un seul prêt actif à la
    # fois, même principe que capital_initial (une nouvelle déclaration
    # REMPLACE l'ancienne, voir declarer_pret_sfd) - pas de table à part
    # pour l'en-tête du prêt, l'échéancier lui-même vit dans EcheanceSfd.
    nom_sfd = Column(String)
    montant_total_sfd_fcfa = Column(Integer)
    duree_mois_sfd = Column(Integer)
    echeance_mensuelle_sfd_fcfa = Column(Integer)
    date_declaration_sfd = Column(DateTime)


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    utilisatrice_id = Column(Integer, ForeignKey("utilisatrices.id"), nullable=False)
    type = Column(String, nullable=False)  # "vente" | "depense"
    article = Column(String)
    quantite = Column(Integer)
    montant_fcfa = Column(Integer, nullable=False)
    unite_dite = Column(String)  # "dorome" | "fcfa" : conservé pour audit
    date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    session_id = Column(Integer, ForeignKey("sessions.id"))


class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True)
    utilisatrice_id = Column(Integer, ForeignKey("utilisatrices.id"), nullable=False)
    nom_ou_code = Column(String, nullable=False)
    montant_du = Column(Integer, default=0)
    date_dernier_mouvement = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Fournisseur(Base):
    """Dette "fournisseur" : symétrique de Client, mais dans l'autre sens -

    ici, c'est l'utilisatrice qui doit de l'argent (achat à crédit, item 5
    du menu, 2026-11-17), pas un client. Table séparée plutôt que de
    réutiliser Client avec un simple booléen "sens" : évite de mélanger deux
    listes de tiers qui n'ont jamais de raison de se recouper (un client et
    un fournisseur sont des personnes différentes) et garde la même logique
    simple "nom -> montant_du" déjà éprouvée pour Client.
    """
    __tablename__ = "fournisseurs"
    id = Column(Integer, primary_key=True)
    utilisatrice_id = Column(Integer, ForeignKey("utilisatrices.id"), nullable=False)
    nom_ou_code = Column(String, nullable=False)
    montant_du = Column(Integer, default=0)
    date_dernier_mouvement = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Stock(Base):
    __tablename__ = "stock"
    id = Column(Integer, primary_key=True)
    utilisatrice_id = Column(Integer, ForeignKey("utilisatrices.id"), nullable=False)
    article = Column(String, nullable=False)
    quantite_actuelle = Column(Integer, default=0)
    seuil_alerte = Column(Integer, default=0)


class MouvementClient(Base):
    """Historique ligne par ligne des mouvements d'un Client (Fiche 11 "Ventes

    à Crédit" papier : Date/Détails/Valeur de la vente/Montant payé/Reste à
    payer) - Client.montant_du seul ne garde que le solde courant, pas le
    détail ligne par ligne nécessaire pour reproduire la fiche en PDF (voir
    moteur/fiches.py). "Reste à payer" à une ligne donnée se calcule à la
    lecture (somme cumulative triée par date), jamais stocké ici.
    """
    __tablename__ = "mouvements_clients"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    montant_fcfa = Column(Integer, nullable=False)
    est_un_paiement = Column(Boolean, default=False)
    libelle = Column(String)
    date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    session_id = Column(Integer, ForeignKey("sessions.id"))


class MouvementFournisseur(Base):
    """Symétrique de MouvementClient, côté Fournisseur (Fiche 12 "Achats à Crédit")."""
    __tablename__ = "mouvements_fournisseurs"
    id = Column(Integer, primary_key=True)
    fournisseur_id = Column(Integer, ForeignKey("fournisseurs.id"), nullable=False)
    montant_fcfa = Column(Integer, nullable=False)
    est_un_paiement = Column(Boolean, default=False)
    libelle = Column(String)
    date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    session_id = Column(Integer, ForeignKey("sessions.id"))


class MouvementStock(Base):
    """Historique ligne par ligne des mouvements de Stock (Carte/Fiche de

    stock papier : Date/Entrée/Sortie/Stock restant) - Stock.quantite_actuelle
    seul ne garde que la valeur courante. Alimentée depuis DEUX endroits :
    enregistrer_mouvement_stock (item 8 du menu) ET le bloc d'ajustement
    stock dans enregistrer_transaction (vente/dépense, items 1/2) - sans ce
    second point, la carte de stock PDF raterait silencieusement tout
    mouvement de stock causé par une vente ou une dépense ordinaire.
    """
    __tablename__ = "mouvements_stock"
    id = Column(Integer, primary_key=True)
    utilisatrice_id = Column(Integer, ForeignKey("utilisatrices.id"), nullable=False)
    article = Column(String, nullable=False)
    quantite_entree = Column(Integer, default=0)
    quantite_sortie = Column(Integer, default=0)
    date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    session_id = Column(Integer, ForeignKey("sessions.id"))


class EcheanceSfd(Base):
    """Une ligne de l'échéancier SFD (Utilisatrice.nom_sfd et consorts pour

    l'en-tête du prêt) - pré-créée en bloc par declarer_pret_sfd (une ligne
    par mois de durée), puis complétée une à une par enregistrer_paiement_sfd
    au fur et à mesure des paiements réels. date_prevue/montant_prevu sont
    connus dès la déclaration (pas de reconnaissance de date parlée dans ce
    projet - voir declarer_pret_sfd) ; date_reelle/montant_paye restent NULL
    tant que cette échéance n'a pas été payée.
    """
    __tablename__ = "echeances_sfd"
    id = Column(Integer, primary_key=True)
    utilisatrice_id = Column(Integer, ForeignKey("utilisatrices.id"), nullable=False)
    numero = Column(Integer, nullable=False)
    date_prevue = Column(DateTime)
    montant_prevu = Column(Integer)
    date_reelle = Column(DateTime)
    montant_paye = Column(Integer)
    session_id = Column(Integer, ForeignKey("sessions.id"))


class SessionAppel(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True)
    utilisatrice_id = Column(Integer, ForeignKey("utilisatrices.id"))
    date_debut = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    date_fin = Column(DateTime)
    statut = Column(String, default="incomplete")  # "complete" | "incomplete" (cas 10)
    canal = Column(String)


class Consentement(Base):
    __tablename__ = "consentements"
    id = Column(Integer, primary_key=True)
    utilisatrice_id = Column(Integer, ForeignKey("utilisatrices.id"), nullable=False)
    date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    texte_lu = Column(String)
    enregistrement_audio_ref = Column(String)


class JournalEvenement(Base):
    __tablename__ = "journal_evenements"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    horodatage = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    etape = Column(String)
    confiance = Column(String)
    resultat = Column(String)


def get_engine(url: str | None = None):
    """URL explicite > DATABASE_URL (env) > SQLite local par défaut."""
    url = url or os.environ.get("DATABASE_URL", "sqlite:///ngoni_nana.db")
    return create_engine(url)


def get_session_factory(engine) -> sessionmaker:
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def enregistrer_transaction(db: SessionSQLAlchemy, *, utilisatrice_id: int, type_: str,
                              champs: dict, session_id: int | None = None) -> Transaction:
    """Seul point d'écriture d'une transaction. Doit être appelé uniquement après
    confirmation finale (Session.confirmer() côté moteur_decision, cas 8/10 du parcours).
    """
    t = Transaction(
        utilisatrice_id=utilisatrice_id,
        type=type_,
        article=champs.get("article"),
        quantite=champs.get("quantite"),
        montant_fcfa=champs.get("montant_fcfa", 0),
        unite_dite=champs.get("unite_dite"),
        session_id=session_id,
    )
    db.add(t)

    # Un achat/une vente fait aussi bouger le stock quand un article est nommé
    # (règle simple de première version ; les seuils de vraisemblance exacts
    # restent à définir avec Fadima, risque R5 de l'architecture).
    if champs.get("article") and champs.get("quantite") is not None:
        ligne_stock = (db.query(Stock)
                       .filter_by(utilisatrice_id=utilisatrice_id, article=champs["article"])
                       .one_or_none())
        if ligne_stock is None:
            ligne_stock = Stock(utilisatrice_id=utilisatrice_id, article=champs["article"],
                                 quantite_actuelle=0, seuil_alerte=0)
            db.add(ligne_stock)
            db.flush()  # assigne ligne_stock.id avant l'UPDATE atomique ci-dessous
        delta = champs["quantite"] if type_ == "depense" else -champs["quantite"]
        # UPDATE atomique (lu et écrit en une seule instruction SQL) plutôt que
        # lire puis réécrire quantite_actuelle en Python : deux ventes du même
        # article arrivant en même temps (deux requêtes HTTP concurrentes) ne
        # doivent jamais s'écraser l'une l'autre (perte de mise à jour).
        (db.query(Stock)
         .filter_by(id=ligne_stock.id)
         .update({Stock.quantite_actuelle: Stock.quantite_actuelle + delta}))
        db.add(MouvementStock(
            utilisatrice_id=utilisatrice_id, article=champs["article"],
            quantite_entree=champs["quantite"] if type_ == "depense" else 0,
            quantite_sortie=champs["quantite"] if type_ == "vente" else 0,
            session_id=session_id))

    db.commit()
    db.refresh(t)
    return t


def enregistrer_mouvement_client(db: SessionSQLAlchemy, *, utilisatrice_id: int,
                                   nom_client: str, montant_fcfa: int, est_un_paiement: bool,
                                   libelle: str | None = None, session_id: int | None = None) -> Client:
    """Cas 5 : nouvelle dette (montant positif) ou paiement reçu (négatif sur la dette).

    Alimente aussi MouvementClient (historique ligne par ligne, voir sa
    docstring) en plus du solde courant montant_du.
    """
    client = (db.query(Client)
              .filter_by(utilisatrice_id=utilisatrice_id, nom_ou_code=nom_client)
              .one_or_none())
    if client is None:
        client = Client(utilisatrice_id=utilisatrice_id, nom_ou_code=nom_client, montant_du=0)
        db.add(client)
        db.flush()  # assigne client.id avant la ligne d'historique ci-dessous
    client.montant_du = (client.montant_du or 0) + (-montant_fcfa if est_un_paiement else montant_fcfa)
    client.date_dernier_mouvement = datetime.now(timezone.utc)
    db.add(MouvementClient(client_id=client.id, montant_fcfa=montant_fcfa, est_un_paiement=est_un_paiement,
                            libelle=libelle, session_id=session_id))
    db.commit()
    db.refresh(client)
    return client


def enregistrer_mouvement_fournisseur(db: SessionSQLAlchemy, *, utilisatrice_id: int,
                                        nom_fournisseur: str, montant_fcfa: int,
                                        est_un_paiement: bool, libelle: str | None = None,
                                        session_id: int | None = None) -> Fournisseur:
    """Symétrique de enregistrer_mouvement_client : nouvelle dette (achat à

    crédit, item 5) ou paiement fait au fournisseur (échéance/dépôt, item 6).
    """
    fournisseur = (db.query(Fournisseur)
                   .filter_by(utilisatrice_id=utilisatrice_id, nom_ou_code=nom_fournisseur)
                   .one_or_none())
    if fournisseur is None:
        fournisseur = Fournisseur(utilisatrice_id=utilisatrice_id, nom_ou_code=nom_fournisseur, montant_du=0)
        db.add(fournisseur)
        db.flush()  # assigne fournisseur.id avant la ligne d'historique ci-dessous
    fournisseur.montant_du = (fournisseur.montant_du or 0) + (-montant_fcfa if est_un_paiement else montant_fcfa)
    fournisseur.date_dernier_mouvement = datetime.now(timezone.utc)
    db.add(MouvementFournisseur(fournisseur_id=fournisseur.id, montant_fcfa=montant_fcfa,
                                 est_un_paiement=est_un_paiement, libelle=libelle, session_id=session_id))
    db.commit()
    db.refresh(fournisseur)
    return fournisseur


def consulter_fournisseur(db: SessionSQLAlchemy, utilisatrice_id: int, nom_fournisseur: str) -> Fournisseur | None:
    return (db.query(Fournisseur)
            .filter_by(utilisatrice_id=utilisatrice_id, nom_ou_code=nom_fournisseur)
            .one_or_none())


def total_du_aux_fournisseurs(db: SessionSQLAlchemy, utilisatrice_id: int) -> int:
    """Somme du reste à payer, tous fournisseurs confondus (item 7, quand

    aucun nom de fournisseur précis n'est donné - voir
    CHAMPS_ATTENDUS["fournisseur_consultation"], moteur_decision.py).
    """
    return sum(f.montant_du or 0 for f in
               db.query(Fournisseur).filter_by(utilisatrice_id=utilisatrice_id).all())


def enregistrer_mouvement_stock(db: SessionSQLAlchemy, *, utilisatrice_id: int,
                                  article: str, quantite: int,
                                  session_id: int | None = None) -> tuple[Stock, bool]:
    """Item 8 du menu : "stock initial" si aucune ligne n'existe encore pour

    cet article (la quantité REMPLACE, comme une première déclaration),
    "réapprovisionnement" si une ligne existe déjà (la quantité s'AJOUTE à
    l'existant) - même distinction que capital_declaration/capital_ajout,
    mais décidée ici plutôt que dans moteur_decision.py (couche pure, sans
    accès à la base) : seule cette fonction sait si une ligne existe déjà.
    Renvoie (ligne_stock, est_une_declaration_initiale) pour que l'appelant
    choisisse le bon message de confirmation si besoin. Alimente aussi
    MouvementStock (toujours une entrée ici, jamais une sortie - voir sa
    docstring).
    """
    ligne = (db.query(Stock)
             .filter_by(utilisatrice_id=utilisatrice_id, article=article)
             .one_or_none())
    if ligne is None:
        ligne = Stock(utilisatrice_id=utilisatrice_id, article=article, quantite_actuelle=quantite, seuil_alerte=0)
        db.add(ligne)
        db.add(MouvementStock(utilisatrice_id=utilisatrice_id, article=article,
                               quantite_entree=quantite, quantite_sortie=0, session_id=session_id))
        db.commit()
        db.refresh(ligne)
        return ligne, True
    (db.query(Stock).filter_by(id=ligne.id)
     .update({Stock.quantite_actuelle: Stock.quantite_actuelle + quantite}))
    db.add(MouvementStock(utilisatrice_id=utilisatrice_id, article=article,
                           quantite_entree=quantite, quantite_sortie=0, session_id=session_id))
    db.commit()
    db.refresh(ligne)
    return ligne, False


def calculer_capital(db: SessionSQLAlchemy, utilisatrice_id: int) -> int:
    """Capital initial + ajouts + recettes - dépenses - dettes clients + dettes fournisseurs

    (formule de l'architecture). "Dettes fournisseurs" n'avait pas de table
    dédiée avant l'item 5 du menu (achat à crédit, 2026-11-17) : implémenté
    maintenant que le cas d'usage existe réellement (voir Fournisseur,
    enregistrer_mouvement_fournisseur).
    """
    utilisatrice = db.get(Utilisatrice, utilisatrice_id)
    capital_initial = (utilisatrice.capital_initial or 0) if utilisatrice else 0
    transactions = db.query(Transaction).filter_by(utilisatrice_id=utilisatrice_id).all()
    recettes = sum(t.montant_fcfa for t in transactions if t.type == "vente")
    depenses = sum(t.montant_fcfa for t in transactions if t.type == "depense")
    ajouts_capital = sum(t.montant_fcfa for t in transactions if t.type == "capital_ajout")
    dettes_clients = sum(c.montant_du or 0 for c in
                          db.query(Client).filter_by(utilisatrice_id=utilisatrice_id).all())
    dettes_fournisseurs = sum(f.montant_du or 0 for f in
                               db.query(Fournisseur).filter_by(utilisatrice_id=utilisatrice_id).all())
    return capital_initial + ajouts_capital + recettes - depenses - dettes_clients + dettes_fournisseurs


def declarer_capital_initial(db: SessionSQLAlchemy, *, utilisatrice_id: int, montant_fcfa: int) -> None:
    """"Mon capital de départ est de X" : remplace la valeur (pas un ajout),

    redéclarer écrase la précédente. Voir ajouter_au_capital pour un vrai
    ajout cumulatif ("j'ajoute X à mon capital").
    """
    utilisatrice = db.get(Utilisatrice, utilisatrice_id)
    utilisatrice.capital_initial = montant_fcfa
    db.commit()


def ajouter_au_capital(db: SessionSQLAlchemy, *, utilisatrice_id: int,
                        montant_fcfa: int, session_id: int | None = None) -> Transaction:
    """"J'ajoute X à mon capital" : cumulatif, chaque ajout s'additionne aux précédents."""
    t = Transaction(utilisatrice_id=utilisatrice_id, type="capital_ajout",
                     montant_fcfa=montant_fcfa, session_id=session_id)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _ajouter_mois(date_depart: datetime, n: int) -> datetime:
    """date_depart + n mois, avec gestion du changement d'année et des mois

    plus courts (ex. 31 janvier + 1 mois -> 28/29 février, pas un débordement
    en mars) - calcul maison avec le module standard `calendar`, pas de
    nouvelle dépendance (python-dateutil) pour ce seul besoin.
    """
    mois_total = date_depart.month - 1 + n
    annee = date_depart.year + mois_total // 12
    mois = mois_total % 12 + 1
    dernier_jour_du_mois = calendar.monthrange(annee, mois)[1]
    jour = min(date_depart.day, dernier_jour_du_mois)
    return date_depart.replace(year=annee, month=mois, day=jour)


def declarer_pret_sfd(db: SessionSQLAlchemy, *, utilisatrice_id: int, nom_sfd: str,
                       montant_total_fcfa: int, duree_mois: int, echeance_mensuelle_fcfa: int,
                       session_id: int | None = None) -> None:
    """Item 10 : déclare le crédit SFD actif (remplace le précédent, comme

    declarer_capital_initial) et pré-crée tout l'échéancier (une ligne
    EcheanceSfd par mois de durée, numérotée, date prévue déjà calculée via
    _ajouter_mois) - la "Fiche 5" papier (documentation Fadima, 2026-11-17)
    montre un échéancier de 12 lignes connu dès la déclaration du crédit,
    pas rempli ligne par ligne au fil du temps.
    """
    utilisatrice = db.get(Utilisatrice, utilisatrice_id)
    if utilisatrice is None:
        return
    maintenant = datetime.now(timezone.utc)
    utilisatrice.nom_sfd = nom_sfd
    utilisatrice.montant_total_sfd_fcfa = montant_total_fcfa
    utilisatrice.duree_mois_sfd = duree_mois
    utilisatrice.echeance_mensuelle_sfd_fcfa = echeance_mensuelle_fcfa
    utilisatrice.date_declaration_sfd = maintenant
    # Une nouvelle déclaration remplace l'ancien échéancier : on repart d'un
    # programme propre plutôt que de mélanger deux programmes différents
    # dans la même liste de lignes (même principe que capital_initial).
    db.query(EcheanceSfd).filter_by(utilisatrice_id=utilisatrice_id).delete()
    for n in range(1, duree_mois + 1):
        db.add(EcheanceSfd(utilisatrice_id=utilisatrice_id, numero=n,
                            date_prevue=_ajouter_mois(maintenant, n),
                            montant_prevu=echeance_mensuelle_fcfa, session_id=session_id))
    db.commit()


def enregistrer_paiement_sfd(db: SessionSQLAlchemy, *, utilisatrice_id: int, montant_fcfa: int,
                               session_id: int | None = None) -> EcheanceSfd:
    """Item 11 : remplit la prochaine échéance non payée (le plus petit

    "numero" avec date_reelle vide). S'il n'en reste aucune (programme
    épuisé, ou aucune déclaration SFD existante), le paiement est quand même
    enregistré dans une ligne supplémentaire plutôt que perdu silencieusement
    (principe du module, voir son docstring en tête de fichier). Limite v1
    assumée : un paiement ne se répartit jamais sur plusieurs échéances,
    même si son montant dépasse le montant prévu d'une échéance.
    """
    ligne = (db.query(EcheanceSfd)
             .filter_by(utilisatrice_id=utilisatrice_id)
             .filter(EcheanceSfd.date_reelle.is_(None))
             .order_by(EcheanceSfd.numero.asc())
             .first())
    if ligne is None:
        dernier = (db.query(EcheanceSfd).filter_by(utilisatrice_id=utilisatrice_id)
                   .order_by(EcheanceSfd.numero.desc()).first())
        ligne = EcheanceSfd(utilisatrice_id=utilisatrice_id, numero=(dernier.numero + 1) if dernier else 1)
        db.add(ligne)
    ligne.date_reelle = datetime.now(timezone.utc)
    ligne.montant_paye = montant_fcfa
    ligne.session_id = session_id
    db.commit()
    db.refresh(ligne)
    return ligne


def bilan_pret_sfd(db: SessionSQLAlchemy, utilisatrice_id: int) -> dict:
    """Item 12 (lecture seule) : reste à payer et montant de la prochaine

    échéance sur le crédit SFD actif.
    """
    utilisatrice = db.get(Utilisatrice, utilisatrice_id)
    montant_total = (utilisatrice.montant_total_sfd_fcfa or 0) if utilisatrice else 0
    lignes = (db.query(EcheanceSfd).filter_by(utilisatrice_id=utilisatrice_id)
              .order_by(EcheanceSfd.numero.asc()).all())
    total_paye = sum(l.montant_paye or 0 for l in lignes)
    prochaine = next((l for l in lignes if l.date_reelle is None), None)
    return {
        "nom_sfd": (utilisatrice.nom_sfd or "") if utilisatrice else "",
        "montant_total_fcfa": montant_total,
        "reste_a_payer_fcfa": max(montant_total - total_paye, 0),
        "prochaine_echeance_fcfa": prochaine.montant_prevu if prochaine else None,
        "echeances": lignes,
    }


def bilan_utilisatrice(db: SessionSQLAlchemy, utilisatrice_id: int, limite_transactions: int = 10) -> dict:
    """Résumé en lecture seule pour le tableau de bord de l'utilisatrice elle-même

    (écran "bilan" de l'application mobile - différent du dashboard admin ABIC,
    voir moteur/admin/, qui agrège par coopérative, jamais le détail d'une
    seule utilisatrice vu par elle-même). Même principe que calculer_capital :
    uniquement des lectures agrégées, aucune écriture.
    """
    transactions_toutes = db.query(Transaction).filter_by(utilisatrice_id=utilisatrice_id).all()
    total_ventes = sum(t.montant_fcfa for t in transactions_toutes if t.type == "vente")
    total_depenses = sum(t.montant_fcfa for t in transactions_toutes if t.type == "depense")

    dernieres = (db.query(Transaction)
                 .filter_by(utilisatrice_id=utilisatrice_id)
                 .order_by(Transaction.date.desc())
                 .limit(limite_transactions).all())

    # Seulement les dettes encore actives (montant_du != 0) : un client soldé
    # n'a pas besoin d'apparaître dans le bilan.
    dettes = (db.query(Client)
              .filter_by(utilisatrice_id=utilisatrice_id)
              .filter(Client.montant_du != 0)
              .order_by(Client.date_dernier_mouvement.desc()).all())

    dettes_fournisseurs = (db.query(Fournisseur)
                            .filter_by(utilisatrice_id=utilisatrice_id)
                            .filter(Fournisseur.montant_du != 0)
                            .order_by(Fournisseur.date_dernier_mouvement.desc()).all())

    stock = db.query(Stock).filter_by(utilisatrice_id=utilisatrice_id).all()

    return {
        "capital": calculer_capital(db, utilisatrice_id),
        "total_ventes": total_ventes,
        "total_depenses": total_depenses,
        "transactions": [
            {"type": t.type, "article": t.article, "quantite": t.quantite,
             "montant_fcfa": t.montant_fcfa, "date": t.date}
            for t in dernieres
        ],
        "dettes_clients": [{"nom": c.nom_ou_code, "montant_du": c.montant_du} for c in dettes],
        "dettes_fournisseurs": [{"nom": f.nom_ou_code, "montant_du": f.montant_du} for f in dettes_fournisseurs],
        "stock": [{"article": s.article, "quantite": s.quantite_actuelle, "seuil_alerte": s.seuil_alerte}
                  for s in stock],
    }


def consulter_client(db: SessionSQLAlchemy, utilisatrice_id: int, nom_client: str) -> Client | None:
    return (db.query(Client)
            .filter_by(utilisatrice_id=utilisatrice_id, nom_ou_code=nom_client)
            .one_or_none())


def consulter_stock(db: SessionSQLAlchemy, utilisatrice_id: int, article: str) -> Stock | None:
    return (db.query(Stock)
            .filter_by(utilisatrice_id=utilisatrice_id, article=article)
            .one_or_none())


def expirer_sessions_anciennes(db: SessionSQLAlchemy, minutes: int = 30) -> list[int]:
    """Marque "expiree" toute session restée "incomplete" depuis plus de `minutes`.

    Sans ça, une utilisatrice qui raccroche/ferme l'onglet en plein milieu
    d'une confirmation laisse une session ouverte indéfiniment (ligne en base
    ET état en mémoire dans AgentVocal._etats, voir agent_vocal.py) : appelé à
    chaque nouvelle session (balayage paresseux, pas de tâche planifiée à
    faire tourner séparément). Renvoie les id expirés pour que l'appelant
    purge aussi son état en mémoire.
    """
    limite = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    perimees = (db.query(SessionAppel)
                .filter(SessionAppel.statut == "incomplete", SessionAppel.date_debut < limite)
                .all())
    ids = [s.id for s in perimees]
    for s in perimees:
        s.statut = "expiree"
        s.date_fin = datetime.now(timezone.utc)
    if ids:
        db.commit()
    return ids


def journaliser(db: SessionSQLAlchemy, *, session_id: int | None, etape: str,
                 confiance: str, resultat: str) -> None:
    """Observabilité par construction (section 8) : jamais le texte brut de l'audio ici,
    seulement l'étape, le score de confiance et le résultat.
    """
    db.add(JournalEvenement(session_id=session_id, etape=etape, confiance=confiance, resultat=resultat))
    db.commit()


# Fonctions de lecture dédiées à la génération des fiches PDF (moteur/fiches.py) :
# chacune renvoie l'historique ligne par ligne trié par date, pour que l'appelant
# calcule lui-même les soldes cumulés ligne à ligne (jamais stockés en double ici,
# même principe que calculer_capital/bilan_utilisatrice).
def ligne_journal(db: SessionSQLAlchemy, utilisatrice_id: int) -> list[Transaction]:
    """Fiche "Journal" : tout l'historique vente/dépense, le plus ancien d'abord."""
    return (db.query(Transaction)
            .filter_by(utilisatrice_id=utilisatrice_id)
            .filter(Transaction.type.in_(("vente", "depense")))
            .order_by(Transaction.date.asc())
            .all())


def ligne_mouvements_client(db: SessionSQLAlchemy, utilisatrice_id: int, nom_client: str) -> list[MouvementClient]:
    """Fiche 11 "Ventes à Crédit" pour un client donné."""
    client = consulter_client(db, utilisatrice_id, nom_client)
    if client is None:
        return []
    return (db.query(MouvementClient)
            .filter_by(client_id=client.id)
            .order_by(MouvementClient.date.asc())
            .all())


def ligne_mouvements_fournisseur(db: SessionSQLAlchemy, utilisatrice_id: int,
                                   nom_fournisseur: str) -> list[MouvementFournisseur]:
    """Fiche 12 "Achats à Crédit" pour un fournisseur donné."""
    fournisseur = consulter_fournisseur(db, utilisatrice_id, nom_fournisseur)
    if fournisseur is None:
        return []
    return (db.query(MouvementFournisseur)
            .filter_by(fournisseur_id=fournisseur.id)
            .order_by(MouvementFournisseur.date.asc())
            .all())


def ligne_mouvements_stock(db: SessionSQLAlchemy, utilisatrice_id: int, article: str) -> list[MouvementStock]:
    """Carte/Fiche de stock pour un article donné."""
    return (db.query(MouvementStock)
            .filter_by(utilisatrice_id=utilisatrice_id, article=article)
            .order_by(MouvementStock.date.asc())
            .all())


def lister_tiers(db: SessionSQLAlchemy, utilisatrice_id: int) -> dict:
    """Noms de clients/fournisseurs/articles connus pour cette utilisatrice -

    alimente les listes déroulantes du panneau "Fiches" côté application
    mobile (voir moteur/web/index.html), pour éviter de retaper un nom à la
    main au moment de choisir quelle fiche générer.
    """
    clients = [c.nom_ou_code for c in db.query(Client).filter_by(utilisatrice_id=utilisatrice_id).all()]
    fournisseurs = [f.nom_ou_code for f in db.query(Fournisseur).filter_by(utilisatrice_id=utilisatrice_id).all()]
    articles = [s.article for s in db.query(Stock).filter_by(utilisatrice_id=utilisatrice_id).all()]
    return {"clients": clients, "fournisseurs": fournisseurs, "articles": articles}
