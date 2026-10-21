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

## Protocole 5 — modèles 7-9B déjà présents localement (Ollama, gratuit, zéro téléchargement)

Suite au protocole 4 (petit modèle 1,5 milliard de paramètres, échec total), question
restée ouverte : un modèle local **de taille intermédiaire** (7-9B, toujours gratuit
et déployable sans API payante) ferait-il mieux ? Trois modèles déjà présents sur la
machine de développement via Ollama ont été testés sur les 2 mêmes phrases de contrôle
que le protocole 4, avec le glossaire complet du protocole 1 :

| Modèle | Phrase 1 (3 moutons, 250 000 F CFA attendu) | Phrase 2 (capital 50 000 F CFA attendu) |
|---|---|---|
| `llama3:8b` | quantité 30 (faux), montant 750 F CFA (faux) | intention correcte, montant 5 000 (faux) |
| `mistral:7b` | quantité 3 (correct), montant 75 F CFA (faux) | intention **fausse** ("consultation") |
| `gemma2:9b` | **timeout à 180 s, aucune réponse** | non testé |

Aucun des trois ne calcule le montant correctement. Un second essai avec un prompt
**few-shot** (3 exemples entièrement résolus ajoutés à la consigne, montrant
explicitement le calcul doromee→F CFA et la multiplication par "waa") a été fait sur
`mistral:7b` et `llama3:8b` :

| Modèle | Phrase 1 | Phrase 2 |
|---|---|---|
| `mistral:7b` | produit et quantité désormais corrects, montant toujours faux (250 F CFA au lieu de 250 000 — facteur ×1000 manquant) | intention désormais correcte, montant faux (100 000 au lieu de 50 000, ×2) |
| `llama3:8b` | produit et quantité corrects, montant toujours faux (750 F CFA au lieu de 250 000) | intention correcte, montant faux (25 000 au lieu de 50 000, ×2 — valeur qui correspond exactement à l'exemple fourni dans le prompt, signe d'un recopiage de l'exemple plutôt que d'un recalcul) |

**Découverte notable en creusant l'échec de la phrase 1** : le corpus réel contient deux
orthographes du même mot pour le même sens (confirmé dans
`asr_test/corpus/phrases_reelles.csv`) — "n ye saga saba feere **wa** bi duuru" (P02) et
"n ye saga saba feere **waa** bi duuru" (P02b), prononcées par des locutrices
différentes mais toutes deux annotées pour le même montant (250 000 F CFA). Le grand
LLM des protocoles 1-3 a géré cette variance orthographique sans erreur (100 %/96 % de
montants exacts, toutes variantes confondues) ; les modèles locaux 7-9B échouent
spécifiquement sur la forme courte "wa", qu'ils ne relient pas de façon fiable à la
règle "waa=1000" du glossaire.

**Conclusion du protocole 5** : le few-shot améliore l'extraction du produit, de la
quantité et de l'intention, mais ne corrige pas l'arithmétique — les erreurs
restantes sont idiosyncratiques (facteur manquant, valeur recopiée d'un exemple,
sensibilité à l'orthographe) plutôt qu'un bug unique et corrigeable comme celui trouvé
au protocole 2. Les modèles 7-9B génériques gratuits testés ici ne sont, à ce stade,
pas fiables pour cette tâche précise, few-shot ou non.

## Protocole 6 — architecture hybride : LLM extrait le texte brut, `montants.py` calcule

Suite à l'échec du protocole 5 (même avec une règle grammaticale précise et
validée, few-shot ou non), changement de design plutôt que de prompt :
au lieu de demander au LLM de **calculer** le montant, on lui demande de
**recopier mot pour mot** l'expression chiffrée prononcée (champ
`expression_montant`), sans aucun calcul de sa part. Un système séparé — le
`montants.py` déterministe déjà en place, validé contre le référentiel
(`REFERENTIEL_NOMBRES_BAMBARA_A_VALIDER.md`) — fait ensuite le calcul réel
(nombre → ×5 → F CFA).

Testé sur `mistral:7b` (le plus petit/moins cher des modèles locaux
essayés), sur 4 phrases incluant le cas central qui avait fait échouer tous
les protocoles précédents :

