import os
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "asr_test" / "scripts"))

# Même fichier/jeton que test_api.py : moteur.api est un singleton construit
# une seule fois au premier import (voir ce fichier) — ces lignes n'ont d'effet
# que si ce module est collecté avant test_api.py, mais restent nécessaires
# pour que ce fichier reste exécutable seul (`pytest tests/test_admin.py`).
os.environ["API_TOKEN"] = "jeton-de-test"
DB_TEST = RACINE / "tests" / "_api_test.db"
try:
    DB_TEST.unlink(missing_ok=True)
except PermissionError:
    pass  # déjà ouvert dans ce process par test_api.py (même fichier, même singleton moteur.api)
os.environ["DATABASE_URL"] = f"sqlite:///{DB_TEST}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from moteur import base_donnees as db  # noqa: E402
from moteur.api import _SessionLocal, app  # noqa: E402

AUTH = ("admin", "jeton-de-test")


@pytest.fixture(autouse=True)
def base_propre():
    yield
    bd = _SessionLocal()
    for table in reversed(db.Base.metadata.sorted_tables):
        bd.execute(table.delete())
    bd.commit()
    bd.close()


def test_refuse_sans_authentification():
    client = TestClient(app)
    r = client.get("/admin/")
    assert r.status_code == 401


def test_refuse_mauvais_mot_de_passe():
    client = TestClient(app)
    r = client.get("/admin/", auth=("admin", "mauvais-jeton"))
    assert r.status_code == 401


def test_vue_ensemble_sans_donnees():
    client = TestClient(app)
    r = client.get("/admin/", auth=AUTH)
    assert r.status_code == 200
    assert "N'GONI NANA" in r.text


@pytest.mark.parametrize("chemin", [
    "/admin/utilisatrices?cooperative_id=",
    "/admin/sessions?cooperative_id=",
    "/admin/sessions?cooperative_id=&statut=&canal=",
])
def test_filtre_toutes_les_cooperatives_ne_plante_pas(chemin):
    """Régression : le <select> "Toutes les coopératives" envoie cooperative_id=""
    (pas absent), que FastAPI refusait de lire comme un entier (401 -> 422).
    Trouvé en test réel sur le dashboard, 2026-10-06.
    """
    client = TestClient(app)
    r = client.get(chemin, auth=AUTH)
    assert r.status_code == 200


def test_filtre_par_cooperative_fonctionne():
    bd = _SessionLocal()
    coop = db.Cooperative(nom="ABIC Dioïla")
    bd.add(coop)
    bd.commit()
    bd.refresh(coop)
    u = db.Utilisatrice(code_anonyme="L01", telephone_hash="x", cooperative_id=coop.id)
    bd.add(u)
    bd.commit()

    client = TestClient(app)
    r = client.get(f"/admin/utilisatrices?cooperative_id={coop.id}", auth=AUTH)
    assert r.status_code == 200
    assert "L01" in r.text


def test_rapport_csv_contient_les_montants():
    bd = _SessionLocal()
    coop = db.Cooperative(nom="ABIC Dioïla")
    bd.add(coop)
    bd.commit()
    bd.refresh(coop)
    u = db.Utilisatrice(code_anonyme="L01", telephone_hash="x", cooperative_id=coop.id)
    bd.add(u)
    bd.commit()
    bd.refresh(u)
    db.enregistrer_transaction(bd, utilisatrice_id=u.id, type_="vente",
                                 champs={"montant_fcfa": 100_000})

    client = TestClient(app)
    r = client.get("/admin/rapports.csv", auth=AUTH)
    assert r.status_code == 200
    assert "100000" in r.text
    assert "ABIC Dioïla" in r.text
