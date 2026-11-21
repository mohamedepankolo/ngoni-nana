"""Dictionnaire de mots-clés bambara pour la reconnaissance d'intention (R9).

Couche 1 du moteur de décision (voir Architecture_Technique_NGONI_NANA.docx,
section 3.3) : associe un texte bambara transcrit à l'une des 6 actions du
parcours (vente, depense, capital, client, stock, consultation).

Construit à partir des 60 phrases réelles vérifiées (phrases_reelles.csv) et
de l'exemple donné dans le document d'architecture ("feere" = vente,
"jagokun" = capital). Comme pour montants.py, ces mots-clés et leurs variantes
restent À VALIDER par une personne bambaraphone (R9) : certains n'ont qu'un ou
deux témoins dans le corpus actuel.

Limite connue, observée dans le corpus lui-même : la frontière entre "achat"
(payer pour obtenir une marchandise) et "depense" (payer pour un service) est
floue même dans l'annotation de référence (ex. l'achat d'emballages est
annoté "depense"). Le parcours utilisateur ne propose de toute façon que 5
actions au menu (vente, depense, capital, client, stock) : "achat" est donc
traité ici comme un cas de "depense", pas comme une 6e action.
"""
from montants import ET, NUMERAUX, extraire_nombres, normaliser

# Ordre de priorité quand plusieurs intentions correspondent à la fois dans la
# même phrase (ex. une question sur une dette contient aussi "juru").
ORDRE_PRIORITE = ["consultation", "client", "vente", "depense", "capital", "stock"]

MOTS_CLES: dict[str, list[str]] = {
    # Marqueurs interrogatifs : une question prime toujours sur le mot-clé
    # métier qu'elle contient (ex. "combien ai-je VENDU" n'est pas une vente).
    # "jɔn" (qui/lequel) est stocké normalisé ("jon", voir montants.normaliser).
    # "jonw" : variante avec marque du pluriel, observée en test réel
    # (RobotsMali/soloni-be-kalan-v0, 2026-10-06).
    "consultation": ["joli", "jon", "jonw"],
    # "juru" = dette/créance (le préfixe absorbe la variante "jurumu" du corpus).
    "client": ["juru"],
    # "feere" = vendre/vendu, couvre aussi "feerelen" (participe). "fere" (un
    # seul e) : variante ASR observée à 4 reprises en test réel (RobotsMali,
    # 2026-10-06, sur 3 locutrices différentes), pas une erreur isolée.
    "vente": ["feere", "fere"],
    # "sara" = payer ; "san" = acheter (englobe "achat", voir note ci-dessus).
    # "musaka" = dépense (nom) : mot transmis par Fadima le 2026-11-21 pour
    # l'étiquette du bouton menu item 2 (voir web/index.html) - ajouté ici en
    # synonyme de "sara" (verbe payer), pas en remplacement : décision
    # explicite de Mohamed de garder les deux formes reconnues à l'oral.
    "depense": ["sara", "san", "musaka"],
    # "jagokun" = capital, cité explicitement dans le document d'architecture.
    "capital": ["jagokun"],
    # "bolo" ("en ma possession"), "tora" (rester) : signaux les plus faibles
    # du dictionnaire, absents d'un des 3 témoins du corpus (P19c). À
    # renforcer en priorité lors de la validation linguistique (R9).
    # "minaw koura" : mot composé transmis par Fadima le 2026-11-21 pour
    # l'étiquette du bouton menu item 9 (consultation stock). Ajouté en
    # synonyme de "bolo"/"tora", pas en remplacement (même décision que pour
    # "musaka" ci-dessus). Volontairement le mot COMPOSÉ ("minaw koura"), pas
    # le seul "minaw" : "Minaw" (sans "koura") est le mot distinct donné pour
    # l'item 8 (stock_ecriture, écrire un mouvement) - un simple "minaw"
    # confondrait les deux intentions (voir _mot_present ci-dessous, qui sait
    # matcher une séquence de plusieurs tokens pour ce cas).
    "stock": ["bolo", "tora", "minaw koura"],
}


