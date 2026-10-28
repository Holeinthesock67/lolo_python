"""Bots virtuels pour OpenRide (Lot N9).

- ConstantPowerBot : puissance constante, même modèle physique que le cycliste.
- GhostBot : rejeu de la position d'une séance passée (.fit ou .jsonl).
- ProfileBot (lot T12) : profil physiologique (CP, W′, masse, pic sur 10 s) et stratégie par segment ;
  réserve W′bal du modèle de la série R (`rogue/wbal.py`), le même pour le joueur et les bots.
  `kind` reste `constant` (contrat 1.4 : `kind` vaut `constant` ou `ghost`) ; le champ `profile` le
  distingue. Cahier : `docs/lots/LOT_T12_bots_profil.md`.
"""

from __future__ import annotations

import bisect
from dataclasses import replace
from datetime import datetime
import math
from pathlib import Path
from typing import Any

from dataclasses import dataclass

from .physics import PhysicsParams, RiderPhysics
from .rogue.wbal import WbalState, wbal_initial, wbal_step
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


# --- bots à profil (lot T12, valeurs validées par le propriétaire le 27 octobre) -------------------

@dataclass(frozen=True)
class BotProfile:
    """Profil d'un bot : masse, CP en W/kg, W′, pic (W/kg sur `peak_s`, 0 sans pic) et fractions de CP
    de sa stratégie sur le plat (et en descente), en montée, en montée tant que la réserve dépasse
    `climb_reserve`, et au sprint (pic dans les `sprint_last_m` derniers mètres d'un sprint)."""

    name: str
    mass_kg: float
    cp_wkg: float
    w_prime_j: float
    flat: float
    climb: float
    climb_attack: float = 0.0      # fraction en montée tant que la réserve dépasse climb_reserve (0 : non)
    climb_reserve: float = 0.20
    peak_wkg: float = 0.0
    peak_s: float = 10.0
    sprint_last_m: float = 200.0


PROFILES: dict[str, BotProfile] = {
    "climber": BotProfile("Grimpeur", 60.0, 4.0, 15000.0, flat=0.92, climb=1.00, climb_attack=1.10),
    "rouleur": BotProfile("Rouleur", 72.0, 3.6, 20000.0, flat=1.00, climb=0.95),
    "sprinter": BotProfile("Sprinteur", 80.0, 3.3, 25000.0, flat=0.90, climb=0.88, peak_wkg=12.0),
    "diesel": BotProfile("Diesel", 75.0, 3.8, 10000.0, flat=1.00, climb=1.00),
}


DEFAULT_BIKE_MASS_KG = 8.0


