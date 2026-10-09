import csv
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "asr_test" / "scripts"))

from moteur.dictionnaire_mots_cles import reconnaitre_confirmation, reconnaitre_intention  # noqa: E402
from moteur.moteur_decision import Session, analyser, extraire_entites  # noqa: E402

# categorie (phrases_reelles.csv) -> intention du moteur. Le parcours
# utilisateur ne propose que 5 actions au menu (vente, depense, capital,
# client, stock) : "achat" est traité comme un cas de "depense" (voir
# dictionnaire_mots_cles.py). "dette_client" -> "client".
INTENTION_ATTENDUE = {
    "dette_client": "client",
    "vente": "vente",
    "achat": "depense",
    "depense": "depense",
    "capital": "capital",
    "consultation": "consultation",
    "stock": "stock",
}

CORPUS = RACINE / "asr_test" / "corpus" / "phrases_reelles.csv"


def _lire_corpus():
    with open(CORPUS, encoding="utf-8") as f:
        return list(csv.DictReader(f))


# Cas connus et documentés où le dictionnaire de mots-clés se trompe
# actuellement (voir dictionnaire_mots_cles.py) : substitutions de verbe par
# une locutrice précise (ex. "feere" à la place de "san"), ou mot-clé absent
# de cette phrase précise. Ce ne sont pas des bugs à corriger à la main : les
# corriger un par un reviendrait à surapprendre ce corpus de 60 phrases au
# lieu d'écrire des règles générales. Liste explicite pour que toute
# régression ailleurs soit détectée (si ce nombre augmente, quelque chose de
# nouveau a cassé).
ECHECS_CONNUS_INTENTION = {"P08b", "P09b", "P05c", "P06c", "P12c", "P14c", "P16c", "P19c"}


def test_precision_intention_sur_corpus_reel():
    """Taux de reconnaissance d'intention sur les 60 phrases vérifiées (R9).

    Seuil fixé sous le score actuel (87%), pas à 100% : voir
    ECHECS_CONNUS_INTENTION pour la liste des cas restants, tous documentés.
    """
    lignes = _lire_corpus()
    echecs = []
    for ligne in lignes:
        attendu = INTENTION_ATTENDUE[ligne["categorie"]]
        trouve = reconnaitre_intention(ligne["texte_bambara"])
        if trouve != attendu:
            echecs.append(ligne["id"])

    assert set(echecs) == ECHECS_CONNUS_INTENTION, (
        f"Échecs différents de ceux attendus : {sorted(set(echecs) ^ ECHECS_CONNUS_INTENTION)}"
    )
    taux = 1 - len(echecs) / len(lignes)
    assert taux >= 0.85


def test_montant_reconstruit_exactement_sur_corpus_reel():
    """Le montant FCFA calculé par le moteur doit retomber sur montant_fcfa (CSV).

    Valide le facteur de conversion dɔrɔmɛ (FACTEUR_DOROME) posé dans
    moteur_decision.py, sur toutes les lignes où un montant est attendu ET où
    l'intention est reconnue (sinon il n'y a pas de couche 2 à tester ici,
    c'est déjà couvert par le test de précision d'intention ci-dessus).
    """
    lignes = [l for l in _lire_corpus() if l["montant_fcfa"] and l["id"] not in ECHECS_CONNUS_INTENTION]
    assert lignes, "le corpus ne devrait pas être vide"
    for ligne in lignes:
        resultat = analyser(ligne["texte_bambara"])
        assert resultat["champs"].get("montant_fcfa") == int(ligne["montant_fcfa"]), ligne["id"]


@pytest.mark.parametrize("texte, intention_attendue", [
    ("n ye saga saba feere wa bi duuru", "vente"),
    ("n ye n ka paser sara kɛmɛ ni bi duuru", "depense"),
    ("n ka jagokun ye waa tan ye", "capital"),
    ("n ka waa fila juru bɛ Awa la", "client"),
    ("n ye joli feere nin kalo in na", "consultation"),
    ("mɔgɔ jɔnw la ka juru bɛ", "consultation"),
    ("phrase totalement hors sujet sans aucun mot-clé", None),
    # "Sarata"/"Saran" (prénoms maliens courants) commencent comme "sara"
    # (payer) : une phrase qui ne fait que nommer la cliente ne doit pas être
    # prise pour une dépense (voir EXCEPTIONS_NOMS_PROPRES, dictionnaire_mots_cles.py).
    ("Sarata bɛ yan", None),
    ("Saran bɛ yan", None),
])
def test_reconnaitre_intention_cas_simples(texte, intention_attendue):
    assert reconnaitre_intention(texte) == intention_attendue


