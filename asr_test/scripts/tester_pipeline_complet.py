"""Teste le pipeline complet (ASR réel -> moteur de décision) sur les 60
phrases réelles vérifiées, plutôt que le moteur seul sur du texte parfait
(tests/test_moteur_decision.py). Donne le vrai chiffre de précision de bout
en bout : l'ASR fait des erreurs, le moteur doit encaisser ce bruit.

Usage :
    python asr_test/scripts/tester_pipeline_complet.py
    python asr_test/scripts/tester_pipeline_complet.py --rapport asr_test/results/pipeline_complet.md
"""
import argparse
import csv
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "asr_test" / "scripts"))

from moteur.dictionnaire_mots_cles import reconnaitre_intention  # noqa: E402
from moteur.moteur_decision import analyser  # noqa: E402

INTENTION_ATTENDUE = {
    "dette_client": "client", "vente": "vente", "achat": "depense",
    "depense": "depense", "capital": "capital", "consultation": "consultation",
    "stock": "stock",
}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--corpus", type=Path, default=RACINE / "asr_test" / "corpus" / "phrases_reelles.csv")
    p.add_argument("--audio", type=Path, default=RACINE / "asr_test" / "audio")
    p.add_argument("--modele", default="RobotsMali/soloni-114m-tdt-ctc-v3")
    p.add_argument("--rapport", type=Path, default=RACINE / "asr_test" / "results" / "pipeline_complet.md")
    args = p.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    with open(args.corpus, newline="", encoding="utf-8") as f:
        lignes = [l for l in csv.DictReader(f) if l.get("fichier_audio")]

    from moteur.asr_robotsmali import obtenir_transcripteur  # noqa: E402 (après sys.path, dépendance lourde)
    print(f"Chargement du modèle ASR ({args.modele})...")
    transcrire = obtenir_transcripteur(args.modele)

    resultats = []
    for l in lignes:
        chemin = args.audio / l["fichier_audio"]
        if not chemin.exists():
            print(f"[{l['id']}] fichier manquant : {chemin}", file=sys.stderr)
            continue
        debut = time.perf_counter()
        texte_asr = transcrire(str(chemin)).strip()
        latence = time.perf_counter() - debut

        intention_attendue = INTENTION_ATTENDUE[l["categorie"]]
        intention_trouvee = reconnaitre_intention(texte_asr)
        resultat_moteur = analyser(texte_asr)

        montant_attendu = int(l["montant_fcfa"]) if l["montant_fcfa"] else None
        montant_trouve = resultat_moteur["champs"].get("montant_fcfa")

        resultats.append({
            "id": l["id"], "locuteur": l["locuteur"],
            "texte_reference": l["texte_bambara"], "texte_asr": texte_asr,
            "intention_attendue": intention_attendue, "intention_trouvee": intention_trouvee,
            "montant_attendu": montant_attendu, "montant_trouve": montant_trouve,
            "latence_s": latence,
        })
        statut = "OK" if intention_trouvee == intention_attendue else "FAUX"
        print(f"[{l['id']}] {statut:5} {latence:.2f}s  intention={intention_trouvee!s:12} « {texte_asr} »")

    n = len(resultats)
    ok_intention = sum(1 for r in resultats if r["intention_trouvee"] == r["intention_attendue"])
    avec_montant = [r for r in resultats if r["montant_attendu"] is not None]
    ok_montant = sum(1 for r in avec_montant if r["montant_trouve"] == r["montant_attendu"])
    latence_moy = sum(r["latence_s"] for r in resultats) / n if n else 0

    print(f"\nIntention correcte (bout en bout) : {ok_intention}/{n} ({100 * ok_intention / n:.0f} %)")
    print(f"Montant exact (bout en bout) : {ok_montant}/{len(avec_montant)} "
          f"({100 * ok_montant / len(avec_montant):.0f} %)" if avec_montant else "Montant exact : n/d")
    print(f"Latence ASR moyenne : {latence_moy:.2f} s")

    args.rapport.parent.mkdir(parents=True, exist_ok=True)
    with open(args.rapport, "w", encoding="utf-8") as f:
        f.write(f"# Pipeline complet (ASR réel + moteur de décision) : {args.modele}\n\n")
        f.write(f"Intention correcte, bout en bout (ASR réel, pas le texte de référence) : "
                f"**{ok_intention}/{n} ({100 * ok_intention / n:.0f} %)**\n\n")
        if avec_montant:
            f.write(f"Montant exact, bout en bout : **{ok_montant}/{len(avec_montant)} "
                    f"({100 * ok_montant / len(avec_montant):.0f} %)**\n\n")
        f.write(f"Latence ASR moyenne : {latence_moy:.2f} s\n\n")
        f.write("## Détail\n\n")
        f.write("| id | locuteur | transcription ASR | intention attendue | intention trouvée | "
                "montant attendu | montant trouvé |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for r in resultats:
            verdict_intention = "✅" if r["intention_trouvee"] == r["intention_attendue"] else "❌"
            verdict_montant = "✅" if r["montant_trouve"] == r["montant_attendu"] else (
                "n/d" if r["montant_attendu"] is None else "❌")
            f.write(f"| {r['id']} | {r['locuteur']} | {r['texte_asr']} | {r['intention_attendue']} "
                    f"| {r['intention_trouvee']} {verdict_intention} | {r['montant_attendu']} "
                    f"| {r['montant_trouve']} {verdict_montant} |\n")
    print(f"\nRapport écrit dans {args.rapport}")


if __name__ == "__main__":
    main()
