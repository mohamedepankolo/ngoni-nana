#!/usr/bin/env python3
"""Prototype isolé de compréhension sémantique — produit une sortie conforme
à schema_semantique_v1.json (v1.2.0). Isolé : ne touche à rien dans
moteur/, utilisable seulement pour l'expérimentation du protocole 8.

Garde-fous appliqués (ARCHITECTURE_EXPERIMENTALE.md) :
  - Le LLM ne classe QUE domaine, operation, personne, produit et le rôle
    de chaque groupe numérique déjà délimité par montants.extraire_groupes().
  - Le montant final est calculé déterministiquement (jamais par le LLM).
  - L'effet comptable est dérivé de EFFET_REFERENTIEL (valider_semantique.py),
    jamais proposé librement par le LLM — élimine le risque qu'il invente un
    effet incohérent avec le référentiel.
  - La sortie finale est validée (schéma + règles applicatives) avant d'être
    renvoyée ; une sortie non conforme est signalée, jamais masquée.

Utilise Ollama (gratuit, local, pas de nouvelle dépense API) — modèle par
défaut mistral:7b, le plus fiable des modèles locaux testés aux protocoles
5-7 pour ce domaine.

Exemples :
  python prototype_semantique_v1.py --smoke
  python prototype_semantique_v1.py --phrase "n ye saga saba feere waa mugan ni duuru"
"""
import argparse
import json
import re
import sys
from pathlib import Path
from urllib import request

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from montants import extraire_groupes  # noqa: E402
from valider_semantique import effet_attendu, valider  # noqa: E402

SCHEMA_VERSION = "1.2.0"

SYSTEM = '''Tu analyses une phrase de comptabilité en bambara, déjà découpée en groupes numériques reconnus par un analyseur déterministe (tu n'as RIEN à calculer, ni aucun montant à convertir).
Pour chaque groupe numérique fourni (identifiant, texte, valeur déjà en dɔrɔmɛ), dis quel rôle il joue : "quantite" (nombre d'articles), "montant_total" (prix/montant total), "prix_unitaire" (prix par article), "autre", ou "ambigu" si tu ne peux pas trancher sans deviner.
Classe aussi le domaine métier : vente, achat, dette_client (argent dû À la commerçante), dette_fournisseur (argent dû PAR la commerçante), capital, stock, depense, consultation, ou inconnu.
Classe l'opération précise : creation, remboursement, augmentation, diminution, consultation, correction, ou inconnue.
Vocabulaire : feere=vendre (vente) ; san=acheter (achat) ; sara=payer (depense OU rembourser une dette selon contexte) ; jagokun=capital ; juru=dette ; joli/jɔn=mot interrogatif (signale consultation, pas vente).
Si une information nécessaire manque (montant, quantité, produit, personne, operation), liste-la dans informations_manquantes — ne la devine JAMAIS.
Réponds uniquement en JSON strict : {"domaine": "...", "operation": "...", "personne": "..." ou null, "produit": "..." ou null, "roles": {"N1": "...", ...}, "informations_manquantes": [...], "ambiguites": [...]}'''


def _decode_json(contenu: str) -> dict:
    try:
        return json.loads(contenu)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", contenu, re.S)
        if not m:
            raise
        return json.loads(m.group())


def _appeler_llm(phrase: str, groupes_pour_llm: list[dict], modele: str, url: str, timeout: int) -> dict:
    contenu = json.dumps({"phrase": phrase, "groupes_numeriques": groupes_pour_llm}, ensure_ascii=False)
    payload = json.dumps({
        "model": modele, "stream": False, "format": "json", "options": {"temperature": 0},
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": contenu}],
    }, ensure_ascii=False).encode("utf-8")
    req = request.Request(url.rstrip("/") + "/api/chat", data=payload,
                           headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=timeout) as r:
        body = json.load(r)
    return _decode_json(body["message"]["content"])


