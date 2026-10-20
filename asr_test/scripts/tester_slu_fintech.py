# -*- coding: utf-8 -*-
"""Évaluation de RobotsMali/soloni-ic-slot-fintech-v0 sur notre corpus réel.

Contexte (voir Communications/instructions.docx) : ce modèle fait de la
compréhension directe voix -> intention + entités (SLU), sans passer par un
transcript intermédiaire. Mais son ontologie est fermée et conçue pour de la
banque mobile (transfert d'argent, consultation de solde, déconnexion, FAQ),
PAS pour notre domaine (vente/dépense/stock/client/capital GERME). Ce script
vérifie concrètement ce que le modèle produit sur nos 60 phrases réelles,
plutôt que de se fier à la seule documentation du modèle.

Nécessite nemo-toolkit==2.5.0 (venv isolé .venv_slu_eval/, pas le venv
principal du projet : la version de nemo-toolkit utilisée pour l'ASR en
production, soloni-be-kalan-v0, est plus récente et incompatible avec cette
classe SLUIntentSlotBPEModel).
"""
import csv
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

RACINE = Path(__file__).resolve().parents[2]
CORPUS = RACINE / "asr_test" / "corpus" / "phrases_reelles.csv"
AUDIO_DIR = RACINE / "asr_test" / "audio"

load_dotenv(RACINE / ".env")  # HF_TOKEN, nécessaire pour from_pretrained


def _patch_compat_nemo():
    """Mêmes correctifs que asr_test/scripts/transcrire.py (bugs de

    compatibilité NeMo sous Python < 3.12 / checkpoints anciens) : sans
    effet si NeMo a déjà corrigé ces bugs entre-temps.
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
            return (
                getattr(cfg, "model_path", None) is None
                and getattr(cfg, "key_phrases_file", None) is None
                and (not getattr(cfg, "key_phrases_list", None))
                and (not getattr(cfg, "key_phrase_items_list", None))
            )

        bgb.BoostingTreeModelConfig.is_empty = staticmethod(is_empty_compat)
    except ImportError:
        pass


def charger_modele():
    _patch_compat_nemo()
    from nemo.collections.asr.models import SLUIntentSlotBPEModel

    modele = SLUIntentSlotBPEModel.from_pretrained("RobotsMali/soloni-ic-slot-fintech-v0")

    # Patches de compatibilité NeMo 2.x documentés sur la page du modèle.
    modele.decoder.freeze = lambda: None
    modele.decoder.unfreeze = lambda *args, **kwargs: None

    original_decode = modele.sequence_generator.decode_semantics_from_tokens

    def patched_decode(seq_tokens):
        if isinstance(seq_tokens, tuple):
            seq_tokens = seq_tokens[0]
        return original_decode(seq_tokens)

    modele.sequence_generator.decode_semantics_from_tokens = patched_decode
    modele.eval()
    return modele


def lire_corpus():
    with open(CORPUS, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    modele = charger_modele()
    lignes = lire_corpus()

    resultats = []
    for ligne in lignes:
        chemin_audio = AUDIO_DIR / ligne["fichier_audio"]
        if not chemin_audio.exists():
            continue
        try:
            sortie = modele.transcribe([str(chemin_audio)])[0]
        except Exception as e:  # noqa: BLE001 : on veut voir TOUTES les pannes, pas juste la 1ere
            sortie = f"ERREUR: {e}"
        resultats.append({
            "id": ligne["id"],
            "categorie": ligne["categorie"],
            "texte_bambara": ligne["texte_bambara"],
            "montant_fcfa_attendu": ligne["montant_fcfa"],
            "sortie_slu": str(sortie),
        })
        print(f"{ligne['id']:6s} ({ligne['categorie']:12s}) -> {sortie}")

    chemin_sortie = RACINE / "asr_test" / "results" / "slu_fintech_vs_corpus_reel.json"
    chemin_sortie.parent.mkdir(exist_ok=True)
    with open(chemin_sortie, "w", encoding="utf-8") as f:
        json.dump(resultats, f, ensure_ascii=False, indent=2)
    print(f"\nÉcrit : {chemin_sortie}")


if __name__ == "__main__":
    main()
