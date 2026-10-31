"""Bots virtuels pour OpenRide (Lot N9).

- ConstantPowerBot : puissance constante, même modèle physique que le cycliste.
- GhostBot : rejeu de la position d'une séance passée (.fit ou .jsonl).
- ProfileBot (lot T12) : profil physiologique (CP, W′, masse, pic sur 10 s) et stratégie par segment ;
  réserve W′bal du modèle de la série R (`rogue/wbal.py`), le même pour le joueur et les bots.
  `kind` reste `constant` (contrat 1.4 : `kind` vaut `constant` ou `ghost`) ; le champ `profile` le
  distingue. Cahier : `docs/lots/LOT_T12_bots_profil.md`.
- calibrate (lot T13) : échelle de la CP d'un bot à profil pour qu'il finisse le parcours dans le temps
  d'un cycliste de référence à `level_pct` % de sa FTP. Cahier : `docs/lots/LOT_T13_equilibrage_bots.md`.
- lot AS1 : les bots `constant` s'abritent (`draft`, posé par `draft.update_bots`) ; un bot à profil
  garde la roue du coureur devant lui (`wheel`) au lieu de le doubler. Cahier :
  `docs/lots/LOT_AS1_abri_entre_bots.md`.
- lot DS3 : tactique de survie du mode « Dernier survivant » (`survival`, posé à chaque pas par la séance
  depuis `survivor.survival_hints`) : sprint avant l'arche quand le bot est menacé, économie dans les
  roues quand il est loin du dernier. Cahier : `docs/lots/LOT_DS3_tactique_bots.md`.
"""

from __future__ import annotations

import bisect
from dataclasses import replace
from datetime import datetime
import math
from pathlib import Path
from typing import Any

from dataclasses import dataclass

from .config import BOUNDS
from .physics import G, V_FLOOR, V_MAX, PhysicsParams, RiderPhysics, air_density, resistive_force
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
        self.draft = 0.0                       # abri lissé (lot AS1), posé par draft.update_bots
        self.wheel: tuple[float, float] | None = None   # roue suivie : écart (m) et vitesse du coureur devant
        self.push = 0.0                        # poussée du coureur qui suit de près
        self.power_factor = 1.0                # mamie à l'attaque du mode WTF (lot WTF2)

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

        self.physics.step(self.power_w * self.power_factor, grade, alt, dt, alpha_draft=self.draft)
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
    survival: float = 1.30         # lot DS3 : fraction de CP du sprint de survie avant une arche


PROFILES: dict[str, BotProfile] = {
    "climber": BotProfile("Grimpeur", 60.0, 4.0, 15000.0, flat=0.92, climb=1.00, climb_attack=1.10,
                          survival=1.25),
    "rouleur": BotProfile("Rouleur", 72.0, 3.6, 20000.0, flat=1.00, climb=0.95),
    "sprinter": BotProfile("Sprinteur", 80.0, 3.3, 25000.0, flat=0.90, climb=0.88, peak_wkg=12.0,
                           survival=1.50),
    "diesel": BotProfile("Diesel", 75.0, 3.8, 10000.0, flat=1.00, climb=1.00, survival=1.20),
}


DEFAULT_BIKE_MASS_KG = 8.0
FOLLOW_GAP_M = 0.5          # lot AS1 : écart visé dans la roue
FOLLOW_GAIN = 0.5           # 1/s : vitesse visée = vitesse de la roue + gain × (écart − écart visé)
FOLLOW_TAU_S = 2.0          # s : temps pour rattraper la vitesse visée
FOLLOW_MIN_CP = 0.60        # puissance plancher dans la roue, en part de la CP
FOLLOW_LEAVE_SPEED = 0.85   # la roue plus lente que 85 % de la vitesse de croisière seule : on repart
SURVIVAL_MIN_WBAL_PCT = 10.0   # lot DS3 : pas de sprint de survie sous 10 % de réserve
SURVIVAL_SAFE_CP = 0.95        # lot DS3 : plafond d'un bot loin du dernier, en part de la CP


