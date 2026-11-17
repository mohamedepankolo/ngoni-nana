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


def test_enchainer_directement_sur_une_nouvelle_action_sans_dire_oui(agent):
    """Régression réelle (2026-10-10) : après "veux-tu faire autre chose ?",

    enchaîner directement sur une nouvelle phrase d'action (sans dire "oui"
    d'abord) était rejeté comme ni oui ni non et redemandait la même
    question - une utilisatrice réelle fait pourtant très naturellement ça
    plutôt que de répondre "oui" puis répéter sa phrase.
    """
    sid = agent.demarrer_session(agent.utilisatrice_id)
    agent.traiter_texte(sid, agent.utilisatrice_id, "n ye saga saba feere wa bi duuru")
    agent.traiter_texte(sid, agent.utilisatrice_id, "owo")

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


def test_redire_toute_la_phrase_pendant_la_confirmation_corrige_le_montant(agent):
    """Régression réelle (2026-10-09, test téléphone) : "ne ye misi naani de

    feere" (j'ai vendu 4 vaches, sans montant) ne donne qu'un seul chiffre,
    pris à tort pour le MONTANT (heuristique : un seul chiffre = toujours
    le montant) ; la quantité est alors redemandée et comblée correctement
    (combler_champ), mais le montant erroné reste figé jusqu'à la
    confirmation. Redire la phrase ENTIÈRE à ce moment-là (avec les deux
    chiffres) doit corriger le montant au lieu d'être rejeté comme bruit et
    de finir par escalader.
    """
    sid = agent.demarrer_session(agent.utilisatrice_id)
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "n ye misi naani feere")
    assert r["contrat"]["action"] == "demander_confirmation"
    assert r["contrat"]["confiance"] == "a_confirmer"
    assert r["contrat"]["champs"]["montant_fcfa"] == 4 * 5  # faux (4 pris pour le montant), sera corrige

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "naani")  # comble la quantite manquante
    assert r["contrat"]["action"] == "demander_confirmation"
    assert r["contrat"]["confiance"] == "haute"
    assert r["contrat"]["champs"]["quantite"] == 4
    assert r["contrat"]["champs"]["montant_fcfa"] == 4 * 5  # toujours faux, pas encore corrige

    # Maintenant en attente de confirmation (oui/non) : redire toute la
    # phrase, avec les deux chiffres cette fois, doit corriger le montant.
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "n ye misi naani feere wa bi duuru")
    assert r["contrat"]["action"] == "demander_confirmation"
    assert r["contrat"]["champs"]["quantite"] == 4
    assert r["contrat"]["champs"]["montant_fcfa"] == 250_000


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
    """Cas 4 : une consultation pure (sans chiffre) répond directement, pas de 'c'est bien ça ?'."""
    sid = agent.demarrer_session(agent.utilisatrice_id)
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "n ka jagokun")

    assert r["contrat"]["intention"] == "capital"
    assert "jagokun" in r["message"]  # "capital", en bambara (messages_bambara.reponse_capital)
    bd = agent._session_factory()
    assert bd.get(db.SessionAppel, sid).statut == "complete"


def test_consultation_pure_donne_un_message_honnete_pas_continuer(agent):
    """Régression réelle (2026-10-10) : "consultation" (ex. "combien ai-je

    vendu ce mois-ci ?") n'a pas de vraie réponse construite, mais réutilisait
    par erreur le message "veux-tu faire autre chose ?", laissant croire à
    tort qu'une action venait d'être enregistrée.
    """
    sid = agent.demarrer_session(agent.utilisatrice_id)
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "n ye joli feere nin kalo in na")  # P17
    assert r["contrat"]["intention"] == "consultation"
    assert "wɛrɛ kɛ wa" not in r["message"]  # pas "veux-tu faire autre chose ?"


def test_declarer_le_capital_initial_demande_confirmation_puis_ecrit(agent):
    """Régression réelle (2026-10-09) : "mon capital de départ est de X"

    (phrase du corpus de référence, P15) était jusqu'ici traitée comme une
    simple consultation - le chiffre donné était silencieusement ignoré, le
    capital affiché ne changeait jamais. Doit maintenant demander
    confirmation puis écrire la valeur.
    """
    sid = agent.demarrer_session(agent.utilisatrice_id)
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "n ka jagokun ye waa tan ye")  # P15 : 50 000
    assert r["contrat"]["intention"] == "capital_declaration"
    assert r["contrat"]["action"] == "demander_confirmation"

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "owo")
    assert r["contrat"]["action"] == "enregistrer"

    bd = agent._session_factory()
    assert db.calculer_capital(bd, agent.utilisatrice_id) == 50_000

    # Redéclarer écrase (pas un ajout) : le capital doit valoir exactement
    # la nouvelle valeur, pas la somme des deux.
    sid2 = agent.demarrer_session(agent.utilisatrice_id)
    agent.traiter_texte(sid2, agent.utilisatrice_id, "n ka jagokun ye wa duuru ye")  # 5000 dorome = 25 000 FCFA
    agent.traiter_texte(sid2, agent.utilisatrice_id, "owo")
    assert db.calculer_capital(bd, agent.utilisatrice_id) == 25_000


