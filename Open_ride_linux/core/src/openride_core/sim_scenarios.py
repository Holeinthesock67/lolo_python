"""Scénarios du Bluetooth simulé (`ble_sim.py`) : réglages des appareils et événements datés.

Un scénario est un dictionnaire (ou un fichier JSON du même format) :

    {
      "seed": 0,
      "trainer": {"appear_at": 2, "connect_delay_s": 0.5, "rider_power_w": 180},
      "click": {"appear_at": 4, "plus": {...}, "minus": {...}, "relay_delay_s": [0.005, 0.04]},
      "hr": {"appear_at": 3, "rest_bpm": 60},
      "events": [{"t": 30, "device": "trainer", "action": "att_error", "code": 128}, ...]
    }

Une section absente (« trainer », « click », « hr ») retire l'appareil ; `null` aussi. Les temps
sont en secondes depuis le démarrage du monde simulé (lancement du core). Les scénarios
intégrés reproduisent les essais réels ; `openride-core run --sim-scenario NOM|FICHIER`.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .ble_sim import SimClickBox, SimHrStrap, SimTrainer, SimWorld


class SimScenarioError(Exception):
    """Scénario illisible ou invalide ; le message est lisible par l'utilisateur."""


TRAINER_KEYS = {"name", "address", "appear_at", "connect_delay_s", "connect_failures", "asleep",
                "ibd_hz", "rider_power_w", "cadence_rpm", "erg_tau_s", "cp_latency_s",
                "power_range", "refuse_control"}
CLICK_BOX_KEYS = {"address", "appear_at", "connect_delay_s", "connect_failures", "asleep",
                  "status_hz", "battery_pct", "sleep_on_drop"}
CLICK_KEYS = CLICK_BOX_KEYS - {"address"} | {"plus", "minus", "relay_delay_s"}
HR_KEYS = {"name", "address", "appear_at", "connect_delay_s", "connect_failures", "asleep",
           "rest_bpm", "max_bpm", "ftp_w", "tau_s", "bpm"}
TOP_KEYS = {"description", "seed", "trainer", "click", "hr", "events"}
ACTIONS = {"press", "drop", "wake", "sleep", "connect_failures", "connect_delay", "att_error",
           "cp_silent", "silence", "control_lost", "refuse_control", "rider", "bpm"}
EVENT_KEYS = {"t", "device", "action", "button", "duration_s", "count", "code", "seconds",
              "value", "watts", "cadence_rpm", "bpm"}

PLUS_ADDRESS = "F4:C4:59:15:E1:E7"   # adresse du boîtier « + » réel (CLAUDE.md)
MINUS_ADDRESS = "F4:C4:59:15:E1:E8"

# Appareils prêts tout de suite : base des scénarios intégrés.
_READY = {
    "trainer": {"appear_at": 0.3, "connect_delay_s": 0.3},
    "click": {"appear_at": 0.5, "connect_delay_s": 0.3},
    "hr": {"appear_at": 0.5, "connect_delay_s": 0.2},
}


def _with(base: dict[str, Any], **changes: Any) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key].update(value)
        else:
            out[key] = value
    return out


def _gear_presses(start: float, period: float, count: int) -> list[dict[str, Any]]:
    """Deux montées de braquet puis une descente, en boucle (appuis courts)."""
    seq = ["+", "+", "-"]
    return [{"t": start + i * period, "action": "press", "button": seq[i % 3]} for i in range(count)]


SCENARIOS: dict[str, dict[str, Any]] = {
    "nominal": _with(_READY, description="Tout se connecte en une seconde, aucune panne.",
                     events=[]),
    "demo": _with(_READY, description=(
        "Séance de démonstration : appuis réguliers sur le Click, appuis longs, effort variable."),
        events=[
            *_gear_presses(8.0, 6.0, 30),
            {"t": 60.0, "action": "press", "button": "+", "duration_s": 1.0},
            {"t": 75.0, "action": "press", "button": "-", "duration_s": 1.0},
            {"t": 90.0, "device": "trainer", "action": "rider", "watts": 260},
            {"t": 150.0, "device": "trainer", "action": "rider", "watts": 150},
            {"t": 200.0, "device": "trainer", "action": "rider", "watts": 200},
        ]),
    "reveil_tardif": _with(_READY, description=(
        "Réveil tardif : trainer allumé à 6 s, ceinture à 10 s ; boîtiers du Click endormis, "
        "réveillés par un appui (perdu) à 15 s et 25 s."),
        trainer={"appear_at": 6.0},
        hr={"appear_at": 10.0},
        click={"appear_at": 0.0, "asleep": True},
        events=[
            {"t": 15.0, "action": "press", "button": "+"},
            {"t": 25.0, "action": "press", "button": "-"},
            {"t": 35.0, "action": "press", "button": "+"},
            {"t": 40.0, "action": "press", "button": "-"},
        ]),
    "erreur_0x80": _with(_READY, description=(
        "Erreur BLE ponctuelle : une écriture du Control Point échoue avec l'erreur ATT 0x80 à 20 s."),
        events=[{"t": 20.0, "device": "trainer", "action": "att_error", "code": 0x80}]),
    "connexions_retardees": _with(_READY, description=(
        "Connexions lentes : trainer à 4 s de connexion et deux échecs, Click à 2 s, ceinture à 3 s "
        "avec un échec."),
        trainer={"connect_delay_s": 4.0, "connect_failures": 2},
        click={"connect_delay_s": 2.0},
        hr={"connect_delay_s": 3.0, "connect_failures": 1}),
    "coupures": _with(_READY, description=(
        "Coupures : trainer à 30 s, Click « − » à 40 s (rendormi, réveillé à 50 s), ceinture à "
        "45 s, silence du trainer de 12 s à 70 s, contrôle FTMS retiré à 100 s."),
        events=[
            {"t": 30.0, "device": "trainer", "action": "drop"},
            {"t": 40.0, "device": "click_minus", "action": "drop"},
            {"t": 45.0, "device": "hr", "action": "drop"},
            {"t": 50.0, "action": "press", "button": "-"},
            {"t": 70.0, "device": "trainer", "action": "silence", "seconds": 12},
            {"t": 100.0, "device": "trainer", "action": "control_lost"},
        ]),
    "controle_refuse": _with(_READY, description=(
        "Le trainer refuse le contrôle FTMS à partir de 10 s (autre application) : la séance "
        "passe en ERROR après deux reprises."),
        events=[
            {"t": 10.0, "device": "trainer", "action": "refuse_control"},
            {"t": 10.1, "device": "trainer", "action": "control_lost"},
        ]),
}
DEFAULT_SCENARIO = "demo"


