"""Erreurs du compilateur et codes de retour de la ligne de commande (lot B1 §3.3)."""

from __future__ import annotations

EXIT_OK = 0
EXIT_INPUT = 1      # GPX invalide ou trop court, sortie existante sans --force, .world invalide
EXIT_INTERNAL = 2


class CompileError(Exception):
    """Erreur d'entrée : le GPX ne peut pas donner de parcours (code de retour 1)."""
