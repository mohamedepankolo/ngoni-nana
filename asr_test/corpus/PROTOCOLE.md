# Protocole d'enregistrement — test ASR bambara

## Avant d'enregistrer

- **Consentement** : avant tout enregistrement, on explique à chaque participante, en bambara, que sa voix sert à tester un outil, qu'elle est gardée en privé et qu'elle peut refuser. On note son accord oral ou écrit.
- On ne note **ni nom réel ni numéro de téléphone** dans les fichiers. On donne à chaque locutrice un code (`L01`, `L02`, etc.) et la correspondance code → personne reste hors du dépôt.
- Les audios se partagent par Drive, **jamais sur GitHub**. Le `.gitignore` les exclut déjà.

## Les phrases

- On part du sens en français donné dans `phrases.csv` (colonne `sens_fr`). La participante dit la phrase **comme elle la dirait naturellement** au marché, sans lire.
- Juste après, on écrit dans `texte_bambara` ce qui a été **réellement dit**, avec l'orthographe officielle si possible (ɛ, ɔ, ɲ). C'est cette référence qui sert à juger la transcription.
- Colonne `unite` : on met `dorome` si le montant a été dit en dɔrɔmɛ, même sans prononcer le mot, sinon `fcfa`. On la remplit **selon ce qui a été dit**, pas selon la valeur pré-remplie.
- Si le montant dit est différent de celui prévu, on corrige `montant_fcfa`.
- Les phrases P17 à P19 n'ont pas de montant : elles servent seulement à mesurer la qualité de transcription des mots.

## Format audio

- Téléphone posé à environ 20 cm de la bouche. Mono. WAV de préférence, sinon m4a, mp3 ou ogg (ils sont convertis automatiquement).
- Nom du fichier : `<id>_<locutrice>_<environnement>.wav`, par exemple `P03_L01_calme.wav`. On l'inscrit dans la colonne `fichier_audio`.
- Colonne `environnement` : `calme` (pièce fermée) ou `bruit` (marché, rue, enfants, radio).

## Objectif minimal

- Les 20 phrases × **au moins 2 locutrices** (idéalement une de Dioïla et une de Kolondieba ou Bamako).
- Au moins **5 phrases avec montant enregistrées en environnement bruyant**.
- Si une phrase a plusieurs enregistrements, on duplique sa ligne avec un id suffixé (`P03b`) et le nouveau fichier.
