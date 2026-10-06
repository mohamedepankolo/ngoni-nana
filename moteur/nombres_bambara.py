"""Convertit un nombre en toutes lettres bambara : l'inverse de montants.py.

Sert à faire parler le TTS en nombres bambara plutôt qu'en chiffres français
("waa bi duuru" plutôt que "50000"). Suit exactement la même grammaire que
`montants.extraire_nombres` (dizaines en bi+unité sauf mugan=20, centaines en
kɛmɛ+multiplicateur, milliers en waa+multiplicateur, "ni" pour additionner) :
un nombre produit ici doit se reparser avec `extraire_nombres` en
retrouvant la même valeur. Voir tests/test_nombres_bambara.py, qui vérifie
exactement cet aller-retour sur une plage de nombres, dont les montants réels
de phrases_reelles.csv.

Comme pour le reste des fichiers bambara du projet : la grammaire des
nombres suit COMPARAISON_MODELES.md / montants.py (déjà en partie validée
par l'usage sur phrases_reelles.csv), mais reste à faire relire par une
personne bambaraphone avant un usage en production.
"""
UNITES = {1: "kelen", 2: "fila", 3: "saba", 4: "naani", 5: "duuru",
          6: "wooro", 7: "wolonwula", 8: "seegin", 9: "kononton"}


def _dizaine(n: int) -> str:
    """0 <= n <= 99."""
    if n == 0:
        return ""
    if n < 10:
        return UNITES[n]
    if n == 10:
        return "tan"
    if n == 20:
        return "mugan"
    dix, reste = divmod(n, 10)
    if n < 20:
        base = "tan"
    elif n < 30:
        base = "mugan"
    else:
        base = "bi " + UNITES[dix]
    return base if reste == 0 else f"{base} ni {UNITES[reste]}"


def _centaine(n: int) -> str:
    """0 <= n <= 999."""
    if n == 0:
        return ""
    cent, reste = divmod(n, 100)
    if cent == 0:
        return _dizaine(reste)
    base = "kɛmɛ" if cent == 1 else f"kɛmɛ {UNITES[cent]}"
    return base if reste == 0 else f"{base} ni {_dizaine(reste)}"


def _termes_milliers(mille: int) -> list[str]:
    """Termes 'waa ...' (déjà en toutes lettres) dont la somme vaut mille*1000.

    Un seul "waa X" ne peut porter qu'un multiplicateur simple (1-99, ou
    "kɛmɛ [1-99]") : la grammaire de montants.py ne permet pas de
    "ni"-chaîner à l'intérieur de ce multiplicateur (un "kɛmɛ ... ni ..."
    imbriqué sous waa se reparse en additionnant le reste HORS du ×1000,
    donc faux). Un millier comme 125 (= 100 + 25, pas 100×quelque chose)
    doit donc sortir comme deux termes "waa" additionnés par "ni" plutôt
    qu'un seul, d'où la récursion plutôt qu'un simple appel à _centaine().
    """
    if mille == 0:
        return []
    if mille < 100:
        return [f"waa {_dizaine(mille)}"]
    cent, reste = divmod(mille, 100)  # cent : 1-9 pour n < 1 000 000 (voir nombre_en_bambara)
    terme_centaine = "kɛmɛ" if cent == 1 else f"kɛmɛ {UNITES[cent]}"
    return [f"waa {terme_centaine}"] + _termes_milliers(reste)


def nombre_en_bambara(n: int) -> str:
    """0 <= n < 1 000 000 (largement suffisant pour des montants FCFA/dɔrɔmɛ réalistes)."""
    if n == 0:
        return "fu"  # "zéro, rien" : rarement énoncé dans ce domaine, peu de témoins pour valider
    if n < 0:
        raise ValueError("nombre_en_bambara ne gère pas les nombres négatifs")

    mille, reste = divmod(n, 1000)
    parties = _termes_milliers(mille)
    if reste:
        parties.append(_centaine(reste))
    return " ni ".join(parties)
