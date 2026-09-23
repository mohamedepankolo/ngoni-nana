"""Transcrit les enregistrements du corpus avec un modèle ASR Hugging Face.

Usage (local ou Colab) :
    export HF_TOKEN=hf_...   # le modèle est à accès restreint : accepter les conditions sur sa page
    python asr_test/scripts/transcrire.py
    python asr_test/scripts/transcrire.py --modele autre/modele --sortie asr_test/results/autre.csv

Lit asr_test/corpus/phrases.csv, transcrit chaque fichier de la colonne
`fichier_audio` (relatif à asr_test/audio/) et écrit un CSV
id, fichier_audio, transcription, latence_s.
"""
import argparse
import csv
import os
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
MODELE_DEFAUT = "FarmRadioInternational/bambara-whisper-asr"


def charger_pipeline(modele: str, device: str | None):
    import torch
    from transformers import pipeline

    if device is None:
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
    return pipeline(
        "automatic-speech-recognition",
        model=modele,
        token=os.environ.get("HF_TOKEN"),
        device=device,
        chunk_length_s=30,
    )


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--modele", default=MODELE_DEFAUT)
    p.add_argument("--corpus", type=Path, default=RACINE / "corpus" / "phrases.csv")
    p.add_argument("--audio", type=Path, default=RACINE / "audio")
    p.add_argument("--sortie", type=Path, default=RACINE / "results" / "transcriptions.csv")
    p.add_argument("--device", default=None, help="cpu, cuda:0... (auto par défaut)")
    args = p.parse_args()

    with open(args.corpus, newline="", encoding="utf-8") as f:
        lignes = [l for l in csv.DictReader(f) if l.get("fichier_audio")]
    manquants = [l["fichier_audio"] for l in lignes if not (args.audio / l["fichier_audio"]).exists()]
    if manquants:
        print(f"Fichiers audio absents de {args.audio} : {', '.join(manquants)}", file=sys.stderr)
    lignes = [l for l in lignes if l["fichier_audio"] not in manquants]
    if not lignes:
        sys.exit("Aucun enregistrement à transcrire.")

    asr = charger_pipeline(args.modele, args.device)
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    with open(args.sortie, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "fichier_audio", "transcription", "latence_s"])
        for l in lignes:
            debut = time.perf_counter()
            texte = asr(str(args.audio / l["fichier_audio"]))["text"].strip()
            latence = time.perf_counter() - debut
            w.writerow([l["id"], l["fichier_audio"], texte, f"{latence:.2f}"])
            print(f"[{l['id']}] {latence:.1f}s  {texte}")
    print(f"\n{len(lignes)} transcriptions écrites dans {args.sortie}")


if __name__ == "__main__":
    main()