def _check_keys(section: str, data: Any, allowed: set[str]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise SimScenarioError(f"{section} : objet attendu, reçu {data!r}")
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise SimScenarioError(f"{section} : clé(s) inconnue(s) {', '.join(unknown)}")
    return data


def _num(section: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SimScenarioError(f"{section} : nombre attendu, reçu {value!r}")
    return float(value)


def validate(spec: Any) -> dict[str, Any]:
    spec = _check_keys("scénario", spec, TOP_KEYS)
    for section, keys in (("trainer", TRAINER_KEYS), ("click", CLICK_KEYS), ("hr", HR_KEYS)):
        if spec.get(section) is not None:
            _check_keys(section, spec[section], keys)
    click = spec.get("click") or {}
    for role in ("plus", "minus"):
        if click.get(role) is not None:
            _check_keys(f"click.{role}", click[role], CLICK_BOX_KEYS)
    events = spec.get("events") or []
    if not isinstance(events, list):
        raise SimScenarioError("events : liste attendue")
    for i, ev in enumerate(events):
        where = f"events[{i}]"
        _check_keys(where, ev, EVENT_KEYS)
        if "t" not in ev or "action" not in ev:
            raise SimScenarioError(f"{where} : « t » et « action » sont obligatoires")
        if _num(f"{where}.t", ev["t"]) < 0:
            raise SimScenarioError(f"{where}.t : doit être positif")
        if ev["action"] not in ACTIONS:
            raise SimScenarioError(f"{where} : action {ev['action']!r} inconnue "
                                   f"(permises : {', '.join(sorted(ACTIONS))})")
        if ev["action"] in ("silence", "connect_delay") and "seconds" not in ev:
            raise SimScenarioError(f"{where} : « seconds » obligatoire pour {ev['action']}")
    return spec


def load_scenario(name_or_path: str | Path | None) -> dict[str, Any]:
    """Scénario intégré par son nom, ou fichier JSON ; None ou vide : `DEFAULT_SCENARIO`."""
    key = str(name_or_path or DEFAULT_SCENARIO)
    if key in SCENARIOS:
        return validate(copy.deepcopy(SCENARIOS[key]))
    path = Path(key).expanduser()
    if not path.is_file():
        raise SimScenarioError(f"scénario « {key} » inconnu : ni intégré ({', '.join(SCENARIOS)}), "
                               "ni fichier JSON")
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SimScenarioError(f"{path} : lecture impossible : {exc}") from None
    return validate(spec)


def build_world(spec: dict[str, Any], name: str = "sim", *, trainer: bool = True,
                click: bool = True, hr: bool = True) -> SimWorld:
    """Crée le monde simulé ; `trainer`, `click`, `hr` à False retirent l'appareil."""
    spec = validate(spec)
    world = SimWorld(seed=int(spec.get("seed", 0)))
    world.name = name
    if trainer and spec.get("trainer") is not None:
        t = dict(spec["trainer"])
        if "power_range" in t:
            t["power_range"] = tuple(int(v) for v in t["power_range"])
        world.trainer = SimTrainer(world, **t)
    if click and spec.get("click") is not None:
        c = dict(spec["click"])
        plus, minus = c.pop("plus", None) or {}, c.pop("minus", None) or {}
        if "relay_delay_s" in c:
            lo, hi = c.pop("relay_delay_s")
            world.relay_delay_s = (float(lo), float(hi))
        world.clicks = [SimClickBox(world, "+", **{"address": PLUS_ADDRESS, **c, **plus}),
                        SimClickBox(world, "-", **{"address": MINUS_ADDRESS, **c, **minus})]
    if hr and spec.get("hr") is not None:
        world.hr = SimHrStrap(world, **spec["hr"])
    devices = {"trainer": world.trainer, "hr": world.hr, "click_plus": world.clicks[:1],
               "click_minus": world.clicks[1:]}
    world.events = []
    for ev in spec.get("events") or []:
        target = ev.get("device", "trainer" if ev["action"] != "press" else "click_plus")
        key = target.lower().replace("-", "_minus").replace("+", "_plus")
        if ev["action"] == "press" and not world.clicks:
            continue   # Click non simulé : appuis ignorés
        if key in devices and not devices[key]:
            continue   # appareil non simulé
        world.events.append(dict(ev))
    return world
