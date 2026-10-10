"""Moteur de décision GERME Comptabilité (étape 5.1 du workplan).

Transforme un texte bambara transcrit (sortie ASR) en une transaction
comptable structurée, sans jamais passer par un LLM génératif : le test sur
42 modèles du sandbox CFA a confirmé qu'aucun ne comprend le bambara de façon
fiable (voir Rapport_Comprehension_Bambara_Sandbox). Ce moteur est donc un
système à règles, déterministe et testable unitairement, conformément à
Architecture_Technique_NGONI_NANA.docx section 3.3.

Architecture interne en 4 couches (une fonction/classe par couche) :
  1. reconnaitre_intention  -> dictionnaire_mots_cles.py
  2. extraire_entites       -> ce module
  3. extraction des nombres -> montants.py (réutilisé tel quel)
  4. Session                -> machine à états de ce module

Contrat de sortie (identique à celui du document d'architecture) : un objet
{"intention", "champs", "confiance", "action"}, pour pouvoir tester ce moteur
sur du texte seul, sans dépendre de l'ASR, du TTS ni de la téléphonie.
"""
from dataclasses import dataclass, field

from montants import ET, NUMERAUX, extraire_nombres, normaliser

from moteur.dictionnaire_mots_cles import EXCEPTIONS_NOMS_PROPRES, MOTS_CLES, _mot_present, reconnaitre_intention

# Conversion dɔrɔmɛ -> FCFA (1 dɔrɔmɛ = 5 FCFA). La plupart des montants sont
# énoncés en dɔrɔmɛ sans que le mot soit prononcé (voir montants.py) ; ce
# facteur reconstruit exactement montant_fcfa sur les 20 phrases vérifiées de
# phrases_reelles.csv (voir tests/test_moteur_decision.py). Reste un point
# ouvert de conception (voir README) : rien ne permet aujourd'hui de détecter
# dans le texte seul un montant qui serait énoncé directement en FCFA plutôt
# qu'en dɔrɔmɛ. D'où l'obligation de toujours faire confirmer le montant
# converti à l'utilisatrice (Cas 8 du parcours) avant de l'enregistrer.
FACTEUR_DOROME = 5

# Champs attendus par intention (couche 2, slot filling), tel que décrit dans
# le document d'architecture et le parcours utilisateur.
CHAMPS_ATTENDUS: dict[str, list[str]] = {
    "vente": ["article", "quantite", "montant_fcfa"],
    "depense": ["article", "montant_fcfa"],
    "client": ["client"],
    "capital": [],
    # "capital" (jagokun) seul = consultation, jamais d'écriture (voir
    # INTENTIONS_LECTURE_SEULE, agent_vocal.py). Pour déclarer ou ajuster le
    # capital, voir _affiner_intention_capital plus bas : deux intentions
    # séparées, chacune avec un vrai montant requis et une confirmation
    # avant écriture, contrairement à "capital" qui répond tout de suite.
    "capital_declaration": ["montant_fcfa"],
    "capital_ajout": ["montant_fcfa"],
    "stock": ["article"],
    "consultation": [],
}

# Mots grammaticaux bambara à ignorer lors de l'extraction de l'article ou du
# nom propre (ce qui reste une fois les nombres et les mots-clés retirés).
# Construit par balayage des 60 phrases de phrases_reelles.csv, complété par
# des variantes observées en test réel ("ne" pour "n" : ASR RobotsMali,
# 2026-10-05, faisait fuir "ne" dans l'article extrait : "ne saga" au lieu de
# "saga") ; à valider et compléter par une personne bambaraphone (R9), au
# même titre que le reste de ce dictionnaire.
MOTS_GRAMMATICAUX = {
    "n", "ne", "ka", "ye", "y", "ni", "be", "la", "na", "min", "fe", "de", "o",
    "a", "i", "in", "tun", "ke", "don", "son", "sonna", "olu", "to", "tora",
    "yere", "bee", "mogo",
    # "ma" : marqueur grammatical très courant (négation, objet indirect...),
    # aussi utilisé dans la négation "ma sɔn" (voir dictionnaire_mots_cles.
    # reconnaitre_confirmation). Ajouté après un test réel (2026-10-09) où
    # il se retrouvait dans l'article extrait.
    "ma",
    # "kan" : postposition ("sur"/"à", ex. "... jagokun kan" = "... sur le
    # capital"), jamais un nom de marchandise. Ajouté après un test réel
    # (2026-10-10) où il polluait l'article extrait ("kan" pris pour le
    # nom de l'article d'une dépense).
    "kan",
}

