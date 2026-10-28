"""Progression recalculée depuis le journal des séances (lot V2) : `openride-core xp`.

    openride-core xp [--dir DOSSIER] [--json] [--config FICHIER] [--save FICHIER | --compare FICHIER]

Lit tous les journaux `.jsonl` de `~/OpenRide/Activities/.journal/` (ou `--dir`) et les tables
de `data/progression.toml` (surchargées par `~/OpenRide/progression.toml`), puis affiche le
niveau, l'expérience, les défis réussis et une ligne par séance (points, ou raison du refus :
`replay`, `simulated`, `too_short`). Sert à régler la courbe sur l'historique réel avant de la
figer (plan V, risque 2). Rien n'est écrit, sauf l'instantané de `--save`.

Non-régression du recalcul (lot X39) : `--save FICHIER` écrit l'instantané (la sortie `--json`) avant une
PR ; `--compare FICHIER` recalcule après la PR et donne l'écart d'expérience, de pièces et de défis, au total
et séance par séance (code 0 sans écart, 1 avec écart, 2 si l'instantané est illisible). Une ancienne sortie
`--json` sert aussi d'instantané. Avec les vrais journaux du PC, l'instantané reste local : il ne se publie
pas (règle de confidentialité).

Clés de la sortie `--json` (stables) :
    directory, total_xp, level, xp_level_start, xp_next_level, coins_earned, coins_balance
        (pièces du lot V3b ; solde d'après ~/OpenRide/profile.json),
    stats (total_km, total_climb_m, sessions, best_session_km, best_session_climb_m,
        erg_completed, segments, segment_prs, jerseys_kom, jerseys_sprint, hc_climbs, rogue_bosses),
    challenges (liste de {id, name, reward, journal, date}),
    sessions (liste de {journal, date, route, workout, source, duration_s, distance_m, climb_m,
        erg_s, erg_completed, counted, reason, xp, coins, gains}),
    errors (liste de {journal, error}).

Clés de la sortie `--compare --json` : before, after (fichier ou dossier), totals (liste de {key, before,
after}), sessions (liste de {journal, date, before, after, changes}, `before`/`after` à null pour une séance
ajoutée ou disparue), challenges_added, challenges_removed (listes de {id, journal}), errors_added.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .. import config as config_mod
from ..journal import JOURNAL_DIR
from ..coins import CoinsError, balance, coin_table, coins_by_session, earned_coins
from ..profile import PROFILE_PATH, peek_profile
from ..progression import ProgressionError, load_table, recompute
from ..garage import workout_duration_finder

REASONS = {"replay": "rejeu", "simulated": "séance simulée", "too_short": "moins de 5 min"}


def _date(ts: float | None) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "?"


def _fr(x: float, digits: int = 1) -> str:
    return f"{x:,.{digits}f}".replace(",", " ").replace(".", ",")


def run(directory: Path | None, as_json: bool, config_path: Path | None,
        workouts_dir: Path | None = None, profile_path: Path = PROFILE_PATH,
        save: Path | None = None, compare: Path | None = None) -> int:
    try:
        cfg = config_mod.load(config_path)
        table = load_table()
        ct = coin_table(table, cfg.rider.ftp_w)
    except (config_mod.ConfigError, ProgressionError, CoinsError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 2
    directory = directory or JOURNAL_DIR
    progress = recompute(directory, table,
                         workout_duration_finder(workouts_dir or config_mod.WORKOUTS_DIR))
    lv = progress.level
    earned = earned_coins(progress, ct)
    per_session = coins_by_session(progress, ct)
    solde = balance(progress, peek_profile(profile_path), ct)
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
            "coins": per_session.get(r.facts.journal, 0),
            "gains": r.gains.as_list() if r.gains else [],
        } for r in progress.sessions],
        "errors": [{"journal": n, "error": e} for n, e in progress.errors],
    }
    if compare is not None:
        try:
            before = json.loads(compare.read_text(encoding="utf-8"))
            if not isinstance(before, dict) or not isinstance(before.get("sessions"), list):
                raise ValueError("pas une sortie de « openride-core xp --json »")
        except (OSError, ValueError) as exc:
            print(f"Erreur : instantané {compare} illisible ({exc})", file=sys.stderr)
            return 2
        diff = compare_snapshots(before, out, str(compare))
        print(json.dumps(diff, ensure_ascii=False, indent=2) if as_json else format_diff(diff), end="\n" if as_json else "")
        return 1 if has_changes(diff) else 0
    if save is not None:
        save.parent.mkdir(parents=True, exist_ok=True)
        save.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Instantané écrit : {save} ({len(out['sessions'])} séances, {_fr(progress.total_xp, 0)} XP)",
              file=sys.stderr if as_json else sys.stdout)
    if as_json:
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


# --- comparaison avant/après (lot X39) ---------------------------------------------------------

TOTAL_KEYS = ("total_xp", "level", "coins_earned", "coins_balance")
SESSION_KEYS = ("counted", "reason", "xp", "coins")
TOTAL_LABELS = {"total_xp": "XP", "level": "niveau", "coins_earned": "pièces gagnées", "coins_balance": "solde"}


def compare_snapshots(before: dict[str, Any], after: dict[str, Any], before_name: str = "") -> dict[str, Any]:
    """Écart entre deux sorties `xp --json` : totaux, séances (par journal), défis et erreurs."""
    totals = [{"key": k, "before": before.get(k), "after": after.get(k)}
              for k in TOTAL_KEYS if before.get(k) != after.get(k)]
    old = {s["journal"]: s for s in before.get("sessions", [])}
    new = {s["journal"]: s for s in after.get("sessions", [])}
    sessions = []
    for name in sorted(old.keys() | new.keys(), key=lambda n: ((new.get(n) or old[n]).get("date", ""), n)):
        a, b = old.get(name), new.get(name)
        if a is None or b is None:
            changes = ["ajoutée" if a is None else "disparue"]
        else:
            changes = [k for k in SESSION_KEYS if a.get(k) != b.get(k)]
            if not changes:
                continue
        pick = lambda r: None if r is None else {k: r.get(k) for k in SESSION_KEYS}   # noqa: E731
        sessions.append({"journal": name, "date": (b or a).get("date"), "before": pick(a), "after": pick(b),
                         "changes": changes})
    key = lambda c: (c.get("id"), c.get("journal"))   # noqa: E731
    old_c = {key(c) for c in before.get("challenges", [])}
    new_c = {key(c) for c in after.get("challenges", [])}
    old_e = {e.get("journal") for e in before.get("errors", [])}
    return {
        "before": before_name or before.get("directory", ""), "after": after.get("directory", ""),
        "totals": totals, "sessions": sessions,
        "challenges_added": [{"id": i, "journal": j} for i, j in sorted(new_c - old_c, key=str)],
        "challenges_removed": [{"id": i, "journal": j} for i, j in sorted(old_c - new_c, key=str)],
        "errors_added": [e for e in after.get("errors", []) if e.get("journal") not in old_e],
    }


def has_changes(diff: dict[str, Any]) -> bool:
    return any(diff[k] for k in ("totals", "sessions", "challenges_added", "challenges_removed", "errors_added"))


def _session_text(r: dict[str, Any] | None) -> str:
    if r is None:
        return "—"
    if not r.get("counted"):
        return f"refusée ({REASONS.get(r.get('reason'), r.get('reason'))})"
    return f"{r.get('xp', 0)} XP, {r.get('coins', 0)} pièces"


def format_diff(diff: dict[str, Any]) -> str:
    lines = [f"Progression recalculée face à l'instantané {diff['before']}"]
    if not has_changes(diff):
        return "\n".join(lines + ["[OK] aucun écart : expérience, pièces, défis et séances identiques"]) + "\n"
    for t in diff["totals"]:
        b, a = t["before"], t["after"]
        delta = f" ({a - b:+g})" if isinstance(a, (int, float)) and isinstance(b, (int, float)) else ""
        lines.append(f"[ÉCART] {TOTAL_LABELS[t['key']]} : {b} → {a}{delta}")
    for c in diff["challenges_added"]:
        lines.append(f"[ÉCART] défi gagné en plus : {c['id']} ({c['journal']})")
    for c in diff["challenges_removed"]:
        lines.append(f"[ÉCART] défi perdu : {c['id']} ({c['journal']})")
    for e in diff["errors_added"]:
        lines.append(f"[ÉCART] journal devenu illisible : {e.get('journal')} ({e.get('error')})")
    if diff["sessions"]:
        lines += ["", f"{len(diff['sessions'])} séance(s) changée(s) :"]
        for s in diff["sessions"]:
            lines.append(f"  {s['date']}  {s['journal']:<32}  {_session_text(s['before'])} → {_session_text(s['after'])}")
    return "\n".join(lines) + "\n"