def _construire_sortie(phrase: str, groupes: list[dict], reponse_llm: dict) -> dict:
    """Assemble la sortie finale conforme au schéma à partir des groupes
    déterministes et du rôle/domaine/operation proposés par le LLM — SANS
    jamais laisser le LLM calculer un montant ou choisir un effet comptable."""
    roles = reponse_llm.get("roles") or {}
    for i, g in enumerate(groupes, 1):
        g["role"] = roles.get(f"N{i}", "ambigu")

    domaine = reponse_llm.get("domaine") or "inconnu"
    operation = reponse_llm.get("operation") or "inconnue"

    groupe_quantite = next((g for g in groupes if g["role"] == "quantite"), None)
    groupes_montant = [g for g in groupes if g["role"] == "montant_total"]
    quantite = {"groupe_id": f"N{groupes.index(groupe_quantite) + 1}", "unite": None} if groupe_quantite else None

    montant = None
    if len(groupes_montant) == 1:
        g = groupes_montant[0]
        montant = {"montant_brut_dorome": g["valeur"], "unite_monetaire": "dorome_implicite",
                   "montant_fcfa": g["valeur"] * 5, "montants_secondaires": []}

    informations_manquantes = list(reponse_llm.get("informations_manquantes") or [])
    ambiguites = [{"champ": a, "raison": "signalé par le composant sémantique"}
                  for a in (reponse_llm.get("ambiguites") or [])]
    if any(g["role"] == "ambigu" for g in groupes):
        ambiguites.append({"champ": "groupes_numeriques", "raison": "au moins un groupe numérique ambigu"})

    effet = effet_attendu(domaine, operation) if not informations_manquantes and not ambiguites else "aucun"
    confirmation_requise = bool(informations_manquantes or ambiguites or (effet and effet != "aucun"))
    if informations_manquantes:
        action = f"demander_{informations_manquantes[0]}" if informations_manquantes[0] in (
            "montant", "quantite", "produit", "personne", "operation") else "demander_confirmation"
    elif ambiguites:
        action = "demander_confirmation"
    else:
        action = "demander_confirmation" if confirmation_requise else "repondre_directement"

    return {
        "schema_version": SCHEMA_VERSION,
        "domaine": domaine, "operation": operation,
        "personne": reponse_llm.get("personne"), "produit": reponse_llm.get("produit"),
        "quantite": quantite,
        "groupes_numeriques": [{"id": f"N{i+1}", "texte": g["texte"], "valeur_dorome": g["valeur"], "role": g["role"]}
                                for i, g in enumerate(groupes)],
        "montant": montant,
        "informations_manquantes": informations_manquantes,
        "ambiguites": ambiguites,
        "effet_comptable_potentiel": effet,
        "action_proposee": action,
        "confirmation_requise": confirmation_requise,
    }


def analyser(phrase: str, modele: str = "mistral:7b", url: str = "http://localhost:11434",
             timeout: int = 240) -> dict:
    groupes = extraire_groupes(phrase)
    groupes_pour_llm = [{"id": f"N{i+1}", "texte": g["texte"], "valeur_dorome": g["valeur"]}
                         for i, g in enumerate(groupes)]
    reponse_llm = _appeler_llm(phrase, groupes_pour_llm, modele, url, timeout)
    sortie = _construire_sortie(phrase, groupes, reponse_llm)
    erreurs = valider(sortie)
    return {"sortie": sortie, "erreurs_validation": erreurs}


def _smoke():
    """Vérifie l'assemblage (_construire_sortie) sans appel réseau, à partir
    d'une réponse LLM fabriquée pour le test."""
    phrase = "n ye saga saba feere waa mugan ni duuru"
    groupes = extraire_groupes(phrase)
    assert len(groupes) == 2, groupes
    reponse_llm_fabriquee = {
        "domaine": "vente", "operation": "creation", "personne": None, "produit": "saga",
        "roles": {"N1": "quantite", "N2": "montant_total"},
        "informations_manquantes": [], "ambiguites": [],
    }
    sortie = _construire_sortie(phrase, groupes, reponse_llm_fabriquee)
    assert sortie["montant"]["montant_fcfa"] == 125000, sortie["montant"]
    assert sortie["effet_comptable_potentiel"] == "creer_transaction"
    erreurs = valider(sortie)
    assert erreurs == [], erreurs
    print(json.dumps(sortie, ensure_ascii=False, indent=2))
    print("Smoke test OK (assemblage correct, 125000 FCFA, 0 erreur de validation)")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--phrase")
    p.add_argument("--model", default="mistral:7b")
    p.add_argument("--url", default="http://localhost:11434")
    p.add_argument("--timeout", type=int, default=240)
    p.add_argument("--smoke", action="store_true")
    args = p.parse_args()

    if args.smoke:
        _smoke()
        return
    if not args.phrase:
        p.error("fournir --phrase, ou --smoke")

    resultat = analyser(args.phrase, args.model, args.url, args.timeout)
    print(json.dumps(resultat, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
