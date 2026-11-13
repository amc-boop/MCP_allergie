"""
Règles de décision (sans aucun appel réseau).

Ici on décide quoi répondre à partir des données d'Open Food Facts.
Principe de sécurité : on ne dit JAMAIS "sans risque". Si une donnée
manque ou est incertaine, la réponse est "inconnu".
"""
from __future__ import annotations

import re
import unicodedata

# --- Réponses possibles (les seules que les outils peuvent renvoyer) -------
CONTIENT = "contient"
TRACES = "traces possibles"
INCONNU = "inconnu"

OUI_ESTIME = "oui (estimé)"
NON = "non"

AVERTISSEMENT_REGIME = (
    "Estimation automatique faite à partir de la liste d'ingrédients : "
    "ce n'est pas une certification. Vérifier l'emballage en cas de doute."
)
AVERTISSEMENT_ALLERGENE = (
    "Données collaboratives d'Open Food Facts, parfois incomplètes. "
    "'inconnu' ne veut pas dire 'sans risque' : vérifier l'emballage."
)

# --- Les 14 allergènes réglementaires de l'UE ------------------------------
# nom français (sans accent, en minuscules) -> étiquette Open Food Facts
ALLERGENES = {
    "gluten": "en:gluten",
    "crustaces": "en:crustaceans",
    "oeufs": "en:eggs",
    "poisson": "en:fish",
    "arachides": "en:peanuts",
    "soja": "en:soybeans",
    "lait": "en:milk",
    "fruits a coque": "en:nuts",
    "celeri": "en:celery",
    "moutarde": "en:mustard",
    "sesame": "en:sesame-seeds",
    "sulfites": "en:sulphur-dioxide-and-sulphites",
    "lupin": "en:lupin",
    "mollusques": "en:molluscs",
}

# Variantes acceptées (singulier, etc.) -> nom officiel ci-dessus
SYNONYMES_ALLERGENES = {
    "oeuf": "oeufs",
    "arachide": "arachides",
    "crustace": "crustaces",
    "mollusque": "mollusques",
    "sulfite": "sulfites",
}

# --- Régimes : pour chacun, l'étiquette "oui" et l'étiquette "non" ----------
# Toute autre étiquette (maybe, unknown...) donnera "inconnu".
REGIMES = {
    "vegan": {"oui": "en:vegan", "non": "en:non-vegan"},
    "vegetarien": {"oui": "en:vegetarian", "non": "en:non-vegetarian"},
    "sans huile de palme": {"oui": "en:palm-oil-free", "non": "en:palm-oil"},
}

SYNONYMES_REGIMES = {
    "vegetarian": "vegetarien",
    "vegane": "vegan",
    "sans palme": "sans huile de palme",
}


def _simplifier(texte: str) -> str:
    """Minuscules, sans accents, espaces propres : "Œufs " -> "oeufs"."""
    texte = (texte or "").strip().lower().replace("œ", "oe").replace("æ", "ae")
    texte = unicodedata.normalize("NFD", texte)
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texte)


# --- Garde-fous sur les entrées --------------------------------------------
def valider_code_barres(code: str) -> str | None:
    """Renvoie le code nettoyé s'il a 8 à 13 chiffres, sinon None."""
    code = (code or "").strip()
    # [0-9] et non \d : \d accepterait aussi des chiffres d'autres alphabets
    if re.fullmatch(r"[0-9]{8,13}", code):
        return code
    return None


def normaliser_allergene(allergene: str) -> str | None:
    """Renvoie le nom officiel de l'allergène, ou None s'il n'est pas prévu."""
    nom = _simplifier(allergene)
    nom = SYNONYMES_ALLERGENES.get(nom, nom)
    return nom if nom in ALLERGENES else None


def normaliser_regime(regime: str) -> str | None:
    """Renvoie le nom officiel du régime, ou None s'il n'est pas prévu."""
    nom = _simplifier(regime)
    nom = SYNONYMES_REGIMES.get(nom, nom)
    return nom if nom in REGIMES else None


def liste_allergenes() -> str:
    return ", ".join(ALLERGENES)


def liste_regimes() -> str:
    return ", ".join(REGIMES)


# --- Les décisions ----------------------------------------------------------
def verdict_allergene(produit: dict | None, allergene: str) -> str:
    """
    allergene : nom officiel (déjà passé par normaliser_allergene).
    Renvoie "contient", "traces possibles" ou "inconnu" - jamais autre chose.
    """
    if not produit:  # produit introuvable : on n'invente rien
        return INCONNU
    etiquette = ALLERGENES[allergene]
    if etiquette in (produit.get("allergens_tags") or []):
        return CONTIENT
    if etiquette in (produit.get("traces_tags") or []):
        return TRACES
    # Absent des données : cela ne prouve PAS l'absence -> inconnu
    return INCONNU


def verdict_regime(produit: dict | None, regime: str) -> str:
    """
    regime : nom officiel (déjà passé par normaliser_regime).
    Renvoie "oui (estimé)", "non" ou "inconnu".
    """
    if not produit:
        return INCONNU
    tags = produit.get("ingredients_analysis_tags") or []
    if REGIMES[regime]["oui"] in tags:
        return OUI_ESTIME
    if REGIMES[regime]["non"] in tags:
        return NON
    # "maybe-...", "...-unknown", ou étiquette absente -> inconnu
    return INCONNU