# Prénoms maliens courants qui, en préfixe, collisionnent avec une racine de
# mot-clé (ex. "Sarata"/"Saran" commencent comme "sara" = payer) : un énoncé
# qui ne fait que nommer un ou une cliente ne doit pas être pris pour une
# dépense. Liste volontairement restreinte à des collisions réellement
# observées ; à compléter si une personne bambaraphone en identifie d'autres
# (R9), pas une liste exhaustive de prénoms.
EXCEPTIONS_NOMS_PROPRES = {"sarata", "saran"}


def _un_mot_present(mot_cle: str, tokens: list[str]) -> bool:
    """Un token du texte correspond-il à ce mot-clé simple (un seul mot) ?

    Préfixe pour absorber les suffixes bambara (ex. "feere" -> "feerelen"),
    mais exact pour les racines de moins de 4 lettres, trop courtes pour un
    préfixe sans faux positif (ex. "san" ne doit pas matcher à l'intérieur de
    "sanɲɔgɔn", qui normalisé devient "sanyogon").
    """
    if len(mot_cle) < 4:
        return mot_cle in tokens
    return any(tok.startswith(mot_cle) and tok not in EXCEPTIONS_NOMS_PROPRES for tok in tokens)


def _mot_present(mot_cle: str, tokens: list[str]) -> bool:
    """`mot_cle` (un mot, ou plusieurs séparés par un espace) apparaît-il dans `tokens` ?

    Un mot composé (ex. "minaw koura", voir MOTS_CLES["stock"]) doit
    correspondre à une séquence de tokens CONSÉCUTIFS, pas à ses mots pris
    séparément n'importe où dans la phrase - sinon "minaw" seul (mot distinct
    de l'item 8, voir commentaire sur MOTS_CLES) déclencherait à tort cette
    entrée dès qu'il apparaît, même sans "koura" à proximité.
    """
    mots = mot_cle.split()
    if len(mots) == 1:
        return _un_mot_present(mot_cle, tokens)
    return any(
        all(_un_mot_present(mots[j], [tokens[i + j]]) for j in range(len(mots)))
        for i in range(len(tokens) - len(mots) + 1)
    )


def intentions_correspondantes(texte: str) -> list[str]:
    """Toutes les intentions dont au moins un mot-clé apparaît dans le texte."""
    tokens = normaliser(texte).split()
    return [intention for intention, mots in MOTS_CLES.items()
            if any(_mot_present(m, tokens) for m in mots)]


def reconnaitre_intention(texte: str) -> str | None:
    """L'intention la plus probable, selon l'ordre de priorité, ou None si aucune ne correspond."""
    trouvees = set(intentions_correspondantes(texte))
    for intention in ORDRE_PRIORITE:
        if intention in trouvees:
            return intention
    if _ressemble_a_une_dette(texte):
        return "client"
    return None


