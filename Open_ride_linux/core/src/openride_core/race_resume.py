"""Instantané d'une course et reprise après un plantage (lot RC1, audit du 22 novembre, L10 et M2 ; module pur).

La séance écrit au journal une ligne `race_snapshot` toutes les `SNAPSHOT_EVERY_S` secondes pendant une Course, un
Grand Prix ou un Dernier survivant, et à chaque pause. Après un plantage du core, la reprise (`resume.py`, lot N8)
recompose le même plateau avec les mêmes réglages, puis pose dessus l'état de l'instantané : positions, réserves
W'bal, temps de course des bots, classement, arrivées, tours, éliminations, points des maillots, objets en main.

Pas de `pickle` (constat R5 de l'audit) : des dictionnaires JSON, un numéro de format (`FORMAT`) et la version du
jeu ; l'un des deux différent, la reprise est refusée et la séance repart sans la course (`SnapshotError`).

Ce qui ne revient pas, pour tout le monde : les attaques et relais en cours des bots (ils repartent de leur rôle
de repos), les projectiles en vol, les effets en cours et les coups en attente du Grand Prix. Entre l'instantané et
la dernière ligne du journal (`SNAPSHOT_EVERY_S` au plus), les bots avancent à leur vitesse de l'instantané.
"""

from __future__ import annotations

import random
from typing import Any

FORMAT = 1
SNAPSHOT_EVERY_S = 5.0
MODES = ("race", "grandprix", "survivor")   # modes repris ; piste, WTF et monde ouvert : hors lot


class SnapshotError(ValueError):
    """Instantané absent, d'un autre format ou d'une autre version du jeu, ou qui ne colle pas au plateau."""


def _r(x: float, nd: int = 3) -> float:
    return round(float(x), nd)


# --- bots à profil ------------------------------------------------------------------------------------------

def bot_state(bot: Any) -> dict:
    """État d'un bot à profil (ou à puissance constante) : de quoi le reposer sur la route avec sa réserve."""
    d: dict[str, Any] = {"id": bot.id, "kind": getattr(bot, "kind", "constant"), "s": _r(bot.physics.s),
                         "distance": _r(bot.physics.distance), "v": _r(bot.physics.v), "t": _r(bot.t),
                         "work_j": _r(bot.work_j, 1), "ride_s": _r(bot.ride_s, 2), "lane_m": _r(bot.lane.m),
                         "lane_home": _r(bot.lane.home), "lane_auto": bool(bot.lane.auto)}
    if hasattr(bot, "profile"):
        tac = bot.tactics
        d.update({"profile": bot.profile, "scale": float(bot.scale), "level_pct": bot.level_pct,
                  "w_bal_j": _r(bot.wbal.w_bal_j, 1), "depleted_s": _r(bot.wbal.depleted_s, 2),
                  "peak_key": list(bot._peak_key) if bot._peak_key is not None else None,
                  "peak_used_s": _r(bot._peak_used_s, 2),
                  "attacks": tac.attacks, "responses": tac.responses,
                  "attack_done": sorted([list(k) for k in tac._attack_done], key=str)})
    else:
        d["power_w"] = _r(bot.power_w, 1)
    return d


def check_field(bots: list[Any], states: list[dict]) -> None:
    """Le plateau recomposé doit être celui de l'instantané : mêmes identifiants, mêmes profils, dans l'ordre."""
    have = [(b.id, getattr(b, "profile", None)) for b in bots]
    want = [(d.get("id"), d.get("profile")) for d in states]
    if have != want:
        raise SnapshotError(f"plateau différent de celui de l'instantané ({len(have)} bots contre {len(want)})")


