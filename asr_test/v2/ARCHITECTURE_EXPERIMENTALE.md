# Architecture expérimentale — hypothèse à éprouver, pas une conclusion

## Hypothèse principale

```
Transcription bambara
  → segmentation numérique déterministe (montants.extraire_groupes)
  → compréhension sémantique (LLM, sortie conforme à schema_semantique_v1.json)
  → attribution des rôles aux groupes numériques (quantité / montant / prix unitaire / autre)
  → validation monétaire et métier (calcul déterministe + référentiel d'opérations)
  → gestionnaire de dialogue (ambiguïtés, informations manquantes)
  → confirmation explicite
  → écriture comptable
```

**C'est une hypothèse à éprouver, pas une architecture jugée optimale.**
Elle découle des protocoles 6-7, qui ont montré que :
- un LLM local gratuit (`mistral:7b`) échoue à délimiter lui-même les
  nombres dans le texte (13 % → voir `COMPARAISON_LLM_COMPREHENSION.md`,
  protocole 6), mais réussit bien mieux (91 %) une fois cette étape faite en
  amont par un composant déterministe (protocole 7) ;
- la compréhension sémantique (quelle intention, quelle opération) reste
  imparfaite même isolée du calcul (66 %/85 % ajusté) et n'a encore jamais
  été mesurée au niveau de granularité que la mission demande (opération
  précise, pas seulement domaine).

Ce que le protocole 8 doit vérifier, sans le supposer acquis : que cette
architecture (plutôt que, par exemple, un seul appel LLM structuré sans
segmentation préalable, ou l'inverse — segmentation ET rôles confiés au
même appel) reste la meilleure sur un corpus **indépendant**.

## Garde-fous non négociables (contraintes de la mission, pas des choix d'implémentation)

1. **Le LLM ne calcule jamais le montant final.** Il propose un rôle pour
   chaque groupe numérique déjà extrait par `montants.extraire_groupes()` ;
   le calcul (×5 si dɔrɔmɛ implicite) est fait par le système, jamais par le
   modèle. Vérifiable directement dans `schema_semantique_v1.json` : le
   champ `montant` n'existe qu'après validation, distinct de
   `groupes_numeriques[].valeur_dorome` (donnée brute, déterministe).
2. **Le LLM ne modifie jamais directement la base comptable.** Il propose
   `effet_comptable_potentiel` ; l'écriture réelle reste un acte séparé,
   après confirmation explicite de l'utilisatrice — inchangé par rapport au
   moteur V1 déjà en production (`moteur/agent_vocal.py`, confirmation
   systématique avant `_conclure`).
3. **Un groupe numérique ambigu entraîne une clarification, jamais une
   interprétation imposée.** Déjà appliqué dans `evaluer_segmente.py`
   (commit `3002580`, suite à la correction d'un surajustement dangereux) :
   `role: "ambigu"` ou `confirmation_requise: true` plutôt qu'un rôle deviné
   silencieusement. `evaluer_metriques.py` mesure explicitement les faux
   négatifs sur ce point (métrique 7b, la plus grave des 9).

## Composants déjà construits (réutilisables, pas à refaire)

| Composant | Fichier | État |
|---|---|---|
| Segmentation numérique déterministe | `asr_test/scripts/montants.py` (`extraire_groupes`) | Validé contre `REFERENTIEL_NOMBRES_BAMBARA_A_VALIDER.md`, testé (`tests/test_montants.py`) |
| Schéma de sortie sémantique versionné | `asr_test/v2/schema_semantique_v1.json` | **V1.1.0** (voir historique de version dans le fichier), validé syntaxiquement (JSON Schema draft 2020-12), règles métier domaine/opération encodées (`allOf`/`if`/`then`), + exemples positifs/négatifs testés |
| Référentiel domaine/opération → effet | `asr_test/v2/REFERENTIEL_OPERATIONS_COMPTABLES.md` | Cohérent avec le moteur V1 en production (capital creation=remplace/augmentation=cumule) ; distingue désormais créance client et dette fournisseur (direction) ; distingue stock (quantité physique) de montant financier |
| Validateur applicatif (complète le JSON Schema) | `asr_test/scripts/valider_semantique.py` | Vérifie les références de groupes numériques et la cohérence stock/quantité — non exprimables en JSON Schema seul. Testé (`tests/test_validation_semantique.py`, 6 cas de sécurité) |
| Évaluateur à 9+ métriques | `asr_test/scripts/evaluer_metriques.py` | Inclut désormais la vérification de l'effet comptable, des montants multiples, et la conformité au schéma/référentiel via `valider_semantique`. Code vérifié (`--smoke`, 3 cas synthétiques, 6 assertions) ; **pas encore exécuté sur de vraies données**, le corpus protocole 8 n'existe pas encore |
| Scénarios pour un corpus indépendant | `asr_test/v2/PROTOCOLE_8_SCENARIOS.md` + gabarit CSV | 25 scénarios en français (10 familles), gabarit enrichi (direction du mouvement financier, montants multiples, conversation/tour, provenance). Formulations bambara à recueillir, aucune n'existe encore |

**Règle méthodologique pour toute évaluation future (ajoutée après relecture)** :
séparer strictement par locutrice lors de l'évaluation — ne jamais répartir
les variantes d'une même locutrice entre ajustement de prompt et mesure de
performance, pour éviter une fuite d'information (risque déjà identifié sur
le corpus existant, où les variantes a/b/c sont les 3 mêmes locutrices
redites, voir `AUDIT_PROTOCOLES_1_A_7.md` §2).

## Ce qui n'est PAS encore construit

- Le composant de compréhension sémantique lui-même produisant une sortie
  conforme à `schema_semantique_v1.json` (actuellement, `evaluer_segmente.py`
  et `evaluer_intention_seule.py` produisent des sorties plus simples, pas
  encore le schéma complet domaine+opération+groupes+effet).
- Le corpus protocole 8 (dépend de Fadima/locutrices).
- Toute mesure réelle avec `evaluer_metriques.py` sur des données non
  synthétiques.
- L'intégration au gestionnaire de dialogue existant (`moteur/agent_vocal.py`)
  — explicitement hors scope tant que l'architecture n'est pas validée
  (consigne reçue : "ne pas changer la logique de production avant
  validation du nouveau comportement").
