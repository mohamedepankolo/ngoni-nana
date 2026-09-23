"""Transcrit les enregistrements du corpus avec un modèle ASR.

Usage (local ou Colab) :
    export HF_TOKEN=hf_...   # le modèle est à accès restreint : accepter les conditions sur sa page
    python asr_test/scripts/transcrire.py
    python asr_test/scripts/transcrire.py --modele autre/modele --sortie asr_test/results/autre.csv
    python asr_test/scripts/transcrire.py --modele RobotsMali/soloni-114m-tdt-ctc-v3 --backend nemo

Lit asr_test/corpus/phrases.csv, transcrit chaque fichier de la colonne
`fichier_audio` (relatif à asr_test/audio/) et écrit un CSV
id, fichier_audio, transcription, latence_s.

Deux moteurs (--backend) :
  - transformers (défaut) : modèles Hugging Face `pipeline`, ex. le modèle
    actuel FarmRadioInternational/bambara-whisper-asr ou MALIBA-AI/bambara-asr-v3.
  - nemo : modèles publiés au format NVIDIA NeMo, ex. RobotsMali/soloni-114m-tdt-ctc-v3
    (voir COMPARAISON_MODELES.md — bien plus rapide, licence libre, mais pas
    compatible `transformers`). Installer avec `pip install nemo-toolkit[asr]`.
"""
import argparse
import csv
import os
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
MODELE_DEFAUT = "FarmRadioInternational/bambara-whisper-asr"
MAX_NEW_TOKENS_DEFAUT = 256


def _patch_compat_nemo():
    """Contourne deux bugs de compatibilité rencontrés avec NeMo sous
    Python < 3.12 / checkpoints plus anciens (ex. RobotsMali/soloni-114m-tdt-ctc-v3,
    voir COMPARAISON_MODELES.md). Patché au runtime pour marcher sur
    n'importe quelle machine sans avoir à modifier site-packages à la main ;
    sans effet (et sans casser quoi que ce soit) si NeMo a corrigé ces bugs
    entre-temps.
    """
    import logging

    try:
        from nemo.utils import tar_utils

        if sys.version_info < (3, 12):
            def safe_extract_compat(tar, path, members=None, *, skip_unsafe=False):
                extract_to = os.path.realpath(path)
                os.makedirs(extract_to, exist_ok=True)
                if members is None:
                    members = tar.getmembers()
                extraits = []
                for membre in members:
                    membre = tar.getmember(membre) if isinstance(membre, str) else membre
                    if tar_utils.is_safe_tar_member(membre, extract_to):
                        # `filter=` (PEP 706) n'existe qu'à partir de Python 3.12
                        tar.extract(membre, extract_to)
                        extraits.append(membre)
                        continue
                    message = f"Skipping potentially unsafe tar member: {membre.name}"
                    if skip_unsafe:
                        logging.warning(message)
                        continue
                    raise tar_utils.TarPathTraversalError(message)
                return extraits

            tar_utils.safe_extract = safe_extract_compat
    except ImportError:
        pass

    try:
        from nemo.collections.asr.parts.context_biasing import boosting_graph_batched as bgb

        def is_empty_compat(cfg):
            # Un checkpoint plus ancien peut ne pas avoir ce champ dans sa
            # config struct OmegaConf : on le traite alors comme absent.
            return (
                getattr(cfg, "model_path", None) is None
                and getattr(cfg, "key_phrases_file", None) is None
                and (not getattr(cfg, "key_phrases_list", None))
                and (not getattr(cfg, "key_phrase_items_list", None))
            )

        bgb.BoostingTreeModelConfig.is_empty = staticmethod(is_empty_compat)
    except ImportError:
        pass


def charger_pipeline_transformers(modele: str, device: str | None, max_new_tokens: int):
    import torch
    from transformers import pipeline

    if device is None:
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
    asr = pipeline(
        "automatic-speech-recognition",
        model=modele,
        token=os.environ.get("HF_TOKEN"),
        device=device,
        chunk_length_s=30,
        # Filet de sécurité : sans limite, un modèle Whisper peut partir en
        # boucle de répétition sur un audio court et tourner indéfiniment
        # sans jamais rendre la main (observé avec MALIBA-AI/bambara-asr-v3 :
        # >1h sans sortie sur un clip de 2 s, CPU à fond, aucun blocage
        # apparent). 256 tokens ≈ largement de quoi transcrire une phrase.
        generate_kwargs={"max_new_tokens": max_new_tokens},
    )
    return lambda chemin: asr(chemin)["text"]


def charger_pipeline_nemo(modele: str):
    _patch_compat_nemo()
    import nemo.collections.asr as nemo_asr

    asr_model = nemo_asr.models.ASRModel.from_pretrained(model_name=modele)

    def transcrire_un(chemin):
        hyp = asr_model.transcribe([chemin])[0]
        return hyp.text if hasattr(hyp, "text") else str(hyp)

    return transcrire_un


def charger_pipeline(modele: str, backend: str, device: str | None, max_new_tokens: int):
    if backend == "nemo":
        return charger_pipeline_nemo(modele)
    return charger_pipeline_transformers(modele, device, max_new_tokens)


def main():
    # Windows attache souvent stdout à cp1252 : les caractères bambara (ɛ, ɔ...)
    # y provoquent une UnicodeEncodeError et coupent la boucle de transcription.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--modele", default=MODELE_DEFAUT)
    p.add_argument("--backend", choices=["transformers", "nemo"], default=None,
                    help="moteur d'inférence (auto : nemo pour un modèle RobotsMali/…, transformers sinon)")
    p.add_argument("--corpus", type=Path, default=RACINE / "corpus" / "phrases.csv")
    p.add_argument("--audio", type=Path, default=RACINE / "audio")
    p.add_argument("--sortie", type=Path, default=RACINE / "results" / "transcriptions.csv")
    p.add_argument("--device", default=None, help="cpu, cuda:0... (auto par défaut, backend transformers uniquement)")
    p.add_argument("--max-new-tokens", type=int, default=MAX_NEW_TOKENS_DEFAUT,
                    help="limite de tokens générés par phrase, pour éviter une boucle infinie "
                         "(défaut 256, backend transformers uniquement)")
    args = p.parse_args()
    backend = args.backend or ("nemo" if args.modele.startswith("RobotsMali/") else "transformers")

    with open(args.corpus, newline="", encoding="utf-8") as f:
        lignes = [l for l in csv.DictReader(f) if l.get("fichier_audio")]
    manquants = [l["fichier_audio"] for l in lignes if not (args.audio / l["fichier_audio"]).exists()]
    if manquants:
        print(f"Fichiers audio absents de {args.audio} : {', '.join(manquants)}", file=sys.stderr)
    lignes = [l for l in lignes if l["fichier_audio"] not in manquants]
    if not lignes:
        sys.exit("Aucun enregistrement à transcrire.")

    print(f"Backend : {backend}  |  Modèle : {args.modele}")
    asr = charger_pipeline(args.modele, backend, args.device, args.max_new_tokens)
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    with open(args.sortie, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "fichier_audio", "transcription", "latence_s"])
        for l in lignes:
            debut = time.perf_counter()
            texte = asr(str(args.audio / l["fichier_audio"])).strip()
            latence = time.perf_counter() - debut
            w.writerow([l["id"], l["fichier_audio"], texte, f"{latence:.2f}"])
            print(f"[{l['id']}] {latence:.1f}s  {texte}")
    print(f"\n{len(lignes)} transcriptions écrites dans {args.sortie}")


if __name__ == "__main__":
    main()
