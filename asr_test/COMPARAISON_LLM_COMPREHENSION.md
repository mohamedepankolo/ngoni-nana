# Évaluation d'un LLM généraliste sur le bambara écrit (N'GONI NANA V2)

Contexte : suite à `Communications/instructions.docx`, qui recommandait de
tester un LLM sur le bambara écrit avant toute décision d'architecture et
avant d'ajouter la complexité de l'audio. Quatre protocoles testés sur les 53
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

## Protocole 4 — petit modèle réellement déployable (Qwen2.5-1.5B-Instruct, local, gratuit)

Les modèles 7B+ (Qwen2.5-7B, Llama-3.1-8B, Qwen3-8B) accessibles via le
routeur d'inférence Hugging Face demandent des crédits payants que ce compte
n'a pas (`"You have no remaining credits"`) — une donnée réelle sur le coût
d'exploitation, pas un simple obstacle technique. Testé à la place un modèle
assez petit pour tourner localement sans frais : Qwen2.5-1.5B-Instruct, avec
exactement le même glossaire complet que le protocole 1.

Avant de lancer les 53 phrases (chaque inférence prenant ~100-115 s sur le
CPU de cette machine, soit ~1h30 pour l'ensemble), un essai sur 2 phrases a
suffi à conclure :

- *"n ye saga saba feere wa bi duuru"* (vendu 3 moutons pour 250 000 F CFA)
  → réponse : produit **"bananes"** (inventé, aucun rapport avec la phrase),
  quantité 30 (au lieu de 3), montant 750 F CFA (au lieu de 250 000).
- *"n ka jagokun ye waa tan ye"* (mon capital est de 50 000) → intention
  correcte, mais montant jamais extrait (null), et le modèle a listé des
  particules grammaticales ("n", "ka") comme des "informations manquantes"
  - signe qu'il ne suit pas la structure de la tâche, pas seulement qu'il
  se trompe sur les chiffres.

Décision prise avec l'utilisateur : ne pas lancer les 53 phrases. Deux échecs
aussi nets (un produit inventé de toutes pièces) suffisent à conclure qu'un
modèle de cette taille (1,5 milliard de paramètres) n'est pas assez capable
pour cette tâche, glossaire ou pas - continuer aurait coûté ~1h30 de calcul
pour confirmer l'évident. Fichier de test conservé
(`asr_test/scripts/tester_llm_deploye.py`) pour un modèle de taille
intermédiaire si cette piste est reprise plus tard.

**C'est le résultat le plus préoccupant des quatre protocoles**, pas
seulement le plus mauvais : inventer un produit absent de la phrase est
exactement le risque que les critères de qualité proposés interdisent ("0
transaction inventée"). Un modèle "petit et gratuit" n'est, à ce stade,
clairement pas une option : soit un modèle intermédiaire reste à tester
(7B via une API payante, ou un 3B local, non essayé faute de preuve que ça
changerait la conclusion), soit la voie "petit modèle local" est à écarter
au profit d'un LLM nettement plus capable, avec le coût que cela implique.

## Synthèse des quatre protocoles

| | P1 (glossaire complet) | P2 (glossaire + lecture stricte) | P3 (sans glossaire) | P4 (petit modèle local) |
|---|---|---|---|---|
| Intentions | 94 % | 85 %* | élevé, non chiffré précisément | correcte sur 1/2, structure non suivie |
| Montants | **100 %** | 96 % | **7 %** | **0 %, avec invention de contenu** |

*la baisse ne traduit pas une régression de compréhension (voir ci-dessus).

**Conclusion directe** : un LLM généraliste **puissant** a une vraie
connaissance préalable du vocabulaire et de la grammaire bambara de ce
domaine (confirmé par le protocole 3), mais **aucune** connaissance de la
convention monétaire locale (dɔrɔmɛ) — celle-ci doit être fournie
explicitement, par un glossaire en contexte (ce qui fonctionne : 100 % et
96 % dans les protocoles 1-2) et/ou par un analyseur déterministe dédié,
comme le fait déjà `montants.py` pour le moteur actuel. Combiner les deux
(LLM guidé pour l'intention/les entités, analyseur déterministe pour la
conversion monétaire finale) reste l'architecture la plus sûre — exactement
ce que proposait `Communications/instructions.docx` dès le premier document.

Mais le protocole 4 ajoute une réserve de taille : cette conclusion ne vaut
que pour un modèle **puissant**. Un modèle réellement gratuit et déployable
localement (1,5 milliard de paramètres) échoue totalement à la même tâche,
glossaire fourni ou non, et invente du contenu plutôt que de signaler une
incertitude. La décision d'architecture ne peut donc pas encore être prise :
il manque la preuve qu'un modèle à la fois capable ET réellement abordable
existe entre ces deux extrêmes.

## Ce que ces quatre protocoles ne mesurent toujours pas

- La compréhension de **phrases réellement inédites** (ces 53 phrases, même
  en aveugle pour le modèle, restent celles du corpus existant).
- Les **conversations à plusieurs tours** (mémoire, corrections, changement
  d'avis en cours de phrase).
- La **compréhension de l'audio réel** (ASR + bruit + hésitations), ces
  quatre protocoles ne testant que du texte déjà transcrit sans erreur.
- Un modèle **de taille intermédiaire** entre un LLM généraliste puissant
  (protocoles 1-3) et un modèle local de 1,5 milliard de paramètres
  (protocole 4, qui échoue totalement) : ni testé, ni écarté à ce jour.

## Désaccords à faire trancher par une personne bambaraphone

Voir `asr_test/DESACCORDS_LLM_A_VALIDER.md` pour le détail complet des cas
où le modèle et l'étiquette du corpus ne s'accordent pas, avec les phrases
exactes et les questions à poser à une locutrice native.