class ProfileBot(ConstantPowerBot):
    """Bot à profil : même physique que ConstantPowerBot, puissance choisie à chaque pas par sa stratégie
    et limitée par sa réserve W′bal (au-dessus de la CP, ramenée à la CP quand la réserve est vide).

    `segments` : segments de la couche du parcours (montées et sprints, ceux de `classic.py`) ;
    sans segment, la règle « plat » partout. `scale` met CP, W′ et pic à l'échelle (lot T13). Masse
    physique : masse du profil (W/kg) plus `bike_mass_kg` (le vélo du cycliste, `config.toml`).
    `level_pct` : niveau demandé au menu (lot T13) ; None : le réglage `bots.level_pct` de la séance."""

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
        level_pct: float | None = None,
    ) -> None:
        if profile not in PROFILES:
            raise BotError(f"profil de bot inconnu : {profile!r} ({', '.join(PROFILES)})")
        self.profile = profile
        self.spec = PROFILES[profile]
        super().__init__(self.spec.cp_wkg * self.spec.mass_kg, bot_id=bot_id,
                         name=name if name is not None else self.spec.name,
                         params=params, mass_kg=self.spec.mass_kg + bike_mass_kg, s=s, v=v)
        self.mass_kg = self.spec.mass_kg
        self.segments = tuple(segments)
        self.level_pct = level_pct
        # lot DS3 : (distance à l'arche en m, menacé, à l'abri, distance de début du sprint) ; None hors mode
        self.survival: tuple[float, bool, bool, float] | None = None
        self.set_scale(scale)

    def set_scale(self, scale: float) -> None:
        """CP, W′ et pic du profil multipliés par `scale` ; réserve pleine (départ de séance, lot T13)."""
        if not math.isfinite(scale) or scale <= 0:
            raise BotError(f"échelle de bot invalide : {scale}")
        self.scale = float(scale)
        self.cp_w = self.spec.cp_wkg * self.spec.mass_kg * scale
        self.w_prime_j = self.spec.w_prime_j * scale
        self.peak_w = self.spec.peak_wkg * self.spec.mass_kg * scale
        self.power_w = self.cp_w
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

    def target_power(self, s: float, length_m: float = 0.0, is_loop: bool = False,
                     wbal_pct: float | None = None) -> float:
        """Puissance demandée par la stratégie à la position s, avant la limite de la réserve
        (`wbal_pct` : réserve à prendre en compte, celle du bot sinon ; simulation du calibrage)."""
        return self._strategy(s, length_m, is_loop, wbal_pct)[0]

    def _strategy(self, s: float, length_m: float, is_loop: bool,
                  wbal_pct: float | None = None) -> tuple[float, bool]:
        """Puissance de la stratégie et vrai pour une attaque en montée ou un sprint (lot AS1 : le bot
        quitte alors la roue qu'il suivait)."""
        spec = self.spec
        if self.survival is not None:
            d_m, danger, safe, sprint_from_m = self.survival
            reserve = self.wbal_pct if wbal_pct is None else wbal_pct
            if danger and d_m <= sprint_from_m and reserve > SURVIVAL_MIN_WBAL_PCT:
                return spec.survival * self.cp_w, True
            power, tactical = self._course_strategy(s, length_m, is_loop, wbal_pct)
            if safe:
                return min(power, SURVIVAL_SAFE_CP * self.cp_w), False
            return power, tactical
        return self._course_strategy(s, length_m, is_loop, wbal_pct)

    def _course_strategy(self, s: float, length_m: float, is_loop: bool,
                         wbal_pct: float | None = None) -> tuple[float, bool]:
        """Stratégie par segment du lot T12 (montée, attaque, sprint ; plat ailleurs)."""
        spec = self.spec
        here = self._segment_here(s, length_m, is_loop)
        if here is None:
            return spec.flat * self.cp_w, False
        seg, lap = here
        if seg.type == "climb":
            reserve = self.wbal_pct if wbal_pct is None else wbal_pct
            attack = spec.climb_attack > 0 and reserve > 100.0 * spec.climb_reserve
            return (spec.climb_attack if attack else spec.climb) * self.cp_w, attack
        pos = s % length_m if is_loop and length_m > 0 else s
        if self.peak_w > 0 and seg.s_end - pos <= spec.sprint_last_m:
            key = (seg.id, lap)
            if key != self._peak_key:
                self._peak_key, self._peak_used_s = key, 0.0
            if self._peak_used_s < spec.peak_s - 1e-9:   # 10 s pile, malgré les arrondis des pas
                return self.peak_w, True
        return spec.flat * self.cp_w, False

    def _cruise_speed(self, power_w: float, grade: float, alt: float) -> float:
        """Vitesse d'équilibre seul, sans abri, à `power_w` (dichotomie courte : un appel par pas)."""
        lo, hi = 0.0, V_MAX
        target = self.params.efficiency * power_w
        for _ in range(24):
            mid = 0.5 * (lo + hi)
            if resistive_force(mid, grade, alt, self.params) * mid < target:
                lo = mid
            else:
                hi = mid
        return 0.5 * (lo + hi)

    def _follow_power(self, power_w: float, grade: float, alt: float) -> float:
        """Puissance pour garder la roue (lot AS1) : vitesse de la roue corrigée de l'écart, sans
        dépasser la stratégie ni descendre sous 60 % de la CP. La stratégie si la roue est trop lente."""
        gap, v_lead = self.wheel
        if v_lead < FOLLOW_LEAVE_SPEED * self._cruise_speed(power_w, grade, alt):
            return power_w
        v = self.physics.v
        v_want = max(v_lead + FOLLOW_GAIN * (gap - FOLLOW_GAP_M), 0.0)
        force = resistive_force(v_want, grade, alt, self.params, self.draft)
        need = (force * v_want + self.params.mass_kg * (v_want - v) / FOLLOW_TAU_S * v) / self.params.efficiency
        return min(power_w, max(need, FOLLOW_MIN_CP * self.cp_w))

    def step(self, dt: float, route: Route | None = None) -> None:
        if dt < 0:
            return
        length = route.length_m if route is not None else 0.0
        loop = route.is_loop if route is not None else False
        power, tactical = self._strategy(self.physics.s, length, loop)
        if self.wheel is not None and not tactical:
            here = route.sample(self.physics.s) if route is not None else None
            power = self._follow_power(power, here.grade_pct if here else 0.0, here.alt_m if here else 0.0)
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


