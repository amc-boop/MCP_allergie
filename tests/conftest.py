"""Réglage pytest : permet d'importer serveur_mcp.py et regles.py depuis tests/."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