# =========================================================================
# Ajouts : fiche produit, labels, nutrition
# =========================================================================
NON_RENSEIGNE = "non renseigné"

# Valeurs qu'Open Food Facts met quand il ne sait pas : on les traite
# comme "absent", sans jamais inventer une valeur à la place.
_VALEURS_VIDES = {"", "unknown", "en:unknown", "not-applicable", "not applicable"}


def valeur_ou_non_renseigne(valeur):
    """Renvoie la valeur, ou "non renseigné" si elle est absente ou vide.
    Attention : 0 est une vraie valeur (ex. 0 g de sucre), on la garde."""
    if valeur is None:
        return NON_RENSEIGNE
    if isinstance(valeur, str):
        valeur = valeur.strip()
        if valeur.lower() in _VALEURS_VIDES:
            return NON_RENSEIGNE
    return valeur


def construire_fiche(produit: dict) -> dict:
    """Fiche produit : chaque champ absent devient "non renseigné"."""
    champs = {
        "nom": "product_name",
        "marque": "brands",
        "quantite": "quantity",
        "categories": "categories",
        "origine": "origins",
        "lieu_fabrication": "manufacturing_places",
        "photo_url": "image_front_url",
    }
    return {cle: valeur_ou_non_renseigne(produit.get(champ)) for cle, champ in champs.items()}


def _nombre_ou_non_renseigne(valeur):
    """Un nombre (int ou float), sinon "non renseigné"."""
    if isinstance(valeur, bool):
        return NON_RENSEIGNE
    if isinstance(valeur, (int, float)):
        return valeur
    if isinstance(valeur, str):
        try:
            return float(valeur)
        except ValueError:
            pass
    return NON_RENSEIGNE


def _lettre_ou_non_renseigne(valeur):
    """Une note (A, B...) en majuscule ; "unknown"/"not-applicable" -> non renseigné."""
    valeur = valeur_ou_non_renseigne(valeur)
    return valeur.upper() if isinstance(valeur, str) and valeur != NON_RENSEIGNE else NON_RENSEIGNE


def construire_nutrition(produit: dict) -> dict:
    """Seulement des faits chiffrés : aucun jugement, aucun conseil."""
    n = produit.get("nutriments") or {}
    additifs = produit.get("additives_tags")
    return {
        "nutriscore": _lettre_ou_non_renseigne(produit.get("nutriscore_grade")),
        "groupe_nova": _nombre_ou_non_renseigne(produit.get("nova_group")),
        "score_environnemental": _lettre_ou_non_renseigne(produit.get("ecoscore_grade")),
        # tags bruts (ex. "en:e330"). Liste vide = aucun additif enregistré
        "additifs": NON_RENSEIGNE if additifs is None else list(additifs),
        "pour_100g": {
            "energie_kcal": _nombre_ou_non_renseigne(n.get("energy-kcal_100g")),
            "matieres_grasses_g": _nombre_ou_non_renseigne(n.get("fat_100g")),
            "sucres_g": _nombre_ou_non_renseigne(n.get("sugars_100g")),
            "sel_g": _nombre_ou_non_renseigne(n.get("salt_100g")),
        },
    }


# --- Labels -----------------------------------------------------------------
PRESENT = "présent"
NON_SIGNALE = "non signalé"  # jamais "absent" ni "faux"

# label -> étiquettes brutes (vérifiées dans la taxonomie Open Food Facts)
LABELS = {
    "bio": ["en:organic", "fr:ab-agriculture-biologique", "en:eu-organic"],
    "commerce equitable": [
        "en:fair-trade",
        "en:fairtrade-international",
        "en:max-havelaar",
        "en:max-havelaar-france",
        "en:fair-for-life",
    ],
    "sans gluten": ["en:no-gluten"],
    "label rouge": ["fr:label-rouge"],
}

SYNONYMES_LABELS = {
    "biologique": "bio",
    "ab": "bio",
    "bio europeen": "bio",
    "equitable": "commerce equitable",
    "fair trade": "commerce equitable",
    "fairtrade": "commerce equitable",
}

AVERTISSEMENT_LABEL = (
    "Les labels sont déclarés par des contributeurs d'Open Food Facts, "
    "ils ne sont pas contrôlés. Vérifier le logo sur l'emballage."
)
AVERTISSEMENT_GLUTEN = (
    "'Sans gluten' est un label, pas une garantie médicale. Pour une allergie "
    "ou une maladie coeliaque, utiliser aussi verifier_allergene (allergène : gluten)."
)


def normaliser_label(label: str) -> str | None:
    """Renvoie le nom officiel du label, ou None s'il n'est pas prévu."""
    nom = _simplifier(label)
    nom = SYNONYMES_LABELS.get(nom, nom)
    return nom if nom in LABELS else None


def liste_labels() -> str:
    return ", ".join(LABELS)


def verdict_label(produit: dict | None, label: str) -> str:
    """Renvoie "présent" ou "non signalé" (ou "inconnu" si produit introuvable)."""
    if not produit:
        return INCONNU
    tags = produit.get("labels_tags") or []
    if any(t in tags for t in LABELS[label]):
        return PRESENT
    return NON_SIGNALE
