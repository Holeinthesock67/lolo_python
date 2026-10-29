"""Test de FTP (lot O10) : rampe par paliers, roulée comme un entraînement ERG.

- **Rampe** (`ramp_workout`) : échauffement, puis paliers d'une minute en watts absolus (+20 W par
  palier, jusqu'à 700 W au plus), puis retour au calme de 5 min à 100 W. La fin de la rampe est
  détectée par `RampWatch` : cadence sous 50 tr/min pendant 5 s, ou puissance sous 80 % de la cible
  pendant 10 s, ou abandon (Z, geste du bloc suivant). La séance saute alors au retour au
  calme au lieu de s'arrêter net. FTP = 75 % de la meilleure puissance moyenne sur 1 minute.

Le test de 20 minutes « à fond » a été retiré (lot O19) : il imposait 20 min de roue libre, et
un entraînement ERG n'a jamais de roue libre. Un ancien résultat `20min` du journal est ignoré.

Une séance de test se choisit comme un entraînement, avec l'identifiant `ftp_test:ramp`
(`openride-core run --ftp-test ramp`, ou une journée d'un plan, lot O11).
À la fin de la séance, `estimate_ftp` calcule le résultat (`FtpResult`) et la session l'écrit au
journal (ligne `ftp_test`, voir `journal.py`). La nouvelle FTP n'est enregistrée dans
`config.toml` qu'après accord : `openride-core ftp-test --accept` (via `config_edit`).

Avertissements du résultat (codes stables, `WARNINGS`) : `too_short` (effort trop court),
`erratic_cadence` (écart type de la cadence au-dessus de 12 tr/min pendant l'effort),
`trainer_dropout` (coupure du trainer pendant l'effort) et `paused` (pause pendant l'effort).
Tous sauf `erratic_cadence` rendent le résultat douteux : `--accept` le refuse sans `--force`.
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .workout import Block, ErgController, Workout

log = logging.getLogger("ftp_test")

KINDS = ("ramp",)
ID_PREFIX = "ftp_test:"

RAMP_MAX_W = 700
RAMP_COOLDOWN_W = 100
RAMP_COOLDOWN_S = 300
RAMP_FACTOR = 0.75            # FTP = 75 % de la meilleure minute

# Fin de la rampe (RampWatch).
LOW_CADENCE_RPM = 50.0
LOW_CADENCE_S = 5.0
LOW_POWER_FRAC = 0.80
LOW_POWER_S = 10.0

# Résultat.
MIN_RAMP_STEPS_S = 240        # moins de 4 min de paliers : test trop court
CADENCE_STDEV_RPM = 12.0
RAMP_FAILURE_TAIL_S = 15      # dernières secondes de la rampe (cadence qui s'effondre) ignorées
DEFAULT_PLAN_FTP_W = 250.0    # FTP supposée pour la durée prévue d'une journée de plan

WARNINGS = {
    "too_short": "test trop court",
    "erratic_cadence": "cadence erratique",
    "trainer_dropout": "coupure du trainer pendant l'effort",
    "paused": "pause pendant l'effort",
}
BLOCKING = ("too_short", "trainer_dropout", "paused")
METHODS = {"ramp": "75 % de la meilleure minute"}
NAMES = {"ramp": "Test de FTP : rampe"}


class FtpTestError(Exception):
    """Test inconnu, journal sans test ; message lisible."""


# --- entraînements -------------------------------------------------------------------------

def _abs(type_: str, duration_s: float, start_w: float, end_w: float | None = None) -> Block:
    return Block(type_, float(duration_s), None, None, float(start_w), float(start_w if end_w is None else end_w))


def ramp_workout(start_w: int = 100, step_w: int = 20, step_s: int = 60, warmup_s: int = 300) -> Workout:
    """Échauffement de `warmup_s` (de 60 % à 100 % du premier palier), paliers de `step_s` en watts
    absolus de `start_w` à 700 W au plus, retour au calme de 5 min à 100 W."""
    if not (0 < start_w <= RAMP_MAX_W and step_w > 0 and step_s > 0 and warmup_s >= 0):
        raise ValueError(f"rampe invalide : {start_w} W, +{step_w} W, {step_s} s, échauffement {warmup_s} s")
    blocks = [_abs("warmup", warmup_s, 0.6 * start_w, start_w)] if warmup_s else []
    blocks += [_abs("steady", step_s, w) for w in range(start_w, RAMP_MAX_W + 1, step_w)]
    blocks.append(_abs("cooldown", RAMP_COOLDOWN_S, RAMP_COOLDOWN_W))
    return Workout("ftp_test:ramp", NAMES["ramp"], tuple(blocks),
                   f"Paliers de {step_s} s, +{step_w} W, à partir de {start_w} W, jusqu'à ne plus tenir.")


def kind_of(workout_id: str | None) -> str | None:
    """`ramp` pour un identifiant `ftp_test:…`, None pour un autre entraînement."""
    if workout_id and workout_id.startswith(ID_PREFIX) and workout_id[len(ID_PREFIX):] in KINDS:
        return workout_id[len(ID_PREFIX):]
    return None


def _check_kind(kind: str) -> None:
    if kind not in KINDS:
        raise FtpTestError(f"test de FTP inconnu : « {kind} » (attendu {', '.join(KINDS)})")


def workout_for(kind: str, ftp_w: float) -> Workout:
    """Entraînement roulé par la séance de test."""
    _check_kind(kind)
    del ftp_w   # paliers en watts absolus : la FTP ne change pas la rampe
    return ramp_workout()


def planned_workout(kind: str, ftp_w: float) -> Workout:
    """Séance attendue, pour la durée et le TSS d'un plan (lot O11) : la rampe s'arrête au palier
    où la meilleure minute vaut FTP / 0,75, puis retour au calme."""
    full = workout_for(kind, ftp_w)
    last_w = ftp_w / RAMP_FACTOR
    steps = [b for b in full.blocks if b.type == "steady" and b.start_w is not None and b.start_w <= last_w]
    return Workout(full.id, full.name, (full.blocks[0], *steps, full.blocks[-1]), full.description)


def planned_duration_s(kind: str, ftp_w: float = DEFAULT_PLAN_FTP_W) -> float:
    return planned_workout(kind, ftp_w).duration_s


def effort_blocks(workout: Workout) -> set[int]:
    """Numéros de blocs (à partir de 1, comme `block` du journal) des paliers de la rampe."""
    return {i + 1 for i, b in enumerate(workout.blocks) if b.type == "steady"}


def cooldown_index(workout: Workout) -> int:
    return len(workout.blocks) - 1


# --- fin de la rampe -----------------------------------------------------------------------

class RampWatch:
    """Détecte la fin de la rampe pendant les paliers ; renvoie la raison une seule fois."""

    def __init__(self, workout: Workout) -> None:
        self.steps = {i - 1 for i in effort_blocks(workout)}   # index des paliers (à partir de 0)
        self.cooldown = cooldown_index(workout)
        self._low_cadence_s = 0.0
        self._low_power_s = 0.0
        self.reason: str | None = None

    def active(self, erg: ErgController) -> bool:
        return self.reason is None and not erg.finished and erg.index in self.steps

    def update(self, dt: float, power_w: float, cadence_rpm: float, erg: ErgController) -> str | None:
        if not self.active(erg) or erg.paused:
            return None
        self._low_cadence_s = self._low_cadence_s + dt if cadence_rpm < LOW_CADENCE_RPM else 0.0
        target = erg.target_w
        self._low_power_s = self._low_power_s + dt if target and power_w < LOW_POWER_FRAC * target else 0.0
        if self._low_cadence_s >= LOW_CADENCE_S:
            self.reason = "cadence"
        elif self._low_power_s >= LOW_POWER_S:
            self.reason = "power"
        return self.reason

    def abandon(self, erg: ErgController) -> bool:
        """Geste de saut de bloc pendant les paliers : abandon du test (vrai si la rampe s'arrête)."""
        if not self.active(erg):
            return False
        self.reason = "abandon"
        return True


# --- résultat --------------------------------------------------------------------------------

@dataclass(frozen=True)
class FtpResult:
    kind: str
    ftp_w: int | None                  # FTP proposée, None si l'effort ne permet aucun calcul
    method: str
    ref_power_w: int | None            # meilleure minute
    held_s: int                        # secondes d'effort (paliers de la rampe)
    step_w: int | None = None          # dernier palier atteint
    warnings: tuple[str, ...] = ()
    previous_ftp_w: int | None = None  # FTP de la séance
    ts: float | None = None

    @property
    def reliable(self) -> bool:
        return self.ftp_w is not None and not any(w in BLOCKING for w in self.warnings)

    def to_line(self) -> dict[str, Any]:
        """Ligne `ftp_test` du journal."""
        return {"kind": "ftp_test", "ts": self.ts, "test": self.kind, "ftp_w": self.ftp_w,
                "method": self.method, "ref_power_w": self.ref_power_w, "held_s": self.held_s,
                "step_w": self.step_w, "warnings": list(self.warnings),
                "previous_ftp_w": self.previous_ftp_w}

    @classmethod
    def from_line(cls, line: dict[str, Any]) -> "FtpResult":
        kind = str(line.get("test"))
        _check_kind(kind)
        return cls(kind, _int(line.get("ftp_w")), str(line.get("method") or METHODS[kind]),
                   _int(line.get("ref_power_w")), int(line.get("held_s") or 0), _int(line.get("step_w")),
                   tuple(str(w) for w in line.get("warnings") or ()), _int(line.get("previous_ftp_w")),
                   line.get("ts"))

    def describe(self) -> str:
        if self.ftp_w is None:
            text = "Test de FTP (rampe) : aucune FTP calculable"
        else:
            step = f", dernier palier {self.step_w} W" if self.step_w else ""
            text = (f"Test de FTP (rampe) : FTP proposée {self.ftp_w} W ({self.method}, "
                    f"{self.ref_power_w} W{step}, effort {_mmss(self.held_s)})")
        if self.warnings:
            text += " ; avertissements : " + ", ".join(WARNINGS.get(w, w) for w in self.warnings)
        return text


def _int(v: Any) -> int | None:
    return None if v is None else int(round(float(v)))


def _mmss(seconds: float) -> str:
    m, s = divmod(int(round(seconds)), 60)
    return f"{m}:{s:02d}"


def _best_mean(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    acc = sum(values[:window])
    best = acc
    for i in range(window, len(values)):
        acc += values[i] - values[i - window]
        best = max(best, acc)
    return best / window


def _within(lines: Iterable[dict], start: float, end: float) -> list[dict]:
    return [ln for ln in lines if ln.get("ts") is not None and start <= float(ln["ts"]) <= end]


def estimate_ftp(records: list[dict], kind: str, events: Iterable[dict] = (), devices: Iterable[dict] = (),
                 previous_ftp_w: float | None = None, workout: Workout | None = None,
                 ts: float | None = None) -> FtpResult:
    """FTP proposée d'après les relevés à 1 Hz du journal (`block` = numéro du bloc de l'entraînement)."""
    _check_kind(kind)
    workout = workout or workout_for(kind, previous_ftp_w or DEFAULT_PLAN_FTP_W)
    blocks = effort_blocks(workout)
    effort = [r for r in records if r.get("block") in blocks]
    previous = _int(previous_ftp_w)
    if not effort:
        return FtpResult(kind, None, METHODS[kind], None, 0, warnings=("too_short",),
                         previous_ftp_w=previous, ts=ts)
    powers = [max(0.0, float(r["power"])) if r.get("power") is not None else 0.0 for r in effort]
    held_s = len(effort)
    warnings: list[str] = []
    ref = _best_mean(powers, 60)
    last = workout.blocks[max(int(r["block"]) for r in effort) - 1]
    step_w = _int(last.start_w)
    cad_records = effort[:-RAMP_FAILURE_TAIL_S] if len(effort) > RAMP_FAILURE_TAIL_S else effort
    if held_s < MIN_RAMP_STEPS_S or ref is None:
        warnings.append("too_short")
    cads = [float(r["cadence"]) for r in cad_records if r.get("cadence")]
    if len(cads) >= 2 and statistics.pstdev(cads) > CADENCE_STDEV_RPM:
        warnings.append("erratic_cadence")
    start, end = float(effort[0]["ts"]), float(effort[-1]["ts"])
    if any(d.get("device") == "trainer" and d.get("state") == "down" for d in _within(devices, start, end)):
        warnings.append("trainer_dropout")
    if any(e.get("event") == "pause" for e in _within(events, start, end)):
        warnings.append("paused")
    ftp = None if ref is None else round(RAMP_FACTOR * ref)
    return FtpResult(kind, ftp, METHODS[kind], _int(ref), held_s, step_w, tuple(warnings), previous, ts)


# --- journaux --------------------------------------------------------------------------------

def read_result(path: Path) -> FtpResult | None:
    """Dernier résultat `ftp_test` d'un journal, None s'il n'y en a pas."""
    from .journal import read_journal

    found = None
    for line in read_journal(path):
        if isinstance(line, dict) and line.get("kind") == "ftp_test":
            try:
                found = FtpResult.from_line(line)
            except (FtpTestError, TypeError, ValueError):
                continue
    return found


def find_results(journal_dir: Path) -> list[tuple[Path, FtpResult]]:
    """Tests trouvés dans les journaux, du plus ancien au plus récent (noms horodatés)."""
    out = []
    for path in sorted(journal_dir.glob("*.jsonl")):
        result = read_result(path)
        if result is not None:
            out.append((path, result))
    return out


def _date(ts: float | None) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)) if ts else "date inconnue"


