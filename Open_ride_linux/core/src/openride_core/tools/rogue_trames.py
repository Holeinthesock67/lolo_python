"""Trames réelles du Cyber-Rogue pour les tests de l'engine (revue de code vague 3, lot EC3).

Les tests de l'engine fabriquaient des trames `state` que le vrai core n'envoie jamais (écart au Firewall de 120 m
dans toutes les phases, `route_length_m` renseigné, `s_room` non nul en couloir, événement de fin de salle avec
l'ennemi encore présent) : cinq défauts visibles en jeu passaient inaperçus (constats E10-02, 04, 05, 06, 09).
Ce script joue une vraie run dans la séance du core (`rogue_bout_en_bout`, lot X40 : graine 5, seuil, 30 min,
cycliste « moyen », run perdue au boss ; puis la même run gagnée par le cycliste « debutant ») et garde une trame par phase et par transition, plus la salle et le
couloir reçus ; la récupération (défaite par le Firewall, absente de cette run) vient du vrai `RogueMode` mené à
puissance basse. Fichier écrit : `engine/tests/data/rogue_trames_core.json`, lu par les tests du mode
(`engine/tests/unit/test_rogue_trames_core.gd`) et vérifié par `core/tests/test_rogue_trames.py`.

    python -m openride_core.tools.rogue_trames            # régénère le fichier du dépôt
    python -m openride_core.tools.rogue_trames --check    # code 1 si le fichier n'est plus à jour
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import tempfile
from pathlib import Path

from ..config import Config
from ..physics import RiderPhysics
from ..rogue.mode import RogueMode, parse_start_run
from . import rogue_bout_en_bout as x40

DEFAULT_OUT = Path(__file__).resolve().parents[4] / "engine" / "tests" / "data" / "rogue_trames_core.json"
OBJECTIVE, DURATION_MIN, SEED, PROFILE = "threshold", 30, 5, "moyen"
VICTORY_PROFILE = "debutant"


def _states(trace: list[dict]) -> list[dict]:
    return [m for m in trace if m["type"] == "state"]


def _first(states: list[dict], pred, start: int = 0) -> int:
    for i in range(start, len(states)):
        if pred(states[i]):
            return i
    raise RuntimeError("trame introuvable dans la run")


def _phase(m: dict) -> str:
    r = m.get("rogue")
    return r["phase"] if isinstance(r, dict) else ""


def _trace(profile: str) -> list[dict]:
    with tempfile.TemporaryDirectory(prefix="openride-rogue-trames-") as tmp:
        path = Path(tmp) / "trace.jsonl"
        rep = x40.run(OBJECTIVE, DURATION_MIN, SEED, profile, trace=path)
        if not rep.ok:
            raise RuntimeError("run X40 en échec : " + "; ".join(d for ok, d, _ in rep.checks if ok is False))
        return [json.loads(ln)["msg"] for ln in path.read_text("utf-8").splitlines()]


def _victory_frames() -> dict[str, dict]:
    """Run gagnée (cycliste « debutant » face à des salles à sa mesure) : fin du boss et premiers résultats."""
    st = _states(_trace(VICTORY_PROFILE))
    i_cool = _first(st, lambda m: _phase(m) == "COOLDOWN")
    i_res = _first(st, lambda m: _phase(m) == "RESULTS", i_cool)
    fin = st[_first(st, lambda m: m["session_state"] == "FINISHED", i_res)]
    if fin["summary"]["rogue"]["result"] != "victory":
        raise RuntimeError("la run « debutant » n'est plus gagnée : choisir une autre graine")
    return {"victory_boss_end_prev": st[i_cool - 1], "victory_boss_end": st[i_cool], "victory_results": st[i_res]}


def _session_frames() -> tuple[dict, list, dict]:
    trace = _trace(PROFILE)
    st = _states(trace)
    out: dict[str, dict] = {}
    i = _first(st, lambda m: _phase(m) == "WARMUP" and m["rogue"]["phase_left_s"] is not None
               and m["rogue"]["phase_left_s"] < 300 and m["rogue"]["loot_stage"] is None)
    out["warmup"] = st[i]
    out["warmup_relic"] = st[_first(st, lambda m: _phase(m) == "WARMUP" and m["rogue"]["loot_stage"] == "card")]
    i_room = _first(st, lambda m: _phase(m) == "ROOM" and m["session_state"] == "RUNNING"
                    and m["rogue"]["s_room"] > 300.0 and m["rogue"]["firewall_gap_m"] > 0.0)
    out["room"] = st[i_room]
    i_end = _first(st, lambda m: _phase(m) != "ROOM", i_room)
    out["room_end_prev"] = st[i_end - 1]              # dernière trame de la salle
    out["room_end"] = st[i_end]                       # trame qui porte la fin de la salle (room_won, room_fled)
    out["corridor"] = st[_first(st, lambda m: _phase(m) == "CORRIDOR" and m["rogue"]["phase_left_s"] is not None
                                and m["rogue"]["phase_left_s"] < 30.0, i_end)]
    i_boss = _first(st, lambda m: _phase(m) == "BOSS" and m["rogue"]["s_room"] > 300.0)
    out["boss"] = st[i_boss]
    i_cool = _first(st, lambda m: _phase(m) == "COOLDOWN", i_boss)
    out["boss_end_prev"] = st[i_cool - 1]
    out["boss_end"] = st[i_cool]
    out["cooldown"] = st[i_cool + 5]
    i_res = _first(st, lambda m: _phase(m) == "RESULTS")
    out["results"] = st[i_res]
    fin = copy.deepcopy(st[_first(st, lambda m: m["session_state"] == "FINISHED", i_res)])
    # Bilan de la séance réduit à sa partie du mode : le reste (chemin du FIT, puissances lissées) dépend de
    # l'horloge de la machine et rendrait le fichier différent à chaque passage.
    fin["summary"] = {"rogue": fin["summary"]["rogue"]}
    out["finished"] = fin
    # Salles reçues : la première salle et la phase 3 du boss (longueur de la salle pour « N m restants »).
    rids = {out["room"]["rogue"]["room_id"], out["boss_end_prev"]["rogue"]["room_id"]}
    rooms = [m for m in trace if m["type"] == "room" and m["room_id"] in rids]
    loot = next(m for m in trace if m["type"] == "loot" and m.get("doors"))
    return out, rooms, loot


def _recovery_frames(template: dict) -> dict[str, dict]:
    """Défaite par le Firewall (puissance très basse dès la première salle) : le vrai `RogueMode`, une trame par
    seconde, posée dans la trame `state` d'une salle de la run (mêmes champs de séance)."""
    cfg = Config()
    mode = RogueMode(cfg, parse_start_run({"objective": OBJECTIVE, "duration_min": DURATION_MIN, "seed": SEED}, cfg))
    body = RiderPhysics(mode.rider.params)
    dt, t = 0.02, 0.0
    frames: list[dict] = []
    n = 0
    while t < 2400.0:
        power = 60.0 if mode.in_fight or mode.engine.phase == "RECOVERY" else 200.0
        mode.step(dt, power, 85.0, body, False, t)
        t += dt
        n += 1
        if n % 50 == 0:
            frames.append(mode.take_frame())
            if len(frames) >= 2 and frames[-2]["phase"] == "RECOVERY" and frames[-1]["phase"] != "RECOVERY":
                break
    out = {}
    i = next(k for k, f in enumerate(frames) if f["phase"] == "RECOVERY")
    for name, k in (("recovery_start", i), ("recovery", i + 5)):
        m = copy.deepcopy(template)
        m["rogue"] = frames[k]
        out[name] = m
    return out


def build() -> dict:
    frames, rooms, loot = _session_frames()
    frames.update(_recovery_frames(frames["room"]))
    frames.update(_victory_frames())
    return {"_doc": "Trames réelles du core (python -m openride_core.tools.rogue_trames), ne pas modifier à la main.",
            "run": {"objective": OBJECTIVE, "duration_min": DURATION_MIN, "seed": SEED, "profile": PROFILE},
            "frames": frames, "room": rooms, "loot": loot}


def dumps(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=1) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Trames réelles du Cyber-Rogue pour les tests de l'engine (lot EC3).")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--check", action="store_true", help="code 1 si le fichier n'est plus à jour")
    args = ap.parse_args(argv)
    text = dumps(build())
    if args.check:
        if not args.out.is_file() or args.out.read_text("utf-8") != text:
            print(f"{args.out} n'est plus à jour : python -m openride_core.tools.rogue_trames", file=sys.stderr)
            return 1
        print(f"{args.out} : à jour")
        return 0
    args.out.write_text(text, "utf-8")
    print(f"écrit : {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
