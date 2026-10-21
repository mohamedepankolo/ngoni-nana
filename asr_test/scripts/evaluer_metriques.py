#!/usr/bin/env python3
"""Évaluateur reproductible pour le protocole 8 (N'GONI NANA V2).

Mesure séparément les 9 métriques demandées en mission, plutôt qu'un seul
score global — pour qu'une réussite sur un aspect (ex. montant) ne masque
pas un échec sur un autre (ex. opération métier, voir
asr_test/v2/AUDIT_PROTOCOLES_1_A_7.md, §5).

Entrées :
  - un gabarit d'annotation (CSV, format `asr_test/v2/gabarit_annotation_protocole8.csv`)
  - un fichier de sorties modèle (JSONL, une sortie par ligne conforme à
    `asr_test/v2/schema_semantique_v1.json`, jointe par `id`)

N'exécute aucun appel réseau/modèle lui-même : prend des sorties déjà
produites, pour rester utilisable quel que soit le modèle ou l'architecture
testée (hypothèse de `ARCHITECTURE_EXPERIMENTALE.md`, à éprouver, pas à
supposer optimale).

Exemple :
  python evaluer_metriques.py --smoke
  python evaluer_metriques.py --gabarit ../v2/gabarit_annotation_protocole8.csv \
      --sorties resultats_protocole8.jsonl --output rapport_protocole8.json
"""
import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent


def _normalise(valeur):
    if valeur is None:
        return None
    v = str(valeur).strip().lower()
    return v or None


def _champ_correct(attendu, obtenu):
    """Égalité tolérante : deux None/'' sont égaux ; sinon comparaison normalisée."""
    a, o = _normalise(attendu), _normalise(obtenu)
    return a == o


def comparer(attendu: dict, obtenu: dict) -> dict:
    """Compare une annotation de référence (ligne du gabarit) à une sortie
    modèle (schema_semantique_v1) pour UN cas. Renvoie les mesures brutes
    (booléens/None), à agréger ensuite sur tout le corpus.
    """
    r = {}

    r["domaine_correct"] = _champ_correct(attendu.get("domaine_attendu"), obtenu.get("domaine"))
    r["operation_correcte"] = _champ_correct(attendu.get("operation_attendue"), obtenu.get("operation"))
    r["produit_correct"] = _champ_correct(attendu.get("produit_attendu"), obtenu.get("produit"))
    r["personne_correcte"] = _champ_correct(attendu.get("personne_attendu"), obtenu.get("personne"))

    # Quantite : cherche parmi les groupes numeriques obtenus celui marque
    # role="quantite", compare sa valeur a quantite_attendue.
    quantite_attendue = attendu.get("quantite_attendue")
    groupes = obtenu.get("groupes_numeriques") or []
    groupe_quantite = next((g for g in groupes if g.get("role") == "quantite"), None)
    if quantite_attendue in (None, ""):
        r["quantite_correcte"] = groupe_quantite is None
    else:
        r["quantite_correcte"] = (groupe_quantite is not None
                                   and str(groupe_quantite.get("valeur_dorome")) == str(quantite_attendue))

    # Montant FCFA : compare au montant calcule par le systeme (jamais celui propose par le LLM seul).
    montant_attendu = attendu.get("montant_fcfa_attendu")
    montant_obtenu = (obtenu.get("montant") or {}).get("montant_fcfa")
    if montant_attendu in (None, ""):
        r["montant_correct"] = montant_obtenu is None
    else:
        r["montant_correct"] = montant_obtenu is not None and int(montant_obtenu) == int(montant_attendu)

    r["transaction_entierement_correcte"] = all([
        r["domaine_correct"], r["operation_correcte"], r["produit_correct"],
        r["personne_correcte"], r["quantite_correcte"], r["montant_correct"],
    ])

    # Ambiguite : le scenario attend-il une clarification (ambiguite_attendue != "non") ?
    ambiguite_attendue_brute = (attendu.get("ambiguite_attendue") or "non").strip().lower()
    ambiguite_attendue = ambiguite_attendue_brute not in ("non", "", "none")
    ambiguite_signalee = bool(obtenu.get("confirmation_requise")) or bool(obtenu.get("informations_manquantes")) \
        or bool(obtenu.get("ambiguites"))
    r["ambiguite_bien_detectee"] = ambiguite_attendue == ambiguite_signalee
    r["ambiguite_attendue"] = ambiguite_attendue
    r["ambiguite_signalee"] = ambiguite_signalee
    # Faux negatif = le plus grave : une ambiguite reelle non signalee (risque d'invention).
    r["faux_negatif_ambiguite"] = ambiguite_attendue and not ambiguite_signalee

    # Fausse confirmation / action incorrecte : un effet comptable propose
    # sur une consultation, ou une action "repondre_directement" alors
    # qu'une confirmation est requise.
    est_consultation = (obtenu.get("domaine") == "consultation" or obtenu.get("operation") == "consultation")
    effet = obtenu.get("effet_comptable_potentiel")
    r["fausse_confirmation"] = bool(
        (est_consultation and effet not in (None, "aucun"))
        or (obtenu.get("confirmation_requise") is False and obtenu.get("informations_manquantes"))
        or (obtenu.get("action_proposee") == "repondre_directement" and obtenu.get("confirmation_requise"))
    )

    r["duree_s"] = obtenu.get("duree_s")
    return r


