"""API applicative (Architecture_Technique_NGONI_NANA.docx, section 3.6).

Implémente les 5 endpoints du document d'architecture, plus /call_audio (voir
plus bas) et une page de test navigateur (/web). Pas de vraie téléphonie
branchée (R2 toujours ouvert) : /call_audio simule ce que ferait un appel
réel, en recevant un fichier audio déjà enregistré plutôt qu'un flux en
direct. Le jour où la téléphonie et l'hébergement (R1) sont tranchés, le flux
entrant n'a qu'à être transcrit avant d'appeler la même fonction
`AgentVocal.traiter_texte` que ce qu'utilisent déjà /call et /call_audio.

Authentification : jeton statique simple (API_TOKEN, variable d'environnement),
exigé sur tous les endpoints sauf /health, conformément à l'architecture.
Volontairement minimal pour ce premier jet : la hiérarchie de rôles complète
(section 4 de l'architecture — utilisatrice / animatrice / gestionnaire /
administratrice) suppose des comptes réels et reste à construire, pas un
prérequis pour tester le pipeline ASR -> moteur -> TTS de bout en bout.
"""
import base64
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from moteur import base_donnees as db
from moteur.admin.routes import router as admin_router
from moteur.agent_vocal import AgentVocal

load_dotenv()  # lit .env (API_TOKEN, HF_TOKEN, DATABASE_URL) s'il existe, jamais commité

app = FastAPI(title="N'GONI NANA — API")

# Page de test "appui pour parler" (voir moteur/web/README.md) : usage
# interne/développement uniquement, pas une interface destinée aux
# utilisatrices finales (le vrai canal reste la téléphonie, R2).
app.mount("/web", StaticFiles(directory=str(Path(__file__).parent / "web"), html=True), name="web")


@app.get("/")
def racine():
    return RedirectResponse("/web/")


app.include_router(admin_router)

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

# Dashboard admin ABIC (section 3.8) : mêmes moteur/fabrique de session que
# le reste de l'API, exposés via app.state pour que moteur/admin/routes.py
# n'ait pas à importer ce module (éviterait un import circulaire : api.py
# inclura ce routeur plus bas).
app.state.admin_session_factory = _SessionLocal


def obtenir_agent() -> AgentVocal:
    return _agent


# Chargement paresseux : l'ASR (NeMo) et le TTS (Space Gradio) sont lourds et
# dépendent d'un jeton HF (voir asr_robotsmali.py / tts_maliba.py). Les
# endpoints texte (/call) marchent sans eux ; seul /call_audio en a besoin.
_transcrire = None
_syntheser = None


def _obtenir_transcrire():
    global _transcrire
    if _transcrire is None:
        from moteur.asr_robotsmali import obtenir_transcripteur
        _transcrire = obtenir_transcripteur()
    return _transcrire


def _obtenir_syntheser():
    global _syntheser
    if _syntheser is None:
        from moteur.tts_maliba import obtenir_synthetiseur
        _syntheser = obtenir_synthetiseur()
    return _syntheser


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


@app.post("/demo/bootstrap", dependencies=[Depends(verifier_jeton)])
def bootstrap_demo():
    """Crée (une seule fois) une coopérative et une utilisatrice de démonstration,
    pour que la page de test n'ait pas à gérer d'inscription réelle.
    """
    bd = _SessionLocal()
    u = bd.get(db.Utilisatrice, 1)
    if u is None:
        coop = db.Cooperative(nom="ABIC Dioïla (démo)", site="Dioïla")
        bd.add(coop)
        bd.commit()
        u = db.Utilisatrice(id=1, code_anonyme="DEMO", telephone_hash="demo", cooperative_id=coop.id)
        bd.add(u)
        bd.commit()
        bd.refresh(u)
    return {"utilisatrice_id": u.id}


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


@app.post("/call_audio", dependencies=[Depends(verifier_jeton)])
async def appeler_en_audio(session_id: int = Form(...), utilisatrice_id: int = Form(...),
                            fichier: UploadFile = File(...)):
    """Même chose que /call, mais à partir d'un enregistrement audio brut (ex. navigateur).

    Convertit en WAV 16 kHz (ffmpeg), transcrit (ASR réel, RobotsMali/NeMo),
    passe le texte à l'agent vocal, puis synthétise la réponse (TTS réel,
    MALIBA-AI) et la renvoie encodée en base64 pour qu'une page web puisse la
    jouer directement, sans endpoint binaire séparé.
    """
    from moteur.asr_robotsmali import convertir_en_wav

    suffixe_entree = Path(fichier.filename or "audio.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffixe_entree, delete=False) as brut:
        brut.write(await fichier.read())
        chemin_brut = brut.name
    chemin_wav = chemin_brut + ".wav"

    try:
        convertir_en_wav(chemin_brut, chemin_wav)
        if os.environ.get("NGONI_DEBUG_AUDIO"):
            # Diagnostic temporaire (désactivé par défaut) : garde une copie du
            # brut et du WAV converti pour inspecter pourquoi une transcription
            # reviendrait vide depuis un enregistrement navigateur.
            import shutil
            import time
            debug_dir = Path("debug_audio")
            debug_dir.mkdir(exist_ok=True)
            horodatage = int(time.time())
            shutil.copy(chemin_brut, debug_dir / f"{horodatage}{suffixe_entree}")
            shutil.copy(chemin_wav, debug_dir / f"{horodatage}.wav")
        texte_reconnu = _obtenir_transcrire()(chemin_wav)
    finally:
        os.unlink(chemin_brut)
        Path(chemin_wav).unlink(missing_ok=True)

    resultat = _agent.traiter_texte(session_id, utilisatrice_id, texte_reconnu)

    chemin_audio_reponse = _obtenir_syntheser()(resultat["message"])
    with open(chemin_audio_reponse, "rb") as f:
        audio_base64 = base64.b64encode(f.read()).decode()
    type_audio = Path(chemin_audio_reponse).suffix.lstrip(".") or "wav"

    return {
        "texte_reconnu": texte_reconnu,
        "message": resultat["message"],
        "intention": resultat["contrat"]["intention"],
        "action": resultat["contrat"]["action"],
        "champs": resultat["contrat"]["champs"],
        "audio_base64": audio_base64,
        "type_audio": type_audio,
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
