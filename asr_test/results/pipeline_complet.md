# Pipeline complet (ASR réel + moteur de décision) : RobotsMali/soloni-114m-tdt-ctc-v3

Intention correcte, bout en bout (ASR réel, pas le texte de référence) : **47/60 (78 %)**

Montant exact, bout en bout : **36/51 (71 %)**

Latence ASR moyenne : 0.30 s

## Détail

| id | locuteur | transcription ASR | intention attendue | intention trouvée | montant attendu | montant trouvé |
|---|---|---|---|---|---|---|
| P01 | L01 | nɛkɛmɛ duuru bɛ marriage na | client | client ✅ | 2500 | 2500 ✅ |
| P02 | L01 | n ye saga saba feere wa bi duuru | vente | vente ✅ | 250000 | 250000 ✅ |
| P03 | L01 | n ye tika bɔrɛ fere wa | vente | vente ✅ | 15000 | None ❌ |
| P04 | L01 | ne ye safunɛ feere kɛmɛ | vente | vente ✅ | 500 | 500 ✅ |
| P05 | L01 | n ye gansara tan | vente | None ❌ | 2500 | None ❌ |
| P06 | L01 | ne ye fini tafe kelen feere wa kelen ni kɛmɛ duuru | vente | vente ✅ | 7500 | 7500 ✅ |
| P07 | L01 | n ye san ka bɔrɛ kelen san wa duuru | depense | depense ✅ | 25000 | 25000 ✅ |
| P08 | L01 | ne ye situlu san kɛmɛ fila ni bi duuru | depense | depense ✅ | 1250 | 1250 ✅ |
| P09 | L01 | ne ye sɛden duuru san waa fila ni kɛmɛ duuru | depense | depense ✅ | 12500 | 12500 ✅ |
| P10 | L01 | n ye n ka paser sa kɛmɛ ni bi duuru | depense | None ❌ | 750 | None ❌ |
| P11 | L01 | ne ye n ka so sigiyɔrɔ sara dɔrɔmɛ mugan | depense | depense ✅ | 100 | 100 ✅ |
| P12 | L01 | ne ye waa kelen kɛ ka mana foroko san | depense | depense ✅ | 5000 | 5000 ✅ |
| P13 | L01 | ne ka waa fila juru bɛ aw la | client | client ✅ | 10000 | 10000 ✅ |
| P14 | L01 | nɛkɛmɛ wolonwula jurumu bi fa ta la a y'o sara | client | client ✅ | 3500 | 3500 ✅ |
| P15 | L01 | ne ka jagokun ye waa tan | capital | capital ✅ | 50000 | 50000 ✅ |
| P16 | L01 | n ye wa naani fara n ka jagokun kan | capital | capital ✅ | 20000 | 20000 ✅ |
| P17 | L01 | ne ye joli de feere nin kalo in na | consultation | consultation ✅ | None | None ✅ |
| P18 | L01 | ne ka juru bɛ mɔgɔ jɔn na | consultation | consultation ✅ | None | None ✅ |
| P19 | L01 | sanɲɔgɔn bɔrɔ naani de bɛ ne bolo a tɔ la | stock | stock ✅ | None | None ✅ |
| P20 | L01 | n ye saga saba feere wa mugan ni duuru | vente | vente ✅ | 125000 | 125000 ✅ |
| P01b | L02 | ne ka kɛmɛ duuru bɛ mariage na | client | client ✅ | 2500 | 2500 ✅ |
| P02b | L02 | ne ye saga saba feere wa duuru | vente | vente ✅ | 250000 | 25000 ❌ |
| P03b | L02 | ne ye bɔrɔ fila t'a bɔrɔ fila nan yo feere wasa | vente | vente ✅ | 15000 | 10 ❌ |
| P04b | L02 | ne ye safunɛ fe yen | vente | None ❌ | 500 | None ❌ |
| P05b | L02 | ne ye gansa fere | vente | vente ✅ | 2500 | None ❌ |
| P06b | L02 | ne ye fini fere a kelen ni kɛmɛ duuru | vente | vente ✅ | 7500 | 2505 ❌ |
| P07b | L02 | ne ye san bɔrɛ fere wa duuru | depense | vente ❌ | 25000 | 25000 ✅ |
| P08b | L02 | n'i ye situlu feere kɛmɛ fila ni bi duuru | depense | vente ❌ | 1250 | 1250 ✅ |
| P09b | L02 | n'i ye sɛ duuru feere wa duuru | depense | vente ❌ | 12500 | 25000 ❌ |
| P10b | L02 | n ye passe sara kɛmɛ ni bi duuru | depense | depense ✅ | 750 | 750 ✅ |
| P11b | L02 | n ye n ka sugu sigiyɔrɔ sara mugan | depense | depense ✅ | 100 | 100 ✅ |
| P12b | L02 | ɲɛ mana foroko ni bɔrɛw san | depense | depense ✅ | 5000 | None ❌ |
| P13b | L02 | ne ka wa fila bɛ aw juru bɛ aw la | client | client ✅ | 10000 | 10000 ✅ |
| P14b | L02 | fanta ye kɛmɛ wolonwula sara ne ka juru la | client | client ✅ | 3500 | 3500 ✅ |
| P15b | L02 | ne ka jagokun bɛɛ ye waa tan | capital | capital ✅ | 50000 | 50000 ✅ |
| P16b | L02 | n ye wa naani fara n ka jagokun kan | capital | capital ✅ | 20000 | 20000 ✅ |
| P17b | L02 | ne yɛrɛ ka minɛn tɔ tora joli nin kalo in na | consultation | consultation ✅ | None | None ✅ |
| P18b | L02 | mɔgɔ jɔn ni jɔn de ka ne ka juru b'olu la | consultation | consultation ✅ | None | None ✅ |
| P19b | L02 | ɛɛ ɲɔ bɔrɛ naani de tora an bolo | stock | stock ✅ | None | None ✅ |
| P20b | L02 | n'i ye saga fere wa mugan ni duuru | vente | vente ✅ | 125000 | 125000 ✅ |
| P01c | L03 | ne ka kɛmɛ duuru bɛ mariama fɛ | client | client ✅ | 2500 | 2500 ✅ |
| P02c | L03 | saga saba feere bɛ na wa abizulu ma i sɔnna | vente | vente ✅ | 250000 | 15 ❌ |
| P03c | L03 | ne ye tika bɔrɔ feere wasa | vente | vente ✅ | 15000 | None ❌ |
| P04c | L03 | ne ye safunɛ san | vente | depense ❌ | 500 | None ❌ |
| P05c | L03 | ne ye gwa sara tan kɛmɛ duuru | vente | depense ❌ | 2500 | 2500 ✅ |
| P06c | L03 | ne ye fini san waa kelen ni kɛmɛ duuru | vente | depense ❌ | 7500 | 7500 ✅ |
| P07c | L03 | ne ye ɲɔ bɔnɛ kelen san wa duuru | depense | depense ✅ | 25000 | 25000 ✅ |
| P08c | L03 | ne ye si tulu san ne ye si tulu kɛmɛ fila ni bi duuru la san | depense | depense ✅ | 1250 | 1250 ✅ |
| P09c | L03 | ne ye sɛ san waa fila ni kɛmɛ duuru | depense | depense ✅ | 12500 | 12500 ✅ |
| P10c | L03 | n'a ye passer sara kɛmɛ ni bi duuru | depense | depense ✅ | 750 | 750 ✅ |
| P11c | L03 | ne ye n sigiyɔrɔ sara damɛ mugan | depense | depense ✅ | 100 | 100 ✅ |
| P12c | L03 | ne ye waa kelen don bɔrɛw la | depense | None ❌ | 5000 | None ❌ |
| P13c | L03 | ne ka waa fila de bɛ aw la | client | client ✅ | 10000 | 10000 ✅ |
| P14c | L03 | fanta ye ne ka kɛmɛ wolonwula sara | client | depense ❌ | 3500 | 3500 ✅ |
| P15c | L03 | ne ka jagokun tun ye waa tan ye | capital | capital ✅ | 50000 | 50000 ✅ |
| P16c | L03 | ne ye waa tan fa o kan | capital | None ❌ | 20000 | None ❌ |
| P17c | L03 | ne ye joli feere ni kalo in na | consultation | consultation ✅ | None | None ✅ |
| P18c | L03 | ne ka wari bɛ jɔn na | consultation | consultation ✅ | None | None ✅ |
| P19c | L03 | ne ka ɲɔ tun ye bɔrɔ naani ye | stock | None ❌ | None | None ✅ |
| P20c | L03 | ne ye saga saba feere wa mugan ni duuru | vente | vente ✅ | 125000 | 125000 ✅ |
