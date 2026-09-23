# Rapport de test ASR bambara — FarmRadioInternational/bambara-whisper-asr

## Synthèse

| Groupe | Phrases | WER | CER | Montants exacts |
|---|---|---|---|---|
| **Total** | 2 | 60 % | 33 % | 0/2 (0 %) |

Latence : moyenne 21.6 s, max 22.4 s (objectif < 5 s : au-dessus de l'objectif).

WER/CER = taux d'erreur par mot / par caractère (plus bas = mieux). Montant exact = le nombre prononcé est retrouvé dans la transcription.

## Détail par phrase

| id | Référence | Transcription | WER | Nombre attendu | Nombres trouvés | Montant |
|---|---|---|---|---|---|---|
| P01 | Mariam ka jɛnɛ ye 2500 francs | madamu ka jɛnɛ ye fansi | 50 % | 2500 | aucun | ❌ |
| P02 | Saga dourou fereli be bin wa bi dourou ma, i son na wah | sana duuru fɛli bɛ biwa bi duuru ma i sona | 69 % | 50000 | 5, 50 | ❌ |

## Montants mal reconnus

- **P01** : attendu 2500, trouvé aucun nombre — « madamu ka jɛnɛ ye fansi »
- **P02** : attendu 50000, trouvé 5, 50 — « sana duuru fɛli bɛ biwa bi duuru ma i sona »
