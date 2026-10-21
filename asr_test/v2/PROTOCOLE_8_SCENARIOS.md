# Protocole 8 — scénarios à faire reformuler en bambara (corpus indépendant)

**Règle absolue : aucune phrase bambara n'est inventée ici.** Chaque ligne
ci-dessous est une description en français d'une situation comptable. Elle
doit être **reformulée naturellement en bambara** par Fadima ou une autre
locutrice compétente — pas traduite mot à mot. Une même situation peut
donner plusieurs formulations différentes (c'est même souhaitable : ça
teste la robustesse aux variantes, pas la mémorisation d'une phrase).

Ce corpus est **indépendant** des 53 phrases existantes
(`asr_test/corpus/phrases_reelles.csv`) : il ne doit **jamais** servir à
ajuster un prompt ou un modèle. Un score mesuré dessus mesure la
généralisation réelle ; un score sur l'ancien corpus ne la mesure plus
(les prompts ont déjà été affinés dessus, protocoles 5-7).

## Comment utiliser ce document

1. Fadima (ou une autre locutrice) lit la situation en français.
2. Elle dit ou écrit comment elle-même, ou une commerçante qu'elle connaît,
   formulerait ça naturellement en bambara — spontanément, pas en traduisant.
3. La formulation est transcrite dans `gabarit_annotation_protocole8.csv`
   (une ligne par formulation), avec son `scenario_id` d'origine.
4. Les champs "attendu" du gabarit (domaine, opération, montant...) sont
   ceux que la commerçante elle-même confirmerait comme corrects pour SA
   formulation — pas une déduction faite a posteriori par l'équipe technique.

## A. Montant manquant (le système doit demander, pas deviner)

- **A1.** Une commerçante dit qu'elle a vendu trois sacs de riz, sans dire
  combien elle les a vendus.
- **A2.** Une commerçante dit qu'elle a dépensé de l'argent pour du
  transport, sans préciser le montant.
- **A3.** Une commerçante dit qu'elle doit de l'argent à son fournisseur,
  sans préciser combien.

## B. Quantité seule, sans montant (distinct de A — ici il n'y a même pas de prix à chercher, juste un état)

- **B1.** Une commerçante dit combien de sacs de mil il lui reste en stock,
  sans mentionner de prix.
- **B2.** Une commerçante dit combien de pagnes elle a reçus d'un
  fournisseur, sans préciser leur prix (juste une livraison, pas encore une
  transaction financière).

## C. Prix unitaire explicite (distinct du montant total)

- **C1.** Une commerçante dit qu'elle a vendu trois sacs à un prix donné
  **par sac** (elle précise "chacun" ou équivalent), sans donner le total.
- **C2.** Une commerçante dit qu'elle a acheté cinq poulets à un prix par
  poulet, puis donne aussi le total qu'elle a payé (les deux montants sont
  mentionnés : prix unitaire ET total — le système doit les distinguer, pas
  les confondre).

## D. Plusieurs montants dans la même phrase (risque explicitement signalé par l'avisor)

- **D1.** Une commerçante dit qu'elle a vendu des sacs à un prix unitaire,
  pour un total donné, à une cliente qui lui doit encore une partie de la
  somme (trois montants différents : prix unitaire, total, reste dû).
- **D2.** Une commerçante dit le prix d'achat et le prix de revente du même
  article dans la même phrase (ex. "j'ai acheté à X et revendu à Y").

## E. Corrections (la commerçante se reprend en cours de phrase ou après coup)

- **E1.** Une commerçante commence à donner un montant puis se corrige pour
  un montant différent, dans la même phrase ("en fait non, c'est plutôt...").
- **E2.** Une commerçante confirme d'abord une transaction, puis revient
  dessus dans l'échange suivant pour dire qu'elle s'est trompée de produit.
- **E3.** Une commerçante dit qu'elle s'est trompée de personne (ce n'est
  pas Mariam qui lui doit cet argent, mais quelqu'un d'autre).

## F. Négations (distinct d'une simple absence d'information)

