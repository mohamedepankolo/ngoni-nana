# Guide de lancement du protocole 8

Procédure complète, de la collecte à la mesure. Chaque étape utilise un
outil déjà construit et testé — rien dans ce guide ne suppose un
développement supplémentaire.

## Étape 0 — collecte (Fadima / animatrices, pas l'assistant de programmation)

1. Lire `PROTOCOLE_8_SCENARIOS.md` (25 scénarios, familles A-K).
2. Pour chaque scénario, une ou plusieurs locutrices **nouvelles** (pas
   L01/L02/L03, déjà utilisées pour affiner les prompts) formulent
   naturellement la situation en bambara.
3. Remplir `gabarit_annotation_protocole8.csv` : une ligne par formulation,
   `statut_validation = a_valider` par défaut.
4. Dès qu'une personne compétente confirme une ligne, passer son
   `statut_validation` à `validee` et renseigner `date_validation`.

## Étape 1 — contrôle du corpus collecté

```bash
cd asr_test/scripts
python importer_corpus_protocole8.py chemin/vers/corpus_reel.csv
```

Corrige toute erreur signalée AVANT de passer à l'étape suivante — en
particulier : identifiants dupliqués, locutrices du corpus existant
(L01-L03) mélangées par erreur, tours de conversation discontinus, JSON
invalide dans `montants_multiples_attendus`.

Pour vérifier qu'aucune locutrice réservée à l'évaluation ne fuite vers un
usage de développement :

```bash
python importer_corpus_protocole8.py corpus_reel.csv --locuteurs-test L05,L06
```

## Étape 2 — génération des sorties du prototype sémantique

Sur les lignes au statut `validee` uniquement (jamais sur `a_valider` —
mesurer sur des formulations non confirmées fausserait le résultat) :

```bash
python prototype_semantique_v1.py --phrase "<texte_bambara de la ligne>"
```

Chaque sortie est déjà validée (`erreurs_validation` dans le résultat) avant
d'être retenue — une sortie non conforme au schéma doit être signalée, pas
intégrée silencieusement aux résultats.

Pour traiter tout le corpus d'un coup, écrire les résultats en JSONL (une
ligne par `id` du gabarit) avant l'étape 3 — script à écrire à ce moment-là
si le volume le justifie, pas avant (pas de généralisation prématurée sur
un format de sortie non encore éprouvé à l'échelle).

## Étape 3 — mesure des 9+ métriques

```bash
python evaluer_metriques.py --gabarit ../v2/gabarit_annotation_protocole8.csv \
    --sorties resultats_protocole8.jsonl --output rapport_protocole8.json
```

Lire le rapport métrique par métrique (pas seulement le taux de montants
exacts) — en particulier `8_taux_fausses_confirmations` et
`7b_taux_faux_negatifs_ambiguite_critique`, les deux plus critiques pour la
sécurité des écritures comptables.

## Étape 4 — publication des résultats

Documenter dans un nouveau fichier (`PROTOCOLE_8_RESULTATS.md`, à créer à ce
moment-là) : le nombre de locutrices distinctes, la répartition par
scénario, les 9 métriques, et toute anomalie trouvée par
`valider_semantique.py` sur des sorties réelles. Ne jamais présenter un
résultat sur ce corpus comme généralisant au-delà de ce qui a été
réellement testé (même règle que pour les protocoles 1-7, voir
`AUDIT_PROTOCOLES_1_A_7.md`).

## Rappel des garde-fous actifs à cette étape

- `dette_fournisseur` : effet toujours forcé à `aucun` (schéma v1.2.0) —
  aucune écriture réelle tant que ce cas d'usage n'est pas confirmé par une
  locutrice ET validé métier séparément de ce protocole.
- Le montant final n'est jamais calculé par le LLM (`prototype_semantique_v1.py`
  l'assemble déterministiquement après le rôle proposé).
- Aucune donnée de ce protocole ne doit servir à ajuster un prompt a
  posteriori sans créer un nouveau sous-ensemble de validation — sinon le
  corpus "indépendant" cesse de l'être pour les mesures suivantes.
