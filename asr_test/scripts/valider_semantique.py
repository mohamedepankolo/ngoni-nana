#!/usr/bin/env python3
"""Validateur applicatif pour schema_semantique_v1.json.

Le JSON Schema seul (voir asr_test/v2/schema_semantique_v1.json) vérifie la
structure et les combinaisons domaine/operation, mais ne peut pas exprimer
certaines règles métier :
  - qu'un groupe_id référencé (quantite.groupe_id, montants_secondaires[].groupe_id)
    existe réellement dans groupes_numeriques ;
  - qu'une déclaration de stock n'est pas enregistrée comme une somme d'argent
    (le JSON Schema ne peut pas croiser domaine/operation avec le contenu de
    groupes_numeriques).

Ce module complète le JSON Schema, il ne le remplace pas : toujours valider
avec les deux (voir `valider`).
"""
import json
from pathlib import Path

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None

BASE = Path(__file__).resolve().parent
SCHEMA_PATH = BASE.parent / "v2" / "schema_semantique_v1.json"


def _charger_schema():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def valider_references_groupes(sortie: dict) -> list[str]:
    """Vérifie que tout groupe_id référencé existe dans groupes_numeriques."""
    ids_connus = {g.get("id") for g in (sortie.get("groupes_numeriques") or [])}
    erreurs = []

    quantite = sortie.get("quantite")
    if quantite and quantite.get("groupe_id") not in ids_connus:
        erreurs.append(f"quantite.groupe_id={quantite.get('groupe_id')!r} ne correspond à aucun "
                        f"groupe de groupes_numeriques ({sorted(ids_connus)})")

    for secondaire in ((sortie.get("montant") or {}).get("montants_secondaires") or []):
        gid = secondaire.get("groupe_id")
        if gid not in ids_connus:
            erreurs.append(f"montant.montants_secondaires contient groupe_id={gid!r} inconnu "
                            f"({sorted(ids_connus)})")
    return erreurs


def valider_stock_quantite_vs_montant(sortie: dict) -> list[str]:
    """Une déclaration de stock (augmentation/diminution/consultation) doit
    porter sur une quantité physique, jamais être enregistrée comme une
    simple somme d'argent (relecture reçue, §C "Stock" des corrections
    obligatoires). Signale une anomalie si le domaine est 'stock' et
    qu'AUCUN groupe numérique n'a le rôle 'quantite' alors qu'au moins un
    groupe a le rôle 'montant_total' — signe que le système a confondu
    une quantité physique avec un montant financier.
    """
    if sortie.get("domaine") != "stock":
        return []
    groupes = sortie.get("groupes_numeriques") or []
    a_quantite = any(g.get("role") == "quantite" for g in groupes)
    a_montant = any(g.get("role") == "montant_total" for g in groupes)
    if a_montant and not a_quantite:
        return ["domaine='stock' mais aucun groupe numérique n'a le rôle 'quantite' "
                "(un groupe est marqué 'montant_total' à la place) — une déclaration de "
                "stock en sacs/kg/pièces ne doit jamais être enregistrée comme un montant financier"]
    return []


def valider_consultation_sans_effet(sortie: dict) -> list[str]:
    """Filet de sécurité redondant avec la règle JSON Schema (allOf), gardé
    ici pour que ce module soit utilisable même sans jsonschema installé."""
    est_consultation = sortie.get("operation") == "consultation" or sortie.get("domaine") == "consultation"
    effet = sortie.get("effet_comptable_potentiel")
    if est_consultation and effet not in (None, "aucun"):
        return [f"operation/domaine='consultation' mais effet_comptable_potentiel={effet!r} "
                f"(doit être 'aucun' ou null)"]
    return []


def valider(sortie: dict) -> list[str]:
    """Valide une sortie contre le JSON Schema PUIS les règles applicatives.
    Renvoie la liste de toutes les erreurs trouvées (vide = valide)."""
    erreurs = []
    if jsonschema is not None:
        schema = _charger_schema()
        erreurs.extend(e.message for e in jsonschema.Draft202012Validator(schema).iter_errors(sortie))
    erreurs.extend(valider_references_groupes(sortie))
    erreurs.extend(valider_stock_quantite_vs_montant(sortie))
    erreurs.extend(valider_consultation_sans_effet(sortie))
    return erreurs


if __name__ == "__main__":
    import sys
    for ligne in sys.stdin:
        ligne = ligne.strip()
        if not ligne:
            continue
        obj = json.loads(ligne)
        erreurs = valider(obj.get("sortie", obj))
        if erreurs:
            print(f"{obj.get('id', '?')} : {len(erreurs)} erreur(s)")
            for e in erreurs:
                print(f"  - {e}")
