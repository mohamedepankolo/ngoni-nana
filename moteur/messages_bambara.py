"""Messages parlés du système, en bambara.

Premier jet de traduction, construit à partir : du vocabulaire déjà utilisé
ailleurs dans ce dépôt (feere=vendre, juru=dette, jagokun=capital, sara=payer,
san=acheter — dictionnaire_mots_cles.py), des tournures réellement observées
dans phrases_reelles.csv (ex. "..., i sɔnna" = "..., tu es d'accord" dans
P02c ; "{qté} {article} de bɛ [X] bolo" = structure de P19/P19b pour un
niveau de stock), et de connaissances générales de la langue pour le reste.

**Pas validé par une personne bambaraphone.** Contrairement au dictionnaire
de mots-clés (quelques mots isolés, faciles à vérifier un par un) ou aux
nombres (nombres_bambara.py, vérifiables par aller-retour automatique avec
montants.py), des phrases complètes ne peuvent pas s'auto-vérifier : une
tournure grammaticalement fausse ou peu naturelle peut passer les tests sans
qu'aucun test ne la détecte. À faire relire en priorité avant tout usage
devant de vraies utilisatrices.
"""
from moteur.nombres_bambara import nombre_en_bambara

FACTEUR_DOROME = 5  # cohérent avec moteur_decision.FACTEUR_DOROME : on reparle en dɔrɔmɛ, pas en FCFA


def _montant_bambara(montant_fcfa: int) -> str:
    return nombre_en_bambara(montant_fcfa // FACTEUR_DOROME)


def confirmation_vente(champs: dict) -> str:
    article = champs.get("article", "")
    quantite = champs.get("quantite")
    montant = _montant_bambara(champs.get("montant_fcfa", 0))
    qte_mot = nombre_en_bambara(quantite) if quantite else ""
    return f"{article} {qte_mot} feerelen bɛ na {montant} ma. I sɔnna wa?".replace("  ", " ")


def confirmation_depense(champs: dict) -> str:
    article = champs.get("article", "")
    montant = _montant_bambara(champs.get("montant_fcfa", 0))
    return f"{article} : wari {montant} sara. I sɔnna wa?"


def confirmation_client(champs: dict) -> str:
    client = champs.get("client", "")
    montant = _montant_bambara(champs.get("montant_fcfa", 0))
    if champs.get("est_un_paiement"):
        return f"{client} ye wari {montant} sara. I sɔnna wa?"
    return f"{client} ka juru ye wari {montant} ye. I sɔnna wa?"


def reponse_capital(montant_fcfa: int) -> str:
    return f"I ka jagokun ye wari {_montant_bambara(montant_fcfa)} ye."


def reponse_stock(article: str, quantite: int, seuil_bas: bool) -> str:
    base = f"{article} {nombre_en_bambara(quantite)} de bɛ i bolo."
    if seuil_bas:
        base += " Bɔrɛ ka dɔgɔ."  # "le stock est bas/insuffisant" — sens correct, formulation à valider
    return base


def continuer() -> str:
    return "Yala i b'a fɛ ka dɔ wɛrɛ kɛ wa?"


def enregistrement_confirme() -> str:
    return f"A sɛbɛnna. {continuer()}"


def reformulation(tentative: int) -> str:
    if tentative <= 1:
        return "Ne ma a faamu. A fɔ tuguni."
    # 2e tentative : propose explicitement les mots que le moteur reconnaît
    # (dictionnaire_mots_cles.MOTS_CLES), pas les noms français des actions —
    # ce sont ces mots-là, et pas leur traduction, que le moteur écoute.
    return "Ne ma a faamu fɔlɔ. A fɔ ka jɛya : feere, sara, jagokun, juru, walima bolo."


def escalade() -> str:
    return "Ne bɛna i bila animatrice kɔrɔ."


def demander_precision_montant() -> str:
    return "Wari hakɛ fɔ tuguni."
