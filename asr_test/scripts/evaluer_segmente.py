#!/usr/bin/env python3
"""Variante B : segmentation numérique déterministe + LLM qui attribue
seulement un rôle à chaque groupe déjà délimité par `montants.extraire_groupes`.

Le LLM ne voit plus la phrase brute pour le calcul : il reçoit des groupes
numériques déjà reconnus (texte + valeur en dɔrɔmɛ), et doit seulement dire
lequel est la quantité, lequel est le montant. Objectif : éliminer la
troncature/régurgitation observée au protocole 6 (évaluation complète,
`evaluer_hybride.py`), où le LLM devait lui-même repérer les frontières du
nombre dans le texte.

Exemples:
  python evaluer_segmente.py --smoke
  python evaluer_segmente.py --model mistral:7b --output resultats_segmentes.jsonl
"""
import argparse, csv, json, re, sys, time
from pathlib import Path
from urllib import request

BASE = Path(__file__).resolve().parent
CORPUS = BASE.parent / "corpus" / "phrases_reelles.csv"
sys.path.insert(0, str(BASE))
from montants import extraire_groupes

SYSTEM = '''Tu analyses une phrase de comptabilite prononcee en bambara, deja decoupee en groupes numeriques reconnus par un analyseur deterministe (tu n'as RIEN a calculer).
Pour chaque groupe numerique fourni (identifiant, texte, valeur deja en dorome), dis quel role il joue dans la phrase. Roles possibles : "quantite" (nombre d'articles), "montant" (le prix/montant total de l'operation), "prix_unitaire" (prix par article, si distinct du montant total), "autre" (ex. numero de telephone, date - n'a rien a voir avec la transaction).
Un groupe peut n'avoir AUCUN role pertinent (role "autre"). Si deux groupes semblent tous les deux plausibles pour "montant", signale-le dans "ambiguite".
Comprends aussi l'intention de la phrase : feere=vente, san=achat, sara=versement/depense (le sens depend du contexte), jagokun=capital, juru=dette ; jolie/joli/jɔn=question=consultation.
Reponds uniquement en JSON strict : {"intention": "...", "produit": "..." ou null, "personne": "..." ou null, "roles": {"N1": "...", "N2": "..."}, "ambiguite": "..." ou null}. Valeurs d'intention : vente, achat, depense, dette_client, capital, consultation, stock, inconnu.'''


def decode_reply(content):
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', content, re.S)
        if not m:
            raise
        return json.loads(m.group())


def call_ollama(model, phrase, groupes, url, timeout):
    groupes_pour_llm = [{"id": f"N{i+1}", "texte": g["texte"], "valeur_dorome": g["valeur"]}
                         for i, g in enumerate(groupes)]
    contenu = json.dumps({"phrase": phrase, "groupes_numeriques": groupes_pour_llm}, ensure_ascii=False)
    payload = json.dumps({
        "model": model, "stream": False, "format": "json", "options": {"temperature": 0},
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": contenu}],
    }, ensure_ascii=False).encode("utf-8")
    req = request.Request(url.rstrip("/") + "/api/chat", data=payload,
                           headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=timeout) as r:
        body = json.load(r)
    return decode_reply(body["message"]["content"])


