# Évaluation de RobotsMali/soloni-ic-slot-fintech-v0 sur notre corpus réel

Contexte : suite à `Communications/instructions.docx` (proposition d'architecture
hybride ASR + compréhension + moteur comptable déterministe), qui recommandait
de tester ce modèle de compréhension directe voix -> intention + entités (SLU)
avant toute décision. Ce document rend compte du test, pas d'une supposition.

## Ce qu'est réellement ce modèle

Un modèle NeMo `SLUIntentSlotBPEModel`, entraîné sur un jeu fermé de 6 actions
de banque mobile : `transfer_to_account`, `transfer_to_momo`, `get_balance`,
`Maps_to` (navigation), `logout`, `search_faq`. Aucune de ces actions ne
correspond à notre domaine (vente, dépense, stock, client, capital GERME).

## Méthode

Script : `asr_test/scripts/tester_slu_fintech.py`. Modèle chargé dans un venv
isolé (`.venv_slu_eval/`, nemo-toolkit==2.5.0, incompatible avec la version
utilisée pour l'ASR de production). Exécuté sur les 60 enregistrements réels
vérifiés de `asr_test/corpus/phrases_reelles.csv`, sortie brute conservée dans
`asr_test/results/slu_fintech_vs_corpus_reel.json`.

## Résultats

| Mesure | Résultat |
|---|---|
| Montants extraits (entité "amount") | **0 / 60** |
| Entités utiles extraites (hors "page" de navigation) | **0 / 60** |
| Action correspondant au vrai sens de la phrase | Aucune catégorie ne correspond (voir ci-dessous) |

Actions produites par catégorie réelle (sur 60 phrases, aucune ne demande
d'argent ni de solde bancaire) :

| Catégorie réelle | Actions produites par le modèle |
|---|---|
| vente | transfer_to_account (15), get_balance (2), Maps_to (1) |
| achat | transfer_to_account (9) |
| depense | transfer_to_account (4), Maps_to (4), get_balance (1) |
| dette_client | get_balance (6), transfer_to_momo (2), transfer_to_account (1) |
| capital | Maps_to (2), transfer_to_account (2), transfer_to_momo (1), get_balance (1) |
| consultation | get_balance (3), Maps_to (3) |
| stock | Maps_to (3) |

Aucune corrélation utilisable : une phrase donnée est associée tantôt à une
action, tantôt à une autre, selon l'enregistrement et la locutrice, pas selon
le sens réel de la phrase.

## Interprétation

Le modèle ne "comprend" pas nos phrases : il les classe, de façon confiante,
dans la catégorie de banque mobile qui leur ressemble acoustiquement le plus
(ex. toutes les phrases d'achat sont lues comme des virements). C'est
exactement le risque que le document d'instructions avait lui-même signalé
("il peut mal comprendre... ou inventer des valeurs") et que ses propres
scores (91,67 % intentions / 75,86 % entités) ne garantissaient pas en dehors
de son propre domaine d'entraînement.

Ce n'est pas un défaut du modèle : il fait exactement ce pour quoi il a été
entraîné (banque mobile), simplement pas ce dont nous avons besoin
(comptabilité GERME). L'utiliser tel quel reviendrait à remplacer un moteur à
règles fiable par un générateur de réponses aléatoires.

## Conclusion

Ce modèle, utilisé directement, n'est **pas** une alternative viable au
moteur actuel pour N'GONI NANA. Deux voies restent ouvertes si l'on veut
explorer la piste "compréhension par un modèle" plutôt que des règles :

1. **Fine-tuning** de ce même modèle (ou d'un autre) sur un corpus annoté
   GERME (vente/dépense/stock/client/capital) — l'option "Niveau 3" du
   document d'instructions. Nécessite de construire ce corpus annoté
   d'abord (pas encore fait).
2. **Option B du document** (ASR + LLM généraliste, prompté en few-shot avec
   nos propres exemples bambara) — déjà en partie écartée par le test
   antérieur des 42 modèles du sandbox CFA (aucun ne comprend le bambara de
   façon fiable), mais jamais testée spécifiquement avec le texte réel issu
   de notre propre ASR (soloni-be-kalan-v0) plutôt qu'en lecture directe.

Le moteur à règles actuel reste, à ce jour, la seule option dont la fiabilité
sur nos 60 phrases réelles est mesurée et documentée (87 % de précision
d'intention, voir `tests/test_moteur_decision.py`).