def test_ajouter_au_capital_est_cumulatif(agent):
    """"J'ajoute X à mon capital" (corpus P16) doit s'additionner aux ajouts

    précédents, à la différence d'une déclaration qui écrase.
    """
    sid = agent.demarrer_session(agent.utilisatrice_id)
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "n ye wa naani fara n ka jagokun kan")  # +20 000
    assert r["contrat"]["intention"] == "capital_ajout"
    agent.traiter_texte(sid, agent.utilisatrice_id, "owo")

    sid2 = agent.demarrer_session(agent.utilisatrice_id)
    agent.traiter_texte(sid2, agent.utilisatrice_id, "n ye wa naani fara n ka jagokun kan")  # +20 000 encore
    agent.traiter_texte(sid2, agent.utilisatrice_id, "owo")

    bd = agent._session_factory()
    assert db.calculer_capital(bd, agent.utilisatrice_id) == 40_000


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


# ---------- Items 4 à 8 du menu (script à 9 choix, 2026-11-17) ----------
# Pas de mot-clé bambara pour ces 4 intentions (voir MENU_NUMERIQUE) : chaque
# champ arrive sur son propre tour (clavier numérique "un champ à la fois",
# même UX que #champSaisie dans moteur/web/index.html), jamais toute la
# phrase en un coup comme pour "vente"/"client" (qui ont un mot-clé pour
# déclencher le chemin "redite entière", voir _combler_champ_en_attente).

def test_vente_credit_cree_une_vente_et_une_dette_client(agent):
    sid = agent.demarrer_session(agent.utilisatrice_id)
    agent.traiter_texte(sid, agent.utilisatrice_id, "4")  # 4 = vente_credit
    agent.traiter_texte(sid, agent.utilisatrice_id, "misi")
    agent.traiter_texte(sid, agent.utilisatrice_id, "fila")
    agent.traiter_texte(sid, agent.utilisatrice_id, "owo")  # confirme la quantité relue
    agent.traiter_texte(sid, agent.utilisatrice_id, "50000")
    agent.traiter_texte(sid, agent.utilisatrice_id, "owo")  # confirme le montant relu
    agent.traiter_texte(sid, agent.utilisatrice_id, "Amadou")
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "owo")  # confirmation finale

    assert r["contrat"]["action"] == "enregistrer"
    bd = agent._session_factory()
    ventes = bd.query(db.Transaction).filter_by(utilisatrice_id=agent.utilisatrice_id, type="vente").all()
    # "50000" tapé au clavier = 50 000 FCFA tel quel, pas de conversion dɔrɔmɛ
    # (voir Session.combler_champ : un chiffre arabe tapé n'est jamais en dɔrɔmɛ).
    assert len(ventes) == 1 and ventes[0].montant_fcfa == 50_000
    assert db.consulter_client(bd, agent.utilisatrice_id, "amadou").montant_du == 50_000


def test_achat_credit_cree_une_depense_et_une_dette_fournisseur(agent):
    sid = agent.demarrer_session(agent.utilisatrice_id)
    agent.traiter_texte(sid, agent.utilisatrice_id, "5")  # 5 = achat_credit
    agent.traiter_texte(sid, agent.utilisatrice_id, "saga")
    agent.traiter_texte(sid, agent.utilisatrice_id, "50")
    agent.traiter_texte(sid, agent.utilisatrice_id, "owo")  # confirme le montant relu
    agent.traiter_texte(sid, agent.utilisatrice_id, "Fanta")
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "owo")  # confirmation finale

    assert r["contrat"]["action"] == "enregistrer"
    bd = agent._session_factory()
    depenses = bd.query(db.Transaction).filter_by(utilisatrice_id=agent.utilisatrice_id, type="depense").all()
    # "50" tapé au clavier = 50 FCFA tel quel (voir test ci-dessus).
    assert len(depenses) == 1 and depenses[0].montant_fcfa == 50
    assert db.consulter_fournisseur(bd, agent.utilisatrice_id, "fanta").montant_du == 50


