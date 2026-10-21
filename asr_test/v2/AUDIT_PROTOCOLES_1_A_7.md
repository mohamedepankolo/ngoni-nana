# Audit des protocoles 1 à 7 — reproductibilité, annotation, risques de surajustement

Mission : vérifier que chaque score annoncé dans
`asr_test/COMPARAISON_LLM_COMPREHENSION.md` se reproduit depuis les
résultats bruts, et distinguer "montant correctement calculé" de
"transaction comptable correctement comprise".

## 1. Reproductibilité des scores annoncés

Chaque score a été recalculé directement depuis son fichier
`resultats_*.jsonl`, sans relire le texte du rapport. Les quatre scores
clés se reproduisent à l'identique :

| Score annoncé | Fichier source | Recalculé | Écart |
|---|---|---|---|
| Protocole 6 (LLM calcule lui-même) : 6/45 — 13,3 % | `resultats_hybrides.jsonl` | 6/45 — 13,3 % | aucun |
| Protocole 7 (segmentation + rôles, règle sûre) : 41/45 — 91,1 %, 4 ambiguës | `resultats_segmentes.jsonl` | 41/45 — 91,1 %, 4 ambiguës | aucun |
| Intention isolée (`mistral:7b`) brut : 35/53 — 66,0 % | `resultats_intention_seule.jsonl` | 35/53 — 66,0 % | aucun |
| Intention isolée "ajusté" : 45/53 — 84,9 % | idem, **reclassification**, pas exclusion — voir correction ci-dessous | 45/53 — 84,9 % | **terminologie corrigée, voir §1.1** |
| Intention isolée (`gemma2:9b`) brut/ajusté : 24/53 — 45,3 % / 34/53 — 64,2 % | `resultats_intention_gemma2.jsonl` | identique | aucun |

**Aucun écart trouvé.** Script de vérification utilisé : recalcul direct en
Python à partir des JSONL + du CSV de référence (pas de relecture du texte
narratif). Reproductible par quiconque avec les fichiers du dépôt.

### 1.1 Correction : le "score ajusté" de 85 % était mal nommé, pas mal calculé

Relecture reçue, à juste titre : "une exclusion de dix exemples donnerait un
dénominateur de 43, pas 53." Vérification faite — **le calcul n'excluait
pas ces 10 cas, il les reclassait** de "nouvel échec" à "désaccord déjà
connu", tout en gardant le dénominateur à 53. Le mot "exclusion" employé
dans `COMPARAISON_LLM_COMPREHENSION.md` était donc trompeur : il suggérait
un dénominateur réduit alors que le calcul réel en gardait un autre. Les
deux lectures possibles, désormais présentées **toutes les deux** plutôt
qu'une seule :

| Lecture | Calcul | Résultat |
|---|---|---|
| **Reclassification** (dénominateur inchangé) : les 10 cas déjà connus ne comptent plus comme un nouvel échec, mais restent dans le corpus mesuré | (35 corrects + 10 reclassés) / 53 | **45/53 = 84,9 %** |
| **Exclusion stricte** (dénominateur réduit) : les 10 cas déjà connus sont retirés du corpus mesuré | 35 corrects / (53 − 10) | **35/43 = 81,4 %** |

Les deux nombres sont proches (81-85 %) et le choix entre les deux ne change
pas la conclusion qualitative (l'écart réel avec le grand LLM est plus
restreint que le 66 % brut ne le suggérait). **Ni l'un ni l'autre ne doit
être présenté comme une performance générale validée ou une borne
inférieure garantie** : les 8 désaccords "vraiment nouveaux" (motifs A/B/C,
`DESACCORDS_LLM_A_VALIDER.md`) ne sont pas encore arbitrés par une
locutrice native — ils pourraient confirmer que le LLM a tort (le score
réel serait alors plus proche de 66 %) ou que le corpus est ambigu/mal
annoté sur ces cas (le score réel serait alors plus proche de 85 %). Tant
que l'arbitrage n'est pas fait, la fourchette honnête est **66 %-85 %**, pas
un chiffre unique.

## 2. Qualité et limites du corpus de référence

`asr_test/corpus/phrases_reelles.csv` : 60 lignes, **53 phrases distinctes**
(7 doublons texte-identique supprimés par déduplication systématique dans
tous les scripts — `{texte: ligne for ligne in reversed(lignes)}`, garde la
première occurrence). Répartition :

- **Catégories** : vente 14, achat 9, dette_client 9, dépense 8, capital 5,
  consultation 5, stock 3 (total 53). Pas de catégorie extrême-minoritaire
  au point d'être non significative, mais stock/consultation/capital restent
  petits (5 ou moins) — toute conclusion par catégorie sur ces trois-là
  repose sur peu de cas.