class ProfileBot(ConstantPowerBot):
    """Bot à profil : même physique que ConstantPowerBot, puissance choisie à chaque pas par sa stratégie
    et limitée par sa réserve W′bal (au-dessus de la CP, ramenée à la CP quand la réserve est vide).

    `segments` : segments de la couche du parcours (montées et sprints, ceux de `classic.py`) ;
    sans segment, la règle « plat » partout. `scale` met CP, W′ et pic à l'échelle (lot T13). Masse
    physique : masse du profil (W/kg) plus `bike_mass_kg` (le vélo du cycliste, `config.toml`)."""

    def __init__(
        self,
        profile: str,
        bot_id: str = "bot1",
        name: str | None = None,
        params: PhysicsParams | None = None,
        segments: tuple = (),
        scale: float = 1.0,
        bike_mass_kg: float = DEFAULT_BIKE_MASS_KG,
        s: float = 0.0,
        v: float = 0.0,
    ) -> None:
        if profile not in PROFILES:
            raise BotError(f"profil de bot inconnu : {profile!r} ({', '.join(PROFILES)})")
        if not math.isfinite(scale) or scale <= 0:
            raise BotError(f"échelle de bot invalide : {scale}")
        self.profile = profile
        self.spec = PROFILES[profile]
        self.cp_w = self.spec.cp_wkg * self.spec.mass_kg * scale
        self.w_prime_j = self.spec.w_prime_j * scale
        self.peak_w = self.spec.peak_wkg * self.spec.mass_kg * scale
        super().__init__(self.cp_w, bot_id=bot_id, name=name if name is not None else self.spec.name,
                         params=params, mass_kg=self.spec.mass_kg + bike_mass_kg, s=s, v=v)
        self.mass_kg = self.spec.mass_kg
        self.segments = tuple(segments)
        self.wbal: WbalState = wbal_initial(self.w_prime_j)
        self._peak_key: tuple | None = None    # sprint (id, tour) dont le pic est entamé
        self._peak_used_s = 0.0

    @property
    def wbal_pct(self) -> float:
        return 100.0 * self.wbal.w_bal_j / self.w_prime_j

    def _segment_here(self, s: float, length_m: float, is_loop: bool) -> tuple[Any, int] | None:
        pos, lap = s, 0
        if is_loop and length_m > 0:
            lap, pos = int(s // length_m), s % length_m
        for seg in self.segments:
            if seg.s_start <= pos < seg.s_end:
                return seg, lap
        return None

    def target_power(self, s: float, length_m: float = 0.0, is_loop: bool = False) -> float:
        """Puissance demandée par la stratégie à la position s, avant la limite de la réserve."""
        spec = self.spec
        here = self._segment_here(s, length_m, is_loop)
        if here is None:
            return spec.flat * self.cp_w
        seg, lap = here
        if seg.type == "climb":
            attack = spec.climb_attack > 0 and self.wbal_pct > 100.0 * spec.climb_reserve
            return (spec.climb_attack if attack else spec.climb) * self.cp_w
        pos = s % length_m if is_loop and length_m > 0 else s
        if self.peak_w > 0 and seg.s_end - pos <= spec.sprint_last_m:
            key = (seg.id, lap)
            if key != self._peak_key:
                self._peak_key, self._peak_used_s = key, 0.0
            if self._peak_used_s < spec.peak_s - 1e-9:   # 10 s pile, malgré les arrondis des pas
                return self.peak_w
        return spec.flat * self.cp_w

    def step(self, dt: float, route: Route | None = None) -> None:
        if dt < 0:
            return
        length = route.length_m if route is not None else 0.0
        loop = route.is_loop if route is not None else False
        power = self.target_power(self.physics.s, length, loop)
        if power > self.cp_w and self.wbal.w_bal_j <= 0.0:
            power = self.cp_w
        if power == self.peak_w and self.peak_w > 0:
            self._peak_used_s += dt
        self.power_w = power
        super().step(dt, route)
        self.wbal = wbal_step(self.wbal, power, 0.0, dt, cp_w=self.cp_w, w_prime_j=self.w_prime_j)

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d.update({"profile": self.profile, "cp_w": round(self.cp_w, 1), "mass_kg": self.mass_kg,
                  "wbal_pct": round(self.wbal_pct, 1)})
        return d


def profile_bot_names(profiles: list[str]) -> list[str]:
    """Noms affichés : « Grimpeur », puis « Grimpeur 2 » pour un deuxième du même profil."""
    seen: dict[str, int] = {}
    out = []
    for p in profiles:
        seen[p] = seen.get(p, 0) + 1
        base = PROFILES[p].name if p in PROFILES else p
        out.append(base if seen[p] == 1 else f"{base} {seen[p]}")
    return out


def attach_segments(bots: list[Any], segments: tuple) -> None:
    """Segments du parcours donnés aux bots à profil au départ de la séance."""
    for b in bots:
        if isinstance(b, ProfileBot):
            b.segments = tuple(segments)


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
                   journal_dir: Path, s: float = 0.0, bike_mass_kg: float = DEFAULT_BIKE_MASS_KG) -> list[Any]:
    """Bots de l'argument `bots` de `start` : `{kind: "constant", power_w}` ou `{kind: "constant",
    ftp_pct}`, `{kind: "profile", profile}` (lot T12 ; au plus 4 bots de ces deux genres en tout) et
    `{kind: "ghost"}` (dernière séance sur ce parcours, un seul).

    Lève BotError (rien ne démarre) si la liste est mal écrite ou si le fantôme n'a pas de séance.
    """
    if not isinstance(items, list) or len(items) > MAX_CONSTANT_BOTS + 1:
        raise BotError(f"liste de {MAX_CONSTANT_BOTS + 1} bots au plus attendue")
    out: list[Any] = []
    constant = 0
    ghost = False
    profiles = [it.get("profile") for it in items if isinstance(it, dict) and it.get("kind") == "profile"]
    names = iter(profile_bot_names([p for p in profiles if isinstance(p, str)]))
    for it in items:
        kind = it.get("kind") if isinstance(it, dict) else None
        if kind == "constant":
            w, pct = it.get("power_w"), it.get("ftp_pct")
            value = w if pct is None else pct
            if (w is None) == (pct is None) or isinstance(value, bool) or not isinstance(value, (int, float)):
                raise BotError("bot à puissance constante : power_w ou ftp_pct attendu")
            constant += 1
            if constant > MAX_CONSTANT_BOTS:
                raise BotError(f"au plus {MAX_CONSTANT_BOTS} bots à puissance constante ou à profil")
            power = float(w) if w is not None else ftp_w * float(pct) / 100.0
            name = f"Bot {pct:g} % FTP" if pct is not None else None
            out.append(ConstantPowerBot(power, bot_id=f"bot{constant}", name=name, params=params, s=s))
        elif kind == "profile":
            profile = it.get("profile")
            if not isinstance(profile, str) or profile not in PROFILES:
                raise BotError(f"profil de bot inconnu : {profile!r} ({', '.join(PROFILES)})")
            constant += 1
            if constant > MAX_CONSTANT_BOTS:
                raise BotError(f"au plus {MAX_CONSTANT_BOTS} bots à puissance constante ou à profil")
            out.append(ProfileBot(profile, bot_id=f"bot{constant}", name=next(names), params=params,
                                  bike_mass_kg=bike_mass_kg, s=s))
        elif kind == "ghost":
            if ghost:
                raise BotError("un seul fantôme")
            ghost = True
            path = last_ride(route_id, journal_dir)
            if path is None:
                raise BotError(f"aucune séance passée sur le parcours « {route_id} » pour le fantôme")
            out.append(GhostBot(path))
        else:
            raise BotError(f"genre de bot inconnu : {kind!r} (constant, profile ou ghost)")
    return out