def apply_bot_state(bot: Any, d: dict, ahead_s: float = 0.0, length_m: float | None = None) -> None:
    """Repose un bot recréé (calibré) dans l'état `d`, avancé de `ahead_s` secondes à sa vitesse de l'instantané,
    à l'arrêt (tout le monde repart arrêté après la reprise). `length_m` : bout d'un parcours en ligne."""
    from .rogue.wbal import WbalState

    v = max(float(d["v"]), 0.0)
    s = float(d["s"]) + v * max(ahead_s, 0.0)
    dist = float(d.get("distance", d["s"])) + v * max(ahead_s, 0.0)
    if length_m is not None:
        s = min(s, length_m)
    if hasattr(bot, "profile"):
        bot.set_scale(float(d["scale"]))   # réserve pleine et tactique remise à zéro, puis l'état de l'instantané
        bot.wbal = WbalState(w_bal_j=min(float(d["w_bal_j"]), bot.w_prime_j), depleted_s=float(d["depleted_s"]))
        bot._peak_key = tuple(d["peak_key"]) if d.get("peak_key") is not None else None
        bot._peak_used_s = float(d.get("peak_used_s", 0.0))
        tac = bot.tactics
        tac.attacks, tac.responses = int(d.get("attacks", 0)), int(d.get("responses", 0))
        tac._attack_done = {tuple(k) for k in d.get("attack_done", [])}
    elif "power_w" in d:
        bot.power_w = float(d["power_w"])
    bot.physics.s, bot.physics.distance, bot.physics.v = s, dist, 0.0
    bot.t = float(d["t"]) + max(ahead_s, 0.0)
    bot.work_j, bot.ride_s = float(d.get("work_j", 0.0)), float(d.get("ride_s", 0.0))
    bot.lane.m, bot.lane.home = float(d.get("lane_m", bot.lane.m)), float(d.get("lane_home", bot.lane.home))
    bot.lane.auto = bool(d.get("lane_auto", True))
    if hasattr(bot, "apply_form"):
        bot.apply_form()   # CP du jour au temps du bot (forme et fatigue de longue durée)


# --- Grand Prix et Course (`GrandPrixMode`) ------------------------------------------------------------------

def gp_state(gp: Any) -> dict:
    """Classement, arrivées, objets en main et compteurs du bilan ; boîtes prises (Grand Prix)."""
    racers = {}
    for r in gp.racers.values():
        racers[r.id] = {"finished": r.finished, "lane": r.lane, "auto": r.auto, "held": r.held,
                        "charges": r.charges, "roll": r.roll, "roll_until": _r(r.roll_until),
                        "last_use": _r(max(r.last_use, -1.0)), "launched": dict(r.launched),
                        "received": dict(r.received), "dodged": r.dodged,
                        "gained_s": {k: _r(v, 2) for k, v in r.gained_s.items()},
                        "lost_s": {k: _r(v, 2) for k, v in r.lost_s.items()}}
    ready = {rid: (None if m.ready_at is None else _r(m.ready_at)) for rid, m in gp.brain.minds.items()}
    return {"mode": gp.mode, "length_m": _r(gp.length_m), "lap_m": None if gp.lap_m is None else _r(gp.lap_m),
            "origin_m": _r(gp.origin_m), "chaos": gp.chaos, "enabled": list(gp.enabled), "clock": _r(gp.clock),
            "arrivals": gp.arrivals, "racers": racers, "ready_at": ready,
            "rows": [_r(x, 2) for x in gp.boxes.rows],
            "taken": [[row, lane, _r(t)] for (row, lane), t in sorted(gp.boxes.taken.items())]}


