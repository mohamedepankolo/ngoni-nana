# Rapport de test ASR bambara — RobotsMali/soloni-114m-tdt-ctc-v3

⚠️ **Résultat biaisé, non comparable à `reelles_farmradio_rapport.md`.** La
colonne `texte_bambara` de `phrases_reelles.csv` a été rédigée en brouillon
en s'aidant de la propre sortie de ce modèle (pour associer chaque segment
audio à son id de phrase) — l'évaluer avec cette référence revient en
partie à le comparer à lui-même. Conservé ici à titre de trace, pas comme
mesure de performance. Le score honnête pour ce corpus attend une
correction humaine de `texte_bambara` (voir `confiance_brouillon`).

## Synthèse

| Groupe | Phrases | WER | CER | Montants exacts |
|---|---|---|---|---|
| **Total** | 60 | 29 % | 14 % | 35/51 (69 %) |
| Locuteur : L01 | 20 | 24 % | 12 % | 12/17 (71 %) |
| Locuteur : L02 | 20 | 38 % | 20 % | 10/17 (59 %) |
| Locuteur : L03 | 20 | 26 % | 11 % | 13/17 (76 %) |

Latence : moyenne 0.3 s, max 0.5 s (objectif < 5 s : OK).

WER/CER = taux d'erreur par mot / par caractère (plus bas = mieux). Montant exact = le nombre prononcé est retrouvé dans la transcription.

## Détail par phrase

