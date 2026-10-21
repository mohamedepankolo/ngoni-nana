#!/usr/bin/env python3
"""Évaluation reproductible du protocole hybride N'GONI NANA.

Dépendances: pip install requests (pour un vrai test Ollama).
Exemples:
  python evaluer_hybride.py --smoke
  python evaluer_hybride.py --model mistral:7b --limit 53 --output resultats_hybrides.jsonl
Lance Ollama sur http://localhost:11434 sur la même machine.
"""
import argparse, csv, json, re, sys, time
from pathlib import Path
from urllib import request

BASE = Path(__file__).resolve().parent
CORPUS = BASE.parent / "corpus" / "phrases_reelles.csv"
sys.path.insert(0, str(BASE))
from montants import extraire_nombres

SYSTEM = '''Tu analyses une phrase de comptabilité prononcée en bambara.
Ne calcule AUCUN nombre. Recopie EXACTEMENT depuis la phrase originale les groupes de mots indiquant (1) la quantité d'articles et (2) le montant financier. Ne change ni l'ordre ni l'orthographe. Ne déduis jamais une quantité absente. Ne coupe jamais un groupe de montant en plusieurs morceaux : «waa kelen ni kɛmɛ duuru» est un seul montant. Si tu es incertain, utilise null. Comprends l'intention à l'aide de feere=vente, san=achat, sara=versement/dépense (le sens dépend du contexte), jagokun=capital, juru=dette; jolie/joli/jɔn=question.
Réponds uniquement en JSON strict avec les champs intention, produit, personne, quantite_texte, expression_montant, ambiguite. Valeurs possibles d'intention : vente, achat, depense, dette_client, capital, consultation, stock, inconnu.
Unité monétaire : ne fais aucune conversion. Le calcul est réalisé après extraction et validation.'''

def strict_span(source, span):
    if span is None: return True
    if not isinstance(span, str) or not span.strip(): return False
    return bool(re.search(r'(?<!\w)'+re.escape(span.strip())+r'(?!\w)', source, re.I))

def decode_reply(content):
    try: return json.loads(content)
    except json.JSONDecodeError:
        m=re.search(r'\{.*\}',content,re.S)
        if not m: raise
        return json.loads(m.group())

def call_ollama(model, phrase, url, timeout):
    payload=json.dumps({'model':model,'stream':False,'format':'json','options':{'temperature':0},'messages':[{'role':'system','content':SYSTEM},{'role':'user','content':phrase}]},ensure_ascii=False).encode('utf-8')
    req=request.Request(url.rstrip('/')+'/api/chat',data=payload,headers={'Content-Type':'application/json'},method='POST')
    with request.urlopen(req,timeout=timeout) as r: body=json.load(r)
    return decode_reply(body['message']['content'])

def evaluate(phrase, gt_fcfa, data):
    expr=data.get('expression_montant')
    qexpr=data.get('quantite_texte')
    spans_ok=strict_span(phrase,expr) and strict_span(phrase,qexpr)
    overlaps=False
    if expr and qexpr and spans_ok:
        a=phrase.lower().find(expr.lower());b=phrase.lower().find(qexpr.lower())
        overlaps=not (a+len(expr)<=b or b+len(qexpr)<=a)
    values=extraire_nombres(expr) if expr and spans_ok and not overlaps else []
    # Ne pas utiliser max() si l'extraction a produit plusieurs valeurs : situation ambiguë.
    parsed=values[0] if len(values)==1 else None
    amount=parsed*5 if parsed is not None else None
    expected=int(gt_fcfa) if gt_fcfa else None
    return {'expression_valide':spans_ok,'chevauchement':overlaps,'nombres_extraits':values,'montant_fcfa_calcule':amount,'montant_fcfa_attendu':expected,'montant_exact':amount==expected if expected is not None else amount is None,'a_clarifier':not spans_ok or overlaps or (expected is not None and parsed is None) or bool(data.get('ambiguite'))}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--model',default='mistral:7b');p.add_argument('--url',default='http://localhost:11434')
    p.add_argument('--limit',type=int,default=0);p.add_argument('--timeout',type=int,default=240)
    p.add_argument('--output',default=str(BASE/'resultats_hybrides.jsonl'))
    p.add_argument('--smoke',action='store_true',help='Vérification sans modèle à partir des quatre réponses du rapport')
    args=p.parse_args()
    with open(CORPUS,encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    # Ne conserver que la première occurrence de chaque phrase distincte.
    rows=list({row['texte_bambara']:row for row in reversed(rows)}.values())[::-1]
    if args.smoke:
        fixtures={
         'n ye saga saba feere wa bi duuru': {'intention':'vente','quantite_texte':'saba','expression_montant':'wa bi duuru'},
         'n ka jagokun ye waa tan ye': {'intention':'consultation','quantite_texte':None,'expression_montant':'waa tan'},
         'n ye saga saba feere waa mugan ni duuru': {'intention':'vente','quantite_texte':'saba','expression_montant':'waa mugan ni duuru'},
         'n ye fini san waa kelen ni kɛmɛ duuru': {'intention':'achat','quantite_texte':'waa kelen','expression_montant':'kɛmɛ duuru'}
        }
        rows=[r for r in rows if r['texte_bambara'] in fixtures]
    else: fixtures={}
    if args.limit: rows=rows[:args.limit]
    results=[]
    for i,row in enumerate(rows,1):
        phrase=row['texte_bambara'];t=time.monotonic()
        try:
            data=fixtures[phrase] if args.smoke else call_ollama(args.model,phrase,args.url,args.timeout)
            report=evaluate(phrase,row['montant_fcfa'],data)
            obj={'id':row['id'],'phrase':phrase,'categorie_reference':row['categorie'],'sortie_modele':data,'temps_s':round(time.monotonic()-t,2),**report}
        except Exception as e:
            obj={'id':row['id'],'phrase':phrase,'erreur':str(e),'montant_exact':False}
        results.append(obj)
        print(f"{i}/{len(rows)} {row['id']} montant_exact={obj['montant_exact']} {obj.get('montant_fcfa_calcule')} attendu={row['montant_fcfa']}",flush=True)
    with open(args.output,'w',encoding='utf-8') as f:
        for x in results:f.write(json.dumps(x,ensure_ascii=False)+'\n')
    valid=[x for x in results if x.get('montant_fcfa_attendu') is not None]
    exact=sum(x.get('montant_exact',False) for x in valid)
    print(f'BILAN montants : {exact}/{len(valid)} exacts ; résultats : {args.output}')
    if args.smoke:
        assert len(results)==4 and exact==3, 'Le bilan doit reproduire les 3/4 du protocole 6'

if __name__=='__main__':main()