def test_fournisseur_paiement_reduit_la_dette_fournisseur(agent):
    bd = agent._session_factory()
    db.enregistrer_mouvement_fournisseur(bd, utilisatrice_id=agent.utilisatrice_id,
                                          nom_fournisseur="fanta", montant_fcfa=250, est_un_paiement=False)

    sid = agent.demarrer_session(agent.utilisatrice_id)
    agent.traiter_texte(sid, agent.utilisatrice_id, "6")  # 6 = fournisseur_paiement (échéance)
    agent.traiter_texte(sid, agent.utilisatrice_id, "Fanta")
    agent.traiter_texte(sid, agent.utilisatrice_id, "10")
    agent.traiter_texte(sid, agent.utilisatrice_id, "owo")  # confirme le montant relu
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "owo")  # confirmation finale

    assert r["contrat"]["action"] == "enregistrer"
    # "10" tapé au clavier = 10 FCFA tel quel (voir tests ci-dessus) : 250 - 10 = 240.
    assert db.consulter_fournisseur(bd, agent.utilisatrice_id, "fanta").montant_du == 240


def test_fournisseur_consultation_ne_demande_pas_de_confirmation(agent):
    """Item 7, comme "capital"/"stock" : une lecture seule répond tout de suite,

    la session se clôture directement (pas de "c'est bien ça ?" - voir
    test_consultation_capital_ne_demande_pas_de_confirmation).
    """
    bd = agent._session_factory()
    db.enregistrer_mouvement_fournisseur(bd, utilisatrice_id=agent.utilisatrice_id,
                                          nom_fournisseur="fanta", montant_fcfa=200, est_un_paiement=False)

    sid = agent.demarrer_session(agent.utilisatrice_id)
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "7")

    assert r["contrat"]["intention"] == "fournisseur_consultation"
    assert "?" not in r["message"]
    assert bd.get(db.SessionAppel, sid).statut == "complete"


def test_stock_ecriture_initial_puis_reapprovisionnement(agent):
    """Item 8 : 1re déclaration pour un article = remplace, la suivante = ajoute."""
    sid = agent.demarrer_session(agent.utilisatrice_id)
    agent.traiter_texte(sid, agent.utilisatrice_id, "8")  # 8 = stock_ecriture
    agent.traiter_texte(sid, agent.utilisatrice_id, "sukaro")
    agent.traiter_texte(sid, agent.utilisatrice_id, "20")
    agent.traiter_texte(sid, agent.utilisatrice_id, "owo")  # confirme la quantité relue
    agent.traiter_texte(sid, agent.utilisatrice_id, "owo")  # confirmation finale

    bd = agent._session_factory()
    assert db.consulter_stock(bd, agent.utilisatrice_id, "sukaro").quantite_actuelle == 20

    sid2 = agent.demarrer_session(agent.utilisatrice_id)
    agent.traiter_texte(sid2, agent.utilisatrice_id, "8")
    agent.traiter_texte(sid2, agent.utilisatrice_id, "sukaro")
    agent.traiter_texte(sid2, agent.utilisatrice_id, "5")
    agent.traiter_texte(sid2, agent.utilisatrice_id, "owo")
    agent.traiter_texte(sid2, agent.utilisatrice_id, "owo")

    assert db.consulter_stock(bd, agent.utilisatrice_id, "sukaro").quantite_actuelle == 25


def test_choix_menu_demarre_une_vente_comme_le_mot_cle(agent):
    """Taper/dire "1" (menu numérique, R2) démarre une vente, comme "feere"."""
    sid = agent.demarrer_session(agent.utilisatrice_id)
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "1")
    assert r["contrat"]["intention"] == "vente"
    assert r["contrat"]["action"] == "demander_confirmation"


def test_choix_menu_apres_veux_tu_faire_autre_chose(agent):
    """Après "veux-tu faire autre chose ?", choisir "3" (capital) au menu

    démarre directement une nouvelle action, sans avoir à dire "oui" d'abord
    - même comportement que la redite d'un mot-clé (voir
    test_enchainer_directement_sur_une_nouvelle_action_sans_dire_oui).
    """
    sid = agent.demarrer_session(agent.utilisatrice_id)
    agent.traiter_texte(sid, agent.utilisatrice_id, "n ye saga saba feere wa bi duuru")
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "owo")
    assert r["contrat"]["action"] == "enregistrer"

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "3")  # 3 = capital, sans dire "oui" d'abord
    assert r["contrat"]["intention"] == "capital"
    assert "jagokun" in r["message"]  # réponse directe de consultation, comme "n ka jagokun"


# --- Confirmation unitaire quantité/montant (saisie clavier, appli mobile) ---