def evaluate(groupes, gt_fcfa, data):
    roles = dict(data.get("roles") or {})
    # ATTENTION (retire apres relecture) : une premiere version de ce code
    # forcait automatiquement "montant" des qu'un seul groupe numerique
    # existait et que l'intention n'etait pas "stock". Corrige sur les 4 cas
    # du corpus actuel (dette/depense sans comptage d'articles), mais c'est
    # un surajustement dangereux : une phrase comme "j'ai vendu trois sacs
    # de riz" (quantite seule, prix absent, absente de ce corpus) aurait ete
    # lue comme un montant de 15 F CFA invente. Remplace par un signalement
    # d'ambiguite plutot qu'une decision automatique, conformement a
    # l'exigence « 0 transaction inventee » : le systeme doit demander une
    # precision, pas deviner silencieusement.
    ids_montant = [gid for gid, role in roles.items() if role == "montant"]
    expected = int(gt_fcfa) if gt_fcfa else None
    if len(groupes) == 1 and data.get("intention") not in ("stock", "consultation") and not ids_montant:
        # Un seul groupe, pas deja marque "montant" par le LLM, intention
        # financiere : ambigu (quantite seule, SANS prix ? ou montant mal
        # etiquete ?) - a signaler, pas a trancher ici.
        return {"roles": roles, "montant_fcfa_calcule": None, "montant_fcfa_attendu": expected,
                "montant_exact": False, "role_ambigu": True,
                "clarification_necessaire": "un seul nombre present : est-ce la quantite ou le montant ?"}
    if len(ids_montant) != 1:
        # Zero ou plusieurs groupes marques "montant" : pas de reponse exploitable.
        return {"roles": roles, "montant_fcfa_calcule": None, "montant_fcfa_attendu": expected,
                "montant_exact": expected is None, "role_ambigu": True}
    idx = int(ids_montant[0][1:]) - 1
    valeur_dorome = groupes[idx]["valeur"] if 0 <= idx < len(groupes) else None
    montant = valeur_dorome * 5 if valeur_dorome is not None else None
    return {"roles": roles, "montant_fcfa_calcule": montant, "montant_fcfa_attendu": expected,
            "montant_exact": montant == expected if expected is not None else montant is None,
            "role_ambigu": False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="mistral:7b")
    p.add_argument("--url", default="http://localhost:11434")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--timeout", type=int, default=240)
    p.add_argument("--output", default=str(BASE / "resultats_segmentes.jsonl"))
    p.add_argument("--smoke", action="store_true", help="Verification locale sans appel reseau")
    args = p.parse_args()

    with open(CORPUS, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    rows = list({row["texte_bambara"]: row for row in reversed(rows)}.values())[::-1]
    if args.limit:
        rows = rows[:args.limit]

    if args.smoke:
        phrase = "n ye saga saba feere waa mugan ni duuru"
        groupes = extraire_groupes(phrase)
        data = {"intention": "vente", "produit": "saga", "personne": None,
                "roles": {"N1": "quantite", "N2": "montant"}, "ambiguite": None}
        rep = evaluate(groupes, 125000, data)
        print(phrase, "->", groupes, "->", rep)
        assert rep["montant_exact"] is True
        print("Smoke test OK")
        return

    results = []
    for i, row in enumerate(rows, 1):
        phrase = row["texte_bambara"]
        groupes = extraire_groupes(phrase)
        t = time.monotonic()
        try:
            if not groupes:
                data = {"intention": "inconnu", "roles": {}}
            else:
                data = call_ollama(args.model, phrase, groupes, args.url, args.timeout)
            rep = evaluate(groupes, row["montant_fcfa"], data)
            obj = {"id": row["id"], "phrase": phrase, "categorie_reference": row["categorie"],
                   "groupes": groupes, "sortie_modele": data, "temps_s": round(time.monotonic() - t, 2), **rep}
        except Exception as e:
            obj = {"id": row["id"], "phrase": phrase, "erreur": str(e), "montant_exact": False}
        results.append(obj)
        print(f"{i}/{len(rows)} {row['id']} montant_exact={obj.get('montant_exact')} "
              f"{obj.get('montant_fcfa_calcule')} attendu={row['montant_fcfa']}", flush=True)

    with open(args.output, "w", encoding="utf-8") as f:
        for x in results:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    valid = [x for x in results if x.get("montant_fcfa_attendu") is not None]
    exact = sum(x.get("montant_exact", False) for x in valid)
    print(f"BILAN montants : {exact}/{len(valid)} exacts ; resultats : {args.output}")


if __name__ == "__main__":
    main()
