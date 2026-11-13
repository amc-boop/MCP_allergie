"""Tests des règles (sans réseau) : un test par garde-fou."""
import pytest

import regles


# --- Garde-fou : code-barres de 8 à 13 chiffres ---------------------------
@pytest.mark.parametrize("code", ["12345678", "3017620422003", " 3017620422003 "])
def test_code_barres_valide(code):
    assert regles.valider_code_barres(code) == code.strip()


@pytest.mark.parametrize(
    "code", ["1234567", "12345678901234", "abcdefgh", "3017-6204", "", None, "../x12345678", "١٢٣٤٥٦٧٨"]
)
def test_code_barres_invalide(code):
    assert regles.valider_code_barres(code) is None


# --- Garde-fou : allergène / régime non prévu ------------------------------
def test_allergene_non_prevu():
    assert regles.normaliser_allergene("chocolat") is None


def test_allergene_accents_et_majuscules():
    assert regles.normaliser_allergene("Œufs") == "oeufs"
    assert regles.normaliser_allergene("FRUITS À COQUE") == "fruits a coque"
    assert regles.normaliser_allergene("arachide") == "arachides"


def test_les_14_allergenes_sont_la():
    assert len(regles.ALLERGENES) == 14


def test_regime_non_prevu():
    assert regles.normaliser_regime("keto") is None


def test_regime_accents():
    assert regles.normaliser_regime("Végétarien") == "vegetarien"


# --- Allergènes : jamais "sans risque" -------------------------------------
def test_contient():
    p = {"allergens_tags": ["en:milk"], "traces_tags": []}
    assert regles.verdict_allergene(p, "lait") == "contient"


def test_traces():
    p = {"allergens_tags": [], "traces_tags": ["en:gluten"]}
    assert regles.verdict_allergene(p, "gluten") == "traces possibles"


def test_allergene_absent_des_donnees_donne_inconnu():
    p = {"allergens_tags": ["en:milk"], "traces_tags": []}
    assert regles.verdict_allergene(p, "arachides") == "inconnu"


def test_produit_sans_donnees_allergenes_donne_inconnu():
    # Produit trouvé mais sans aucun champ allergènes / traces
    assert regles.verdict_allergene({"code": "12345678"}, "lait") == "inconnu"
    assert regles.verdict_allergene({"allergens_tags": None, "traces_tags": None}, "lait") == "inconnu"


def test_produit_introuvable_donne_inconnu():
    assert regles.verdict_allergene(None, "lait") == "inconnu"
    assert regles.verdict_regime(None, "vegan") == "inconnu"


def test_jamais_sans_risque():
    cas = [None, {}, {"allergens_tags": []}, {"traces_tags": ["en:milk"]}, {"allergens_tags": ["en:milk"]}]
    for p in cas:
        for a in regles.ALLERGENES:
            assert regles.verdict_allergene(p, a) in {"contient", "traces possibles", "inconnu"}


# --- Régimes ----------------------------------------------------------------
def test_regime_oui_et_non():
    assert regles.verdict_regime({"ingredients_analysis_tags": ["en:vegan"]}, "vegan") == "oui (estimé)"
    assert regles.verdict_regime({"ingredients_analysis_tags": ["en:non-vegan"]}, "vegan") == "non"
    assert regles.verdict_regime({"ingredients_analysis_tags": ["en:palm-oil-free"]}, "sans huile de palme") == "oui (estimé)"
    assert regles.verdict_regime({"ingredients_analysis_tags": ["en:palm-oil"]}, "sans huile de palme") == "non"


@pytest.mark.parametrize("tag", ["en:maybe-vegan", "en:vegan-status-unknown", "en:maybe-vegetarian", "en:vegetarian-status-unknown"])
def test_maybe_et_unknown_donnent_inconnu(tag):
    p = {"ingredients_analysis_tags": [tag]}
    assert regles.verdict_regime(p, "vegan") == "inconnu"
    assert regles.verdict_regime(p, "vegetarien") == "inconnu"


def test_regime_sans_donnees_donne_inconnu():
    assert regles.verdict_regime({}, "vegan") == "inconnu"
