# Rapport de test ASR bambara — FarmRadioInternational/bambara-whisper-asr

## Synthèse

| Groupe | Phrases | WER | CER | Montants exacts |
|---|---|---|---|---|
| **Total** | 60 | 54 % | 24 % | 24/51 (47 %) |
| Locuteur : L01 | 20 | 54 % | 25 % | 10/17 (59 %) |
| Locuteur : L02 | 20 | 49 % | 21 % | 11/17 (65 %) |
| Locuteur : L03 | 20 | 60 % | 25 % | 3/17 (18 %) |

Latence : moyenne 25.2 s, max 37.4 s (objectif < 5 s : au-dessus de l'objectif).

WER/CER = taux d'erreur par mot / par caractère (plus bas = mieux). Montant exact = le nombre prononcé est retrouvé dans la transcription.

## Détail par phrase

| id | Référence | Transcription | WER | Nombre attendu | Nombres trouvés | Montant |
|---|---|---|---|---|---|---|
| P01 | n kɛmɛ duuru bɛ Mariam na | ne ka kɛmɛ duuru bɛ mariyamu na | 50 % | 500 | 500 | ✅ |
| P02 | n ye saga saba feere wa bi duuru | n ye saka saba fere ye wabiduru | 62 % | 50000 | 3, 50000 | ✅ |
| P03 | n ye tiga bɔrɛ fila feere wa [?] | n i ye siga bɔrɛ fila fere ye wasaba | 71 % | 3000 | 2, 3000 | ✅ |
| P04 | n ye safunɛ feere kɛmɛ | ne ye safunɛ fere kɛmɛ ye | 60 % | 500 | 100 | ❌ |
| P05 | n ye [gaban] tan feere [?] | n ye gan sara tan fɛ de kɛmɛ duuru | 120 % | 500 | 10, 500 | ✅ |
| P06 | n ye fini kelen feere wa kelen ni kɛmɛ duuru | ne ye fini tafɛ kelen fɛɛrɛ ye wa kelen ni kɛmɛ duuru | 30 % | 1500 | 1, 1500 | ✅ |
| P07 | n ye bɔrɛ kelen san wa duuru | n ye saɲɔbɔrɛ kelen sa u ka duuru | 57 % | 5000 | 1, 5 | ❌ |
| P08 | n ye si tulu san kɛmɛ fila ni bi duuru | ne ye situlu san kɛmɛ fila ni biduuru | 50 % | 250 | 200, 50 | ❌ |
| P09 | n ye sɛ duuru san waa fila ni kɛmɛ duuru | ne ye cɛ den duuru san wafila ani kɛmɛ duuru | 60 % | 2500 | 5, 2000, 500 | ❌ |
| P10 | n ye n ka paser sara kɛmɛ ni bi duuru | n ye n ka pase sara kɛmɛ ni biduuru | 30 % | 150 | 100, 50 | ❌ |
| P11 | n ye n ka sugu sigiyɔrɔ sara dɔrɔmɛ mugan | ne ye n ka sugu sigiyɔrɔ sara dɔrɔmɛ mugan | 11 % | 20 | 20 | ✅ |
| P12 | n ye waa kelen kɛ ka mana foroko san | ne ye wa kelen kɛ ka mana foroko san | 22 % | 1000 | 1000 | ✅ |
| P13 | n ka waa fila juru bɛ Awa la | ne ka wafila juru bɛ awa la | 38 % | 2000 | 2000 | ✅ |
| P14 | n ka kɛmɛ wolonwula jurumu bɛ Fanta la, a y'o sara | n i ka kɛmɛ wolonwula juru minnu bɛ fɛn ta la a ye o sara | 50 % | 700 | 700 | ✅ |
| P15 | n ka jagokun ye waa tan ye | e tɔgɔ ni jamu ne tɔgɔ ye adama kamara | 114 % | 10000 | aucun | ❌ |
| P16 | n ye wa naani fara n ka jagokun kan | n ye wa nani fara n ka jago kun kan | 33 % | 4000 | 4000 | ✅ |
| P17 | n ye joli feere nin kalo in na | ne ye joli de fɛ de ni kalo in na | 62 % | — | aucun | — |
| P18 | n ka juru bɛ mɔgɔ jɔn na | n i ka juru bɛ mɔgɔ jɔnw na | 29 % | — | aucun | — |
| P19 | sanɲɔgɔn bɔrɔ naani de bɛ ne bolo | saɲɔ bɔrɔ nani de bɛ ne bolo a tɔ la | 71 % | — | 4 | — |
| P20 | n ye saga saba feere wa mugan ni duuru | n ye saka saba fere ye u ka mugan ni duuru | 56 % | 25000 | 3, 25 | ❌ |
| P01b | n ka kɛmɛ duuru bɛ Mariam min na | ne ka kɛmɛ duru be mariyamu na | 50 % | 500 | 500 | ✅ |
| P02b | n ye saga saba feere waa bi duuru | ne ye saka saba fere wa bi duuru | 50 % | 50000 | 3, 50000 | ✅ |
| P03b | n ye tiga bɔrɛ fila feere waa saba | ne ye tiga bɔrɛ fila ne y o fɛ wasaba | 75 % | 3000 | 2, 3000 | ✅ |
| P04b | n ye safunɛ feere [?] | ne ye sɛtɛnɛ fɛ ye | 100 % | 500 | aucun | ❌ |
| P05b | n ye [gaban] feere kɛmɛ duuru | ne ye gan safere kɛmɛ duuru | 50 % | 500 | 500 | ✅ |
| P06b | n ye fini feere wa kelen ni kɛmɛ duuru | ne ye fini feere a kelen ni kɛmɛ duuru | 22 % | 1500 | 501 | ❌ |
| P07b | n ye bɔrɛ san waa duuru | ne ye saɲɔ bɔrɛ ke fere wa duuru | 83 % | 5000 | 5000 | ✅ |
| P08b | n ye si tulu feere kɛmɛ fila bi duuru | n i ye situlu fere kɛmɛ fila nin b i duuru | 78 % | 250 | 200, 5 | ❌ |
| P09b | n ye sɛfuru feere waa fila ni kɛmɛ duuru | n ye cɛ duuru fere wafila ni kɛmɛ duuru | 44 % | 2500 | 5, 2500 | ✅ |
| P10b | n ye pase sara kɛmɛ ni bi duuru | n ye pase sara kɛmɛ ni bi duuru | 0 % | 150 | 150 | ✅ |
| P11b | n ye n ka sugu sigiyɔrɔ sara mugan | ɲɛ ka sugu sigiyɔrɔ sara mugan | 38 % | 20 | 20 | ✅ |
| P12b | [?] mana foroko ni bɔrɛw san | n i mana furoko ni bɔrɛw sa | 80 % | 1000 | aucun | ❌ |
| P13b | n ka wa fila juru bɛ Awa la | ne ka wafila juru be awa la | 38 % | 2000 | 2000 | ✅ |
| P14b | Fanta ye kɛmɛ wolonwula sara, n ka juru la | faanta ye kɛmɛ wolonwula sɔrɔ ne ka juru la | 33 % | 700 | 700 | ✅ |
| P15b | n ka jagokun bɛɛ ye waa tan | e tɔgɔ ni jamu ne tɔgɔ ye adama kamara | 114 % | 10000 | aucun | ❌ |
| P16b | n ye wa naani fara n ka jagokun kan | n ye wananni fara n ka jagokun kan | 22 % | 4000 | aucun | ❌ |
| P17b | n yɛrɛ ka minɛn tɔ tora joli nin kalo in na | ne yɛrɛ ka minɛn tɔ tora joli ni kalo in na | 18 % | — | aucun | — |
| P18b | mɔgɔ jɔn ni jɔn de ka n ka juru b'olu la | mɔgɔ jɔn ni jɔn de ka ne ka juru bɛ olu la | 17 % | — | aucun | — |
| P19b | ɲɔ bɔrɛ naani de tora an bolo | ɛɛ ɲɔ bɔra nani de tora an bolo | 43 % | — | 4 | — |
| P20b | n ye saga saba feere waa mugan ni duuru | n ye saga saba fere wa mugan ni duuru | 22 % | 25000 | 3, 25000 | ✅ |
| P01c | n ka kɛmɛ duuru bɛ Mariama fɛ | ne ka kɛmɛ duru bɛ mariyamu fɛ | 43 % | 500 | 500 | ✅ |
| P02c | saga saba feerelen bɛ na waa bi duuru ma, i sɔnna | sakasaba ferele bɛnna wa bi jɛrɛ i ma i sɔnna | 73 % | 50000 | aucun | ❌ |
| P03c | n ye tiga bɔrɔ feere wa[a saba] | ne ye tika bɔrɛ fila ferewasaba | 88 % | 3000 | 2 | ❌ |
| P04c | n ye safunɛ san [?] | ne ye safunɛ sa | 50 % | 500 | aucun | ❌ |
| P05c | n ye [gaban] sara tan, kɛmɛ duuru | ne ye gan sarata fɛ kɛmɛ duuru | 57 % | 500 | 500 | ✅ |
| P06c | n ye fini san waa kelen ni kɛmɛ duuru | ne ye finisan wakelen kɛmɛ duuru | 67 % | 1500 | 1000, 500 | ❌ |
| P07c | n ye ɲɔ bɔrɛ kelen san waa duuru | ne ye ɲɔbɔrɛ kelen sa wajuru | 75 % | 5000 | 1 | ❌ |
| P08c | n ye si tulu san kɛmɛ fila ni bi duuru la | ne ye situlu ye san ne ye situlu kɛmɛ fila ni biduobila san | 82 % | 250 | 200 | ❌ |
| P09c | n ye sɛ san waa fila ni kɛmɛ duuru | ne ye cɛsisan cɛwisan o b a fila ni kɛmɛjuru | 89 % | 2500 | 2 | ❌ |
| P10c | n ye pase sara kɛmɛ ni bi duuru | ne ye pase sara kɛmɛ ni biduuru | 38 % | 150 | 100, 50 | ❌ |
| P11c | n ye n sigiyɔrɔ sara dɔrɔmɛ mugan | ne ye n sigiyɔrɔ sara dɔrɔmɛ mɔgɔ ye | 43 % | 20 | aucun | ❌ |
| P12c | n ye waa kelen don bɔrɛw la | ne ye u ka hakilina do bɔrɛw la | 71 % | 1000 | aucun | ❌ |
| P13c | n ka waa fila de bɛ Awa la | ne ka bɔ a fila de bɛ aw la | 50 % | 2000 | 2 | ❌ |
| P14c | Fanta ye n ka kɛmɛ wolonwula sara | faanta in ye ne ka kɛ makɔlɔn fila in sara | 100 % | 700 | 2 | ❌ |
| P15c | n ka jagokun tun ye waa tan ye | ne ka jagokun tun ye waata ye | 38 % | 10000 | aucun | ❌ |
| P16c | n ye wa naani fara'o kan | ne ye wanan fariw kan | 71 % | 4000 | aucun | ❌ |
| P17c | n ye joli feere nin kalo in na | ne ye joli fɛrɛ ye nin kalo in na | 38 % | — | aucun | — |
| P18c | n ka wari bɛ jɔn na | ne ka wari bɛ jɔn na | 17 % | — | aucun | — |
| P19c | n ka ɲɔ tun ye bɔrɔ naani ye | ne ka ɲɔgɔn ye bɔrɛlali ye | 62 % | — | aucun | — |
| P20c | n ye saga saba feere wa mugan ni duuru | ne ye saka saba fere ye wa mugan ni duuru | 44 % | 25000 | 3, 25000 | ✅ |

## Montants mal reconnus

- **P04** : attendu 500, trouvé 100 — « ne ye safunɛ fere kɛmɛ ye »
- **P07** : attendu 5000, trouvé 1, 5 — « n ye saɲɔbɔrɛ kelen sa u ka duuru »
- **P08** : attendu 250, trouvé 200, 50 — « ne ye situlu san kɛmɛ fila ni biduuru »
- **P09** : attendu 2500, trouvé 5, 2000, 500 — « ne ye cɛ den duuru san wafila ani kɛmɛ duuru »
- **P10** : attendu 150, trouvé 100, 50 — « n ye n ka pase sara kɛmɛ ni biduuru »
- **P15** : attendu 10000, trouvé aucun nombre — « e tɔgɔ ni jamu ne tɔgɔ ye adama kamara »
- **P20** : attendu 25000, trouvé 3, 25 — « n ye saka saba fere ye u ka mugan ni duuru »
- **P04b** : attendu 500, trouvé aucun nombre — « ne ye sɛtɛnɛ fɛ ye »
- **P06b** : attendu 1500, trouvé 501 — « ne ye fini feere a kelen ni kɛmɛ duuru »
- **P08b** : attendu 250, trouvé 200, 5 — « n i ye situlu fere kɛmɛ fila nin b i duuru »
- **P12b** : attendu 1000, trouvé aucun nombre — « n i mana furoko ni bɔrɛw sa »
- **P15b** : attendu 10000, trouvé aucun nombre — « e tɔgɔ ni jamu ne tɔgɔ ye adama kamara »
- **P16b** : attendu 4000, trouvé aucun nombre — « n ye wananni fara n ka jagokun kan »
- **P02c** : attendu 50000, trouvé aucun nombre — « sakasaba ferele bɛnna wa bi jɛrɛ i ma i sɔnna »
- **P03c** : attendu 3000, trouvé 2 — « ne ye tika bɔrɛ fila ferewasaba »
- **P04c** : attendu 500, trouvé aucun nombre — « ne ye safunɛ sa »
- **P06c** : attendu 1500, trouvé 1000, 500 — « ne ye finisan wakelen kɛmɛ duuru »
- **P07c** : attendu 5000, trouvé 1 — « ne ye ɲɔbɔrɛ kelen sa wajuru »
- **P08c** : attendu 250, trouvé 200 — « ne ye situlu ye san ne ye situlu kɛmɛ fila ni biduobila san »
- **P09c** : attendu 2500, trouvé 2 — « ne ye cɛsisan cɛwisan o b a fila ni kɛmɛjuru »
- **P10c** : attendu 150, trouvé 100, 50 — « ne ye pase sara kɛmɛ ni biduuru »
- **P11c** : attendu 20, trouvé aucun nombre — « ne ye n sigiyɔrɔ sara dɔrɔmɛ mɔgɔ ye »
- **P12c** : attendu 1000, trouvé aucun nombre — « ne ye u ka hakilina do bɔrɛw la »
- **P13c** : attendu 2000, trouvé 2 — « ne ka bɔ a fila de bɛ aw la »
- **P14c** : attendu 700, trouvé 2 — « faanta in ye ne ka kɛ makɔlɔn fila in sara »
- **P15c** : attendu 10000, trouvé aucun nombre — « ne ka jagokun tun ye waata ye »
- **P16c** : attendu 4000, trouvé aucun nombre — « ne ye wanan fariw kan »