| id | Référence | Transcription | WER | Nombre attendu | Nombres trouvés | Montant |
|---|---|---|---|---|---|---|
| P01 | n kɛmɛ duuru bɛ Mariam na | nɛkɛmɛ duuru bɛ marriage na | 50 % | 500 | 5 | ❌ |
| P02 | n ye saga saba feere wa bi duuru | n ye saga saba feere wa bi duuru | 0 % | 50000 | 3, 50000 | ✅ |
| P03 | n ye tiga bɔrɛ fila feere wa [?] | n ye tika bɔrɛ fere wa | 43 % | 3000 | aucun | ❌ |
| P04 | n ye safunɛ feere kɛmɛ | ne ye safunɛ feere kɛmɛ | 20 % | 500 | 100 | ❌ |
| P05 | n ye [gaban] tan feere [?] | n ye gansara tan | 40 % | 500 | 10 | ❌ |
| P06 | n ye fini kelen feere wa kelen ni kɛmɛ duuru | ne ye fini tafe kelen feere wa kelen ni kɛmɛ duuru | 20 % | 1500 | 1, 1500 | ✅ |
| P07 | n ye bɔrɛ kelen san wa duuru | n ye san ka bɔrɛ kelen san wa duuru | 29 % | 5000 | 1, 5000 | ✅ |
| P08 | n ye si tulu san kɛmɛ fila ni bi duuru | ne ye situlu san kɛmɛ fila ni bi duuru | 30 % | 250 | 250 | ✅ |
| P09 | n ye sɛ duuru san waa fila ni kɛmɛ duuru | ne ye sɛden duuru san waa fila ni kɛmɛ duuru | 20 % | 2500 | 5, 2500 | ✅ |
| P10 | n ye n ka paser sara kɛmɛ ni bi duuru | n ye n ka paser sa kɛmɛ ni bi duuru | 10 % | 150 | 150 | ✅ |
| P11 | n ye n ka sugu sigiyɔrɔ sara dɔrɔmɛ mugan | ne ye n ka so sigiyɔrɔ sara dɔrɔmɛ mugan | 22 % | 20 | 20 | ✅ |
| P12 | n ye waa kelen kɛ ka mana foroko san | ne ye waa kelen kɛ ka mana foroko san | 11 % | 1000 | 1000 | ✅ |
| P13 | n ka waa fila juru bɛ Awa la | ne ka waa fila juru bɛ aw la | 25 % | 2000 | 2000 | ✅ |
| P14 | n ka kɛmɛ wolonwula jurumu bɛ Fanta la, a y'o sara | nɛkɛmɛ wolonwula jurumu bi fa ta la a y'o sara | 50 % | 700 | 7 | ❌ |
| P15 | n ka jagokun ye waa tan ye | ne ka jagokun ye waa tan | 29 % | 10000 | 10000 | ✅ |
| P16 | n ye wa naani fara n ka jagokun kan | n ye wa naani fara n ka jagokun kan | 0 % | 4000 | 4000 | ✅ |
| P17 | n ye joli feere nin kalo in na | ne ye joli de feere nin kalo in na | 25 % | — | aucun | — |
| P18 | n ka juru bɛ mɔgɔ jɔn na | ne ka juru bɛ mɔgɔ jɔn na | 14 % | — | aucun | — |
| P19 | sanɲɔgɔn bɔrɔ naani de bɛ ne bolo | sanɲɔgɔn bɔrɔ naani de bɛ ne bolo a tɔ la | 43 % | — | 4 | — |
| P20 | n ye saga saba feere wa mugan ni duuru | n ye saga saba feere wa mugan ni duuru | 0 % | 25000 | 3, 25000 | ✅ |
| P01b | n ka kɛmɛ duuru bɛ Mariam min na | ne ka kɛmɛ duuru bɛ mariage na | 38 % | 500 | 500 | ✅ |
| P02b | n ye saga saba feere waa bi duuru | ne ye saga saba feere wa duuru | 38 % | 50000 | 3, 5000 | ❌ |
| P03b | n ye tiga bɔrɛ fila feere waa saba | ne ye bɔrɔ fila t'a bɔrɔ fila nan yo feere wasa | 125 % | 3000 | 2, 2 | ❌ |
| P04b | n ye safunɛ feere [?] | ne ye safunɛ fe yen | 75 % | 500 | aucun | ❌ |
| P05b | n ye [gaban] feere kɛmɛ duuru | ne ye gansa fere | 83 % | 500 | aucun | ❌ |
| P06b | n ye fini feere wa kelen ni kɛmɛ duuru | ne ye fini fere a kelen ni kɛmɛ duuru | 33 % | 1500 | 501 | ❌ |
| P07b | n ye bɔrɛ san waa duuru | ne ye san bɔrɛ fere wa duuru | 67 % | 5000 | 5000 | ✅ |
| P08b | n ye si tulu feere kɛmɛ fila bi duuru | n'i ye situlu feere kɛmɛ fila ni bi duuru | 44 % | 250 | 250 | ✅ |
| P09b | n ye sɛfuru feere waa fila ni kɛmɛ duuru | n'i ye sɛ duuru feere wa duuru | 78 % | 2500 | 5, 5000 | ❌ |
| P10b | n ye pase sara kɛmɛ ni bi duuru | n ye passe sara kɛmɛ ni bi duuru | 12 % | 150 | 150 | ✅ |
| P11b | n ye n ka sugu sigiyɔrɔ sara mugan | n ye n ka sugu sigiyɔrɔ sara mugan | 0 % | 20 | 20 | ✅ |
| P12b | [?] mana foroko ni bɔrɛw san | ɲɛ mana foroko ni bɔrɛw san | 20 % | 1000 | aucun | ❌ |
| P13b | n ka wa fila juru bɛ Awa la | ne ka wa fila bɛ aw juru bɛ aw la | 50 % | 2000 | 2000 | ✅ |
| P14b | Fanta ye kɛmɛ wolonwula sara, n ka juru la | fanta ye kɛmɛ wolonwula sara ne ka juru la | 11 % | 700 | 700 | ✅ |
| P15b | n ka jagokun bɛɛ ye waa tan | ne ka jagokun bɛɛ ye waa tan | 14 % | 10000 | 10000 | ✅ |
| P16b | n ye wa naani fara n ka jagokun kan | n ye wa naani fara n ka jagokun kan | 0 % | 4000 | 4000 | ✅ |
| P17b | n yɛrɛ ka minɛn tɔ tora joli nin kalo in na | ne yɛrɛ ka minɛn tɔ tora joli nin kalo in na | 9 % | — | aucun | — |
| P18b | mɔgɔ jɔn ni jɔn de ka n ka juru b'olu la | mɔgɔ jɔn ni jɔn de ka ne ka juru b'olu la | 8 % | — | aucun | — |
| P19b | ɲɔ bɔrɛ naani de tora an bolo | ɛɛ ɲɔ bɔrɛ naani de tora an bolo | 14 % | — | 4 | — |
| P20b | n ye saga saba feere waa mugan ni duuru | n'i ye saga fere wa mugan ni duuru | 44 % | 25000 | 25000 | ✅ |
| P01c | n ka kɛmɛ duuru bɛ Mariama fɛ | ne ka kɛmɛ duuru bɛ mariama fɛ | 14 % | 500 | 500 | ✅ |
| P02c | saga saba feerelen bɛ na waa bi duuru ma, i sɔnna | saga saba feere bɛ na wa abizulu ma i sɔnna | 36 % | 50000 | 3 | ❌ |
| P03c | n ye tiga bɔrɔ feere wa[a saba] | ne ye tika bɔrɔ feere wasa | 62 % | 3000 | aucun | ❌ |
| P04c | n ye safunɛ san [?] | ne ye safunɛ san | 25 % | 500 | aucun | ❌ |
| P05c | n ye [gaban] sara tan, kɛmɛ duuru | ne ye gwa sara tan kɛmɛ duuru | 29 % | 500 | 10, 500 | ✅ |
| P06c | n ye fini san waa kelen ni kɛmɛ duuru | ne ye fini san waa kelen ni kɛmɛ duuru | 11 % | 1500 | 1500 | ✅ |
| P07c | n ye ɲɔ bɔrɛ kelen san waa duuru | ne ye ɲɔ bɔnɛ kelen san wa duuru | 38 % | 5000 | 1, 5000 | ✅ |
| P08c | n ye si tulu san kɛmɛ fila ni bi duuru la | ne ye si tulu san ne ye si tulu kɛmɛ fila ni bi duuru la san | 55 % | 250 | 250 | ✅ |
| P09c | n ye sɛ san waa fila ni kɛmɛ duuru | ne ye sɛ san waa fila ni kɛmɛ duuru | 11 % | 2500 | 2500 | ✅ |
| P10c | n ye pase sara kɛmɛ ni bi duuru | n'a ye passer sara kɛmɛ ni bi duuru | 25 % | 150 | 150 | ✅ |
| P11c | n ye n sigiyɔrɔ sara dɔrɔmɛ mugan | ne ye n sigiyɔrɔ sara damɛ mugan | 29 % | 20 | 20 | ✅ |
| P12c | n ye waa kelen don bɔrɛw la | ne ye waa kelen don bɔrɛw la | 14 % | 1000 | 1000 | ✅ |
| P13c | n ka waa fila de bɛ Awa la | ne ka waa fila de bɛ aw la | 25 % | 2000 | 2000 | ✅ |
| P14c | Fanta ye n ka kɛmɛ wolonwula sara | fanta ye ne ka kɛmɛ wolonwula sara | 14 % | 700 | 700 | ✅ |
| P15c | n ka jagokun tun ye waa tan ye | ne ka jagokun tun ye waa tan ye | 12 % | 10000 | 10000 | ✅ |
| P16c | n ye wa naani fara'o kan | ne ye waa tan fa o kan | 57 % | 4000 | 10000 | ❌ |
| P17c | n ye joli feere nin kalo in na | ne ye joli feere ni kalo in na | 25 % | — | aucun | — |
| P18c | n ka wari bɛ jɔn na | ne ka wari bɛ jɔn na | 17 % | — | aucun | — |
| P19c | n ka ɲɔ tun ye bɔrɔ naani ye | ne ka ɲɔ tun ye bɔrɔ naani ye | 12 % | — | 4 | — |
| P20c | n ye saga saba feere wa mugan ni duuru | ne ye saga saba feere wa mugan ni duuru | 11 % | 25000 | 3, 25000 | ✅ |

