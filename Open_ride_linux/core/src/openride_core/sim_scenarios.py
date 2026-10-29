"""Scénarios du Bluetooth simulé (`ble_sim.py`) : réglages des appareils et événements datés.

Un scénario est un dictionnaire (ou un fichier JSON du même format) :

    {
      "seed": 0,
      "trainer": {"appear_at": 2, "connect_delay_s": 0.5},
      "rider": {"strategy": "constante", "watts": 180, "cadence_rpm": 88},
      "click": {"appear_at": 4, "plus": {...}, "minus": {...}, "relay_delay_s": [0.005, 0.04]},
      "hr": {"appear_at": 3, "rest_bpm": 60, "contact": true, "battery_pct": 80},
      "hr_watch": {"appear_at": 0, "rssi": -45},
      "events": [{"t": 30, "device": "trainer", "action": "att_error", "code": 128}, ...],
      "control_file": "/tmp/appuis.jsonl"
    }

Une section absente (« trainer », « click », « hr », « hr_watch ») retire l'appareil ; `null` aussi.
« rider » décrit le cycliste virtuel qui pédale sur le trainer (`sim_rider.py`, lot X27) ; absente, il
roule à 180 W et 88 rpm. Les temps sont en secondes depuis le démarrage du monde simulé (lancement du
core). `control_file` (facultatif) : fichier suivi pendant la séance, une ligne JSON par événement
appliqué tout de suite (sans « t »). Les scénarios
intégrés reproduisent les essais réels ; `openride-core run --sim-scenario NOM|FICHIER`.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .ble_sim import (RESPONSES, WATCH_ADDRESS, WATCH_NAME, SimClickBox, SimHrStrap, SimTrainer, SimWorld,
                      click_button, load_calibration)
from .sim_rider import RIDER_KEYS, STRATEGIES, SimRider


class SimScenarioError(Exception):
    """Scénario illisible ou invalide ; le message est lisible par l'utilisateur."""


TRAINER_KEYS = {"name", "address", "appear_at", "connect_delay_s", "connect_failures", "asleep",
                "ibd_hz", "erg_tau_s", "cp_latency_s", "power_range", "refuse_control", "busy_window_s", "relayed_hr",
                "response", "brake_delay_s", "brake_tau_up_s", "brake_tau_down_s", "flywheel_kg_m2",
                "notify_jitter_s", "rider_max_w", "calibration"}
# Réglages du modèle réaliste (lot X6) : nombres positifs, sans effet en réponse « instant ».
RESPONSE_KEYS = ("brake_delay_s", "brake_tau_up_s", "brake_tau_down_s", "flywheel_kg_m2", "notify_jitter_s",
                 "rider_max_w")
CLICK_BOX_KEYS = {"address", "appear_at", "connect_delay_s", "connect_failures", "asleep",
                  "status_hz", "battery_pct", "sleep_on_drop", "mute_after_s", "unlock_on_ride_on"}
CLICK_KEYS = CLICK_BOX_KEYS - {"address"} | {"plus", "minus", "relay_delay_s"}
HR_KEYS = {"name", "address", "appear_at", "connect_delay_s", "connect_failures", "asleep",
           "rest_bpm", "max_bpm", "ftp_w", "tau_s", "bpm", "contact", "battery_pct", "rssi"}
TOP_KEYS = {"description", "seed", "trainer", "rider", "click", "hr", "hr_watch", "events", "control_file"}
ACTIONS = {"press", "drop", "wake", "sleep", "connect_failures", "connect_delay", "att_error",
           "cp_silent", "other_device", "silence", "control_lost", "refuse_control", "rider", "bpm", "contact"}
EVENT_KEYS = {"t", "device", "action", "button", "duration_s", "count", "code", "seconds",
              "value", "watts", "cadence_rpm", "bpm"}

PLUS_ADDRESS = "C1:1C:00:00:00:01"   # adresse du boîtier « + » réel (CLAUDE.md)
MINUS_ADDRESS = "C1:1C:00:00:00:02"

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


