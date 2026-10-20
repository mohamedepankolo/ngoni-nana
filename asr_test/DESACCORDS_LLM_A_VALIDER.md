# Désaccords entre le LLM et l'étiquette du corpus — à faire trancher par une personne bambaraphone

Contexte : test en aveugle d'un LLM généraliste sur les 53 phrases bambara
réelles distinctes du corpus (voir `asr_test/COMPARAISON_LLM_COMPREHENSION.md`
pour le rapport complet). Sur 53 phrases, seules 3 ont donné une intention
différente de l'étiquette du corpus. Conformément à la remarque reçue : ces
désaccords ne doivent **pas** être tranchés par supposition (ni "le LLM a
raison", ni "le corpus a raison") mais vérifiés par une personne compétente en
bambara (Fadima ou une autre locutrice de l'équipe).

Pour chacun, trois explications sont possibles, à distinguer :
1. Une vraie erreur de compréhension du LLM.
2. Une erreur d'étiquetage du corpus (la catégorie assignée ne correspond pas
   au mot réellement prononcé).
3. Une expression réellement ambiguë en bambara (le même verbe peut couvrir
   plusieurs opérations selon le contexte réel, que le texte seul ne donne pas).

**Fait notable, pas une conclusion** : les 3 cas ci-dessous font partie d'une
liste de 8 phrases déjà documentée dans `tests/test_moteur_decision.py`
(`ECHECS_CONNUS_INTENTION`) comme des échecs connus du moteur à règles actuel
— construite il y a plusieurs semaines, pour une raison indépendante de ce
test. Sur ces 8 mêmes phrases, le LLM est tombé d'accord avec l'étiquette du
corpus sur les 5 autres (P09b, P12c, P14c, P16c, P19c), et seulement en
désaccord sur ces 3-là.

## Cas 1

- **ID corpus** : P08b (locutrice L02)
- **Texte bambara** : *n ye si tulu feere kɛmɛ fila ni bi duuru*
- **Sens attendu (corpus)** : « J'ai acheté du beurre de karité pour 1250 francs » — catégorie **achat**
- **Réponse du LLM** : intention **vente** (il a lu le verbe "feere" = vendre, littéralement présent dans la phrase)
- **Montant** : les deux s'accordent sur 1250 F CFA — seule l'intention diffère.
- **Question pour la locutrice** : le mot "feere" a-t-il été dit par erreur à la
  place de "san" (acheter) par cette locutrice, ou ce mot peut-il légitimement
  couvrir les deux sens selon le contexte ?

## Cas 2

- **ID corpus** : P05c (locutrice L03)
- **Texte bambara** : *n ye gban sara tan, kɛmɛ duuru*
- **Sens attendu (corpus)** : « J'ai vendu 10 tas de gombo à 2500 francs » — catégorie **vente**
- **Réponse du LLM** : intention **depense** (il a lu le verbe "sara" = payer/dépenser)
- **Montant** : les deux s'accordent sur 2500 F CFA.
- **Question** : "sara" a-t-il été utilisé ici au sens de "faire payer"
  (donc compatible avec une vente, le vendeur "se faisant payer") plutôt que
  "dépenser" ? C'est une nuance que le LLM n'a pas pu deviner du texte seul.

## Cas 3

- **ID corpus** : P06c (locutrice L03)
- **Texte bambara** : *n ye fini san waa kelen ni kɛmɛ duuru*
- **Sens attendu (corpus)** : « J'ai vendu un pagne à 7500 francs » — catégorie **vente**
- **Réponse du LLM** : intention **depense** (il a lu le verbe "san" = acheter, classé dans sa catégorie la plus proche disponible à ce moment du test)
- **Montant** : les deux s'accordent sur 7500 F CFA.
- **Question** : même question que le cas 1, pour la même locutrice (L03) —
  substitution "san"/"feere" répétée chez cette locutrice en particulier ?

## Cas 4 (second test, schéma à 7 catégories)

- **ID corpus** : P09b (locutrice L02)
- **Texte bambara** : *n ye sɛ duuru feere waa fila ni kɛmɛ duuru*
- **Sens attendu (corpus)** : « J'ai acheté 5 poulets à 12500 francs » — catégorie **achat**
- **Réponse du LLM** : intention **vente** (verbe "feere" littéralement présent)
- **Montant** : les deux s'accordent sur 12500 F CFA.
- Même famille que les cas 1 et 3 : substitution verbale déjà documentée
  (`ECHECS_CONNUS_INTENTION`, moteur à règles).

## Deux cas où "achat" vs "depense" diffère à cause d'un flou du corpus LUI-MÊME

Ce ne sont **pas** des désaccords à faire trancher par une locutrice : ce sont
des cas où `moteur/dictionnaire_mots_cles.py` documente déjà, depuis
plusieurs semaines, que la frontière achat/dépense est floue **dans
l'annotation de référence elle-même** (« l'achat d'emballages est annoté
'depense' »). Le LLM, en lisant le verbe "san" (acheter) littéralement, a
répondu "achat" là où le corpus annote "depense" pour ces deux phrases
précises :

