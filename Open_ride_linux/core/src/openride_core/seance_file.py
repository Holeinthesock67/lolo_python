"""Séance verrouillée au lancement (`run --autostart`, lot EP1 « essais physiques »).

Une séance lancée sans menu est une liste de commandes IPC, les mêmes que celles des menus de l'engine,
jouées dans l'ordre par le core avant que l'engine ne se connecte. `--route`, `--workout` et `--mode`
donnent la liste courte (`select_route`, `select_workout`, `start`) ; `--seance FICHIER` donne une liste
complète écrite par le guide des essais (bots, épreuve de piste, run Cyber-Rogue, options du mode) :
rien n'est repris de la partie d'avant, et un essai ne part jamais sur un autre terrain que le sien.

Fichier JSON :

    {"id": "j4-alpe", "but": "pente des rampes, lacets, trainer",
     "commandes": [{"cmd": "select_route", "args": {"route_id": "alpe-d-huez"}},
                   {"cmd": "start", "args": {"bots": []}}]}

`id` et `but` sont lus par le guide ; le core ne lit que `commandes`. La dernière commande est `start`.
"""

from __future__ import annotations

import json
from pathlib import Path

# Commandes du menu qui préparent une séance ; aucune autre ne se joue au lancement.
COMMANDS = ("select_route", "select_workout", "start_run", "set_wtf_rule", "set_mode_option", "start_open_world",
            "start")
# `start_open_world` (essai du 21/11, la mer) : le monde se prépare en LOADING ; les commandes suivantes
# (dont `start`) se jouent quand il est prêt (`CoreSession._open_world_tick`).


class SeanceError(ValueError):
    """Fichier de séance illisible ou liste de commandes refusée."""


def from_options(route_id: str = "demo", workout_id: str | None = None,
                 game_mode: str | None = None) -> list[tuple[str, dict]]:
    """Liste courte de `--route`, `--workout` et `--mode` (lot J1), la même forme qu'un fichier."""
    cmds: list[tuple[str, dict]] = [("select_route", {"route_id": route_id})]
    if workout_id:
        cmds.append(("select_workout", {"workout_id": workout_id}))
    cmds.append(("start", {"mode": game_mode} if game_mode else {}))
    return cmds


def check(cmds: object) -> list[tuple[str, dict]]:
    """Vérifie la forme de la liste ; `SeanceError` avec la raison sinon."""
    if not isinstance(cmds, list) or not cmds:
        raise SeanceError("'commandes' attend une liste non vide")
    out: list[tuple[str, dict]] = []
    for i, c in enumerate(cmds, 1):
        if not isinstance(c, dict) or not isinstance(c.get("cmd"), str):
            raise SeanceError(f"commande {i} : objet {{cmd, args}} attendu")
        name, args = c["cmd"], c.get("args", {})
        if name not in COMMANDS:
            raise SeanceError(f"commande {i} : « {name} » ne prépare pas une séance ({', '.join(COMMANDS)})")
        if not isinstance(args, dict):
            raise SeanceError(f"commande {i} : 'args' attend un objet")
        out.append((name, args))
    if out[-1][0] != "start" or any(n == "start" for n, _ in out[:-1]):
        raise SeanceError("la liste finit par 'start', une seule fois")
    return out


def load(path: Path) -> list[tuple[str, dict]]:
    """Commandes d'un fichier de séance."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SeanceError(f"fichier de séance {path} illisible : {exc}") from exc
    if not isinstance(data, dict):
        raise SeanceError(f"fichier de séance {path} : objet JSON attendu")
    return check(data.get("commandes"))