def _burst(start: float, button: str, count: int, period: float) -> list[dict[str, Any]]:
    """Rafale d'appuis courts sur le même bouton."""
    return [{"t": round(start + i * period, 2), "action": "press", "button": button} for i in range(count)]


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
    "rafale_0x80": _with(_READY, description=(
        "Rafale de braquets (séance A du 28 octobre) : le Control Point reste occupé 0,6 s après "
        "chaque réponse et refuse les écritures rapprochées (ATT 0x80) ; cinq « − » en 6 s à 10 s, "
        "cinq « + » en 1 s à 25 s. La liaison doit tenir, sans pause automatique."),
        trainer={"busy_window_s": 0.6},
        events=[*_burst(10.0, "-", 5, 1.2), *_burst(25.0, "+", 5, 0.25)]),
    "montre_garmin": _with(_READY, description=(
        "Montre Garmin qui se connecte au trainer (séance A du 28 octobre) : le Control Point refuse "
        "toute écriture (ATT 0x80) pendant 8 s à 15 s puis 6 s à 40 s, braquets changés pendant ce "
        "temps. Consignes reportées, liaison gardée, bandeau « piloté par un autre appareil »."),
        events=[
            {"t": 15.0, "device": "trainer", "action": "other_device", "seconds": 8},
            *_burst(17.0, "-", 3, 1.0),
            {"t": 40.0, "device": "trainer", "action": "other_device", "seconds": 6},
            *_burst(41.0, "+", 2, 2.0),
        ]),
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
    "click_gauche_muet": _with(_READY, description=(
        "Boîtier gauche du Click muet 5 s après la connexion : n'envoie plus que des messages "
        "sans bouton ; le boîtier droit continue à fonctionner normalement."),
        click={
            "minus": {"mute_after_s": 5.0},
        },
        events=[
            {"t": 1.0, "action": "press", "button": "-"},
            {"t": 3.0, "action": "press", "button": "-"},
            {"t": 10.0, "action": "press", "button": "+"},
            {"t": 15.0, "action": "press", "button": "-"},
            {"t": 20.0, "action": "press", "button": "+"},
        ]),
    "realiste": _with(_READY, description=(
        "Trainer à réponse réaliste (lot X6) : frein à retard pur, serrage en 2 s, relâchement en 4,9 s "
        "(90 % vers 12 s, comme à l'essai du 25 octobre), volant d'inertie, effort de la route en SIM."),
        trainer={"response": "realiste"},
        events=[]),
    "fc_relayee_figee": _with(_READY, description=(
        "Ceinture appairée au trainer : FC relayée qui varie, puis reste figée 40 s avant de reprendre."),
        trainer={"appear_at": 0.3, "connect_delay_s": 0.3, "relayed_hr": True},
        hr={"asleep": True},
        events=[
            {"t": 10.0, "device": "trainer", "action": "bpm", "bpm": 105},
            {"t": 50.0, "device": "trainer", "action": "bpm", "bpm": None},
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
    for section, keys in (("trainer", TRAINER_KEYS), ("click", CLICK_KEYS), ("hr", HR_KEYS),
                          ("hr_watch", HR_KEYS)):
        if spec.get(section) is not None:
            _check_keys(section, spec[section], keys)
    rider = spec.get("rider")
    if rider is not None:
        _check_keys("rider", rider, RIDER_KEYS)
        if rider.get("strategy", "constante") not in STRATEGIES:
            raise SimScenarioError(f"rider.strategy : {rider['strategy']!r} inconnue ({', '.join(STRATEGIES)})")
        for key, value in rider.items():
            if key == "sprint_at_s":
                if not isinstance(value, list):
                    raise SimScenarioError("rider.sprint_at_s : liste de temps attendue")
                for v in value:
                    _num("rider.sprint_at_s", v)
            elif key not in ("strategy", "seed") and value is not None:
                _num(f"rider.{key}", value)
        if rider.get("strategy") == "vitesse" and not 0 < _num("rider.speed_kmh", rider.get("speed_kmh")) <= 80:
            raise SimScenarioError("rider.speed_kmh : entre 0 et 80 km/h")
    trainer = spec.get("trainer") or {}
    if trainer.get("response", "instant") not in RESPONSES:
        raise SimScenarioError(f"trainer.response : {' ou '.join(RESPONSES)} attendu")
    for key in RESPONSE_KEYS:
        if trainer.get(key) is not None and _num(f"trainer.{key}", trainer[key]) < 0:
            raise SimScenarioError(f"trainer.{key} : doit être positif")
    if trainer.get("calibration") is not None:
        try:
            load_calibration(str(trainer["calibration"]))
        except (OSError, ValueError) as exc:
            raise SimScenarioError(f"trainer.calibration : {exc}") from None
    for section in ("hr", "hr_watch"):
        hr = spec.get(section) or {}
        if hr.get("contact") is not None and not isinstance(hr["contact"], bool):
            raise SimScenarioError(f"{section}.contact : vrai, faux ou null attendu")
        if hr.get("battery_pct") is not None and not 0 <= _num(f"{section}.battery_pct",
                                                               hr["battery_pct"]) <= 100:
            raise SimScenarioError(f"{section}.battery_pct : entre 0 et 100")
    click = spec.get("click") or {}
    for role in ("plus", "minus"):
        if click.get(role) is not None:
            _check_keys(f"click.{role}", click[role], CLICK_BOX_KEYS)
            box = click[role]
            if "mute_after_s" in box and box["mute_after_s"] is not None:
                if _num(f"click.{role}.mute_after_s", box["mute_after_s"]) < 0:
                    raise SimScenarioError(f"click.{role}.mute_after_s : doit être positif")
            if "unlock_on_ride_on" in box and box["unlock_on_ride_on"] is not None:
                if not isinstance(box["unlock_on_ride_on"], bool):
                    raise SimScenarioError(f"click.{role}.unlock_on_ride_on : booléen attendu")
    if spec.get("control_file") is not None and not isinstance(spec["control_file"], str):
        raise SimScenarioError("control_file : chemin attendu")
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
        if ev["action"] == "press":
            try:
                click_button(ev.get("button", "+"))
            except KeyError:
                raise SimScenarioError(f"{where}.button : bouton {ev.get('button')!r} inconnu (+, -, A, B, Y, Z, "
                                       "LEFT, UP, RIGHT, DOWN)") from None
        if ev["action"] == "contact" and not isinstance(ev.get("value", True), (bool, type(None))):
            raise SimScenarioError(f"{where}.value : vrai, faux ou null attendu pour contact")
        if ev["action"] in ("silence", "connect_delay", "other_device") and "seconds" not in ev:
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
    world.control_file = spec.get("control_file")
    if trainer and spec.get("trainer") is not None:
        t = dict(spec["trainer"])
        if "power_range" in t:
            t["power_range"] = tuple(int(v) for v in t["power_range"])
        world.trainer = SimTrainer(world, rider=SimRider.from_spec(spec.get("rider")), **t)
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
    if hr and spec.get("hr_watch") is not None:
        world.hr_watch = SimHrStrap(world, **{"name": WATCH_NAME, "address": WATCH_ADDRESS,
                                              "rssi": -50, **spec["hr_watch"]})
    devices = {"trainer": world.trainer, "hr": world.hr, "hr_watch": world.hr_watch, "click_plus": world.clicks[:1],
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
