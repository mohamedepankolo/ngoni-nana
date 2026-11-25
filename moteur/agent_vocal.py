"""Agent vocal : orchestrateur (Architecture_Technique_NGONI_NANA.docx, section 3.5).

Fait circuler les données entre l'ASR, le moteur de décision (moteur_decision.py)
et le TTS pour une session donnée. Gère aussi la base de données : c'est ici,
et nulle part ailleurs, que les écritures ont lieu, après confirmation.

Pas de vraie téléphonie branchée (R2 toujours ouvert) : `traiter_texte` prend
du texte déjà transcrit, pour pouvoir être testé sans dépendre d'un appel
réel. `transcrire`/`syntheser` sont injectés (voir asr_robotsmali.py /
tts_maliba.py) : un test peut passer des fonctions factices à la place des
vrais modèles, lourds et dépendants d'un accès réseau/HF_TOKEN.

Les messages parlés sont en bambara (messages_bambara.py) : un premier jet de
traduction, pas un texte validé. Voir la réserve en tête de ce module-là.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone

from montants import extraire_nombres, normaliser

from moteur import base_donnees as db
from moteur import messages_bambara as msg
from moteur.dictionnaire_mots_cles import reconnaitre_choix_menu, reconnaitre_confirmation, reconnaitre_intention
from moteur.moteur_decision import Session, est_une_redite_numerique_fiable

# Intentions qui ne font que lire des données déjà en base : rien à écrire, et
# donc rien à faire confirmer par un "oui" avant de répondre (cas 4 et 6 du
# parcours). "client" reste à part : consulter une dette ne demande pas de
# confirmation, mais enregistrer un paiement, oui. "fournisseur_consultation"
# (item 7, 2026-11-17) : même principe, côté dette fournisseur.
INTENTIONS_LECTURE_SEULE = {"capital", "consultation", "stock", "fournisseur_consultation", "sfd_consultation"}

CONSTRUCTEURS_CONFIRMATION = {
    "vente": msg.confirmation_vente,
    "depense": msg.confirmation_depense,
    "client": msg.confirmation_client,
    "capital_declaration": msg.confirmation_capital_declaration,
    "capital_ajout": msg.confirmation_capital_ajout,
    "vente_credit": msg.confirmation_vente_credit,
    "achat_credit": msg.confirmation_achat_credit,
    "fournisseur_paiement": msg.confirmation_fournisseur_paiement,
    "stock_ecriture": msg.confirmation_stock_ecriture,
    "sfd_declaration": msg.confirmation_sfd_declaration,
    "sfd_paiement": msg.confirmation_sfd_paiement,
}

# Une question ciblée par champ manquant, plutôt qu'un "redonne le montant"
# générique qui n'avait aucun sens quand c'était l'article ou la quantité qui
# manquait (bug réel constaté en test, 2026-10-09 : voir messages_bambara.py).
CONSTRUCTEURS_DEMANDE_CHAMP = {
    "montant_fcfa": msg.demander_precision_montant,
    "quantite": msg.demander_quantite,
    "article": msg.demander_article,
    "client": msg.demander_client,
    "fournisseur": msg.demander_fournisseur,
    "nom_sfd": msg.demander_nom_sfd,
    "duree_mois": msg.demander_duree_mois,
    "echeance_mensuelle_fcfa": msg.demander_echeance_mensuelle,
}

# Même chose, mais pour RE-demander un champ après un refus explicite (un
# "non" à la relecture, ou une valeur mal comprise) : ces messages disent
# "tuguni" ("encore"), qui ferait bizarre sur la toute première question
# posée sur ce champ (retour terrain, 2026-11-17, Mohamed) - CONSTRUCTEURS_
# DEMANDE_CHAMP ci-dessus sert pour cette première question, celui-ci
# seulement quand on repose la MÊME question après un échec sur CE champ.
CONSTRUCTEURS_REDEMANDE_CHAMP = {
    "montant_fcfa": msg.demander_precision_montant_encore,
    "quantite": msg.demander_quantite_encore,
    "article": msg.demander_article_encore,
    "client": msg.demander_client_encore,
    "fournisseur": msg.demander_fournisseur_encore,
    "nom_sfd": msg.demander_nom_sfd_encore,
    "duree_mois": msg.demander_duree_mois_encore,
    "echeance_mensuelle_fcfa": msg.demander_echeance_mensuelle_encore,
}

# Champs pour lesquels la valeur tout juste saisie (clavier ou voix) est
# relue en bambara et doit être confirmée AVANT de passer au champ suivant
# (demande explicite : saisie clavier des chiffres sur l'application mobile,
# avec relecture immédiate, en plus de la confirmation globale de fin de
# transaction déjà existante). Limité aux deux champs numériques : un nom
# d'article ou de client mal compris se corrige sans risque particulier,
# un chiffre mal compris peut fausser toute l'écriture comptable.
CHAMPS_A_CONFIRMER_UNITAIREMENT = {"quantite", "montant_fcfa", "duree_mois", "echeance_mensuelle_fcfa"}

# Champs qu'on peut proposer de corriger après un "non" au résumé final (voir
# _demarrer_correction, msg.demander_quel_champ_corriger) - ordre fixe plutôt
# que l'ordre de CHAMPS_ATTENDUS (moteur_decision.py) : certaines intentions
# (ex. "client") ont un montant effectivement saisi sans l'exiger dans
# CHAMPS_ATTENDUS, cet ordre fixe les propose quand même s'ils sont présents.
CHAMPS_CORRIGIBLES = ("article", "quantite", "montant_fcfa", "client", "fournisseur",
                       "nom_sfd", "duree_mois", "echeance_mensuelle_fcfa")


def _reconnaitre_choix_champ(texte: str, champs: list[str]) -> str | None:
    """Reconnaît le choix d'UN champ parmi `champs` (voir

    msg.demander_quel_champ_corriger) : un chiffre tapé (1, 2...), un nombre
    dit en bambara (kelen, fila...), ou le mot bambara du champ lui-même
    (msg.NOMS_CHAMPS_BAMBARA) - même principe à plusieurs canaux que
    reconnaitre_choix_menu (dictionnaire_mots_cles.py), mais sur une liste
    choisie à la volée (les champs de CETTE transaction), pas le menu fixe.
    None si rien de tout ça ne correspond.
    """
    texte_brut = texte.strip()
    if texte_brut.isdigit():
        indice = int(texte_brut)
        return champs[indice - 1] if 1 <= indice <= len(champs) else None

    nombres = extraire_nombres(texte)
    if len(nombres) == 1 and 1 <= nombres[0] <= len(champs):
        return champs[nombres[0] - 1]

    tokens = set(normaliser(texte).split())
    for champ in champs:
        mots_champ = set(normaliser(msg.NOMS_CHAMPS_BAMBARA.get(champ, "")).split())
        if mots_champ and mots_champ <= tokens:
            return champ
    return None


@dataclass
class _EtatSession:
    session_moteur: Session = field(default_factory=Session)
    en_attente_confirmation: bool = False
    # Un seul champ précis est attendu au tour suivant (soit parce qu'il
    # manquait pour compléter la transaction, soit parce que l'utilisatrice a
    # dit "non" et qu'on lui redemande ce champ-là) : voir
    # _combler_champ_en_attente et _demarrer_correction.
    champ_en_attente: str | None = None
    # Champ dont la valeur vient d'être saisie et attend sa confirmation
    # unitaire (voir CHAMPS_A_CONFIRMER_UNITAIREMENT, _traiter_confirmation_champ)
    # - distinct de champ_en_attente (qui attend une NOUVELLE valeur) et de
    # en_attente_confirmation (qui attend le "oui" global de fin de transaction).
    champ_a_confirmer: str | None = None
    # Liste des champs proposés au choix après un "non" au résumé final (voir
    # _demarrer_correction, _traiter_choix_champ_a_corriger) - distinct de
    # champ_en_attente (qui attend la NOUVELLE valeur d'UN champ déjà choisi) :
    # ici on attend encore LEQUEL corriger, avant de demander sa valeur.
    champs_a_choisir: list[str] | None = None
    # Compte les "non" d'affilée, séparément de Session.tentatives_reformulation
    # (qui compte les énoncés non compris). Nécessaire car un champ libre
    # (article, nom de client) est "rempli avec succès" par n'importe quel mot
    # restant, même du bruit (pas de chiffre à vérifier comme pour un
    # montant) : sans ce compteur dédié, dire "non" en boucle sur un article
    # mal comblé ne faisait jamais progresser aucun compteur d'échec et ne
    # pouvait donc jamais escalader (bug réel, 2026-10-09).
    refus_consecutifs: int = 0
    # Vrai juste après un enregistrement réussi, le temps de savoir si
    # l'utilisatrice veut faire autre chose ou arrêter là (voir
    # _traiter_reponse_continuer). Distinct de en_attente_confirmation : ici
    # on attend un oui/non sur "veux-tu faire autre chose ?", pas sur une
    # transaction à enregistrer.
    attente_continuer: bool = False
    tentatives_continuer: int = 0
    # Compte les "non" d'affilée à LA RELECTURE D'UN CHAMP (CHAMPS_A_CONFIRMER_
    # UNITAIREMENT, _traiter_confirmation_champ) - encore un autre compteur
    # distinct (voir refus_consecutifs ci-dessus pour pourquoi chaque étape a
    # le sien) : avant, dire "non" en boucle à "I ko wari X, i sɔnna wa?" ne
    # faisait progresser AUCUN compteur d'échec, donc n'escaladait jamais,
    # même après plus de 10 refus (bug réel signalé en test, 2026-11-17,
    # Mohamed - la docstring de _traiter_confirmation_champ documentait déjà
    # cette limite comme "à corriger si observé en test réel").
    refus_champ_consecutifs: int = 0


class AgentVocal:
    """Une instance par déploiement ; garde un état par session_id en mémoire.

    L'état moteur (Session) est en mémoire, pas persisté : une coupure réelle
    perdrait le fil de la conversation en cours, mais jamais une transaction
    déjà confirmée (déjà écrite en base avant la coupure) ni une transaction
    non confirmée (jamais écrite, cas 10 du parcours). Persister aussi l'état
    conversationnel est une amélioration future, pas un prérequis du MVP.
    """

    def __init__(self, session_factory, transcrire=None, syntheser=None):
        self._session_factory = session_factory
        self._transcrire = transcrire
        self._syntheser = syntheser
        self._etats: dict[int, _EtatSession] = {}

    def demarrer_session(self, utilisatrice_id: int, canal: str = "voix") -> int:
        bd = self._session_factory()
        try:
            for id_expire in db.expirer_sessions_anciennes(bd):
                self._etats.pop(id_expire, None)
            s = db.SessionAppel(utilisatrice_id=utilisatrice_id, canal=canal, statut="incomplete")
            bd.add(s)
            bd.commit()
            bd.refresh(s)
            self._etats[s.id] = _EtatSession()
            return s.id
        finally:
            bd.close()

    def reinitialiser(self, session_id: int) -> None:
        """Abandonne l'opération en cours pour cette session (bouton "Retour

        au menu" côté app, voir web/index.html) : repart d'un état frais,
        SANS rejouer le message d'accueil (contrairement à
        demarrer_session) - sinon chaque annulation redéclencherait le bug
        de l'audio d'accueil de ~72s (voir messages_bambara.menu_principal).
        Ne touche pas à la session SQL (SessionAppel) : annuler une
        opération n'est pas terminer l'appel, juste repartir à "menu" pour
        permettre une nouvelle action tout de suite.
        """
        self._etats[session_id] = _EtatSession()

    def traiter_audio(self, session_id: int, utilisatrice_id: int, chemin_audio: str) -> dict:
        if self._transcrire is None:
            raise RuntimeError("Aucune fonction de transcription fournie à cet AgentVocal.")
        texte = self._transcrire(chemin_audio)
        return self.traiter_texte(session_id, utilisatrice_id, texte)

    def etat_attente(self, session_id: int) -> str:
        """Interroge l'attente courante d'une session SANS traiter de nouvel

        énoncé (voir _attente) : utile quand un tour échoue avant même
        d'atteindre le moteur (ex. ASR en panne, api.py/_reponse_secours) -
        l'état de la session n'a alors pas bougé, mais l'appelant a quand
        même besoin de savoir quoi proposer comme widget de saisie.
        """
        etat = self._etats.setdefault(session_id, _EtatSession())
        return self._attente(etat)

    def traiter_texte(self, session_id: int, utilisatrice_id: int, texte: str) -> dict:
        etat = self._etats.setdefault(session_id, _EtatSession())
        bd = self._session_factory()
        try:
            resultat = self._traiter_texte_interne(bd, etat, session_id, utilisatrice_id, texte)
            # Ajouté ici, en un seul point, plutôt que threadé à travers les ~25
            # appels internes à _repondre : dit à une interface (application
            # mobile) ce qu'il faut proposer au PROCHAIN tour (clavier numérique,
            # oui/non, menu...) sans qu'elle ait à deviner depuis le texte parlé.
            resultat["attente"] = self._attente(etat)
            return resultat
        finally:
            bd.close()

    @staticmethod
    def _attente(etat: "_EtatSession") -> str:
        """Ce que le système attend au prochain tour, pour que l'interface

        choisisse le bon widget de saisie : "menu" (aucune intention active -
        menu numérique ou parole libre), "champ:<nom>" (un champ précis
        manque - clavier numérique pour quantite/montant_fcfa, texte libre
        pour article/client), "confirmation_champ:<nom>" (relecture d'un
        chiffre à confirmer), "choix_champ:<nom1>,<nom2>,..." (après un "non"
        au résumé : lequel de ces champs corriger, voir CHAMPS_CORRIGIBLES),
        "confirmation" (confirmation globale de fin de transaction) ou
        "continuer" ("veux-tu faire autre chose ?"). Reflète exactement
        l'ordre de branchement de _traiter_texte_interne.
        """
        if etat.attente_continuer:
            return "continuer"
        if etat.champs_a_choisir:
            return "choix_champ:" + ",".join(etat.champs_a_choisir)
        if etat.champ_a_confirmer:
            return f"confirmation_champ:{etat.champ_a_confirmer}"
        if etat.champ_en_attente:
            return f"champ:{etat.champ_en_attente}"
        if etat.en_attente_confirmation:
            return "confirmation"
        return "menu"

    def _traiter_texte_interne(self, bd, etat: "_EtatSession", session_id: int,
                                utilisatrice_id: int, texte: str) -> dict:
        s = etat.session_moteur

        if etat.attente_continuer:
            return self._traiter_reponse_continuer(bd, etat, session_id, utilisatrice_id, texte)

        if etat.champs_a_choisir:
            return self._traiter_choix_champ_a_corriger(bd, etat, session_id, texte)

        if etat.champ_a_confirmer:
            return self._traiter_confirmation_champ(bd, etat, session_id, utilisatrice_id, texte)

        if etat.champ_en_attente:
            return self._combler_champ_en_attente(bd, etat, session_id, utilisatrice_id, texte)

        if etat.en_attente_confirmation:
            reponse = reconnaitre_confirmation(texte)
            if reponse is True:
                contrat = s.confirmer()
                message = self._conclure(bd, session_id, utilisatrice_id, contrat)
                etat.en_attente_confirmation = False
                etat.attente_continuer = True
                return self._repondre(bd, session_id, contrat, message)
            if reponse is False:
                return self._demarrer_correction(bd, etat, session_id)
            # Ni oui ni non. Deux façons légitimes de corriger sans dire
            # "non" d'abord :
            # (a) redire la phrase ENTIÈRE (même mot-clé d'action reconnu) :
            #     passe par le même chemin qu'un énoncé frais (s.recevoir),
            #     qui fusionne proprement les nouvelles valeurs - utile en
            #     particulier quand un seul chiffre avait été pris à tort
            #     pour le montant plutôt que la quantité (ou l'inverse) :
            #     redire les DEUX chiffres ensemble corrige les deux d'un
            #     coup (bug réel, test téléphone 2026-10-09 : la phrase
            #     complète était rejetée comme "bruit" et finissait par
            #     escalader au lieu de corriger).
            # (b) redire UNIQUEMENT un nombre (cas 9), seulement si l'énoncé
            #     est PUREMENT numérique (voir est_une_redite_numerique_fiable),
            #     jamais s'il contient aussi un mot non reconnu : un mot de
            #     bruit ASR contenant un chiffre par coïncidence (ex.
            #     "hamaden fila don", "fila"=2) a déjà écrasé silencieusement
            #     l'article déjà confirmé avec ce bruit (bug réel, même date).
            meme_action_redite = s.intention is not None and reconnaitre_intention(texte) == s.intention
            if meme_action_redite or est_une_redite_numerique_fiable(texte):
                etat.en_attente_confirmation = False
            else:
                return self._repeter_confirmation_ou_escalader(bd, etat, session_id)

        return self._traiter_nouvelle_action(bd, etat, session_id, utilisatrice_id, texte)

    def _traiter_nouvelle_action(self, bd, etat: "_EtatSession", session_id: int,
                                  utilisatrice_id: int, texte: str) -> dict:
        """Passe un énoncé par le moteur de décision (Session.recevoir) et

        enchaîne sur la bonne étape (reformulation, escalade, lecture seule,
        confirmation ou champ manquant). Factorisé pour être appelé aussi
        bien dans le flux normal qu'en réponse directe à "veux-tu faire
        autre chose ?" (voir _traiter_reponse_continuer).
        """
        s = etat.session_moteur
        contrat = s.recevoir(texte)

        if contrat["action"] == "reformuler":
            message = msg.reformulation(s.tentatives_reformulation)
            return self._repondre(bd, session_id, contrat, message)

        if contrat["action"] == "escalade_humaine":
            self._cloturer_session(bd, session_id, statut="incomplete")
            return self._repondre(bd, session_id, contrat, msg.escalade())

        # action == "demander_confirmation"
        if contrat["intention"] in INTENTIONS_LECTURE_SEULE and contrat["confiance"] == "haute":
            s.confirmer()
            message = self._repondre_lecture(bd, utilisatrice_id, contrat)
            self._cloturer_session(bd, session_id, statut="complete")
            return self._repondre(bd, session_id, contrat, message)

        if contrat["confiance"] == "haute":
            etat.en_attente_confirmation = True
            construire = CONSTRUCTEURS_CONFIRMATION.get(contrat["intention"])
            message = construire(contrat["champs"]) if construire else msg.demander_precision_montant()
            return self._repondre(bd, session_id, contrat, message)

        # confiance == "a_confirmer" : un champ précis manque encore. Cible la
        # question sur CE champ (pas un "redonne le montant" générique, qui ne
        # voulait rien dire quand c'était l'article ou la quantité qui
        # manquait - bug réel, 2026-10-09).
        manquant = s.premier_champ_manquant()
        etat.champ_en_attente = manquant
        construire = CONSTRUCTEURS_DEMANDE_CHAMP.get(manquant, msg.demander_precision_montant)
        return self._repondre(bd, session_id, contrat, construire())

    def _traiter_reponse_continuer(self, bd, etat: "_EtatSession", session_id: int,
                                    utilisatrice_id: int, texte: str) -> dict:
        """Répond à "veux-tu faire autre chose ?" (posée après un enregistrement).

        "oui" : la session continue, prête pour une nouvelle action (sans
        redemander un montant au hasard). "non" : clôture nette avec un vrai
        message de fin, au lieu de laisser la réponse se faire interpréter
        comme une tentative d'action ratée (bug réel, test téléphone
        2026-10-09 : répondre à cette question finissait par redemander des
        informations de vente sans aucun sens).

        Enchaîner directement sur une nouvelle action (sans dire "oui"
        d'abord) est aussi accepté : une utilisatrice réelle fait très
        naturellement ça plutôt que de répondre "oui" puis répéter sa
        phrase (constaté en test réel, 2026-10-10 : enchaîner directement
        faisait redemander "oui ou non ?" en boucle jusqu'à l'échec).
        """
        # Un choix de menu (chiffre 1-6) est aussi accepté ici, pas seulement un
        # mot-clé parlé : à ce moment précis, la session repart de zéro juste
        # en dessous (Session() fraîche), donc aucune intention active ne peut
        # entrer en collision avec le chiffre (voir Session.recevoir).
        if reconnaitre_intention(texte) is not None or reconnaitre_choix_menu(texte) is not None:
            etat.attente_continuer = False
            etat.tentatives_continuer = 0
            etat.session_moteur = Session()
            return self._traiter_nouvelle_action(bd, etat, session_id, utilisatrice_id, texte)

        reponse = reconnaitre_confirmation(texte)
        if reponse is True:
            etat.attente_continuer = False
            etat.tentatives_continuer = 0
            etat.session_moteur = Session()
            contrat = {"intention": None, "champs": {}, "confiance": "haute", "action": "continuer_session"}
            return self._repondre(bd, session_id, contrat, msg.pret_a_ecouter())
        if reponse is False:
            etat.attente_continuer = False
            contrat = {"intention": None, "champs": {}, "confiance": "haute", "action": "fin_session"}
            return self._repondre(bd, session_id, contrat, msg.au_revoir())

        etat.tentatives_continuer += 1
        if etat.tentatives_continuer > Session.MAX_REFORMULATIONS:
            etat.attente_continuer = False
            contrat = {"intention": None, "champs": {}, "confiance": "echec", "action": "fin_session"}
            return self._repondre(bd, session_id, contrat, msg.au_revoir())
        contrat = {"intention": None, "champs": {}, "confiance": "a_confirmer", "action": "demander_confirmation"}
        return self._repondre(bd, session_id, contrat, msg.continuer())

    def _demarrer_correction(self, bd, etat: "_EtatSession", session_id: int) -> dict:
        """L'utilisatrice dit "non" à la confirmation : propose un choix

        numéroté parmi les champs réellement saisis (CHAMPS_CORRIGIBLES),
        plutôt qu'un "je n'ai pas compris" générique OU deviner tout seul le
        dernier champ confirmé (ancien comportement, pas forcément le bon
        champ en cause - retour terrain, 2026-11-17, Mohamed : "ça peut
        concerner autant la quantité que le montant, que le produit"). Voir
        _traiter_choix_champ_a_corriger pour la suite (le choix lui-même).
        """
        s = etat.session_moteur
        etat.refus_consecutifs += 1
        if etat.refus_consecutifs > s.MAX_REFORMULATIONS:
            s.escaladee = True
            etat.en_attente_confirmation = False
            etat.champ_en_attente = None
            contrat = {"intention": s.intention, "champs": dict(s.champs_confirmes),
                       "confiance": "echec", "action": "escalade_humaine"}
            self._cloturer_session(bd, session_id, statut="incomplete")
            return self._repondre(bd, session_id, contrat, msg.escalade())

        champs_possibles = [c for c in CHAMPS_CORRIGIBLES if c in s.champs_confirmes]
        etat.en_attente_confirmation = False
        if not champs_possibles:
            contrat = {"intention": s.intention, "champs": {}, "confiance": "echec", "action": "reformuler"}
            return self._repondre(bd, session_id, contrat, msg.demander_precision_montant())
        etat.champs_a_choisir = champs_possibles
        contrat = {"intention": s.intention, "champs": dict(s.champs_confirmes),
                   "confiance": "a_confirmer", "action": "demander_confirmation"}
        return self._repondre(bd, session_id, contrat, msg.demander_quel_champ_corriger(champs_possibles))

    def _traiter_choix_champ_a_corriger(self, bd, etat: "_EtatSession", session_id: int, texte: str) -> dict:
        """Répond au choix du champ à corriger (demander_quel_champ_corriger,

        posé par _demarrer_correction) : un chiffre (1, 2...), un nombre dit
        en bambara, ou le mot bambara du champ lui-même (voir
        _reconnaitre_choix_champ). Une fois le champ choisi, l'efface et
        redemande sa valeur (CONSTRUCTEURS_REDEMANDE_CHAMP, comme l'ancien
        comportement de _demarrer_correction une fois le champ identifié).
        """
        s = etat.session_moteur
        champs_possibles = etat.champs_a_choisir or []
        champ = _reconnaitre_choix_champ(texte, champs_possibles)

        if champ is None:
            contrat = {"intention": s.intention, "champs": dict(s.champs_confirmes),
                       "confiance": "a_confirmer", "action": "demander_confirmation"}
            return self._repondre(bd, session_id, contrat, msg.demander_quel_champ_corriger(champs_possibles))

        etat.champs_a_choisir = None
        s.champs_confirmes.pop(champ, None)
        etat.champ_en_attente = champ
        contrat = {"intention": s.intention, "champs": dict(s.champs_confirmes),
                   "confiance": "a_confirmer", "action": "demander_confirmation"}
        construire = CONSTRUCTEURS_REDEMANDE_CHAMP.get(champ, msg.demander_precision_montant_encore)
        return self._repondre(bd, session_id, contrat, construire())

    def _repeter_confirmation_ou_escalader(self, bd, etat: "_EtatSession", session_id: int) -> dict:
        s = etat.session_moteur
        s.tentatives_reformulation += 1
        if s.tentatives_reformulation > s.MAX_REFORMULATIONS:
            s.escaladee = True
            etat.en_attente_confirmation = False
            contrat = {"intention": s.intention, "champs": dict(s.champs_confirmes),
                       "confiance": "echec", "action": "escalade_humaine"}
            self._cloturer_session(bd, session_id, statut="incomplete")
            return self._repondre(bd, session_id, contrat, msg.escalade())
        contrat = {"intention": s.intention, "champs": dict(s.champs_confirmes),
                   "confiance": "a_confirmer", "action": "demander_confirmation"}
        construire = CONSTRUCTEURS_CONFIRMATION.get(s.intention)
        message = construire(s.champs_confirmes) if construire else msg.demander_precision_montant()
        return self._repondre(bd, session_id, contrat, message)

    def _combler_champ_en_attente(self, bd, etat: "_EtatSession", session_id: int,
                                   utilisatrice_id: int, texte: str) -> dict:
        """Traite une réponse à une question ciblée sur un seul champ

        (Session.combler_champ) : un chiffre isolé remplit directement CE
        champ précis, sans réappliquer l'heuristique générale qui suppose à
        tort qu'un seul nombre est toujours le montant (bug réel, 2026-10-09 :
        redonner uniquement le montant demandé n'aboutissait jamais si la
        quantité restait aussi manquante).
        """
        s = etat.session_moteur
        champ = etat.champ_en_attente

        # Si l'utilisatrice redit la phrase ENTIÈRE (même mot-clé d'action
        # reconnu) plutôt qu'un seul mot/chiffre pour ce champ précis, fusionne
        # proprement via le chemin normal (s.recevoir) au lieu de ne combler
        # que CE champ : sinon un montant déjà faux (pris à tort dans un
        # énoncé précédent) restait figé même quand la phrase redite le
        # corrigeait (bug réel, test téléphone 2026-10-09).
        if s.intention is not None and reconnaitre_intention(texte) == s.intention:
            etat.champ_en_attente = None
            contrat = s.recevoir(texte)
            if contrat["action"] == "reformuler":
                return self._repondre(bd, session_id, contrat, msg.reformulation(s.tentatives_reformulation))
            return self._apres_champ_confirme(bd, etat, session_id, utilisatrice_id, s, contrat)

        contrat = s.combler_champ(champ, texte)

        if contrat["action"] == "reformuler":
            s.tentatives_reformulation += 1
            if s.tentatives_reformulation > s.MAX_REFORMULATIONS:
                s.escaladee = True
                etat.champ_en_attente = None
                contrat = {"intention": s.intention, "champs": dict(s.champs_confirmes),
                           "confiance": "echec", "action": "escalade_humaine"}
                self._cloturer_session(bd, session_id, statut="incomplete")
                return self._repondre(bd, session_id, contrat, msg.escalade())
            construire = CONSTRUCTEURS_REDEMANDE_CHAMP.get(champ, msg.demander_precision_montant_encore)
            return self._repondre(bd, session_id, contrat, construire())

        s.tentatives_reformulation = 0
        if champ in CHAMPS_A_CONFIRMER_UNITAIREMENT:
            # Relecture immédiate AVANT de passer au champ suivant ou à la
            # confirmation globale (voir CHAMPS_A_CONFIRMER_UNITAIREMENT) :
            # la décision du "champ suivant vs confirmation globale" est
            # reportée dans _apres_champ_confirme, rejouée une fois le "oui"
            # reçu (_traiter_confirmation_champ).
            etat.champ_en_attente = None
            etat.champ_a_confirmer = champ
            return self._repondre(bd, session_id, contrat,
                                   msg.confirmer_champ(champ, s.champs_confirmes[champ]))
        return self._apres_champ_confirme(bd, etat, session_id, utilisatrice_id, s, contrat)

    def _apres_champ_confirme(self, bd, etat: "_EtatSession", session_id: int,
                               utilisatrice_id: int, s: Session, contrat: dict) -> dict:
        """Que faire une fois un champ réglé : poser la question du prochain

        champ manquant, ou passer à la confirmation globale de fin de
        transaction si c'était le dernier. Factorisé pour être rejoué aussi
        bien juste après un remplissage direct (champs qui n'exigent pas de
        confirmation unitaire) qu'après un "oui" à la relecture d'un champ
        qui en exigeait une (_traiter_confirmation_champ).

        Une intention de lecture seule (ex. "stock", item 9) peut arriver ici
        avec confiance "haute" dès que son dernier champ manquant (l'article)
        vient d'être comblé par ce chemin "un champ à la fois" - distinct du
        chemin direct de _traiter_nouvelle_action qui, lui, vérifiait déjà
        INTENTIONS_LECTURE_SEULE. Sans ce même raccourci ici, "stock" n'avait
        pas d'entrée dans CONSTRUCTEURS_CONFIRMATION et retombait à tort sur
        msg.demander_precision_montant() - bug réel trouvé en testant "9" puis
        l'article dans un tour séparé (2026-11-18).
        """
        if contrat["intention"] in INTENTIONS_LECTURE_SEULE and contrat["confiance"] == "haute":
            etat.champ_en_attente = None
            message = self._repondre_lecture(bd, utilisatrice_id, contrat)
            self._cloturer_session(bd, session_id, statut="complete")
            return self._repondre(bd, session_id, contrat, message)

        if contrat["confiance"] == "haute":
            etat.champ_en_attente = None
            etat.en_attente_confirmation = True
            construire = CONSTRUCTEURS_CONFIRMATION.get(contrat["intention"])
            message = construire(contrat["champs"]) if construire else msg.demander_precision_montant()
            return self._repondre(bd, session_id, contrat, message)

        manquant = s.premier_champ_manquant()
        etat.champ_en_attente = manquant
        construire = CONSTRUCTEURS_DEMANDE_CHAMP.get(manquant, msg.demander_precision_montant)
        return self._repondre(bd, session_id, contrat, construire())

    def _traiter_confirmation_champ(self, bd, etat: "_EtatSession", session_id: int,
                                     utilisatrice_id: int, texte: str) -> dict:
        """Répond à la relecture d'un champ numérique tout juste saisi

        (CHAMPS_A_CONFIRMER_UNITAIREMENT). "oui" : passe à l'étape suivante
        (champ manquant suivant, ou confirmation globale si c'était le
        dernier - voir _apres_champ_confirme). "non" : redemande CE champ
        précis, valeur fausse retirée - pas le dernier champ confirmé au
        hasard comme _demarrer_correction, puisqu'ici le champ en cause est
        déjà connu avec certitude. Escalade après trop de "non" d'affilée
        (etat.refus_champ_consecutifs, voir sa docstring) - corrige une
        limite réelle signalée en test (2026-11-17, Mohamed : plus de 10
        "non" sur une quantité sans jamais escalader).

        Limite connue, assumée pour cette première version : une réponse ni
        oui ni non ici ne compte dans aucun compteur de tentatives - ne peut
        donc pas encore escalader vers une personne si ÇA boucle (seule la
        boucle du "non" explicite est corrigée ici). À corriger si observé
        en test réel, comme le reste des compteurs d'échec de ce fichier.
        """
        s = etat.session_moteur
        champ = etat.champ_a_confirmer

        # Même motif que _combler_champ_en_attente : redire la phrase ENTIÈRE
        # (même mot-clé/choix de menu reconnu) corrige via le chemin normal
        # (s.recevoir), qui peut aussi corriger un autre champ déjà faux en
        # même temps (ex. un montant mal pris pour la quantité plus tôt) -
        # sinon une telle redite serait rejetée comme "ni oui ni non" et le
        # champ fautif resterait figé (même bug que celui déjà corrigé le
        # 2026-10-09 pour la confirmation globale, voir _demarrer_correction).
        meme_action_redite = s.intention is not None and (
            reconnaitre_intention(texte) == s.intention or reconnaitre_choix_menu(texte) == s.intention
        )
        if meme_action_redite:
            etat.champ_a_confirmer = None
            contrat = s.recevoir(texte)
            if contrat["action"] == "reformuler":
                return self._repondre(bd, session_id, contrat, msg.reformulation(s.tentatives_reformulation))
            return self._apres_champ_confirme(bd, etat, session_id, utilisatrice_id, s, contrat)

        reponse = reconnaitre_confirmation(texte)

        if reponse is True:
            etat.champ_a_confirmer = None
            etat.refus_champ_consecutifs = 0
            contrat = {"intention": s.intention, "champs": dict(s.champs_confirmes),
                       "confiance": "a_confirmer" if s.premier_champ_manquant() else "haute",
                       "action": "demander_confirmation"}
            return self._apres_champ_confirme(bd, etat, session_id, utilisatrice_id, s, contrat)

        if reponse is False:
            etat.champ_a_confirmer = None
            etat.refus_champ_consecutifs += 1
            if etat.refus_champ_consecutifs > s.MAX_REFORMULATIONS:
                s.escaladee = True
                etat.champ_en_attente = None
                contrat = {"intention": s.intention, "champs": dict(s.champs_confirmes),
                           "confiance": "echec", "action": "escalade_humaine"}
                self._cloturer_session(bd, session_id, statut="incomplete")
                return self._repondre(bd, session_id, contrat, msg.escalade())
            s.champs_confirmes.pop(champ, None)
            etat.champ_en_attente = champ
            construire = CONSTRUCTEURS_REDEMANDE_CHAMP.get(champ, msg.demander_precision_montant_encore)
            contrat = {"intention": s.intention, "champs": dict(s.champs_confirmes),
                       "confiance": "a_confirmer", "action": "demander_confirmation"}
            return self._repondre(bd, session_id, contrat, construire())

        # Ni oui ni non : redemande la même relecture (voir limite dans la docstring).
        contrat = {"intention": s.intention, "champs": dict(s.champs_confirmes),
                   "confiance": "a_confirmer", "action": "demander_confirmation"}
        return self._repondre(bd, session_id, contrat,
                               msg.confirmer_champ(champ, s.champs_confirmes.get(champ)))

    def _repondre_lecture(self, bd, utilisatrice_id: int, contrat: dict) -> str:
        intention = contrat["intention"]
        if intention == "capital":
            capital = db.calculer_capital(bd, utilisatrice_id)
            return msg.reponse_capital(capital)
        if intention == "stock":
            article = contrat["champs"].get("article", "")
            ligne = db.consulter_stock(bd, utilisatrice_id, article)
            if ligne is None:
                return f"An ma {article} sɔrɔ."
            seuil_bas = ligne.quantite_actuelle <= (ligne.seuil_alerte or 0)
            return msg.reponse_stock(article, ligne.quantite_actuelle, seuil_bas)
        if intention == "fournisseur_consultation":
            fournisseur = contrat["champs"].get("fournisseur")
            if fournisseur:
                ligne = db.consulter_fournisseur(bd, utilisatrice_id, fournisseur)
                montant = ligne.montant_du if ligne else 0
                return msg.reponse_fournisseur_consultation(montant, fournisseur)
            return msg.reponse_fournisseur_consultation(db.total_du_aux_fournisseurs(bd, utilisatrice_id))
        if intention == "sfd_consultation":
            bilan = db.bilan_pret_sfd(bd, utilisatrice_id)
            return msg.reponse_sfd_consultation(bilan["reste_a_payer_fcfa"], bilan["prochaine_echeance_fcfa"])
        # "consultation" (ex. "combien ai-je vendu ce mois-ci ?") n'a pas
        # encore de vraie réponse construite (pas de requête par période) :
        # message honnête plutôt que de réutiliser continuer() à tort, qui
        # laissait croire qu'une action venait d'être enregistrée (bug réel,
        # test téléphone 2026-10-10).
        return msg.consultation_non_disponible()

    def _conclure(self, bd, session_id: int, utilisatrice_id: int, contrat: dict) -> str:
        intention = contrat["intention"]
        champs = contrat["champs"]
        if intention in ("vente", "depense"):
            db.enregistrer_transaction(bd, utilisatrice_id=utilisatrice_id, type_=intention,
                                        champs=champs, session_id=session_id)
        elif intention == "client" and "montant_fcfa" in champs:
            db.enregistrer_mouvement_client(bd, utilisatrice_id=utilisatrice_id,
                                             nom_client=champs.get("client", "inconnu"),
                                             montant_fcfa=champs["montant_fcfa"],
                                             est_un_paiement=champs.get("est_un_paiement", False),
                                             libelle="Paiement reçu" if champs.get("est_un_paiement") else "Nouvelle dette",
                                             session_id=session_id)
        elif intention == "capital_declaration":
            db.declarer_capital_initial(bd, utilisatrice_id=utilisatrice_id,
                                         montant_fcfa=champs.get("montant_fcfa", 0))
        elif intention == "capital_ajout":
            db.ajouter_au_capital(bd, utilisatrice_id=utilisatrice_id,
                                   montant_fcfa=champs.get("montant_fcfa", 0), session_id=session_id)
        elif intention == "vente_credit":
            # Une vente à crédit reste une vraie vente (chiffre d'affaires,
            # mouvement de stock) ET crée une créance client - les deux
            # écritures, jamais l'une sans l'autre (voir base_donnees.py).
            db.enregistrer_transaction(bd, utilisatrice_id=utilisatrice_id, type_="vente",
                                        champs=champs, session_id=session_id)
            db.enregistrer_mouvement_client(bd, utilisatrice_id=utilisatrice_id,
                                             nom_client=champs.get("client", "inconnu"),
                                             montant_fcfa=champs.get("montant_fcfa", 0),
                                             est_un_paiement=False,
                                             libelle=f"Vente à crédit : {champs.get('article', '')}".strip(),
                                             session_id=session_id)
        elif intention == "achat_credit":
            # Même principe côté achat : une dépense (qui augmente le stock,
            # voir enregistrer_transaction) ET une dette fournisseur.
            db.enregistrer_transaction(bd, utilisatrice_id=utilisatrice_id, type_="depense",
                                        champs=champs, session_id=session_id)
            db.enregistrer_mouvement_fournisseur(bd, utilisatrice_id=utilisatrice_id,
                                                  nom_fournisseur=champs.get("fournisseur", "inconnu"),
                                                  montant_fcfa=champs.get("montant_fcfa", 0),
                                                  est_un_paiement=False,
                                                  libelle=f"Achat à crédit : {champs.get('article', '')}".strip(),
                                                  session_id=session_id)
        elif intention == "fournisseur_paiement":
            db.enregistrer_mouvement_fournisseur(bd, utilisatrice_id=utilisatrice_id,
                                                  nom_fournisseur=champs.get("fournisseur", "inconnu"),
                                                  montant_fcfa=champs.get("montant_fcfa", 0),
                                                  est_un_paiement=True,
                                                  libelle="Paiement fournisseur",
                                                  session_id=session_id)
        elif intention == "stock_ecriture":
            db.enregistrer_mouvement_stock(bd, utilisatrice_id=utilisatrice_id,
                                            article=champs.get("article", ""),
                                            quantite=champs.get("quantite", 0),
                                            session_id=session_id)
        elif intention == "sfd_declaration":
            db.declarer_pret_sfd(bd, utilisatrice_id=utilisatrice_id,
                                  nom_sfd=champs.get("nom_sfd", "inconnu"),
                                  montant_total_fcfa=champs.get("montant_fcfa", 0),
                                  duree_mois=champs.get("duree_mois", 0),
                                  echeance_mensuelle_fcfa=champs.get("echeance_mensuelle_fcfa", 0),
                                  session_id=session_id)
        elif intention == "sfd_paiement":
            db.enregistrer_paiement_sfd(bd, utilisatrice_id=utilisatrice_id,
                                         montant_fcfa=champs.get("montant_fcfa", 0),
                                         session_id=session_id)
        self._cloturer_session(bd, session_id, statut="complete")
        return msg.enregistrement_confirme()

    def _cloturer_session(self, bd, session_id: int, statut: str) -> None:
        s = bd.get(db.SessionAppel, session_id)
        if s is not None:
            s.statut = statut
            s.date_fin = datetime.now(timezone.utc)
            bd.commit()

    def _repondre(self, bd, session_id: int, contrat: dict, message: str) -> dict:
        db.journaliser(bd, session_id=session_id, etape=contrat.get("intention") or "incompris",
                        confiance=contrat["confiance"], resultat=contrat["action"])
        audio = None
        if self._syntheser:
            try:
                audio = self._syntheser(message)
            except Exception:  # noqa: BLE001 : une panne TTS ne doit jamais faire échouer la réponse
                audio = None
        return {"contrat": contrat, "message": message, "audio": audio}