- **F1.** Une commerçante dit qu'elle n'a **pas** encore été payée pour une
  vente (donc une dette, pas une vente encaissée).
- **F2.** Une commerçante dit qu'elle n'a **pas** de dette envers telle
  personne, en réponse à une question du système (nie une supposition,
  distinct de "je ne sais pas").

## G. Remboursements (distinction centrale de la mission : dette créée vs diminuée)

- **G1.** Une cliente rembourse une partie de ce qu'elle doit (la dette
  diminue, mais n'est pas soldée).
- **G2.** Une cliente rembourse la totalité de sa dette (la dette tombe à
  zéro).
- **G3.** Une commerçante rembourse elle-même une dette qu'elle doit à un
  fournisseur (le sens du remboursement est inversé par rapport à G1/G2 —
  teste si le système confond "je rembourse" et "on me rembourse").

## H. Consultations (question, jamais un enregistrement)

- **H1.** Une commerçante demande combien telle cliente lui doit au total.
- **H2.** Une commerçante demande combien elle a vendu ce mois-ci (pas une
  nouvelle vente — bien distinguer de la déclaration d'une vente).
- **H3.** Une commerçante demande quel est son capital actuel.
- **H4.** Une commerçante demande ce qu'il lui reste en stock pour un
  article donné.

## I. Conversations à plusieurs tours (pas des phrases isolées)

- **I1.** Le système demande le montant manquant (scénario A1) ; la
  commerçante répond au tour suivant avec juste le chiffre, sans répéter le
  contexte ("c'est 15 000" par exemple, sans redire "j'ai vendu...").
- **I2.** Le système demande une confirmation ; la commerçante répond par
  une correction partielle plutôt que oui/non (ex. corrige juste le
  montant, confirme implicitement le reste).
- **I3.** La commerçante enchaîne spontanément une deuxième opération sans
  qu'on le lui demande, juste après avoir confirmé la première (ex. "et
  aussi, j'ai acheté...").
- **I4.** La commerçante répond à une question de clarification par une
  autre question (ne répond pas directement, demande une précision en
  retour) — teste si le système boucle correctement sans se tromper de
  champ à remplir.

## Légende du gabarit d'annotation (`gabarit_annotation_protocole8.csv`)

Vocabulaire de statut repris de `REFERENTIEL_NOMBRES_BAMBARA_A_VALIDER.md`
pour rester cohérent dans tout le dépôt (`a_valider`/`validee`/`variante`/
`rejetee` sont les équivalents machine-friendly de "À vérifier"/"Validée"/
"Variante"/"Rejetée").

| Colonne | Signification |
|---|---|
| `id` | Identifiant unique de la ligne (ex. P8-A1-001) |
| `scenario_id` | Renvoie à la section de ce document (ex. "A1") |
| `locuteur_id` | Identifiant anonymisé de la locutrice (ex. L04, L05 — nouveaux identifiants, distincts de L01-L03 du corpus existant) |
| `texte_bambara` | La formulation telle que dite/écrite par la locutrice — jamais pré-remplie par l'équipe technique |
| `sens_fr` | Reformulation française de ce qu'elle vient de dire, pour audit humain |
| `domaine_attendu` / `operation_attendue` | Valeurs du schéma `schema_semantique_v1.json` que LA LOCUTRICE elle-même confirme, pas une déduction technique |
| `ambiguite_attendue` | "non", ou une description courte de l'ambiguïté volontaire du scénario (ex. "oui - montant manquant") |
| `statut_validation` | `a_valider` par défaut ; passe à `validee` seulement après relecture explicite |

## Ce que ce document ne couvre pas encore

- Scénarios multi-domaines dans une seule phrase (ex. vente à crédit = vente
  + dette simultanément) — à ajouter si les scénarios ci-dessus révèlent que
  c'est une situation fréquente en pratique, pas ajouté par anticipation.
- Le nombre de locutrices (3 dans le corpus actuel) reste une limite même
  pour ce nouveau corpus si les mêmes personnes le reformulent — à signaler
  explicitement si c'est le cas, pour que l'analyse en tienne compte.
