# -*- coding: utf-8 -*-
"""Teste un petit LLM réellement déployable (gratuit, local, CPU) sur le

même protocole que le test en aveugle du LLM puissant (voir
asr_test/COMPARAISON_LLM_COMPREHENSION.md). Les API payantes (Qwen 7B+,
Llama 3.1 8B) via le routeur d'inférence Hugging Face ont demandé des
crédits que ce compte n'a pas : testé ici un modèle assez petit pour
tourner localement sans frais, ce qui est d'ailleurs plus représentatif
d'un vrai déploiement à coût nul pour ce projet.
"""
import json
import re
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
MODELE = "Qwen/Qwen2.5-1.5B-Instruct"

GLOSSAIRE = """Tu es un assistant comptable vocal pour des commerçantes au Mali qui parlent bambara.
Vocabulaire bambara utile :
- "feere" = vendre/vendu (intention "vente") ; "san" = acheter/acheté (intention "achat") ;
  "sara" = payer/dépensé, ou régler une dette (intention "depense") ;
  "jagokun" = capital ; "juru" = dette ; "bolo"/"tora" = en stock/possession ;
  "joli"/"jon"/"jonw" = combien/qui (marque une question = "consultation").
- Mots grammaticaux à ignorer pour le produit/la personne : n, ne, ka, ye, bɛ, la, na, min, de, fɛ, kan, ma.
- Nombres : kelen=1, fila=2, saba=3, naani=4, duuru=5, wɔɔrɔ=6, wolonwula=7, seegin=8, kɔnɔntɔn=9,
  tan=10, mugan=20, kɛmɛ=100, waa=1000. "bi X"=dizaine (bi saba=30, bi duuru=50). "ni"=plus (addition).
- IMPORTANT : les montants sont presque toujours énoncés en dɔrɔmɛ SANS dire le mot "dɔrɔmɛ".
  1 dɔrɔmɛ = 5 FCFA. Donc multiplie par 5 le chiffre trouvé, sauf si "FCFA" est dit explicitement.

Réponds UNIQUEMENT avec un objet JSON (rien d'autre, pas de texte autour), avec exactement ces champs :
{"intention": "vente|achat|depense|dette_client|capital|consultation|stock",
 "produit": "..." ou null, "personne": "..." ou null, "quantite": nombre ou null,
 "montant_brut": nombre ou null, "montant_fcfa": nombre ou null,
 "informations_manquantes": [...], "action": "demander_confirmation|demander_montant|demander_quantite|demander_produit|repondre_directement"}

Phrase à interpréter : "{phrase}"
"""


def charger_modele():
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(MODELE)
    modele = AutoModelForCausalLM.from_pretrained(MODELE, torch_dtype=torch.bfloat16)
    modele.eval()
    return tokenizer, modele


def interpreter(tokenizer, modele, phrase: str) -> str:
    import torch

    messages = [{"role": "user", "content": GLOSSAIRE.replace("{phrase}", phrase)}]
    entree = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(entree, return_tensors="pt")
    with torch.no_grad():
        sortie = modele.generate(**inputs, max_new_tokens=300, do_sample=False,
                                   pad_token_id=tokenizer.eos_token_id)
    texte = tokenizer.decode(sortie[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    return texte.strip()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    import csv
    with open(RACINE / "asr_test" / "corpus" / "phrases_reelles.csv", encoding="utf-8") as f:
        lignes = list(csv.DictReader(f))
    vus = {}
    for l in lignes:
        vus.setdefault(l["texte_bambara"], l)

    print(f"Chargement de {MODELE}...")
    debut_chargement = time.time()
    tokenizer, modele = charger_modele()
    print(f"Chargé en {time.time() - debut_chargement:.1f}s")

    resultats = []
    for i, (texte, ligne) in enumerate(vus.items(), 1):
        debut = time.time()
        reponse = interpreter(tokenizer, modele, texte)
        duree = time.time() - debut
        resultats.append({"num": i, "id_corpus": ligne["id"], "texte": texte,
                           "categorie_attendue": ligne["categorie"],
                           "montant_attendu": ligne["montant_fcfa"],
                           "reponse_brute": reponse, "duree_s": round(duree, 1)})
        print(f"{i:2d}. ({duree:4.1f}s) {texte[:40]:40s} -> {reponse[:150]}")

    chemin_sortie = RACINE / "asr_test" / "results" / "llm_deploye_vs_corpus_reel.json"
    with open(chemin_sortie, "w", encoding="utf-8") as f:
        json.dump(resultats, f, ensure_ascii=False, indent=2)
    print(f"\nÉcrit : {chemin_sortie}")


if __name__ == "__main__":
    main()
