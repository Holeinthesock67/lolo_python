"""Journal continu de séance (SRS §9).

Un fichier JSONL par séance, une ligne par seconde, vidée sur disque à chaque ligne : après
un plantage, `openride-core recover` peut transformer le dernier journal en FIT.

Deux sortes de lignes :
- `{"kind": "record", "ts": ..., ...}`  échantillon à 1 Hz ;
- `{"kind": "event", "ts": ..., "event": "start" | "pause" | "resume" | "stop"}`.
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

EVENTS = ("start", "pause", "resume", "stop")


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
    block: int | None = None     # bloc d'entraînement ERG (à partir de 1)


class JournalWriter:
    def __init__(self, path: Path, route_id: str | None = None) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._fh: IO[str] = path.open("a", encoding="utf-8")
        self._last_sync = 0.0
        self._write({"kind": "header", "version": 1, "route_id": route_id})

    def _write(self, obj: dict) -> None:
        self._fh.write(json.dumps(obj, separators=(",", ":")) + "\n")
        self._fh.flush()   # survit à un plantage du programme
        now = time.monotonic()
        if now - self._last_sync >= FSYNC_EVERY_S:   # survit aussi à une coupure de courant (à 5 s près)
            os.fsync(self._fh.fileno())
            self._last_sync = now

    def record(self, rec: Record) -> None:
        self._write({"kind": "record", **asdict(rec)})

    def event(self, name: str, ts: float) -> None:
        if name not in EVENTS:
            raise ValueError(f"événement inconnu : {name}")
        self._write({"kind": "event", "event": name, "ts": ts})

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