def agreger(resultats: list[dict]) -> dict:
    n = len(resultats)
    if n == 0:
        return {"n": 0}

    def taux(cle):
        vals = [r[cle] for r in resultats if r.get(cle) is not None]
        return (sum(bool(v) for v in vals) / len(vals)) if vals else None

    durees = [r["duree_s"] for r in resultats if r.get("duree_s") is not None]
    return {
        "n": n,
        "1_exactitude_intentions_domaine": taux("domaine_correct"),
        "2_exactitude_operations": taux("operation_correcte"),
        "3_exactitude_produits": taux("produit_correct"),
        "3_exactitude_personnes": taux("personne_correcte"),
        "4_exactitude_quantites_roles": taux("quantite_correcte"),
        "5_exactitude_montants_fcfa": taux("montant_correct"),
        "6_taux_transaction_entierement_correcte": taux("transaction_entierement_correcte"),
        "7_taux_ambiguites_bien_detectees": taux("ambiguite_bien_detectee"),
        "7b_taux_faux_negatifs_ambiguite_critique": taux("faux_negatif_ambiguite"),
        "8_taux_fausses_confirmations": taux("fausse_confirmation"),
        "9_duree_s_mediane": statistics.median(durees) if durees else None,
        "9_duree_s_moyenne": statistics.mean(durees) if durees else None,
    }


def charger_gabarit(chemin: Path) -> dict:
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        return {row["id"]: row for row in csv.DictReader(f)}


def charger_sorties(chemin: Path) -> dict:
    sorties = {}
    with open(chemin, encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne:
                continue
            obj = json.loads(ligne)
            sorties[obj["id"]] = obj.get("sortie", obj)
    return sorties


def _smoke():
    """Vérifie le code des métriques sur 3 cas synthétiques fabriqués pour le
    test (PAS des phrases bambara réelles ni validées — uniquement pour
    vérifier que comparer()/agreger() calculent ce qu'ils doivent).
    """
    cas = [
        # Cas 1 : tout correct.
        (
            {"domaine_attendu": "vente", "operation_attendue": "creation", "produit_attendu": "riz",
             "personne_attendu": "", "quantite_attendue": "3", "montant_fcfa_attendu": "15000",
             "ambiguite_attendue": "non"},
            {"domaine": "vente", "operation": "creation", "produit": "riz", "personne": None,
             "groupes_numeriques": [{"id": "N1", "role": "quantite", "valeur_dorome": 3}],
             "montant": {"montant_fcfa": 15000}, "confirmation_requise": True,
             "informations_manquantes": [], "ambiguites": [], "effet_comptable_potentiel": "creer_transaction",
             "action_proposee": "demander_confirmation"},
        ),
        # Cas 2 : montant manquant correctement signale (pas invente).
        (
            {"domaine_attendu": "vente", "operation_attendue": "creation", "produit_attendu": "riz",
             "personne_attendu": "", "quantite_attendue": "3", "montant_fcfa_attendu": "",
             "ambiguite_attendue": "oui - montant manquant"},
            {"domaine": "vente", "operation": "creation", "produit": "riz", "personne": None,
             "groupes_numeriques": [{"id": "N1", "role": "quantite", "valeur_dorome": 3}],
             "montant": None, "confirmation_requise": True,
             "informations_manquantes": ["montant"], "ambiguites": [], "effet_comptable_potentiel": None,
             "action_proposee": "demander_montant"},
        ),
        # Cas 3 : bug grave - effet propose sur une simple consultation.
        (
            {"domaine_attendu": "consultation", "operation_attendue": "consultation", "produit_attendu": "",
             "personne_attendu": "Mariam", "quantite_attendue": "", "montant_fcfa_attendu": "",
             "ambiguite_attendue": "non"},
            {"domaine": "consultation", "operation": "consultation", "produit": None, "personne": "Mariam",
             "groupes_numeriques": [], "montant": None, "confirmation_requise": False,
             "informations_manquantes": [], "ambiguites": [], "effet_comptable_potentiel": "augmenter_creance",
             "action_proposee": "repondre_directement"},
        ),
    ]
    resultats = [comparer(attendu, obtenu) for attendu, obtenu in cas]
    bilan = agreger(resultats)
    print(json.dumps(bilan, ensure_ascii=False, indent=2))
    assert resultats[0]["transaction_entierement_correcte"] is True
    assert resultats[1]["ambiguite_bien_detectee"] is True and resultats[1]["faux_negatif_ambiguite"] is False
    assert resultats[2]["fausse_confirmation"] is True, "le cas 3 doit detecter l'effet propose sur une consultation"
    print("Smoke test OK (3/3 assertions)")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--gabarit", help="CSV d'annotation (format gabarit_annotation_protocole8.csv)")
    p.add_argument("--sorties", help="JSONL des sorties modele, une par id, conformes a schema_semantique_v1.json")
    p.add_argument("--output", default=str(BASE / "rapport_metriques.json"))
    p.add_argument("--smoke", action="store_true", help="Verifie le code des metriques sur 3 cas synthetiques")
    args = p.parse_args()

    if args.smoke:
        _smoke()
        return

    if not args.gabarit or not args.sorties:
        p.error("--gabarit et --sorties sont requis (ou --smoke pour verifier le code seul)")

    gabarit = charger_gabarit(Path(args.gabarit))
    sorties = charger_sorties(Path(args.sorties))
    manquants = set(gabarit) - set(sorties)
    if manquants:
        print(f"ATTENTION : {len(manquants)} id du gabarit sans sortie modele correspondante : "
              f"{sorted(manquants)[:10]}{'...' if len(manquants) > 10 else ''}", file=sys.stderr)

    resultats = []
    for id_, attendu in gabarit.items():
        if id_ not in sorties:
            continue
        resultats.append(comparer(attendu, sorties[id_]))

    bilan = agreger(resultats)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({"bilan": bilan, "n_sans_sortie": len(manquants)}, f, ensure_ascii=False, indent=2)
    print(json.dumps(bilan, ensure_ascii=False, indent=2))
    print(f"\nRapport ecrit : {args.output}")


if __name__ == "__main__":
    main()
