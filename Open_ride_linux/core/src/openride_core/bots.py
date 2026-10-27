"""Bots virtuels pour OpenRide (Lot N9).

- ConstantPowerBot : puissance constante, même modèle physique que le cycliste.
- GhostBot : rejeu de la position d'une séance passée (.fit ou .jsonl).
"""

from __future__ import annotations

import bisect
from dataclasses import replace
from datetime import datetime
import math
from pathlib import Path
from typing import Any

from .physics import PhysicsParams, RiderPhysics
from .route import Route
from .tools.session_summary import Session, load_session, running_records


class BotError(Exception):
    """Erreur liée à la création ou à l'exécution d'un bot."""


class ConstantPowerBot:
    """Bot avançant à puissance constante selon le modèle physique d'OpenRide."""

    def __init__(
        self,
        power_w: float,
        bot_id: str = "bot1",
        name: str | None = None,
        params: PhysicsParams | None = None,
        mass_kg: float | None = None,
        s: float = 0.0,
        v: float = 0.0,
    ) -> None:
        if not math.isfinite(power_w) or power_w <= 0:
            raise BotError(f"puissance de bot invalide : {power_w}")
        self.id = str(bot_id)[:8]
        self.power_w = float(power_w)
        default_name = f"Bot {int(round(self.power_w))} W"
        self.name = str(name if name is not None else default_name)[:16]
        self.kind = "constant"

        p = params or PhysicsParams()
        if mass_kg is not None:
            if mass_kg <= 0 or not math.isfinite(mass_kg):
                raise BotError(f"masse invalide : {mass_kg}")
            p = replace(p, mass_kg=float(mass_kg))
        self.params = replace(p)   # copie propre au bot : son vent de face lui est propre (lot P2)
        self.physics = RiderPhysics(self.params, s=s, v=v)
        self.t = 0.0

    @property
    def s(self) -> float:
        return self.physics.s

    @property
    def v(self) -> float:
        return self.physics.v

    def step(self, dt: float, route: Route | None = None) -> None:
        """Avance la physique du bot d'un pas dt."""
        if dt < 0:
            return
        s = self.physics.s
        grade = 0.0
        alt = 0.0
        if route is not None:
            if not route.is_loop and s >= route.length_m:
                self.physics.s = route.length_m
                self.physics.v = 0.0
                self.t += dt
                return
            here = route.sample(s)
            grade = here.grade_pct
            alt = here.alt_m

        self.physics.step(self.power_w, grade, alt, dt)
        if route is not None and not route.is_loop and self.physics.s >= route.length_m:
            self.physics.s = route.length_m
            self.physics.v = 0.0
        self.t += dt

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "s": round(self.physics.s, 2),
            "v": round(self.physics.v, 3),
            "kind": self.kind,
        }


