"""Extraction des nombres et montants depuis une transcription bambara.

Le point le plus critique du test ASR est l'exactitude des montants. Le modèle
peut sortir les nombres en chiffres ("2500") ou en toutes lettres bambara
("dɔrɔmɛ kɛmɛ duuru"). Ce module gère les deux.

Règles de numération bambara prises en compte (à faire valider par un·e
linguiste de l'équipe) :
  - unités : kelen 1, fila 2, saba 3, naani 4, duuru 5, wɔɔrɔ 6,
    wolonwula 7, seegin 8, kɔnɔntɔn 9
  - tan 10, mugan 20, bi + unité = dizaines (bi saba = 30)
  - kɛmɛ 100, le multiplicateur suit (kɛmɛ fila = 200)
  - waa / ba 1000, le multiplicateur suit (waa bi duuru = 50 000)
  - "ni" additionne (waa fila ni kɛmɛ duuru = 2 500), y compris à l'intérieur
    d'un multiplicateur de dizaine : waa tan ni duuru = 1000 x 15 = 15 000,
    kɛmɛ bi saba ni naani = 100 x 34 = 3 400. Un multiplicateur d'une seule
    unité ne s'étend pas : kɛmɛ fila ni bi duuru = 200 + 50 = 250.
  - "dɔrɔmɛ" = unité de 5 FCFA : dɔrɔmɛ kɛmɛ = 500 FCFA.

Attention : les prix sont très souvent énoncés en dɔrɔmɛ SANS dire le mot.
Exemple du cahier des charges : "wa bi dourou" = 50 000 (dɔrɔmɛ) = 250 000 FCFA.
L'ASR ne peut donc être jugé que sur le nombre prononcé ; la conversion en FCFA
relève du moteur de décision (qui connaît le contexte). C'est pourquoi
`extraire_nombres` ne multiplie pas par 5 et que l'évaluation compare le nombre
prononcé.
"""
import re
import unicodedata

# Graphies normalisées (sans caractères spéciaux) -> valeur.
UNITES = {
    "kelen": 1, "fila": 2, "saba": 3, "naani": 4, "nani": 4,
    # "dou" : troncature de dourou/duuru observée en sortie ASR (RobotsMali/
    # soloni-114m-tdt-ctc-v3 sur "wa bi dourou") — à valider avec un·e
    # linguiste comme le reste de ces règles, mais sans ce variant le
    # montant n'est simplement jamais retrouvé.
    "duuru": 5, "duru": 5, "dourou": 5, "dou": 5, "wooro": 6, "woro": 6,
    "wolonwula": 7, "wolonfila": 7, "seegin": 8, "segin": 8, "seguin": 8,
    "kononton": 9,
}
DIX = {"tan"}
VINGT = {"mugan", "mougan"}
DIZAINES = {"bi"}
CENT = {"keme"}
MILLE = {"waa", "wa", "ba"}
ET = {"ni"}

NUMERAUX = set(UNITES) | DIX | VINGT | DIZAINES | CENT | MILLE


def normaliser(texte: str) -> str:
    """Minuscules, ɛ->e, ɔ->o, ɲ->ny, ŋ->ng, sans accents ni ponctuation."""
    t = texte.lower()
    t = t.replace("ɛ", "e").replace("ɔ", "o").replace("ɲ", "ny").replace("ŋ", "ng")
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"(?<=\d)[ .](?=\d{3}\b)", "", t)  # 2 500 / 2.500 -> 2500
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _petit(tokens, i):
    """Nombre < 100 à partir de tokens[i] : unité, tan, mugan, bi X (+ ni unité)."""
    tok = tokens[i] if i < len(tokens) else None
    if tok in UNITES:
        return UNITES[tok], i + 1
    if tok in DIX:
        return 10, i + 1
    if tok in VINGT:
        return 20, i + 1
    if tok in DIZAINES and i + 1 < len(tokens) and tokens[i + 1] in UNITES:
        return 10 * UNITES[tokens[i + 1]], i + 2
    return None, i