def test_nom_propre_sarata_ne_declenche_pas_est_un_paiement():
    # Meme collision que ci-dessus, mais dans extraire_entites directement
    # (champ "est_un_paiement", calcule separement du dictionnaire de
    # mots-cles) : nommer la cliente ne doit pas faire croire a un paiement
    # recu alors que la phrase ne fait que declarer une nouvelle dette.
    champs = extraire_entites("Sarata ka juru ye wari kɛmɛ ye", "client")
    assert champs["est_un_paiement"] is False


def test_variante_ne_pour_n_ne_pollue_pas_larticle():
    # ASR RobotsMali, test réel 2026-10-05 : "ne" (variante de "n") a été
    # transcrit à la place de "n" et s'est retrouvé dans l'article extrait
    # ("ne saga" au lieu de "saga") avant d'être ajouté à MOTS_GRAMMATICAUX.
    champs = extraire_entites("ne ye saga saba feere wa bi duuru", "vente")
    assert champs["article"] == "saga"


@pytest.mark.parametrize("texte, attendu", [
    ("owo", True), ("awo", True), ("aawo", True), ("oui", True),
    ("n sɔnna", True), ("awo ne sɔnna", True), ("awa", True),
    ("ayi", False), ("non", False),
    ("n ye saga saba feere", None),
])
def test_reconnaitre_confirmation(texte, attendu):
    # "aawo" : graphie observée en test réel (ASR RobotsMali, 2026-10-05) pour
    # le "oui" bambara, a fait planter une vraie session avant d'être ajoutée.
    # "n sɔnna" : la question posée se termine par "I sɔnna wa ?" ; une
    # locutrice répond naturellement en reprenant ce verbe plutôt que par un
    # "owo" isolé (test réel, 2026-10-09). "awa" : transcription exacte et
    # répétée (3/3) d'un vrai "oui" prononcé par une vraie locutrice, obtenue
    # en rejouant ses enregistrements captés (NGONI_DEBUG_AUDIO, même date).
    assert reconnaitre_confirmation(texte) == attendu


def test_session_rien_enregistre_avant_confirmation_finale():
    """Cas 10 du parcours : aucune écriture tant que confirmer() n'a pas été appelé."""
    session = Session()
    resultat = session.recevoir("n ye saga saba feere wa bi duuru")
    assert resultat["action"] != "enregistrer"
    assert session.confirmee is False

    resultat = session.confirmer()
    assert resultat["action"] == "enregistrer"
    assert session.confirmee is True


def test_session_escalade_apres_deux_reformulations():
    """Cas 7 du parcours : jamais plus de 2 reformulations avant escalade humaine."""
    session = Session()
    for _ in range(2):
        resultat = session.recevoir("bruit incompréhensible")
        assert resultat["action"] == "reformuler"
        assert session.escaladee is False

    resultat = session.recevoir("toujours incompréhensible")
    assert resultat["action"] == "escalade_humaine"
    assert session.escaladee is True

    # Une fois escaladée, la session reste escaladée (ne redemande plus).
    resultat = session.recevoir("n ye saga saba feere wa bi duuru")
    assert resultat["action"] == "escalade_humaine"


def test_session_garde_les_champs_deja_confirmes_entre_les_tours():
    """Les champs reconnus à un tour restent en mémoire aux tours suivants (slot filling progressif).

    Reproduit un échange en 2 tours comme dans le parcours réel : le 2e tour
    ne répète pas le mot-clé "depense", il répond juste à la question posée
    par le système (« quel montant ? ») par un nombre seul.
    """
    session = Session()
    session.recevoir("n ye n ka paser sara")  # poste de dépense, montant pas encore donné
    resultat = session.recevoir("kɛmɛ ni bi duuru")  # le montant arrive seul, dans un 2e tour

    assert resultat["intention"] == "depense"
    assert "paser" in resultat["champs"].get("article", "")
    assert resultat["champs"].get("montant_fcfa") == 150 * 5


def test_session_correction_ne_touche_que_le_champ_signale():
    """Cas 9 du parcours : corriger le montant ne doit pas effacer l'article déjà confirmé."""
    session = Session()
    session.recevoir("n ye saga saba feere wa bi duuru")
    avant = dict(session.champs_confirmes)
    assert "article" in avant

    resultat = session.corriger("montant_fcfa", "waa saba")
    assert resultat["champs"]["article"] == avant["article"]
    assert resultat["champs"]["montant_fcfa"] == 3000 * 5
