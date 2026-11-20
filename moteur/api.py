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
(section 4 de l'architecture : utilisatrice / animatrice / gestionnaire /
administratrice) suppose des comptes réels et reste à construire, pas un
prérequis pour tester le pipeline ASR -> moteur -> TTS de bout en bout.
"""
import base64
import io
import json
import logging
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from moteur import base_donnees as db
from moteur import fiches
from moteur import messages_bambara as msg
from moteur.admin.routes import router as admin_router
from moteur.agent_vocal import AgentVocal

load_dotenv()  # lit .env (API_TOKEN, HF_TOKEN, DATABASE_URL) s'il existe, jamais commité

logger = logging.getLogger("ngoni_nana")

# Taille max d'un enregistrement vocal brut (un tour de parole dure quelques
# secondes) : au-delà, probablement un flux bloqué plutôt qu'un vrai
# enregistrement, à rejeter avant de le charger entièrement en mémoire.
TAILLE_MAX_AUDIO_OCTETS = 15 * 1024 * 1024  # 15 Mo

# Message d'accueil : voix humaine réelle plutôt que le TTS synthétique, si
# ce fichier local existe (2026-11-17, demande explicite - un des 5
# enregistrements de l'équipe terrain couvrant les 9 choix du menu, bien
# plus naturel qu'une synthèse, et sans le problème de vocabulaire bambara
# non validé pour les items 4 à 8, voir messages_bambara.menu_principal).
# Fichier dans ressource/ : jamais commité sur GitHub (voix de vraies
# personnes, pas d'accord explicite pour une publication publique) - d'où
# le repli silencieux sur le TTS si absent (ex. sur un autre poste), pas une
# erreur. Choix du fichier à changer ici une fois l'équipe a écouté les 5 et
# tranché (voir ressource/enregistrements_menu_bambara_2026-11-17/).
CHEMIN_AUDIO_ACCUEIL_HUMAIN = (
    Path(__file__).resolve().parent.parent
    / "ressource" / "enregistrements_menu_bambara_2026-11-17" / "personne_1.ogg"
)


@asynccontextmanager
async def _cycle_de_vie(_app: FastAPI):
    """Charge l'ASR et le TTS au démarrage plutôt qu'au premier appel réel.

    Mesuré en conditions réelles (2026-10-08) : le premier /call_audio après
    un démarrage du serveur paie le chargement du modèle NeMo (plusieurs
    secondes sur CPU, "CUDA is not available") PLUS la connexion au Space
    Gradio du TTS, assez pour dépasser le délai maximal côté PWA
    (DELAI_MAX_MS, index.html) : l'utilisatrice voit le bouton tourner puis
    passer en erreur alors que la vraie transcription a fini par aboutir,
    trop tard. Activé seulement si NGONI_PREWARM=1 (jamais en test : charger
    le vrai modèle NeMo ou joindre le vrai Space HF à chaque lancement de la
    suite de tests serait lent et dépendant du réseau).
    """
    if os.environ.get("NGONI_PREWARM") == "1":
        try:
            _obtenir_transcrire()
            logger.info("ASR préchargé.")
        except Exception:
            logger.exception("Préchauffage ASR impossible (nemo-toolkit absent ? voir requirements.txt).")
        try:
            _obtenir_syntheser()
            logger.info("TTS préchargé.")
        except Exception:
            logger.exception("Préchauffage TTS impossible (réseau/HF_TOKEN ?).")
    yield


app = FastAPI(title="N'GONI NANA : API", lifespan=_cycle_de_vie)

# Necessaire pour l'appli mobile (Capacitor) : sa page est chargee depuis une
# origine locale (https://localhost), differente de celle du serveur - sans
# CORS, le navigateur embarque bloque silencieusement la requete ("Failed to
# fetch") avant meme qu'elle n'atteigne l'API, independamment du reseau ou du
# jeton. Sans impact sur la securite : le jeton (verifier_jeton, plus bas)
# reste exige sur chaque endpoint, CORS ne fait qu'autoriser le navigateur a
# LIRE la reponse d'une origine differente.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/web/config.js")
def config_web():
    """Fournit le jeton API à la page de test sans que l'équipe ait à le

    taper à la main sur chaque appareil (geste caché 5 appuis en secours
    seulement, voir index.html). Pas d'authentification ici par construction
    (une page qui doit D'ABORD obtenir le jeton ne peut pas déjà le
    présenter) : cohérent avec le reste de ce module, qui documente déjà ce
    jeton comme une protection minimale contre les accès accidentels, pas un
    vrai contrôle d'accès (section 1, à construire pour de vrai avec des
    comptes réels). Enregistré AVANT le mount StaticFiles ci-dessous pour
    que cette route explicite soit essayée en premier.
    """
    jeton = os.environ.get("API_TOKEN", "")
    return PlainTextResponse(f"window.NGONI_JETON = {json.dumps(jeton)};\n", media_type="application/javascript")


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


def _syntheser_message(texte: str) -> str:
    """Synthétise un message complet (voir syntheser_par_phrases,
    tts_maliba.py) : une vraie pause entre chaque phrase pour les messages
    qui en contiennent plusieurs (le menu principal notamment), sans coût
    ajouté pour les messages à une seule phrase (la grande majorité)."""
    from moteur.tts_maliba import syntheser_par_phrases
    return syntheser_par_phrases(_obtenir_syntheser(), texte)


# Message audio de secours, pré-synthétisé une seule fois (voir
# scripts/generer_audio_secours.py) et bundlé avec l'app plutôt que généré à
# la volée : si le TTS en ligne (Space Gradio, section tts_maliba.py) est en
# panne ou injoignable, l'utilisatrice doit quand même entendre quelque chose
# ("Ne ma a faamu. A fɔ tuguni." = "je n'ai pas compris, répète") plutôt qu'un
# silence total. Chargé une fois en mémoire, jamais régénéré par requête.
_CHEMIN_AUDIO_SECOURS = Path(__file__).parent / "web" / "assets" / "erreur.wav"
_audio_secours_base64: str | None = None


def _obtenir_audio_secours() -> str | None:
    global _audio_secours_base64
    if _audio_secours_base64 is None and _CHEMIN_AUDIO_SECOURS.exists():
        _audio_secours_base64 = base64.b64encode(_CHEMIN_AUDIO_SECOURS.read_bytes()).decode()
    return _audio_secours_base64


def _reponse_secours(texte_reconnu: str | None, message: str, session_id: int | None = None) -> dict:
    # L'état de la session n'a pas bougé (l'échec arrive AVANT le moteur :
    # ASR/conversion en panne) : "attente" doit refléter ce qui était déjà
    # attendu, pas "menu" par défaut, sinon l'interface afficherait le mauvais
    # widget de saisie après une simple erreur réseau/micro.
    attente = _agent.etat_attente(session_id) if session_id is not None else "menu"
    return {
        "texte_reconnu": texte_reconnu,
        "message": message,
        "intention": None,
        "action": "reformuler",
        "champs": {},
        "audio_base64": _obtenir_audio_secours(),
        "type_audio": "wav",
        "attente": attente,
    }


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
        with _SessionLocal() as bd:
            bd.execute(db.Base.metadata.tables["cooperatives"].select().limit(1))
        etat["base_de_donnees"] = "ok"
    except Exception as e:  # noqa: BLE001 : on veut remonter n'importe quelle panne ici
        etat["base_de_donnees"] = f"erreur: {e}"
    etat["asr"] = "non chargé (chargement à la demande, voir asr_robotsmali.py)"
    etat["tts"] = "non chargé (chargement à la demande, voir tts_maliba.py)"
    return etat


@app.get("/modules", dependencies=[Depends(verifier_jeton)])
def modules():
    return {"modules": MODULES_GERME}


@app.post("/session", dependencies=[Depends(verifier_jeton)])
def creer_session(requete: CreerSessionRequete, agent: AgentVocal = Depends(obtenir_agent)):
    """Démarre une session ET renvoie le message d'accueil + menu numérique

    (menu_principal, messages_bambara.py), pour qu'une utilisatrice entende
    tout de suite ce qu'elle peut faire plutôt que d'appuyer sur le bouton
    sans savoir quoi dire (R2, menu numérique 1-6). L'audio est au mieux : si
    le TTS échoue, le texte reste disponible (journal de test), pas d'erreur
    - contrairement à /call_audio, pas de son de secours ici, un bip d'erreur
    au tout premier contact donnerait l'impression à tort que quelque chose a
    déjà mal tourné.
    """
    session_id = agent.demarrer_session(requete.utilisatrice_id, canal=requete.canal)
    message = msg.menu_principal()
    audio_base64, type_audio = None, "wav"
    try:
        if CHEMIN_AUDIO_ACCUEIL_HUMAIN.exists():
            chemin_audio = str(CHEMIN_AUDIO_ACCUEIL_HUMAIN)
        else:
            chemin_audio = _syntheser_message(message)
        with open(chemin_audio, "rb") as f:
            audio_base64 = base64.b64encode(f.read()).decode()
        type_audio = Path(chemin_audio).suffix.lstrip(".") or "wav"
    except Exception:
        logger.exception("Échec TTS pour le message d'accueil (session %s)", session_id)
    return {"session_id": session_id, "message": message, "audio_base64": audio_base64,
            "type_audio": type_audio, "attente": "menu"}


@app.get("/session/{session_id}", dependencies=[Depends(verifier_jeton)])
def consulter_session(session_id: int):
    with _SessionLocal() as bd:
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
    with _SessionLocal() as bd:
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
    """Comme /call_audio, mais à partir de texte déjà disponible (ex. un choix

    de menu tapé "1".."6" sur la page de test, voir web/index.html) : évite
    de repasser par le micro pour tester rapidement le menu numérique (R2).
    Synthétise aussi la réponse en audio (avant : texte seul, jamais parlé),
    avec le même repli que /call_audio si le TTS échoue.
    """
    resultat = agent.traiter_texte(requete.session_id, requete.utilisatrice_id, requete.texte)
    audio_base64, type_audio = None, "wav"
    try:
        chemin_audio = _syntheser_message(resultat["message"])
        with open(chemin_audio, "rb") as f:
            audio_base64 = base64.b64encode(f.read()).decode()
        type_audio = Path(chemin_audio).suffix.lstrip(".") or "wav"
    except Exception:
        logger.exception("Échec TTS pour /call (session %s)", requete.session_id)
        audio_base64 = _obtenir_audio_secours()
    return {
        "message": resultat["message"],
        "intention": resultat["contrat"]["intention"],
        "confiance": resultat["contrat"]["confiance"],
        "action": resultat["contrat"]["action"],
        "champs": resultat["contrat"]["champs"],
        "audio_base64": audio_base64,
        "type_audio": type_audio,
        "attente": resultat["attente"],
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

    contenu = await fichier.read()
    if not contenu:
        return _reponse_secours(None, msg.reformulation(0), session_id)
    if len(contenu) > TAILLE_MAX_AUDIO_OCTETS:
        logger.warning("Enregistrement rejeté (%d octets > limite) pour la session %s", len(contenu), session_id)
        return _reponse_secours(None, msg.reformulation(0), session_id)

    suffixe_entree = Path(fichier.filename or "audio.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffixe_entree, delete=False) as brut:
        brut.write(contenu)
        chemin_brut = brut.name
    chemin_wav = chemin_brut + ".wav"

    texte_reconnu = None
    try:
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
        except Exception:
            # Conversion ffmpeg ou ASR en panne (fichier corrompu, modèle
            # indisponible, etc.) : jamais un 500 muet pour une utilisatrice au
            # téléphone, elle doit entendre qu'il faut réessayer (voir
            # _reponse_secours, section audit robustesse).
            logger.exception("Échec conversion/ASR pour la session %s", session_id)
            return _reponse_secours(None, msg.reformulation(0), session_id)
    finally:
        os.unlink(chemin_brut)
        Path(chemin_wav).unlink(missing_ok=True)

    if not texte_reconnu or not texte_reconnu.strip():
        return _reponse_secours(texte_reconnu, msg.reformulation(0), session_id)

    try:
        resultat = _agent.traiter_texte(session_id, utilisatrice_id, texte_reconnu)
    except Exception:
        logger.exception("Échec du moteur de décision pour la session %s", session_id)
        return _reponse_secours(texte_reconnu, msg.reformulation(0), session_id)

    try:
        chemin_audio_reponse = _syntheser_message(resultat["message"])
        with open(chemin_audio_reponse, "rb") as f:
            audio_base64 = base64.b64encode(f.read()).decode()
        type_audio = Path(chemin_audio_reponse).suffix.lstrip(".") or "wav"
    except Exception:
        # Le TTS en ligne a échoué, mais le moteur a bien traité la demande
        # (et, si l'action était "enregistrer", la transaction est déjà en
        # base : voir _conclure dans agent_vocal.py). On ne doit surtout pas
        # redire à l'utilisatrice de répéter son tour, ça créerait un doublon
        # si elle recommence. On renvoie le vrai message, avec la voix de
        # secours pré-enregistrée à la place de l'audio généré à la volée.
        logger.exception("Échec TTS pour la session %s (message texte conservé)", session_id)
        audio_base64 = _obtenir_audio_secours()
        type_audio = "wav"

    return {
        "texte_reconnu": texte_reconnu,
        "message": resultat["message"],
        "intention": resultat["contrat"]["intention"],
        "action": resultat["contrat"]["action"],
        "champs": resultat["contrat"]["champs"],
        "audio_base64": audio_base64,
        "type_audio": type_audio,
        "attente": resultat["attente"],
    }


@app.get("/bilan/{utilisatrice_id}", dependencies=[Depends(verifier_jeton)])
def bilan(utilisatrice_id: int):
    """Écran "bilan" de l'application mobile (lecture seule, section 3

    du vocal, "une partie bilan/résumé" demandée en plus du flux vocal) :
    capital, totaux ventes/dépenses, dernières transactions, dettes clients,
    stock. Voir moteur/base_donnees.bilan_utilisatrice - différent du
    dashboard admin ABIC (moteur/admin/), qui agrège par coopérative.
    """
    with _SessionLocal() as bd:
        return db.bilan_utilisatrice(bd, utilisatrice_id)


def _pdf(contenu: bytes, nom_fichier: str) -> StreamingResponse:
    """Même pattern que /admin/rapports.csv (StreamingResponse +

    Content-Disposition), juste media_type="application/pdf" et des octets
    PDF à la place d'un CSV.
    """
    return StreamingResponse(io.BytesIO(contenu), media_type="application/pdf",
                              headers={"Content-Disposition": f"attachment; filename={nom_fichier}"})


@app.get("/fiches/disponibles/{utilisatrice_id}", dependencies=[Depends(verifier_jeton)])
def fiches_disponibles(utilisatrice_id: int):
    """Noms de clients/fournisseurs/articles connus, pour les listes

    déroulantes du panneau "Fiches" (voir moteur/web/index.html) - évite de
    retaper un nom à la main au moment de choisir quelle fiche générer.
    """
    with _SessionLocal() as bd:
        return db.lister_tiers(bd, utilisatrice_id)


@app.get("/fiches/journal/{utilisatrice_id}", dependencies=[Depends(verifier_jeton)])
def fiche_journal(utilisatrice_id: int):
    with _SessionLocal() as bd:
        return _pdf(fiches.generer_pdf_journal(bd, utilisatrice_id), "journal.pdf")


@app.get("/fiches/vente_credit/{utilisatrice_id}", dependencies=[Depends(verifier_jeton)])
def fiche_vente_credit(utilisatrice_id: int, nom_client: str):
    with _SessionLocal() as bd:
        return _pdf(fiches.generer_pdf_vente_credit(bd, utilisatrice_id, nom_client), "ventes_a_credit.pdf")


@app.get("/fiches/achat_credit/{utilisatrice_id}", dependencies=[Depends(verifier_jeton)])
def fiche_achat_credit(utilisatrice_id: int, nom_fournisseur: str):
    with _SessionLocal() as bd:
        return _pdf(fiches.generer_pdf_achat_credit(bd, utilisatrice_id, nom_fournisseur), "achats_a_credit.pdf")


@app.get("/fiches/carte_stock/{utilisatrice_id}", dependencies=[Depends(verifier_jeton)])
def fiche_carte_stock(utilisatrice_id: int, article: str):
    with _SessionLocal() as bd:
        return _pdf(fiches.generer_pdf_carte_stock(bd, utilisatrice_id, article), "carte_de_stock.pdf")


@app.get("/fiches/sfd/{utilisatrice_id}", dependencies=[Depends(verifier_jeton)])
def fiche_sfd(utilisatrice_id: int):
    with _SessionLocal() as bd:
        return _pdf(fiches.generer_pdf_sfd(bd, utilisatrice_id), "suivi_sfd.pdf")


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
    with _SessionLocal() as bd:
        db.journaliser(bd, session_id=None, etape="sms",
                        confiance="haute", resultat=f"à envoyer à {requete.utilisatrice_id}: {requete.message}")
    return {"statut": "journalisé, envoi réel non implémenté (R2 non tranché)"}
