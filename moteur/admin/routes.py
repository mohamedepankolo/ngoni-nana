"""Routes du dashboard admin ABIC (architecture section 3.8).

Accès complet façon "Administratrice ABIC" (section 4 de l'architecture) :
les deux autres rôles qui touchent à un dashboard (animatrice = ses seules
utilisatrices assignées ; gestionnaire de coopérative = rapports agrégés de
sa coopérative uniquement, jamais le détail individuel) supposent de vrais
comptes avec une coopérative/un portefeuille d'utilisatrices attaché à
chacun, qui n'existent pas encore (voir README, "pas de vrais comptes").
Restreindre ces vues attendra ces comptes réels plutôt qu'une distinction
inventée ici.

Authentification HTTP Basic (couple utilisateur/mot de passe natif du
navigateur, pas de formulaire à construire) : seul le mot de passe compte,
comparé à API_TOKEN — cohérent avec le jeton unique déjà utilisé par le
reste de l'API (voir api.py).
"""
import csv
import io
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates

from moteur.admin import donnees

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
securite = HTTPBasic()


def verifier_acces(identifiants: HTTPBasicCredentials = Depends(securite)) -> None:
    jeton_attendu = os.environ.get("API_TOKEN")
    if not jeton_attendu or identifiants.password != jeton_attendu:
        raise HTTPException(status_code=401, detail="Identifiants invalides.",
                             headers={"WWW-Authenticate": "Basic"})


def _session_factory_app(request: Request):
    return request.app.state.admin_session_factory()


@router.get("/", response_class=HTMLResponse, dependencies=[Depends(verifier_acces)])
def vue_ensemble(request: Request):
    bd = _session_factory_app(request)
    kpis = donnees.kpis_vue_ensemble(bd)
    return templates.TemplateResponse(request, "vue_ensemble.html", {"page": "vue_ensemble", "kpis": kpis})


@router.get("/utilisatrices", response_class=HTMLResponse, dependencies=[Depends(verifier_acces)])
def utilisatrices(request: Request, cooperative_id: int | None = None, recherche: str | None = None):
    bd = _session_factory_app(request)
    return templates.TemplateResponse(request, "utilisatrices.html", {
        "page": "utilisatrices",
        "cooperatives": donnees.lister_cooperatives(bd),
        "utilisatrices": donnees.lister_utilisatrices(bd, cooperative_id, recherche),
        "cooperative_id": cooperative_id,
        "recherche": recherche,
    })


@router.get("/sessions", response_class=HTMLResponse, dependencies=[Depends(verifier_acces)])
def sessions(request: Request, cooperative_id: int | None = None,
             statut: str | None = None, canal: str | None = None):
    bd = _session_factory_app(request)
    return templates.TemplateResponse(request, "sessions.html", {
        "page": "sessions",
        "cooperatives": donnees.lister_cooperatives(bd),
        "sessions": donnees.lister_sessions(bd, cooperative_id, statut, canal),
        "cooperative_id": cooperative_id, "statut": statut, "canal": canal,
    })


@router.get("/rapports", response_class=HTMLResponse, dependencies=[Depends(verifier_acces)])
def rapports(request: Request):
    bd = _session_factory_app(request)
    rapport = donnees.rapport_par_cooperative(bd)
    return templates.TemplateResponse(request, "rapports.html", {
        "page": "rapports",
        "rapport": rapport,
        "total_recettes": sum(r["recettes"] for r in rapport),
        "total_depenses": sum(r["depenses"] for r in rapport),
        "total_solde": sum(r["solde"] for r in rapport),
    })


@router.get("/rapports.csv", dependencies=[Depends(verifier_acces)])
def rapports_csv(request: Request):
    bd = _session_factory_app(request)
    rapport = donnees.rapport_par_cooperative(bd)
    tampon = io.StringIO()
    w = csv.writer(tampon)
    w.writerow(["cooperative", "recettes_fcfa", "depenses_fcfa", "solde_fcfa"])
    for r in rapport:
        w.writerow([r["cooperative"].nom, r["recettes"], r["depenses"], r["solde"]])
    tampon.seek(0)
    return StreamingResponse(tampon, media_type="text/csv",
                               headers={"Content-Disposition": "attachment; filename=rapport_germe.csv"})
