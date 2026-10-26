"""Progression recalculée depuis le journal des séances (lot V2) : `openride-core xp`.

    openride-core xp [--dir DOSSIER] [--json] [--config FICHIER]

Lit tous les journaux `.jsonl` de `~/OpenRide/Activities/.journal/` (ou `--dir`) et les tables
de `data/progression.toml` (surchargées par `~/OpenRide/progression.toml`), puis affiche le
niveau, l'expérience, les défis réussis et une ligne par séance (points, ou raison du refus :
`replay`, `simulated`, `too_short`). Sert à régler la courbe sur l'historique réel avant de la
figer (plan V, risque 2). Rien n'est écrit.

Clés de la sortie `--json` (stables) :
    directory, total_xp, level, xp_level_start, xp_next_level, coins_earned, coins_balance
        (pièces du lot V3b ; solde d'après ~/OpenRide/profile.json),
    stats (total_km, total_climb_m, sessions, best_session_km, best_session_climb_m,
        erg_completed, segments, segment_prs, jerseys_kom, jerseys_sprint, hc_climbs, rogue_bosses),
    challenges (liste de {id, name, reward, journal, date}),
    sessions (liste de {journal, date, route, workout, source, duration_s, distance_m, climb_m,
        erg_s, erg_completed, counted, reason, xp, coins, gains}),
    errors (liste de {journal, error}).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from .. import config as config_mod
from ..journal import JOURNAL_DIR
from ..coins import CoinsError, balance, coin_table, earned_coins, session_coins
from ..profile import PROFILE_PATH, peek_profile
from ..progression import ProgressionError, load_table, recompute
from ..workout import WorkoutError, load_workout, workout_path

REASONS = {"replay": "rejeu", "simulated": "séance simulée", "too_short": "moins de 5 min"}


def _date(ts: float | None) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "?"


def _fr(x: float, digits: int = 1) -> str:
    return f"{x:,.{digits}f}".replace(",", " ").replace(".", ",")


def workout_duration_finder(directory: Path):
    """Durée d'un entraînement d'après son identifiant (None s'il est introuvable)."""
    cache: dict[str, float | None] = {}

    def find(workout_id: str) -> float | None:
        if workout_id not in cache:
            try:
                cache[workout_id] = load_workout(workout_path(directory, workout_id)).duration_s
            except (WorkoutError, OSError):
                cache[workout_id] = None
        return cache[workout_id]
    return find


def run(directory: Path | None, as_json: bool, config_path: Path | None,
        workouts_dir: Path | None = None, profile_path: Path = PROFILE_PATH) -> int:
    try:
        config_mod.load(config_path)
        table = load_table()
        ct = coin_table(table)
    except (config_mod.ConfigError, ProgressionError, CoinsError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 2
    directory = directory or JOURNAL_DIR
    progress = recompute(directory, table,
                         workout_duration_finder(workouts_dir or config_mod.WORKOUTS_DIR))
    lv = progress.level
    earned = earned_coins(progress, ct)
    solde = balance(progress, peek_profile(profile_path), ct)
    if as_json:
        out = {
            "directory": str(directory), "total_xp": progress.total_xp, "level": lv.level,
            "xp_level_start": lv.xp_level_start, "xp_next_level": lv.xp_next_level,
            "coins_earned": earned, "coins_balance": solde,
            "stats": {k: round(v, 1) for k, v in progress.stats.items()},
            "challenges": [{"id": c.id, "name": c.name, "reward": c.reward, "journal": c.journal,
                            "date": _date(c.start_ts)} for c in progress.challenges],
            "sessions": [{
                "journal": r.facts.journal, "date": _date(r.facts.start_ts), "route": r.facts.route_id,
                "workout": r.facts.workout_id, "source": r.facts.source,
                "duration_s": round(r.facts.duration_s, 1), "distance_m": round(r.facts.distance_m, 1),
                "climb_m": round(r.facts.climb_m, 1), "erg_s": r.facts.erg_s,
                "erg_completed": r.facts.erg_completed, "counted": r.gains is not None,
                "reason": r.reason, "xp": r.gains.total if r.gains else 0,
                "coins": session_coins(r.facts, ct) if r.gains else 0,
                "gains": r.gains.as_list() if r.gains else [],
            } for r in progress.sessions],
            "errors": [{"journal": n, "error": e} for n, e in progress.errors],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    nxt = f" / {_fr(lv.xp_next_level, 0)} pour le niveau {lv.level + 1}" if lv.xp_next_level else " (niveau maximal)"
    print(f"Niveau {lv.level} — {_fr(progress.total_xp, 0)} XP{nxt}")
    st = progress.stats
    print(f"Pièces : {_fr(earned, 0)} gagnées, solde {_fr(solde, 0)}")
    print(f"{int(st['sessions'])} séances comptées, {_fr(st['total_km'])} km, "
          f"{_fr(st['total_climb_m'], 0)} m de dénivelé")
    if progress.challenges:
        print("Défis réussis :")
        for c in progress.challenges:
            print(f"  {_date(c.start_ts)}  {c.name}")
    print()
    for r in progress.sessions:
        f = r.facts
        head = (f"{_date(f.start_ts)}  {(f.route_id or '?')[:24]:<24}  {f.duration_s / 60:5.0f} min  "
                f"{_fr(f.distance_m / 1000):>6} km  {f.climb_m:5.0f} m")
        tail = f"{r.gains.total:6d} XP" if r.gains else f"  refusée : {REASONS.get(r.reason, r.reason)}"
        print(head + "  " + tail)
    for name, err in progress.errors:
        print(f"{name} : illisible ({err})")
    if not progress.sessions:
        print(f"Aucune séance dans {directory}")
    return 0
