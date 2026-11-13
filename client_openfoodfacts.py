"""Client minimal pour l'API Open Food Facts (produits alimentaires uniquement)."""
from __future__ import annotations

import os
from typing import Any

import httpx

URL_OPEN_FOOD_FACTS = "https://world.openfoodfacts.org"

# Open Food Facts demande un User-Agent qui identifie votre appli
USER_AGENT = os.getenv(
    "OFF_USER_AGENT", "OpenFoodFactsMCP/0.1 (votre-email@exemple.com)"
)

# Champs demandés à l'API (limite la taille des réponses)
CHAMPS_RESUME = [
    "code",
    "product_name",
    "brands",
    "quantity",
    "categories",
    "nutriscore_grade",
    "nova_group",
    "ecoscore_grade",
    "image_front_small_url",
]

CHAMPS_DETAIL = CHAMPS_RESUME + [
    "generic_name",
    "ingredients_text",
    "allergens_tags",
    "traces_tags",
    "additives_tags",
    "labels",
    "origins",
    "manufacturing_places",
    "packaging",
    "stores",
    "countries",
    "serving_size",
    "nutriments",
]

# Ajout : champs pour fiche_produit, verifier_label et infos_nutrition
CHAMPS_FICHE = [
    "code",
    "product_name",
    "brands",
    "quantity",
    "categories",
    "origins",
    "manufacturing_places",
    "image_front_url",
]
CHAMPS_LABELS = ["code", "labels_tags"]
CHAMPS_NUTRITION = [
    "code",
    "nutriscore_grade",
    "nova_group",
    "ecoscore_grade",  # score environnemental (nom du champ vérifié sur l'API)
    "additives_tags",
    "nutriments",
]

# Ajout : champs bruts pour verifier_allergene et verifier_regime
CHAMPS_VERIFICATION = [
    "code",
    "allergens_tags",
    "traces_tags",
    "ingredients_analysis_tags",
]

NUTRIMENTS_UTILES = {
    "energy-kcal_100g": "energie_kcal",
    "fat_100g": "matieres_grasses_g",
    "saturated-fat_100g": "acides_gras_satures_g",
    "carbohydrates_100g": "glucides_g",
    "sugars_100g": "sucres_g",
    "fiber_100g": "fibres_g",
    "proteins_100g": "proteines_g",
    "salt_100g": "sel_g",
}


class OpenFoodFactsError(Exception):
    """Erreur renvoyée lors d'un appel à l'API."""