def apply_gp_state(gp: Any, d: dict, seed: int) -> None:
    """Pose l'instantané sur une course recréée et démarrée (`start`) aux positions de la reprise. Projectiles,
    effets et coups en attente ne reviennent pas ; le tirage repart d'une graine tirée de la course et de l'heure."""
    if set(d["racers"]) != set(gp.racers):
        raise SnapshotError("coureurs du Grand Prix différents de ceux de l'instantané")
    gp.clock = float(d["clock"])
    gp.grace_until = gp.clock
    gp.arrivals = int(d["arrivals"])
    for rid, rd in d["racers"].items():
        r = gp.racers[rid]
        r.finished = rd["finished"]
        r.lane, r.lane_to, r.auto = int(rd["lane"]), None, bool(rd["auto"])
        r.held, r.charges = rd["held"], int(rd["charges"])
        r.roll, r.roll_until = rd["roll"], float(rd["roll_until"])
        r.last_use = float(rd["last_use"])
        r.launched, r.received = dict(rd["launched"]), dict(rd["received"])
        r.dodged = int(rd["dodged"])
        r.gained_s, r.lost_s = dict(rd["gained_s"]), dict(rd["lost_s"])
        r.fx, r.impulses, r.hit_until = [], [], -1e9
    for rid, at in d.get("ready_at", {}).items():
        if rid in gp.brain.minds:
            gp.brain.minds[rid].ready_at = at
    gp.boxes.rows = [float(x) for x in d.get("rows", gp.boxes.rows)]
    gp.boxes.taken = {(int(row), int(lane)): float(t) for row, lane, t in d.get("taken", [])}
    gp.rng = random.Random(f"{seed}:{gp.clock:.2f}")


# --- Dernier survivant -----------------------------------------------------------------------------------------

def survivor_state(sv: Any) -> dict:
    return {"arches": [_r(a, 2) for a in sv.arches], "bots": [[i, n, lv] for i, n, lv in sv.bots],
            "spacing_km": sv.spacing_km, "seed": sv.seed, "arch": sv.arch,
            "winner": sv.winner,
            "crossings": [{k: _r(v) for k, v in c.items()} for c in sv.crossings],
            "racers": {r.id: {"out_arch": r.out_arch, "place": r.place, "gap_s": r.gap_s} for r in sv.racers.values()}}


def apply_survivor_state(sv: Any, d: dict) -> None:
    if set(d["racers"]) != set(sv.racers):
        raise SnapshotError("coureurs du Dernier survivant différents de ceux de l'instantané")
    sv.arch, sv.winner = int(d["arch"]), d.get("winner")
    sv.crossings = [dict(c) for c in d["crossings"]]
    for rid, rd in d["racers"].items():
        r = sv.racers[rid]
        r.out_arch, r.place, r.gap_s = rd["out_arch"], rd["place"], rd["gap_s"]


# --- points des maillots (mode classique de la Course) ---------------------------------------------------------

def standings_state(st: Any) -> dict:
    return {"arrived": [[seg, lap, list(ids)] for (seg, lap), ids in st._arrived.items()],
            "points": {j: dict(p) for j, p in st._points.items()},
            "reached": {j: {k: _r(v) for k, v in p.items()} for j, p in st._reached.items()},
            "awards": [[a.rider_id, a.segment_id, a.lap, a.place, a.points, a.jersey] for a in st.awards]}


def apply_standings_state(st: Any, d: dict) -> None:
    from .jerseys import Award

    st._arrived = {(seg, int(lap)): list(ids) for seg, lap, ids in d["arrived"]}
    st._points = {j: dict(p) for j, p in d["points"].items()}
    st._reached = {j: dict(p) for j, p in d["reached"].items()}
    st.awards = [Award(rid, seg, int(lap), int(place), int(pts), jersey) for rid, seg, lap, place, pts, jersey
                 in d["awards"]]


# --- contrôle de la ligne -------------------------------------------------------------------------------------

def check(line: dict | None, version: str) -> dict:
    """Ligne `race_snapshot` utilisable par ce jeu ; `SnapshotError` avec la raison écrite sinon."""
    if line is None:
        raise SnapshotError("aucun instantané de la course dans le journal")
    if line.get("format") != FORMAT:
        raise SnapshotError(f"instantané au format {line.get('format')!r}, ce jeu lit le format {FORMAT}")
    if line.get("version") != version:
        raise SnapshotError(f"instantané écrit par la version {line.get('version')} du jeu, celle-ci est la {version}")
    if line.get("mode") not in MODES:
        raise SnapshotError(f"mode {line.get('mode')!r} non repris")
    return line