# Menu numérique (R2, intégration téléphonie/USSD) : une utilisatrice peut
# choisir une action en disant ou en tapant un chiffre plutôt que le mot-clé
# bambara correspondant - plus fiable sur un canal USSD/clavier, où un
# chiffre isolé est quasi toujours bien reconnu, alors qu'un mot-clé parlé
# dépend de la qualité de l'ASR. Ordre arbitraire mais à garder stable une
# fois annoncé aux utilisatrices (voir messages_bambara.menu_principal) : le
# changer casserait l'association déjà apprise par une utilisatrice régulière.
# "consultation" (ancien 6, "joli") retiré du menu (2026-11-16) : cette
# intention n'a pas de vraie réponse construite derrière (voir
# AgentVocal.consultation_non_disponible). Reste reconnue en reconnaissance
# libre (MOTS_CLES ci-dessus), juste pas proposée comme raccourci chiffré.
#
# Passage de 5 à 9 choix (2026-11-17, script corrigé par l'équipe terrain -
# voir les 9 phrases "Appuyez sur X pour...") : 4 nouvelles actions (vente à
# crédit, achat à crédit, échéance/dépôt fournisseur, consultation du reste à
# payer) et "client" (ancien 4) et "stock" (ancien 5) renumérotés. Ces
# nouvelles intentions n'ont PAS de mot-clé dans MOTS_CLES ci-dessus pour la
# RECONNAISSANCE LIBRE (reconnaitre_intention) : accessibles seulement par le
# chiffre du menu (clavier ou nombre dit en bambara), jamais en disant leur
# nom. Fadima (GERME) a transmis le 2026-11-21 un mot bambara pour CHACUN des
# items 1-12 (y compris 4-8 et 10-12, voir web/index.html pour leur affichage
# comme étiquette de bouton) - mais seuls deux d'entre eux ont été ajoutés
# ci-dessus à MOTS_CLES (comme synonymes d'un mot déjà reconnu, items 2 et 9,
# décision explicite de Mohamed) : les mots des items 4-8/10-12 ("Fereli-
# djouroula", "Sani-djouroula", "Djourousarata-hake", etc.) contiennent tous
# la racine "djourou" (dette), qui collisionnerait avec "juru" déjà utilisé
# pour l'intention "client" - les ajouter à la reconnaissance libre demande
# une analyse de collision dédiée, pas faite ici. Simple étiquette affichée
# pour l'instant, pas une nouvelle voie de reconnaissance vocale.
MENU_NUMERIQUE: dict[int, str] = {
    1: "vente", 2: "depense", 3: "capital",
    4: "vente_credit", 5: "achat_credit",
    6: "fournisseur_paiement", 7: "fournisseur_consultation",
    8: "stock_ecriture", 9: "stock",
    # Items 10-12 (2026-11-17, suite aux fiches terrain transmises par
    # Fadima) : suivi d'un crédit SFD (institution de microfinance), même
    # principe que 4-8 - chiffre de menu uniquement pour la reconnaissance
    # libre (voir reconnaitre_choix_menu et la note juste au-dessus sur les
    # mots transmis le 2026-11-21, affichés mais pas ajoutés à MOTS_CLES).
    10: "sfd_declaration", 11: "sfd_paiement", 12: "sfd_consultation",
}


def reconnaitre_choix_menu(texte: str) -> str | None:
    """Un chiffre isolé (1 à 12) -> l'intention correspondante du menu, sinon None.

    Accepte aussi bien un chiffre arabe tapé tel quel ("1", canal USSD/clavier)
    qu'un nombre dit en toutes lettres bambara ("kelen", canal vocal) - voir
    MENU_NUMERIQUE. Volontairement strict : rejette tout énoncé contenant
    autre chose qu'un seul nombre dans cette plage, pour ne jamais confondre
    un choix de menu avec un nombre qui fait partie d'une vraie phrase (ex.
    "n ye saga saba feere" contient "saba"=3, mais n'est pas un choix de menu
    - "feere" prime, voir reconnaitre_intention).

    À utiliser seulement quand aucune intention n'est déjà active dans la
    session (voir Session.recevoir, moteur_decision.py) : une fois une
    intention en cours, un chiffre isolé est la réponse à un champ demandé
    (quantité, montant...), jamais un nouveau choix de menu.
    """
    brut = texte.strip()
    if brut in {str(n) for n in MENU_NUMERIQUE}:
        return MENU_NUMERIQUE[int(brut)]

    tokens = normaliser(texte).split()
    mots_restants = [t for t in tokens if not t.isdigit() and t not in NUMERAUX and t not in ET]
    nombres = extraire_nombres(texte)
    if len(nombres) == 1 and not mots_restants and nombres[0] in MENU_NUMERIQUE:
        return MENU_NUMERIQUE[nombres[0]]
    return None


