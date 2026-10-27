"""Progression de la série V (lot V2) : expérience, niveaux et défis recalculés depuis le journal.

Module pur : il ne lit que les journaux de séance (`journal.py`) et le fichier de données
`data/progression.toml` (surchargé clé par clé par `~/OpenRide/progression.toml`). Rien n'est
stocké : effacer le profil ne perd ni l'expérience ni les défis (plan V, risque 4).

Règles (plan V §2.1, décisions du 25 octobre 2026) :
- seules comptent les séances enregistrées par OpenRide, `source` = `live` dans l'en-tête du
  journal (absente des journaux antérieurs au lot V2 : comptés comme `live`) ; pas de rejeu,
  pas de séance simulée, pas de séance de moins de `min_session_s` chronométrées ;
- un journal repris après une panne d'écriture (`_reprise-N`, `recorder.py`) contient toute la
  séance : deux journaux de même heure de départ comptent une fois (le plus long) ;
- en ERG, avec `erg_replaces_distance`, les minutes d'entraînement remplacent la distance et
  le dénivelé (question V-Q7).

Les événements des séries T et R (segments, maillots, runs) arrivent par `SessionFacts.events`
(lot V5) : `{"kind": "segment", "pr": bool, "category": str | None}`,
`{"kind": "jersey", "jersey": "kom" | "sprint"}`,
`{"kind": "rogue_run", "minutes": float, "bosses": [identifiant, ...]}`.
"""

from __future__ import annotations

import copy
import math
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from .config import OPENRIDE_HOME
from .journal import read_journal

DEFAULT_TABLE_PATH = Path(__file__).resolve().parent / "data" / "progression.toml"
USER_TABLE_PATH = OPENRIDE_HOME / "progression.toml"

SOURCES = ("live", "simulated", "replay")
GAIN_SOURCES = ("distance", "climb", "erg", "erg_bonus", "segment", "segment_pr", "jersey",
                "rogue", "rogue_boss")
STATS = ("total_km", "total_climb_m", "sessions", "best_session_km", "best_session_climb_m",
         "erg_completed", "segments", "segment_prs", "jerseys_kom", "jerseys_sprint",
         "hc_climbs", "rogue_bosses")
ERG_END_TOLERANCE_S = 5.0
SAME_START_TOLERANCE_S = 1.0

# Clés connues des sections vérifiées : nom -> type attendu. Les autres sections (catalogue
# du lot V3, pièces du lot V3b) sont gardées telles quelles pour les lots qui les lisent.
_SCHEMA: dict[str, dict[str, type]] = {
    "xp": {"per_km": float, "per_climb_m": float, "erg_per_min": float,
           "erg_completed_bonus": float, "per_segment": float, "per_segment_pr": float,
           "per_jersey": float, "rogue_per_min": float, "rogue_boss_default": float,
           "rogue_boss": dict},
    "rules": {"min_session_s": float, "climb_deadband_m": float, "erg_replaces_distance": bool},
    "levels": {"count": int, "xp_level_2": float, "xp_level_max": float},
}
_CHALLENGE_KEYS = {"id": str, "name": str, "stat": str, "threshold": float, "reward": str}


class ProgressionError(Exception):
    """Fichier de données invalide (le message nomme le fichier et la clé fautive)."""


# --- fichier de données ---------------------------------------------------------------------

@dataclass(frozen=True)
class Challenge:
    id: str
    name: str
    stat: str
    threshold: float
    reward: str = ""


@dataclass
class Table:
    """Tables d'équilibrage chargées et vérifiées ; `data` garde tout le fichier fusionné."""
    data: dict[str, Any]
    thresholds: list[int]            # thresholds[n - 1] : expérience cumulée du niveau n
    challenges: list[Challenge]

    def xp(self, key: str) -> Any:
        return self.data["xp"][key]

    def rule(self, key: str) -> Any:
        return self.data["rules"][key]

    @property
    def level_count(self) -> int:
        return len(self.thresholds)


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _check_value(value: Any, expected: type, where: str) -> Any:
    if expected is bool:
        if not isinstance(value, bool):
            raise ProgressionError(f"{where} : booléen attendu (true ou false)")
        return value
    if expected in (int, float):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ProgressionError(f"{where} : nombre attendu")
        if value < 0:
            raise ProgressionError(f"{where} : doit être positif ou nul")
        if expected is int and int(value) != value:
            raise ProgressionError(f"{where} : entier attendu")
        return expected(value)
    if not isinstance(value, expected):
        raise ProgressionError(f"{where} : {expected.__name__} attendu")
    return value