# --- équilibrage des bots à profil (lot T13) ------------------------------------------------------

CALIBRATION_DT = 0.5          # s : pas de la simulation du calibrage (pas les 50 Hz de la séance)
CALIBRATION_TOL = 0.002       # écart de temps visé, sous les 0,5 % du cahier (relevé du parcours à 10 m)
CALIBRATION_CELL_M = 10.0     # pente et altitude relevées tous les 10 m
CALIBRATION_MAX_ITER = 12
SCALE_BOUNDS = (0.2, 5.0)


@dataclass(frozen=True)
class RefRider:
    """Cycliste de référence du calibrage : FTP et physique du cycliste dans la séance (`config.toml`
    et équipement de la série V : `apply_equipment`, lot V5), pour que le niveau choisi reste juste."""

    ftp_w: float
    params: PhysicsParams


class RouteProfile:
    """Parcours relevé une fois pour tous les bots : sinus, cosinus de la pente et densité de l'air
    tous les `cell_m` mètres, sur un tour pour une boucle."""

    def __init__(self, route: Any, cell_m: float = CALIBRATION_CELL_M) -> None:
        self.length_m = float(route.length_m)
        self.cell_m = cell_m
        n = max(1, int(math.ceil(self.length_m / cell_m)))
        self.sin: list[float] = []
        self.cos: list[float] = []
        self.rho: list[float] = []
        for i in range(n):
            here = route.sample(min((i + 0.5) * cell_m, self.length_m))
            theta = math.atan(here.grade_pct / 100.0)
            self.sin.append(math.sin(theta))
            self.cos.append(math.cos(theta))
            self.rho.append(air_density(here.alt_m))