# Confirmation oui/non (demandée après chaque montant, cas 8 du parcours).
# "owo"/"ayi" : formes bambara courantes, non encore vues dans un corpus de ce
# projet (aucune phrase de confirmation n'y figure), à valider en priorité
# par une personne bambaraphone, comme le reste de ce fichier. "aawo" :
# graphie observée en test réel (ASR RobotsMali sur une vraie locutrice,
# 2026-10-05) pour le même mot. Les formes françaises sont gardées en repli,
# les documents du projet n'étant pas tous cohérents sur ce point.
# "sonna" : la question posée par le système se termine toujours par "I
# sɔnna wa ?" ("es-tu d'accord ?", littéralement "tu es d'accord ?") ; une
# locutrice répond naturellement en reprenant ce même verbe ("Awo, ne
# sɔnna" ou juste "N sɔnna" = "je suis d'accord"), pas forcément par un
# "owo"/"oui" isolé. Construction déjà citée comme réelle dans le corpus
# (P02c, voir messages_bambara.py) mais absente de cette liste jusqu'ici :
# un test réel (2026-10-09) a confirmé qu'une confirmation de ce type
# n'était pas reconnue, faisant croire à tort à une boucle sans fin.
# "awa" : particule d'accord/acquiescement ("bon", "d'accord", "alors") très
# courante en bambara. Ajoutée après un test réel (2026-10-09) où une vraie
# locutrice a dit "oui" trois fois de suite sans jamais être reconnue ;
# analyse directe des enregistrements captés (NGONI_DEBUG_AUDIO) : l'ASR a
# transcrit exactement "awa" les 3 fois, de façon parfaitement cohérente
# (donc pas un bruit aléatoire, un vrai mot). Risque connu : "Awa" est aussi
# un prénom malien très courant (déjà utilisé comme tel dans les tests,
# voir test_agent_vocal.py) ; la collision ne joue que pendant une fenêtre
# de confirmation déjà ouverte (le système vient de poser une question
# oui/non), ce qui limite le risque réel de faux positif.
MOTS_OUI = ["owo", "awo", "aawo", "oui", "sonna", "awa"]
# "ayiwa" : variante de "ayi" observée deux fois en test réel (2026-10-09 et
# 2026-10-10), jamais reconnue jusqu'ici ("ayi" exige une correspondance
# exacte, "ayiwa" ne matche pas). Ajoutée en toutes lettres plutôt que de
# changer la règle générale (éviter un faux positif plus large sur "ayi").
MOTS_NON = ["ayi", "ayiwa", "non"]


def reconnaitre_confirmation(texte: str) -> bool | None:
    """True = oui, False = non, None = ni l'un ni l'autre (pas une réponse de confirmation)."""
    tokens = normaliser(texte).split()
    # "ma sɔn(na)" = "n'est pas d'accord" : négation du même verbe que la
    # question elle-même ("... I sɔnna wa ?"), forme de "non" naturelle en
    # bambara. Vérifiée AVANT le simple "sonna" => oui ci-dessous, sinon ce
    # "non" grammatical serait lu comme un "oui" (observé en test réel,
    # 2026-10-09 : "a ye ne ma sɔn" jamais reconnu comme un refus).
    for i, tok in enumerate(tokens[:-1]):
        if tok == "ma" and tokens[i + 1].startswith("son"):
            return False
    if any(_mot_present(m, tokens) for m in MOTS_OUI):
        return True
    if any(_mot_present(m, tokens) for m in MOTS_NON):
        return False
    return None


def _ressemble_a_une_dette(texte: str) -> bool:
    """Repli pour le cas 'client' sans le mot "juru" (ex. "X bɛ Mariam na" = Mariam doit X).

    Signal plus faible qu'un mot-clé dédié (la construction "bɛ ... na/la/fɛ"
    sert à bien d'autres usages en bambara) : n'est donc utilisé qu'en dernier
    recours, quand aucun mot-clé fort ne correspond déjà, et seulement si un
    nombre est présent (une dette s'accompagne toujours d'un montant).
    À valider par une personne bambaraphone (R9), comme le reste.
    """
    t = normaliser(texte)
    tokens = t.split()
    if "be" not in tokens or not extraire_nombres(texte):
        return False
    return any(tok in ("na", "la", "fe", "min") for tok in tokens)