def level_thresholds(count: int, xp_level_2: float, xp_level_max: float) -> list[int]:
    """Seuils cumulés des niveaux 1 à `count` : écart croissant de façon régulière d'un niveau
    au suivant (progression arithmétique), le premier valant `xp_level_2` et le total
    `xp_level_max` ; arrondis à la dizaine."""
    steps = count - 1
    if steps < 2:
        raise ProgressionError("[levels] count : au moins 3 niveaux")
    increment = (xp_level_max - steps * xp_level_2) / (steps * (steps - 1) / 2)
    if increment <= 0:
        raise ProgressionError("[levels] xp_level_max : trop petit pour des écarts croissants "
                               f"(au moins {steps * xp_level_2:.0f} avec xp_level_2 = {xp_level_2:g})")
    out, total = [0], 0.0
    for k in range(steps):
        total += xp_level_2 + increment * k
        out.append(int(round(total / 10.0)) * 10)
    return out


def _validate(data: dict, source: str) -> Table:
    for section, keys in _SCHEMA.items():
        values = data.get(section)
        if not isinstance(values, dict):
            raise ProgressionError(f"{source} : section [{section}] absente ou mal formée")
        for key, value in values.items():
            if key not in keys:
                raise ProgressionError(f"{source}, [{section}] {key} : clé inconnue")
            values[key] = _check_value(value, keys[key], f"{source}, [{section}] {key}")
        missing = [k for k in keys if k not in values and k != "rogue_boss"]
        if missing:
            raise ProgressionError(f"{source}, [{section}] {missing[0]} : clé manquante")
    for boss, value in data["xp"].get("rogue_boss", {}).items():
        data["xp"]["rogue_boss"][boss] = _check_value(value, float, f"{source}, [xp.rogue_boss] {boss}")
    data["xp"].setdefault("rogue_boss", {})
    lv = data["levels"]
    thresholds = level_thresholds(lv["count"], lv["xp_level_2"], lv["xp_level_max"])

    challenges: list[Challenge] = []
    seen: set[str] = set()
    raw = data.get("challenges", [])
    if not isinstance(raw, list):
        raise ProgressionError(f"{source} : [[challenges]] doit être une liste")
    for i, ch in enumerate(raw):
        where = f"{source}, [[challenges]] n° {i + 1}"
        if not isinstance(ch, dict):
            raise ProgressionError(f"{where} : table attendue")
        for key in ch:
            if key not in _CHALLENGE_KEYS:
                raise ProgressionError(f"{where} {key} : clé inconnue")
        for key in ("id", "name", "stat", "threshold"):
            if key not in ch:
                raise ProgressionError(f"{where} {key} : clé manquante")
        values = {k: _check_value(v, _CHALLENGE_KEYS[k], f"{where} {k}") for k, v in ch.items()}
        if values["stat"] not in STATS:
            raise ProgressionError(f"{where} stat : « {values['stat']} » inconnue "
                                   f"(attendu : {', '.join(STATS)})")
        if values["id"] in seen:
            raise ProgressionError(f"{where} id : « {values['id']} » en double")
        seen.add(values["id"])
        challenges.append(Challenge(**values))
    return Table(data=data, thresholds=thresholds, challenges=challenges)


def _read_toml(path: Path) -> dict:
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise ProgressionError(f"{path} : TOML invalide : {exc}") from None
    except OSError as exc:
        raise ProgressionError(f"{path} : lecture impossible : {exc}") from None


