import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "asr_test" / "scripts"))

from moteur import base_donnees as db  # noqa: E402
from moteur.agent_vocal import AgentVocal  # noqa: E402


@pytest.fixture
def agent():
    """Une base SQLite en mémoire, partagée entre toutes les sessions SQLAlchemy du test
    (StaticPool + une seule connexion), avec une utilisatrice de test déjà créée.
    """
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = db.get_session_factory(engine)

    bd = SessionLocal()
    coop = db.Cooperative(nom="ABIC Dioïla", site="Dioïla")
    bd.add(coop)
    bd.commit()
    utilisatrice = db.Utilisatrice(code_anonyme="L01", telephone_hash="x", cooperative_id=coop.id)
    bd.add(utilisatrice)
    bd.commit()
    bd.refresh(utilisatrice)

    a = AgentVocal(session_factory=SessionLocal)
    a.utilisatrice_id = utilisatrice.id  # commodité pour les tests, pas utilisé par AgentVocal lui-même
    return a


def test_parcours_vente_complet_jusqu_a_l_enregistrement(agent):
    """Cas 2 du parcours : vente, confirmation, écriture, capital mis à jour."""
    sid = agent.demarrer_session(agent.utilisatrice_id)

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "n ye saga saba feere wa bi duuru")
    assert r["contrat"]["action"] == "demander_confirmation"
    assert r["contrat"]["confiance"] == "haute"
    assert "?" in r["message"]

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "owo")  # "oui"
    assert r["contrat"]["action"] == "enregistrer"
    assert "sɛbɛnna" in r["message"]  # "c'est enregistré", en bambara (messages_bambara.py)

    bd = agent._session_factory()
    transactions = bd.query(db.Transaction).filter_by(utilisatrice_id=agent.utilisatrice_id).all()
    assert len(transactions) == 1
    assert transactions[0].montant_fcfa == 250_000

    capital = db.calculer_capital(bd, agent.utilisatrice_id)
    assert capital == 250_000

    session_bd = bd.get(db.SessionAppel, sid)
    assert session_bd.statut == "complete"


def test_oui_apres_enregistrement_relance_sans_redemander_un_montant(agent):
    """Après "veux-tu faire autre chose ?", répondre "oui" doit juste rendre

    la session prête pour une nouvelle action - pas redemander un montant au
    hasard (bug réel, test téléphone 2026-10-09 : répondre à cette question
    finissait par relancer une demande de vente incomplète sans aucun sens).
    """
    sid = agent.demarrer_session(agent.utilisatrice_id)
    agent.traiter_texte(sid, agent.utilisatrice_id, "n ye saga saba feere wa bi duuru")
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "owo")
    assert r["contrat"]["action"] == "enregistrer"
    assert "wa?" in r["message"] or "wa ?" in r["message"]  # "veux-tu faire autre chose ?" toujours inclus

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "owo")  # "oui, autre chose"
    assert r["contrat"]["action"] == "continuer_session"
    assert "lamɛnna" in r["message"]  # "j'écoute", pas une question de montant

    # Une nouvelle vente, juste après, doit repartir de zéro (pas de champs
    # de la vente précédente qui traîneraient).
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "n ye misi feere wa bi duuru")
    assert r["contrat"]["action"] == "demander_confirmation"
    assert r["contrat"]["champs"]["article"] == "misi"


def test_non_apres_enregistrement_dit_au_revoir(agent):
    sid = agent.demarrer_session(agent.utilisatrice_id)
    agent.traiter_texte(sid, agent.utilisatrice_id, "n ye saga saba feere wa bi duuru")
    agent.traiter_texte(sid, agent.utilisatrice_id, "owo")

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "ayi")  # "non, rien d'autre"
    assert r["contrat"]["action"] == "fin_session"
    assert "ce" in r["message"] or "bɛn" in r["message"]  # message de salutation/fin