def test_quantite_et_montant_sont_relus_et_confirmes_un_par_un(agent):
    """Chaque champ numérique (quantité, puis montant) est relu en bambara et

    confirmé séparément avant de passer au suivant, puis la confirmation
    globale habituelle a toujours lieu à la fin - demande explicite : saisie
    clavier des chiffres sur l'application mobile, avec relecture immédiate.
    """
    sid = agent.demarrer_session(agent.utilisatrice_id)

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "n ye saga feere")  # article seul, rien de chiffré
    assert r["contrat"]["action"] == "demander_confirmation"
    assert "Hakɛ" in r["message"]  # demande la quantité (demander_quantite)

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "saba")  # quantite = 3
    assert r["contrat"]["champs"]["quantite"] == 3
    assert "saba" in r["message"]  # relecture : "I ko saba..." (nombre_en_bambara(3))

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "owo")  # confirme la quantite
    assert "Wari" in r["message"]  # passe au champ suivant : demande le montant

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "waa saba")  # montant = 3000 dorome -> 15000 FCFA
    assert r["contrat"]["champs"]["montant_fcfa"] == 15_000
    assert "wari" in r["message"].lower()  # relecture du montant

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "owo")  # confirme le montant
    assert r["contrat"]["confiance"] == "haute"
    assert "sɔnna" in r["message"]  # confirmation globale habituelle (confirmation_vente)

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "owo")  # confirmation finale
    assert r["contrat"]["action"] == "enregistrer"

    bd = agent._session_factory()
    transactions = bd.query(db.Transaction).filter_by(utilisatrice_id=agent.utilisatrice_id).all()
    assert len(transactions) == 1
    assert transactions[0].montant_fcfa == 15_000
    assert transactions[0].quantite == 3


def test_refuser_la_relecture_dun_champ_redemande_ce_champ(agent):
    """Dire "non" à la relecture d'un chiffre redemande CE champ précisément,

    pas une incompréhension générique ni le dernier champ confirmé au hasard.
    """
    sid = agent.demarrer_session(agent.utilisatrice_id)
    agent.traiter_texte(sid, agent.utilisatrice_id, "n ye saga feere")
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "saba")  # quantite = 3, en attente de confirmation
    assert r["contrat"]["champs"]["quantite"] == 3

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "ayi")  # "non" : la quantite dite n'est pas la bonne
    assert "quantite" not in r["contrat"]["champs"]
    assert "Hakɛ" in r["message"]  # redemande bien la quantite, pas une confirmation globale

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "naani")  # la bonne quantite, cette fois : 4
    assert r["contrat"]["champs"]["quantite"] == 4


def test_redire_toute_la_phrase_pendant_la_confirmation_unitaire_corrige(agent):
    """Même garde-fou que pour la confirmation globale (voir

    test_redire_toute_la_phrase_pendant_la_confirmation_corrige_le_montant) :
    redire la phrase entière PENDANT la relecture d'un champ (plutôt que de
    dire oui/non) doit corriger via le chemin normal, pas être rejeté comme
    une réponse incomprise.
    """
    sid = agent.demarrer_session(agent.utilisatrice_id)
    agent.traiter_texte(sid, agent.utilisatrice_id, "n ye misi naani feere")  # 4 pris a tort pour le montant
    r = agent.traiter_texte(sid, agent.utilisatrice_id, "naani")  # comble la quantite -> en attente de confirmation
    assert r["contrat"]["champs"]["montant_fcfa"] == 4 * 5  # toujours faux a ce stade

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "n ye misi naani feere wa bi duuru")
    assert r["contrat"]["champs"]["quantite"] == 4
    assert r["contrat"]["champs"]["montant_fcfa"] == 250_000  # corrige


def test_attente_decrit_le_prochain_widget_pour_une_interface(agent):
    """"attente" (ajouté pour l'application mobile) doit refléter exactement

    ce que le système attend au prochain tour, à chaque étape d'un parcours
    complet - pour qu'une interface sache afficher un clavier numérique, un
    choix oui/non, ou le menu, sans avoir à deviner depuis le texte parlé.
    """
    sid = agent.demarrer_session(agent.utilisatrice_id)

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "n ye saga feere")
    assert r["attente"] == "champ:quantite"

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "saba")
    assert r["attente"] == "confirmation_champ:quantite"

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "owo")
    assert r["attente"] == "champ:montant_fcfa"

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "waa saba")
    assert r["attente"] == "confirmation_champ:montant_fcfa"

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "owo")
    assert r["attente"] == "confirmation"

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "owo")
    assert r["attente"] == "continuer"

    r = agent.traiter_texte(sid, agent.utilisatrice_id, "ayi")  # ne veut rien faire d'autre
    assert r["attente"] == "menu"