## Montants mal reconnus

- **P01** : attendu 500, trouvé 5 — « nɛkɛmɛ duuru bɛ marriage na »
- **P03** : attendu 3000, trouvé aucun nombre — « n ye tika bɔrɛ fere wa »
- **P04** : attendu 500, trouvé 100 — « ne ye safunɛ feere kɛmɛ »
- **P05** : attendu 500, trouvé 10 — « n ye gansara tan »
- **P14** : attendu 700, trouvé 7 — « nɛkɛmɛ wolonwula jurumu bi fa ta la a y'o sara »
- **P02b** : attendu 50000, trouvé 3, 5000 — « ne ye saga saba feere wa duuru »
- **P03b** : attendu 3000, trouvé 2, 2 — « ne ye bɔrɔ fila t'a bɔrɔ fila nan yo feere wasa »
- **P04b** : attendu 500, trouvé aucun nombre — « ne ye safunɛ fe yen »
- **P05b** : attendu 500, trouvé aucun nombre — « ne ye gansa fere »
- **P06b** : attendu 1500, trouvé 501 — « ne ye fini fere a kelen ni kɛmɛ duuru »
- **P09b** : attendu 2500, trouvé 5, 5000 — « n'i ye sɛ duuru feere wa duuru »
- **P12b** : attendu 1000, trouvé aucun nombre — « ɲɛ mana foroko ni bɔrɛw san »
- **P02c** : attendu 50000, trouvé 3 — « saga saba feere bɛ na wa abizulu ma i sɔnna »
- **P03c** : attendu 3000, trouvé aucun nombre — « ne ye tika bɔrɔ feere wasa »
- **P04c** : attendu 500, trouvé aucun nombre — « ne ye safunɛ san »
- **P16c** : attendu 4000, trouvé 10000 — « ne ye waa tan fa o kan »
