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

from montants import extraire_nombres

from moteur import base_donnees as db
from moteur import messages_bambara as msg
from moteur.dictionnaire_mots_cles import reconnaitre_confirmation
from moteur.moteur_decision import Session

# Intentions qui ne font que lire des données déjà en base : rien à écrire, et
# donc rien à faire confirmer par un "oui" avant de répondre (cas 4 et 6 du
# parcours). "client" reste à part : consulter une dette ne demande pas de
# confirmation, mais enregistrer un paiement, oui.
INTENTIONS_LECTURE_SEULE = {"capital", "consultation", "stock"}

CONSTRUCTEURS_CONFIRMATION = {
    "vente": msg.confirmation_vente,
    "depense": msg.confirmation_depense,
    "client": msg.confirmation_client,
}


@dataclass
class _EtatSession:
    session_moteur: Session = field(default_factory=Session)
    en_attente_confirmation: bool = False
    champ_en_correction: str | None = None


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

    def traiter_audio(self, session_id: int, utilisatrice_id: int, chemin_audio: str) -> dict:
        if self._transcrire is None:
            raise RuntimeError("Aucune fonction de transcription fournie à cet AgentVocal.")
        texte = self._transcrire(chemin_audio)
        return self.traiter_texte(session_id, utilisatrice_id, texte)

    def traiter_texte(self, session_id: int, utilisatrice_id: int, texte: str) -> dict:
        etat = self._etats.setdefault(session_id, _EtatSession())
        bd = self._session_factory()
        try:
            return self._traiter_texte_interne(bd, etat, session_id, utilisatrice_id, texte)
        finally:
            bd.close()

    def _traiter_texte_interne(self, bd, etat: "_EtatSession", session_id: int,
                                utilisatrice_id: int, texte: str) -> dict:
        s = etat.session_moteur

        if etat.en_attente_confirmation:
            reponse = reconnaitre_confirmation(texte)
            if reponse is True:
                contrat = s.confirmer()
                message = self._conclure(bd, session_id, utilisatrice_id, contrat)
                etat.en_attente_confirmation = False
                return self._repondre(bd, session_id, contrat, message)
            if reponse is False:
                champ = etat.champ_en_correction or (list(s.champs_confirmes)[-1] if s.champs_confirmes else None)
                if champ is None:
                    contrat = {"intention": s.intention, "champs": {}, "confiance": "echec", "action": "reformuler"}
                    return self._repondre(bd, session_id, contrat, msg.demander_precision_montant())
                contrat = s.corriger(champ, "")  # vide : on redemandera la valeur au tour suivant
                etat.en_attente_confirmation = False
                etat.champ_en_correction = champ
                return self._repondre(bd, session_id, contrat, msg.reformulation(1))
            # Ni oui ni non. Cas 9 (redire un nombre directement, sans dire
            # "non" d'abord) : seulement si un VRAI nombre est prononcé,
            # jamais sur un mot isolé seul. Régression réelle trouvée en test
            # (2026-10-09) : un mot de bruit ASR (ni oui/non, ni mot-clé, pas
            # de nombre) était jusqu'ici traité comme une correction directe
            # de l'article, l'écrasant silencieusement avec du bruit et
            # redemandant confirmation avec ce faux article - perçu comme
            # "la même question qui boucle", avec un vrai risque d'enregistrer
            # la mauvaise marchandise si un "oui" finissait par être reconnu.
            if extraire_nombres(texte):
                etat.en_attente_confirmation = False
            else:
                s.tentatives_reformulation += 1
                if s.tentatives_reformulation > s.MAX_REFORMULATIONS:
                    s.escaladee = True
                    contrat = {"intention": s.intention, "champs": dict(s.champs_confirmes),
                               "confiance": "echec", "action": "escalade_humaine"}
                    self._cloturer_session(bd, session_id, statut="incomplete")
                    return self._repondre(bd, session_id, contrat, msg.escalade())
                contrat = {"intention": s.intention, "champs": dict(s.champs_confirmes),
                           "confiance": "a_confirmer", "action": "demander_confirmation"}
                construire = CONSTRUCTEURS_CONFIRMATION.get(s.intention)
                message = construire(s.champs_confirmes) if construire else msg.demander_precision_montant()
                return self._repondre(bd, session_id, contrat, message)

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
        else:
            message = msg.demander_precision_montant()
        return self._repondre(bd, session_id, contrat, message)

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
        return msg.continuer()

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
                                             est_un_paiement=champs.get("est_un_paiement", False))
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