def test_bruit_asr_pendant_la_confirmation_ne_corrompt_pas_larticle(agent):
    """Régression réelle (2026-10-09) : une utilisatrice confirme "oui" plusieurs

    fois de suite et entend toujours "la même question". Cause : un mot bruit
    de l'ASR (ni "oui" ni "non" reconnu, voir reconnaitre_confirmation) était
    traité comme une correction directe de l'article (cas 9), l'écrasant
    silencieusement avec du bruit et redemandant confirmation avec le nouveau
    (faux) article - d'où l'impression de boucle infinie, et un risque réel
    d'enregistrer la mauvaise marchandise si l'utilisatrice finit par dire un
    "oui" reconnu. Seul un nombre explicitement redit doit valoir correction
    directe (cas 9) ; un mot isolé sans chiffre doit juste redemander oui/non,
    sans toucher aux champs déjà confirmés.
    """
    sid = agent.demarrer_session(agent.utilisatrice_id)
    agent.traiter_texte(sid, agent.utilisatrice_id, "n ye saga saba feere wa bi duuru")

    # "wo" : ni oui/non reconnu, ni mot-clé, ni nombre - un mot de bruit plausible.
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "wo")
    assert r["contrat"]["action"] == "demander_confirmation"
    assert r["contrat"]["champs"]["article"] == "saga"  # inchangé, pas "wo"
    assert "saga" in r["message"]

    # Confirmer pour de vrai doit encore marcher, avec les bonnes valeurs d'origine.
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "owo")
    assert r["contrat"]["action"] == "enregistrer"
    bd = agent._session_factory()
    transactions = bd.query(db.Transaction).filter_by(utilisatrice_id=agent.utilisatrice_id).all()
    assert len(transactions) == 1
    assert transactions[0].article == "saga"
    assert transactions[0].montant_fcfa == 250_000


def test_bruit_repete_pendant_la_confirmation_finit_par_escalader(agent):
    # Sans escalade, du bruit ASR repete indefiniment ferait boucler
    # l'utilisatrice sans fin (c'est exactement le symptome rapporte).
    sid = agent.demarrer_session(agent.utilisatrice_id)
    agent.traiter_texte(sid, agent.utilisatrice_id, "n ye saga saba feere wa bi duuru")

    for _ in range(2):
        r = agent.traiter_texte(sid, agent.utilisatrice_id, "wo")
        assert r["contrat"]["action"] == "demander_confirmation"
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "wo")
    assert r["contrat"]["action"] == "escalade_humaine"


def test_redire_un_montant_sans_dire_non_corrige_quand_meme(agent):
    """Cas 9 : l'utilisatrice redit directement un nombre sans dire "non" d'abord."""
    sid = agent.demarrer_session(agent.utilisatrice_id)
    agent.traiter_texte(sid, agent.utilisatrice_id, "n ye saga saba feere wa bi duuru")

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "waa bi duuru")  # un nouveau montant, redit directement
    assert r["contrat"]["action"] == "demander_confirmation"
    assert r["contrat"]["confiance"] == "haute"


def test_bruit_avec_un_chiffre_fortuit_ne_passe_pas_pour_une_redite(agent):
    """Régression réelle (2026-10-09, test téléphone) : "hamaden fila don"

    contient "fila" (2, un chiffre valide) mais "hamaden" et "don" ne sont
    reconnus ni comme mot-clé ni comme nombre. Accepté à tort comme redite
    du cas 9, ça écrasait l'article déjà confirmé ("saga") avec "hamaden",
    produisant une confirmation absurde. Un énoncé qui contient aussi du
    texte non reconnu ne doit jamais valoir comme redite numérique fiable.
    """
    sid = agent.demarrer_session(agent.utilisatrice_id)
    agent.traiter_texte(sid, agent.utilisatrice_id, "n ye saga saba feere wa bi duuru")

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "hamaden fila don")
    assert r["contrat"]["action"] == "demander_confirmation"
    assert r["contrat"]["champs"]["article"] == "saga"  # inchangé, pas "hamaden"
    assert r["contrat"]["champs"]["montant_fcfa"] == 250_000  # inchangé


