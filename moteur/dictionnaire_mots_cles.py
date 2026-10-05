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
from montants import extraire_nombres, normaliser

# Ordre de priorité quand plusieurs intentions correspondent à la fois dans la
# même phrase (ex. une question sur une dette contient aussi "juru").
ORDRE_PRIORITE = ["consultation", "client", "vente", "depense", "capital", "stock"]

MOTS_CLES: dict[str, list[str]] = {
    # Marqueurs interrogatifs : une question prime toujours sur le mot-clé
    # métier qu'elle contient (ex. "combien ai-je VENDU" n'est pas une vente).
    # "jɔn" (qui/lequel) est stocké normalisé ("jon", voir montants.normaliser).
    "consultation": ["joli", "jon"],
    # "juru" = dette/créance (le préfixe absorbe la variante "jurumu" du corpus).
    "client": ["juru"],
    # "feere" = vendre/vendu. Couvre aussi la forme "feerelen" (participe).
    "vente": ["feere"],
    # "sara" = payer ; "san" = acheter (englobe "achat", voir note ci-dessus).
    "depense": ["sara", "san"],
    # "jagokun" = capital, cité explicitement dans le document d'architecture.
    "capital": ["jagokun"],
    # "bolo" ("en ma possession"), "tora" (rester) : signaux les plus faibles
    # du dictionnaire, absents d'un des 3 témoins du corpus (P19c). À
    # renforcer en priorité lors de la validation linguistique (R9).
    "stock": ["bolo", "tora"],
}


def _mot_present(mot_cle: str, tokens: list[str]) -> bool:
    """Un token du texte correspond-il à ce mot-clé ?

    Préfixe pour absorber les suffixes bambara (ex. "feere" -> "feerelen"),
    mais exact pour les racines de moins de 4 lettres, trop courtes pour un
    préfixe sans faux positif (ex. "san" ne doit pas matcher à l'intérieur de
    "sanɲɔgɔn", qui normalisé devient "sanyogon").
    """
    if len(mot_cle) < 4:
        return mot_cle in tokens
    return any(tok.startswith(mot_cle) for tok in tokens)


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


# Confirmation oui/non (demandée après chaque montant, cas 8 du parcours).
# "owo"/"ayi" : formes bambara courantes, non encore vues dans un corpus de ce
# projet (aucune phrase de confirmation n'y figure) — à valider en priorité
# par une personne bambaraphone, comme le reste de ce fichier. "aawo" :
# graphie observée en test réel (ASR RobotsMali sur une vraie locutrice,
# 2026-10-05) pour le même mot. Les formes françaises sont gardées en repli,
# les documents du projet n'étant pas tous cohérents sur ce point.
MOTS_OUI = ["owo", "awo", "aawo", "oui"]
MOTS_NON = ["ayi", "non"]


def reconnaitre_confirmation(texte: str) -> bool | None:
    """True = oui, False = non, None = ni l'un ni l'autre (pas une réponse de confirmation)."""
    tokens = normaliser(texte).split()
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
