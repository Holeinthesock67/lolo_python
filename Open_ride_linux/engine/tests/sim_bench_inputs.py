"""Appuis joués et attentes des scénarios du banc simulé (lot X33), sans Godot ni core : module pur.

Section `inputs` d'un scénario de `sim_bench_scenarios/`, à côté de `events` :
- `{"t": 42, "key": "Z", "hold_ms": 200, "shift": false}` : touche du clavier, message de test `key` de
  l'engine (vrai chemin : `_unhandled_input`, `key_map.gd`, puis `input_event` vers le core en séance) ;
- `{"t": 42, "button": "Z", "duration_s": 0.2}` : bouton du Click simulé, ajouté aux événements `press`
  du scénario Bluetooth (chemin Bluetooth complet : notifications, `PressClassifier`, core).
Chaque appui peut porter son effet attendu, lu au journal de séance autour de `t` :
- `bias` : écart du biais ERG (`erg_bias_pct`) entre l'échantillon d'avant et celui d'après (+2, −10…), et la
  cible ERG dans le même rapport à ± 0,5 point (même bloc) ;
- `block` : écart du numéro de bloc (+1 pour Z, bloc suivant) ;
- `state` : `PAUSED` ou `RUNNING`, ligne `pause` ou `resume` du journal juste après l'appui.

Section `bench.expect` : attentes de la séance entière, chacune avec `recette` (renvoi à l'étape) :
- `{"journal": "segment", "where": {"segment_id": "climb1"}, "min": 1}` : lignes du journal de séance ;
- `{"log": "core" | "engine", "motif": "regex", "min": 1}` (ou `max`) : lignes des journaux du core et de
  l'engine ;
- `{"widget": "bonus_held", "min": 1}` (+ `contains`) : captures où l'élément du HUD est visible et écrit ;
- `{"file": "OpenRide/records.json", "contains": ["climb1"]}` : fichier du HOME temporaire ;
- `{"bonus_speed": 15}` : vitesse moyenne des N s qui suivent chaque bonus activé face aux 5 s d'avant
  (information : la pente change sous les roues, la mesure n'échoue jamais).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

INPUT_KEYS = {"t", "key", "shift", "hold_ms", "button", "duration_s", "bias", "block", "state", "recette"}
EXPECT_KEYS = {"journal", "where", "log", "motif", "widget", "contains", "file", "bonus_speed", "min", "max",
               "recette", "label"}
STATES = {"PAUSED": "pause", "RUNNING": "resume"}
BUTTONS = {"+", "-", "A", "B", "Y", "Z"}
RATIO_TOL = 0.005          # ± 0,5 point sur le rapport des cibles ERG
BEFORE_S = 4.0             # échantillon d'avant : au plus 4 s avant l'appui
AFTER_S = (1.0, 4.0)       # échantillon d'après : 1 à 4 s après le relâchement

Check = tuple[bool | None, str, str]


class InputsError(ValueError):
    """Section `inputs` ou `bench.expect` mal écrite."""


def validate_inputs(inputs: Any) -> list[dict[str, Any]]:
    if not isinstance(inputs, list):
        raise InputsError("inputs : une liste est attendue")
    out = []
    for k, x in enumerate(inputs):
        where = f"inputs[{k}]"
        if not isinstance(x, dict):
            raise InputsError(f"{where} : un objet est attendu")
        unknown = set(x) - INPUT_KEYS
        if unknown:
            raise InputsError(f"{where} : clé(s) inconnue(s) {sorted(unknown)}")
        if not isinstance(x.get("t"), (int, float)) or x["t"] < 0:
            raise InputsError(f"{where}.t : temps en secondes attendu")
        if ("key" in x) == ("button" in x):
            raise InputsError(f"{where} : `key` (clavier) ou `button` (Click), l'un des deux")
        if "button" in x and x["button"] not in BUTTONS:
            raise InputsError(f"{where}.button : {x['button']!r} inconnu ({', '.join(sorted(BUTTONS))})")
        if "key" in x and (not isinstance(x["key"], str) or not x["key"]):
            raise InputsError(f"{where}.key : nom de touche Godot attendu (Z, Equal, PageUp, Escape…)")
        if "state" in x and x["state"] not in STATES:
            raise InputsError(f"{where}.state : PAUSED ou RUNNING")
        for key in ("bias", "block"):
            if key in x and not isinstance(x[key], int):
                raise InputsError(f"{where}.{key} : entier attendu")
        out.append(x)
    return sorted(out, key=lambda x: float(x["t"]))


def validate_expect(expect: Any) -> list[dict[str, Any]]:
    if not isinstance(expect, list):
        raise InputsError("bench.expect : une liste est attendue")
    for k, x in enumerate(expect):
        where = f"bench.expect[{k}]"
        if not isinstance(x, dict):
            raise InputsError(f"{where} : un objet est attendu")
        unknown = set(x) - EXPECT_KEYS
        if unknown:
            raise InputsError(f"{where} : clé(s) inconnue(s) {sorted(unknown)}")
        kinds = [key for key in ("journal", "log", "widget", "file", "bonus_speed") if key in x]
        if len(kinds) != 1:
            raise InputsError(f"{where} : une seule attente parmi journal, log, widget, file, bonus_speed")
        if "log" in x:
            if x["log"] not in ("core", "engine") or not isinstance(x.get("motif"), str):
                raise InputsError(f"{where} : log core ou engine, avec motif")
            re.compile(x["motif"])
        if "file" in x and not isinstance(x.get("contains"), list):
            raise InputsError(f"{where} : file avec la liste contains")
    return list(expect)


def click_events(inputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Appuis du Click simulé, au format des événements `press` du scénario Bluetooth."""
    out = []
    for x in inputs:
        if "button" in x:
            ev = {"t": float(x["t"]), "action": "press", "button": x["button"]}
            if "duration_s" in x:
                ev["duration_s"] = float(x["duration_s"])
            out.append(ev)
    return out


