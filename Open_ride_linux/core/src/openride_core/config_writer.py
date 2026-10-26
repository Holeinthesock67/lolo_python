"""Écriture commune de `~/OpenRide/config.toml` (lot O3) : valeurs typées, fichier gardé tel quel.

`update_config({("rider", "ftp_w"): 265, ...}, path)` écrit chaque valeur dans le type TOML qui
lui revient (texte entre guillemets, entier, nombre décimal, booléen) avec les règles de
`config_edit.py` : commentaires, ordre, autres sections et clés inconnues gardés, copie
`config.toml.bak`, résultat validé par `config.validate` avant d'écrire (sinon rien n'est écrit,
`ConfigWriteError` cite la section, la clé et les bornes), remplacement atomique.

Utilisé par l'appairage (`pairing.save`, lot N12) et les réglages (`settings.apply`, lot O3).
"""

from __future__ import annotations

import math
from pathlib import Path

from . import config as config_mod
from .config_edit import ConfigEditError, _toml_string, write_literals

ConfigWriteError = ConfigEditError


def toml_literal(value: object) -> str:
    """Valeur Python écrite en TOML ; un nombre entier s'écrit sans décimale (`265`, pas `265.0`)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ConfigWriteError(f"valeur {value!r} non finie")
        return str(int(value)) if value.is_integer() else repr(value)
    if isinstance(value, str):
        return _toml_string(value)
    raise ConfigWriteError(f"valeur {value!r} de type {type(value).__name__} non prise en charge")


def update_config(changes: dict[tuple[str, str], object], path: Path | None = None) -> list[str]:
    """Écrit `changes` dans `path` (défaut : `~/OpenRide/config.toml`) ; renvoie les lignes changées.

    Lève `ConfigWriteError` si une valeur est invalide : rien n'est écrit.
    """
    literals = [(sec, key, toml_literal(value)) for (sec, key), value in changes.items()]
    return write_literals(path or config_mod.DEFAULT_CONFIG_PATH, literals)
