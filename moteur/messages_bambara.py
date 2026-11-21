"""Messages parlés du système, en bambara.

Premier jet de traduction, construit à partir : du vocabulaire déjà utilisé
ailleurs dans ce dépôt (feere=vendre, juru=dette, jagokun=capital, sara=payer,
san=acheter, dictionnaire_mots_cles.py), des tournures réellement observées
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
    """Relit un montant en bambara TOUJOURS en dɔrɔmɛ (divisé par 5) : c'est

    la convention réelle pour ÉNONCER un prix en bambara (voir montants.py,
    "les prix sont très souvent énoncés en dɔrɔmɛ sans dire le mot"), que le
    montant vienne d'un énoncé vocal déjà en dɔrɔmɛ OU d'un montant tapé/dit
    directement en FCFA (clavier, ou "3000 francs" à voix haute) - la valeur
    FCFA enregistrée (moteur_decision.py, unite_dite) ne change pas selon le
    canal, seule la façon de la PRONONCER suit toujours cette convention.
    Retour terrain (2026-11-17, Mohamed) : un montant tapé "3000" devait bien
    s'enregistrer comme 3000 FCFA, mais se prononcer "kɛmɛ wɔɔrɔ" (600,
    converti) et non "waa saba" (3000, lu tel quel) - un chiffre FCFA brut
    prononcé tel quel ne sonne pas comme un prix dit naturellement en
    bambara. Différent de la version précédente de cette fonction (qui ne
    divisait PAS un montant tapé au clavier) : corrige ce choix, qui avait
    lui-même corrigé un bug différent (clavier enregistrant à tort x5) sans
    revenir sur le x5 côté prononciation.
    """
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


def confirmation_vente_credit(champs: dict) -> str:
    """Item 4 : vente à crédit. Construction par analogie avec confirmation_vente

    et confirmation_client - pas de mot "crédit" validé (voir
    dictionnaire_mots_cles.MENU_NUMERIQUE), "juru" (dette) suffit à porter le
    sens : "vendu à X, qui le doit". À valider par une personne bambaraphone
    en priorité, comme le reste de ce fichier.
    """
    article = champs.get("article", "")
    quantite = champs.get("quantite")
    montant = _montant_bambara(champs.get("montant_fcfa", 0))
    client = champs.get("client", "")
    qte_mot = nombre_en_bambara(quantite) if quantite else ""
    return (f"{article} {qte_mot} feerelen bɛ na {montant} ma, {client} ye juru la. "
            "I sɔnna wa?").replace("  ", " ")


def confirmation_achat_credit(champs: dict) -> str:
    """Item 5 : achat à crédit. Même limite que confirmation_vente_credit

    ci-dessus (pas de mot validé pour "crédit"/"fournisseur").
    """
    article = champs.get("article", "")
    montant = _montant_bambara(champs.get("montant_fcfa", 0))
    fournisseur = champs.get("fournisseur", "")
    return f"{article} : wari {montant} san juru la, {fournisseur} fɛ. I sɔnna wa?"


def confirmation_fournisseur_paiement(champs: dict) -> str:
    """Item 6 : échéance/dépôt - un paiement qui réduit ce que l'utilisatrice

    doit à un fournisseur (voir base_donnees.enregistrer_mouvement_fournisseur,
    toujours est_un_paiement=True pour cette intention).
    """
    fournisseur = champs.get("fournisseur", "")
    montant = _montant_bambara(champs.get("montant_fcfa", 0))
    return f"{fournisseur} : wari {montant} sara. I sɔnna wa?"


def reponse_fournisseur_consultation(montant_fcfa: int, fournisseur: str | None = None) -> str:
    """Item 7 : reste à payer. Avec un nom -> ce fournisseur précis, sans nom

    -> le total tous fournisseurs confondus (voir
    base_donnees.total_du_aux_fournisseurs, AgentVocal._repondre_lecture).
    """
    montant_mot = _montant_bambara(montant_fcfa)
    if fournisseur:
        return f"I bɛ wari {montant_mot} de sara {fournisseur} ye fɔlɔ."
    return f"I bɛ wari {montant_mot} de sara forow bɛɛ ye fɔlɔ."


def confirmation_stock_ecriture(champs: dict) -> str:
    """Item 8 : déclarer un stock initial ou un réapprovisionnement - même

    phrase de confirmation dans les deux cas (la distinction initial/ajout
    est décidée à l'écriture, voir base_donnees.enregistrer_mouvement_stock,
    pas ici : au moment de confirmer, les deux se décrivent pareil, "X
    quantité pour cet article").
    """
    article = champs.get("article", "")
    quantite = champs.get("quantite")
    qte_mot = nombre_en_bambara(quantite) if quantite else ""
    return f"{article} {qte_mot} bɛna bila i ka bolo la. I sɔnna wa?".replace("  ", " ")


def confirmation_capital_declaration(champs: dict) -> str:
    montant = _montant_bambara(champs.get("montant_fcfa", 0))
    return f"I ka jagokun bɛna kɛ wari {montant} ye. I sɔnna wa?"


def confirmation_capital_ajout(champs: dict) -> str:
    montant = _montant_bambara(champs.get("montant_fcfa", 0))
    return f"Wari {montant} bɛna fara i ka jagokun kan. I sɔnna wa?"


def confirmation_sfd_declaration(champs: dict) -> str:
    """Item 10 : déclaration d'un crédit SFD (institution de microfinance -

    "Fiche 5, Suivi des remboursements SFD", documentation Fadima,
    2026-11-17). "SFD" gardé tel quel (sigle propre à l'institution, pas un
    mot bambara à traduire) ; le reste réutilise des mots déjà présents dans
    ce fichier (wari=argent, kalo=mois, kelen=un) plutôt que d'en inventer -
    pas validé par une personne bambaraphone, comme le reste de ce module.
    """
    nom_sfd = champs.get("nom_sfd", "")
    montant = _montant_bambara(champs.get("montant_fcfa", 0))
    duree = nombre_en_bambara(champs.get("duree_mois", 0))
    echeance = _montant_bambara(champs.get("echeance_mensuelle_fcfa", 0))
    return (f"SFD {nom_sfd} : wari {montant} juru la, kalo {duree} kɔnɔ, "
            f"kalo kelen-kelen wari {echeance} sara. I sɔnna wa?")


def confirmation_sfd_paiement(champs: dict) -> str:
    """Item 11 : paiement d'une échéance SFD - un seul prêt actif supposé

    (voir base_donnees.enregistrer_paiement_sfd), donc pas besoin de
    redemander le nom du SFD ici.
    """
    montant = _montant_bambara(champs.get("montant_fcfa", 0))
    return f"SFD wari {montant} sara. I sɔnna wa?"


def reponse_sfd_consultation(montant_restant_fcfa: int, prochaine_echeance_fcfa: int | None = None) -> str:
    """Item 12 : reste à payer sur le crédit SFD, et montant de la prochaine

    échéance si elle existe (pas de date parlée - voir EcheanceSfd,
    base_donnees.py - aucune reconnaissance de date n'existe dans ce projet).
    """
    montant_mot = _montant_bambara(montant_restant_fcfa)
    if prochaine_echeance_fcfa:
        prochaine_mot = _montant_bambara(prochaine_echeance_fcfa)
        return f"I bɛ wari {montant_mot} de sara SFD ye fɔlɔ. Kalo nata wari {prochaine_mot}."
    return f"I bɛ wari {montant_mot} de sara SFD ye fɔlɔ."


def reponse_stock(article: str, quantite: int, seuil_bas: bool) -> str:
    base = f"{article} {nombre_en_bambara(quantite)} de bɛ i bolo."
    if seuil_bas:
        base += " Bɔrɛ ka dɔgɔ."  # "le stock est bas/insuffisant" : sens correct, formulation à valider
    return base


def menu_principal() -> str:
    """Message d'accueil avec le menu numérique (MENU_NUMERIQUE,

    dictionnaire_mots_cles.py) : annonce chaque action avec son chiffre ET
    son mot-clé bambara habituel, quand ce mot existe (voir
    moteur_decision.Session.recevoir, qui reconnaît les deux). Mots-clés
    repris tels quels de dictionnaire_mots_cles.MOTS_CLES plutôt que de
    nouveaux mots, pour ne pas ajouter de vocabulaire non validé
    supplémentaire à celui déjà signalé comme À VALIDER (R9) en tête de ce
    module.

    Passage à 9 choix (2026-11-17, script corrigé par l'équipe terrain) :
    seuls 1 (vente), 2 (dépense), 3 (capital) et 9 (stock, ex-5 renuméroté)
    ont un mot-clé annoncé ici. Les 4 nouveaux choix (vente/achat à crédit,
    échéance fournisseur, reste à payer - items 4 à 7), le réapprovisionnement
    de stock (item 8) et les items 10-12 (SFD) ne sont annoncés QUE par leur
    chiffre, à choisir au clavier ou en disant le nombre en bambara - l'écran
    affiche leur libellé (voir moteur/web/index.html).

    Fadima (GERME) a transmis le 2026-11-21 un mot bambara pour chacun de ces
    items (4-8, 10-12) - voir web/index.html, qui les affiche désormais comme
    étiquette de bouton. Ce texte-ci (le message vocal d'accueil) ne les
    annonce volontairement PAS en plus de ceux déjà présents : l'audio de ce
    message est déjà anormalement long en test réel (~72s mesurés, voir
    tts_maliba.py et le suivi du bug correspondant) pour un texte aussi court -
    y ajouter 8 mots composés (certains à 3 segments, ex. "Warimarasow-
    djourousarata-hake") l'allongerait encore, sans bénéfice clair puisque le
    choix par chiffre fonctionne déjà. À reconsidérer seulement après
    correction de ce bug de lenteur.
    """
    return ("I ni ce, aw bisimila N'GONI NANA na. "
            "Kelen : feere. Fila : sara. Saba : jagokun. "
            "Kononton : bolo.")


def continuer() -> str:
    return "Yala i b'a fɛ ka dɔ wɛrɛ kɛ wa?"


def enregistrement_confirme() -> str:
    # La question qui suit ("veux-tu faire autre chose ?") a maintenant une
    # vraie suite : voir AgentVocal._traiter_reponse_continuer (agent_vocal.py).
    # Un premier essai l'avait retirée faute d'écoute réelle derrière (bug
    # réel, test téléphone 2026-10-09) ; corrigé pour de vrai au lieu de
    # simplement supprimer la question.
    return f"A sɛbɛnna. {continuer()}"


def pret_a_ecouter() -> str:
    """Dit après un "oui" à "veux-tu faire autre chose ?" : la session

    continue, prête pour une nouvelle action, sans redemander de montant.
    """
    return "Ne lamɛnna."


def au_revoir() -> str:
    """Dit après un "non" à "veux-tu faire autre chose ?" : clôture nette,

    pas une nouvelle tentative d'action mal comprise.
    """
    return "I ni ce. K'an bɛn."


def reformulation(tentative: int) -> str:
    if tentative <= 1:
        return "Ne ma a faamu. A fɔ tuguni."
    # 2e tentative : propose explicitement les mots que le moteur reconnaît
    # (dictionnaire_mots_cles.MOTS_CLES), pas les noms français des actions,
    # ce sont ces mots-là, et pas leur traduction, que le moteur écoute.
    return "Ne ma a faamu fɔlɔ. A fɔ ka jɛya : feere, sara, jagokun, juru, walima bolo."


def escalade() -> str:
    return "Ne bɛna i bila animatrice kɔrɔ."


# Mot bambara court identifiant chaque champ corrigible (voir
# agent_vocal.CHAMPS_CORRIGIBLES) - repris tel quel des messages demander_*
# ci-dessous (demander_article dit "a tɔgɔ", demander_quantite dit "hakɛ",
# etc.) : pas un nouveau mot inventé pour l'occasion, juste la réutilisation
# du mot déjà choisi pour ce champ ailleurs dans ce fichier.
NOMS_CHAMPS_BAMBARA = {
    "article": "a tɔgɔ",
    "quantite": "hakɛ",
    "montant_fcfa": "wari",
    "client": "mɔgɔ tɔgɔ",
    "fournisseur": "fɛn feerelikɛla tɔgɔ",
    # Items 10-12 (SFD, 2026-11-17) : "nom_sfd" distinct de "fournisseur" -
    # NOMS_CHAMPS_BAMBARA["fournisseur"] signifie explicitement "nom du
    # fournisseur de marchandises", un mauvais libellé pour une institution
    # de microfinance (confusion sémantique réelle à éviter, pas juste un
    # style différent).
    "nom_sfd": "SFD tɔgɔ",
    "duree_mois": "kalo hakɛ",
    "echeance_mensuelle_fcfa": "kalo wari",
}


def demander_quel_champ_corriger(champs: list[str]) -> str:
    """Propose un choix numéroté (1, 2, 3...) parmi les champs réellement

    saisis pour cette transaction, pour cibler PRÉCISÉMENT ce qui doit être
    corrigé après un "non" au résumé final - au lieu de deviner le dernier
    champ confirmé (ancien comportement de agent_vocal._demarrer_correction),
    qui n'était pas forcément le bon si l'erreur portait sur un champ saisi
    plus tôt (retour terrain, 2026-11-17, Mohamed : "ça peut concerner autant
    la quantité que le montant, que le produit"). Même format parlé "chiffre
    : mot" que menu_principal() (chaque ":" devient une vraie pause à la
    synthèse, voir tts_maliba._decouper_phrases).
    """
    options = " ".join(
        f"{nombre_en_bambara(i)} : {NOMS_CHAMPS_BAMBARA.get(champ, champ)}."
        for i, champ in enumerate(champs, start=1)
    )
    return f"Mun tɛ bɛn? {options}"


def confirmer_champ(champ: str, valeur) -> str:
    """Relit UNE valeur tout juste saisie (quantité ou montant) avant de

    poursuivre - sécurité supplémentaire sur les champs numériques les plus
    sensibles à la saisie clavier (voir agent_vocal.CHAMPS_A_CONFIRMER_
    UNITAIREMENT : montant, quantité, et depuis les items 10-12 SFD, durée
    en mois et échéance mensuelle). Pas pour l'article ou le client : un
    nom mal compris se corrige sans risque, un chiffre mal compris peut
    fausser toute l'écriture comptable.
    """
    if champ in ("montant_fcfa", "echeance_mensuelle_fcfa"):
        return f"I ko wari {_montant_bambara(valeur)}. I sɔnna wa?"
    if champ in ("quantite", "duree_mois"):
        return f"I ko {nombre_en_bambara(valeur)}. I sɔnna wa?"
    return "I sɔnna wa?"


def demander_precision_montant() -> str:
    return "Wari hakɛ fɔ."


# Les trois messages suivants ciblent précisément UN champ manquant (voir
# Session.premier_champ_manquant / combler_champ, moteur_decision.py).
# Avant, le système redemandait toujours "le montant" par défaut, même
# quand c'était la quantité ou l'article qui manquait réellement : constaté
# en test réel (2026-10-09), ça rendait toute correction impossible à
# comprendre (redonner juste le montant ne suffisait jamais si la quantité
# restait aussi manquante, sans que personne sache qu'il fallait la redire
# aussi). Constructions par analogie avec demander_precision_montant,
# jusqu'ici seul message de ce type ; à valider par une personne
# bambaraphone comme le reste de ce fichier.
def demander_quantite() -> str:
    return "Hakɛ fɔ."


def demander_article() -> str:
    return "A tɔgɔ fɔ."


def demander_client() -> str:
    return "Mɔgɔ tɔgɔ fɔ."


def demander_fournisseur() -> str:
    return "Fɛn feerelikɛla tɔgɔ fɔ."


# Items 10-12 (SFD) : trois nouveaux champs, même principe que les cinq
# ci-dessus (première demande sans "tuguni", voir les variantes "_encore").
def demander_nom_sfd() -> str:
    return "SFD tɔgɔ fɔ."


def demander_duree_mois() -> str:
    return "Kalo hakɛ fɔ."


def demander_echeance_mensuelle() -> str:
    return "Kalo kelen-kelen wari hakɛ fɔ."


# Variantes "encore" (avec "tuguni", = "encore/à nouveau") des cinq messages
# ci-dessus : à utiliser UNIQUEMENT pour redemander un champ après un refus
# explicite (un "non" à la relecture, ou une valeur mal comprise) - jamais
# pour la toute première question posée sur ce champ, qui n'est pas encore
# une répétition (retour terrain, 2026-11-17, Mohamed : "tuguni" dès la
# première saisie fait bizarre, ça ne doit apparaître qu'au second essai).
def demander_precision_montant_encore() -> str:
    return "Wari hakɛ fɔ tuguni."


def demander_quantite_encore() -> str:
    return "Hakɛ fɔ tuguni."


def demander_article_encore() -> str:
    return "A tɔgɔ fɔ tuguni."


def demander_client_encore() -> str:
    return "Mɔgɔ tɔgɔ fɔ tuguni."


def demander_fournisseur_encore() -> str:
    return "Fɛn feerelikɛla tɔgɔ fɔ tuguni."


def demander_nom_sfd_encore() -> str:
    return "SFD tɔgɔ fɔ tuguni."


def demander_duree_mois_encore() -> str:
    return "Kalo hakɛ fɔ tuguni."


def demander_echeance_mensuelle_encore() -> str:
    return "Kalo kelen-kelen wari hakɛ fɔ tuguni."


def consultation_non_disponible() -> str:
    """"Combien ai-je vendu ce mois-ci ?" (intention "consultation") n'a

    jamais eu de vraie réponse construite (pas de requête sur les
    transactions par période) : avant, ce cas réutilisait par erreur
    continuer() ("veux-tu faire autre chose ?"), qui laissait croire à tort
    qu'une action venait d'être enregistrée (trouvé en test réel,
    2026-10-10). Un message honnête, même générique, vaut mieux qu'un
    message trompeur en attendant une vraie implémentation.
    """
    return "Ne tɛ se k'o fɔ fɔlɔ."
