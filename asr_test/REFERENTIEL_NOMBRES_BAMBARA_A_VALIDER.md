# Référentiel des nombres bambara — à faire valider par un·e locuteur·rice natif·ve

## Origine et statut

Extrait de `Nombres_1_a_1000000_Bambara_et_Argent_CORRIGE.xlsx` (Téléchargements,
2026-10-20), un tableau généré automatiquement selon une règle grammaticale
régulière (pas vérifié individuellement). Son propre onglet "Guide et sources"
le dit explicitement : *"les grands nombres composés sont générés selon une
règle régulière : une validation par locuteur natif est conseillée"*.

**Aucune ligne ci-dessous n'est confirmée.** Ce fichier ne doit **pas** servir
d'oracle pour le moteur numérique, le LLM ou les tests tant que le statut n'est
pas passé à "Validée". Conformément à la remarque reçue : le risque est que le
tableur, le moteur et les tests se valident mutuellement sur une même erreur
sans qu'aucun humain ne l'ait jamais vérifiée.

Statuts possibles : **Validée** (confirmée par un·e locuteur·rice compétent·e) ·
**À vérifier** (générée automatiquement, en attente) · **Variante** (autre
formulation acceptée) · **Rejetée** (incorrecte ou inadaptée au contexte).

## La question centrale à trancher

Ce n'est **pas** la conversion ×5 dɔrɔmɛ→F CFA (déjà testée et stable à
100 %/96 % dans les protocoles 1-2). C'est la **portée de "waa"** sur le
groupe qui le suit :

> *"waa mugan ni duuru"* — est-ce que "waa" porte sur tout le groupe
> "mugan ni duuru" (= waa × (20+5) = 25 000), ou seulement sur "mugan"
> (= waa × 20, puis + 5 séparément = 20 005) ?

Le tableur choisit systématiquement la première lecture. C'est aussi
l'interprétation que notre corpus utilise (P20/P20b/P20c : 125 000 F CFA
attendu). Mais ni le tableur ni notre propre annotation de corpus n'est une
confirmation indépendante — les deux pourraient reproduire la même erreur.

## Cas structurants à valider (extraits du tableur)

| Nombre | Transcription bambara (tableur) | Lecture dɔrɔmɛ (tableur) | Statut | Question pour le·la locuteur·rice |
|---|---|---|---|---|
| 15 | tan ni duuru | dɔrɔmɛ saba | À vérifier | — |
| 20 | mugan | dɔrɔmɛ naani | À vérifier | — |
| 25 | mugan ni duuru | dɔrɔmɛ duuru | À vérifier | — |
| 50 | bi duuru | dɔrɔmɛ tan | À vérifier | — |
| 100 | kɛmɛ | dɔrɔmɛ mugan | À vérifier | — |
| 101 | kɛmɛ ani kelen | dɔrɔmɛ mugan + 1 F CFA (reste) | À vérifier | "ani" relie bien centaine et reste, pas une addition de même niveau ? |
| 150 | kɛmɛ ani bi duuru | dɔrɔmɛ bi saba | À vérifier | — |
| 250 | kɛmɛ fila ani bi duuru | dɔrɔmɛ bi duuru | À vérifier | — |
| 500 | kɛmɛ duuru | dɔrɔmɛ kɛmɛ | À vérifier | — |
| 999 | kɛmɛ kɔnɔntɔn ani bi kɔnɔntɔn ni kɔnɔntɔn | dɔrɔmɛ kɛmɛ ani bi kɔnɔntɔn ni kɔnɔntɔn + 4 F CFA (reste) | À vérifier | Cas limite — une locutrice dirait-elle vraiment ça, ou une forme plus courte ? |
| 1000 | waa kelen | dɔrɔmɛ kɛmɛ fila | À vérifier | — |
| 1001 | waa kelen ani kelen | dɔrɔmɛ kɛmɛ fila + 1 F CFA (reste) | À vérifier | — |
| 1500 | waa kelen ani kɛmɛ duuru | dɔrɔmɛ kɛmɛ saba | À vérifier | — |
| 2500 | waa fila ani kɛmɛ duuru | dɔrɔmɛ kɛmɛ duuru | À vérifier | — |
| 10000 | waa tan | dɔrɔmɛ waa fila | À vérifier | — |
| 12500 | waa tan ni fila ani kɛmɛ duuru | dɔrɔmɛ waa fila ani kɛmɛ duuru | À vérifier | Mélange "ni" (tan ni fila = 12) et "ani" (+ kɛmɛ duuru = +500) dans la même expression — à confirmer que c'est naturel. |
| **25000** | **waa mugan ni duuru** | **dɔrɔmɛ waa duuru** | **À vérifier — cas central** | **"waa" porte-t-il sur "mugan ni duuru" (25) en bloc, ou seulement sur "mugan" (20) ?** Correspond exactement à notre phrase corpus P20 ("n ye saga saba feere waa mugan ni duuru", annotée 125 000 F CFA = 25 000 dɔrɔmɛ). |
| 50000 | waa bi duuru | dɔrɔmɛ waa tan | À vérifier | — |
| 100000 | waa kɛmɛ | dɔrɔmɛ waa mugan | À vérifier | — |
| 125000 | waa kɛmɛ ani mugan ni duuru | dɔrɔmɛ waa mugan ni duuru | À vérifier | Combine le cas 100 000 (waa kɛmɛ) et le cas central 25 000 (mugan ni duuru) via "ani" — à vérifier que le même principe de portée s'applique au "ani" central lui-même. |
| 250000 | waa kɛmɛ fila ani bi duuru | dɔrɔmɛ waa bi duuru | À vérifier | — |
| 500000 | waa kɛmɛ duuru | dɔrɔmɛ waa kɛmɛ | À vérifier | — |
| 1000000 | milyɔn kelen | dɔrɔmɛ waa kɛmɛ fila | À vérifier | — |

## Ce qui reste à faire (dépend de la validation ci-dessus)

1. Faire confirmer/corriger chaque ligne par Fadima ou une autre personne
   bambaraphone de l'équipe — en particulier le cas central (25 000) qui
   conditionne l'interprétation de 2 phrases réelles du corpus (P20, P20b,
   P20c) et l'erreur d'arithmétique documentée du LLM
   (`DESACCORDS_LLM_A_VALIDER.md`).
2. Une fois validé : mettre à jour `asr_test/scripts/montants.py` (l'analyseur
   déterministe du moteur actuel) pour qu'il applique la même règle de
   portée, avec des tests de régression sur ces cas précis.
3. Reformuler le prompt few-shot des protocoles LLM avec la règle confirmée
   (pas la règle supposée du tableur) et refaire le protocole 5.
4. Ne jamais traiter une ligne "À vérifier" comme une vérité pour calculer un
   vrai montant dans l'application — seulement comme hypothèse de travail
   pour construire des tests.