def input_name(x: dict[str, Any]) -> str:
    if "key" in x:
        return f"touche {'Maj+' if x.get('shift') else ''}{x['key']}" + (f" {x['hold_ms']} ms" if x.get("hold_ms") else "")
    return f"Click {x['button']}" + (f" {x['duration_s']:g} s" if x.get("duration_s") else "")


def held_s(x: dict[str, Any]) -> float:
    return float(x.get("hold_ms", 100)) / 1000.0 if "key" in x else float(x.get("duration_s", 0.1))


def _ref(x: dict[str, Any]) -> str:
    return f"[{x['recette']}] " if x.get("recette") else ""


def _around(records: list[dict[str, Any]], t0: float, x: dict[str, Any]) -> tuple[dict | None, dict | None]:
    t = float(x["t"])
    release = t + held_s(x)
    before = [r for r in records if t - BEFORE_S <= r["ts"] - t0 < t]
    after = [r for r in records if release + AFTER_S[0] <= r["ts"] - t0 <= release + AFTER_S[1]]
    return (before[-1] if before else None), (after[0] if after else None)


def input_checks(inputs: list[dict[str, Any]], rows: list[dict[str, Any]], t0: float,
                 keys_done: list[str]) -> list[Check]:
    """Une vérification par effet attendu de chaque appui ; `keys_done` : touches lues dans `[test] key done=…`."""
    out: list[Check] = []
    records = [r for r in rows if r.get("kind") == "record" and isinstance(r.get("ts"), (int, float))]
    events = [r for r in rows if r.get("kind") == "event"]
    pending = list(keys_done)
    for x in inputs:
        t = float(x["t"])
        name = f"{_ref(x)}{input_name(x)} à {t:.0f} s"
        if "key" in x:
            seen = x["key"] in pending
            if seen:
                pending.remove(x["key"])
            out.append((seen, f"{name} : touche jouée par l'engine", "« key done » lu" if seen else "aucun « key done »"))
        before, after = _around(records, t0, x)
        if "bias" in x:
            out.append(_bias_check(name, int(x["bias"]), before, after))
        if "block" in x:
            if before is None or after is None or before.get("block") is None or after.get("block") is None:
                out.append((False, f"{name} : bloc {x['block']:+d}", "pas d'échantillon ERG avant ou après l'appui"))
            else:
                d = int(after["block"]) - int(before["block"])
                out.append((d == x["block"], f"{name} : bloc {x['block']:+d}", f"bloc {before['block']} → {after['block']}"))
        if "state" in x:
            want = STATES[x["state"]]
            got = [e for e in events if e.get("event") == want and t <= e["ts"] - t0 <= t + held_s(x) + AFTER_S[1]]
            out.append((bool(got), f"{name} : {x['state']}",
                        f"« {want} » au journal {got[0]['ts'] - t0 - t:+.1f} s après" if got else f"aucune ligne « {want} »"))
    return out


