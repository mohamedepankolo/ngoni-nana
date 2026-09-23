"""Compare les transcriptions au corpus de référence et produit le rapport de test.

Usage :
    python asr_test/scripts/evaluer.py
    python asr_test/scripts/evaluer.py --transcriptions asr_test/results/demo_cgiar.csv

Les transcriptions peuvent venir de transcrire.py ou être saisies à la main
depuis la démo en ligne (même format CSV : id, transcription[, latence_s]).

Mesures, sur les trois questions posées par CfA :
  1. Mots correctement transcrits ?  -> WER / CER (texte normalisé)
  2. Nombres et montants exacts ?    -> le nombre prononcé est-il retrouvé
  3. Robuste aux accents / au bruit ? -> mêmes mesures par locuteur et par environnement
"""
import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

import jiwer

from montants import extraire_nombres, normaliser

RACINE = Path(__file__).resolve().parents[1]
SEUIL_LATENCE_S = 5.0


def lire_csv(chemin: Path) -> list[dict]:
    with open(chemin, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def nombre_attendu(ref: dict) -> int | None:
    """Nombre réellement prononcé : montant FCFA, divisé par 5 s'il est dit en dɔrɔmɛ."""
    if not ref.get("montant_fcfa"):
        return None
    montant = int(ref["montant_fcfa"])
    return montant // 5 if ref.get("unite", "fcfa").strip().lower() == "dorome" else montant


def evaluer(refs: list[dict], hyps: list[dict]) -> list[dict]:
    par_id = {h["id"]: h for h in hyps}
    lignes = []
    for ref in refs:
        hyp = par_id.get(ref["id"])
        if hyp is None or not ref.get("texte_bambara"):
            continue
        r, h = normaliser(ref["texte_bambara"]), normaliser(hyp["transcription"])
        attendu = nombre_attendu(ref)
        trouves = extraire_nombres(hyp["transcription"])
        lignes.append({
            "id": ref["id"],
            "locuteur": ref.get("locuteur") or "?",
            "environnement": ref.get("environnement") or "?",
            "reference": ref["texte_bambara"],
            "transcription": hyp["transcription"],
            "wer": jiwer.wer(r, h) if r else 0.0,
            "cer": jiwer.cer(r, h) if r else 0.0,
            "attendu": attendu,
            "trouves": trouves,
            "montant_ok": None if attendu is None else attendu in trouves,
            "latence": float(hyp["latence_s"]) if hyp.get("latence_s") else None,
        })
    return lignes


def synthese(lignes: list[dict]) -> dict:
    avec_montant = [l for l in lignes if l["montant_ok"] is not None]
    latences = [l["latence"] for l in lignes if l["latence"] is not None]
    return {
        "n": len(lignes),
        "wer": sum(l["wer"] for l in lignes) / len(lignes),
        "cer": sum(l["cer"] for l in lignes) / len(lignes),
        "montants": (sum(l["montant_ok"] for l in avec_montant), len(avec_montant)),
        "latence_moy": sum(latences) / len(latences) if latences else None,
        "latence_max": max(latences) if latences else None,
    }


def pct(x: float) -> str:
    return f"{100 * x:.0f} %"


def ligne_synthese(nom: str, s: dict) -> str:
    ok, total = s["montants"]
    montants = f"{ok}/{total} ({pct(ok / total)})" if total else "—"
    return f"| {nom} | {s['n']} | {pct(s['wer'])} | {pct(s['cer'])} | {montants} |"


def rapport(lignes: list[dict], modele: str) -> str:
    g = synthese(lignes)
    out = [f"# Rapport de test ASR bambara — {modele}", ""]
    out += ["## Synthèse", "",
            "| Groupe | Phrases | WER | CER | Montants exacts |", "|---|---|---|---|---|",
            ligne_synthese("**Total**", g)]
    for cle, titre in (("environnement", "Environnement"), ("locuteur", "Locuteur")):
        groupes = defaultdict(list)
        for l in lignes:
            groupes[l[cle]].append(l)
        if len(groupes) > 1:
            out += [ligne_synthese(f"{titre} : {k}", synthese(v)) for k, v in sorted(groupes.items())]
    if g["latence_moy"] is not None:
        verdict = "OK" if g["latence_max"] < SEUIL_LATENCE_S else "au-dessus de l'objectif"
        out += ["", f"Latence : moyenne {g['latence_moy']:.1f} s, max {g['latence_max']:.1f} s "
                    f"(objectif < {SEUIL_LATENCE_S:.0f} s : {verdict})."]
    out += ["", "WER/CER = taux d'erreur par mot / par caractère (plus bas = mieux). "
                "Montant exact = le nombre prononcé est retrouvé dans la transcription.", ""]

    out += ["## Détail par phrase", "",
            "| id | Référence | Transcription | WER | Nombre attendu | Nombres trouvés | Montant |",
            "|---|---|---|---|---|---|---|"]
    for l in lignes:
        verdict = {True: "✅", False: "❌", None: "—"}[l["montant_ok"]]
        trouves = ", ".join(map(str, l["trouves"])) or "aucun"
        attendu = l["attendu"] if l["attendu"] is not None else "—"
        out.append(f"| {l['id']} | {l['reference']} | {l['transcription']} | {pct(l['wer'])} "
                   f"| {attendu} | {trouves} | {verdict} |")

    erreurs = [l for l in lignes if l["montant_ok"] is False]
    if erreurs:
        out += ["", "## Montants mal reconnus", ""]
        out += [f"- **{l['id']}** : attendu {l['attendu']}, trouvé "
                f"{', '.join(map(str, l['trouves'])) or 'aucun nombre'} — « {l['transcription']} »"
                for l in erreurs]
    return "\n".join(out) + "\n"


def main():
    # Windows attache souvent stdout à cp1252 : les caractères bambara (ɛ, ɔ...)
    # y provoquent une UnicodeEncodeError.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--corpus", type=Path, default=RACINE / "corpus" / "phrases.csv")
    p.add_argument("--transcriptions", type=Path, default=RACINE / "results" / "transcriptions.csv")
    p.add_argument("--rapport", type=Path, default=RACINE / "results" / "rapport.md")
    p.add_argument("--modele", default="FarmRadioInternational/bambara-whisper-asr")
    args = p.parse_args()

    lignes = evaluer(lire_csv(args.corpus), lire_csv(args.transcriptions))
    if not lignes:
        sys.exit("Aucune phrase commune entre le corpus (avec texte_bambara rempli) et les transcriptions.")
    texte = rapport(lignes, args.modele)
    args.rapport.write_text(texte, encoding="utf-8")
    print(texte)
    print(f"Rapport écrit dans {args.rapport}")


if __name__ == "__main__":
    main()
