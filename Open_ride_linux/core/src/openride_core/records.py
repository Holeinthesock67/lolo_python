"""Records personnels par segment et classement local du passage (lot T5, série T).

Module pur, sans branchement dans la séance (il vient avec le contrat T1). Cahier :
`docs/lots/LOT_T5_records_classement.md`.

Règles (plan de la série T §3.2, décisions T-Q1 et du 27 octobre) :
- un fichier `~/OpenRide/records.json`, par parcours et par segment, garde les 10 meilleurs
  temps avec leur date ;
- les records « avec bonus » et « sans bonus » sont tenus séparément ;
- le fichier se recalcule depuis les journaux des séances (`RecordBook.rebuild`) ;
- classement local d'un passage : toi, tes records passés de la même table et les bots ; le
  fantôme compte comme ton meilleur temps, pas comme un coureur de plus ;
- écart au record en direct : chrono moins le record au prorata de la distance parcourue.

Forme du fichier (version 1) :

    {"version": 1, "routes": {"<route_id>": {"<segment_id>": {
        "no_bonus": [{"time_s": 312.4, "date": "2026-10-27 18:05", "avg_power_w": 251.0,
                      "avg_wkg": 3.4}],
        "bonus": []}}}}
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .config import OPENRIDE_HOME
from .journal import read_journal
from .segment_timing import SegmentLike, SegmentPass, passes_from_journal

RECORDS_FILE = OPENRIDE_HOME / "records.json"
FORMAT_VERSION = 1
TOP_N = 10
TABLES = ("no_bonus", "bonus")
DATE_FORMAT = "%Y-%m-%d %H:%M"


class RecordsError(ValueError):
    """Fichier de records illisible ou d'une forme inconnue."""


def table_of(with_bonus: bool) -> str:
    return "bonus" if with_bonus else "no_bonus"


