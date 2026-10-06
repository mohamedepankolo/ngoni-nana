# Pipeline complet (ASR réel + moteur de décision) : RobotsMali/soloni-be-kalan-v0

Intention correcte, bout en bout (ASR réel, pas le texte de référence) : **50/60 (83 %)**

Montant exact, bout en bout : **39/51 (76 %)**

Latence ASR moyenne : 0.29 s

## Détail

| id | locuteur | transcription ASR | intention attendue | intention trouvée | montant attendu | montant trouvé |
|---|---|---|---|---|---|---|
| P01 | L01 | ne ka kɛmɛ duuru bɛ mariyamu na | client | client ✅ | 2500 | 2500 ✅ |
| P02 | L01 | n ye saga saba feere wa bi duuru | vente | vente ✅ | 250000 | 250000 ✅ |
| P03 | L01 | u ye tiga bɔrɛ fila feere wa saba saba | vente | vente ✅ | 15000 | 15000 ✅ |
| P04 | L01 | ne ye safunɛ feere kɛmɛ | vente | vente ✅ | 500 | 500 ✅ |
| P05 | L01 | n ye gan sara tan feere kɛmɛ ni duuru | vente | vente ✅ | 2500 | 525 ❌ |
| P06 | L01 | ne ye finita fɛn feere wa kelen ni kɛmɛ duuru | vente | vente ✅ | 7500 | 7500 ✅ |
| P07 | L01 | n ye saɲɔ bɔrɛ kelen san wa duuru | depense | depense ✅ | 25000 | 25000 ✅ |
| P08 | L01 | ne ye situlu san kɛmɛ fila ni bi duuru | depense | depense ✅ | 1250 | 1250 ✅ |
| P09 | L01 | ne ye shɛ den duuru san wa fila ani kɛmɛ duuru | depense | depense ✅ | 12500 | 10000 ❌ |
| P10 | L01 | n ye n ka pase sara kɛmɛ ni bi duuru | depense | depense ✅ | 750 | 750 ✅ |
| P11 | L01 | ne ye n ka so sigiyɔrɔ sara dɔrɔmɛ mugan | depense | depense ✅ | 100 | 100 ✅ |
| P12 | L01 | ne ye wa kelen kɛ ka maana foroko san | depense | depense ✅ | 5000 | 5000 ✅ |
| P13 | L01 | ne ka wa fila juru bɛ awa la | client | client ✅ | 10000 | 10000 ✅ |
| P14 | L01 | ne ka kɛmɛ wolonwula juru min bɛ fanta la a ye o sara | client | client ✅ | 3500 | 3500 ✅ |
| P15 | L01 | ne ka jagokun ye wa tan | capital | capital ✅ | 50000 | 50000 ✅ |
| P16 | L01 | n ye wa naani fara n ka jagokun kan | capital | capital ✅ | 20000 | 20000 ✅ |
| P17 | L01 | ne ye joli de feere nin kalo in na | consultation | consultation ✅ | None | None ✅ |
| P18 | L01 | ne ka juru bɛ mɔgɔ jɔnw la | consultation | consultation ✅ | None | None ✅ |
| P19 | L01 | sɛgɛn bɔrɔ naani de bɛ ne bolo a tɔ la | stock | stock ✅ | None | None ✅ |
| P20 | L01 | n ye saga saba feere wa mugan ni duuru | vente | vente ✅ | 125000 | 125000 ✅ |
| P01b | L02 | ne ka kɛmɛ duuru bɛ mariyamu na | client | client ✅ | 2500 | 2500 ✅ |
| P02b | L02 | ne ye saga saba feere wa bi duuru | vente | vente ✅ | 250000 | 250000 ✅ |
| P03b | L02 | ne ye tiga bɔrɛ fila ne ye o feere wa saba | vente | vente ✅ | 15000 | 15000 ✅ |
| P04b | L02 | ne ye safunɛ feere | vente | vente ✅ | 500 | None ❌ |
| P05b | L02 | ne ye gan san feere kɛmɛ ni bi duuru | vente | vente ✅ | 2500 | 750 ❌ |
| P06b | L02 | ne ye fini feere hakilinw | vente | vente ✅ | 7500 | None ❌ |
| P07b | L02 | ne ye saɲɔ bɔrɛ feere wa duuru | depense | vente ❌ | 25000 | 25000 ✅ |
| P08b | L02 | n ye situlu feere kɛmɛ fila ni bi duuru | depense | vente ❌ | 1250 | 1250 ✅ |
| P09b | L02 | n ye siyɛ duuru feere wa fila ni kɛmɛ duuru | depense | vente ❌ | 12500 | 12500 ✅ |
| P10b | L02 | n ye pase sara kɛmɛ ni bi duuru | depense | depense ✅ | 750 | 750 ✅ |
| P11b | L02 | n ye nka sugu sigiyɔrɔ sara mun kan | depense | depense ✅ | 100 | None ❌ |
| P12b | L02 | n ye maanafo ni bɔrɛw san | depense | depense ✅ | 5000 | None ❌ |
| P13b | L02 | ne ka wa fila juru bɛ awa la | client | client ✅ | 10000 | 10000 ✅ |
| P14b | L02 | fanta ye kɛmɛ wolonfila sara ne ka juru la | client | client ✅ | 3500 | 3500 ✅ |
| P15b | L02 | ne ka jagokun bɛ wa tan | capital | capital ✅ | 50000 | 50000 ✅ |
| P16b | L02 | n ye wa naani fara n ka jagokunw kan | capital | capital ✅ | 20000 | 20000 ✅ |
| P17b | L02 | ne yɛrɛ ka minɛ tɔ tora joli ni kalo in na | consultation | consultation ✅ | None | None ✅ |
| P18b | L02 | mɔgɔ jɔn ni jɔn de bɛ ne ka juru kolo la | consultation | consultation ✅ | None | None ✅ |
| P19b | L02 | ɛɛ ɲɔ bɔrɛ naani de tora an bolo | stock | stock ✅ | None | None ✅ |
| P20b | L02 | n ye saga saba feere wa mugan ni duuru | vente | vente ✅ | 125000 | 125000 ✅ |
| P01c | L03 | ne ka kɛmɛ duuru bɛ mariyamu fɛ | client | client ✅ | 2500 | 2500 ✅ |
| P02c | L03 | saga saba feerelen bɛ wa bi duuru ma i sɔnna | vente | vente ✅ | 250000 | 250000 ✅ |
| P03c | L03 | ne ye tiga bɔrɛ fila feere wa saba | vente | vente ✅ | 15000 | 15000 ✅ |
| P04c | L03 | ne ye safinɛ san | vente | depense ❌ | 500 | None ❌ |
| P05c | L03 | ne ye gan sarata feere kɛmɛ duuru | vente | vente ✅ | 2500 | 2500 ✅ |
| P06c | L03 | ne ye finiw san wa kelen ni kɛmɛ duuru | vente | depense ❌ | 7500 | 7500 ✅ |
| P07c | L03 | ne ye ɲɔ bɔrɛ kelen san wa duuru | depense | depense ✅ | 25000 | 25000 ✅ |
| P08c | L03 | ne ye si san ne ye situlu kɛmɛ fila ni bi duuru san | depense | depense ✅ | 1250 | 1250 ✅ |
| P09c | L03 | ne ye shɛ san shɛ san ni kɛmɛ duuru | depense | depense ✅ | 12500 | 2500 ❌ |
| P10c | L03 | ne ye pase sara kɛmɛ ni bi duuru | depense | depense ✅ | 750 | 750 ✅ |
| P11c | L03 | ne ye sigiyɔrɔ sara da mugan | depense | depense ✅ | 100 | 100 ✅ |
| P12c | L03 | ne ye wa kelen don bɔrɛ la | depense | None ❌ | 5000 | None ❌ |
| P13c | L03 | ne ka wa fila de bɛ a walan | client | None ❌ | 10000 | None ❌ |
| P14c | L03 | fanta ye ne ka kɛmɛ wolonwula sara | client | depense ❌ | 3500 | 3500 ✅ |
| P15c | L03 | ne ka jagokun tun ye wa tan ye | capital | capital ✅ | 50000 | 50000 ✅ |
| P16c | L03 | ne banana | capital | None ❌ | 20000 | None ❌ |
| P17c | L03 | ne ye joli feere nin kalo in na | consultation | consultation ✅ | None | None ✅ |
| P18c | L03 | ne ka wari bɛ jɔn na | consultation | consultation ✅ | None | None ✅ |
| P19c | L03 | ne ka ɲɔ tɔ ye bɔrɛ naani ye | stock | None ❌ | None | None ✅ |
| P20c | L03 | ne ye saga saba feere wa mugan ni duuru | vente | vente ✅ | 125000 | 125000 ✅ |