_TOUS_MOTS_CLES: set[str] = set()
for _mots in MOTS_CLES.values():
    _TOUS_MOTS_CLES.update(_mots)


def _mots_restants(texte: str) -> list[str]:
    """Tokens du texte une fois nombres, mots-clés et mots grammaticaux retirés.

    Heuristique volontairement simple (pas d'étiquetage grammatical réel) :
    sert de premier jet pour deviner l'article ou le nom propre en jeu. À
    remplacer par une vraie extraction d'entités si la précision observée en
    test ne suffit pas.
    """
    tokens = normaliser(texte).split()

    restants = []
    for tok in tokens:
        if tok.isdigit() or tok in MOTS_GRAMMATICAUX:
            continue
        # _mot_present (préfixe pour les racines >=4 lettres) : une variante
        # conjuguée d'un mot-clé ("feereli" pour "feere") doit être filtrée
        # comme le mot-clé lui-même, pas seulement une correspondance exacte
        # - sinon elle polluait l'article (bug réel, test téléphone
        # 2026-10-09 : "feereli" se retrouvait dans l'article extrait).
        if any(_mot_present(m, [tok]) for m in _TOUS_MOTS_CLES):
            continue
        # Retire aussi les tokens qui sont uniquement des mots-nombres
        # (kelen, fila, waa, kɛmɛ...), déjà capturés par extraire_nombres.
        if tok in NUMERAUX or tok in ET:
            continue
        restants.append(tok)
    return restants


def est_une_redite_numerique_fiable(texte: str) -> bool:
    """Vrai si l'énoncé ne contient QUE des nombres (et des mots-clés/mots

    grammaticaux), rien d'autre. Sert à distinguer une vraie redite de
    valeur (cas 9 : redire un montant sans dire "non" d'abord) d'un mot de
    bruit qui contiendrait un chiffre par coïncidence - ex. "hamaden fila
    don" contient "fila" (2), mais "hamaden"/"don" ne sont ni un chiffre ni
    un mot reconnu : accepter ce genre d'énoncé comme redite a déjà écrasé
    silencieusement un article confirmé avec du bruit (bug réel, test
    réel 2026-10-09, voir agent_vocal.py).
    """
    return bool(extraire_nombres(texte)) and not _mots_restants(texte)


def _affiner_intention_capital(texte: str, intention: str | None) -> str | None:
    """"jagokun" (capital) peut vouloir dire trois choses différentes : juste

    consulter, déclarer un capital de départ, ou en ajouter. Un simple
    mot-clé ne suffit pas à les distinguer (même mot dans les trois cas) :
    affiné après coup, via un marqueur spécifique ("fara" = ajouter) ou la
    présence d'un chiffre (probablement une déclaration plutôt qu'une
    question). Avant cet ajout, "capital" ne faisait QUE consulter : tout
    chiffre prononcé à côté ("mon capital est de 50 000") était
    silencieusement ignoré (constaté en test réel, 2026-10-09), alors que le
    corpus de référence (phrases_reelles.csv, P15/P16) prévoyait bien ces
    deux cas depuis le début.
    """
    if intention != "capital":
        return intention
    tokens = normaliser(texte).split()
    if "fara" in tokens:
        return "capital_ajout"
    if extraire_nombres(texte):
        return "capital_declaration"
    return "capital"


