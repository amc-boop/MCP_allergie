"""
Serveur MCP Open Food Facts (produits alimentaires uniquement).

Aucun outil n'est exposé pour l'instant : ajoutez-les ci-dessous avec @mcp.tool().

Lancement :
    uv run serveur_mcp.py         # transport stdio (Claude Desktop, Claude Code…)
"""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from client_openfoodfacts import OpenFoodFactsClient, OpenFoodFactsError

mcp = MCPServer("openfoodfacts")
client = OpenFoodFactsClient()


if __name__ == "__main__":
    mcp.run()