@dataclass(frozen=True)
class RecordEntry:
    time_s: float
    date: str                    # « AAAA-MM-JJ HH:MM », heure locale du passage
    avg_power_w: float | None = None
    avg_wkg: float | None = None

    def to_dict(self) -> dict:
        return {"time_s": round(self.time_s, 2), "date": self.date,
                "avg_power_w": None if self.avg_power_w is None else round(self.avg_power_w, 1),
                "avg_wkg": None if self.avg_wkg is None else round(self.avg_wkg, 2)}

    @classmethod
    def from_dict(cls, d: dict) -> "RecordEntry":
        try:
            time_s = float(d["time_s"])
            date = str(d["date"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RecordsError(f"record incomplet : {d!r}") from exc
        if not math.isfinite(time_s) or time_s <= 0:
            raise RecordsError(f"temps de record invalide : {time_s}")
        p, w = d.get("avg_power_w"), d.get("avg_wkg")
        return cls(time_s, date, None if p is None else float(p), None if w is None else float(w))


@dataclass(frozen=True)
class AddResult:
    rank: int | None             # place dans la table (1 = record), None hors des 10 meilleurs
    is_record: bool
    previous_best_s: float | None
    gap_s: float | None          # temps − ancien record (négatif = record battu)


@dataclass(frozen=True)
class RankEntry:
    kind: str                    # "you", "record" ou "bot"
    id: str                      # "you", la date du record ou l'identifiant du bot
    time_s: float


@dataclass
class RecordBook:
    routes: dict[str, dict[str, dict[str, list[RecordEntry]]]] = field(default_factory=dict)

    # --- fichier -------------------------------------------------------------------------

    @classmethod
    def load(cls, path: Path | None = None) -> "RecordBook":
        """Lit le fichier de records ; un fichier absent donne un carnet vide."""
        path = path or RECORDS_FILE
        if not path.is_file():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RecordsError(f"{path} illisible : {exc}") from exc
        if not isinstance(data, dict) or data.get("version") != FORMAT_VERSION:
            raise RecordsError(f"{path.name} : version {data.get('version') if isinstance(data, dict) else '?'} inconnue")
        book = cls()
        routes = data.get("routes", {})
        if not isinstance(routes, dict):
            raise RecordsError(f"{path.name} : « routes » doit être un objet")
        for route_id, segs in routes.items():
            if not isinstance(segs, dict):
                raise RecordsError(f"{path.name} : parcours {route_id} mal formé")
            for seg_id, tables in segs.items():
                if not isinstance(tables, dict) or set(tables) - set(TABLES):
                    raise RecordsError(f"{path.name} : segment {seg_id} mal formé")
                for table in TABLES:
                    for d in tables.get(table, []):
                        book._insert(route_id, seg_id, table, RecordEntry.from_dict(d))
        return book

    def save(self, path: Path | None = None) -> None:
        """Écrit le fichier d'un coup (fichier temporaire puis remplacement)."""
        path = path or RECORDS_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"version": FORMAT_VERSION, "routes": {
            r: {s: {t: [e.to_dict() for e in tables.get(t, [])] for t in TABLES}
                for s, tables in sorted(segs.items())}
            for r, segs in sorted(self.routes.items())}}
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        os.replace(tmp, path)

    # --- lecture et ajout ----------------------------------------------------------------

    def table(self, route_id: str, segment_id: str, with_bonus: bool) -> list[RecordEntry]:
        return list(self.routes.get(route_id, {}).get(segment_id, {}).get(table_of(with_bonus), []))

    def best(self, route_id: str, segment_id: str, with_bonus: bool) -> RecordEntry | None:
        entries = self.table(route_id, segment_id, with_bonus)
        return entries[0] if entries else None

    def _insert(self, route_id: str, segment_id: str, table: str, entry: RecordEntry) -> int | None:
        entries = self.routes.setdefault(route_id, {}).setdefault(segment_id, {}).setdefault(table, [])
        if any(e.date == entry.date and abs(e.time_s - entry.time_s) < 0.005 for e in entries):
            return None          # même passage déjà noté (rejeu d'un journal déjà lu)
        entries.append(entry)
        entries.sort(key=lambda e: (e.time_s, e.date))
        del entries[TOP_N:]
        return entries.index(entry) + 1 if entry in entries else None

    def add(self, route_id: str, segment_id: str, p: SegmentPass, date: str) -> AddResult:
        """Note un passage terminé dans la table qui lui correspond (avec ou sans bonus)."""
        table = table_of(p.with_bonus)
        prev = self.best(route_id, segment_id, p.with_bonus)
        rank = self._insert(route_id, segment_id, table,
                            RecordEntry(p.time_s, date, p.avg_power_w, p.avg_wkg))
        prev_s = prev.time_s if prev else None
        return AddResult(rank, rank == 1, prev_s, None if prev_s is None else p.time_s - prev_s)

    # --- en direct et classement ---------------------------------------------------------

    def live_gap(self, route_id: str, segment_id: str, with_bonus: bool, elapsed_s: float,
                 fraction: float) -> float | None:
        """Écart au record pendant le passage (négatif = en avance), au prorata de la distance."""
        best = self.best(route_id, segment_id, with_bonus)
        if best is None:
            return None
        return elapsed_s - best.time_s * min(max(fraction, 0.0), 1.0)

    def ranking(self, route_id: str, segment_id: str, p: SegmentPass,
                bots: dict[str, float] | None = None) -> list[RankEntry]:
        """Classement local du passage `p` : toi, tes records de la même table, les bots.

        À appeler avant `add`, pour que le passage ne figure pas deux fois. Le fantôme n'est
        pas un coureur de plus : ton meilleur temps le représente.
        """
        rows = [RankEntry("you", "you", p.time_s)]
        rows += [RankEntry("record", e.date, e.time_s)
                 for e in self.table(route_id, segment_id, p.with_bonus)]
        rows += [RankEntry("bot", bid, float(t)) for bid, t in (bots or {}).items()]
        order = {"you": 0, "record": 1, "bot": 2}
        return sorted(rows, key=lambda r: (r.time_s, order[r.kind]))

    # --- recalcul depuis les journaux ----------------------------------------------------

    @classmethod
    def rebuild(cls, route_id: str, journals: Iterable[Path], segments: list[SegmentLike],
                length_m: float, loop: bool = False,
                rider_mass_kg: float | None = None) -> "RecordBook":
        """Carnet d'un parcours recalculé depuis des journaux `.jsonl` (les autres sont ignorés)."""
        book = cls()
        for path in journals:
            head, date = _journal_route_and_date(path)
            if head != route_id or date is None:
                continue
            for p in passes_from_journal(path, segments, length_m, loop, rider_mass_kg):
                book.add(route_id, p.segment_id, p, date)
        return book

    def merge(self, other: "RecordBook") -> None:
        """Ajoute les records d'un autre carnet (par exemple un parcours recalculé)."""
        for r, segs in other.routes.items():
            for s, tables in segs.items():
                for t, entries in tables.items():
                    for e in entries:
                        self._insert(r, s, t, e)


def _journal_route_and_date(path: Path) -> tuple[str | None, str | None]:
    """Parcours de l'en-tête et date du premier relevé (heure locale)."""
    route_id = None
    for line in read_journal(path):
        kind = line.get("kind")
        if kind == "header":
            route_id = line.get("route_id")
        elif kind == "record":
            try:
                return route_id, datetime.fromtimestamp(float(line["ts"])).strftime(DATE_FORMAT)
            except (KeyError, TypeError, ValueError, OverflowError, OSError):
                return route_id, None
    return route_id, None
