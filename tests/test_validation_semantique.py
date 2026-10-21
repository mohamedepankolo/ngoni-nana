"""Tests de sécurité pour le validateur applicatif (asr_test/v2/schema_semantique_v1.json
+ asr_test/scripts/valider_semantique.py). Conformément à la relecture reçue :
vérifie qu'une consultation, une négation, une information historique, une
quantité seule ou une opération ambiguë ne provoque jamais d'écriture
financière incorrecte — en vérifiant que le VALIDATEUR rejette ces cas
avant toute écriture, puisque le composant de compréhension sémantique
lui-même n'est pas encore implémenté (voir ARCHITECTURE_EXPERIMENTALE.md).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "asr_test" / "scripts"))

from valider_semantique import valider  # noqa: E402

BASE_VALIDE = {
    "schema_version": "1.1.0", "domaine": "vente", "operation": "creation",
    "personne": None, "produit": "riz",
    "quantite": {"groupe_id": "N1", "unite": "sac"},
    "groupes_numeriques": [
        {"id": "N1", "texte": "saba", "valeur_dorome": 3, "role": "quantite"},
        {"id": "N2", "texte": "waa mugan ni duuru", "valeur_dorome": 25000, "role": "montant_total"},
    ],
    "montant": {"montant_brut_dorome": 25000, "unite_monetaire": "dorome_implicite", "montant_fcfa": 125000},
    "informations_manquantes": [], "ambiguites": [],
    "effet_comptable_potentiel": "creer_transaction",
    "action_proposee": "demander_confirmation", "confirmation_requise": True,
}


def _variante(**changements):
    out = {k: (v if k not in changements else changements[k]) for k, v in BASE_VALIDE.items()}
    return out


def test_cas_valide_ne_souleve_aucune_erreur():
    assert valider(BASE_VALIDE) == []


def test_consultation_avec_effet_comptable_est_rejetee():
    # Une question ("combien Mariam me doit ?") ne doit jamais produire d'effet comptable.
    mauvais = _variante(domaine="dette_client", operation="consultation",
                         effet_comptable_potentiel="augmenter_creance")
    erreurs = valider(mauvais)
    assert erreurs, "une consultation avec un effet comptable propose doit etre rejetee"


def test_stock_enregistre_comme_montant_est_rejete():
    # Une declaration de stock en sacs ne doit jamais devenir une somme d'argent.
    mauvais = _variante(
        domaine="stock", operation="augmentation", effet_comptable_potentiel="ajuster_stock_plus",
        quantite=None,
        groupes_numeriques=[{"id": "N1", "texte": "naani", "valeur_dorome": 4, "role": "montant_total"}],
    )
    erreurs = valider(mauvais)
    assert any("stock" in e for e in erreurs), "une quantite de stock marquee montant_total doit etre signalee"


def test_reference_a_un_groupe_numerique_inexistant_est_rejetee():
    mauvais = _variante(quantite={"groupe_id": "N99", "unite": "sac"})
    erreurs = valider(mauvais)
    assert any("N99" in e for e in erreurs)


def test_operation_hors_combinaison_valide_est_rejetee():
    # "remboursement" n'a pas de sens pour le domaine stock (voir REFERENTIEL_OPERATIONS_COMPTABLES.md).
    mauvais = _variante(domaine="stock", operation="remboursement")
    erreurs = valider(mauvais)
    assert erreurs


def test_capital_creation_avec_effet_augmentation_est_rejete():
    # capital/creation doit REMPLACER (definir_capital_initial), pas CUMULER (augmenter_capital).
    mauvais = _variante(domaine="capital", operation="creation", produit=None, quantite=None,
                         groupes_numeriques=[{"id": "N1", "texte": "waa tan", "valeur_dorome": 10000, "role": "montant_total"}],
                         effet_comptable_potentiel="augmenter_capital")
    erreurs = valider(mauvais)
    assert erreurs, "capital/creation avec l'effet d'augmentation (cumulatif) doit etre rejete"
