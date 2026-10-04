# N'GONI NANA

Assistant vocal en bambara et en français pour le module **Comptabilité** de la formation GERME (OIT). Il s'adresse aux femmes membres des coopératives ABIC Dioïla et aux bénéficiaires FIER II. Le projet est porté par ABIC Dioïla (subvention de prototypage IDRC, en partenariat avec Code for Africa, bac à sable GAIC).

Parcours visé : l'utilisatrice appelle → **reconnaissance vocale (ASR, bambara)** → moteur de décision GERME → base de données → **synthèse vocale (TTS, bambara)** → confirmation vocale.

## État d'avancement

| Brique | Dossier | État |
|---|---|---|
| Test du modèle ASR bambara | `asr_test/` | **en cours** |
| Moteur de décision GERME Comptabilité | `moteur/moteur_decision.py` | **en cours** (premier jet : dictionnaire de mots-clés + machine à états) |
| Intégration ASR (RobotsMali, NeMo) | `moteur/asr_robotsmali.py` | code prêt, pas encore exécuté en bout en bout (dépendance NeMo lourde, non installée ici) |
| Intégration TTS (MALIBA-AI) | `moteur/tts_maliba.py` | code prêt ; licence CC-BY-NC toujours non confirmée pour la production (R4) |
| Agent vocal (orchestrateur) + base de données | `moteur/agent_vocal.py`, `moteur/base_donnees.py` | **en cours**, testé de bout en bout en texte (SQLite local) |
| API Gateway | `moteur/api.py` | **en cours**, testé de bout en bout (voir plus bas) |
| Téléphonie (remplaçant de Retell AI) | — | à choisir (R2) |
| Hébergement réel (API, base de données) | — | à trancher avec CFA (R1) ; SQLite/Neon en attendant |
| Tableau de bord ABIC | — | maquette Figma faite, code à venir |

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
  asr_robotsmali.py           intégration ASR (RobotsMali/soloni-114m-tdt-ctc-v3, backend NeMo)
  tts_maliba.py                intégration TTS (MALIBA-AI/MalianTTS, licence CC-BY-NC à confirmer pour la prod, R4)
  api.py                      API Gateway (section 3.6) : /health, /session, /call, /modules, /sms
```

Jamais de LLM génératif pour comprendre le bambara : le test sur les 42 modèles du sandbox (voir `Rapport comprehension Bambara - Sandbox`) a montré qu'aucun ne le fait de façon fiable. Le moteur est donc un système à règles, testé sur les 60 phrases vérifiées de `asr_test/corpus/phrases_reelles.csv` (`tests/test_moteur_decision.py`) :

- reconnaissance d'intention : **87 %** (52/60), échecs restants documentés et listés explicitement dans le test (substitutions de verbe par une locutrice précise, ou mot-clé absent de cette phrase) — pas corrigés au cas par cas pour ne pas surapprendre ce corpus de 60 phrases ;
- montant FCFA reconstruit exactement : **96 %** (49/51).

Le dictionnaire de mots-clés, les mots de confirmation oui/non, et l'extraction d'article/nom propre (heuristique simple, pas d'étiquetage grammatical réel) restent **à valider et compléter par une personne bambaraphone**, comme `montants.py`.

### Pas encore fait, à savoir avant de tester

- `asr_robotsmali.py` et `tts_maliba.py` sont du code réel, pas des maquettes, mais **pas exécutés de bout en bout dans ce dépôt** : NeMo (ASR) est une dépendance lourde non installée par défaut, et le TTS a besoin d'un `HF_TOKEN` + d'un accès réseau à Hugging Face. `/call` prend donc du texte déjà transcrit, pas un fichier audio, pour l'instant.
- La hiérarchie de rôles complète (section 4 : animatrice, gestionnaire de coopérative, administratrice) n'existe pas encore : l'API n'a qu'un seul jeton statique (`API_TOKEN`), pas de vrais comptes.
- Les seuils de vraisemblance des montants (R5), la politique de rétention audio (R7) et le mécanisme d'escalade humaine réel (R6) restent à définir avec Fadima/CFA ; l'escalade ici se limite à un message, rien n'est câblé vers une vraie animatrice.

### Lancer l'API en local

```bash
pip install -r requirements.txt
export API_TOKEN=demo
export DATABASE_URL=sqlite:///ngoni_nana.db   # omis = même défaut
python -m uvicorn moteur.api:app --reload
```

Puis, par exemple :

```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/session -H "Authorization: Bearer demo" \
  -H "Content-Type: application/json" -d '{"utilisatrice_id": 1}'
curl -X POST http://127.0.0.1:8000/call -H "Authorization: Bearer demo" \
  -H "Content-Type: application/json" \
  -d '{"session_id": 1, "utilisatrice_id": 1, "texte": "n ye saga saba feere wa bi duuru"}'
```

### Tests

```bash
pip install -r requirements.txt
pytest
```
