# Référentiel des opérations comptables — domaine × opération → effet

Accompagne `schema_semantique_v1.json`. Définit, pour chaque combinaison
valide de `domaine`/`operation`, l'effet comptable potentiel, les champs
requis, et un exemple. Toute combinaison absente de ce tableau doit être
traitée comme `operation: "inconnue"` par le composant de compréhension
sémantique — jamais déduite par analogie.

## Tableau des combinaisons valides

| Domaine | Opération | Effet comptable potentiel | Champs requis | Champs jamais requis (ne pas demander) |
|---|---|---|---|---|
| vente | creation | `creer_transaction` | montant, produit | personne (souvent absente, ex. vente au comptant) |
| vente | correction | `corriger_transaction_existante` | référence à la transaction visée (hors v1 : pas encore de mécanisme d'identification, voir §3) | — |
| achat | creation | `creer_transaction` | montant, produit | personne |
| achat | correction | `corriger_transaction_existante` | idem vente/correction | — |
| depense | creation | `creer_transaction` | montant | produit, personne (souvent absents, ex. "dépensé 1000 pour l'électricité") |
| depense | correction | `corriger_transaction_existante` | idem | — |
| dette_client | creation | `augmenter_creance` | montant, personne | produit |
| dette_client | remboursement | `diminuer_creance` | montant, personne | produit |
| dette_client | consultation | `aucun` | personne (ou absente si question générique "qui me doit de l'argent ?") | montant (c'est la question) |
| dette_client | correction | `corriger_transaction_existante` | personne, référence à la transaction | — |
| dette_fournisseur | creation | `augmenter_dette_fournisseur` | montant, personne | produit |
| dette_fournisseur | remboursement | `diminuer_dette_fournisseur` | montant, personne | produit |
| dette_fournisseur | consultation | `aucun` | personne | montant |
| dette_fournisseur | correction | `corriger_transaction_existante` | personne, référence à la transaction | — |
| capital | creation | `definir_capital_initial` — **remplace**, voir §2 | montant | — |
| capital | augmentation | `augmenter_capital` — **cumule**, voir §2 | montant | — |
| capital | consultation | `aucun` | — | montant |
| stock | augmentation | `ajuster_stock_plus` | **quantité physique** (sac, kg, pièce...), produit | montant financier (voir §3 — une quantité de stock n'est jamais un montant) |
| stock | diminution | `ajuster_stock_moins` | quantité physique, produit | montant financier |
| stock | consultation | `aucun` | produit (ou absent si "qu'est-ce qu'il me reste en stock ?") | montant |
| consultation | consultation | `aucun` | — (dépend de la question : montant total vendu, dette totale...) | — |

`operation: "inconnue"` (tout domaine) : `effet_comptable_potentiel: null`,
`action_proposee: "demander_operation"`, jamais d'effet proposé.

## 1. Distinctions explicitement demandées par la mission

- **Créance client vs dette fournisseur (ajouté après relecture)** : une
  dette a une **direction**, pas seulement un montant. `dette_client` =
  argent dû À la commerçante (une créance — son remboursement DIMINUE ce
  qu'on lui doit). `dette_fournisseur` = argent dû PAR la commerçante (une
  dette au sens courant — son remboursement DIMINUE ce qu'elle doit, mais
  ce n'est PAS une créance). Scénario qui a révélé l'ambiguïté : **G3**
  (`PROTOCOLE_8_SCENARIOS.md`) — une commerçante rembourse son propre
  fournisseur, direction inverse de G1/G2 (une cliente la rembourse, elle).
  Aucune opération ne doit diminuer `diminuer_creance` quand c'est en fait
  `diminuer_dette_fournisseur`, et réciproquement. **Réserve importante** :
  `dette_fournisseur` n'est pas un cas d'usage confirmé à ce jour — absent
  de `phrases_reelles.csv`, déjà signalé comme tel dans
  `moteur/base_donnees.py:calculer_capital` ("Dettes fournisseurs n'a pas
  encore de table dédiée... à corriger si Fadima confirme ce cas d'usage").
  Le schéma prévoit la distinction ; son utilité réelle reste à confirmer
  par une locutrice avant toute implémentation du calcul de capital
  correspondant.
- **Dette nouvellement créée vs remboursement** : `dette_client/creation`
  augmente la créance (la cliente doit plus) ; `dette_client/remboursement`
  la diminue. Le marqueur linguistique n'est pas toujours le verbe seul —
  "sara" peut signifier payer (dépense) OU rembourser une dette selon le
  contexte (déjà noté dans `DESACCORDS_LLM_A_VALIDER.md`, motif proche du
  cas 2). Distinction à trancher par le contexte conversationnel (une dette
  préexistante connue de ce client augmente la confiance qu'il s'agit d'un
  remboursement), pas par le seul verbe — raison pour laquelle ce
  référentiel ne mappe pas "sara" directement à une opération.
- **Solde actuel vs état historique** : `capital/consultation` et
  `stock/consultation` interrogent l'état **actuel** (après tous les
  mouvements), jamais une transaction isolée. Le composant sémantique ne
  doit jamais confondre "le capital est maintenant de 50 000" (créer un
  état initial, `capital/creation`) avec "le capital a augmenté de 50 000"
  (`capital/augmentation`) — la phrase P15 du corpus
  (*"n ka jagokun ye waa tan ye"*) est actuellement annotée comme
  `capital` sans préciser l'opération ; **cette distinction n'existe pas
  encore dans l'annotation actuelle et devra être clarifiée au protocole 8**.
- **Question vs instruction d'enregistrement** : toute `operation:
  "consultation"` a `effet_comptable_potentiel: "aucun"` par construction
  — un système qui propose un effet comptable sur une question est un bug,
  pas une ambiguïté (devrait être détectable par un test automatisé, voir
  `evaluer_metriques.py`, métrique "taux de fausses confirmations").

## 2. Précédent déjà résolu par le moteur V1 en production

`capital/creation` vs `capital/augmentation` existe déjà dans
`moteur/base_donnees.py` : `declarer_capital_initial` **remplace** la valeur
("mon capital de départ est de X", redéclarer écrase la précédente) tandis
qu'`ajouter_au_capital` **cumule** ("j'ajoute X à mon capital", chaque ajout
s'additionne). Le schéma V2 doit reprendre exactement cette distinction
(`capital/creation` → remplace, `capital/augmentation` → cumule) pour rester
cohérent avec le moteur à règles déjà en production — pas une question
ouverte, un précédent à respecter.

## 3. Stock : quantité physique vs montant financier (ajouté après relecture)

Une phrase de stock (`stock/augmentation`, `stock/diminution`) porte sur une
**quantité physique** (sacs, kilogrammes, pièces...), jamais sur un montant
en F CFA — contrairement à `vente`/`achat`/`depense` où le nombre pertinent
est presque toujours un montant. Le groupe numérique associé doit porter le
rôle `quantite`, jamais `montant_total`. `valider_semantique.py`
(`valider_stock_quantite_vs_montant`) signale toute sortie où un domaine
`stock` n'a aucun groupe `quantite` alors qu'un groupe `montant_total` est
présent — signe que le système a confondu "il me reste 4 sacs" avec "il me
reste 4 francs". Testé explicitement dans
`tests/test_validation_semantique.py`.

## 4. Ce que ce référentiel ne couvre pas encore

- Le mécanisme d'identification d'une transaction existante pour
  `operation: "correction"` (quelle transaction corriger ? par date ? par
  description ? par confirmation orale du montant précédent ?) — explicitement
  hors scope de ce référentiel, à spécifier séparément avant tout test
  impliquant des corrections.
- Les opérations impliquant plusieurs domaines dans une même phrase (ex.
  "j'ai vendu à crédit" = vente + dette simultanément) — absentes du corpus
  actuel, à couvrir dans les scénarios du protocole 8.