def _multiplicateur(tokens, i):
    """Multiplicateur < 100 ; une dizaine peut être suivie de "ni" + unité (tan ni duuru = 15)."""
    val, j = _petit(tokens, i)
    if val is not None and val >= 10 and val % 10 == 0 and j + 1 < len(tokens) \
            and tokens[j] in ET and tokens[j + 1] in UNITES:
        return val + UNITES[tokens[j + 1]], j + 2
    return val, j


def _terme(tokens, i):
    """Un terme additif : petit nombre, kɛmɛ [N], ou waa [N]."""
    tok = tokens[i]
    if tok in CENT:
        mult, j = _multiplicateur(tokens, i + 1)
        return 100 * (mult or 1), j
    if tok in MILLE:
        # "wa", "ba" sont aussi des mots courants (particule interrogative,
        # "mère"/"grand") : on n'y voit 1000 que si un multiplicateur suit.
        mult, j = _sous_mille(tokens, i + 1)
        return (1000 * mult if mult else None), j
    return _petit(tokens, i)


def _sous_mille(tokens, i):
    """Multiplicateur de waa : kɛmɛ [N] ou petit nombre (sans 'ni')."""
    if i < len(tokens) and tokens[i] in CENT:
        mult, j = _multiplicateur(tokens, i + 1)
        return 100 * (mult or 1), j
    return _multiplicateur(tokens, i)


def _nombre(tokens, i):
    """Suite de termes reliés par 'ni'. Renvoie (valeur, index suivant)."""
    total, j = _terme(tokens, i)
    if total is None:
        return None, i
    while j + 1 < len(tokens) and tokens[j] in ET and tokens[j + 1] in NUMERAUX:
        val, k = _terme(tokens, j + 1)
        if val is None:
            break
        total, j = total + val, k
    return total, j


def _decouper_mot_colle(mot: str, profondeur_max: int = 4) -> list[str] | None:
    """Décompose un mot collé (ex. "biwa") en mots numéraux connus mis
    bout à bout, sans reste, ou None si impossible.

    Sans pause audible entre deux mots, l'ASR peut les fusionner en un seul
    token (observé : "wa bi dourou" transcrit avec "wa"+"bi" fusionnés en
    "biwa"), ce qui casse le découpage par espaces dont dépend le parseur.
    Cherche à chaque étape le préfixe connu le plus long, pour préférer les
    mots les plus spécifiques (éviter par ex. de lire "duuru" comme deux
    mots plus courts qui n'existent pas dans NUMERAUX).
    """
    if not mot or profondeur_max == 0:
        return None
    if mot in NUMERAUX:
        return [mot]
    plus_long = max((len(m) for m in NUMERAUX), default=0)
    for taille in range(min(len(mot) - 1, plus_long), 1, -1):
        prefixe, reste = mot[:taille], mot[taille:]
        if prefixe in NUMERAUX:
            suite = _decouper_mot_colle(reste, profondeur_max - 1)
            if suite is not None:
                return [prefixe] + suite
    return None


def extraire_nombres(texte: str) -> list[int]:
    """Tous les nombres prononcés (chiffres ou toutes lettres), sans conversion d'unité."""
    tokens = normaliser(texte).split()
    nombres = []
    i = 0
    while i < len(tokens):
        if tokens[i].isdigit():
            nombres.append(int(tokens[i]))
            i += 1
            continue
        if tokens[i] not in NUMERAUX:
            morceaux = _decouper_mot_colle(tokens[i])
            if morceaux and len(morceaux) > 1:
                tokens[i:i + 1] = morceaux
        if tokens[i] in NUMERAUX:
            valeur, j = _nombre(tokens, i)
            if valeur is not None:
                nombres.append(valeur)
                i = j
                continue
        i += 1
    return nombres


def nombre_principal(texte: str) -> int | None:
    """Le plus grand nombre de la phrase : en général le montant (les petits sont des quantités)."""
    n = extraire_nombres(texte)
    return max(n) if n else None
