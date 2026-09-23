# Comparaison de modèles ASR bambara (23/09/2026)

**Mise à jour** : RobotsMali/soloni-114m-tdt-ctc-v3 est maintenant intégré
au pipeline officiel — `transcrire.py --modele RobotsMali/soloni-114m-tdt-ctc-v3`
suffit (le backend NeMo est auto-détecté au préfixe `RobotsMali/`, sinon
`--backend nemo` explicite). Les deux bugs de compatibilité NeMo notés plus
bas sont maintenant corrigés automatiquement au runtime par `transcrire.py`,
plus besoin de patcher site-packages à la main. `montants.py` a aussi été
corrigé (dictionnaire élargi + tolérance aux mots collés) : le montant P02
est maintenant retrouvé avec RobotsMali (1/2 au lieu de 0/2, voir détail
plus bas — inchangé pour P01, qui reste un problème de synthèse TTS, pas
du parseur).

Le modèle prévu dans Réponses_Amina (`FarmRadioInternational/bambara-whisper-asr`)
n'est **pas benchmarké** sur le [leaderboard communautaire](https://huggingface.co/spaces/MALIBA-AI/bambara-asr-leaderboard)
qui compare une quarantaine de modèles bambara. Avant d'aller plus loin, on a
testé deux alternatives libres avec notre propre pipeline (`transcrire.py` +
`evaluer.py`), sur 7 échantillons : les 2 phrases à montants connus du
cahier des charges (lues en synthèse vocale par MALIBA-AI TTS, voir
`audio_synthetique/`) + 5 extraits de vrai bambara parlé (dataset public
[RobotsMali/afvoices](https://huggingface.co/datasets/RobotsMali/afvoices)).

⚠️ Échantillon minuscule (n=7, dont seulement 2 avec montant) — ces chiffres
indiquent une tendance, pas une conclusion statistique. Rien ne remplace un
vrai test sur les enregistrements terrain à venir.

## Résultats

| | FarmRadioInternational<br>(modèle actuel) | RobotsMali/<br>soloni-114m-tdt-ctc-v3 | MALIBA-AI/<br>bambara-asr-v3 |
|---|---|---|---|
| WER — 5 échantillons réels | 36 % | **21 %** | 50 % |
| WER — 2 phrases à montants | 60 % | 64 % | 56 % |
| Montants exacts trouvés | 0/2 | 0/2 | 0/2 |
| Latence (CPU, par phrase) | 16 – 38 s | **0,1 – 0,4 s** | 58 – 84 s |
| Taille | ~0,8 Md param. (Whisper-medium) | **114 M param.** | 2 Md param. (Whisper-large-v3) |
| Licence | ? (non vérifiée) | CC-BY-4.0, libre | CC-BY-NC-4.0, non commercial, gated |
| Fiabilité | RAS | RAS | ⚠️ bascule en anglais halluciné sur 2/5 échantillons réels (voir ci-dessous) |

### Détail des montants (le point critique du cahier des charges)

Aucun des trois modèles n'a retrouvé le bon montant sur nos 2 échantillons,
mais **pour trois raisons différentes**, toutes côté `montants.py` plutôt
qu'un vrai échec de compréhension :

- **FarmRadioInternational** : fusionne « wa » et « bi » en un seul mot
  « biwa », donc `montants.py` ne reconnaît plus le marqueur des milliers.
- **RobotsMali/soloni** : transcrit « dourou » en « dou » tronqué, variante
  absente du dictionnaire de `montants.py`.
- **MALIBA-AI/bambara-asr-v3** : ne prononce/entend pas du tout "2500" (le
  chiffre écrit en digits dans le texte de référence disparaît entièrement,
  y compris pour les deux autres modèles — sur ce point précis, le
  problème vient peut-être de la synthèse MALIBA-AI TTS elle-même, pas de
  l'ASR. Voir `audio_synthetique/README.md`).

→ Fait : dictionnaire de numéraux élargi (variante « dou ») et parseur
  rendu tolérant aux mots collés dans `montants.py`. Corrige le cas
  RobotsMali (P02 ✅) et le cas FarmRadioInternational (« biwa » → 50 000
  retrouvé aussi, vérifié manuellement). Le cas P01 (MALIBA-AI et les deux
  autres modèles) reste non résolu : aucun des trois n'entend le moindre
  chiffre, ce qui pointe vers la synthèse TTS plutôt que vers l'ASR ou le
  parseur (voir `audio_synthetique/README.md`).

### Problème de fiabilité trouvé sur MALIBA-AI/bambara-asr-v3

Sur 2 des 5 échantillons de bambara réel (AFV00, AFV02), le modèle n'a pas
transcrit en bambara mais a produit une **phrase anglaise sans rapport**
(« I can't wait until she gets old. », « It's a good idea. »). C'est un
comportement d'hallucination de traduction connu sur les modèles Whisper
multilingues quand ils hésitent sur la langue source — un risque sérieux
pour un assistant vocal en production, où une réponse plausible mais fausse
est pire qu'une erreur de reconnaissance.

## Recommandation

**RobotsMali/soloni-114m-tdt-ctc-v3** est le candidat le plus prometteur à
creuser en priorité :
- Meilleur WER sur de la parole naturelle (21 % vs 36 % pour le modèle
  actuel).
- Considérablement plus rapide (sous la seconde, même sur CPU) — décisif
  pour l'objectif de latence < 5 s du cahier des charges, qu'aucun des
  deux autres modèles ne tient sur CPU.
- Vraiment libre (CC-BY-4.0, pas de compte ni de token requis).
- 17x plus petit que le modèle actuel → coûts d'inférence et d'hébergement
  bien moindres.

**Inconvénient à peser** : il tourne sur le toolkit **NVIDIA NeMo**, pas sur
`transformers` comme le reste du pipeline — une dépendance nettement plus
lourde à faire fonctionner sur le GAIC Sandbox. À vérifier avec Isaak/CFA.
Le pipeline de test (`transcrire.py`) gère déjà les deux backends de façon
transparente, mais ça ne dit rien de la faisabilité d'un déploiement NeMo
sur le sandbox lui-même.

**MALIBA-AI/bambara-asr-v3** ne semble pas adapté à ce projet : plus lent
que le modèle actuel sur CPU, licence non commerciale, et le risque
d'hallucination en anglais est disqualifiant pour un usage en production.
Il resterait pertinent uniquement si un déploiement GPU devient possible.

## Notes techniques (pour qui reproduit ce test)

Deux bugs d'environnement rencontrés et contournés, sans rapport avec la
qualité des modèles eux-mêmes :

1. **NeMo + Python 3.11 sous Windows** : `nemo.utils.tar_utils.safe_extract`
   appelle `TarFile.extract(..., filter="data")`, un paramètre qui n'existe
   qu'à partir de Python 3.12. Un deuxième bug de compatibilité de version
   touche `BoostingTreeModelConfig.is_empty()` (accès à un champ de config
   absent d'un checkpoint plus ancien). **Désormais corrigé automatiquement**
   par `transcrire.py` (`_patch_compat_nemo()`, appliqué au runtime avant
   de charger un modèle NeMo — sans effet si NeMo a corrigé ces bugs
   entre-temps).
2. **MALIBA-AI/bambara-asr-v3 en fp16 sur CPU** : le pipeline `transformers`
   charge le modèle dans le dtype natif du checkpoint (fp16), ce qui l'a
   fait tourner plus d'une heure sans produire le moindre résultat sur un
   clip de 2 s (CPU à ~270 %, donc pas un vrai blocage — juste des calculs
   fp16 non optimisés sur CPU). Forcer `torch_dtype=torch.float32` à
   l'instanciation du pipeline règle le problème (64-84 s/phrase ensuite,
   toujours trop lent pour l'objectif de latence).

`transcrire.py` a aussi été durci (`generate_kwargs={"max_new_tokens": ...}`,
`--max-new-tokens` en CLI) pour éviter qu'une génération parte en boucle
sans jamais rendre la main, quel que soit le modèle utilisé.