def test_rien_n_est_ecrit_si_lutilisatrice_dit_non(agent):
    sid = agent.demarrer_session(agent.utilisatrice_id)
    agent.traiter_texte(sid, agent.utilisatrice_id, "n ye saga saba feere wa bi duuru")
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "ayi")  # "non"

    assert r["contrat"]["action"] != "enregistrer"
    bd = agent._session_factory()
    assert bd.query(db.Transaction).count() == 0


def test_dire_non_puis_redonner_la_valeur_corrige_et_enregistre(agent):
    """Régression réelle (2026-10-09) : dire "non" faisait répéter la même

    question de confirmation en boucle (perçue comme sans fin, jamais
    d'escalade) parce que le message après "non" était un "je n'ai pas
    compris" générique, poussant à tout répéter depuis le début plutôt qu'à
    corriger juste le champ visé. Maintenant, "non" cible un champ précis
    (ici l'article, dernier champ confirmé) et attend UNIQUEMENT sa
    correction, pas une phrase entière.
    """
    sid = agent.demarrer_session(agent.utilisatrice_id)
    agent.traiter_texte(sid, agent.utilisatrice_id, "n ye saga saba feere wa bi duuru")

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "ayi")  # "non"
    assert r["contrat"]["action"] == "demander_confirmation"
    assert "article" not in r["contrat"]["champs"]  # retiré, en attente d'être redonné

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "misi")  # juste le nouvel article, rien d'autre
    assert r["contrat"]["champs"]["article"] == "misi"
    assert r["contrat"]["champs"]["montant_fcfa"] == 250_000  # inchangé

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "owo")
    assert r["contrat"]["action"] == "enregistrer"
    bd = agent._session_factory()
    transactions = bd.query(db.Transaction).filter_by(utilisatrice_id=agent.utilisatrice_id).all()
    assert len(transactions) == 1
    assert transactions[0].article == "misi"


def test_champ_numerique_jamais_rempli_finit_par_escalader(agent):
    # Sans ça, un champ attendu (ici la quantité) jamais correctement rempli
    # pouvait rester en attente indéfiniment. Un mot sans chiffre ne doit
    # jamais combler un champ numérique (voir Session.combler_champ) ; au
    # bout de MAX_REFORMULATIONS échecs, on escalade plutôt que de boucler.
    sid = agent.demarrer_session(agent.utilisatrice_id)
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "n ye saga saba feere")  # quantite manquante
    assert r["contrat"]["action"] == "demander_confirmation"
    assert r["contrat"]["confiance"] == "a_confirmer"

    for _ in range(2):
        r = agent.traiter_texte(sid, agent.utilisatrice_id, "bruit")  # aucun chiffre : ne comble pas
        assert r["contrat"]["action"] == "reformuler"
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "bruit")
    assert r["contrat"]["action"] == "escalade_humaine"


def test_non_repete_sur_un_article_mal_rempli_finit_par_escalader(agent):
    """Un champ libre (article) est rempli par N'IMPORTE quel mot restant,

    même du bruit (rien à vérifier comme un chiffre pour un montant) : dire
    "non" en boucle sur un article jamais correctement compris ne faisait
    donc jamais progresser Session.tentatives_reformulation (chaque
    remplissage "réussissait" mécaniquement), et ne pouvait jamais escalader
    (bug réel, 2026-10-09). Compteur dédié (refus_consecutifs) indépendant.
    """
    sid = agent.demarrer_session(agent.utilisatrice_id)
    agent.traiter_texte(sid, agent.utilisatrice_id, "n ye saga saba feere wa bi duuru")

    for _ in range(2):
        r = agent.traiter_texte(sid, agent.utilisatrice_id, "ayi")  # "non" -> cible l'article
        assert r["contrat"]["action"] == "demander_confirmation"
        r = agent.traiter_texte(sid, agent.utilisatrice_id, "bruit")  # "remplit" l'article avec du bruit
        assert r["contrat"]["action"] == "demander_confirmation"
        assert r["contrat"]["confiance"] == "haute"

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "ayi")  # 3e "non" : doit escalader
    assert r["contrat"]["action"] == "escalade_humaine"