def run(file: Path | None, accept: bool, force: bool, history: bool, as_json: bool = False,
        config_path: Path | None = None, journal_dir: Path | None = None) -> int:
    """`openride-core ftp-test [FICHIER] [--accept [--force]] [--history] [--json]`."""
    from . import config as config_mod
    from . import config_edit
    from . import profiles

    journal_dir = profiles.current().journal_dir if journal_dir is None else journal_dir
    if history:
        found = find_results(journal_dir)
        if as_json:
            print(json.dumps([{"file": str(p), **r.to_line()} for p, r in found], ensure_ascii=False, indent=2))
            return 0
        if not found:
            print("Aucun test de FTP trouvé.")
            return 0
        for _, r in found:
            ftp = f"{r.ftp_w} W" if r.ftp_w is not None else "—"
            note = f"  ({', '.join(WARNINGS.get(w, w) for w in r.warnings)})" if r.warnings else ""
            print(f"{_date(r.ts)}  rampe  FTP {ftp:>6}{note}")
        return 0

    if file is not None:
        result = read_result(file) if file.is_file() else None
        if result is None:
            print(f"openride-core ftp-test : aucun test de FTP dans {file}")
            return 1
    else:
        found = find_results(journal_dir)
        if not found:
            print("openride-core ftp-test : aucun test de FTP trouvé dans les journaux.")
            return 1
        file, result = found[-1]
    try:
        cfg = config_mod.load(config_path)
    except config_mod.ConfigError as exc:
        print(f"openride-core ftp-test : configuration invalide : {exc}")
        return 1
    current = round(cfg.rider.ftp_w)
    if as_json and not accept:
        print(json.dumps({"file": str(file), "current_ftp_w": current, **result.to_line()},
                         ensure_ascii=False, indent=2))
        return 0
    print(f"{result.describe()}  [{_date(result.ts)}]")
    if result.ftp_w is not None:
        delta = result.ftp_w - current
        print(f"FTP actuelle {current} W, nouvelle {result.ftp_w} W, écart {delta:+d} W ({delta / current * 100:+.1f} %)")
    if not accept:
        return 0
    if result.ftp_w is None:
        print("openride-core ftp-test : aucune FTP à enregistrer.")
        return 1
    if not result.reliable and not force:
        print("openride-core ftp-test : résultat douteux, rien n'est écrit (utiliser --force pour l'enregistrer quand même).")
        return 1
    path = config_path or config_mod.DEFAULT_CONFIG_PATH
    try:
        changed = config_edit.update_config(path, [("rider", "ftp_w", result.ftp_w)])
    except config_edit.ConfigEditError as exc:
        print(f"openride-core ftp-test : {exc}")
        return 1
    print(f"FTP enregistrée dans {path} : {result.ftp_w} W" if changed else "FTP inchangée.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m openride_core.ftp_test", description="Résultat des tests de FTP (rampe).")
    p.add_argument("file", nargs="?", type=Path)
    p.add_argument("--accept", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--history", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--config", type=Path)
    a = p.parse_args(argv)
    return run(a.file, a.accept, a.force, a.history, a.json, a.config)


if __name__ == "__main__":
    raise SystemExit(main())
