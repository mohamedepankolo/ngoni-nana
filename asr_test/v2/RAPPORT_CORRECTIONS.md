# Rapport de correction — relecture de la branche `v2-audit-protocole8`

Pour chaque anomalie relevée : décision retenue, fichiers modifiés, tests
associés, questions métier encore ouvertes. Aucun composant de production
n'a été modifié. Tous les résultats expérimentaux précédents (protocoles
1-7) sont conservés tels quels.

## A. Score d'intention ajusté à 85 % — terminologie corrigée

**Anomalie** : "exclusion de 10 désaccords" aurait dû donner un dénominateur
de 43, pas 53 — incohérence mathématique dans la présentation (pas dans le
calcul lui-même, qui était correct pour ce qu'il faisait réellement).

**Décision** : le calcul était en fait une **reclassification** (dénominateur
inchangé à 53), pas une exclusion. Présenter désormais les deux lectures
possibles séparément : 45/53 = 84,9 % (reclassification) et 35/43 = 81,4 %
(exclusion stricte). Aucune des deux n'est présentée comme une borne
garantie tant que les 8 désaccords "vraiment nouveaux" ne sont pas arbitrés
par une locutrice.

**Fichiers modifiés** : `asr_test/v2/AUDIT_PROTOCOLES_1_A_7.md` (§1.1, nouvelle
section de correction), `asr_test/COMPARAISON_LLM_COMPREHENSION.md`,
`asr_test/DESACCORDS_LLM_A_VALIDER.md`.

**Tests** : aucun (correction de présentation, pas de code).

**Question ouverte** : les 8 désaccords "vraiment nouveaux" (motifs A/B/C,
`DESACCORDS_LLM_A_VALIDER.md`) restent à faire trancher par Fadima ou une
autre locutrice — la fourchette honnête reste 66 %-85 % jusque-là.

## B. Effet comptable du capital initial

**Anomalie** : le référentiel indiquait `capital/creation → aucun` dans le
tableau, puis précisait ailleurs que cette opération devait remplacer le
capital initial — contradiction interne.

**Décision** : ajout d'un effet explicite `definir_capital_initial`
(remplace), distinct d'`augmenter_capital` (cumule) — reprend exactement la
distinction déjà implémentée dans `moteur/base_donnees.py`
(`declarer_capital_initial` vs `ajouter_au_capital`), pas une nouvelle règle
inventée.

**Fichiers modifiés** : `asr_test/v2/schema_semantique_v1.json` (nouvel enum,
règle `allOf` liant `capital/creation` à cet effet, version → 1.1.0),
`asr_test/v2/REFERENTIEL_OPERATIONS_COMPTABLES.md` (tableau + §2 corrigés).

**Tests** : `tests/test_validation_semantique.py::test_capital_creation_avec_effet_augmentation_est_rejete`.

**Question ouverte** : aucune — résolu par le précédent déjà en production.

## C. Créances clients vs dettes fournisseurs

**Anomalie** : le référentiel ne distinguait pas la direction d'une dette ;
le scénario G3 (remboursement d'un fournisseur PAR la commerçante) aurait
été mal mappé sur `diminuer_creance` (qui suppose l'inverse).

**Décision** : `domaine: "dette"` remplacé par deux valeurs distinctes,
`dette_client` (créance) et `dette_fournisseur` (dette), avec effets
séparés (`augmenter_creance`/`diminuer_creance` vs
`augmenter_dette_fournisseur`/`diminuer_dette_fournisseur`). Conserve la
convention déjà utilisée dans `phrases_reelles.csv` (catégorie
`dette_client`, jamais `dette` générique).

**Fichiers modifiés** : `schema_semantique_v1.json` (enum domaine, règles
`allOf`), `REFERENTIEL_OPERATIONS_COMPTABLES.md` (§1, tableau), nouveaux
scénarios J1/J2 dans `PROTOCOLE_8_SCENARIOS.md`.

**Tests** : couvert indirectement par les règles `allOf` du schéma
(vérifiées par script lors du développement) ; pas de test pytest dédié à
cette distinction précise — **limite reconnue**, à ajouter si `evaluer_metriques.py`
est exécuté sur des scénarios J1/J2 réels.

**Question ouverte, explicitement non tranchée** : `dette_fournisseur` est
un cas d'usage **non confirmé** à ce jour — absent de `phrases_reelles.csv`,
déjà signalé comme un trou connu dans `moteur/base_donnees.py:183`
("Dettes fournisseurs... à corriger si Fadima confirme ce cas d'usage"). Le
schéma prévoit la capacité, son utilité réelle reste à valider par une
locutrice avant toute implémentation du calcul de capital correspondant.

## D. Stock : quantité physique vs montant financier

**Anomalie** : rien n'empêchait, structurellement, qu'une déclaration de
stock (en sacs/kg) soit confondue avec un montant financier.

**Décision** : ajout d'une règle de validation applicative
(`valider_stock_quantite_vs_montant`) signalant toute sortie où
`domaine="stock"` n'a aucun groupe numérique de rôle `quantite` alors qu'un
groupe `montant_total` est présent.

**Fichiers modifiés** : `asr_test/scripts/valider_semantique.py` (nouveau),
`REFERENTIEL_OPERATIONS_COMPTABLES.md` (§3, nouvelle section), `schema_semantique_v1.json`
(descriptions des champs `quantite.unite` et `groupes_numeriques[].role`).

**Tests** : `tests/test_validation_semantique.py::test_stock_enregistre_comme_montant_est_rejete`.

**Question ouverte** : aucune pour le principe ; la couverture réelle sur
des phrases de stock variées reste à mesurer une fois le composant
sémantique implémenté.

## E. Validations métier du JSON Schema insuffisantes

**Anomalie** : le schéma acceptait des références de groupes numériques
inexistants, des combinaisons domaine/opération non autorisées, et un effet
comptable incohérent avec l'opération.

**Décision** : 
1. Ajout de règles `allOf`/`if`/`then` dans le JSON Schema pour les
   combinaisons domaine/opération valides et la cohérence consultation/effet
   — vérifiable en JSON Schema pur.
2. Ajout d'un validateur applicatif séparé (`valider_semantique.py`) pour ce
   qui ne l'est pas (référence de groupe_id existant) — comme recommandé,
   "certaines vérifications nécessiteront un validateur applicatif".
3. Version du schéma incrémentée à **1.1.0** (changement structurel,
   conformément à la règle de versionnage déjà présente dans le fichier).

**Fichiers modifiés** : `schema_semantique_v1.json`, nouveau
`valider_semantique.py`.

**Tests** : validation positive + 3 cas négatifs testés en ligne de commande
lors du développement (consultation+effet, capital creation+mauvais effet,
stock+opération invalide) ; `tests/test_validation_semantique.py` (6 tests,
dont référence de groupe inexistante et combinaison domaine/opération
invalide).

**Question ouverte** : aucune pour les règles ajoutées ; d'autres règles
métier pourraient apparaître une fois le protocole 8 exécuté sur de vraies
données — ce validateur est voué à grossir, pas figé.

## F. Gabarit d'annotation incomplet

**Anomalie** : le gabarit ne gérait pas les montants multiples, l'effet
comptable attendu, ni les conversations à plusieurs tours ; les scénarios
suggéraient parfois une formulation précise plutôt que de décrire
uniquement la situation.

**Décision** : gabarit enrichi avec `conversation_id`, `tour_id`,
`sens_mouvement_financier`, `montants_multiples_attendus` (JSON),
`effet_comptable_attendu`, `notes_locutrice`, `date_validation`. Scénarios
D2/E1/I1 reformulés pour décrire la situation sans suggérer la formulation
exacte (retrait des exemples de phrases françaises entre guillemets).
Ajout des familles J (dette fournisseur) et K (domaines combinés), et d'un
"bilan de couverture" explicite (25 scénarios, 10 familles, pas présenté
comme un corpus figé).

**Fichiers modifiés** : `asr_test/v2/gabarit_annotation_protocole8.csv`,
`asr_test/v2/PROTOCOLE_8_SCENARIOS.md`.

**Tests** : le gabarit enrichi parse correctement (vérifié : 4 lignes,
colonne JSON `montants_multiples_attendus` valide).

**Question ouverte** : le format `montants_multiples_attendus` (JSON dans
une cellule CSV) est fonctionnel mais pourrait gêner une locutrice qui
remplit le fichier à la main — à revoir une fois la collecte réelle commencée,
si ça s'avère peu pratique.

## G. Tests de sécurité absents

**Anomalie** : rien ne garantissait qu'une consultation, une quantité de
stock, ou une référence incohérente ne produirait jamais d'écriture
financière incorrecte — demandé explicitement en relecture.

**Décision** : nouveau fichier de tests dédié, 6 cas couvrant : cas valide
(témoin), consultation + effet comptable proposé, stock enregistré comme
montant, référence à un groupe numérique inexistant, combinaison
domaine/opération invalide, confusion capital creation/augmentation.

**Fichiers modifiés** : `tests/test_validation_semantique.py` (nouveau).

**Tests** : lui-même — 6/6 passent, intégré à la suite complète (152 tests
au total, aucune régression sur les 146 existants).

**Question ouverte** : les cas de négation et d'information historique
mentionnés en relecture ne sont pas encore testables ici — ils dépendent du
composant de compréhension sémantique lui-même (pas encore implémenté),
pas seulement du validateur. À couvrir une fois ce composant construit.

## H. Cohérence référentiel / schéma / évaluateur

**Décision** : `evaluer_metriques.py` appelle désormais
`valider_semantique.valider()` sur chaque sortie modèle
(`conforme_au_schema`), et compare l'effet comptable obtenu à l'effet
attendu du gabarit (`effet_comptable_correct`) plutôt que de l'ignorer.
Empêche toute dérive silencieuse entre les trois documents.

**Fichiers modifiés** : `asr_test/scripts/evaluer_metriques.py`.

**Tests** : smoke test étendu (6 assertions, dont la conformité schéma des
3 cas synthétiques).

## Récapitulatif des fichiers touchés

| Fichier | Nature du changement |
|---|---|
| `asr_test/v2/schema_semantique_v1.json` | v1.0.0 → v1.1.0 : dette_client/fournisseur, definir_capital_initial, règles allOf |
| `asr_test/v2/REFERENTIEL_OPERATIONS_COMPTABLES.md` | Corrections B, C, D |
| `asr_test/v2/AUDIT_PROTOCOLES_1_A_7.md` | Correction A (§1.1 ajouté) |
| `asr_test/v2/PROTOCOLE_8_SCENARIOS.md` | Scénarios J/K ajoutés, reformulations moins prescriptives, bilan de couverture |
| `asr_test/v2/gabarit_annotation_protocole8.csv` | Colonnes enrichies (F) |
| `asr_test/v2/ARCHITECTURE_EXPERIMENTALE.md` | Composants mis à jour, règle de séparation par locutrice |
| `asr_test/scripts/valider_semantique.py` | Nouveau (D, E) |
| `asr_test/scripts/evaluer_metriques.py` | Métriques étendues (H) |
| `tests/test_validation_semantique.py` | Nouveau (G) |
| `asr_test/COMPARAISON_LLM_COMPREHENSION.md`, `asr_test/DESACCORDS_LLM_A_VALIDER.md` | Correction A propagée |

152 tests passent (146 existants + 6 nouveaux), aucune régression. Aucun
fichier de `moteur/` modifié.
