"""Derniers choix du menu, mémorisés par profil (lot O32, module pur hors lecture et écriture du fichier).

Le core note dans `<profil>/derniers_choix.json` ce que le joueur a choisi au menu et que le core a
accepté : parcours (`select_route`), entraînement (`select_workout`), bots et fantôme (`start`), départ du
monde ouvert (`start_open_world`). Le fichier est publié dans `hello_ack.config.last_choices` (contrat IPC
révision 1.5) : le core recharge lui-même le dernier parcours au démarrage et au changement de profil,
l'engine reprend les autres choix sur ses écrans. Le Cyber-Rogue garde sa dernière run par le journal
(`hello_ack.config.rogue.last`, lot R13) : rien ici.

Une valeur refusée à la lecture (fichier modifié à la main, ancien format) est oubliée sans erreur : le
menu repart de ses valeurs par défaut pour cette valeur seulement.
"""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path
from typing import Any

FILE_NAME = "derniers_choix.json"
KEYS = ("route_id", "workout_id", "bots", "open_world")
MAX_BOTS = 5   # 4 bots et un fantôme (contrat IPC §4, `start`)
_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
NAVS = ("ride", "destination", "loop")


def path_for(root: Path) -> Path:
    return root / FILE_NAME


def _number(value: Any, low: float, high: float) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) \
        and low <= value <= high


def _valid_point(value: Any) -> bool:
    return isinstance(value, dict) and _number(value.get("lat"), -90, 90) and _number(value.get("lon"), -180, 180)


def clean(key: str, value: Any) -> Any:
    """Valeur gardée pour `key`, ou None si elle est refusée."""
    if key in ("route_id", "workout_id"):
        return value if isinstance(value, str) and _ID_RE.match(value) and not value.startswith("ow:") else None
    if key == "bots":
        if not isinstance(value, list) or len(value) > MAX_BOTS:
            return None
        if not all(isinstance(b, dict) and isinstance(b.get("kind"), str) for b in value):
            return None
        return [dict(b) for b in value]
    if key == "open_world":
        if not _valid_point(value) or value.get("nav", "ride") not in NAVS:
            return None
        out = {"lat": value["lat"], "lon": value["lon"], "nav": value.get("nav", "ride")}
        if _number(value.get("heading_deg"), 0, 360):
            out["heading_deg"] = value["heading_deg"]
        if _number(value.get("loop_km"), 1, 1000):
            out["loop_km"] = value["loop_km"]
        if _valid_point(value.get("target")):
            out["target"] = {"lat": value["target"]["lat"], "lon": value["target"]["lon"]}
        return out
    return None


def load(path: Path) -> dict[str, Any]:
    """Choix gardés ; {} si le fichier manque ou est illisible, valeurs refusées oubliées une à une."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, Any] = {}
    for key in KEYS:
        value = clean(key, data.get(key))
        if value is not None:
            out[key] = value
    return out


def remember(path: Path, key: str, value: Any) -> dict[str, Any]:
    """Remplace un choix et réécrit le fichier (écriture sûre) ; renvoie tous les choix gardés.

    Valeur refusée : rien n'est écrit. Lève `OSError` si le fichier ne peut pas être écrit."""
    choices = load(path)
    value = clean(key, value)
    if value is None or choices.get(key) == value:
        return choices
    choices[key] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(choices, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return choices