def load_table(user_path: Path | None = USER_TABLE_PATH,
               default_path: Path = DEFAULT_TABLE_PATH) -> Table:
    """Tables livrées, surchargées par `user_path` s'il existe ; lève `ProgressionError`."""
    data = _read_toml(default_path)
    source = str(default_path)
    if user_path is not None and user_path.exists():
        data = _merge(data, _read_toml(user_path))
        source = str(user_path)
    return _validate(data, source)


# --- faits d'une séance -------------------------------------------------------------------

POWER_STEP_W = 10   # pas de l'histogramme de puissance d'une séance
RECORD_DURATIONS_S = (5, 60, 300, 1200)   # records de puissance moyenne (primes en pièces, V3b)


@dataclass
class SessionFacts:
    journal: str
    start_ts: float | None = None
    route_id: str | None = None
    workout_id: str | None = None
    source: str = "live"
    duration_s: float = 0.0
    distance_m: float = 0.0
    climb_m: float = 0.0
    erg_s: float = 0.0
    erg_completed: bool | None = None
    events: list[dict] = field(default_factory=list)
    power_s: dict[int, float] = field(default_factory=dict)   # secondes par pas de 10 W (pièces, V3b)
    ftp_w: float | None = None   # FTP de la séance si l'en-tête la donne (écrite par V11)
    best_power: dict[int, float] = field(default_factory=dict)   # meilleure moyenne par durée (s)


def _climb(altitudes: Iterable[float], deadband_m: float) -> float:
    """Dénivelé positif avec zone morte : une variation plus petite que `deadband_m` est du bruit."""
    total, ref = 0.0, None
    for alt in altitudes:
        if ref is None:
            ref = alt
        elif alt - ref >= deadband_m:
            total += alt - ref
            ref = alt
        elif ref - alt >= deadband_m:
            ref = alt
    return total


def best_power(powers: list[float], durations: Iterable[int] = RECORD_DURATIONS_S) -> dict[int, float]:
    """Meilleure puissance moyenne sur chaque durée (relevés à 1 Hz) ; durée absente si trop longue."""
    best: dict[int, float] = {}
    for d in durations:
        if d > len(powers):
            continue
        window = sum(powers[:d])
        top = window
        for i in range(d, len(powers)):
            window += powers[i] - powers[i - d]
            top = max(top, window)
        best[d] = round(top / d, 1)
    return best