def extraire_entites(texte: str, intention: str | None) -> dict:
    """Couche 2 + 3 : isole article/quantité/montant/client selon l'intention reconnue."""
    champs: dict = {}
    nombres = extraire_nombres(texte)
    mots = _mots_restants(texte)

    if intention in ("vente", "depense", "capital", "capital_declaration", "capital_ajout", "client"):
        if nombres:
            montant_brut = max(nombres)
            champs["montant_fcfa"] = montant_brut * FACTEUR_DOROME
            champs["unite_dite"] = "dorome"
        if intention == "vente" and len(nombres) >= 2:
            champs["quantite"] = min(nombres)

    if intention == "stock" and nombres:
        champs["quantite"] = min(nombres)

    if intention in ("vente", "depense", "stock") and mots:
        champs["article"] = " ".join(mots)
    if intention == "client" and mots:
        champs["client"] = mots[0]
        # "juru" seul = l'utilisatrice déclare une nouvelle dette (P13 : "Awa
        # me doit 10000 francs"). "juru" + "sara" (payer) = un paiement reçu
        # qui RÉDUIT la dette (P14 : "Fanta m'a remboursé..., a y'o sara").
        # Signal tiré des 60 phrases vérifiées, voir tests/test_moteur_decision.py.
        tokens_bruts = normaliser(texte).split()
        champs["est_un_paiement"] = any(t.startswith("sara") and t not in EXCEPTIONS_NOMS_PROPRES
                                         for t in tokens_bruts)

    return champs


def analyser(texte: str) -> dict:
    """Fonction pure couches 1 à 3 : un texte -> le contrat de sortie du moteur.

    Ne gère pas la reformulation ni l'escalade (couche 4, voir Session) :
    c'est l'analyse d'un seul énoncé, indépendante de tout historique de
    session, pour rester testable isolément (voir Architecture_Technique
    section 9, stratégie de test).
    """
    intention = reconnaitre_intention(texte)
    if intention is None:
        return {"intention": None, "champs": {}, "confiance": "echec", "action": "reformuler"}
    intention = _affiner_intention_capital(texte, intention)

    champs = extraire_entites(texte, intention)
    attendus = CHAMPS_ATTENDUS[intention]
    manquants = [c for c in attendus if c not in champs]

    if manquants:
        return {
            "intention": intention,
            "champs": champs,
            "confiance": "a_confirmer",
            "action": "demander_confirmation",
        }

    return {
        "intention": intention,
        "champs": champs,
        "confiance": "haute",
        "action": "demander_confirmation" if attendus else "enregistrer",
    }


