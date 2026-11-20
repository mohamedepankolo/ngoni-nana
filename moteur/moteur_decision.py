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

from moteur.dictionnaire_mots_cles import (
    EXCEPTIONS_NOMS_PROPRES,
    MOTS_CLES,
    _mot_present,
    reconnaitre_choix_menu,
    reconnaitre_intention,
)

# Conversion dɔrɔmɛ -> FCFA (1 dɔrɔmɛ = 5 FCFA). La plupart des montants sont
# énoncés en dɔrɔmɛ sans que le mot soit prononcé (voir montants.py) ; ce
# facteur reconstruit exactement montant_fcfa sur les 20 phrases vérifiées de
# phrases_reelles.csv (voir tests/test_moteur_decision.py). Reste un point
# ouvert de conception (voir README) : rien ne permet aujourd'hui de détecter
# dans le texte seul un montant qui serait énoncé directement en FCFA plutôt
# qu'en dɔrɔmɛ. D'où l'obligation de toujours faire confirmer le montant
# converti à l'utilisatrice (Cas 8 du parcours) avant de l'enregistrer.
FACTEUR_DOROME = 5

# Mots qui, dits explicitement à côté d'un nombre, signalent que ce nombre EST
# déjà le montant FCFA (pas un montant en dɔrɔmɛ à multiplier par
# FACTEUR_DOROME) : "franc(s)"/"FCFA" sont des emprunts au français déjà
# présents comme forme ASR réaliste dans ce projet (tests/test_montants.py,
# "Mariam ka jɛnɛ ye 2500 francs", "2 500 FCFA") - pas un mot bambara inventé.
# Bug réel signalé en test (2026-11-17, Mohamed) : un montant dit avec ce
# marqueur explicite ("1000 francs") subissait quand même le x5 dɔrɔmɛ,
# contrairement à la convention du cahier des charges (dɔrɔmɛ SANS dire le
# mot, voir montants.py) - un marqueur franc/FCFA explicite dit le contraire :
# le nombre EST le montant FCFA, pas un nombre de dɔrɔmɛ.
MOTS_MONTANT_LITTERAL = {"franc", "francs", "fcfa"}


def _montant_est_litteral(texte: str) -> bool:
    """Vrai si le nombre de `texte` doit être pris comme montant FCFA direct

    (pas de x5 dɔrɔmɛ) : soit un chiffre tapé tel quel (canal clavier, voir
    Session.combler_champ), soit un nombre dit avec franc(s)/FCFA explicite
    à côté (voir MOTS_MONTANT_LITTERAL).
    """
    if texte.strip().isdigit():
        return True
    return bool(set(normaliser(texte).split()) & MOTS_MONTANT_LITTERAL)

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
    # Les 4 intentions suivantes (2026-11-17, script à 9 choix) ne sont
    # atteignables que par le chiffre du menu (voir MENU_NUMERIQUE,
    # dictionnaire_mots_cles.py) : pas de mot-clé bambara validé pour
    # "crédit"/"fournisseur"/"échéance" pour l'instant.
    "vente_credit": ["article", "quantite", "montant_fcfa", "client"],
    "achat_credit": ["article", "montant_fcfa", "fournisseur"],
    "fournisseur_paiement": ["fournisseur", "montant_fcfa"],
    # Consultation du reste à payer aux fournisseurs : le nom du fournisseur
    # est optionnel (si absent, réponse = total tous fournisseurs confondus,
    # voir AgentVocal._repondre_lecture), donc aucun champ n'est STRICTEMENT
    # requis - même logique que "capital"/"stock" en lecture.
    "fournisseur_consultation": [],
    # Déclaration ou réapprovisionnement de stock (distinct de "stock", qui
    # reste la consultation - voir _affiner_intention_stock) : l'un ou
    # l'autre est décidé à l'écriture (base_donnees.enregistrer_mouvement_stock),
    # selon qu'une ligne de stock existe déjà pour cet article, pas ici.
    "stock_ecriture": ["article", "quantite"],
    # Items 10-12 (SFD, 2026-11-17, documentation Fadima - "Fiche 5, Suivi
    # des remboursements SFD") : même principe que 4-9, chiffre de menu
    # uniquement (MENU_NUMERIQUE, dictionnaire_mots_cles.py). "nom_sfd" est
    # un champ à part de "fournisseur" (voir messages_bambara.NOMS_CHAMPS_
    # BAMBARA) : "fournisseur" désigne un fournisseur de marchandises, pas
    # une institution de microfinance - réutiliser ce champ créerait une
    # confusion sémantique réelle, pas seulement un style différent.
    # Un seul prêt SFD actif supposé (comme capital_initial) : pas de nom à
    # redemander pour "sfd_paiement"/"sfd_consultation".
    "sfd_declaration": ["nom_sfd", "montant_fcfa", "duree_mois", "echeance_mensuelle_fcfa"],
    "sfd_paiement": ["montant_fcfa"],
    "sfd_consultation": [],
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
    # Un énoncé qui N'EST QUE le chiffre du menu numérique (R2) ne doit pas
    # être pris pour un montant déclaré : "3" tout seul sélectionne la
    # consultation du capital (voir MENU_NUMERIQUE), ce n'est pas "mon
    # capital est de 3 dɔrɔmɛ". Vérifié avant extraire_nombres, qui verrait
    # sinon ce même chiffre comme un montant (bug réel, trouvé en testant le
    # menu numérique : "3" tapé seul devenait à tort "capital_declaration").
    if reconnaitre_choix_menu(texte) == "capital":
        return "capital"
    if extraire_nombres(texte):
        return "capital_declaration"
    return "capital"


