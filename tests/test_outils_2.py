"""Tests des outils 4 à 6 (fiche_produit, verifier_label, infos_nutrition).
API simulée : aucun accès réseau."""
import asyncio
import json

import httpx
import pytest

import client_openfoodfacts as off
import regles
import serveur_mcp
from client_openfoodfacts import OpenFoodFactsError

CODE = "3017620422003"
RAISON = "Produit introuvable dans Open Food Facts"


def lancer(coroutine):
    return asyncio.run(coroutine)


class FauxClient:
    """Remplace le vrai client pour les 3 nouvelles méthodes."""

    def __init__(self, produit=None, erreur=None):
        self.produit, self.erreur, self.appels = produit, erreur, 0

    async def _repondre(self, code):
        self.appels += 1
        if self.erreur:
            raise self.erreur
        return self.produit

    produit_fiche = produit_labels = produit_nutrition = _repondre


@pytest.fixture
def faux(monkeypatch):
    def installer(**kw):
        f = FauxClient(**kw)
        monkeypatch.setattr(serveur_mcp, "client", f)
        return f
    return installer


def _erreur(cause):
    e = OpenFoodFactsError("x")
    e.__cause__ = cause
    return e


# --- Garde-fou : code-barres invalide, sans appel réseau ---------------------
@pytest.mark.parametrize("mauvais", ["123", "abcdefgh", "12345678901234", ""])
def test_code_barres_refuse_sans_appel_reseau(faux, mauvais):
    f = faux(produit={})
    for rep in (
        lancer(serveur_mcp.fiche_produit(mauvais)),
        lancer(serveur_mcp.verifier_label(mauvais, "bio")),
        lancer(serveur_mcp.infos_nutrition(mauvais)),
    ):
        assert "invalide" in rep["erreur"]
    assert f.appels == 0


# --- Garde-fou : produit introuvable -> inconnu + raison ----------------------
def test_produit_introuvable_inconnu_et_raison(faux):
    faux(produit=None)
    for rep in (
        lancer(serveur_mcp.fiche_produit(CODE)),
        lancer(serveur_mcp.verifier_label(CODE, "bio")),
        lancer(serveur_mcp.infos_nutrition(CODE)),
    ):
        assert rep == {"reponse": "inconnu", "raison": RAISON}


# --- Garde-fou : champ absent -> "non renseigné" ------------------------------
def test_fiche_champs_absents_non_renseignes(faux):
    faux(produit={"code": CODE, "product_name": "Pâtes", "brands": "", "origins": None})
    rep = lancer(serveur_mcp.fiche_produit(CODE))
    assert rep["nom"] == "Pâtes"
    for champ in ("marque", "quantite", "categories", "origine", "lieu_fabrication", "photo_url"):
        assert rep[champ] == "non renseigné"


def test_fiche_complete(faux):
    faux(produit={
        "product_name": "Nutella", "brands": "Ferrero", "quantity": "400 g",
        "categories": "Pâtes à tartiner", "origins": "France",
        "manufacturing_places": "Villers-Ecalles", "image_front_url": "https://x/y.jpg",
    })
    rep = lancer(serveur_mcp.fiche_produit(CODE))
    assert rep["marque"] == "Ferrero" and rep["photo_url"] == "https://x/y.jpg"
    assert "non renseigné" not in rep.values()


def test_nutrition_valeurs_absentes_non_renseignees(faux):
    faux(produit={"code": CODE})
    rep = lancer(serveur_mcp.infos_nutrition(CODE))
    assert rep["nutriscore"] == rep["groupe_nova"] == rep["score_environnemental"] == "non renseigné"
    assert rep["additifs"] == "non renseigné"
    assert set(rep["pour_100g"].values()) == {"non renseigné"}


def test_nutrition_zero_est_une_vraie_valeur(faux):
    faux(produit={"nutriments": {"sugars_100g": 0, "fat_100g": 0.0}})
    rep = lancer(serveur_mcp.infos_nutrition(CODE))
    assert rep["pour_100g"]["sucres_g"] == 0 and rep["pour_100g"]["matieres_grasses_g"] == 0.0


# --- Nutrition : score environnemental, unknown / not-applicable -------------
@pytest.mark.parametrize("valeur", ["unknown", "not-applicable", "", None])
def test_score_environnemental_inconnu(faux, valeur):
    faux(produit={"ecoscore_grade": valeur, "nutriscore_grade": valeur})
    rep = lancer(serveur_mcp.infos_nutrition(CODE))
    assert rep["score_environnemental"] == "non renseigné"
    assert rep["nutriscore"] == "non renseigné"


def test_score_environnemental_lettre_telle_quelle(faux):
    faux(produit={"ecoscore_grade": "c"})
    assert lancer(serveur_mcp.infos_nutrition(CODE))["score_environnemental"] == "C"


