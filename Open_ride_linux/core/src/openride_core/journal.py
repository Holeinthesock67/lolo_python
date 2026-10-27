"""Journal continu de séance (SRS §9).

Un fichier JSONL par séance, une ligne par seconde, vidée sur disque à chaque ligne : après
un plantage, `openride-core recover` peut transformer le dernier journal en FIT.

Sortes de lignes :
- `{"kind": "header", "version": 1, "route_id": ..., "workout_id": ..., "source": ...}` en tête
  (`workout_id` : entraînement ERG choisi ou `null`, absent des journaux antérieurs au lot N8 ;
  `source` : `live` (trainer réel), `simulated` (trainer `mock` ou `sim`) ou `replay` (rejeu),
  absent des journaux antérieurs au lot V2, qui le lit pour la progression ; `ftp_w` facultatif :
  FTP de la séance, lue pour les pièces gagnées à l'effort, lot V3b, écrite à partir de V11) ;
  champ facultatif `plan` = `{"id": ..., "week": n, "day": "mardi"}` quand la séance réalise une
  séance d'un plan d'entraînement actif (lot O11), absent sinon ;
- `{"kind": "record", "ts": ..., ...}`  échantillon à 1 Hz ;
- `{"kind": "event", "ts": ..., "event": "start" | "pause" | "resume" | "stop"}` ;
- `{"kind": "event", "ts": ..., "event": "resume_after_crash"}` : le core relancé après un
  plantage reprend la séance dans le même fichier (lot N8) ; ce n'est pas un événement du
  chronomètre : les lectures du chronomètre et le FIT ne gardent que `TIMER_EVENTS` ;
- `{"kind": "device", "ts": ..., "device": "trainer" | "click_plus" | "click_minus" | "hr",
  "state": "up" | "down"}` au changement d'état d'un appareil (lot M4, absentes des journaux
  antérieurs au 24 octobre 2026). Les lectures qui ne connaissent pas cette sorte l'ignorent ;
- `{"kind": "ftp_test", "ts": ..., "test": "ramp" | "20min", "ftp_w": ..., "method": ...,
  "ref_power_w": ..., "held_s": ..., "step_w": ..., "warnings": [...], "previous_ftp_w": ...}`
  à la fin d'une séance de test de FTP, juste avant l'événement `stop` (lot O10, voir
  `ftp_test.py`) ; `ftp_w`, `ref_power_w` et `step_w` peuvent valoir `null`. Ligne facultative :
  les journaux sans test restent lus comme avant, et les lectures qui ne la connaissent pas l'ignorent.
`ts` est l'heure Unix (secondes, UTC).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import IO, Iterator

from .config import OPENRIDE_HOME

JOURNAL_DIR = OPENRIDE_HOME / "Activities" / ".journal"

FSYNC_EVERY_S = 5.0   # fsync bloque la boucle ~7 ms ; flush à chaque ligne protège déjà d'un plantage du programme

TIMER_EVENTS = ("start", "pause", "resume", "stop")
EVENTS = (*TIMER_EVENTS, "resume_after_crash")
DEVICES = ("trainer", "click_plus", "click_minus", "hr")
DEVICE_STATES = ("up", "down")


@dataclass
class Record:
    ts: float
    t: float                     # temps de séance chronométré (s)
    lat: float | None = None
    lon: float | None = None
    alt: float | None = None
    distance: float = 0.0        # m
    speed: float = 0.0           # m/s
    power: float | None = None   # W
    cadence: float | None = None # rpm
    hr: int | None = None        # bpm
    grade: float | None = None   # %
    mode: str = "SIM"
    gear: int | None = None
    grade_sent: float | None = None   # % envoyé au trainer en SIM (braquet, anticipation, lissage)
    difficulty_pct: int | None = None
    block: int | None = None     # bloc d'entraînement ERG (à partir de 1)
    target_w: float | None = None  # cible ERG envoyée au trainer (W), None en SIM / FreeRide / pause
    erg_bias_pct: float | None = None  # biais du Click appliqué à la cible (%, 0 sans appui), None hors ERG actif
    head_mps: float | None = None      # vent de face (m/s, positif de face), None vent coupé (lot P2)
    wind_grade_pct: float | None = None  # supplément de pente dû au vent et à l'abri (SIM), lots P2 et P3
    draft: float | None = None         # abri derrière un bot (0 à 0,45), None sans bot (lot P3)
    hr_frozen: bool | None = None      # True : FC relayée par le trainer figée, ignorée (lot Q5)


# Champs de la série P absents de la ligne quand ils valent None (vent coupé, pas de bot) :
# une séance sans vent ni bot garde exactement les lignes d'avant, et la mémoire de la séance aussi.
OPTIONAL_RECORD_KEYS = ("head_mps", "wind_grade_pct", "draft", "hr_frozen")


def record_line(rec: Record) -> dict:
    # Dictionnaire construit sans ces clés (un `del` ne réduirait pas sa table en mémoire).
    return {"kind": "record", **{k: v for k, v in asdict(rec).items()
                                 if v is not None or k not in OPTIONAL_RECORD_KEYS}}


class JournalWriter:
    def __init__(self, path: Path, route_id: str | None = None, workout_id: str | None = None,
                 header: bool = True, source: str | None = None, plan: dict | None = None) -> None:
        """Ouvre le journal en ajout ; `header=False` continue un journal existant (reprise, lot N8)."""
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._fh: IO[str] = path.open("a", encoding="utf-8")
        self._last_sync = 0.0
        if header:
            head = {"kind": "header", "version": 1, "route_id": route_id, "workout_id": workout_id}
            if source is not None:
                head["source"] = source
            if plan:
                head["plan"] = plan
            self._write(head)

    def _write(self, obj: dict) -> None:
        self._fh.write(json.dumps(obj, separators=(",", ":")) + "\n")
        self._fh.flush()   # survit à un plantage du programme
        now = time.monotonic()
        if now - self._last_sync >= FSYNC_EVERY_S:   # survit aussi à une coupure de courant (à 5 s près)
            os.fsync(self._fh.fileno())
            self._last_sync = now

    def record(self, rec: Record) -> None:
        self._write(record_line(rec))

    def event(self, name: str, ts: float) -> None:
        if name not in EVENTS:
            raise ValueError(f"événement inconnu : {name}")
        self._write({"kind": "event", "event": name, "ts": ts})

    def device(self, device: str, state: str, ts: float) -> None:
        """Changement d'état d'un appareil (coupure ou retour), lot M4."""
        if device not in DEVICES:
            raise ValueError(f"appareil inconnu : {device}")
        if state not in DEVICE_STATES:
            raise ValueError(f"état d'appareil inconnu : {state}")
        self._write({"kind": "device", "ts": ts, "device": device, "state": state})

    def ftp_test(self, line: dict) -> None:
        """Résultat d'un test de FTP (lot O10) : `FtpResult.to_line()`."""
        self._write({**line, "kind": "ftp_test"})

    def powerup(self, kind: str, t_start: float, duration_s: float, ts: float) -> None:
        """Bonus activé (série T, lot T5) : type, début en temps chronométré, durée."""
        self._write({"kind": "powerup", "ts": ts, "powerup": kind, "t": round(t_start, 2),
                     "duration_s": round(duration_s, 2)})

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.flush()
            os.fsync(self._fh.fileno())
            self._fh.close()

    def __enter__(self) -> "JournalWriter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def read_journal(path: Path) -> Iterator[dict]:
    """Relit un journal ; une dernière ligne tronquée (plantage en cours d'écriture) est ignorée."""
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def latest_journal(directory: Path = JOURNAL_DIR) -> Path | None:
    files = sorted(directory.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None
