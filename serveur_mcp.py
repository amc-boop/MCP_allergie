"""
Serveur MCP Open Food Facts (produits alimentaires uniquement).

Outils : chercher_produit, verifier_allergene, verifier_regime,
fiche_produit, verifier_label, infos_nutrition (voir plus bas).

Lancement :
    uv run serveur_mcp.py         # transport stdio (Claude Desktop, Claude Code…)
"""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer

import httpx

import regles
from client_openfoodfacts import OpenFoodFactsClient, OpenFoodFactsError

mcp = MCPServer("openfoodfacts")
client = OpenFoodFactsClient()


# =========================================================================
# Outils ajoutés : sécurité alimentaire (allergènes et régimes)
# Tous sont en LECTURE SEULE : on ne fait que des requêtes GET.
# =========================================================================

RAISON_INTROUVABLE = "Produit introuvable dans Open Food Facts"


def _message_api_indisponible(e: OpenFoodFactsError) -> dict:
    """Transforme une panne de l'API en message clair (sans rien inventer)."""
    if isinstance(e.__cause__, httpx.TimeoutException):
        cause = "Open Food Facts a mis trop de temps à répondre (timeout)."
    else:
        cause = "Impossible de joindre Open Food Facts (erreur réseau ou API)."
    return {
        "reponse": regles.INCONNU,
        "erreur": cause + " Réessayez plus tard. Aucune information n'est disponible.",
    }


@mcp.tool()
async def chercher_produit(nom: str) -> dict:
    """Cherche des produits alimentaires par nom ou par marque (5 résultats
    maximum). À utiliser en premier dès que l'utilisateur nomme un produit
    sans donner de code-barres : "le Nutella", "des pâtes Barilla",
    "ce biscuit", "trouve-moi le produit...".
    Renvoie pour chacun le nom, la marque et le code-barres. Ce code-barres
    sert ensuite à tous les autres outils (allergènes, régimes, labels,
    fiche produit, nutrition)."""
    nom = (nom or "").strip()
    if not nom:  # garde-fou : recherche vide
        return {"erreur": "Le nom du produit est vide. Donnez un nom à chercher."}
    try:
        resultat = await client.rechercher(nom, nb=5)
    except OpenFoodFactsError as e:
        return _message_api_indisponible(e)
    # On ne garde que 3 informations, et 5 produits au plus
    produits = [
        {"nom": p["nom"], "marque": p["marques"], "code_barres": p["code_barres"]}
        for p in resultat["produits"][:5]
    ]
    return {"produits": produits}


@mcp.tool()
async def verifier_allergene(code_barres: str, allergene: str) -> dict:
    """Utilise TOUJOURS cet outil avant de répondre à une question d'allergie
    ou d'intolérance sur un produit, plutôt que tes connaissances.

    À utiliser dès qu'on parle de : allergie, allergène, allergique,
    intolérance, "est-ce que ça contient du lait / des oeufs / des
    cacahuètes / du gluten...", "puis-je en manger si je suis allergique",
    "des traces de...", "ça peut contenir...", cacahuète, noix, lactose.
    Réponses possibles : "contient", "traces possibles" ou "inconnu".
    Ne répond JAMAIS "sans risque" : "inconnu" veut dire qu'on ne sait pas,
    il faut alors conseiller de lire l'emballage.
    Allergènes acceptés : les 14 allergènes réglementaires de l'UE (gluten,
    crustacés, oeufs, poisson, arachides, soja, lait, fruits à coque,
    céleri, moutarde, sésame, sulfites, lupin, mollusques)."""
    code = regles.valider_code_barres(code_barres)
    if code is None:
        return {"erreur": "Code-barres invalide : il faut 8 à 13 chiffres."}
    nom = regles.normaliser_allergene(allergene)
    if nom is None:
        return {
            "erreur": f"Allergène non prévu : '{allergene}'.",
            "choix_possibles": regles.liste_allergenes(),
        }
    try:
        produit = await client.produit_brut(code)
    except OpenFoodFactsError as e:
        return _message_api_indisponible(e)
    return {
        "code_barres": code,
        "allergene": nom,
        "reponse": regles.verdict_allergene(produit, nom),
        "remarque": regles.AVERTISSEMENT_ALLERGENE,
        # Produit introuvable : on explique pourquoi la réponse est "inconnu"
        **({"raison": RAISON_INTROUVABLE} if produit is None else {}),
    }


@mcp.tool()
async def verifier_regime(code_barres: str, regime: str) -> dict:
    """Utilise TOUJOURS cet outil avant de répondre à une question de régime
    alimentaire sur un produit, plutôt que tes connaissances.

    À utiliser dès qu'on parle de : vegan, végétalien, végane, végétarien,
    "sans viande", "sans produit animalier", "sans huile de palme", palme,
    "est-ce que je peux en manger si je suis vegan / végétarien".
    Régimes acceptés : vegan, végétarien, sans huile de palme.
    Réponses : "oui (estimé)", "non" ou "inconnu". C'est une estimation
    automatique, pas une certification : le préciser à l'utilisateur."""
    code = regles.valider_code_barres(code_barres)
    if code is None:
        return {"erreur": "Code-barres invalide : il faut 8 à 13 chiffres."}
    nom = regles.normaliser_regime(regime)
    if nom is None:
        return {
            "erreur": f"Régime non prévu : '{regime}'.",
            "choix_possibles": regles.liste_regimes(),
        }
    try:
        produit = await client.produit_brut(code)
    except OpenFoodFactsError as e:
        return _message_api_indisponible(e)
    return {
        "code_barres": code,
        "regime": nom,
        "reponse": regles.verdict_regime(produit, nom),
        "avertissement": regles.AVERTISSEMENT_REGIME,
        **({"raison": RAISON_INTROUVABLE} if produit is None else {}),
    }


