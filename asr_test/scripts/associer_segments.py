"""Propose une association segment <-> id de phrase (P01...P20), en comparant
le montant attendu de chaque phrase du corpus au(x) nombre(s) détecté(s) dans
l'aperçu de transcription de chaque segment (produit par decouper_audio.py).

C'est une aide à la relecture manuelle, pas une vérité : une phrase sans
montant (P17-P19), un montant ambigu ou plusieurs segments candidats doivent
être tranchés à l'oreille.

Usage :
    python asr_test/scripts/associer_segments.py asr_test/audio/segments/L01/L01_segments.csv
"""
import argparse
import csv
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from montants import extraire_nombres  # noqa: E402


def nombres_attendus(ref: dict) -> dict:
    """Renvoie {interprétation: valeur} — on ne sait pas encore, avant
    d'écouter, si la locutrice a dit le montant en francs ou en dɔrɔmɛ
    (le protocole demande de corriger `unite` après coup selon ce qui a
    été dit) : on cherche donc les deux valeurs possibles dans les
    segments, plutôt que de se fier à l'unité pré-remplie dans le corpus.
    """
    if not ref.get("montant_fcfa"):
        return {}
    montant = int(ref["montant_fcfa"])
    valeurs = {"fcfa": montant}
    if montant % 5 == 0:
        valeurs["dorome"] = montant // 5
    return valeurs


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("segments_csv", type=Path)
    p.add_argument("--corpus", type=Path, default=RACINE / "corpus" / "phrases.csv")
    args = p.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    with open(args.corpus, newline="", encoding="utf-8") as f:
        phrases = list(csv.DictReader(f))
    with open(args.segments_csv, newline="", encoding="utf-8") as f:
        segments = list(csv.DictReader(f))
    for s in segments:
        s["nombres"] = extraire_nombres(s["apercu_transcription"])

    utilises = set()
    print(f"{'id':4} {'fcfa':>8} {'dorome':>7}  segment(s) candidat(s)")
    print("-" * 80)
    for ref in phrases:
        valeurs = nombres_attendus(ref)
        if not valeurs:
            print(f"{ref['id']:4} {'—':>8} {'—':>7}  (pas de montant — à faire à l'oreille : « {ref['sens_fr']} »)")
            continue
        etiquette = f"{valeurs.get('fcfa', '—'):>8} {valeurs.get('dorome', '—'):>7}"
        candidats = []
        for s in segments:
            for interpretation, val in valeurs.items():
                if val in s["nombres"]:
                    candidats.append((s, interpretation))
                    break
        if not candidats:
            print(f"{ref['id']:4} {etiquette}  AUCUN candidat — « {ref['sens_fr']} »")
        elif len(candidats) == 1:
            s, interpretation = candidats[0]
            utilises.add(s["segment"])
            print(f"{ref['id']:4} {etiquette}  [{s['segment']}] ({interpretation}) {s['apercu_transcription']}")
        else:
            print(f"{ref['id']:4} {etiquette}  {len(candidats)} candidats, à trancher :")
            for s, interpretation in candidats:
                print(f"          [{s['segment']}] ({interpretation}) {s['apercu_transcription']}")

    non_utilises = [s for s in segments if s["segment"] not in utilises]
    if non_utilises:
        print("\nSegments non réclamés par un montant (retakes probables, ou phrases sans montant) :")
        for s in non_utilises:
            print(f"  [{s['segment']}] {s['duree_s']}s  {s['apercu_transcription']}")


if __name__ == "__main__":
    main()
