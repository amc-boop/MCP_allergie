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
    """Cherche des produits alimentaires par nom (5 résultats maximum).
    Renvoie pour chacun le nom, la marque et le code-barres. Le code-barres
    sert ensuite à verifier_allergene et verifier_regime."""
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
    """Indique si un produit contient un allergène, d'après Open Food Facts.
    Réponses possibles : "contient", "traces possibles" ou "inconnu".
    Ne répond JAMAIS "sans risque" : "inconnu" veut dire qu'on ne sait pas.
    Allergènes acceptés : les 14 allergènes réglementaires de l'UE."""
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
    """Estime si un produit convient à un régime : vegan, végétarien ou
    sans huile de palme. Réponses : "oui (estimé)", "non" ou "inconnu".
    C'est une estimation automatique, pas une certification."""
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
    """Donne la fiche d'un produit : nom, marque, quantité, catégories,
    origine, lieu de fabrication et URL de la photo. Un champ absent est
    indiqué "non renseigné" (jamais une valeur inventée)."""
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
    """Indique si un label est signalé sur un produit : bio (AB ou bio
    européen), commerce équitable, sans gluten ou Label Rouge.
    Réponses : "présent" ou "non signalé" (jamais "absent").
    Les labels sont déclarés par des contributeurs : vérifier l'emballage."""
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
    """Donne des chiffres sur un produit : Nutri-Score, groupe NOVA, score
    environnemental, additifs et valeurs pour 100 g (énergie en kcal,
    matières grasses, sucres, sel). Uniquement des données brutes :
    aucun conseil de santé, aucun jugement. Valeur absente : "non renseigné"."""
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