- Phrase 12 (*n ye waa kelen kɛ ka mana foroko san*, "j'ai dépensé 1000 pour
  des emballages") — corpus : depense ; LLM : achat (montant d'accord : 5000).
- Phrase 30 (variante avec "ni bɔrɛw", mêmes emballages + sacs) — corpus :
  depense ; LLM : achat (montant d'accord : 5000).

Cohérent avec ce que le moteur à règles du projet fait déjà (il traite
volontairement tout "achat" comme un cas de "depense", précisément à cause de
cette même frontière floue) — pas une nouvelle découverte, une confirmation.

## Une vraie erreur d'arithmétique trouvée (reproductible, pas un hasard)

Sur la construction numérique **"waa [dizaine] ni [unité]"** (ex. "waa mugan
ni duuru" = 1000 × (20+5) = 25 000 dɔrɔmɛ = 125 000 F CFA), le LLM s'est
trompé **deux fois sur deux**, de façon identique : il a calculé "waa mugan"
(20 000) puis ajouté "duuru" (5) tel quel avant la conversion ×5, obtenant à
tort 100 025 F CFA au lieu de 125 000 F CFA — soit 20 000 dɔrɔmɛ + 5 dɔrɔmɛ
au lieu de 1000 × (20 + 5) dɔrɔmɛ.

- Phrase 20 (*n ye saga saba feere wa mugan ni duuru*) : attendu 125 000,
  obtenu 100 025.
- Phrase 37 (même construction, variante) : même erreur, à l'identique.

C'est une erreur de **calcul**, pas de compréhension : le LLM a correctly
identifié la vente, l'article, la quantité — seule la priorité des opérations
(additionner "mugan ni duuru" AVANT de multiplier par "waa", pas après) a été
mal appliquée. Cette règle n'avait été donnée qu'une seule fois dans la
consigne, via un seul exemple ("kɛmɛ ni bi duuru" = 150, un cas plus simple
sans second niveau d'unité) : il faudrait soit un deuxième exemple couvrant
spécifiquement "unité ni dizaine", soit déléguer cette conversion à un
analyseur déterministe (ce que `montants.py` fait déjà, et fait bien, pour le
moteur actuel) plutôt que de la confier entièrement au LLM.

## Pourquoi cette vérification compte

Si les 3 cas sont de vraies erreurs d'étiquetage du corpus (pas des erreurs du
LLM ni du moteur actuel), alors le taux de compréhension réel du LLM sur ce
corpus serait de 53/53 sur les phrases qui ne sont pas ambiguës dans leur
formulation même. Si au contraire ce sont des locutrices qui confondent
réellement ces verbes à l'oral, cela révèle une ambiguïté linguistique que
**tout** système (règles ou LLM) devra apprendre à gérer par le contexte, pas
par le seul mot prononcé.