def ride_time(prof: RouteProfile, params: PhysicsParams, power_w: float = 0.0,
              bot: ProfileBot | None = None, dt: float = CALIBRATION_DT) -> float:
    """Temps d'un tour du parcours, depuis l'arrêt, au pas `dt` : puissance constante `power_w`, ou
    stratégie et réserve W′bal de `bot` (remis à neuf par son `set_scale`). Mêmes équations que
    `RiderPhysics.step` et `wbal_step` (vérifié par `test_bots_calibration.py`), écrites en ligne pour
    tenir le coût du cahier : moins de 0,5 s pour 4 bots sur 100 km."""
    m, eff, crr, wind = params.mass_kg, params.efficiency, params.crr, params.wind_mps
    gravity = [m * G * (sn + crr * cs) for sn, cs in zip(prof.sin, prof.cos)]
    aero = [0.5 * rho * params.cda_m2 for rho in prof.rho]
    n, cell, length = len(gravity), prof.cell_m, prof.length_m
    max_t = 24 * 3600.0
    cp = wp = w = peak = 0.0
    if bot is not None:
        cp, wp, peak = bot.cp_w, bot.w_prime_j, bot.peak_w
        w = wp
    s = v = t = 0.0
    while s < length and t < max_t:
        i = min(int(s / cell), n - 1)
        p = power_w
        if bot is not None:
            p = bot.target_power(s, length, False, 100.0 * w / wp)
            if p > cp and w <= 0.0:
                p = cp
            if p == peak and peak > 0:
                bot._peak_used_s += dt
            if p > cp:
                w = max(w - (p - cp) * dt, 0.0)
            else:
                w = wp - (wp - w) * math.exp(-(cp - p) / wp * dt)
        if v < V_FLOOR and (p > 0.0 or gravity[i] < 0.0):
            v = V_FLOOR
        va = v + wind
        energy = 0.5 * m * v * v + (eff * p - (aero[i] * va * abs(va) + gravity[i]) * v) * dt
        v_new = min(math.sqrt(max(energy, 0.0) * 2.0 / m), V_MAX)
        if s + v_new * dt >= length and v_new > 0:
            return t + (length - s) / v_new   # fraction du dernier pas
        s += v_new * dt
        v = v_new
        t += dt
    return t