def _affiner_intention_stock(texte: str, intention: str | None) -> str | None:
    """"bolo" (stock) peut vouloir dire consulter le stock d'un article, ou en

    déclarer/ajouter une quantité (item 8 du menu, 2026-11-17) - même
    ambiguïté et même principe de résolution que _affiner_intention_capital
    ci-dessus : un chiffre prononcé à côté du mot signale une écriture, pas
    une simple question. Le chiffre du menu (8 ou 9, voir MENU_NUMERIQUE)
    résout déjà l'ambiguïté sans passer par ici (reconnaitre_choix_menu
    renvoie directement "stock_ecriture" ou "stock"), donc ce repli ne joue
    que pour le mot-clé parlé libre ("bolo").
    """
    if intention != "stock":
        return intention
    if reconnaitre_choix_menu(texte) == "stock":
        return "stock"
    if extraire_nombres(texte):
        return "stock_ecriture"
    return "stock"


def extraire_entites(texte: str, intention: str | None) -> dict:
    """Couche 2 + 3 : isole article/quantité/montant/client/fournisseur selon l'intention reconnue."""
    champs: dict = {}
    # Si l'énoncé N'EST QUE le chiffre qui vient de sélectionner CETTE
    # intention au menu (ex. "4" pour choisir vente_credit), ce chiffre ne
    # doit jamais être pris pour une valeur métier (montant, quantité...) -
    # bug réel trouvé en ajoutant les items 4 à 8 (2026-11-17) : "1" seul
    # faisait déjà silencieusement enregistrer montant_fcfa=5 (1 dɔrɔmɛ*5)
    # pour "vente", sans jamais redemander le vrai montant tant qu'aucun
    # autre chiffre n'était redit ensuite (champs_confirmes le considérait
    # comme déjà rempli). Seul _affiner_intention_capital avait un garde-fou
    # pour ce cas, limité au choix "capital" ; généralisé ici à toutes les
    # intentions plutôt que dupliqué pour chacune des 6 nouvelles.
    nombres = [] if reconnaitre_choix_menu(texte) == intention else extraire_nombres(texte)
    mots = _mots_restants(texte)

    intentions_avec_montant = (
        "vente", "depense", "capital", "capital_declaration", "capital_ajout",
        "client", "vente_credit", "achat_credit", "fournisseur_paiement",
        # "sfd_declaration" : seul montant_fcfa (le total du crédit) est
        # extrait ici ; "duree_mois" et "echeance_mensuelle_fcfa" ne le sont
        # JAMAIS depuis cette phrase initiale (voir combler_champ plus bas) -
        # trois nombres dont deux de forme "montant" (total et mensualité) et
        # un petit ("durée en mois") ne peuvent pas se désambiguïser de façon
        # fiable par magnitude seule, contrairement au couple montant/quantité
        # déjà géré ailleurs dans cette fonction.
        "sfd_declaration", "sfd_paiement",
    )
    if intention in intentions_avec_montant:
        if nombres:
            montant_brut = max(nombres)
            if _montant_est_litteral(texte):
                champs["montant_fcfa"] = montant_brut
                champs["unite_dite"] = "fcfa"
            else:
                champs["montant_fcfa"] = montant_brut * FACTEUR_DOROME
                champs["unite_dite"] = "dorome"
        if intention in ("vente", "vente_credit") and len(nombres) >= 2:
            champs["quantite"] = min(nombres)

    if intention in ("stock", "stock_ecriture") and nombres:
        champs["quantite"] = min(nombres)

    if intention in ("vente", "depense", "stock", "stock_ecriture", "vente_credit", "achat_credit") and mots:
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
    # fournisseur_paiement/fournisseur_consultation n'ont pas de mot-clé
    # bambara (voir CHAMPS_ATTENDUS) : atteints uniquement par chiffre de
    # menu, "mots" ne contient alors que le nom propre dit à côté du chiffre
    # (ex. "6 Amadou") - même logique que "client" plus haut (premier mot
    # restant = le nom). "client" du côté vente_credit n'est volontairement
    # pas extrait ici : "mots" a déjà été pris par "article" juste au-dessus,
    # le nom du client sera redemandé séparément (voir
    # CHAMPS_ATTENDUS["vente_credit"], AgentVocal._combler_champ_en_attente).
    if intention in ("fournisseur_paiement", "fournisseur_consultation") and mots:
        champs["fournisseur"] = mots[0]
    # "sfd_declaration" : seul le nom du SFD est extrait d'une éventuelle
    # phrase initiale (ex. "10 Soro microfinance") - duree_mois et
    # echeance_mensuelle_fcfa sont toujours redemandés séparément (voir
    # intentions_avec_montant plus haut et combler_champ, même fichier).
    if intention == "sfd_declaration" and mots:
        champs["nom_sfd"] = " ".join(mots)

    return champs


