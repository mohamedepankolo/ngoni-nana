# Évaluation d'un LLM généraliste sur le bambara écrit (N'GONI NANA V2)

Contexte : suite à `Communications/instructions.docx`, qui recommandait de
tester un LLM sur le bambara écrit avant toute décision d'architecture et
avant d'ajouter la complexité de l'audio. Trois protocoles testés sur les 53
phrases bambara réelles distinctes du corpus (`asr_test/corpus/phrases_reelles.csv`),
chacun avec un agent isolé n'ayant jamais vu les réponses attendues (test en
aveugle, pas une relecture de données déjà mémorisées dans cette session).

## Protocole 1 — glossaire complet, 6 catégories (achat replié dans depense)

Le modèle reçoit : un glossaire de verbes/nombres/grammaire bambara, la règle
de conversion dɔrɔmɛ (1 dɔrɔmɛ = 5 F CFA), un schéma JSON cible à 6
catégories (vente/depense/dette_client/capital/consultation/stock).

| Mesure | Résultat |
|---|---|
| Montants FCFA exacts | **45 / 45 — 100 %** |
| Intentions correctes | **50 / 53 — 94 %** |

Les 3 désaccords correspondent tous à des phrases où la locutrice a
prononcé un verbe différent de celui attendu par l'étiquette du corpus
(ex. "feere"=vendre dit à la place de "san"=acheter) — un phénomène déjà
documenté, indépendamment de ce test, dans
`tests/test_moteur_decision.py` (`ECHECS_CONNUS_INTENTION`, 8 cas connus du
moteur à règles actuel). Sur ces mêmes 8 cas, le LLM est tombé d'accord avec
le corpus sur 5 d'entre eux, le moteur à règles sur aucun.

## Protocole 2 — même glossaire, 7 catégories (achat séparé), lecture stricte du verbe littéral

Correctif demandé après le protocole 1 : le repli achat→depense empêchait une
comparaison équitable avec les 7 catégories réelles du corpus. Le modèle est
cette fois explicitement instruit de classer selon le verbe littéralement
prononcé, pas selon ce qui "ferait sens" commercialement.

| Mesure | Résultat |
|---|---|
| Montants FCFA exacts | **51 / 53 — 96 %** |
| Intentions correctes (face au corpus) | **45 / 53 — 85 %** |

Deux montants faux cette fois, tous les deux sur la **même construction
numérique** ("waa [dizaine] ni [unité]", ex. "waa mugan ni duuru" =
1000×(20+5)=25 000 dɔrɔmɛ) : le modèle a additionné après la conversion au
lieu d'avant, à l'identique les deux fois que cette construction apparaît —
une vraie erreur de calcul, reproductible, pas un hasard (détail dans
`DESACCORDS_LLM_A_VALIDER.md`).

La baisse du taux d'intention (94 %→85 %) ne traduit pas une moins bonne
compréhension : 2 des 8 désaccords supplémentaires viennent d'un flou **déjà
documenté dans notre propre corpus** entre "achat" et "depense" (ex. l'achat
d'emballages, annoté "depense" dans le corpus de référence alors que le mot
prononcé est bien "san"=acheter — notre moteur à règles traite d'ailleurs
tout achat comme un cas de dépense pour cette même raison). Les autres
désaccords restent la même famille de substitutions verbales déjà connue, +1
nouveau cas identique (P09b) révélé par la séparation plus stricte des
catégories, et 2 cas que le modèle lui-même a signalés comme des choix
limites honnêtes (vocabulaire hors glossaire ; absence du mot "juru" dans un
contexte de remboursement).

## Protocole 3 — sans aucun glossaire (ablation), connaissance propre du modèle

Objectif explicite de ce protocole : mesurer ce qui relève d'une vraie
connaissance préalable du bambara par le modèle, par opposition à ce qui
n'existe que parce qu'on le lui a donné en contexte. Le modèle reçoit
uniquement les 53 phrases et le schéma JSON cible — aucun vocabulaire, aucune
règle de conversion monétaire, aucune indication sur le sens des mots.

| Mesure | Résultat |
|---|---|
| Intentions correctes | Élevé, du même ordre que les protocoles 1-2 (mêmes 4 cas de substitution verbale signalés spontanément comme ambigus, sans qu'on les lui pointe) |
| Montants FCFA exacts | **3 / 45 — 7 %** |

**C'est le résultat le plus important des trois protocoles.** Sans qu'on le
lui dise, le modèle a traité les montants comme des francs CFA directs,
sans appliquer la conversion ×5. Les 3 seuls montants corrects sont les 2
phrases où le mot "dɔrɔmɛ" est prononcé explicitement, plus 1 cas où le
modèle a deviné juste par analogie avec une phrase sœur. Les 42 autres sont
**systématiquement 5 fois trop bas**.

Le modèle lui-même confirme, dans son paragraphe d'auto-évaluation final,
que son vocabulaire bambara (saga=mouton, sɛ=poulet, ɲɔ=mil, juru=dette,
jagokun=capital, les verbes san/feere/sara, le système numéral complet...)
vient d'une vraie connaissance préalable de la langue, pas d'un bachotage sur
ces 53 phrases répétées — mais que la convention dɔrɔmɛ=5 F CFA n'en fait
clairement pas partie : c'est un usage commercial local, culturellement
spécifique, absent de toute ressource générale sur le bambara.

## Synthèse des trois protocoles

| | Protocole 1 (glossaire complet) | Protocole 2 (glossaire + lecture stricte) | Protocole 3 (sans glossaire) |
|---|---|---|---|
| Intentions | 94 % | 85 %* | élevé, non chiffré précisément |
| Montants | **100 %** | 96 % | **7 %** |

*la baisse ne traduit pas une régression de compréhension (voir ci-dessus).

**Conclusion directe** : un LLM généraliste a une vraie connaissance
préalable du vocabulaire et de la grammaire bambara de ce domaine (confirmé
par le protocole 3 pour l'identification des opérations), mais **aucune**
connaissance de la convention monétaire locale (dɔrɔmɛ) — celle-ci doit être
fournie explicitement, par un glossaire en contexte (ce qui fonctionne : 100 %
et 96 % dans les protocoles 1-2) et/ou par un analyseur déterministe dédié,
comme le fait déjà `montants.py` pour le moteur actuel. Combiner les deux
(LLM guidé pour l'intention/les entités, analyseur déterministe pour la
conversion monétaire finale) reste l'architecture la plus sûre — exactement
ce que proposait `Communications/instructions.docx` dès le premier document.

## Ce que ces trois protocoles ne mesurent toujours pas

- La compréhension de **phrases réellement inédites** (ces 53 phrases, même
  en aveugle pour le modèle, restent celles du corpus existant).
- Les **conversations à plusieurs tours** (mémoire, corrections, changement
  d'avis en cours de phrase).
- La **compréhension de l'audio réel** (ASR + bruit + hésitations), ces
  trois protocoles ne testant que du texte déjà transcrit sans erreur.
- Un modèle **réellement déployable à coût maîtrisé** : les trois protocoles
  ci-dessus utilisent un LLM généraliste puissant, pas un candidat pour la
  production. Voir `asr_test/results/llm_deploye_vs_corpus_reel.json` (test
  séparé, en cours) pour la comparaison avec un modèle local de petite taille.

## Désaccords à faire trancher par une personne bambaraphone

Voir `asr_test/DESACCORDS_LLM_A_VALIDER.md` pour le détail complet des cas
où le modèle et l'étiquette du corpus ne s'accordent pas, avec les phrases
exactes et les questions à poser à une locutrice native.