def calibrate(profile: str, route: Any, level_pct: float, rider: RefRider, segments: tuple = (),
              bike_mass_kg: float = DEFAULT_BIKE_MASS_KG, prof: RouteProfile | None = None,
              bot_params: PhysicsParams | None = None) -> float:
    """Échelle de la CP (et de W′ et du pic) du profil pour finir le parcours dans le temps du cycliste
    de référence à `level_pct` % de sa FTP, à `CALIBRATION_TOL` près. Fonction pure.

    `bot_params` : physique du bot pendant la séance (CdA, Crr, rendement ; sa masse vient du profil),
    celle du cycliste par défaut. L'équipement du cycliste (lot V5) ne s'applique qu'à lui : le bot
    roule sans, son échelle compense.

    Recherche sur le logarithme de l'échelle : sécante, gardée dans l'encadrement trouvé (dichotomie
    quand la sécante en sort) ; le temps décroît avec l'échelle. `prof` : relevé du parcours à partager
    entre bots."""
    if profile not in PROFILES:
        raise BotError(f"profil de bot inconnu : {profile!r} ({', '.join(PROFILES)})")
    prof = prof or RouteProfile(route)
    still = replace(rider.params, wind_mps=0.0)   # calibrage sans vent, pour le cycliste comme pour le bot
    t_ref = ride_time(prof, still, power_w=rider.ftp_w * level_pct / 100.0)
    bot = ProfileBot(profile, params=replace(bot_params or rider.params, wind_mps=0.0), segments=segments,
                     bike_mass_kg=bike_mass_kg)
    lo_x, hi_x = math.log(SCALE_BOUNDS[0]), math.log(SCALE_BOUNDS[1])

    def err(x: float) -> float:
        bot.set_scale(math.exp(x))
        return math.log(ride_time(prof, bot.params, bot=bot) / t_ref)

    # Départ : même W/kg que le cycliste de référence.
    spec = PROFILES[profile]
    rider_wkg = rider.ftp_w * level_pct / 100.0 / max(rider.params.mass_kg - bike_mass_kg, 1.0)
    x0 = min(max(math.log(rider_wkg / spec.cp_wkg), lo_x), hi_x)
    f0 = err(x0)
    best = (abs(f0), x0)
    x1 = min(max(x0 + f0 / 0.7, lo_x), hi_x)   # temps à peu près en échelle^-0,7
    lo, hi = (lo_x, hi_x)
    for _ in range(CALIBRATION_MAX_ITER):
        if best[0] <= math.log1p(CALIBRATION_TOL):
            break
        f1 = err(x1)
        best = min(best, (abs(f1), x1))
        # Encadrement : erreur positive (trop lent) à gauche, négative à droite.
        if f1 > 0:
            lo = max(lo, x1)
        else:
            hi = min(hi, x1)
        if f0 > 0:
            lo = max(lo, x0)
        else:
            hi = min(hi, x0)
        x2 = x1 - f1 * (x1 - x0) / (f1 - f0) if f1 != f0 else 0.5 * (lo + hi)
        if not lo < x2 < hi:
            x2 = 0.5 * (lo + hi)
        x0, f0, x1 = x1, f1, x2
    return math.exp(best[1])


def calibrate_bots(bots: list[Any], route: Any, rider: RefRider, level_pct: float, segments: tuple = (),
                   bike_mass_kg: float = DEFAULT_BIKE_MASS_KG,
                   bot_params: PhysicsParams | None = None) -> dict[tuple[str, float], float]:
    """Calibre les bots à profil de la séance (niveau du bot, `level_pct` du réglage sinon) ; un calcul
    par couple (profil, niveau). Renvoie les échelles trouvées. `bot_params` : voir `calibrate`."""
    scales: dict[tuple[str, float], float] = {}
    prof: RouteProfile | None = None
    for b in bots:
        if not isinstance(b, ProfileBot):
            continue
        key = (b.profile, float(b.level_pct if b.level_pct is not None else level_pct))
        if key not in scales:
            prof = prof or RouteProfile(route)
            scales[key] = calibrate(b.profile, route, key[1], rider, segments, bike_mass_kg, prof, bot_params)
        b.set_scale(scales[key])
    return scales


# --- bots choisis au menu (lot O7, contrat IPC révision 1.3) --------------------------------------

MAX_CONSTANT_BOTS = 4
LEVEL_BOUNDS = BOUNDS[("bots", "level_pct")]   # % de la FTP : bornes du réglage `bots.level_pct`


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
    ftp_pct}`, `{kind: "profile", profile, level_pct?}` (lots T12 et T13 ; au plus 4 bots de ces deux
    genres en tout ; `level_pct` dans les bornes du réglage `bots.level_pct`, celui-ci sans lui) et
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
            level = it.get("level_pct")
            lo, hi = LEVEL_BOUNDS
            if level is not None and (isinstance(level, bool) or not isinstance(level, (int, float))
                                      or not lo <= level <= hi):
                raise BotError(f"niveau de bot : {level!r} refusé ({lo:g} à {hi:g} % de la FTP)")
            constant += 1
            if constant > MAX_CONSTANT_BOTS:
                raise BotError(f"au plus {MAX_CONSTANT_BOTS} bots à puissance constante ou à profil")
            out.append(ProfileBot(profile, bot_id=f"bot{constant}", name=next(names), params=params,
                                  bike_mass_kg=bike_mass_kg, s=s,
                                  level_pct=float(level) if level is not None else None))
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
