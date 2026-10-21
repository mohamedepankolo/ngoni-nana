#!/usr/bin/env python3
"""Classification d'intention seule, sans groupes numériques ni attribution de
rôle — pour mesurer si séparer cette tâche (proposé après le protocole 7)
améliore l'exactitude par rapport au prompt combiné de `evaluer_segmente.py`.

Exemples:
  python evaluer_intention_seule.py --smoke
  python evaluer_intention_seule.py --model mistral:7b --output resultats_intention_seule.jsonl
"""
import argparse, csv, json, sys, time
from pathlib import Path

BASE = Path(__file__).resolve().parent
CORPUS = BASE.parent / "corpus" / "phrases_reelles.csv"
sys.path.insert(0, str(BASE))
from evaluer_segmente import decode_reply
from urllib import request

SYSTEM = '''Tu classes l intention d une phrase de comptabilite en bambara prononcee par une commercante.
Vocabulaire : feere=vendre (intention vente) ; san=acheter (intention achat) ; sara=payer (depense, OU rembourser une dette) ; jagokun=le capital de l entreprise (intention capital, PAS vente, meme si un nombre suit) ; juru=dette ; joli/jɔn=mot interrogatif (combien/qui), signale une question (intention consultation, PAS vente) ; bolo/tora=en stock/possession (intention stock).
Reponds uniquement en JSON strict : {"intention": "..."}. Valeurs possibles, UNE SEULE : vente, achat, depense, dette_client, capital, consultation, stock, inconnu.'''


def call_ollama(model, phrase, url, timeout):
    payload = json.dumps({
        "model": model, "stream": False, "format": "json", "options": {"temperature": 0},
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": phrase}],
    }, ensure_ascii=False).encode("utf-8")
    req = request.Request(url.rstrip("/") + "/api/chat", data=payload,
                           headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=timeout) as r:
        body = json.load(r)
    return decode_reply(body["message"]["content"])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="mistral:7b")
    p.add_argument("--url", default="http://localhost:11434")
    p.add_argument("--timeout", type=int, default=240)
    p.add_argument("--output", default=str(BASE / "resultats_intention_seule.jsonl"))
    p.add_argument("--smoke", action="store_true", help="Verification locale sans appel reseau")
    args = p.parse_args()

    if args.smoke:
        # Verifie juste que le prompt est bien forme (pas d'appel reseau).
        assert "jagokun" in SYSTEM and "consultation" in SYSTEM
        print("Smoke test OK (prompt bien forme)")
        return

    with open(CORPUS, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    rows = list({r["texte_bambara"]: r for r in reversed(rows)}.values())[::-1]

    results = []
    correct = 0
    for i, row in enumerate(rows, 1):
        phrase = row["texte_bambara"]
        try:
            data = call_ollama(args.model, phrase, args.url, args.timeout)
            intention_correcte = data.get("intention") == row["categorie"]
            correct += int(intention_correcte)
            obj = {"id": row["id"], "phrase": phrase, "categorie_reference": row["categorie"],
                   "intention_llm": data.get("intention"), "intention_correcte": intention_correcte}
        except Exception as e:
            obj = {"id": row["id"], "phrase": phrase, "erreur": str(e), "intention_correcte": False}
        results.append(obj)
        print(f"{i}/{len(rows)} {row['id']} correcte={obj['intention_correcte']}", flush=True)

    with open(args.output, "w", encoding="utf-8") as f:
        for x in results:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    print(f"BILAN intention : {correct}/{len(rows)} = {correct/len(rows):.1%} ; resultats : {args.output}")


if __name__ == "__main__":
    main()