def test_montant_seul_manquant_est_cible_sans_redire_toute_la_phrase(agent):
    """Régression réelle (2026-10-09) : le système redemandait toujours "le

    montant" même quand c'était la quantité qui manquait, et redonner
    uniquement le montant ne suffisait jamais sans aussi redonner l'article
    et la quantité dans la même phrase.
    """
    sid = agent.demarrer_session(agent.utilisatrice_id)
    # Un seul nombre dans la phrase ("saba"=3) : pris comme montant par
    # l'heuristique generale, donc "quantite" manque reellement.
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "n ye saga saba feere")
    assert r["contrat"]["action"] == "demander_confirmation"
    assert r["contrat"]["confiance"] == "a_confirmer"
    assert "quantite" not in r["contrat"]["champs"]

    # Redonner UNIQUEMENT un nombre, sans repeter l'article ni le mot-cle "feere".
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "saba")
    assert r["contrat"]["champs"]["quantite"] == 3
    assert r["contrat"]["confiance"] == "haute"  # plus rien ne manque


def test_consultation_capital_ne_demande_pas_de_confirmation(agent):
    """Cas 4 : une consultation pure répond directement, pas de 'c'est bien ça ?'."""
    sid = agent.demarrer_session(agent.utilisatrice_id)
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "n ka jagokun ye waa tan ye")

    assert r["contrat"]["intention"] == "capital"
    assert "jagokun" in r["message"]  # "capital", en bambara (messages_bambara.reponse_capital)
    bd = agent._session_factory()
    assert bd.get(db.SessionAppel, sid).statut == "complete"


def test_escalade_apres_trois_incomprehensions(agent):
    sid = agent.demarrer_session(agent.utilisatrice_id)
    for _ in range(2):
        r = agent.traiter_texte(sid, agent.utilisatrice_id, "bruit")
        assert r["contrat"]["action"] == "reformuler"
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "bruit")
    assert r["contrat"]["action"] == "escalade_humaine"
    assert "animatrice" in r["message"]


def test_client_nouvelle_dette_declaree_augmente_le_solde(agent):
    """P13 : "Awa me doit 10000 francs" sans "sara" = nouvelle dette, pas un paiement."""
    sid = agent.demarrer_session(agent.utilisatrice_id)
    agent.traiter_texte(sid, agent.utilisatrice_id, "n ka waa fila juru bɛ awa la")
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "owo")

    assert r["contrat"]["action"] == "enregistrer"
    bd = agent._session_factory()
    client = db.consulter_client(bd, agent.utilisatrice_id, "awa")
    assert client.montant_du == 10_000


def test_client_paiement_recu_reduit_la_dette(agent):
    """P14b : "sara" aux côtés de "juru" = un paiement reçu, qui réduit la dette."""
    bd = agent._session_factory()
    db.enregistrer_mouvement_client(bd, utilisatrice_id=agent.utilisatrice_id,
                                     nom_client="fanta", montant_fcfa=10_000, est_un_paiement=False)

    sid = agent.demarrer_session(agent.utilisatrice_id)
    agent.traiter_texte(sid, agent.utilisatrice_id, "Fanta ye kɛmɛ wolonwula sara, n ka juru la")
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "owo")

    assert r["contrat"]["action"] == "enregistrer"
    client = db.consulter_client(bd, agent.utilisatrice_id, "fanta")
    assert client.montant_du == 10_000 - 3_500
