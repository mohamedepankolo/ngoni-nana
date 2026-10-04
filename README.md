# N'GONI NANA

Assistant vocal en bambara et en français pour le module **Comptabilité** de la formation GERME (OIT). Il s'adresse aux femmes membres des coopératives ABIC Dioïla et aux bénéficiaires FIER II. Le projet est porté par ABIC Dioïla (subvention de prototypage IDRC, en partenariat avec Code for Africa, bac à sable GAIC).

Parcours visé : l'utilisatrice appelle → **reconnaissance vocale (ASR, bambara)** → moteur de décision GERME → base de données → **synthèse vocale (TTS, bambara)** → confirmation vocale.

## État d'avancement

| Brique | Dossier | État |
|---|---|---|
| Test du modèle ASR bambara | `asr_test/` | **en cours** |
| Moteur de décision GERME Comptabilité | `moteur/` | **en cours** (premier jet : dictionnaire de mots-clés + machine à états) |
| TTS bambara (MALIBA-AI, licence à valider) | — | bloqué : licence |
| Téléphonie (remplaçant de Retell AI) | — | à choisir |
| API et tableau de bord ABIC | — | à venir |

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

## Moteur de décision : `moteur/`

Premier jet du moteur de décision GERME Comptabilité (étape 5.1 du workplan), en 4 couches comme défini dans `Architecture_Technique_NGONI_NANA.docx` (section 3.3) :

```
moteur/
  dictionnaire_mots_cles.py   couche 1 : reconnaissance d'intention par mots-clés bambara (R9)
  moteur_decision.py          couches 2 à 4 : entités, nombres (réutilise montants.py), machine à états de session
```

Jamais de LLM génératif ici : le test sur les 42 modèles du sandbox (voir `Rapport comprehension Bambara - Sandbox`) a montré qu'aucun ne comprend le bambara de façon fiable. Le moteur est donc un système à règles, testé sur les 60 phrases vérifiées de `asr_test/corpus/phrases_reelles.csv` (`tests/test_moteur_decision.py`) :

- reconnaissance d'intention : **87 %** (52/60), échecs restants documentés et listés explicitement dans le test (substitutions de verbe par une locutrice précise, ou mot-clé absent de cette phrase) — pas corrigés au cas par cas pour ne pas surapprendre ce corpus de 60 phrases ;
- montant FCFA reconstruit exactement : **96 %** (49/51).

Le dictionnaire de mots-clés et l'extraction d'article/nom propre (heuristique simple, pas d'étiquetage grammatical réel) restent **à valider et compléter par une personne bambaraphone**, comme `montants.py`.

### Tests

```bash
pip install jiwer pytest
pytest
```