# =========================================================================
# Outils 4 à 6 : fiche produit, labels, nutrition (lecture seule)
# =========================================================================

def _introuvable() -> dict:
    """Réponse commune quand le produit n'existe pas : on n'invente rien."""
    return {"reponse": regles.INCONNU, "raison": RAISON_INTROUVABLE}


@mcp.tool()
async def fiche_produit(code_barres: str) -> dict:
    """Donne la fiche d'identité d'un produit à partir de son code-barres.

    À utiliser pour : "c'est quoi ce produit", "de quelle marque", "quelle
    quantité / quel poids / quel format", "dans quelle catégorie", "d'où
    vient-il", "où est-il fabriqué", "provenance", "origine", "photo",
    "image de l'emballage".
    Donne : nom, marque, quantité, catégories, origine, lieu de
    fabrication et URL de la photo. Un champ absent est indiqué
    "non renseigné" (jamais une valeur inventée). Pour les allergènes, les
    régimes ou la nutrition, utiliser plutôt les outils dédiés."""
    code = regles.valider_code_barres(code_barres)
    if code is None:
        return {"erreur": "Code-barres invalide : il faut 8 à 13 chiffres."}
    try:
        produit = await client.produit_fiche(code)
    except OpenFoodFactsError as e:
        return _message_api_indisponible(e)
    if produit is None:
        return _introuvable()
    return {"code_barres": code, **regles.construire_fiche(produit)}


@mcp.tool()
async def verifier_label(code_barres: str, label: str) -> dict:
    """Utilise TOUJOURS cet outil avant de répondre à une question de label ou
    de certification sur un produit, plutôt que tes connaissances.

    À utiliser dès qu'on parle de : bio, biologique, AB, agriculture
    biologique, "bio européen", feuille verte, commerce équitable, équitable,
    Fairtrade, Max Havelaar, "sans gluten", gluten free, Label Rouge,
    label, certification, certifié, "est-ce que c'est bio ?".
    Labels acceptés : bio (AB ou bio européen), commerce équitable,
    sans gluten, Label Rouge.
    Réponses : "présent" ou "non signalé" (jamais "absent").
    Les labels sont déclarés par des contributeurs : vérifier le logo sur
    l'emballage. Pour "sans gluten" : c'est un label, pas une garantie
    médicale ; en cas d'allergie, utiliser aussi verifier_allergene."""
    code = regles.valider_code_barres(code_barres)
    if code is None:
        return {"erreur": "Code-barres invalide : il faut 8 à 13 chiffres."}
    nom = regles.normaliser_label(label)
    if nom is None:
        return {
            "erreur": f"Label non prévu : '{label}'.",
            "choix_possibles": regles.liste_labels(),
        }
    try:
        produit = await client.produit_labels(code)
    except OpenFoodFactsError as e:
        return _message_api_indisponible(e)
    if produit is None:
        return _introuvable()
    rep = {
        "code_barres": code,
        "label": nom,
        "reponse": regles.verdict_label(produit, nom),
        "avertissement": regles.AVERTISSEMENT_LABEL,
    }
    if nom == "sans gluten":  # rappel spécial : label et non garantie médicale
        rep["avertissement_gluten"] = regles.AVERTISSEMENT_GLUTEN
    return rep


@mcp.tool()
async def infos_nutrition(code_barres: str) -> dict:
    """Utilise TOUJOURS cet outil avant de répondre à une question de santé
    ou de nutrition sur un produit, plutôt que tes connaissances.

    À utiliser dès qu'on parle de : santé, nutrition, calories, kcal,
    énergie, sucre, sucres, gras, matières grasses, sel, additifs, Nutri-Score,
    NOVA, ultra-transformé, score environnemental, "est-ce bon pour la
    santé ?", "est-ce sain ?", "est-ce light ?", "ça fait grossir ?",
    "combien de calories / de sucre ?", "valeurs nutritionnelles".

    Donne : Nutri-Score, groupe NOVA, score environnemental, additifs et
    valeurs pour 100 g (énergie en kcal, matières grasses, sucres, sel).
    Il faut le code-barres (le trouver d'abord avec chercher_produit).
    Ne renvoie QUE des chiffres issus d'Open Food Facts : aucun conseil
    médical, aucun jugement. Rapporte ces chiffres tels quels, sans dire
    si c'est "bon" ou "mauvais" pour la santé. Valeur absente : "non renseigné"."""
    code = regles.valider_code_barres(code_barres)
    if code is None:
        return {"erreur": "Code-barres invalide : il faut 8 à 13 chiffres."}
    try:
        produit = await client.produit_nutrition(code)
    except OpenFoodFactsError as e:
        return _message_api_indisponible(e)
    if produit is None:
        return _introuvable()
    return {
        "code_barres": code,
        **regles.construire_nutrition(produit),
        "remarque": "Données brutes d'Open Food Facts, sans interprétation. "
        "Une liste d'additifs vide signifie : aucun additif enregistré.",
    }


if __name__ == "__main__":
    mcp.run()
