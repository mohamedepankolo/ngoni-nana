# N'GONI NANA

Assistant vocal en bambara et en français pour le module **Comptabilité** de la formation GERME (OIT). Il s'adresse aux femmes membres des coopératives ABIC Dioïla et aux bénéficiaires FIER II. Le projet est porté par ABIC Dioïla (subvention de prototypage IDRC, en partenariat avec Code for Africa, bac à sable GAIC).

Parcours visé : l'utilisatrice appelle → **reconnaissance vocale (ASR, bambara)** → moteur de décision GERME → base de données → **synthèse vocale (TTS, bambara)** → confirmation vocale.

## État d'avancement

| Brique | Dossier | État |
|---|---|---|
| Test du modèle ASR bambara | `asr_test/` | **en cours** |
| Moteur de décision GERME Comptabilité | `moteur/moteur_decision.py` | **en cours** (premier jet : dictionnaire de mots-clés + machine à états) |
| Intégration ASR (RobotsMali, NeMo) | `moteur/asr_robotsmali.py` | **validé en réel** sur téléphone (2026-10-05) et sur 60 phrases (2026-10-06, 83 % intention), ~0,3 s |
| Intégration TTS (MALIBA-AI) | `moteur/tts_maliba.py` | **validé en réel** sur téléphone (2026-10-05) ; licence CC-BY-NC toujours non confirmée pour la production (R4) ; lit du texte français pour l'instant (voir plus bas) |
| Agent vocal (orchestrateur) + base de données | `moteur/agent_vocal.py`, `moteur/base_donnees.py` | **validé en réel** : vente complète enregistrée via vraie voix, capital mis à jour |
| API Gateway (+ page de test vocal `/web`) | `moteur/api.py`, `moteur/web/` | **validé en réel** : test vocal complet depuis un téléphone, en HTTPS |
| Téléphonie (remplaçant de Retell AI) | n/d | à choisir (R2) |
| Hébergement réel (API, base de données) | n/d | à trancher avec CFA (R1) ; SQLite/Neon en attendant |
| Tableau de bord ABIC | `moteur/admin/` | **en cours**, branché sur les vraies données (voir plus bas) |

## Test ASR : `asr_test/`