def session_facts(path: Path, workout_duration_s: float | None = None,
                  climb_deadband_m: float = 1.0) -> SessionFacts:
    """Lit un journal ; `workout_duration_s` sert à dire si l'entraînement ERG est terminé."""
    facts = SessionFacts(journal=path.name)
    altitudes: list[float] = []
    powers: list[float] = []
    first_record_ts = None
    for line in read_journal(path):
        if not isinstance(line, dict):
            continue
        kind = line.get("kind")
        if kind == "header":
            facts.route_id = line.get("route_id")
            facts.workout_id = line.get("workout_id")
            src = line.get("source")
            facts.source = src if src in SOURCES else "live"
            ftp = line.get("ftp_w")
            if isinstance(ftp, (int, float)) and not isinstance(ftp, bool) and ftp > 0:
                facts.ftp_w = float(ftp)
        elif kind == "event":
            if line.get("event") == "start" and facts.start_ts is None:
                facts.start_ts = float(line.get("ts", 0.0))
        elif kind == "record":
            if first_record_ts is None:
                first_record_ts = float(line.get("ts", 0.0))
            facts.duration_s = max(facts.duration_s, float(line.get("t") or 0.0))
            facts.distance_m = max(facts.distance_m, float(line.get("distance") or 0.0))
            if line.get("alt") is not None:
                altitudes.append(float(line["alt"]))
            if line.get("target_w") is not None:
                facts.erg_s += 1.0   # relevés à 1 Hz pendant la séance chronométrée
            power = line.get("power")
            if isinstance(power, (int, float)) and not isinstance(power, bool) and power >= 0:
                step = int(power // POWER_STEP_W) * POWER_STEP_W
                facts.power_s[step] = facts.power_s.get(step, 0.0) + 1.0
            powers.append(float(power) if isinstance(power, (int, float)) and not isinstance(power, bool)
                          and power >= 0 else 0.0)
        elif kind in ("segment", "jersey", "rogue_run"):   # lignes écrites par les séries T et R (V5)
            facts.events.append(dict(line))
    if facts.start_ts is None:
        facts.start_ts = first_record_ts
    facts.climb_m = _climb(altitudes, climb_deadband_m)
    facts.best_power = best_power(powers)
    if facts.erg_s > 0 and workout_duration_s:
        facts.erg_completed = facts.erg_s >= workout_duration_s - ERG_END_TOLERANCE_S
    return facts


# --- gains et niveaux ----------------------------------------------------------------------

@dataclass
class XpGains:
    by_source: dict[str, int]

    @property
    def total(self) -> int:
        return sum(self.by_source.values())

    def as_list(self) -> list[dict]:
        """Sources non nulles, dans l'ordre du plan (forme du message `xp` du contrat V1)."""
        return [{"source": s, "points": p} for s, p in self.by_source.items() if p]


def ineligible_reason(facts: SessionFacts, table: Table) -> str | None:
    if facts.source == "replay":
        return "replay"
    if facts.source == "simulated":
        return "simulated"
    if facts.duration_s < table.rule("min_session_s"):
        return "too_short"
    return None


def session_gains(facts: SessionFacts, table: Table) -> XpGains:
    """Points de la séance par source (entiers arrondis par source), sans contrôle d'éligibilité."""
    g = dict.fromkeys(GAIN_SOURCES, 0)
    erg = facts.erg_s > 0
    if not (erg and table.rule("erg_replaces_distance")):
        g["distance"] = round(table.xp("per_km") * facts.distance_m / 1000.0)
        g["climb"] = round(table.xp("per_climb_m") * facts.climb_m)
    if erg:
        g["erg"] = round(table.xp("erg_per_min") * facts.erg_s / 60.0)
        if facts.erg_completed:
            g["erg_bonus"] = round(g["erg"] * table.xp("erg_completed_bonus"))
    bosses = table.xp("rogue_boss")
    for ev in facts.events:
        kind = ev.get("kind")
        if kind == "segment":
            g["segment"] += round(table.xp("per_segment"))
            if ev.get("pr"):
                g["segment_pr"] += round(table.xp("per_segment_pr"))
        elif kind == "jersey":
            g["jersey"] += round(table.xp("per_jersey"))
        elif kind == "rogue_run":
            g["rogue"] += round(table.xp("rogue_per_min") * float(ev.get("minutes") or 0.0))
            for boss in ev.get("bosses") or []:
                g["rogue_boss"] += round(bosses.get(boss, table.xp("rogue_boss_default")))
    return XpGains(g)


@dataclass(frozen=True)
class LevelInfo:
    level: int
    xp: int
    xp_level_start: int
    xp_next_level: int | None


def level_for(xp: int, table: Table) -> LevelInfo:
    th = table.thresholds
    level = 1
    for n, needed in enumerate(th, start=1):
        if xp >= needed:
            level = n
    nxt = th[level] if level < len(th) else None
    return LevelInfo(level=level, xp=xp, xp_level_start=th[level - 1], xp_next_level=nxt)


# --- recalcul complet ---------------------------------------------------------------------

@dataclass
class SessionResult:
    facts: SessionFacts
    gains: XpGains | None        # None si la séance est refusée
    reason: str | None           # raison du refus, ou None


@dataclass(frozen=True)
class ChallengeDone:
    id: str
    name: str
    reward: str
    journal: str
    start_ts: float | None


@dataclass
class Progress:
    sessions: list[SessionResult]
    errors: list[tuple[str, str]]
    total_xp: int
    level: LevelInfo
    stats: dict[str, float]
    challenges: list[ChallengeDone]

    @property
    def counted(self) -> list[SessionResult]:
        return [r for r in self.sessions if r.gains is not None]


def _add_stats(stats: dict[str, float], facts: SessionFacts) -> None:
    km = facts.distance_m / 1000.0
    stats["total_km"] += km
    stats["total_climb_m"] += facts.climb_m
    stats["sessions"] += 1
    stats["best_session_km"] = max(stats["best_session_km"], km)
    stats["best_session_climb_m"] = max(stats["best_session_climb_m"], facts.climb_m)
    if facts.erg_completed:
        stats["erg_completed"] += 1
    for ev in facts.events:
        kind = ev.get("kind")
        if kind == "segment":
            stats["segments"] += 1
            stats["segment_prs"] += 1 if ev.get("pr") else 0
            stats["hc_climbs"] += 1 if ev.get("category") == "HC" else 0
        elif kind == "jersey":
            key = "jerseys_kom" if ev.get("jersey") == "kom" else "jerseys_sprint"
            stats[key] += 1
        elif kind == "rogue_run":
            stats["rogue_bosses"] += len(ev.get("bosses") or [])


def _dedupe(facts_list: list[SessionFacts]) -> list[SessionFacts]:
    """Un journal repris après une panne (`_reprise-N`) recopie toute la séance : même départ."""
    out: list[SessionFacts] = []
    for f in facts_list:
        twin = next((o for o in out if f.start_ts is not None and o.start_ts is not None
                     and abs(o.start_ts - f.start_ts) <= SAME_START_TOLERANCE_S), None)
        if twin is None:
            out.append(f)
        elif f.duration_s > twin.duration_s:
            out[out.index(twin)] = f
    return out


WorkoutDurations = Callable[[str], float | None] | dict[str, float] | None


def _duration_lookup(workout_durations: WorkoutDurations) -> Callable[[str], float | None]:
    if workout_durations is None:
        return lambda _id: None
    if isinstance(workout_durations, dict):
        return workout_durations.get
    return workout_durations


def recompute(journal_dir: Path, table: Table,
              workout_durations: WorkoutDurations = None) -> Progress:
    """Expérience, niveau, statistiques et défis depuis tous les journaux de `journal_dir`."""
    lookup = _duration_lookup(workout_durations)
    facts_list: list[SessionFacts] = []
    errors: list[tuple[str, str]] = []
    paths = sorted(journal_dir.glob("*.jsonl")) if journal_dir.is_dir() else []
    deadband = table.rule("climb_deadband_m")
    for path in paths:
        try:
            header_wid = None
            for line in read_journal(path):
                if isinstance(line, dict) and line.get("kind") == "header":
                    header_wid = line.get("workout_id")
                break
            duration = lookup(header_wid) if isinstance(header_wid, str) else None
            facts_list.append(session_facts(path, duration, deadband))
        except (OSError, ValueError, TypeError) as exc:
            errors.append((path.name, str(exc)))
    facts_list = _dedupe(facts_list)
    facts_list.sort(key=lambda f: (f.start_ts if f.start_ts is not None else math.inf, f.journal))

    stats = dict.fromkeys(STATS, 0.0)
    done: dict[str, ChallengeDone] = {}
    results: list[SessionResult] = []
    total = 0
    for facts in facts_list:
        reason = ineligible_reason(facts, table)
        if reason is not None:
            results.append(SessionResult(facts, None, reason))
            continue
        gains = session_gains(facts, table)
        total += gains.total
        results.append(SessionResult(facts, gains, None))
        _add_stats(stats, facts)
        for ch in table.challenges:
            if ch.id not in done and stats[ch.stat] >= ch.threshold:
                done[ch.id] = ChallengeDone(ch.id, ch.name, ch.reward, facts.journal, facts.start_ts)
    return Progress(sessions=results, errors=errors, total_xp=total,
                    level=level_for(total, table), stats=stats, challenges=list(done.values()))


def journal_source(trainer: str, replay: str = "") -> str:
    """Valeur `source` de l'en-tête du journal d'après le pilote du trainer (`[drivers]`)."""
    if replay:
        return "replay"
    return "live" if trainer == "ftms" else "simulated"