| Phrase | Expression extraite par le LLM | Calcul `montants.py` | Attendu | Résultat |
|---|---|---|---|---|
| "...feere wa bi duuru" | "wa bi duuru" | 250 000 | 250 000 | **Exact** |
| "...jagokun ye waa tan ye" | "waa tan" | 50 000 | 50 000 | **Exact** |
| "...feere waa mugan ni duuru" (cas central) | "waa mugan ni duuru" | 125 000 | 125 000 | **Exact** |
| "...san waa kelen ni kɛmɛ duuru" | "kɛmɛ duuru" (incomplet — a classé "waa kelen" comme quantité) | 2 500 | 7 500 | Faux |

**3 montants exacts sur 4**, y compris le cas le plus difficile de toute
cette série de tests — contre 0/2 à 0/4 pour toutes les tentatives
précédentes avec ce même modèle (protocoles 5, prompt simple et few-shot).
Le seul échec restant est une erreur de **segmentation** (confondre quel
groupe de mots est la quantité vs le montant, quand la phrase ne contient
pas de comptage d'articles séparé) — pas une erreur de calcul. L'intention
reste parfois fausse elle aussi (phrase 2 classée "consultation" au lieu de
"capital"), un problème indépendant du montant.

**Ce résultat à 4 phrases ne s'est PAS généralisé — voir la correction
ci-dessous.**

### Correction : évaluation sur les 53 phrases du corpus (script `evaluer_hybride.py`)

Script reçu, vérifié (mode `--smoke` : reproduit bien exactement 3/4 à partir
des réponses déjà enregistrées, avant toute nouvelle inférence), puis exécuté
pour de vrai sur les 53 phrases distinctes avec `mistral:7b`.

| Mesure | Résultat |
|---|---|
| Montants FCFA exacts | **6 / 45 — 13 %** |

**Le 3/4 (75 %) du test à 4 phrases ne tenait pas à l'échelle : c'était un
échantillon chanceux, pas une vraie amélioration.** En creusant le détail des
échecs, trois bugs systématiques, distincts de l'arithmétique :

1. **Régurgitation littérale de l'exemple du prompt système.** Pour 4
   phrases différentes (P03, P06, P12, P15), le modèle a répondu exactement
   `"waa kelen ni kɛmɛ duuru"` — l'exemple donné dans la consigne elle-même
   (*"«waa kelen ni kɛmɛ duuru» est un seul montant"*) — alors qu'aucune de
   ces phrases ne contient ce texte. Un essai en retirant cet exemple du
   prompt système n'a cependant pas résolu le problème dans l'ensemble (voir
   point 4).
2. **Troncature au dernier mot.** Pour au moins 6 phrases, le modèle a
   répondu seulement "duuru" (dernier mot d'un groupe numéral) au lieu de
   l'expression complète ("wa bi duuru"), produisant un montant 10 000 fois
   trop petit.
3. **Mauvais token sélectionné.** Pour les phrases de dette (P13, P13b,
   *"n ka waa fila juru bɛ Awa la"*), le modèle a recopié le mot "juru"
   (= dette) lui-même comme si c'était le montant, au lieu du nombre qui le
   précède.
4. **Un nouvel essai ciblé** sur les 10 phrases en échec, avec le prompt
   système débarrassé de l'exemple littéral, n'a corrigé qu'1 cas sur 10 —
   confirmant que le problème n'est pas la formulation du prompt mais une
   limite réelle de `mistral:7b` à isoler des groupes numéraux multi-mots de
   façon fiable sur des phrases variées.

**Conclusion révisée du protocole 6** : l'idée de séparer "extraire le texte"
(LLM) de "calculer" (`montants.py`, déjà validé) reste architecturalement la
bonne direction — le seul échec de calcul observé sur l'ensemble du corpus
vient d'une mauvaise extraction en amont, jamais d'une erreur de
`montants.py` lui-même. Mais `mistral:7b` n'est, à ce stade, pas assez fiable
pour cette étape d'extraction à l'échelle d'un corpus varié (13 %, pas
75 %). La leçon méthodologique à retenir : **ne jamais juger un protocole sur
un échantillon de 2-4 phrases** — exactement l'erreur commise ici avant
cette correction. Reste à tester si un modèle plus capable (payant, ou un
modèle local plus gros type `gemma2:9b` si sa lenteur peut être réglée) fait
mieux sur cette même étape d'extraction, désormais isolée du calcul.

## Protocole 7 — segmentation déterministe + LLM qui attribue un rôle (Variante B)

Proposition reçue suite à la correction du protocole 6 : au lieu de demander
au LLM de repérer lui-même les frontières du nombre dans le texte (ce qui
causait troncature et régurgitation), un segmenteur déterministe isole
d'abord tous les groupes numériques complets (texte + valeur), et le LLM
n'a plus qu'à décider lequel est la quantité et lequel est le montant.

**Implémentation** : `montants.extraire_groupes()` (nouvelle fonction,
réutilise la logique déjà validée de `_nombre`/`_terme` contre le
référentiel) renvoie des groupes complets avec leur texte d'origine et leur
valeur — jamais un mot isolé au milieu d'un groupe plus long. Testé :
élimine directement les deux bugs du protocole 6 (plus de troncature possible
puisque le LLM ne voit plus la phrase brute à segmenter ; "juru"=dette
n'apparaît plus comme groupe candidat puisqu'il n'est pas un numéral).

Script `evaluer_segmente.py`, testé en mode `--smoke` puis exécuté pour de
vrai sur les 53 phrases avec `mistral:7b` — **le même modèle qui n'obtenait
que 13 % au protocole 6** :

| Mesure | Résultat |
|---|---|
| Montants FCFA exacts (brut, sans règle de repli) | **41 / 45 — 91 %** |
| Montants FCFA exacts (avec règle de repli, voir ci-dessous) | **45 / 45 — 100 %** |

Les 4 échecs restants partageaient un point commun exact : une seule phrase
à un seul groupe numérique (dette ou dépense sans comptage d'articles,
ex. *"Fanta ye kɛmɛ wolonwula sara, n ka juru la"*), que le modèle étiquette
à tort "quantité" au lieu de "montant".

**Correction importante (après relecture) : la règle de repli initiale était
un surajustement dangereux, retirée.** Une première version forçait
automatiquement le rôle "montant" dès qu'un seul groupe numérique existait
et que l'intention n'était pas "stock" — corrige les 4 cas ci-dessus, mais
une phrase absente de ce corpus comme *"j'ai vendu trois sacs de riz"*
(quantité seule, prix non mentionné) aurait été lue comme un montant de
15 F CFA inventé. Remplacée par un **signalement d'ambiguïté** plutôt qu'une
décision automatique, conformément à l'exigence "0 transaction inventée" :
le système doit demander une précision, pas deviner silencieusement quand un
seul nombre est présent et qu'aucun rôle n'a été donné explicitement par le
LLM.

| Mesure (règle sûre, sans forçage automatique) | Résultat |
|---|---|
| Montants FCFA exacts | **41 / 45 — 91 %** |
| Signalés "ambigu, à clarifier" (pas une erreur silencieuse) | 4 / 45 |

**Conclusion du protocole 7 sur les montants** : en retirant au LLM la seule
tâche où il échouait réellement (délimiter les frontières d'un nombre
multi-mots), et en ne lui laissant que des décisions qu'il sait déjà bien
prendre (quel groupe joue quel rôle), le même petit modèle local gratuit
passe de 13 % à 91 % sur l'ensemble du corpus, le reste étant signalé pour
clarification plutôt que faux.

### Mais l'intention reste un problème non résolu — 49 % seulement

Le focus sur les montants a masqué un problème aussi important : sur les
mêmes 53 phrases, l'intention retournée par le LLM ne correspond à la
catégorie du corpus que **26/53 fois (49 %)** — bien pire que les
protocoles 1-2 (94 %/85 %). Deux échecs systématiques, pas aléatoires :

- **"capital" → "vente" à chaque fois (5/5)**, y compris pour
  *"n ka jagokun ye waa tan ye"* (mon capital est de...), malgré "jagokun=capital"
  explicitement donné dans la consigne.
- **"consultation" → "inconnu" à chaque fois (5/5)**, pour toutes les
  phrases avec "joli"/"jɔn" (combien/qui).

Un enregistrement avec le bon montant mais la mauvaise catégorie comptable
(ex. une dette de Mariam enregistrée comme une vente) est une erreur aussi
grave qu'un montant faux pour un assistant comptable.

**Test ciblé** : un prompt dédié, uniquement à la classification d'intention
(sans les groupes numériques ni l'attribution de rôle), testé séparément sur
les 53 phrases — hypothèse qu'isoler cette tâche (comme suggéré) corrige les
deux échecs systématiques ci-dessus.

| Mesure | Combiné (groupes + rôles + intention) | Intention seule (prompt dédié) |
|---|---|---|
| Intention exacte | 49 % (26/53) | **66 % (35/53)** |

**Séparer la tâche aide réellement** (+17 points) : le problème
"capital → vente à chaque fois" est quasiment résolu (4/5 corrigés — seul
*"n ye wa naani fara'o kan"* reste faux). Mais "consultation" reste fragile
(encore 3/5 faux, avec des réponses différentes à chaque fois plutôt que le
même "inconnu" systématique d'avant). Les erreurs restantes recoupent
largement une ambiguïté **déjà documentée aux protocoles 1-2** : confusion
achat/vente par substitution du verbe littéralement prononcé (ex. "feere"
lu comme vente quand le corpus attend achat) et confusion achat/dépense
(frontière déjà floue dans l'annotation de référence elle-même, voir
`DESACCORDS_LLM_A_VALIDER.md`) — pas un problème entièrement nouveau.

**Vérification méthodologique (avant de conclure)** : les 18 désaccords ont
été croisés avec ce qui est déjà documenté — `ECHECS_CONNUS_INTENTION` (8 cas,
moteur à règles) et le flou achat/dépense du corpus (2 cas) — avant d'être
traités comme des erreurs du LLM. Détail complet dans
`DESACCORDS_LLM_A_VALIDER.md`. **10 des 18 désaccords ne sont pas de
nouvelles erreurs.** Score ajusté : **45/53 = 85 %**, bien plus proche des
94 %/85 % du grand LLM que le 66 % brut ne le suggérait.

Il reste 8 vrais nouveaux désaccords, regroupés en 3 motifs précis (détail et
phrases exactes dans `DESACCORDS_LLM_A_VALIDER.md`) :
- **4 cas** : déclaration monétaire sans verbe ("X francs sont chez Y"),
  ambiguë entre vente et dette_client — à faire trancher par une locutrice,
  pas évident que ce soit une erreur du LLM plutôt qu'une vraie ambiguïté.
- **3 cas** : le marqueur interrogatif (joli/jɔn) n'est pas priorisé face à
  un mot-thème présent dans la même phrase (feere/tora/juru) — ressemble à
  une vraie limite de compréhension, pas une ambiguïté de la phrase.
- **1 cas** : faux positif lexical ("san"=acheter lu à l'intérieur du mot
  "sanɲɔgɔn", sans rapport).

**Conclusion sur l'intention** : séparer les tâches est la bonne direction,
et l'écart réel avec le grand LLM est plus restreint que le 66 % brut ne le
suggérait (85 % ajusté). Le problème le plus clairement attribuable à
`mistral:7b` lui-même, pas à une ambiguïté du corpus, est la gestion des
questions (motif B) — une piste de correction plus ciblée que "le modèle ne
comprend pas le bambara".

**Un modèle local plus gros ne fait pas mieux.** `mistral-tdr-biais:latest`
(déjà présent sur la machine) écarté après vérification : c'est un
fine-tune pour détecter des biais dans des appels d'offres publics
burkinabè, sans rapport avec le bambara ou la comptabilité. `gemma2:9b`
(9 milliards de paramètres, plus gros que `mistral:7b`) testé sur la même
tâche d'intention seule : **45 % brut, 64 % ajusté — moins bien que
`mistral:7b` sur les deux mesures**, malgré une taille supérieure. Confirme
qu'il ne s'agit pas simplement d'une question de taille de modèle :
`mistral:7b` reste le meilleur candidat local gratuit testé à ce jour.

**Conclusion générale du protocole 7, révisée** : l'architecture
"segmentation déterministe + LLM pour les rôles" résout bien le problème des
montants (13 %→91 %, sans invention grâce au signalement d'ambiguïté). Mais
la compréhension de l'opération comptable elle-même (quelle catégorie)
reste, à ce stade, le problème non résolu le plus important — un système qui
calcule juste mais classe mal n'est pas encore fiable.

**Réserves à garder en tête avant de généraliser** : corpus de 53 phrases
existantes (pas encore de phrases inédites, pas de conversations à plusieurs
tours) ; les cas à plusieurs groupes numériques plus complexes (prix
unitaire + total + quantité dans une même phrase) n'ont pas encore été
rencontrés dans ce corpus et restent à tester ; ne pas réévaluer la règle de
repli sur ce même corpus comme preuve de généralisation — c'est lui qui l'a
fait naître.

## Synthèse des sept protocoles

| | P1 (glossaire complet) | P2 (glossaire + lecture stricte) | P3 (sans glossaire) | P4 (petit modèle local 1,5B) | P5 (modèles locaux 7-9B, calcul demandé au LLM) | P6 (modèle local 7B, calcul délégué à `montants.py`) |
|---|---|---|---|---|---|---|
| | P1 | P2 | P3 | P4 | P5 | P6 | P7 (segmentation + rôle) |
|---|---|---|---|---|---|---|---|
| Intentions | 94 % | 85 %* | élevé, non chiffré | 1/2, structure non suivie | 2-3/4 essais | non chiffrée | 66 % brut, **85 % ajusté** (après exclusion des désaccords déjà connus) |
| Montants | **100 %** | 96 % | **7 %** | **0 %, invention** | **0 %** | **13 % (6/45)** | **91 % (41/45), 4 signalées ambiguës plutôt que devinées** |

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

Les protocoles 4 et 5 ont d'abord ajouté une réserve de taille : aucun modèle
gratuit et déployable localement (1,5B au protocole 4, trois modèles 7-9B au
protocole 5, few-shot et règle précise inclus) ne réussissait à calculer un
montant correctement. Le protocole 6 confirme la bonne direction architecturale
(séparer extraction et calcul) mais, une fois testé sur les 53 phrases et pas
seulement 4, montre que `mistral:7b` reste insuffisant même pour la seule
tâche d'extraction (13 %, voir correction ci-dessus) : un gain existe (6/45
contre 0 dans les protocoles précédents), mais il est loin de suffire pour un
déploiement.

**Conclusion actuelle, mise à jour par le protocole 7** : l'architecture
hybride proposée dès `Communications/instructions.docx` (LLM pour
l'intention/les entités, analyseur déterministe pour les montants) était la
bonne direction, mais le protocole 6 avait encore laissé au LLM une tâche où
il échouait (délimiter lui-même les frontières du nombre). Une fois cette
tâche retirée — la segmentation numérique faite en amont par `montants.py`,
le LLM se limitant à attribuer un rôle à des groupes déjà délimités — le même
petit modèle local gratuit (`mistral:7b`) atteint 100 % sur l'ensemble du
corpus. La leçon méthodologique du protocole 6 (ne jamais juger sur un
échantillon de 2-4 phrases) reste valable et a été appliquée ici : le
protocole 7 a été évalué sur les 53 phrases dès le départ, pas sur un
échantillon.

## Ce que ces six protocoles ne mesurent toujours pas

- La compréhension de **phrases réellement inédites** (ces 53 phrases, même
  en aveugle pour le modèle, restent celles du corpus existant).
- Les **conversations à plusieurs tours** (mémoire, corrections, changement
  d'avis en cours de phrase).
- La **compréhension de l'audio réel** (ASR + bruit + hésitations), ces
  six protocoles ne testant que du texte déjà transcrit sans erreur.
- La **segmentation quantité/montant** sur l'architecture hybride du
  protocole 6, testée sur seulement 4 phrases : reste à chiffrer sur les 53
  phrases du corpus, voire sur des phrases inédites.
- La **robustesse de l'intention** une fois le calcul délégué : le protocole
  6 montre encore des erreurs (jagokun/capital mal classé) indépendantes du
  problème de montant, non encore quantifiées sur l'ensemble du corpus.

## Désaccords à faire trancher par une personne bambaraphone

Voir `asr_test/DESACCORDS_LLM_A_VALIDER.md` pour le détail complet des cas
où le modèle et l'étiquette du corpus ne s'accordent pas, avec les phrases
exactes et les questions à poser à une locutrice native.