class OpenFoodFactsClient:
    def __init__(self, timeout: float = 20.0) -> None:
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> dict:
        try:
            rep = await self._client.get(url, params=params)
            rep.raise_for_status()
            return rep.json()
        except httpx.HTTPStatusError as e:
            raise OpenFoodFactsError(
                f"L'API a répondu {e.response.status_code} pour {e.request.url}"
            ) from e
        except httpx.HTTPError as e:
            raise OpenFoodFactsError(f"Erreur réseau : {e}") from e

    # --- Recherche par nom (texte libre) -------------------------------
    async def rechercher(self, nom: str, nb: int = 5, page: int = 1) -> dict:
        params = {
            "search_terms": nom,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page": page,
            "page_size": nb,
            "fields": ",".join(CHAMPS_RESUME),
        }
        data = await self._get(f"{URL_OPEN_FOOD_FACTS}/cgi/search.pl", params)
        return {
            "total": data.get("count", 0),
            "page": page,
            "produits": [resumer(p) for p in data.get("products", [])],
        }

    # --- Recherche par filtres (catégorie, marque, Nutri-Score…) -------
    async def filtrer(
        self,
        categorie: str | None = None,
        marque: str | None = None,
        nutriscore: str | None = None,
        pays: str | None = None,
        nb: int = 10,
        page: int = 1,
    ) -> dict:
        params: dict[str, Any] = {
            "page": page,
            "page_size": nb,
            "fields": ",".join(CHAMPS_RESUME),
        }
        if categorie:
            params["categories_tags"] = categorie
        if marque:
            params["brands_tags"] = marque
        if nutriscore:
            params["nutrition_grades_tags"] = nutriscore.lower()
        if pays:
            params["countries_tags"] = pays
        data = await self._get(f"{URL_OPEN_FOOD_FACTS}/api/v2/search", params)
        return {
            "total": data.get("count", 0),
            "page": page,
            "produits": [resumer(p) for p in data.get("products", [])],
        }

    # --- Fiche produit par code-barres ---------------------------------
    async def produit(self, code_barres: str) -> dict | None:
        params = {"fields": ",".join(CHAMPS_DETAIL)}
        data = await self._get(
            f"{URL_OPEN_FOOD_FACTS}/api/v2/product/{code_barres}.json", params
        )
        if data.get("status") != 1 or not data.get("product"):
            return None
        return detailler(data["product"])

    # --- Ajout : données brutes pour les vérifications (lecture seule) --
    async def produit_brut(self, code_barres: str) -> dict | None:
        """Renvoie les étiquettes telles que l'API les donne, sans les
        modifier (ex. "en:milk"). None si le produit est introuvable."""
        params = {"fields": ",".join(CHAMPS_VERIFICATION)}
        data = await self._get(
            f"{URL_OPEN_FOOD_FACTS}/api/v2/product/{code_barres}.json", params
        )
        if data.get("status") != 1 or not data.get("product"):
            return None
        return data["product"]

    # --- Ajout : lecture de champs précis (GET uniquement) --------------
    async def _produit_champs(self, code_barres: str, champs: list[str]) -> dict | None:
        """Lit seulement les champs demandés, sans les modifier.
        None si le produit est introuvable (status différent de 1)."""
        data = await self._get(
            f"{URL_OPEN_FOOD_FACTS}/api/v2/product/{code_barres}.json",
            {"fields": ",".join(champs)},
        )
        if data.get("status") != 1 or not data.get("product"):
            return None
        return data["product"]

    async def produit_fiche(self, code_barres: str) -> dict | None:
        return await self._produit_champs(code_barres, CHAMPS_FICHE)

    async def produit_labels(self, code_barres: str) -> dict | None:
        return await self._produit_champs(code_barres, CHAMPS_LABELS)

    async def produit_nutrition(self, code_barres: str) -> dict | None:
        return await self._produit_champs(code_barres, CHAMPS_NUTRITION)


# --- Mise en forme des réponses ------------------------------------------
def _maj(val: Any) -> Any:
    return val.upper() if isinstance(val, str) else val


def resumer(p: dict) -> dict:
    return {
        "code_barres": p.get("code"),
        "nom": p.get("product_name") or None,
        "marques": p.get("brands") or None,
        "quantite": p.get("quantity") or None,
        "nutriscore": _maj(p.get("nutriscore_grade")),
        "nova": p.get("nova_group"),
        "green_score": _maj(p.get("ecoscore_grade")),
        "image": p.get("image_front_small_url"),
    }


def _nettoyer_tags(tags: list[str] | None) -> list[str]:
    # "en:gluten" -> "gluten"
    return [t.split(":", 1)[-1] for t in (tags or [])]


def detailler(p: dict) -> dict:
    n = p.get("nutriments") or {}
    fiche = resumer(p)
    fiche.update(
        {
            "nom_generique": p.get("generic_name") or None,
            "categories": p.get("categories") or None,
            "ingredients": p.get("ingredients_text") or None,
            "allergenes": _nettoyer_tags(p.get("allergens_tags")),
            "traces": _nettoyer_tags(p.get("traces_tags")),
            "additifs": _nettoyer_tags(p.get("additives_tags")),
            "labels": p.get("labels") or None,
            "origines": p.get("origins") or None,
            "lieux_fabrication": p.get("manufacturing_places") or None,
            "emballage": p.get("packaging") or None,
            "magasins": p.get("stores") or None,
            "pays_vente": p.get("countries") or None,
            "portion": p.get("serving_size") or None,
            "nutrition_pour_100g": {
                cle_fr: n.get(cle) for cle, cle_fr in NUTRIMENTS_UTILES.items()
            },
            "url": f"{URL_OPEN_FOOD_FACTS}/product/{p.get('code')}",
        }
    )
    return fiche
