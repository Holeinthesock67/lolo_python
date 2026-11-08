"""Budget de taille des datagrammes IPC (lot X25, contrat IPC v1 §2).

- `encode()` : encodage unique des messages (JSON compact, UTF-8 sans échappement `\\u`).
  « Fantôme » prend 8 octets au lieu de 12 avec l'échappement ASCII de `json.dumps`.
- `fit_state()` : allège une trame `state` trop grande au lieu de la jeter. Les champs
  facultatifs partent dans l'ordre de `STATE_DEGRADATION` ; position, vitesse, puissance et
  état de séance restent toujours.
- `worst_state()` : trame la plus lourde attendue pour une révision du contrat, avec les
  longueurs maximales de `MAX_TEXT`. Chaque révision qui ajoute des champs à `state` ajoute
  sa fonction dans `REVISION_EXTRAS` ; `tests/test_ipc_budget.py` vérifie que toutes tiennent.
- Cible et limite : la cible est de 1 400 octets jusqu'à la révision 1.3 (place gardée pour les
  ajouts de la 2.0) ; la limite de `state` est de 1 400 octets jusqu'à la révision 1.2 et de
  4 096 octets depuis la 1.3 (contrat §2, décision D1). Depuis la 1.4 (séries R, T et V, lot T1),
  `state` utilise cette place : sa cible devient sa limite, et seuls les messages courts
  (`segment_result`, `xp_result`, `progression`, `loot`) visent encore 1 400 octets
  (`worst_rogue_state`, `worst_short_messages`). Le core n'allège qu'au-delà de la limite.
- Depuis la révision 1.5, la limite de 4 096 octets vaut pour tout message hors messages en parties
  (`ipc_server.MAX_DATAGRAM_SIZE`) ; les cibles de 1 400 octets restent une réserve de place.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Callable

MAX_DATAGRAM_SIZE = 1400          # cible de toutes les révisions, et limite jusqu'à la 1.2
STATE_LIMIT_1_3 = 4096            # limite de `state` depuis la révision 1.3 (ipc_server.MAX_DATAGRAM_SIZE, tout message depuis la 1.5)

# Longueurs maximales attendues des textes libres (caractères). Au-delà, `fit_state` raccourcit.
MAX_TEXT = {
    "route_id": 64,           # identifiant de parcours du catalogue
    "workout_name": 48,       # titre d'entraînement affiché dans le bandeau ERG
    "trainer_name": 32,       # nom annoncé par le trainer (devices.trainer.name)
    "bot_name": 16,           # contrat : maxLength 16
    "bot_id": 8,              # contrat : maxLength 8
}

# Textes de remplissage : lettres accentuées (2 octets en UTF-8) pour le pire cas.
_FILL = "Fantôme éé à ô û"


def encode(msg: dict[str, Any]) -> bytes:
    """Encodage des datagrammes IPC : JSON compact en UTF-8."""
    return json.dumps(msg, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def size(msg: dict[str, Any]) -> int:
    return len(encode(msg))


def _text(n: int) -> str:
    return (_FILL * (n // len(_FILL) + 1))[:n]


def _shorten_texts(d: dict[str, Any]) -> None:
    erg = d.get("erg")
    if isinstance(erg, dict) and isinstance(erg.get("workout_name"), str):
        erg["workout_name"] = erg["workout_name"][:MAX_TEXT["workout_name"]]
    devices = d.get("devices")
    trainer = devices.get("trainer") if isinstance(devices, dict) else None
    if isinstance(trainer, dict) and isinstance(trainer.get("name"), str):
        trainer["name"] = trainer["name"][:MAX_TEXT["trainer_name"]]
    for bot in d.get("bots") or []:
        if isinstance(bot, dict) and isinstance(bot.get("name"), str):
            bot["name"] = bot["name"][:MAX_TEXT["bot_name"]]


def _drop(key: str) -> Callable[[dict[str, Any]], None]:
    return lambda d: d.pop(key, None)


def _short_bot_names(d: dict[str, Any]) -> None:
    for bot in d.get("bots") or []:
        if isinstance(bot, dict) and isinstance(bot.get("name"), str):
            bot["name"] = bot["name"][:6]


def _bots_if_devices(d: dict[str, Any]) -> None:
    if "devices" in d:
        d.pop("bots", None)


# Ordre d'allègement, du moins gênant au plus gênant. `devices` n'est que dans une trame sur 30 :
# sur cette trame-là, les bots peuvent manquer (ils reviennent 33 ms plus tard) ; l'inverse
# priverait l'engine de l'état des appareils pendant toute la séance.
STATE_DEGRADATION: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
    ("textes raccourcis", _shorten_texts),
    ("noms des bots raccourcis", _short_bot_names),
    ("bots (trame avec devices)", _bots_if_devices),
    ("devices", _drop("devices")),
    ("summary", _drop("summary")),
    ("bots", _drop("bots")),
    ("riders", _drop("riders")),          # lot AS7 : extrapolés par l'engine, ils reviennent 100 ms plus tard
    ("vehicles", _drop("vehicles")),      # lot AS6 : extrapolés par l'engine, ils reviennent 100 ms plus tard
    ("open_world", _drop("open_world")),
    ("erg", _drop("erg")),
]


def fit_state(msg: dict[str, Any], limit: int = MAX_DATAGRAM_SIZE) -> tuple[dict[str, Any], list[str]]:
    """Trame `state` qui tient dans `limit` octets et liste des allègements appliqués.

    La trame d'origine n'est jamais modifiée. Si rien ne suffit, la dernière version est rendue
    (l'appelant la jette, comme avant).
    """
    if size(msg) <= limit:
        return msg, []
    out = copy.deepcopy(msg)
    done: list[str] = []
    for label, step in STATE_DEGRADATION:
        step(out)
        done.append(label)
        if size(out) <= limit:
            break
    return out, done


# --- Trames les plus lourdes, par révision du contrat ---

# Valeurs les plus longues permises par le schéma `state`, flottants à la précision envoyée par le core
# (arrondi de `IpcState.to_dict`, décision D1 de l'audit IPC du 26 octobre) : t et s à 2 décimales,
# v à 3, pentes à 2, puissances et cadence à 1, lat et lon à 6, alt à 2, longueur de la route à 1.
def _worst_1_0() -> dict[str, Any]:
    return {
        "type": "state", "v": 1, "seq": 2_147_483_647, "t": 86_399.99,
        "session_state": "PAUSED", "pause_reason": "trainer_lost",
        "trainer_status": "RECONNECTING", "input_status": "CONNECTED", "mode": "ERG",
        "route_id": ("col-" * 16)[:MAX_TEXT["route_id"]], "route_length_m": 199_999.9,
        "s": 123_456.79, "v": 16.667, "grade": -12.35, "grade_sent": -10.25,
        "power": 1234.5, "power_3s": 1234.5, "cadence": 123.4, "hr": 199, "gear": 24, "gears_total": 24,
        "lat": -45.123457, "lon": -123.123457, "alt": 2802.35,
        "erg": {"workout_name": _text(MAX_TEXT["workout_name"]), "block_index": 120, "block_count": 120,
                "block_type": "interval_on", "block_remaining_s": 3599.75, "block_total_s": 3600.0,
                "target_w": 1234.0, "next_target_w": 1234.0, "bias_pct": 110.0, "paused": True},
        "summary": None, "last_cmd_id": 2_147_483_647,
    }


def _extras_1_1(d: dict[str, Any]) -> None:
    d["devices"] = {
        "trainer": {"status": "RECONNECTING", "name": _text(MAX_TEXT["trainer_name"]),
                    "address": "C1:1C:00:00:00:03"},
        "click": [{"side": "minus", "status": "SEARCHING", "battery_pct": 100},
                  {"side": "minus", "status": "SEARCHING", "battery_pct": 100}],
        "hr": {"status": "SEARCHING", "source": "trainer", "battery_pct": 100},
    }
    d["bots"] = [{"id": f"bot-{i}-ab"[:MAX_TEXT["bot_id"]], "name": _text(MAX_TEXT["bot_name"]),
                  "s": 123_456.79 + i, "v": 16.667, "kind": "constant"} for i in range(5)]


def _extras_1_2(d: dict[str, Any]) -> None:
    d["difficulty_pct"] = 100


def _extras_1_3(d: dict[str, Any]) -> None:
    # `wind` n'est jamais dans la même trame que `devices` (contrat §3) : la trame qui porte
    # `devices`, plus lourde, reste la pire. Seuls `draft` et `draft_bot` s'y ajoutent.
    d["draft"] = 0.45
    d["draft_bot"] = d["bots"][0]["id"]


_ID = "x" * 24                     # identifiants de segment et de carte : maxLength 24
# Compteurs de la série V (expérience, pièces) : 8 chiffres suffisent pour des années de séances.


def _extras_1_4(d: dict[str, Any]) -> None:
    # Série T (lot T1) : majorant des modes classique et ERG. En ERG, `powerup` est absent
    # (T-Q2) ; la pire trame garde quand même `erg` et `powerup` ensemble.
    for bot in d["bots"]:
        bot.update({"profile": "sprinter", "cp_w": 1234.5, "mass_kg": 123.4, "wbal_pct": 100.0,
                    "jersey": "sprint", "gap_s": -3599.99})
    d["segment"] = {"id": _ID, "kind": "climb", "category": "HC", "d_to_start_m": 199_999.9,
                    "elapsed_s": 3599.99, "gap_to_pr_s": -3599.99}
    d["powerup"] = {"held": "power", "active": "light", "remaining_s": 120.0}
    d["jerseys"] = {"sprint": d["bots"][0]["id"], "kom": d["bots"][1]["id"]}
    d["bot_ahead"], d["bot_behind"] = d["bots"][2]["id"], d["bots"][3]["id"]


def _extras_1_5(d: dict[str, Any]) -> None:
    # Monde ouvert (lot W9) : `open_world` n'est jamais dans une trame qui porte `devices` (contrat §4).
    # La trame la plus lourde du monde ouvert est donc celle sans `devices`, avec carrefour à 4 branches.
    d.pop("devices", None)
    d["open_world"] = {"rev": 2_147_483_647,
                       "next": {"id": "j" + "9" * 23, "d_m": 2999.9, "default": 3, "chosen": 3, "locked": True,
                                "b": [[-179, "p", -99.9], [-90, "s", 99.9], [90, "m", -12.3], [179, "k", 12.3]]},
                       "data": "downloading"}
    # Lot AS6 : au plus 4 véhicules proches, chacun au plus long (identifiant de case, sorte la plus longue)
    d["vehicles"] = [{"id": "v1000099", "kind": "tractor", "color": 7, "s": 123_456.79 + i, "dir": -1,
                      "v": 22.22, "lane_m": -2.33} for i in range(4)]
    # Lot AS7 : au plus 6 cyclistes du décor proches, identifiants de case et d'apparence au plus long
    d["riders"] = [{"id": "c1000099-5", "s": 123_456.79 + i, "dir": -1, "v": 19.44, "lane_m": -2.33,
                    "look": 1_048_575} for i in range(6)]


PELOTON_BOTS = 12   # lot PL1 : 11 bots et un fantôme (bots.MAX_BOTS)


def _extras_1_6(d: dict[str, Any]) -> None:
    # Peloton (lot PL1, 3.0) : 12 bots. Comme `bots.light_frame`, les 5 plus proches gardent tous les champs,
    # les autres n'ont plus `cp_w`, `mass_kg`, `wbal_pct` ni `gap_s` (ni `name` et `profile`, sauf l'un d'eux
    # à tour de rôle), et `jersey` n'est là que porté (deux
    # maillots au plus). Pire cas : tous avec `lane_m`, `profile` et `out` (Dernier survivant), même si `out`
    # et les maillots ne vont pas ensemble (le mode n'a pas de segments).
    from .bots import FULL_FRAME_BOTS, light_frame

    full = d["bots"][0]
    bots = []
    for i in range(PELOTON_BOTS):
        b = {**full, "id": f"bot-{i}-ab"[:MAX_TEXT["bot_id"]], "s": 123_456.79 + i, "lane_m": -2.33, "out": 11,
             "gap_s": -3599.9, "jersey": ("sprint", "kom")[i] if i < 2 else None}
        bots.append(b)
    d["bots"] = light_frame(bots, 123_456.79)
    assert sum("cp_w" in b for b in d["bots"]) == FULL_FRAME_BOTS
    d["draft_bot"] = d["bots"][0]["id"]
    d["jerseys"] = {"sprint": d["bots"][0]["id"], "kom": d["bots"][1]["id"]}
    d["bot_ahead"], d["bot_behind"] = d["bots"][2]["id"], d["bots"][3]["id"]


def _extras_1_9(d: dict[str, Any]) -> None:
    # Demi-tour depuis la pause (lot N17) : `dir` = -1 à rebours ; `segment`, `bot_ahead` et `bot_behind`
    # n'y sont plus remplis, majorant gardé avec eux. Les révisions 1.7 (Grand Prix) et 1.8 (collection, sans
    # champ de `state`) ont leurs trames à part (`worst_grandprix_state`).
    d["dir"] = -1


# Une entrée par révision : chaque révision hérite des ajouts des précédentes.
REVISION_EXTRAS: dict[str, Callable[[dict[str, Any]], None]] = {
    "1.1": _extras_1_1,
    "1.2": _extras_1_2,
    "1.3": _extras_1_3,
    "1.4": _extras_1_4,
    "1.5": _extras_1_5,
    "1.6": _extras_1_6,
    "1.9": _extras_1_9,
}


def worst_peloton_devices() -> dict[str, Any]:
    """Trame du peloton (révision 1.6) qui porte `devices` (une sur 30) : sans `open_world`, avec ERG,
    segment, bonus, maillots et 12 bots."""
    d = worst_state("1.4")
    _extras_1_6(d)
    return d


def worst_survivor_state() -> dict[str, Any]:
    """Trame du Dernier survivant à 11 adversaires (lot DS8, révision 1.6) : peloton sans fantôme ni maillots,
    sans ERG, segment ni bonus (le mode n'en a pas, plan DS §2), monde ouvert gardé, et l'objet `survivor` au
    plus lourd. Majorant : les 12 coureurs à la fois en course (`alive`) et les 11 bots éliminés (`out`), tous
    les bots de la trame avec `out`."""
    from .bots import MAX_CONSTANT_BOTS

    d = worst_state("1.6")
    for key in ("segment", "powerup", "jerseys"):
        d.pop(key, None)
    d.update({"mode": "SIM", "erg": None})
    d["bots"] = [b for b in d["bots"] if b.get("kind") != "ghost"][:MAX_CONSTANT_BOTS]
    for b in d["bots"]:
        b.pop("jersey", None)
    ids = [b["id"] for b in d["bots"]]
    d["draft_bot"], d["bot_ahead"], d["bot_behind"] = ids[0], ids[1], ids[2]
    d["survivor"] = {"arch": MAX_CONSTANT_BOTS, "arches": MAX_CONSTANT_BOTS, "d_m": 2999.9,
                     "alive": ["me", *ids], "last": ids[-1], "gap_last_s": 3599.9,
                     "out": [[i, MAX_CONSTANT_BOTS] for i in ids], "me_out": None, "winner": None,
                     "ahead": {"id": ids[0], "gap_s": 3599.9, "catch_w": 1999}}
    return d


GP_LONGEST_ITEM, GP_FX = "musette_x3", 4   # majorant : 4 effets à la fois (le sien, un coup, une éclaboussure, une glissade)
GP_LONGEST_SHOT = "musette"                 # objet posé ou lancé le plus long tel que l'engine le dessine


def worst_grandprix_state(opponents: int = 4) -> dict[str, Any]:
    """Trame du Grand Prix des objets (lot GP2, révision 1.7) : `opponents` bots à profil sans fantôme, maillots,
    ERG, segment, bonus ni monde ouvert (le mode les refuse, plan GP §2), donc avec `devices`, chaque bot avec
    son objet et `GP_FX` effets (au-delà de 5, comme `bots.light_frame`), et `gp` au plus lourd (12 objets en vue,
    identifiants de 1 à `route_objects.ID_MAX`, menace, 2 rangées de boîtes, tours)."""
    from .bots import light_frame
    from .grandprix import ITEM_IDS
    from .route_objects import ID_MAX

    d = worst_state("1.6")
    for key in ("segment", "powerup", "jerseys", "open_world"):
        d.pop(key, None)
    d.update({"mode": "SIM", "erg": None, "devices": worst_state("1.4")["devices"]})
    full = worst_state("1.4")["bots"][0]
    longest = sorted(ITEM_IDS, key=len, reverse=True)[:GP_FX]
    bots = [{**full, "id": f"bot-{i}-ab"[:MAX_TEXT["bot_id"]], "kind": "constant", "s": 123_456.79 + i,
             "lane_m": -2.33, "gap_s": -3599.9, "jersey": None, "item": GP_LONGEST_ITEM, "fx": longest}
            for i in range(opponents)]
    d["bots"] = bots = light_frame(bots, 123_456.79)
    ids = [b["id"] for b in bots]
    d["draft_bot"], d["bot_ahead"], d["bot_behind"] = ids[0], ids[1], ids[-1]
    d["gp"] = {"place": 12, "of": 12, "gap_s": -3599.9, "held": GP_LONGEST_ITEM, "n": 3, "roll_s": 1.5,
               "lane": 2, "auto": False, "fx": [[k, 99.9] for k in longest],
               "warn": [GP_LONGEST_SHOT, 399.9],
               "obj": [[ID_MAX, GP_LONGEST_SHOT, 123_456.7, -1] for _ in range(12)],
               "boxes": [199_999, 199_999], "pick": True, "lap": [5, 5]}
    return d


def revisions() -> list[str]:
    return ["1.0", *REVISION_EXTRAS]


def worst_state(revision: str) -> dict[str, Any]:
    """Trame `state` la plus lourde attendue pour `revision` (ajouts des révisions précédentes compris)."""
    if revision not in revisions():
        raise ValueError(f"révision inconnue : {revision}")
    d = _worst_1_0()
    for rev in revisions()[1:revisions().index(revision) + 1]:
        REVISION_EXTRAS[rev](d)
    return d


def worst_rogue_state() -> dict[str, Any]:
    """Trame `state` la plus lourde du mode `ROGUE` (révision 1.4, série R) : 4 fenêtres, 4 événements."""
    d = worst_state("1.3")
    for key in ("erg", "bots", "draft", "draft_bot"):
        d.pop(key, None)
    d.update({"mode": "ROGUE", "erg": None, "route_id": None, "lat": None, "lon": None, "alt": None,
              "gear": 12, "gears_total": 12})
    d["rogue"] = {
        "phase": "CORRIDOR", "room_id": 2_147_483_647, "room_index": 99, "rooms_total": 99,
        "archetype": "sprinteur", "boss_phase": 3, "s_room": 99_999.99,
        "enemy_hp": 99_999.9, "enemy_hp_max": 99_999.9, "shield": 999.9, "shield_max": 999.9,
        "adrenaline": 100.0, "w_bal_j": -99_999.9, "w_prime_j": 99_999.9, "posture": "VELOCE",
        "firewall_gap_m": -9_999.99, "gold": 2_147_483_647,
        "windows": [{"kind": "strike_target", "s_start": 99_999.99, "s_end": 99_999.99}] * 4,
        "hack": {"locked": True, "forced_gear": 12, "until_s": 99_999.99},
        "overheat": True, "loot_focus": 4,
        "events": ["firewall_contact", "room_skipped", "perfect_shift", "parry_miss"],
    }
    return d


def worst_short_messages() -> dict[str, dict[str, Any]]:
    """Messages courts de la révision 1.4 au plus lourd (cible 1 400 octets, contrat §9)."""
    text = _text
    progression = {
        "level": 50, "xp": 2_147_483_647, "xp_level_start": 2_147_483_647, "xp_next_level": None,
        "coins": 2_147_483_647, "equipped": {k: _ID for k in ("frame", "wheels", "helmet", "kit", "socks", "glasses")},
        "avatar": {"height": "XL", "build": "strong", "skin": 7, "hair": 5, "hair_color": 7,
                   "kit_primary": 15, "kit_secondary": 15, "number": 999,
                   "standing_grade_pct": 99.9, "standing_power_pct": 999.9},
        "lives": 2_147_483_647,
    }
    return {
        "segment_result": {
            "type": "segment_result", "v": 1, "segment_id": _ID, "name": text(48), "kind": "climb",
            "time_s": 99_999.99, "with_powerup": True, "pr": False, "pr_time_s": 99_999.99,
            "rank": 99, "rank_total": 99, "points": 20, "equipment_gain_s": -999.99},
        "xp_result": {
            "type": "xp_result", "v": 1, "eligible": True, "reason": None,
            "gains": [{"source": s, "points": 99_999_999} for s in
                      ("distance", "climb", "erg", "erg_bonus", "segment", "segment_pr", "jersey", "rogue", "rogue_boss")],
            "total": 99_999_999, "level_before": 49, "level_after": 50, "xp_total": 99_999_999,
            "xp_level_start": 99_999_999, "xp_next_level": None, "coins_gained": 99_999_999, "coins_total": 99_999_999,
            "unlocked": [_ID] * 8,
            "challenges": [{"id": _ID, "name": text(32), "reward_item": _ID}] * 4,
            "equipment_gain_s": -9_999.99, "more": True},
        "progression": {"type": "progression", "v": 1, "request_cmd_id": 2_147_483_647, **progression},
        "loot": {
            "type": "loot", "v": 1, "corridor_id": 2_147_483_647,
            "cards": [{"id": _ID, "name": text(32), "kind": text(16), "text": text(120), "replaces_gear": 12}] * 3,
            "doors": [{"side": side, "room_id": 2_147_483_647, "archetype": "sprinteur"} for side in ("left", "right")],
            "reroll_cost": 2_147_483_647, "gold": 2_147_483_647},
    }


def state_limit(revision: str) -> int:
    """Limite de taille d'une trame `state` pour `revision` (contrat §2)."""
    major, minor = (int(x) for x in revision.split("."))
    return STATE_LIMIT_1_3 if (major, minor) >= (1, 3) else MAX_DATAGRAM_SIZE


def state_target(revision: str) -> int:
    """Taille visée pour `state` : 1 400 octets jusqu'à la 1.3, la limite depuis la 1.4."""
    major, minor = (int(x) for x in revision.split("."))
    return state_limit(revision) if (major, minor) >= (1, 4) else MAX_DATAGRAM_SIZE


def report() -> str:
    """Tableau texte : taille de la pire trame par révision (python -m openride_core.ipc_budget)."""
    lines = [f"{'révision':<22} {'octets':>6}  {'cible 1400':>10}  {'limite':>6}  marge"]
    rows = [(rev, worst_state(rev), state_limit(rev)) for rev in revisions()]
    rows.append(("1.6 peloton + devices", worst_peloton_devices(), state_limit("1.6")))
    rows.append(("1.6 dernier survivant", worst_survivor_state(), state_limit("1.6")))
    rows.append(("1.7 grand prix", worst_grandprix_state(), state_limit("1.7")))
    gp11 = worst_grandprix_state(11)
    gp11.pop("devices")
    rows.append(("1.7 grand prix 11 bots", gp11, state_limit("1.7")))
    rows.append(("1.4 rogue", worst_rogue_state(), state_limit("1.4")))
    rows += [(f"1.4 {name}", msg, MAX_DATAGRAM_SIZE) for name, msg in worst_short_messages().items()]
    for label, msg, limit in rows:
        n = size(msg)
        lines.append(f"{label:<22} {n:>6}  {MAX_DATAGRAM_SIZE - n:>+10d}  {limit:>6}  {limit - n:+d}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(report())