def _bias_check(name: str, step: int, before: dict | None, after: dict | None) -> Check:
    label = f"{name} : biais ERG {step:+d} %"
    if before is None or after is None:
        return False, label, "pas d'échantillon avant ou après l'appui"
    b0, b1 = before.get("erg_bias_pct"), after.get("erg_bias_pct")
    if b0 is None or b1 is None:
        return False, label, "biais absent du journal (ERG inactif ?)"
    measure = f"biais {b0:+g} → {b1:+g} %"
    ok = round(b1 - b0) == step
    tw0, tw1 = before.get("target_w"), after.get("target_w")
    if before.get("block") != after.get("block"):
        return False, label, measure + f" ; bloc changé ({before.get('block')} → {after.get('block')}) : cible non comparable"
    if tw0 and tw1:
        want = (100.0 + b1) / (100.0 + b0)
        ratio = tw1 / tw0
        ok = ok and abs(ratio - want) <= RATIO_TOL
        measure += f" ; cible {tw0:.0f} → {tw1:.0f} W (rapport {ratio:.3f}, attendu {want:.3f})"
    else:
        ok = False
        measure += " ; cible ERG absente"
    return ok, label, measure


def _count_label(x: dict[str, Any], n: int) -> tuple[bool, str]:
    lo, hi = x.get("min"), x.get("max")
    if lo is None and hi is None:
        lo = 1
    ok = (lo is None or n >= lo) and (hi is None or n <= hi)
    bound = " et ".join(b for b in ((f"au moins {lo}" if lo is not None else ""),
                                    (f"au plus {hi}" if hi is not None else "")) if b)
    return ok, f"{n} ({bound} attendu)"


def expect_checks(expect: list[dict[str, Any]], rows: list[dict[str, Any]], core_text: str, engine_text: str,
                  shots: list[dict[str, Any]], home: Path, t0: float) -> list[Check]:
    out: list[Check] = []
    for x in expect:
        ref = _ref(x)
        if "journal" in x:
            where = x.get("where", {})
            n = sum(1 for r in rows if r.get("kind") == x["journal"] and all(r.get(k) == v for k, v in where.items()))
            ok, measure = _count_label(x, n)
            what = x["journal"] + (" " + ", ".join(f"{k}={v}" for k, v in where.items()) if where else "")
            out.append((ok, ref + x.get("label", f"lignes « {what} » au journal de séance"), measure))
        elif "log" in x:
            text = core_text if x["log"] == "core" else engine_text
            n = len(re.findall(x["motif"], text, re.M))
            ok, measure = _count_label(x, n)
            out.append((ok, ref + x.get("label", f"journal {x['log']} : « {x['motif']} »"), measure))
        elif "widget" in x:
            want = x.get("contains", "")
            seen = [s for s in shots if want in s.get("widgets", {}).get(x["widget"], "")
                    and s.get("widgets", {}).get(x["widget"], "")]
            ok, measure = _count_label(x, len(seen))
            if seen:
                measure += f", ex. {seen[0]['file']} : « {seen[0]['widgets'][x['widget']][:60]} »"
            out.append((ok, ref + x.get("label", f"écran : {x['widget']} visible" + (f" avec « {want} »" if want else "")),
                        "captures " + measure))
        elif "file" in x:
            p = home / x["file"]
            text = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""
            missing = [c for c in x["contains"] if c not in text]
            out.append((p.is_file() and not missing, ref + x.get("label", f"fichier {x['file']}"),
                        "absent" if not p.is_file() else ("contient " + ", ".join(x["contains"]) if not missing
                                                          else "manque " + ", ".join(missing))))
        else:
            out.append(_bonus_speed(x, rows, t0, ref))
    return out


def _bonus_speed(x: dict[str, Any], rows: list[dict[str, Any]], t0: float, ref: str) -> Check:
    span = float(x["bonus_speed"])
    records = [r for r in rows if r.get("kind") == "record"]
    ups = [r for r in rows if r.get("kind") == "powerup" and r.get("event", "activate") == "activate"]
    parts = []
    for u in ups:
        ts = float(u["ts"])
        pre = [r["speed"] for r in records if ts - 5.0 <= r["ts"] < ts]
        post = [r["speed"] for r in records if ts <= r["ts"] < ts + span]
        if pre and post:
            a, b = sum(pre) / len(pre) * 3.6, sum(post) / len(post) * 3.6
            parts.append(f"{u.get('powerup', '?')} à {ts - t0:.0f} s : {a:.1f} → {b:.1f} km/h")
    return None, ref + x.get("label", f"vitesse pendant {span:.0f} s de bonus"), "; ".join(parts) or "aucun bonus activé"


def keys_done(engine_text: str) -> list[str]:
    return re.findall(r"\[test\] key done=(\S+)", engine_text)