- **Locuteurs·rices** : **seulement 3** (L01 : 15 phrases, L02 : 18, L03 :
  20). C'est la limite la plus importante à garder en tête : tout score sur
  ce corpus mesure la compréhension de **3 façons de parler**, pas une
  diversité réelle de locutrices. Les variantes "a/b/c" du même énoncé
  (ex. P02/P02b/P02c) sont featured mes mêmes propositions redites par les 3
  locutrices, pas 3 phrases indépendantes — un modèle qui échoue sur une
  variante échoue structurellement sur les 2 autres, ce qui gonfle
  artificiellement le poids de certains échecs/succès dans les pourcentages
  globaux.
- **Confiance de transcription** : "haute - vérifié à l'oreille" sur les 53
  lignes — bonne nouvelle, aucune transcription douteuse dans ce corpus.
- **Montant annoté** : présent sur 45/53 phrases (les 8 restantes sont
  consultation/stock, non-monétaires par nature).

## 3. Annotation : désaccords déjà identifiés, à ne pas re-confondre avec des erreurs de mesure

Deux sources de désaccords structurels existent **indépendamment** de tout
modèle testé, documentées avant même ce protocole :

- `ECHECS_CONNUS_INTENTION` (`tests/test_moteur_decision.py`) : 8 phrases où
  le moteur à règles du projet (en production) n'est pas d'accord avec
  l'étiquette du corpus — construit pour une raison indépendante de ces
  tests LLM, il y a plusieurs semaines.
- Flou achat/dépense dans l'annotation de référence elle-même (2 phrases,
  achat d'emballages annoté "depense") — documenté dans
  `DESACCORDS_LLM_A_VALIDER.md` au protocole 2.

Ces 10 cas ont été exclus du "score ajusté" d'intention (66 %→85 % pour
`mistral:7b`). **Ce n'est pas un enjolivement a posteriori** : la liste
`ECHECS_CONNUS_INTENTION` existait avant ce protocole, et le flou
achat/dépense avant le protocole 7. Aucun des deux n'a été inventé pour
excuser les résultats de `mistral:7b` après coup.

**Ce qui reste un vrai signal d'erreur, pas une excuse d'annotation** : les
8 désaccords "vraiment nouveaux" du protocole 7 (motifs A/B/C dans
`DESACCORDS_LLM_A_VALIDER.md`), non encore tranchés par une locutrice
native. Tant qu'ils ne sont pas validés, le score ajusté (85 %) doit être lu
comme "au moins 85 %, au plus 100 %" — pas comme un chiffre définitif.

## 4. Risques de surajustement identifiés (et déjà corrigés ou à surveiller)

- **Corrigé** : la règle de repli initiale du protocole 7 ("un seul groupe
  numérique + intention ≠ stock ⇒ montant") collait exactement aux 4 échecs
  du corpus actuel et aurait mal généralisé (ex. "j'ai vendu trois sacs de
  riz" sans prix annoncé). Remplacée par un signalement d'ambiguïté — voir
  commit `3002580`.
- **À surveiller** : le prompt système d'`evaluer_segmente.py` et
  d'`evaluer_intention_seule.py` a été affiné sur ce même corpus de 53
  phrases (via plusieurs itérations, protocoles 5-7). Tout score mesuré
  avec ces prompts sur ce corpus **ne prouve pas** qu'ils généraliseront à
  des phrases inédites — c'est exactement pourquoi la mission demande un
  protocole 8 sur un corpus **indépendant**, non utilisé pour ajuster les
  prompts.
- **Non testé à ce jour** : les cas à plusieurs groupes numériques
  concurrents dans une même phrase (prix unitaire + quantité + total) —
  absents du corpus actuel, donc ni la segmentation ni l'attribution de
  rôle n'ont jamais été mises à l'épreuve sur ce type de phrase.

## 5. Montant correct ≠ transaction comprise — où en est-on précisément

| Dimension mesurée | Résultat (meilleur modèle, `mistral:7b`) | Fiabilité |
|---|---|---|
| Montant FCFA exact (architecture segmentée) | 91 % (41/45), 4 signalées ambiguës plutôt que devinées | Haute, sur ce corpus |
| Intention (catégorie comptable) | 66 % brut / 85 % ajusté (sous réserve des 8 désaccords non tranchés) | Moyenne — point faible identifié : gestion des questions (joli/jɔn) |
| Opération précise (ex. nouvelle dette vs remboursement) | **Non mesuré à ce jour** | Le schéma actuel (7 catégories plates) ne distingue pas création/remboursement/consultation d'un même domaine — c'est exactement le problème relevé en mission (le "troisième niveau" : diminuer_creance vs juste reconnaître "juru") |
| Transaction entièrement correcte (intention + montant + rôles + personne/produit) | **Non mesuré à ce jour** | Aucun protocole précédent n'a combiné ces mesures en un seul taux |

**Conclusion de l'audit** : les scores annoncés sont fiables et
reproductibles pour ce qu'ils mesurent, mais ce qu'ils mesurent est
plus étroit que "N'GONI NANA comprend les opérations comptables" — exactement
le point soulevé dans la mission. Le protocole 8 doit introduire les
métriques manquantes (opération précise, transaction complète) avant toute
nouvelle annonce de succès.
