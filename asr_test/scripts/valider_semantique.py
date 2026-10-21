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

# Table domaine/operation -> effet, derivee de REFERENTIEL_OPERATIONS_COMPTABLES.md.
# Source unique de verite : l'effet ne doit JAMAIS etre invente librement par
# le LLM, seulement derive de ce tableau une fois domaine/operation connus
# (le LLM ne classe que domaine/operation, pas l'effet qui en decoule).
# dette_fournisseur : effet force a "aucun" quelle que soit l'operation tant
# que ce cas d'usage n'est pas confirme (voir schema_semantique_v1.json 1.2.0).
EFFET_REFERENTIEL = {
    ("vente", "creation"): "creer_transaction",
    ("vente", "correction"): "corriger_transaction_existante",
    ("achat", "creation"): "creer_transaction",
    ("achat", "correction"): "corriger_transaction_existante",
    ("depense", "creation"): "creer_transaction",
    ("depense", "correction"): "corriger_transaction_existante",
    ("dette_client", "creation"): "augmenter_creance",
    ("dette_client", "remboursement"): "diminuer_creance",
    ("dette_client", "consultation"): "aucun",
    ("dette_client", "correction"): "corriger_transaction_existante",
    ("dette_fournisseur", "creation"): "aucun",
    ("dette_fournisseur", "remboursement"): "aucun",
    ("dette_fournisseur", "consultation"): "aucun",
    ("dette_fournisseur", "correction"): "aucun",
    ("capital", "creation"): "definir_capital_initial",
    ("capital", "augmentation"): "augmenter_capital",
    ("capital", "consultation"): "aucun",
    ("stock", "augmentation"): "ajuster_stock_plus",
    ("stock", "diminution"): "ajuster_stock_moins",
    ("stock", "consultation"): "aucun",
    ("consultation", "consultation"): "aucun",
}


def effet_attendu(domaine: str, operation: str) -> str | None:
    """Effet comptable dérivé du référentiel pour ce domaine/operation, ou
    None si la combinaison n'est pas répertoriée (-> 'inconnue')."""
    return EFFET_REFERENTIEL.get((domaine, operation))


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


_EFFETS_AUGMENTATION = {"augmenter_creance", "augmenter_dette_fournisseur", "augmenter_capital",
                        "ajuster_stock_plus", "definir_capital_initial"}
_EFFETS_DIMINUTION = {"diminuer_creance", "diminuer_dette_fournisseur", "ajuster_stock_moins"}


def valider_direction_effet(sortie: dict) -> list[str]:
    """Un remboursement ne doit jamais AUGMENTER un solde, et une création/
    augmentation ne doit jamais en DIMINUER un — aucune opération ne doit
    diminuer le mauvais solde (correction demandée en relecture)."""
    operation = sortie.get("operation")
    effet = sortie.get("effet_comptable_potentiel")
    if operation == "remboursement" and effet in _EFFETS_AUGMENTATION:
        return [f"operation='remboursement' mais effet={effet!r} AUGMENTE un solde (devrait diminuer)"]
    if operation in ("creation", "augmentation") and effet in _EFFETS_DIMINUTION:
        return [f"operation={operation!r} mais effet={effet!r} DIMINUE un solde (devrait augmenter/créer)"]
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
    erreurs.extend(valider_direction_effet(sortie))
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
