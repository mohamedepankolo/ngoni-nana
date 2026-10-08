import io
import os
import sys
import wave
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "asr_test" / "scripts"))

# Doivent être définies AVANT l'import de moteur.api : ce module construit son
# AgentVocal (et sa base de données) une seule fois, au chargement du module.
os.environ["API_TOKEN"] = "jeton-de-test"
DB_TEST = RACINE / "tests" / "_api_test.db"
# Repartir d'un fichier neuf à CHAQUE lancement (pas en fin de test) : sur
# Windows, SQLAlchemy/SQLite peut garder le fichier verrouillé après usage
# tant que le processus Python tourne, ce qui rend un `unlink` en fin de
# session peu fiable. Un fichier orphelin d'un run précédent (ex. process tué)
# ne gêne donc jamais le suivant. PermissionError : test_admin.py (collecté
# avant celui-ci) a déjà importé moteur.api et ouvert ce même fichier.
try:
    DB_TEST.unlink(missing_ok=True)
except PermissionError:
    pass
os.environ["DATABASE_URL"] = f"sqlite:///{DB_TEST}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from moteur import api as moteur_api  # noqa: E402
from moteur import base_donnees as db  # noqa: E402
from moteur.api import _agent, _SessionLocal, app  # noqa: E402

ENTETES = {"Authorization": "Bearer jeton-de-test"}


@pytest.fixture(autouse=True)
def base_propre():
    """Vide les tables entre chaque test : la base de l'API est un fichier partagé
    entre les tests (module importé une seule fois), pas une base en mémoire isolée.
    """
    yield
    bd = _SessionLocal()
    for table in reversed(db.Base.metadata.sorted_tables):
        bd.execute(table.delete())
    bd.commit()
    bd.close()
    # Les id SQLite peuvent être réutilisés après un DELETE complet (pas de
    # mot-clé AUTOINCREMENT ici) : purge aussi l'état en mémoire de l'agent
    # pour qu'un session_id réutilisé ne retrouve pas l'état d'un test précédent.
    _agent._etats.clear()
    moteur_api._transcrire = None
    moteur_api._syntheser = None


def test_health_ne_demande_aucune_authentification():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["base_de_donnees"] == "ok"


def test_endpoints_proteges_refusent_sans_jeton():
    client = TestClient(app)
    r = client.get("/modules")
    assert r.status_code == 401


def test_modules_liste_les_5_actions_du_menu():
    client = TestClient(app)
    r = client.get("/modules", headers=ENTETES)
    assert r.status_code == 200
    actions = {m["action"] for m in r.json()["modules"]}
    assert actions == {"vente", "depense", "capital", "client", "stock"}


def test_parcours_complet_session_puis_call():
    client = TestClient(app)

    bd = _SessionLocal()
    coop = db.Cooperative(nom="ABIC Dioïla")
    bd.add(coop)
    bd.commit()
    utilisatrice = db.Utilisatrice(code_anonyme="L01", telephone_hash="x", cooperative_id=coop.id)
    bd.add(utilisatrice)
    bd.commit()
    bd.refresh(utilisatrice)

    r = client.post("/session", json={"utilisatrice_id": utilisatrice.id}, headers=ENTETES)
    assert r.status_code == 200
    session_id = r.json()["session_id"]

    r = client.post("/call", headers=ENTETES, json={
        "session_id": session_id, "utilisatrice_id": utilisatrice.id,
        "texte": "n ye n ka paser sara kɛmɛ ni bi duuru",
    })
    assert r.status_code == 200
    corps = r.json()
    assert corps["intention"] == "depense"
    assert corps["action"] == "demander_confirmation"

    r = client.post("/call", headers=ENTETES, json={
        "session_id": session_id, "utilisatrice_id": utilisatrice.id, "texte": "owo",
    })
    assert r.json()["action"] == "enregistrer"

    r = client.get(f"/session/{session_id}", headers=ENTETES)
    assert r.json()["statut"] == "complete"


def _wav_silence(duree_s: float = 0.3) -> bytes:
    tampon = io.BytesIO()
    with wave.open(tampon, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * int(16000 * duree_s))
    return tampon.getvalue()


