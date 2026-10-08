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


def calculer_capital(db: SessionSQLAlchemy, utilisatrice_id: int) -> int:
    """Recettes - dépenses - dettes clients + dettes fournisseurs (formule de l'architecture).

    "Dettes fournisseurs" n'a pas encore de table dédiée dans ce premier jet
    (non observée dans phrases_reelles.csv ni dans le parcours utilisateur
    actuel) : traitée comme 0 pour l'instant, à corriger si Fadima confirme
    ce cas d'usage.
    """
    transactions = db.query(Transaction).filter_by(utilisatrice_id=utilisatrice_id).all()
    recettes = sum(t.montant_fcfa for t in transactions if t.type == "vente")
    depenses = sum(t.montant_fcfa for t in transactions if t.type == "depense")
    dettes_clients = sum(c.montant_du or 0 for c in
                          db.query(Client).filter_by(utilisatrice_id=utilisatrice_id).all())
    return recettes - depenses - dettes_clients


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