# --- Nutrition : uniquement des chiffres, aucun conseil -----------------------
def test_nutrition_sans_conseil_ni_jugement(faux):
    faux(produit={
        "nutriscore_grade": "e", "nova_group": 4, "additives_tags": ["en:e330"],
        "nutriments": {"energy-kcal_100g": 539, "fat_100g": 30.9, "sugars_100g": 56.3, "salt_100g": 0.107},
    })
    rep = lancer(serveur_mcp.infos_nutrition(CODE))
    assert rep["nutriscore"] == "E" and rep["groupe_nova"] == 4
    assert rep["additifs"] == ["en:e330"]
    assert rep["pour_100g"] == {"energie_kcal": 539, "matieres_grasses_g": 30.9, "sucres_g": 56.3, "sel_g": 0.107}
    texte = json.dumps(rep, ensure_ascii=False).lower()
    for mot in ("santé", "bon pour", "mauvais", "conseil", "recommand", "éviter", "dangereux"):
        # "santé" n'apparaît que dans la phrase de remarque ; on vérifie les autres
        if mot != "santé":
            assert mot not in texte


# --- Labels : choix, vocabulaire, avertissements -----------------------------
def test_label_non_prevu_liste_les_choix(faux):
    f = faux(produit={})
    rep = lancer(serveur_mcp.verifier_label(CODE, "vegan"))
    assert "non prévu" in rep["erreur"]
    for choix in ("bio", "commerce equitable", "sans gluten", "label rouge"):
        assert choix in rep["choix_possibles"]
    assert f.appels == 0


def test_label_present_et_non_signale(faux):
    faux(produit={"labels_tags": ["fr:ab-agriculture-biologique", "en:max-havelaar-france"]})
    assert lancer(serveur_mcp.verifier_label(CODE, "bio"))["reponse"] == "présent"
    assert lancer(serveur_mcp.verifier_label(CODE, "Commerce équitable"))["reponse"] == "présent"
    assert lancer(serveur_mcp.verifier_label(CODE, "label rouge"))["reponse"] == "non signalé"


def test_bio_europeen_compte_comme_bio(faux):
    faux(produit={"labels_tags": ["en:eu-organic"]})
    assert lancer(serveur_mcp.verifier_label(CODE, "bio"))["reponse"] == "présent"


def test_label_jamais_absent_ni_faux(faux):
    for produit in ({"code": CODE}, {"labels_tags": None}, {"labels_tags": []}, {"labels_tags": ["fr:triman"]}):
        faux(produit=produit)
        for label in regles.LABELS:
            rep = lancer(serveur_mcp.verifier_label(CODE, label))
            assert rep["reponse"] in {"présent", "non signalé"}
            assert "absent" not in rep["reponse"] and "faux" not in rep["reponse"]


def test_label_precise_declaration_par_contributeurs(faux):
    faux(produit={"labels_tags": []})
    rep = lancer(serveur_mcp.verifier_label(CODE, "bio"))
    assert "contributeurs" in rep["avertissement"] and "emballage" in rep["avertissement"]


def test_sans_gluten_renvoie_vers_verifier_allergene(faux):
    faux(produit={"labels_tags": ["en:no-gluten"]})
    rep = lancer(serveur_mcp.verifier_label(CODE, "sans gluten"))
    assert rep["reponse"] == "présent"
    assert "pas une garantie médicale" in rep["avertissement_gluten"]
    assert "verifier_allergene" in rep["avertissement_gluten"]


def test_rappel_gluten_seulement_pour_sans_gluten(faux):
    faux(produit={"labels_tags": ["en:organic"]})
    assert "avertissement_gluten" not in lancer(serveur_mcp.verifier_label(CODE, "bio"))


# --- Garde-fou : API qui ne répond pas ----------------------------------------
def test_timeout_message_clair(faux):
    faux(erreur=_erreur(httpx.ReadTimeout("lent")))
    for rep in (
        lancer(serveur_mcp.fiche_produit(CODE)),
        lancer(serveur_mcp.verifier_label(CODE, "bio")),
        lancer(serveur_mcp.infos_nutrition(CODE)),
    ):
        assert rep["reponse"] == "inconnu" and "timeout" in rep["erreur"]


def test_erreur_reseau_message_clair(faux):
    faux(erreur=_erreur(httpx.ConnectError("coupé")))
    assert "réseau" in lancer(serveur_mcp.infos_nutrition(CODE))["erreur"]


# --- Client : champs demandés, status != 1, lecture seule ---------------------
def _client_simule(handler):
    c = off.OpenFoodFactsClient()
    c._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), headers=c._client.headers)
    return c


def test_client_demande_les_bons_champs_en_get():
    vus = []

    def handler(request):
        vus.append((request.method, request.url.params["fields"], request.headers["User-Agent"]))
        return httpx.Response(200, json={"status": 1, "product": {"code": CODE}})

    c = _client_simule(handler)
    lancer(c.produit_fiche(CODE))
    lancer(c.produit_labels(CODE))
    lancer(c.produit_nutrition(CODE))
    assert {v[0] for v in vus} == {"GET"}
    assert "image_front_url" in vus[0][1]
    assert "labels_tags" in vus[1][1]
    assert "ecoscore_grade" in vus[2][1] and "nutriments" in vus[2][1]
    assert all("OpenFoodFactsMCP" in v[2] for v in vus)


def test_client_status_different_de_1_donne_none():
    c = _client_simule(lambda r: httpx.Response(200, json={"status": 0}))
    assert lancer(c.produit_fiche(CODE)) is None
    assert lancer(c.produit_labels(CODE)) is None
    assert lancer(c.produit_nutrition(CODE)) is None
