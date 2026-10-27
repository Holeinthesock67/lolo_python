"""Reprise d'une séance après un plantage du core (lot N8).

Le lanceur relance `openride-core run --resume JOURNAL` quand le core meurt pendant une séance.
Ce module relit le journal JSONL (dernière ligne tronquée tolérée, comme `recover`) et en tire
l'état à restaurer : temps chronométré, distance, braquet, mode, bloc ERG et temps écoulé dans
le bloc, biais du Click. La vitesse repart de zéro : le cycliste a dû s'arrêter de pédaler.

Un journal est « non terminé » quand son dernier événement du chronomètre n'est pas `stop`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .journal import GAME_KINDS, TIMER_EVENTS, read_journal


class ResumeError(Exception):
    """Journal impossible à reprendre (absent, vide, déjà terminé)."""


@dataclass
class ResumeState:
    path: Path
    route_id: str | None
    workout_id: str | None
    t: float                          # temps chronométré (s) de la dernière ligne complète
    s: float                          # distance (m)
    gear: int | None
    mode: str                         # SIM ou ERG
    block: int | None                 # bloc ERG en cours (à partir de 1), None hors ERG
    t_block: float = 0.0              # temps écoulé dans le bloc (s)
    erg_bias_pct: float | None = None # biais du Click (écart au défaut, %), None s'il est inconnu
    last_ts: float = 0.0              # heure Unix de la dernière ligne (instant approché du plantage)
    running: bool = True              # le chronomètre tournait au moment du plantage
    lines: list[dict] = field(default_factory=list)   # lignes à reprendre en mémoire (sans en-tête)
    rogue: dict | None = None         # dernier instantané `rogue_snapshot` d'une run Cyber-Rogue (lot R8)


def _timer_events(lines: list[dict]) -> list[dict]:
    return [ln for ln in lines if ln.get("kind") == "event" and ln.get("event") in TIMER_EVENTS]


def is_unfinished(path: Path) -> bool:
    """Vrai si le journal a commencé une séance que rien n'a terminée."""
    try:
        events = _timer_events(list(read_journal(path)))
    except OSError:
        return False
    return bool(events) and events[-1]["event"] != "stop"


def find_unfinished_journal(directory: Path, since: float = 0.0) -> Path | None:
    """Journal le plus récent, modifié depuis `since` (heure Unix), et non terminé."""
    try:
        files = [p for p in directory.glob("*.jsonl") if p.stat().st_mtime >= since]
    except OSError:
        return None
    if not files:
        return None
    newest = max(files, key=lambda p: p.stat().st_mtime)
    return newest if is_unfinished(newest) else None


def load_resume_state(path: Path) -> ResumeState:
    """Relit un journal non terminé et renvoie l'état de la séance à reprendre."""
    try:
        all_lines = list(read_journal(path))
    except OSError as exc:
        raise ResumeError(f"journal illisible ({path}) : {exc}") from exc
    header = next((ln for ln in all_lines if ln.get("kind") == "header"), {})
    lines = [ln for ln in all_lines if ln.get("kind") in ("record", "event", "device", *GAME_KINDS)]
    events = _timer_events(lines)
    if not events:
        raise ResumeError(f"aucune séance commencée dans {path}")
    if events[-1]["event"] == "stop":
        raise ResumeError(f"séance déjà terminée dans {path}")
    records = [ln for ln in lines if ln.get("kind") == "record"]

    state = ResumeState(
        path=path, route_id=header.get("route_id"), workout_id=header.get("workout_id"),
        t=0.0, s=0.0, gear=None, mode="SIM", block=None,
        last_ts=float(events[-1]["ts"]), running=events[-1]["event"] in ("start", "resume"),
        lines=lines, rogue=next((ln for ln in reversed(lines) if ln.get("kind") == "rogue_snapshot"), None))
    if not records:
        return state
    last = records[-1]
    state.t = float(last.get("t") or 0.0)
    state.s = float(last.get("distance") or 0.0)
    state.gear = last.get("gear")
    state.mode = str(last.get("mode") or "SIM")
    state.last_ts = max(state.last_ts, float(last["ts"]))
    state.block = last.get("block")
    if state.block is not None:
        # Entrée dans le bloc : entre la dernière ligne du bloc précédent et la première de
        # celui-ci (lignes à 1 Hz), donc à 0,5 s près en prenant le milieu.
        first = len(records) - 1
        while first > 0 and records[first - 1].get("block") == state.block:
            first -= 1
        t_first = float(records[first].get("t") or 0.0)
        t_prev = float(records[first - 1].get("t") or 0.0) if first > 0 else None
        entry = t_first if t_prev is None else (t_prev + t_first) / 2.0
        if first == 0 and state.block == 1:
            entry = 0.0   # premier bloc : il commence avec la séance
        state.t_block = max(0.0, state.t - entry)
        bias = next((r.get("erg_bias_pct") for r in reversed(records)
                     if r.get("erg_bias_pct") is not None), None)
        state.erg_bias_pct = bias
    return state
