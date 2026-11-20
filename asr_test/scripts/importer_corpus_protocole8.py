#!/usr/bin/env python3
"""Importation et contrôle du corpus du protocole 8 (gabarit d'annotation).

Vérifie, sans jamais deviner ni compléter silencieusement une valeur
manquante : identifiants de locutrices, scénarios, conversations/tours,
statuts de validation, cohérence du JSON embarqué (montants multiples).
Fait aussi respecter la séparation stricte entre les locutrices du corpus
existant (L01-L03, déjà utilisées pour affiner les prompts aux protocoles
5-7) et celles du nouveau corpus indépendant — mélanger les deux
invaliderait toute mesure de généralisation (voir
asr_test/v2/AUDIT_PROTOCOLES_1_A_7.md §2).

Exemples :
  python importer_corpus_protocole8.py --smoke
  python importer_corpus_protocole8.py ../v2/gabarit_annotation_protocole8.csv
  python importer_corpus_protocole8.py corpus_reel.csv --locuteurs-test L05,L06
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
SCENARIOS_PATH = BASE.parent / "v2" / "PROTOCOLE_8_SCENARIOS.md"
LOCUTEURS_CORPUS_EXISTANT = {"L01", "L02", "L03"}
STATUTS_VALIDES = {"a_valider", "validee", "variante", "rejetee"}
COLONNES_REQUISES = [
    "id", "scenario_id", "conversation_id", "tour_id", "locuteur_id", "texte_bambara",
    "sens_fr", "domaine_attendu", "operation_attendue", "sens_mouvement_financier",
    "personne_attendu", "produit_attendu", "quantite_attendue", "unite_quantite",
    "montant_fcfa_attendu", "montants_multiples_attendus", "effet_comptable_attendu",
    "ambiguite_attendue", "statut_validation", "notes_locutrice", "date_validation",
]


def _scenarios_connus() -> set[str]:
    """Extrait les identifiants de scénario (ex. 'A1', 'K2') du document des
    scénarios, pour vérifier que scenario_id y renvoie bien quelque part."""
    if not SCENARIOS_PATH.exists():
        return set()
    texte = SCENARIOS_PATH.read_text(encoding="utf-8")
    return set(re.findall(r"\*\*([A-K]\d+)\.\*\*", texte))


def charger(chemin: Path) -> list[dict]:
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def verifier_colonnes(lignes: list[dict]) -> list[str]:
    if not lignes:
        return ["le fichier est vide (aucune ligne)"]
    colonnes = set(lignes[0].keys())
    manquantes = set(COLONNES_REQUISES) - colonnes
    if manquantes:
        return [f"colonnes manquantes : {sorted(manquantes)}"]
    return []


def verifier_lignes(lignes: list[dict], scenarios_connus: set[str]) -> list[str]:
    erreurs = []
    ids_vus = set()
    conversations = {}  # conversation_id -> {tour_id: ligne}

    for i, ligne in enumerate(lignes, 1):
        prefixe = f"ligne {i} (id={ligne.get('id')!r})"

        if not ligne.get("id"):
            erreurs.append(f"{prefixe} : id vide")
        elif ligne["id"] in ids_vus:
            erreurs.append(f"{prefixe} : id dupliqué")
        ids_vus.add(ligne.get("id"))

        if scenarios_connus and ligne.get("scenario_id") not in scenarios_connus:
            erreurs.append(f"{prefixe} : scenario_id={ligne.get('scenario_id')!r} absent de "
                            f"PROTOCOLE_8_SCENARIOS.md")

        statut = ligne.get("statut_validation")
        if statut and statut not in STATUTS_VALIDES:
            erreurs.append(f"{prefixe} : statut_validation={statut!r} invalide (attendu {STATUTS_VALIDES})")

        if ligne.get("locuteur_id") in LOCUTEURS_CORPUS_EXISTANT:
            erreurs.append(f"{prefixe} : locuteur_id={ligne.get('locuteur_id')!r} appartient au corpus "
                            f"EXISTANT (déjà utilisé pour affiner les prompts, protocoles 5-7) — "
                            f"le protocole 8 doit utiliser des locutrices distinctes")

        if not (ligne.get("texte_bambara") or "").strip() or "à remplir" in (ligne.get("texte_bambara") or "").lower():
            erreurs.append(f"{prefixe} : texte_bambara vide ou non rempli (placeholder laissé tel quel)")

        montants_bruts = ligne.get("montants_multiples_attendus")
        if montants_bruts:
            try:
                json.loads(montants_bruts)
            except json.JSONDecodeError as e:
                erreurs.append(f"{prefixe} : montants_multiples_attendus n'est pas du JSON valide ({e})")

        conv_id, tour_id = ligne.get("conversation_id"), ligne.get("tour_id")
        if conv_id:
            conversations.setdefault(conv_id, {})
            try:
                conversations[conv_id][int(tour_id)] = ligne
            except (TypeError, ValueError):
                erreurs.append(f"{prefixe} : tour_id={tour_id!r} n'est pas un entier")

    for conv_id, tours in conversations.items():
        attendus = set(range(1, len(tours) + 1))
        if set(tours) != attendus:
            erreurs.append(f"conversation_id={conv_id!r} : tours {sorted(tours)} discontinus "
                            f"(attendu 1..{len(tours)} sans trou)")

    return erreurs


def verifier_separation_locuteurs(lignes: list[dict], locuteurs_test: set[str] | None) -> list[str]:
    """Si --locuteurs-test est fourni : toute ligne d'une autre locutrice est
    une fuite potentielle entre dev (ajustement de prompt) et test
    (évaluation de généralisation) — signalée, jamais filtrée silencieusement."""
    if not locuteurs_test:
        return []
    hors_test = {l.get("locuteur_id") for l in lignes} - locuteurs_test
    if hors_test:
        return [f"--locuteurs-test={sorted(locuteurs_test)} fourni, mais le fichier contient aussi "
                f"{sorted(hors_test)} — séparer ces locutrices dans des fichiers distincts avant "
                f"d'évaluer, pour ne jamais mélanger dev et test"]
    return []


def importer(chemin: Path, locuteurs_test: set[str] | None = None) -> tuple[list[dict], list[str]]:
    lignes = charger(chemin)
    erreurs = verifier_colonnes(lignes)
    if erreurs:
        return lignes, erreurs
    erreurs += verifier_lignes(lignes, _scenarios_connus())
    erreurs += verifier_separation_locuteurs(lignes, locuteurs_test)
    return lignes, erreurs


def _smoke():
    import tempfile
    bon = ("id,scenario_id,conversation_id,tour_id,locuteur_id,texte_bambara,sens_fr,domaine_attendu,"
           "operation_attendue,sens_mouvement_financier,personne_attendu,produit_attendu,quantite_attendue,"
           "unite_quantite,montant_fcfa_attendu,montants_multiples_attendus,effet_comptable_attendu,"
           "ambiguite_attendue,statut_validation,notes_locutrice,date_validation\n"
           'P8-001,A1,CONV-1,1,L05,"n ye malo sogo saba feere",vente 3 sacs riz prix absent,vente,creation,'
           'aucun,,malo,3,sac,,[],aucun,oui - montant manquant,a_valider,,\n')
    mauvais = bon + (
        'P8-001,A1,CONV-1,1,L01,"doublon id et locutrice existante",x,vente,creation,aucun,,malo,3,sac,,[],'
        'aucun,non,statut_invalide,,\n'
    )
    with tempfile.TemporaryDirectory() as d:
        p_bon = Path(d) / "bon.csv"
        p_bon.write_text(bon, encoding="utf-8")
        lignes, erreurs = importer(p_bon)
        assert erreurs == [], f"le fichier correct ne devrait soulever aucune erreur : {erreurs}"
        print("Fichier correct : 0 erreur, comme attendu.")

        p_mauvais = Path(d) / "mauvais.csv"
        p_mauvais.write_text(mauvais, encoding="utf-8")
        lignes, erreurs = importer(p_mauvais)
        assert len(erreurs) >= 3, f"attendu au moins 3 erreurs (id dupliqué, locutrice existante, statut invalide), eu {erreurs}"
        for e in erreurs:
            print(" -", e)
        print(f"Fichier incorrect : {len(erreurs)} erreur(s) détectée(s), comme attendu.")
    print("Smoke test OK")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("chemin", nargs="?", help="Fichier CSV à importer (format du gabarit)")
    p.add_argument("--locuteurs-test", help="Liste séparée par des virgules (ex. L05,L06) : "
                                             "vérifie qu'aucune autre locutrice n'est mélangée")
    p.add_argument("--smoke", action="store_true")
    args = p.parse_args()

    if args.smoke:
        _smoke()
        return
    if not args.chemin:
        p.error("fournir un chemin de fichier, ou --smoke")

    locuteurs_test = set(args.locuteurs_test.split(",")) if args.locuteurs_test else None
    lignes, erreurs = importer(Path(args.chemin), locuteurs_test)
    print(f"{len(lignes)} lignes chargées.")
    if erreurs:
        print(f"{len(erreurs)} erreur(s) :")
        for e in erreurs:
            print(" -", e)
        sys.exit(1)
    print("Aucune erreur détectée.")


if __name__ == "__main__":
    main()
