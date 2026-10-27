"""Budget de taille des datagrammes IPC (lot X25, contrat IPC v1 §2).

- `encode()` : encodage unique des messages (JSON compact, UTF-8 sans échappement `\\u`).
  « Fantôme » prend 8 octets au lieu de 12 avec l'échappement ASCII de `json.dumps`.
- `fit_state()` : allège une trame `state` trop grande au lieu de la jeter. Les champs
  facultatifs partent dans l'ordre de `STATE_DEGRADATION` ; position, vitesse, puissance et
  état de séance restent toujours.
- `worst_state()` : trame la plus lourde attendue pour une révision du contrat, avec les
  longueurs maximales de `MAX_TEXT`. Chaque révision qui ajoute des champs à `state` ajoute
  sa fonction dans `REVISION_EXTRAS` ; `tests/test_ipc_budget.py` vérifie que toutes tiennent.
- Cible et limite : la cible reste 1 400 octets pour toutes les révisions (place gardée pour les
  ajouts de la 2.0) ; la limite de `state` est de 1 400 octets jusqu'à la révision 1.2 et de
  4 096 octets depuis la 1.3 (contrat §2, décision D1). Le core n'allège qu'au-delà de la limite.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Callable

MAX_DATAGRAM_SIZE = 1400          # cible de toutes les révisions, et limite jusqu'à la 1.2
STATE_LIMIT_1_3 = 4096            # limite de `state` depuis la révision 1.3 (MAX_STATE_DATAGRAM_SIZE)

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


# Une entrée par révision : chaque révision hérite des ajouts des précédentes.
REVISION_EXTRAS: dict[str, Callable[[dict[str, Any]], None]] = {
    "1.1": _extras_1_1,
    "1.2": _extras_1_2,
    "1.3": _extras_1_3,
}


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


def state_limit(revision: str) -> int:
    """Limite de taille d'une trame `state` pour `revision` (contrat §2)."""
    major, minor = (int(x) for x in revision.split("."))
    return STATE_LIMIT_1_3 if (major, minor) >= (1, 3) else MAX_DATAGRAM_SIZE


def report() -> str:
    """Tableau texte : taille de la pire trame par révision (python -m openride_core.ipc_budget)."""
    lines = [f"{'révision':<9} {'octets':>6}  {'cible 1400':>10}  {'limite':>6}  marge"]
    for rev in revisions():
        n = size(worst_state(rev))
        limit = state_limit(rev)
        lines.append(f"{rev:<9} {n:>6}  {MAX_DATAGRAM_SIZE - n:>+10d}  {limit:>6}  {limit - n:+d}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(report())