@dataclass
class Session:
    """Couche 4 : machine à états d'une session utilisatrice.

    Règles reprises du parcours utilisateur (User_Workflow_NGONI_NANA,
    cas 7/8/9/10) : jamais plus de 2 reformulations avant escalade humaine ;
    rien n'est marqué prêt à enregistrer avant une confirmation explicite ;
    une correction ne doit annuler que le champ corrigé, pas toute la
    transaction (les champs déjà confirmés restent en mémoire).
    """

    intention: str | None = None
    champs_confirmes: dict = field(default_factory=dict)
    tentatives_reformulation: int = 0
    escaladee: bool = False
    confirmee: bool = False

    MAX_REFORMULATIONS = 2

    def recevoir(self, texte: str) -> dict:
        """Traite un énoncé de l'utilisatrice et renvoie le contrat de sortie du moteur.

        Une intention déjà active dans la session reste valable d'un tour à
        l'autre : la plupart des réponses de l'utilisatrice à une question du
        système (« quel montant ? ») ne répètent pas le mot-clé d'action
        (« vente »), elles ne contiennent qu'un nombre ou un nom. Ne retenir
        que les énoncés qui reconnaissent une intention FRAÎCHE traiterait ces
        réponses normales comme des incompréhensions (cas 7), à tort.
        """
        if self.escaladee:
            return {"intention": self.intention, "champs": dict(self.champs_confirmes),
                     "confiance": "echec", "action": "escalade_humaine"}

        intention = reconnaitre_intention(texte) or self.intention
        intention = _affiner_intention_capital(texte, intention)
        nouveaux_champs = extraire_entites(texte, intention) if intention else {}

        # "Rien d'extrait" ne veut dire "pas compris" que si l'intention
        # attend au moins un champ (vente, dépense...). Pour une intention
        # qui n'en attend aucun (capital en pure consultation, consultation
        # elle-même), ne rien extraire est normal, pas un échec - bug réel
        # trouvé en test (2026-10-09) : "n ka jagokun" seul (consulter le
        # capital, sans aucun chiffre) était rejeté comme incompris alors que
        # l'intention était correctement reconnue.
        champ_requis = bool(CHAMPS_ATTENDUS.get(intention)) if intention else False
        if intention is None or (not nouveaux_champs and champ_requis):
            self.tentatives_reformulation += 1
            if self.tentatives_reformulation > self.MAX_REFORMULATIONS:
                self.escaladee = True
                return {"intention": self.intention, "champs": dict(self.champs_confirmes),
                         "confiance": "echec", "action": "escalade_humaine"}
            return {"intention": self.intention, "champs": dict(self.champs_confirmes),
                     "confiance": "echec", "action": "reformuler"}

        self.tentatives_reformulation = 0
        self.intention = intention
        self.champs_confirmes.update(nouveaux_champs)
        manquants = [c for c in CHAMPS_ATTENDUS[intention] if c not in self.champs_confirmes]
        return {"intention": intention, "champs": dict(self.champs_confirmes),
                 "confiance": "a_confirmer" if manquants else "haute",
                 "action": "demander_confirmation"}

    def confirmer(self) -> dict:
        """Confirmation finale vocale de l'utilisatrice : seul moment où l'écriture est autorisée.

        Avant cet appel, rien n'est enregistré (principe de non-perte
        silencieuse, cas 10 du parcours : une coupure réseau avant ce point
        ne doit jamais produire de transaction à moitié enregistrée).
        """
        self.confirmee = True
        return {"intention": self.intention, "champs": self.champs_confirmes,
                 "confiance": "haute", "action": "enregistrer"}

    def corriger(self, champ: str, texte: str) -> dict:
        """Cas 9 : ne redemande/corrige que le champ signalé, garde le reste en mémoire."""
        self.champs_confirmes.pop(champ, None)
        nouveaux = extraire_entites(texte, self.intention)
        if champ in nouveaux:
            self.champs_confirmes[champ] = nouveaux[champ]
        return {"intention": self.intention, "champs": dict(self.champs_confirmes),
                 "confiance": "a_confirmer", "action": "demander_confirmation"}

    def premier_champ_manquant(self) -> str | None:
        """Le premier champ encore manquant pour l'intention en cours, ou None si complet."""
        for champ in CHAMPS_ATTENDUS.get(self.intention, []):
            if champ not in self.champs_confirmes:
                return champ
        return None

    def combler_champ(self, champ: str, texte: str) -> dict:
        """Renseigne précisément UN champ déjà identifié comme manquant ou à corriger.

        Différent de `corriger` : n'applique pas l'heuristique générale
        "un seul nombre = forcément le montant" (extraire_entites), qui ne
        peut jamais remplir "quantite" à partir d'un énoncé bref ne
        contenant qu'un chiffre. Ici, le champ visé est déjà connu (on l'a
        explicitement demandé à l'utilisatrice), donc un chiffre isolé peut
        directement remplir CE champ-là, quel qu'il soit. Corrige le bug
        réel (2026-10-09) : redonner uniquement le montant demandé
        n'aboutissait jamais si la quantité restait aussi manquante, sans
        que l'utilisatrice sache qu'il fallait aussi la redire.
        """
        nombres = extraire_nombres(texte)
        mots = _mots_restants(texte)

        if champ == "montant_fcfa" and nombres:
            self.champs_confirmes["montant_fcfa"] = max(nombres) * FACTEUR_DOROME
            self.champs_confirmes["unite_dite"] = "dorome"
        elif champ == "quantite" and nombres:
            # min(), pas max() : coherent avec extraire_entites (le montant
            # est toujours le plus grand des deux chiffres, la quantite le
            # plus petit). Avec un seul chiffre les deux sont identiques,
            # donc ca ne change rien au cas courant (juste un nombre redit) ;
            # mais si l'enonce contient aussi un autre chiffre (ex. parce que
            # la phrase entiere a ete repetee), max() assignait a tort le
            # plus gros chiffre a la quantite (bug reel, 2026-10-09).
            self.champs_confirmes["quantite"] = min(nombres)
        elif champ in ("article", "client") and mots:
            self.champs_confirmes[champ] = " ".join(mots) if champ == "article" else mots[0]
        else:
            return {"intention": self.intention, "champs": dict(self.champs_confirmes),
                     "confiance": "echec", "action": "reformuler"}

        manquant = self.premier_champ_manquant()
        return {"intention": self.intention, "champs": dict(self.champs_confirmes),
                 "confiance": "haute" if manquant is None else "a_confirmer",
                 "action": "demander_confirmation"}
