# Échantillons de synthèse (MALIBA-AI TTS)

Deux phrases du corpus (`P01`, `P02`) lues par le modèle de synthèse vocale
bambara [MALIBA-AI/bambara-tts](https://huggingface.co/MALIBA-AI/bambara-tts)
(voix "Bourama"), via l'espace hébergé
[MALIBA-AI/MalianTTS](https://huggingface.co/spaces/MALIBA-AI/MalianTTS).

**Pourquoi ces fichiers existent** : en attendant les vrais enregistrements
de l'équipe terrain, ils permettent de tester `transcrire.py` +
`evaluer.py` de bout en bout avec du **vrai bambara** (pas une voix
anglaise lisant du français) et des **montants connus**, ce qui est le
point le plus critique du cahier des charges.

⚠️ **Ce ne sont pas des voix humaines réelles ni des phrases terrain** :
elles ne remplacent pas le vrai test avec les 15-20 enregistrements de
l'équipe (voir `../corpus/PROTOCOLE.md`). Un résultat correct ici ne
garantit rien sur une vraie utilisatrice avec un vrai téléphone dans un
vrai marché.

**Licence** : le modèle MALIBA-AI TTS est sous CC-BY-NC-SA-4.0
(usage non commercial), compatible avec ce projet à but non lucratif.

## Contenu

| Fichier | Description |
|---|---|
| `maliba_p01.wav`, `maliba_p02.wav` | Audios de synthèse pour P01 et P02 |
| `corpus.csv` | Corpus minimal pointant vers ces deux audios |
| `transcriptions_exemple.csv`, `rapport_exemple.md` | Résultat d'un run du 23/09/2026 (modèle `FarmRadioInternational/bambara-whisper-asr`), à titre d'exemple |

## Pour relancer ce test

```bash
python asr_test/scripts/transcrire.py \
  --corpus asr_test/audio_synthetique/corpus.csv \
  --audio  asr_test/audio_synthetique \
  --sortie asr_test/audio_synthetique/transcriptions_exemple.csv

python asr_test/scripts/evaluer.py \
  --corpus asr_test/audio_synthetique/corpus.csv \
  --transcriptions asr_test/audio_synthetique/transcriptions_exemple.csv \
  --rapport asr_test/audio_synthetique/rapport_exemple.md
```

## Constat du run du 23/09/2026

Les deux montants ont été mal reconnus, pour deux raisons distinctes :

- **P01** (« 2500 francs ») : aucun nombre entendu par l'ASR. À vérifier
  en écoutant l'audio si c'est le TTS qui ne prononce pas bien un montant
  écrit en chiffres, ou l'ASR qui ne l'entend pas.
- **P02** (« wa bi dourou » = 50 000) : l'ASR a fusionné « wa » et « bi »
  en un seul mot « biwa », ce qui empêche `montants.py` de reconnaître le
  marqueur des milliers. À corriger dans `montants.py` : tolérer les mots
  numéraux collés, pas seulement séparés par des espaces.
