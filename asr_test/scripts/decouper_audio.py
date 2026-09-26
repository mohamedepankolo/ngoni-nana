"""Découpe un enregistrement contenant plusieurs phrases à la suite (silences
entre chaque phrase) en fichiers individuels, et transcrit chacun pour
faciliter l'association manuelle aux ids du corpus (P01, P02...).

Usage :
    python asr_test/scripts/decouper_audio.py fichier.mp4 --locuteur L01
    python asr_test/scripts/decouper_audio.py fichier.ogg --locuteur L02 --seuil-db 35

Écrit les segments dans asr_test/audio/segments/<locuteur>/<locuteur>_NN.wav
et un CSV récapitulatif (segments, durée, aperçu transcrit) à côté, pour
relecture avant de remplir corpus/phrases.csv.
"""
import argparse
import csv
import sys
from pathlib import Path

import librosa
import soundfile as sf

RACINE = Path(__file__).resolve().parents[1]


def decouper(chemin_audio: Path, seuil_db: float, duree_min_s: float, marge_s: float, fusion_max_s: float):
    """Renvoie une liste de (debut_s, fin_s, y) pour chaque segment non silencieux.

    Découpe d'abord finement (sensible aux silences), puis refusionne les
    segments consécutifs séparés par une pause courte (< fusion_max_s) : une
    locutrice qui marque des pauses entre les mots d'une même phrase sinon
    fait éclater chaque phrase en plusieurs segments (observé : jusqu'à 2-3
    segments pour une seule phrase). Une vraie pause entre deux phrases est
    presque toujours plus longue que ça.
    """
    y, sr = librosa.load(chemin_audio, sr=16000, mono=True)
    intervalles = librosa.effects.split(y, top_db=seuil_db)
    intervalles = [(d, f) for d, f in intervalles if (f - d) / sr >= duree_min_s]

    fusionnes = []
    for debut, fin in intervalles:
        if fusionnes and (debut - fusionnes[-1][1]) / sr < fusion_max_s:
            fusionnes[-1] = (fusionnes[-1][0], fin)
        else:
            fusionnes.append((debut, fin))

    marge = int(marge_s * sr)
    segments = []
    for debut, fin in fusionnes:
        debut_m = max(0, debut - marge)
        fin_m = min(len(y), fin + marge)
        segments.append((debut_m / sr, fin_m / sr, y[debut_m:fin_m]))
    return segments, sr


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("audio", type=Path, help="fichier brut (mp4, ogg, mp3, wav...)")
    p.add_argument("--locuteur", required=True, help="code de la locutrice, ex. L01")
    p.add_argument("--sortie", type=Path, default=None,
                    help="dossier de sortie (défaut : asr_test/audio/segments/<locuteur>)")
    p.add_argument("--seuil-db", type=float, default=30.0,
                    help="sensibilité de détection du silence (défaut 30 ; plus bas = plus strict)")
    p.add_argument("--duree-min", type=float, default=0.4,
                    help="durée minimale d'un segment en secondes, pour ignorer les bruits parasites (défaut 0.4)")
    p.add_argument("--marge", type=float, default=0.15,
                    help="marge ajoutée avant/après chaque segment, en secondes (défaut 0.15)")
    p.add_argument("--fusion-max", type=float, default=0.7,
                    help="pause maximale (s) pour fusionner deux segments consécutifs "
                         "en un seul, ex. mots d'une même phrase (défaut 0.7)")
    p.add_argument("--transcrire", action="store_true", default=True,
                    help="transcrit chaque segment pour prévisualisation (activé par défaut)")
    p.add_argument("--no-transcrire", dest="transcrire", action="store_false")
    # RobotsMali par défaut : sous la seconde par segment, contre 16-38s pour
    # FarmRadioInternational — indispensable ici vu le nombre de segments à
    # prévisualiser d'un coup. C'est un aperçu de travail, pas le test final.
    p.add_argument("--modele", default="RobotsMali/soloni-114m-tdt-ctc-v3")
    p.add_argument("--backend", choices=["transformers", "nemo"], default=None)
    args = p.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    sortie = args.sortie or (RACINE / "audio" / "segments" / args.locuteur)
    sortie.mkdir(parents=True, exist_ok=True)

    print(f"Découpage de {args.audio.name}...")
    segments, sr = decouper(args.audio, args.seuil_db, args.duree_min, args.marge, args.fusion_max)
    print(f"{len(segments)} segments détectés (seuil {args.seuil_db} dB).")

    asr = None
    if args.transcrire:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from transcrire import charger_pipeline
        backend = args.backend or ("nemo" if args.modele.startswith("RobotsMali/") else "transformers")
        print(f"Chargement du modèle {args.modele} ({backend}) pour prévisualisation...")
        asr = charger_pipeline(args.modele, backend, None, 256)

    lignes = []
    for i, (debut, fin, y) in enumerate(segments, start=1):
        nom = f"{args.locuteur}_{i:02d}.wav"
        chemin = sortie / nom
        sf.write(chemin, y, sr)
        apercu = ""
        if asr is not None:
            apercu = asr(str(chemin)).strip()
        lignes.append({
            "segment": i, "fichier": str(chemin.relative_to(RACINE)),
            "debut_s": f"{debut:.2f}", "fin_s": f"{fin:.2f}", "duree_s": f"{fin - debut:.2f}",
            "apercu_transcription": apercu,
        })
        print(f"[{i:02d}] {fin - debut:4.1f}s  {apercu}")

    csv_sortie = sortie / f"{args.locuteur}_segments.csv"
    with open(csv_sortie, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["segment", "fichier", "debut_s", "fin_s", "duree_s", "apercu_transcription"])
        w.writeheader()
        w.writerows(lignes)
    print(f"\nRécapitulatif écrit dans {csv_sortie}")


if __name__ == "__main__":
    main()
