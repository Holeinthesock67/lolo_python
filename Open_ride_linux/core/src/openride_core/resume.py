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
    erg_kind: str | None = None       # ERG d'une session libre (`free`, `cadence`, lot O18), None sinon
    target_w: float | None = None     # dernière cible ERG écrite (W), pour l'ERG d'une session libre
    cadence_target_rpm: int | None = None  # cadence cible de l'ERG cadence (lot O18)


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
    state.erg_kind = last.get("erg_kind")
    if state.erg_kind is not None:
        state.cadence_target_rpm = last.get("cadence_target_rpm")
        state.target_w = next((r.get("target_w") for r in reversed(records)
                               if r.get("target_w") is not None and r.get("erg_kind") == state.erg_kind), None)
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


# --- séance interrompue d'un lancement précédent (lot O34) --------------------------------------

INTERRUPTED_SCAN = 10   # journaux les plus récents examinés au démarrage (lecture complète de chacun)
INTERRUPTED_MAX = 3     # séances proposées au plus


def _summary_of(lines: list[dict]):
    from .fit_export import summarize

    records = [ln for ln in lines if ln.get("kind") == "record"]
    events = [ln for ln in lines if ln.get("kind") == "event"]
    if not records:
        return records, None
    stop = {"kind": "event", "event": "stop", "ts": max(r["ts"] for r in records)}
    return records, summarize(records, [*events, stop])


def interrupted_sessions(journal_dir: Path, skip: Path | None = None) -> list[dict]:
    """Séances commencées que rien n'a terminées (arrêt brutal du PC ou du core), sans FIT, les plus
    récentes d'abord : `{id, start, route_id, distance_m, duration_s}` (`id` = nom du journal).
    `skip` : journal repris par la séance en cours (`--resume`), jamais proposé."""
    from datetime import datetime

    from .fit_export import default_fit_path

    try:
        files = sorted(journal_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return []
    found: list[dict] = []
    for path in files[:INTERRUPTED_SCAN]:
        if skip is not None and path.resolve() == skip.resolve():
            continue
        try:
            lines = list(read_journal(path))
        except (OSError, UnicodeDecodeError):
            continue
        events = _timer_events(lines)
        if not events or events[-1]["event"] == "stop":
            continue
        header = next((ln for ln in lines if ln.get("kind") == "header"), {})
        records, summary = _summary_of(lines)
        if summary is None or default_fit_path(records[0]["ts"], header.get("route_id")).exists():
            continue   # rien d'enregistré, ou déjà rattrapée par `recover` (lanceur, lot N8)
        last = records[-1]   # temps chronométré et distance du dernier relevé (comme la reprise, lot N8)
        found.append({"id": path.name, "start": datetime.fromtimestamp(summary.start_ts).strftime("%Y-%m-%dT%H:%M"),
                      "route_id": header.get("route_id"), "distance_m": round(float(last.get("distance") or 0.0)),
                      "duration_s": round(float(last.get("t") or 0.0))})
        if len(found) >= INTERRUPTED_MAX:
            break
    return found


def close_interrupted(path: Path, save: bool) -> Path | None:
    """Termine une séance interrompue : FIT si `save` (comme `recover`), puis événement `stop` (raison
    `interrupted`) ajouté au journal, qui n'est plus proposé. Renvoie le FIT ou None.
    Lève `ResumeError` (journal illisible, déjà terminé, sans relevé) ou `OSError` (écriture)."""
    import json

    from .fit_export import journal_to_fit

    try:
        lines = list(read_journal(path))
    except (OSError, UnicodeDecodeError) as exc:
        raise ResumeError(f"journal illisible ({path.name}) : {exc}") from exc
    events = _timer_events(lines)
    records, summary = _summary_of(lines)
    if not events or events[-1]["event"] == "stop" or summary is None:
        raise ResumeError(f"{path.name} : aucune séance interrompue à terminer")
    fit = journal_to_fit(path)[0] if save else None
    with path.open("rb") as fh:
        size = fh.seek(0, 2)
        if size:
            fh.seek(-1, 2)
        ends_cleanly = size == 0 or fh.read(1) == b"\n"
    stop = {"kind": "event", "event": "stop", "ts": summary.end_ts, "reason": "interrupted"}
    with path.open("a", encoding="utf-8") as fh:   # dernière ligne tronquée : laissée seule sur sa ligne
        fh.write(("" if ends_cleanly else "\n") + json.dumps(stop, ensure_ascii=False) + "\n")
    return fit