def analyser(texte: str) -> dict:
    """Fonction pure couches 1 à 3 : un texte -> le contrat de sortie du moteur.

    Ne gère pas la reformulation ni l'escalade (couche 4, voir Session) :
    c'est l'analyse d'un seul énoncé, indépendante de tout historique de
    session, pour rester testable isolément (voir Architecture_Technique
    section 9, stratégie de test).
    """
    intention = reconnaitre_intention(texte) or reconnaitre_choix_menu(texte)
    if intention is None:
        return {"intention": None, "champs": {}, "confiance": "echec", "action": "reformuler"}
    intention = _affiner_intention_capital(texte, intention)
    intention = _affiner_intention_stock(texte, intention)

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

        # Le choix de menu (chiffre 1-6) n'est consulté que si AUCUNE intention
        # n'est encore active cette session : sinon un chiffre isolé donné en
        # réponse à un champ demandé ("quelle quantité ?" -> "1") serait repris
        # à tort pour un nouveau choix de menu plutôt que la valeur du champ
        # (collision chiffre de menu / chiffre de champ, voir
        # dictionnaire_mots_cles.reconnaitre_choix_menu).
        intention = reconnaitre_intention(texte)
        if intention is None and self.intention is None:
            intention = reconnaitre_choix_menu(texte)
        intention = intention or self.intention
        intention = _affiner_intention_capital(texte, intention)
        intention = _affiner_intention_stock(texte, intention)
        nouveaux_champs = extraire_entites(texte, intention) if intention else {}

        # "Rien d'extrait" ne veut dire "pas compris" que si l'intention
        # attend au moins un champ (vente, dépense...). Pour une intention
        # qui n'en attend aucun (capital en pure consultation, consultation
        # elle-même), ne rien extraire est normal, pas un échec - bug réel
        # trouvé en test (2026-10-09) : "n ka jagokun" seul (consulter le
        # capital, sans aucun chiffre) était rejeté comme incompris alors que
        # l'intention était correctement reconnue. Même chose pour un chiffre
        # de menu qui vient tout juste de sélectionner CETTE intention (ex.
        # "4" pour vente_credit) : rien n'est encore extrait (le chiffre
        # lui-même ne compte plus pour un montant, voir extraire_entites),
        # c'est une sélection réussie, pas un échec de compréhension - bug
        # réel trouvé en ajoutant les items 4 à 8 (2026-11-17) : sans ce
        # garde-fou, choisir une action au chiffre seul (ex. "1") déclenchait
        # tout de suite "je n'ai pas compris" avant même de pouvoir demander
        # le premier champ manquant.
        vient_du_choix_menu = reconnaitre_choix_menu(texte) == intention
        champ_requis = bool(CHAMPS_ATTENDUS.get(intention)) if intention else False
        if intention is None or (not nouveaux_champs and champ_requis and not vient_du_choix_menu):
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
            # Voir _montant_est_litteral : un chiffre arabe tapé tel quel
            # (clavier numérique de l'appli, #champSaisie) OU un nombre dit
            # avec franc(s)/FCFA explicite est un montant FCFA direct, jamais
            # un montant en dɔrɔmɛ - contrairement à la voix sans ce marqueur
            # (où le dɔrɔmɛ est la convention orale réelle, validée sur
            # phrases_reelles.csv). Bug réel signalé en test (2026-11-17,
            # clavier) : le clavier appliquait quand même le x5, donc taper
            # 1000 enregistrait 5000 FCFA sans que la relecture vocale (qui
            # redit le même chiffre) ne le révèle - puis (même jour, re-signalé)
            # le même x5 pour un montant dit à voix haute avec "francs"
            # explicite ("1000 francs" -> 5000 prononcé).
            if _montant_est_litteral(texte):
                self.champs_confirmes["montant_fcfa"] = max(nombres)
                self.champs_confirmes["unite_dite"] = "fcfa"
            else:
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
        elif champ in ("article", "client", "fournisseur") and mots:
            self.champs_confirmes[champ] = " ".join(mots) if champ == "article" else mots[0]
        elif champ == "nom_sfd" and mots:
            # Jointure complète (comme "article"), pas mots[0] (comme
            # "client"/"fournisseur") : le nom d'une institution de
            # microfinance est souvent composé de plusieurs mots.
            self.champs_confirmes["nom_sfd"] = " ".join(mots)
        elif champ == "duree_mois" and nombres:
            # Un nombre de mois, pas un montant : jamais de conversion dorome
            # ici, contrairement à montant_fcfa/echeance_mensuelle_fcfa.
            self.champs_confirmes["duree_mois"] = min(nombres)
        elif champ == "echeance_mensuelle_fcfa" and nombres:
            # Montant FCFA comme montant_fcfa : même convention dorome/
            # littéral (_montant_est_litteral), une échéance mensuelle se
            # dit aussi naturellement en dɔrɔmɛ à voix haute.
            if _montant_est_litteral(texte):
                self.champs_confirmes["echeance_mensuelle_fcfa"] = max(nombres)
            else:
                self.champs_confirmes["echeance_mensuelle_fcfa"] = max(nombres) * FACTEUR_DOROME
        else:
            return {"intention": self.intention, "champs": dict(self.champs_confirmes),
                     "confiance": "echec", "action": "reformuler"}

        manquant = self.premier_champ_manquant()
        return {"intention": self.intention, "champs": dict(self.champs_confirmes),
                 "confiance": "haute" if manquant is None else "a_confirmer",
                 "action": "demander_confirmation"}
