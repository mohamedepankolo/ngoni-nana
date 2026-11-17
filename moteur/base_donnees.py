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
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, create_engine
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

    db.commit()
    db.refresh(t)
    return t


def enregistrer_mouvement_client(db: SessionSQLAlchemy, *, utilisatrice_id: int,
                                   nom_client: str, montant_fcfa: int, est_un_paiement: bool) -> Client:
    """Cas 5 : nouvelle dette (montant positif) ou paiement reçu (négatif sur la dette)."""
    client = (db.query(Client)
              .filter_by(utilisatrice_id=utilisatrice_id, nom_ou_code=nom_client)
              .one_or_none())
    if client is None:
        client = Client(utilisatrice_id=utilisatrice_id, nom_ou_code=nom_client, montant_du=0)
        db.add(client)
    client.montant_du = (client.montant_du or 0) + (-montant_fcfa if est_un_paiement else montant_fcfa)
    client.date_dernier_mouvement = datetime.now(timezone.utc)
    db.commit()
    db.refresh(client)
    return client


def enregistrer_mouvement_fournisseur(db: SessionSQLAlchemy, *, utilisatrice_id: int,
                                        nom_fournisseur: str, montant_fcfa: int,
                                        est_un_paiement: bool) -> Fournisseur:
    """Symétrique de enregistrer_mouvement_client : nouvelle dette (achat à

    crédit, item 5) ou paiement fait au fournisseur (échéance/dépôt, item 6).
    """
    fournisseur = (db.query(Fournisseur)
                   .filter_by(utilisatrice_id=utilisatrice_id, nom_ou_code=nom_fournisseur)
                   .one_or_none())
    if fournisseur is None:
        fournisseur = Fournisseur(utilisatrice_id=utilisatrice_id, nom_ou_code=nom_fournisseur, montant_du=0)
        db.add(fournisseur)
    fournisseur.montant_du = (fournisseur.montant_du or 0) + (-montant_fcfa if est_un_paiement else montant_fcfa)
    fournisseur.date_dernier_mouvement = datetime.now(timezone.utc)
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
                                  article: str, quantite: int) -> tuple[Stock, bool]:
    """Item 8 du menu : "stock initial" si aucune ligne n'existe encore pour

    cet article (la quantité REMPLACE, comme une première déclaration),
    "réapprovisionnement" si une ligne existe déjà (la quantité s'AJOUTE à
    l'existant) - même distinction que capital_declaration/capital_ajout,
    mais décidée ici plutôt que dans moteur_decision.py (couche pure, sans
    accès à la base) : seule cette fonction sait si une ligne existe déjà.
    Renvoie (ligne_stock, est_une_declaration_initiale) pour que l'appelant
    choisisse le bon message de confirmation si besoin.
    """
    ligne = (db.query(Stock)
             .filter_by(utilisatrice_id=utilisatrice_id, article=article)
             .one_or_none())
    if ligne is None:
        ligne = Stock(utilisatrice_id=utilisatrice_id, article=article, quantite_actuelle=quantite, seuil_alerte=0)
        db.add(ligne)
        db.commit()
        db.refresh(ligne)
        return ligne, True
    (db.query(Stock).filter_by(id=ligne.id)
     .update({Stock.quantite_actuelle: Stock.quantite_actuelle + quantite}))
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
