# Serveur MCP Open Food Facts

Serveur [MCP](https://modelcontextprotocol.io) qui permet à Claude Code (ou tout client MCP) d'interroger la base ouverte **Open Food Facts**, limitée aux produits alimentaires.

Aucune clé d'API n'est nécessaire pour la lecture.

## Outils exposés

Aucun outil pour l'instant (voir « Structure » pour en ajouter un).

## Prérequis

[uv](https://docs.astral.sh/uv/) installé. `uv` crée l'environnement et installe les dépendances (déclarées dans `pyproject.toml`) automatiquement au premier lancement.

## Connecter à Claude Code (uniquement ce dossier)

Depuis la racine du dépôt cloné (quel que soit le nom du dossier) :

```bash
claude mcp add openfoodfacts -e OFF_USER_AGENT="MonProjet/1.0 (vous@exemple.com)" -- uv run serveur_mcp.py
```

Vérifier :

```bash
claude mcp list
```

Puis lancer `claude` dans ce dossier et taper `/mcp` pour voir le serveur et ses outils.

Variante : `claude mcp add --scope project ...` crée un fichier `.mcp.json` partageable avec le projet (Git).

Retirer le serveur :

```bash
claude mcp remove openfoodfacts
```

## Tester sans Claude

Avec l'inspecteur MCP (interface web de test) :

```bash
uv run mcp dev serveur_mcp.py
```

## Configuration

| Variable d'environnement | Rôle |
|---|---|
| `OFF_USER_AGENT` | Identifie votre appli auprès d'Open Food Facts, ex. `MonProjet/1.0 (vous@exemple.com)`. Fortement recommandé. |

## Structure

```
./
├── pyproject.toml           # Dépendances (lu par uv)
├── serveur_mcp.py           # Point d'entrée : serveur MCP et définition des outils
├── client_openfoodfacts.py  # Appels HTTP à l'API Open Food Facts + mise en forme des réponses
└── README.md
```

Pour ajouter un outil : écrivez la méthode dans `client_openfoodfacts.py`, puis une fonction décorée par `@mcp.tool()` dans `serveur_mcp.py`. La docstring de la fonction est ce que Claude lit pour savoir quand l'utiliser.

## Règles d'usage d'Open Food Facts

- Un appel API doit correspondre à un vrai besoin utilisateur. Pour de gros volumes, utilisez les exports quotidiens : https://world.openfoodfacts.org/data
- Renseignez un User-Agent avec vos coordonnées.
- Licences : base sous ODbL, contenus sous DbCL, images sous CC BY-SA. Citez Open Food Facts si vous réutilisez les données.

Documentation de l'API : https://openfoodfacts.github.io/documentation/docs/Product-Opener/api/