Modèle testé : [`FarmRadioInternational/bambara-whisper-asr`](https://huggingface.co/FarmRadioInternational/bambara-whisper-asr) (Whisper, Apache 2.0).

Le test répond aux trois questions posées par Code for Africa :

1. Les mots sont-ils bien transcrits ? → taux d'erreur par mot et par caractère (WER / CER)
2. **Les nombres et montants sont-ils exacts ?** C'est le point critique. On vérifie que le nombre prononcé se retrouve dans la transcription, qu'il soit écrit en chiffres ou en toutes lettres (« waa tan ni duuru »).
3. Le modèle résiste-t-il aux accents et au bruit ? → mêmes mesures, séparées par locutrice et par environnement.

On mesure aussi la latence, avec un objectif de moins de 5 s.

```
asr_test/
  corpus/phrases.csv        20 phrases de transaction : sens, texte bambara, montant, unité, audio
  corpus/PROTOCOLE.md       comment enregistrer (consentement, format, nommage)
  audio/                    enregistrements, gardés HORS de Git (voir .gitignore)
  scripts/transcrire.py     transcrit les audios avec le modèle (HF_TOKEN requis)
  scripts/evaluer.py        compare avec la référence et produit results/rapport.md
  scripts/montants.py       lit les nombres bambara (chiffres ou toutes lettres, dɔrɔmɛ)
```

### Étapes

1. **Corpus** : l'équipe terrain complète `texte_bambara`, `unite`, `locuteur` et `environnement` dans `corpus/phrases.csv`, puis enregistre les audios en suivant `corpus/PROTOCOLE.md`.
2. **Test rapide (navigateur)** : on passe les audios dans la démo [CGIAR/bambara-asr](https://huggingface.co/spaces/CGIAR/bambara-asr). On colle chaque transcription dans un fichier `results/demo_cgiar.csv` avec les colonnes `id,transcription`.
3. **Test approfondi** (en local ou sur Colab), après avoir accepté les conditions d'accès sur la page du modèle :
   ```bash
   pip install -r requirements.txt
   export HF_TOKEN=hf_...
   python asr_test/scripts/transcrire.py
   ```
4. **Rapport** :
   ```bash
   python asr_test/scripts/evaluer.py                                              # modèle en local ou sur Colab
   python asr_test/scripts/evaluer.py --transcriptions asr_test/results/demo_cgiar.csv --rapport asr_test/results/rapport_demo.md
   ```
   Le fichier `results/rapport.md` est le document à envoyer à CfA.

**Sur Colab** : `!git clone` le dépôt, montez le Drive qui contient les audios, copiez-les dans `asr_test/audio/`, puis lancez les commandes ci-dessus précédées de `!`. Choisissez un environnement d'exécution GPU pour une latence réaliste.

### Point important : les montants en dɔrɔmɛ

Beaucoup de prix se disent en **dɔrɔmɛ** (1 dɔrɔmɛ = 5 FCFA), souvent sans prononcer le mot. Exemple tiré du cahier des charges : « wa bi dourou » veut dire 50 000 dɔrɔmɛ, soit **250 000 FCFA**.

Le modèle de reconnaissance vocale ne peut retranscrire que le nombre **prononcé**. C'est donc ce nombre que l'évaluation compare, déduit de `montant_fcfa` et de la colonne `unite` (`fcfa` ou `dorome`). La conversion en FCFA revient au moteur de décision. Il devra confirmer le montant à l'utilisatrice, ou lui faire taper le montant au clavier, comme Isaak Kamau l'a suggéré.

La lecture des nombres en toutes lettres (`montants.py`) suit les règles de numération décrites dans le fichier. **Un·e linguiste bambara doit les valider.**

## MVP : `moteur/`

Tous les composants applicatifs du MVP (Architecture_Technique_NGONI_NANA.docx, section 3), sauf la téléphonie (R2) et l'hébergement réel (R1), toujours ouverts :

```
moteur/
  dictionnaire_mots_cles.py   couche 1 : reconnaissance d'intention par mots-clés bambara (R9)
  moteur_decision.py          couches 2 à 4 : entités, nombres (réutilise montants.py), machine à états de session
  base_donnees.py             schéma SQLAlchemy (section 3.7) ; SQLite par défaut, Postgres/Neon via DATABASE_URL
  agent_vocal.py              orchestrateur (section 3.5) : relie moteur + base de données, gère la confirmation oui/non
  asr_robotsmali.py           intégration ASR (RobotsMali/soloni-be-kalan-v0, backend NeMo) + conversion audio (ffmpeg)
  tts_maliba.py                intégration TTS (MALIBA-AI/MalianTTS, licence CC-BY-NC à confirmer pour la prod, R4)
  api.py                      API Gateway (section 3.6) : /health, /session, /call, /call_audio, /modules, /sms
  web/index.html              page de test "maintenir pour parler" (navigateur, y compris mobile), servie sur /web
```

Jamais de LLM génératif pour comprendre le bambara : le test sur les 42 modèles du sandbox (voir `Rapport comprehension Bambara - Sandbox`) a montré qu'aucun ne le fait de façon fiable. Le moteur est donc un système à règles, testé sur les 60 phrases vérifiées de `asr_test/corpus/phrases_reelles.csv` (`tests/test_moteur_decision.py`) :

- reconnaissance d'intention : **87 %** (52/60), échecs restants documentés et listés explicitement dans le test (substitutions de verbe par une locutrice précise, ou mot-clé absent de cette phrase), pas corrigés au cas par cas pour ne pas surapprendre ce corpus de 60 phrases ;
- montant FCFA reconstruit exactement : **96 %** (49/51).

Ces chiffres partent du texte de référence, pas de l'ASR réel. Le vrai chiffre de bout en bout (ASR + moteur, `asr_test/scripts/tester_pipeline_complet.py`, résultat dans `asr_test/results/pipeline_complet.md`) est plus bas, logiquement : **83 % d'intention correcte, 76 % de montant exact** sur les mêmes 60 enregistrements réels (modèle RobotsMali/soloni-be-kalan-v0, voir `asr_test/COMPARAISON_MODELES.md`), cette fois transcrits par le modèle plutôt que lus depuis le corpus. L'écart vient presque entièrement du bruit de l'ASR (mots tronqués, fusionnés, ou mal transcrits), pas du moteur lui-même. Trois bugs réels trouvés et corrigés grâce à ce test (variante "fere" pour "feere", fusion "ne"+numéral collé, variante "jonw" pour "jɔn"), plus un changement de modèle ASR (nouveau modèle RobotsMali publié début octobre 2026, meilleur sur nos propres phrases) ; le reste des écarts restants est documenté dans le rapport comme du bruit ASR non corrigeable sans réentraîner le modèle.

Le dictionnaire de mots-clés, les mots de confirmation oui/non, et l'extraction d'article/nom propre (heuristique simple, pas d'étiquetage grammatical réel) restent **à valider et compléter par une personne bambaraphone**, comme `montants.py`.

### Pas encore fait, à savoir avant de tester

- La hiérarchie de rôles complète (section 4 : animatrice, gestionnaire de coopérative, administratrice) n'existe pas encore : l'API n'a qu'un seul jeton statique (`API_TOKEN`), pas de vrais comptes.
- Les seuils de vraisemblance des montants (R5), la politique de rétention audio (R7) et le mécanisme d'escalade humaine réel (R6) restent à définir avec Fadima/CFA ; l'escalade ici se limite à un message, rien n'est câblé vers une vraie animatrice.
- Pas de vraie téléphonie (R2) ni d'hébergement tranché (R1) : la page `/web` et `/call_audio` simulent un appel à partir d'un enregistrement navigateur, pas d'un vrai réseau téléphonique.
- Les messages du système (`moteur/messages_bambara.py`) sont maintenant **en bambara**, mais c'est un premier jet non validé : les nombres (`nombres_bambara.py`) sont vérifiés automatiquement par aller-retour avec `montants.py`, mais la grammaire des phrases elle-même ne peut pas s'auto-tester : seule une personne bambaraphone peut confirmer qu'une phrase est correcte et naturelle. À faire relire avant tout usage devant de vraies utilisatrices.

### Lancer l'API en local (avec ASR + TTS réels)

**Python 3.11, pas une version plus récente.** NeMo (ASR) tire des dépendances (numpy, onnx, protobuf, ml_dtypes...) qui, en pratique, ne sont pas encore stables sur Python 3.14 : la combinaison a produit en test une chaîne d'incompatibilités (`numpy`/longdouble, `onnx`/`protobuf`, `onnx`/`ml_dtypes`), chacune corrigeable une à une mais sans fin propre. Un environnement virtuel dédié en 3.11 évite tout ça d'un coup, testé de bout en bout (ASR + TTS réels) le 2026-10-05 dans cette configuration.

```bash
py -3.11 -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
./.venv/Scripts/python.exe -m pip install "nemo-toolkit[asr]"   # lourd (plusieurs Go), à part : voir ci-dessus
cp .env.example .env
# éditer .env : mettre un API_TOKEN et un HF_TOKEN valides (voir ce fichier pour le détail)
```

`ffmpeg` doit être installé et sur le PATH (conversion de l'audio navigateur avant l'ASR).

**Pour tester depuis un téléphone, servir en HTTPS** : les navigateurs mobiles bloquent l'accès au micro (`getUserMedia`) hors HTTPS ou localhost : sans ça, le bouton de la page de test ne fait rien, sans message d'erreur. Un certificat auto-signé suffit (le navigateur affichera un avertissement à accepter une fois) :

```bash
mkdir .certs
MSYS_NO_PATHCONV=1 openssl req -x509 -newkey rsa:2048 -keyout .certs/key.pem -out .certs/cert.pem -days 365 -nodes \
  -subj "/CN=ngoni-nana-test" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:VOTRE_IP_LOCALE"

./.venv/Scripts/python.exe -m uvicorn moteur.api:app --host 0.0.0.0 --port 8099 \
  --ssl-keyfile .certs/key.pem --ssl-certfile .certs/cert.pem
```

**Page de test "maintenir pour parler"** : ouvrir `https://VOTRE_IP_LOCALE:8099/` depuis un téléphone sur le même réseau Wi-Fi, accepter l'avertissement de certificat, entrer l'`API_TOKEN` du `.env`, puis maintenir le bouton pour parler et relâcher pour envoyer. L'ASR (RobotsMali), le moteur de décision et le TTS (MALIBA-AI) tournent réellement, sans téléphonie.

Diagnostic : `NGONI_DEBUG_AUDIO=1` (variable d'environnement) conserve une copie de chaque enregistrement reçu dans `debug_audio/` (brut + converti en WAV), utile si une transcription revient vide sans erreur.

**En ligne de commande, en texte** (sans ASR/TTS, juste moteur + base de données) :

```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/demo/bootstrap -H "Authorization: Bearer $API_TOKEN"
curl -X POST http://127.0.0.1:8000/session -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" -d '{"utilisatrice_id": 1}'
curl -X POST http://127.0.0.1:8000/call -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"session_id": 1, "utilisatrice_id": 1, "texte": "n ye saga saba feere wa bi duuru"}'
```

## Dashboard admin ABIC : `moteur/admin/`

Interface web en lecture seule pour les administratrices ABIC (architecture section 3.8) : suivi des sessions, rapports GERME Comptabilité par coopérative, liste des utilisatrices. Branchée sur la même base de données que l'agent vocal : les sessions et transactions de test apparaissent immédiatement dedans.

```
moteur/admin/
  donnees.py              requêtes de lecture (KPIs, listes filtrées, rapport par coopérative)
  routes.py               routes /admin/* (FastAPI), authentification HTTP Basic
  templates/               pages Jinja2 (base, vue_ensemble, utilisatrices, sessions, rapports)
```

Accessible sur `https://.../admin/` une fois l'API lancée (voir ci-dessus) : identifiant libre, mot de passe = `API_TOKEN` du `.env` (le navigateur affiche une boîte de connexion native). 4 pages : Vue d'ensemble (KPIs, répartition par coopérative, alertes stock bas), Utilisatrices (filtrable par coopérative/recherche), Sessions (filtrable par coopérative/statut/canal), Rapports (recettes/dépenses/solde par coopérative, export CSV).

**Limite connue** : un seul niveau d'accès ("Administratrice ABIC", tout voir) : les deux autres rôles qui touchent à un dashboard (animatrice : ses utilisatrices assignées seulement ; gestionnaire de coopérative : rapports agrégés de sa coopérative seulement, section 4 de l'architecture) demandent de vrais comptes, qui n'existent pas encore.

### Tests

```bash
pip install -r requirements.txt
pytest
```