class GhostBot:
    """Fantôme rejouant la position d'une séance passée (.fit ou .jsonl)."""

    def __init__(
        self,
        path: Path | str,
        bot_id: str = "ghost",
        name: str | None = None,
    ) -> None:
        path = Path(path)
        self.id = str(bot_id)[:8]
        self.kind = "ghost"
        self.path = path

        try:
            session = load_session(path)
        except Exception as exc:
            raise BotError(f"impossible de charger la séance fantôme ({path}) : {exc}") from exc

        self.times, self.distances, self.speeds, start_ts = self._extract_series(session, path)

        if name is not None:
            self.name = str(name)[:16]
        else:
            dt = datetime.fromtimestamp(start_ts)
            self.name = f"Fantôme du {dt.strftime('%d/%m')}"[:16]

        self.t = 0.0
        self.s = self.distances[0]
        self.v = self.speeds[0] if self.speeds else 0.0

    @staticmethod
    def _extract_series(
        session: Session, path: Path
    ) -> tuple[list[float], list[float], list[float], float]:
        recs = running_records(session.records, session.events)
        recs_with_dist = [r for r in recs if r.get("distance") is not None]
        if not recs_with_dist:
            raise BotError(f"séance sans relevé de distance ({path})")

        start_ts = session.records[0]["ts"] if session.records else 0.0

        # Calcul du temps chronométré cumulé sans les pauses
        active_intervals: list[tuple[float, float]] = []
        t_start: float | None = None
        for ev in sorted(session.events, key=lambda e: e["ts"]):
            if ev["event"] in ("start", "resume") and t_start is None:
                t_start = ev["ts"]
            elif ev["event"] in ("pause", "stop") and t_start is not None:
                active_intervals.append((t_start, ev["ts"]))
                t_start = None
        if t_start is not None and recs_with_dist:
            active_intervals.append((t_start, recs_with_dist[-1]["ts"]))

        def calc_t(ts: float) -> float:
            if not active_intervals:
                return max(0.0, ts - start_ts)
            acc = 0.0
            for a, b in active_intervals:
                if ts <= a:
                    break
                elif ts < b:
                    acc += ts - a
                    break
                else:
                    acc += b - a
            return acc

        times: list[float] = []
        distances: list[float] = []
        speeds: list[float] = []

        for r in recs_with_dist:
            t_val = calc_t(r["ts"])
            times.append(t_val)
            distances.append(float(r["distance"]))
            spd = r.get("speed")
            speeds.append(float(spd) if spd is not None else 0.0)

        # Assure des temps strictement croissants ou non décroissants
        if times and times[0] > 0.0:
            t0 = times[0]
            times = [t - t0 for t in times]

        return times, distances, speeds, start_ts

    def step(self, dt: float, route: Route | None = None) -> None:
        """Avance le temps du fantôme et interpole sa position."""
        if dt < 0:
            return
        self.t += dt
        if not self.times:
            return

        if self.t >= self.times[-1]:
            self.s = self.distances[-1]
            self.v = 0.0
            return

        if self.t <= self.times[0]:
            self.s = self.distances[0]
            self.v = self.speeds[0] if self.speeds else 0.0
            return

        idx = bisect.bisect_right(self.times, self.t) - 1
        t0, t1 = self.times[idx], self.times[idx + 1]
        s0, s1 = self.distances[idx], self.distances[idx + 1]
        dt_span = t1 - t0
        if dt_span > 0:
            u = (self.t - t0) / dt_span
            self.s = (1.0 - u) * s0 + u * s1
            self.v = (s1 - s0) / dt_span
        else:
            self.s = s0
            self.v = self.speeds[idx] if self.speeds else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "s": round(self.s, 2),
            "v": round(self.v, 3),
            "kind": self.kind,
        }


# --- bots choisis au menu (lot O7, contrat IPC révision 1.3) --------------------------------------

MAX_CONSTANT_BOTS = 4


def last_ride(route_id: str | None, directory: Path) -> Path | None:
    """Journal le plus récent d'une séance sur ce parcours, d'où un fantôme peut partir ; None sinon."""
    from .journal import read_journal

    if not route_id or not directory.is_dir():
        return None
    for path in sorted(directory.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            header = next((line for line in read_journal(path) if isinstance(line, dict)), {})
        except Exception:
            continue
        if header.get("kind") == "header" and header.get("route_id") == route_id:
            try:
                GhostBot(path)
            except BotError:
                continue   # séance sans distance : on remonte à la précédente
            return path
    return None


def bots_from_menu(items: Any, params: PhysicsParams, ftp_w: float, route_id: str | None,
                   journal_dir: Path, s: float = 0.0) -> list[Any]:
    """Bots de l'argument `bots` de `start` : `{kind: "constant", power_w}` ou `{kind: "constant",
    ftp_pct}` (au plus 4) et `{kind: "ghost"}` (dernière séance sur ce parcours, un seul).

    Lève BotError (rien ne démarre) si la liste est mal écrite ou si le fantôme n'a pas de séance.
    """
    if not isinstance(items, list) or len(items) > MAX_CONSTANT_BOTS + 1:
        raise BotError(f"liste de {MAX_CONSTANT_BOTS + 1} bots au plus attendue")
    out: list[Any] = []
    constant = 0
    ghost = False
    for it in items:
        kind = it.get("kind") if isinstance(it, dict) else None
        if kind == "constant":
            w, pct = it.get("power_w"), it.get("ftp_pct")
            value = w if pct is None else pct
            if (w is None) == (pct is None) or isinstance(value, bool) or not isinstance(value, (int, float)):
                raise BotError("bot à puissance constante : power_w ou ftp_pct attendu")
            constant += 1
            if constant > MAX_CONSTANT_BOTS:
                raise BotError(f"au plus {MAX_CONSTANT_BOTS} bots à puissance constante")
            power = float(w) if w is not None else ftp_w * float(pct) / 100.0
            name = f"Bot {pct:g} % FTP" if pct is not None else None
            out.append(ConstantPowerBot(power, bot_id=f"bot{constant}", name=name, params=params, s=s))
        elif kind == "ghost":
            if ghost:
                raise BotError("un seul fantôme")
            ghost = True
            path = last_ride(route_id, journal_dir)
            if path is None:
                raise BotError(f"aucune séance passée sur le parcours « {route_id} » pour le fantôme")
            out.append(GhostBot(path))
        else:
            raise BotError(f"genre de bot inconnu : {kind!r} (constant ou ghost)")
    return out
