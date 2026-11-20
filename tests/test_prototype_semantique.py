"""Tests du prototype isolé (asr_test/scripts/prototype_semantique_v1.py),
sans appel réseau — _appeler_llm est remplacé par une réponse fabriquée.

Couvre les deux corrections demandées après le premier test réel :
A. Un champ signalé "manquant" par le LLM mais jamais requis pour ce
   domaine/opération (ex. produit/personne pour capital/creation) ne doit
   plus bloquer l'effet comptable attendu.
B. Une sortie rejetée par le validateur doit systématiquement retomber sur
   un état sûr (effet nul, confirmation requise, action = clarification),
   jamais être traitée comme corrigée automatiquement.
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "asr_test" / "scripts"))

import prototype_semantique_v1 as proto  # noqa: E402


def test_capital_creation_produit_personne_non_requis_ne_bloque_pas_leffet():
    # Reproduit exactement le cas trouve lors du premier test reel :
    # "n ka jagokun ye waa tan ye" (capital), LLM signale produit+personne
    # manquants a tort.
    phrase = "n ka jagokun ye waa tan ye"
    groupes = proto.extraire_groupes(phrase)
    reponse_llm = {
        "domaine": "capital", "operation": "creation", "personne": None, "produit": None,
        "roles": {"N1": "montant_total"},
        "informations_manquantes": ["personne", "produit"], "ambiguites": [],
    }
    sortie = proto._construire_sortie(phrase, groupes, reponse_llm)
    assert sortie["informations_manquantes"] == [], (
        "personne/produit ne sont jamais requis pour capital/creation, "
        "ne doivent pas apparaitre dans informations_manquantes"
    )
    assert sortie["effet_comptable_potentiel"] == "definir_capital_initial"
    assert sortie["montant"]["montant_fcfa"] == 50000
    assert proto.valider(sortie) == []


def test_vente_sans_montant_reste_bloquee_a_juste_titre():
    # Contre-exemple : un champ REELLEMENT requis (montant pour une vente)
    # doit continuer a bloquer l'effet, le filtrage ne doit pas tout laisser
    # passer.
    phrase = "n ye saga saba feere"  # pas de groupe de montant dans cette phrase
    groupes = proto.extraire_groupes(phrase)
    reponse_llm = {
        "domaine": "vente", "operation": "creation", "personne": None, "produit": "saga",
        "roles": {"N1": "quantite"} if groupes else {},
        "informations_manquantes": ["montant"], "ambiguites": [],
    }
    sortie = proto._construire_sortie(phrase, groupes, reponse_llm)
    assert sortie["informations_manquantes"] == ["montant"]
    assert sortie["effet_comptable_potentiel"] == "aucun"
    assert sortie["confirmation_requise"] is True


def test_sortie_rejetee_retombe_sur_un_etat_sur():
    # B. Simule une reponse LLM invalide (operation hors combinaison
    # autorisee pour dette_client) et verifie l'etat apres rejet.
    phrase = "n ka waa fila juru bɛ Awa la"
    groupes = proto.extraire_groupes(phrase)
    reponse_llm_invalide = {
        "domaine": "dette_client", "operation": "augmentation",  # invalide pour dette_client
        "personne": "Awa", "produit": None, "roles": {"N1": "montant_total"},
        "informations_manquantes": [], "ambiguites": [],
    }
    with patch.object(proto, "_appeler_llm", return_value=reponse_llm_invalide):
        resultat = proto.analyser(phrase)

    assert resultat["statut"] == "rejete_par_validateur"
    assert resultat["erreurs_validation"], "le rejet doit etre journalise dans erreurs_validation"
    sortie = resultat["sortie"]
    assert sortie["effet_comptable_potentiel"] == "aucun", "aucun effet ne doit jamais s'appliquer apres un rejet"
    assert sortie["confirmation_requise"] is True
    assert sortie["action_proposee"] == "demander_confirmation"
    # La sortie brute (avant securisation) reste accessible pour le journal/audit.
    assert "sortie_brute" in resultat


def test_sortie_valide_a_le_statut_valide():
    phrase = "n ye saga saba feere waa mugan ni duuru"
    groupes = proto.extraire_groupes(phrase)
    reponse_llm = {
        "domaine": "vente", "operation": "creation", "personne": None, "produit": "saga",
        "roles": {"N1": "quantite", "N2": "montant_total"},
        "informations_manquantes": [], "ambiguites": [],
    }
    with patch.object(proto, "_appeler_llm", return_value=reponse_llm):
        resultat = proto.analyser(phrase)
    assert resultat["statut"] == "valide"
    assert resultat["erreurs_validation"] == []
    assert "sortie_brute" not in resultat
