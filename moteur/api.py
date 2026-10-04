"""API applicative (Architecture_Technique_NGONI_NANA.docx, section 3.6).

Implémente les 5 endpoints du document d'architecture. Point d'entrée /call
en texte déjà transcrit pour l'instant (pas en audio) : la passerelle de
téléphonie (R2) et l'hébergement (R1) ne sont pas tranchés, donc rien ne peut
encore faire arriver un vrai flux audio jusqu'ici. Le jour où l'un des deux
est débloqué, l'audio entrant n'a qu'à être transcrit avant d'appeler la même
fonction `AgentVocal.traiter_texte` que ce qu'utilise déjà /call.

Authentification : jeton statique simple (API_TOKEN, variable d'environnement),
exigé sur tous les endpoints sauf /health, conformément à l'architecture.
Volontairement minimal pour ce premier jet : la hiérarchie de rôles complète
(section 4 de l'architecture — utilisatrice / animatrice / gestionnaire /
administratrice) suppose des comptes réels et reste à construire, pas un
prérequis pour tester le pipeline ASR -> moteur -> TTS de bout en bout.
"""
import os

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from moteur import base_donnees as db
from moteur.agent_vocal import AgentVocal

app = FastAPI(title="N'GONI NANA — API")

MODULES_GERME = [
    {"action": "vente", "description": "Enregistrer une vente"},
    {"action": "depense", "description": "Enregistrer une dépense (y compris un achat)"},
    {"action": "capital", "description": "Consulter son capital"},
    {"action": "client", "description": "Suivre la dette d'un client, enregistrer un paiement"},
    {"action": "stock", "description": "Consulter et gérer son stock"},
]


# Un seul moteur SQLAlchemy pour tout le processus (pas un par requête : sur
# SQLite, ça rouvrirait un nouveau fichier/connexion à chaque appel, sans
# jamais les refermer). `_SessionLocal` reste la fabrique à passer partout.
_engine = db.get_engine()
_SessionLocal = db.get_session_factory(_engine)

# Une seule instance partagée par le processus : l'état des sessions en
# mémoire (voir agent_vocal.py) doit survivre entre deux appels HTTP.
_agent = AgentVocal(session_factory=_SessionLocal)


def obtenir_agent() -> AgentVocal:
    return _agent


def verifier_jeton(authorization: str | None = Header(default=None)) -> None:
    jeton_attendu = os.environ.get("API_TOKEN")
    if not jeton_attendu:
        # Pas de jeton configuré : on refuse par défaut plutôt que d'ouvrir
        # l'API sans authentification (défense en profondeur, section 1).
        raise HTTPException(status_code=503, detail="API_TOKEN non configuré côté serveur.")
    if authorization != f"Bearer {jeton_attendu}":
        raise HTTPException(status_code=401, detail="Jeton invalide ou absent.")


class CreerSessionRequete(BaseModel):
    utilisatrice_id: int
    canal: str = "voix"


class AppelRequete(BaseModel):
    session_id: int
    utilisatrice_id: int
    texte: str


@app.get("/health")
def health():
    """Vérifie l'état réel des dépendances, pas seulement que l'API répond (section 7)."""
    etat = {"api": "ok"}
    try:
        bd = _SessionLocal()
        bd.execute(db.Base.metadata.tables["cooperatives"].select().limit(1))
        etat["base_de_donnees"] = "ok"
    except Exception as e:  # noqa: BLE001 — on veut remonter n'importe quelle panne ici
        etat["base_de_donnees"] = f"erreur: {e}"
    etat["asr"] = "non chargé (chargement à la demande, voir asr_robotsmali.py)"
    etat["tts"] = "non chargé (chargement à la demande, voir tts_maliba.py)"
    return etat


@app.get("/modules", dependencies=[Depends(verifier_jeton)])
def modules():
    return {"modules": MODULES_GERME}


@app.post("/session", dependencies=[Depends(verifier_jeton)])
def creer_session(requete: CreerSessionRequete, agent: AgentVocal = Depends(obtenir_agent)):
    session_id = agent.demarrer_session(requete.utilisatrice_id, canal=requete.canal)
    return {"session_id": session_id}


@app.get("/session/{session_id}", dependencies=[Depends(verifier_jeton)])
def consulter_session(session_id: int):
    bd = _SessionLocal()
    s = bd.get(db.SessionAppel, session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Session introuvable.")
    return {"session_id": s.id, "statut": s.statut, "canal": s.canal,
             "date_debut": s.date_debut, "date_fin": s.date_fin}


@app.post("/call", dependencies=[Depends(verifier_jeton)])
def appeler(requete: AppelRequete, agent: AgentVocal = Depends(obtenir_agent)):
    resultat = agent.traiter_texte(requete.session_id, requete.utilisatrice_id, requete.texte)
    return {
        "message": resultat["message"],
        "intention": resultat["contrat"]["intention"],
        "confiance": resultat["contrat"]["confiance"],
        "action": resultat["contrat"]["action"],
        "champs": resultat["contrat"]["champs"],
        "audio": resultat["audio"],
    }


class SmsRequete(BaseModel):
    utilisatrice_id: int
    message: str


@app.post("/sms", dependencies=[Depends(verifier_jeton)])
def envoyer_sms(requete: SmsRequete):
    """Notifications sortantes (section 3.6). Pas de passerelle SMS choisie à ce
    jour (dépend de R2, téléphonie) : journalise l'intention d'envoi sans
    envoyer réellement de SMS, pour ne pas donner une fausse impression de
    fonctionnalité livrée.
    """
    bd = _SessionLocal()
    db.journaliser(bd, session_id=None, etape="sms",
                    confiance="haute", resultat=f"à envoyer à {requete.utilisatrice_id}: {requete.message}")
    return {"statut": "journalisé, envoi réel non implémenté (R2 non tranché)"}
