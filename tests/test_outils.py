"""Tests des outils MCP, avec une fausse API (aucun accès réseau)."""
import asyncio

import httpx
import pytest

import client_openfoodfacts as off
import serveur_mcp
from client_openfoodfacts import OpenFoodFactsError

CODE = "3017620422003"


def lancer(coroutine):
    return asyncio.run(coroutine)


class FauxClient:
    """Remplace le vrai client : renvoie un produit ou lève une erreur."""

    def __init__(self, produit=None, erreur=None, resultats=None):
        self.produit, self.erreur, self.resultats = produit, erreur, resultats
        self.appels = 0

    async def produit_brut(self, code):
        self.appels += 1
        if self.erreur:
            raise self.erreur
        return self.produit

    async def rechercher(self, nom, nb=5, page=1):
        self.appels += 1
        if self.erreur:
            raise self.erreur
        return {"total": len(self.resultats), "page": 1, "produits": self.resultats}


@pytest.fixture
def faux(monkeypatch):
    def installer(**kw):
        f = FauxClient(**kw)
        monkeypatch.setattr(serveur_mcp, "client", f)
        return f
    return installer


# --- Garde-fou : code-barres invalide, sans appel à l'API -------------------
def test_code_barres_refuse_sans_appeler_lapi(faux):
    f = faux(produit={})
    for outil, arg in [(serveur_mcp.verifier_allergene, "lait"), (serveur_mcp.verifier_regime, "vegan")]:
        rep = lancer(outil("123", arg))
        assert "invalide" in rep["erreur"]
    assert f.appels == 0


# --- Garde-fou : produit introuvable -> "inconnu" ---------------------------
def test_produit_introuvable(faux):
    faux(produit=None)
    assert lancer(serveur_mcp.verifier_allergene(CODE, "lait"))["reponse"] == "inconnu"
    assert lancer(serveur_mcp.verifier_regime(CODE, "vegan"))["reponse"] == "inconnu"


def test_produit_introuvable_donne_une_raison(faux):
    faux(produit=None)
    attendu = "Produit introuvable dans Open Food Facts"
    assert lancer(serveur_mcp.verifier_allergene(CODE, "lait"))["raison"] == attendu
    assert lancer(serveur_mcp.verifier_regime(CODE, "vegan"))["raison"] == attendu


def test_pas_de_raison_quand_le_produit_existe(faux):
    faux(produit={"allergens_tags": ["en:milk"], "ingredients_analysis_tags": ["en:vegan"]})
    assert "raison" not in lancer(serveur_mcp.verifier_allergene(CODE, "lait"))
    assert "raison" not in lancer(serveur_mcp.verifier_regime(CODE, "vegan"))


def test_client_status_different_de_1_donne_none(monkeypatch):
    """Le vrai client renvoie None si status != 1 (API simulée)."""
    c = off.OpenFoodFactsClient()

    async def faux_get(url, params=None):
        return {"status": 0, "status_verbose": "product not found"}

    monkeypatch.setattr(c, "_get", faux_get)
    assert lancer(c.produit_brut(CODE)) is None


# --- Garde-fou : allergène / régime non prévu, avec la liste des choix ------
def test_allergene_non_prevu_liste_les_choix(faux):
    f = faux(produit={})
    rep = lancer(serveur_mcp.verifier_allergene(CODE, "chocolat"))
    assert "non prévu" in rep["erreur"] and "lait" in rep["choix_possibles"]
    assert f.appels == 0


def test_regime_non_prevu_liste_les_choix(faux):
    faux(produit={})
    rep = lancer(serveur_mcp.verifier_regime(CODE, "keto"))
    assert "non prévu" in rep["erreur"] and "vegan" in rep["choix_possibles"]


# --- Garde-fou : API qui ne répond pas --------------------------------------
def _erreur(cause):
    e = OpenFoodFactsError("x")
    e.__cause__ = cause
    return e


def test_timeout_message_clair(faux):
    faux(erreur=_erreur(httpx.ReadTimeout("lent")))
    rep = lancer(serveur_mcp.verifier_allergene(CODE, "lait"))
    assert rep["reponse"] == "inconnu" and "timeout" in rep["erreur"]


def test_erreur_reseau_message_clair(faux):
    faux(erreur=_erreur(httpx.ConnectError("coupé")))
    for rep in (
        lancer(serveur_mcp.verifier_regime(CODE, "vegan")),
        lancer(serveur_mcp.chercher_produit("nutella")),
    ):
        assert "réseau" in rep["erreur"]


def test_le_vrai_client_convertit_les_erreurs_httpx(monkeypatch):
    c = off.OpenFoodFactsClient()

    async def boom(*a, **k):
        raise httpx.ConnectTimeout("lent")

    monkeypatch.setattr(c._client, "get", boom)
    with pytest.raises(OpenFoodFactsError) as info:
        lancer(c.produit_brut(CODE))
    assert isinstance(info.value.__cause__, httpx.TimeoutException)


# --- Garde-fou : User-Agent --------------------------------------------------
def test_user_agent_nomme_lapplication():
    c = off.OpenFoodFactsClient()
    ua = c._client.headers["User-Agent"]
    assert "OpenFoodFactsMCP" in ua  # nom de l'appli (sauf si OFF_USER_AGENT est défini)
    assert "python-httpx" not in ua


# --- Garde-fou : lecture seule (uniquement des GET) --------------------------
def test_lecture_seule_uniquement_des_get():
    methodes = []

    def handler(request):
        methodes.append(request.method)
        return httpx.Response(200, json={"status": 1, "product": {"code": CODE}, "products": []})

    c = off.OpenFoodFactsClient()
    c._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), headers=c._client.headers)
    lancer(c.produit_brut(CODE))
    lancer(c.rechercher("lait"))
    assert methodes and set(methodes) == {"GET"}


# --- chercher_produit --------------------------------------------------------
def test_recherche_nom_vide(faux):
    f = faux(resultats=[])
    assert "vide" in lancer(serveur_mcp.chercher_produit("   "))["erreur"]
    assert f.appels == 0


def test_recherche_5_resultats_max_et_3_champs(faux):
    produits = [
        {"code_barres": str(10000000 + i), "nom": f"P{i}", "marques": "M", "nutriscore": "A"}
        for i in range(8)
    ]
    faux(resultats=produits)
    rep = lancer(serveur_mcp.chercher_produit("pâtes"))
    assert len(rep["produits"]) == 5
    assert set(rep["produits"][0]) == {"nom", "marque", "code_barres"}


# --- Réponses des outils ------------------------------------------------------
def test_produit_sans_donnees_allergenes_repond_inconnu(faux):
    faux(produit={"code": CODE})  # produit trouvé, mais aucune donnée d'allergènes
    assert lancer(serveur_mcp.verifier_allergene(CODE, "lait"))["reponse"] == "inconnu"


def test_allergene_contient_et_traces(faux):
    faux(produit={"allergens_tags": ["en:milk"], "traces_tags": ["en:nuts"]})
    assert lancer(serveur_mcp.verifier_allergene(CODE, "lait"))["reponse"] == "contient"
    assert lancer(serveur_mcp.verifier_allergene(CODE, "fruits à coque"))["reponse"] == "traces possibles"


def test_regime_precise_que_cest_une_estimation(faux):
    faux(produit={"ingredients_analysis_tags": ["en:vegan"]})
    rep = lancer(serveur_mcp.verifier_regime(CODE, "vegan"))
    assert rep["reponse"] == "oui (estimé)"
    assert "pas une certification" in rep["avertissement"]
