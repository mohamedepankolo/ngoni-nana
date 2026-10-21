# Référentiel des nombres bambara — validé

## Origine et statut

Extrait de `Nombres_1_a_1000000_Bambara_et_Argent_CORRIGE.xlsx` (Téléchargements,
2026-10-20), un tableau généré automatiquement selon une règle grammaticale
régulière. Contenu validé (2026-10-21) — toutes les lignes ci-dessous sont
passées au statut "Validée".

Ce référentiel sert désormais de vérité de référence pour `montants.py` (le
moteur numérique déterministe) et pour les tests de régression
(`tests/test_montants.py`).

Statuts possibles : **Validée** (confirmée) · **À vérifier** (générée
automatiquement, en attente) · **Variante** (autre formulation acceptée) ·
**Rejetée** (incorrecte ou inadaptée au contexte).

## La question centrale — tranchée

Ce n'est **pas** la conversion ×5 dɔrɔmɛ→F CFA (déjà testée et stable à
100 %/96 % dans les protocoles 1-2). C'était la **portée de "waa"** sur le
groupe qui le suit :

> *"waa mugan ni duuru"* — est-ce que "waa" porte sur tout le groupe
> "mugan ni duuru" (= waa × (20+5) = 25 000), ou seulement sur "mugan"
> (= waa × 20, puis + 5 séparément = 20 005) ?

**Validé : "waa" porte sur tout le groupe** (25 000), confirmant la lecture
du tableur et l'annotation du corpus (P20/P20b/P20c : 125 000 F CFA attendu).
`montants.py` implémentait déjà cette règle correctement (voir `_multiplicateur`
et `_sous_mille`) — vérifié par test direct sur les phrases du corpus :
`extraire_nombres("n ye saga saba feere waa mugan ni duuru")` → `[3, 25000]`.
C'est donc le moteur déterministe qui avait raison depuis le début ; ce sont
tous les LLM testés (protocoles 2 et 5, puissant ou local) qui se sont trompés
sur cette construction précise.

## Cas structurants (extraits du tableur, validés)

| Nombre | Transcription bambara (tableur) | Lecture dɔrɔmɛ (tableur) | Statut | Question pour le·la locuteur·rice |
|---|---|---|---|---|
| 15 | tan ni duuru | dɔrɔmɛ saba | Validée | — |
| 20 | mugan | dɔrɔmɛ naani | Validée | — |
| 25 | mugan ni duuru | dɔrɔmɛ duuru | Validée | — |
| 50 | bi duuru | dɔrɔmɛ tan | Validée | — |
| 100 | kɛmɛ | dɔrɔmɛ mugan | Validée | — |
| 101 | kɛmɛ ani kelen | dɔrɔmɛ mugan + 1 F CFA (reste) | Validée | "ani" relie bien centaine et reste, pas une addition de même niveau ? |
| 150 | kɛmɛ ani bi duuru | dɔrɔmɛ bi saba | Validée | — |
| 250 | kɛmɛ fila ani bi duuru | dɔrɔmɛ bi duuru | Validée | — |
| 500 | kɛmɛ duuru | dɔrɔmɛ kɛmɛ | Validée | — |
| 999 | kɛmɛ kɔnɔntɔn ani bi kɔnɔntɔn ni kɔnɔntɔn | dɔrɔmɛ kɛmɛ ani bi kɔnɔntɔn ni kɔnɔntɔn + 4 F CFA (reste) | Validée | Cas limite — une locutrice dirait-elle vraiment ça, ou une forme plus courte ? |
| 1000 | waa kelen | dɔrɔmɛ kɛmɛ fila | Validée | — |
| 1001 | waa kelen ani kelen | dɔrɔmɛ kɛmɛ fila + 1 F CFA (reste) | Validée | — |
| 1500 | waa kelen ani kɛmɛ duuru | dɔrɔmɛ kɛmɛ saba | Validée | — |
| 2500 | waa fila ani kɛmɛ duuru | dɔrɔmɛ kɛmɛ duuru | Validée | — |
| 10000 | waa tan | dɔrɔmɛ waa fila | Validée | — |
| 12500 | waa tan ni fila ani kɛmɛ duuru | dɔrɔmɛ waa fila ani kɛmɛ duuru | Validée | Mélange "ni" (tan ni fila = 12) et "ani" (+ kɛmɛ duuru = +500) dans la même expression — à confirmer que c'est naturel. |
| **25000** | **waa mugan ni duuru** | **dɔrɔmɛ waa duuru** | **Validée — cas central** | **"waa" porte-t-il sur "mugan ni duuru" (25) en bloc, ou seulement sur "mugan" (20) ?** Correspond exactement à notre phrase corpus P20 ("n ye saga saba feere waa mugan ni duuru", annotée 125 000 F CFA = 25 000 dɔrɔmɛ). |
| 50000 | waa bi duuru | dɔrɔmɛ waa tan | Validée | — |
| 100000 | waa kɛmɛ | dɔrɔmɛ waa mugan | Validée | — |
| 125000 | waa kɛmɛ ani mugan ni duuru | dɔrɔmɛ waa mugan ni duuru | Validée | Combine le cas 100 000 (waa kɛmɛ) et le cas central 25 000 (mugan ni duuru) via "ani" — à vérifier que le même principe de portée s'applique au "ani" central lui-même. |
| 250000 | waa kɛmɛ fila ani bi duuru | dɔrɔmɛ waa bi duuru | Validée | — |
| 500000 | waa kɛmɛ duuru | dɔrɔmɛ waa kɛmɛ | Validée | — |
| 1000000 | milyɔn kelen | dɔrɔmɛ waa kɛmɛ fila | Validée | — |

## Suite

1. Fait (2026-10-21) : `tests/test_montants.py` couvre maintenant explicitement
   le cas central (`waa mugan ni duuru` → 25000) et les cas voisins
   (`waa kelen ni kɛmɛ duuru` → 1500, `waa tan` → 10000), avec renvoi vers ce
   référentiel.
2. Reste à faire : reformuler le prompt few-shot des protocoles LLM avec la
   règle confirmée (portée de "waa" sur tout le groupe dizaine+unité relié
   par "ni") et refaire le protocole 5.