def test_call_audio_bout_en_bout_avec_asr_et_tts_factices(monkeypatch):
    """N'exerce pas les vrais modèles (ASR/TTS réels : voir README) : vérifie que
    /call_audio convertit bien l'audio (ffmpeg), appelle l'agent avec le texte
    transcrit, et renvoie une réponse audio encodée en base64.
    """
    monkeypatch.setattr(moteur_api, "_obtenir_transcrire",
                         lambda: (lambda chemin_wav: "n ye saga saba feere wa bi duuru"))
    monkeypatch.setattr(moteur_api, "_obtenir_syntheser",
                         lambda: (lambda texte: _ecrire_wav_temporaire()))

    client = TestClient(app)
    bd = _SessionLocal()
    coop = db.Cooperative(nom="ABIC Dioïla")
    bd.add(coop)
    bd.commit()
    u = db.Utilisatrice(code_anonyme="L01", telephone_hash="x", cooperative_id=coop.id)
    bd.add(u)
    bd.commit()
    bd.refresh(u)
    session_id = client.post("/session", json={"utilisatrice_id": u.id}, headers=ENTETES).json()["session_id"]

    r = client.post(
        "/call_audio", headers=ENTETES,
        data={"session_id": session_id, "utilisatrice_id": u.id},
        files={"fichier": ("tour.webm", _wav_silence(), "audio/wav")},
    )
    assert r.status_code == 200
    corps = r.json()
    assert corps["texte_reconnu"] == "n ye saga saba feere wa bi duuru"
    assert corps["intention"] == "vente"
    assert corps["audio_base64"]


def _ecrire_wav_temporaire() -> str:
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(_wav_silence(0.2))
        return f.name


def _demarrer_session(client):
    bd = _SessionLocal()
    coop = db.Cooperative(nom="ABIC Dioïla")
    bd.add(coop)
    bd.commit()
    u = db.Utilisatrice(code_anonyme="L01", telephone_hash="x", cooperative_id=coop.id)
    bd.add(u)
    bd.commit()
    bd.refresh(u)
    session_id = client.post("/session", json={"utilisatrice_id": u.id}, headers=ENTETES).json()["session_id"]
    return u.id, session_id


def test_call_audio_fichier_vide_renvoie_un_message_de_secours_sans_planter():
    # Un enregistrement vide (micro coupe trop tot, upload interrompu) ne doit
    # jamais faire planter l'appel : l'utilisatrice doit entendre qu'il faut
    # reessayer, pas un silence suivi d'une erreur serveur brute.
    client = TestClient(app)
    utilisatrice_id, session_id = _demarrer_session(client)

    r = client.post(
        "/call_audio", headers=ENTETES,
        data={"session_id": session_id, "utilisatrice_id": utilisatrice_id},
        files={"fichier": ("tour.webm", b"", "audio/webm")},
    )
    assert r.status_code == 200
    corps = r.json()
    assert corps["action"] == "reformuler"
    assert corps["audio_base64"]  # le clip de secours bundlé (assets/erreur.wav)


def test_call_audio_echec_asr_renvoie_un_message_de_secours_sans_planter(monkeypatch):
    # Fichier qui n'est pas un vrai audio : ffmpeg/convertir_en_wav doit
    # echouer (CalledProcessError), ce qui ne doit jamais remonter en 500.
    client = TestClient(app)
    utilisatrice_id, session_id = _demarrer_session(client)

    r = client.post(
        "/call_audio", headers=ENTETES,
        data={"session_id": session_id, "utilisatrice_id": utilisatrice_id},
        files={"fichier": ("tour.webm", b"ceci n'est pas de l'audio", "audio/webm")},
    )
    assert r.status_code == 200
    corps = r.json()
    assert corps["action"] == "reformuler"
    assert corps["audio_base64"]


def test_call_audio_echec_tts_garde_quand_meme_le_message_du_moteur(monkeypatch):
    # Le moteur a bien traite la demande (le message texte est correct, et si
    # l'action est "enregistrer" la transaction est deja en base) : une panne
    # du TTS en ligne ne doit pas effacer ce resultat, seulement remplacer
    # l'audio genere par le clip de secours.
    monkeypatch.setattr(moteur_api, "_obtenir_transcrire",
                         lambda: (lambda chemin_wav: "n ye saga saba feere wa bi duuru"))

    def _tts_en_panne(*a, **k):
        raise RuntimeError("Space Gradio injoignable")
    monkeypatch.setattr(moteur_api, "_obtenir_syntheser", lambda: _tts_en_panne)

    client = TestClient(app)
    utilisatrice_id, session_id = _demarrer_session(client)

    r = client.post(
        "/call_audio", headers=ENTETES,
        data={"session_id": session_id, "utilisatrice_id": utilisatrice_id},
        files={"fichier": ("tour.webm", _wav_silence(), "audio/wav")},
    )
    assert r.status_code == 200
    corps = r.json()
    assert corps["intention"] == "vente"
    assert corps["action"] == "demander_confirmation"
    assert corps["audio_base64"]  # clip de secours, pas l'audio genere (qui a echoue)
