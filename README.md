# Serveur MCP Open Food Facts

Serveur [MCP](https://modelcontextprotocol.io) qui permet à Claude Code (ou à tout autre client MCP) d'interroger la base ouverte **Open Food Facts**, limitée aux produits alimentaires.

- Aucune clé d'API n'est nécessaire.
- Tous les outils sont en **lecture seule**.
- Fonctionne sur **macOS**, **Linux** et **Windows**.

---

## Sommaire

1. [Outils disponibles](#1-outils-disponibles)
2. [Installation](#2-installation)
3. [Connecter le serveur à Claude Code](#3-connecter-le-serveur-à-claude-code)
4. [Identifier votre projet auprès d'Open Food Facts (optionnel)](#4-identifier-votre-projet-auprès-dopen-food-facts-optionnel)
5. [Tester sans Claude](#5-tester-sans-claude)
6. [Lancer les tests](#6-lancer-les-tests)
7. [Structure du projet](#7-structure-du-projet)
8. [Règles d'usage d'Open Food Facts](#8-règles-dusage-dopen-food-facts)

---

## 1. Outils disponibles

| Outil | Ce qu'il fait |
|---|---|
| `chercher_produit(nom)` | Cherche un produit par son nom (5 résultats max) : nom, marque, code-barres. |
| `fiche_produit(code_barres)` | Nom, marque, quantité, catégories, origine, lieu de fabrication, URL de la photo. Champ absent : « non renseigné ». |
| `verifier_allergene(code_barres, allergene)` | Répond « contient », « traces possibles » ou « inconnu ». Ne répond **jamais** « sans risque ». |
| `verifier_regime(code_barres, regime)` | Vegan, végétarien ou sans huile de palme : « oui (estimé) », « non » ou « inconnu ». C'est une estimation, pas une certification. |
| `verifier_label(code_barres, label)` | Bio (AB ou bio européen), commerce équitable, sans gluten, Label Rouge : « présent » ou « non signalé ». Les labels sont déclarés par des contributeurs : vérifiez l'emballage. |
| `infos_nutrition(code_barres)` | Nutri-Score, groupe NOVA, score environnemental, additifs, valeurs pour 100 g (kcal, matières grasses, sucres, sel). Uniquement des chiffres, aucun conseil de santé. |

Les règles de décision (allergènes, régimes, labels) sont dans `regles.py`.

---

## 2. Installation

### Prérequis

- [Claude Code](https://docs.claude.com/en/docs/claude-code) installé (commande `claude` disponible dans le terminal).
- [uv](https://docs.astral.sh/uv/), le gestionnaire Python. Il crée l'environnement virtuel et installe les dépendances (déclarées dans `pyproject.toml`) automatiquement au premier lancement. Pas besoin d'installer Python à la main.

### Installer uv

**macOS / Linux** (Terminal) :

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Ou, avec Homebrew sur Mac :

```bash
brew install uv
```

**Windows** (PowerShell) :

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Fermez puis rouvrez le terminal, et vérifiez :

```bash
uv --version
```

### Récupérer le projet

Identique sur macOS, Linux et Windows :

```bash
git clone <url-du-depot>
cd openfoodfacts-mcp
```

> Le nom du dossier n'a pas d'importance : l'essentiel est de lancer les commandes suivantes **depuis la racine du projet** (là où se trouve `serveur_mcp.py`).

---

## 3. Connecter le serveur à Claude Code

Les commandes ci-dessous sont **identiques sur macOS (Terminal) et Windows (PowerShell)**.

### Ajouter le serveur

Depuis la racine du projet :

```bash
claude mcp add openfoodfacts -- uv run serveur_mcp.py
```

Le serveur est alors disponible dans Claude Code, **uniquement quand vous travaillez dans ce dossier**.

> **Partager la configuration avec l'équipe** : ajoutez `--scope project` pour créer un fichier `.mcp.json` à committer dans Git :
>
> ```bash
> claude mcp add --scope project openfoodfacts -- uv run serveur_mcp.py
> ```

### Vérifier que ça marche

```bash
claude mcp list
```

Puis lancez `claude` dans ce dossier et tapez `/mcp` pour voir le serveur et ses outils.

Exemple de question à poser à Claude : *« Est-ce que le Nutella contient des traces de fruits à coque ? »*

### Retirer le serveur

```bash
claude mcp remove openfoodfacts
```

---

## 4. Identifier votre projet auprès d'Open Food Facts (optionnel)

Open Food Facts demande à chaque application de s'identifier via un **User-Agent** : un petit texte envoyé avec chaque requête, qui indique le nom de l'appli et un moyen de contacter son auteur. Cela leur permet de vous joindre en cas de problème (trop de requêtes, bug…) plutôt que de bloquer l'accès.

Par défaut, le serveur envoie `OpenFoodFactsMCP/0.1 (votre-email@exemple.com)`. Ça fonctionne, mais ce n'est pas *votre* identité. Pour un usage régulier ou public, il est **recommandé** de renseigner la vôtre avec la variable d'environnement `OFF_USER_AGENT`.

Pour cela, ajoutez l'option `-e` à la commande d'installation (à la place de celle de la section 3) :

```bash
claude mcp add openfoodfacts -e OFF_USER_AGENT="MonProjet/1.0 (vous@exemple.com)" -- uv run serveur_mcp.py
```

- `-e OFF_USER_AGENT="..."` : transmet la variable au serveur à chaque lancement par Claude Code.
- Remplacez `MonProjet/1.0` par le nom et la version de votre projet, et `vous@exemple.com` par votre adresse e-mail.
- Cette commande fonctionne telle quelle sur macOS et sur Windows (PowerShell).

> Si le serveur est déjà ajouté, retirez-le d'abord avec `claude mcp remove openfoodfacts`, puis relancez la commande ci-dessus.

---

## 5. Tester sans Claude

L'inspecteur MCP ouvre une interface web pour appeler les outils à la main :

```bash
uv run mcp dev serveur_mcp.py
```

---

## 6. Lancer les tests

Les tests simulent l'API (pas d'appel réseau) :

```bash
uv run pytest
```

---

## 7. Structure du projet

```
./
├── pyproject.toml           # Dépendances (lu par uv)
├── serveur_mcp.py           # Point d'entrée : serveur MCP et définition des outils
├── client_openfoodfacts.py  # Appels HTTP à l'API Open Food Facts + mise en forme des réponses
├── regles.py                # Règles de décision allergènes / régimes / labels (sans réseau)
├── tests/                   # Tests pytest (API simulée)
└── README.md
```

**Ajouter un outil** :

1. Écrivez la méthode dans `client_openfoodfacts.py`.
2. Ajoutez une fonction décorée par `@mcp.tool()` dans `serveur_mcp.py`.
3. Soignez la docstring : c'est elle que Claude lit pour savoir quand utiliser l'outil.

---

## 8. Règles d'usage d'Open Food Facts

- Un appel API doit correspondre à un vrai besoin utilisateur. Pour de gros volumes, utilisez les exports quotidiens : https://world.openfoodfacts.org/data
- Identifiez votre application avec un User-Agent (voir [section 4](#4-identifier-votre-projet-auprès-dopen-food-facts-optionnel)).
- Licences : base sous ODbL, contenus sous DbCL, images sous CC BY-SA. Citez Open Food Facts si vous réutilisez les données.

Documentation de l'API : https://openfoodfacts.github.io/documentation/docs/Product-Opener/api/
