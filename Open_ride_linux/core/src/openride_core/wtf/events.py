"""Événements du mode WTF : une seule à la fois, durée limitée (lot WTF1, module pur).

Un événement reçoit à chaque pas une `WtfInput` (mesures et position du pas) et écrit ses effets
dans `Effects` ; `WtfMode` les combine et les borne. Les effets possibles :

- `grade_k`, `grade_sign`, `grade_add_pct` : transformation de la pente du parcours, pour la
  physique virtuelle **et** pour la pente envoyée au trainer (avant braquet, lissage et bornes) ;
- `feel_offset_pct` : supplément de pente envoyé au trainer seulement, borné par `WtfMode` ;
- `crr_factor`, `mass_add_kg`, `wind_add_mps`, `power_factor` : physique virtuelle seulement.

La puissance mesurée, celle du journal et du FIT, n'est jamais modifiée.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from ..physics import PhysicsParams, steady_speed

MOON_G, JUPITER_G = 0.165, 2.53


@dataclass(frozen=True)
class WtfInput:
    t: float                  # temps chronométré de la séance (s)
    dt: float
    s: float                  # position cumulée (m)
    v: float                  # vitesse virtuelle (m/s)
    power_w: float            # puissance mesurée
    cadence_rpm: float
    grade_pct: float          # pente du parcours sous les roues
    measures_ok: bool = True  # faux pendant une coupure du trainer : pas de détection d'à-coup


@dataclass
class Effects:
    grade_k: float = 1.0
    grade_sign: float = 1.0
    grade_add_pct: float = 0.0
    feel_offset_pct: float = 0.0
    crr_factor: float = 1.0
    mass_add_kg: float = 0.0
    wind_add_mps: float = 0.0
    power_factor: float = 1.0


@dataclass(frozen=True)
class Ctx:
    """Ce que les événements savent du cycliste."""
    ftp_w: float
    params: PhysicsParams


class Event:
    """Base : `step` à chaque pas, `apply` pour les effets, `frame` pour la trame `state`."""

    id = ""
    duration_s = 60.0

    def __init__(self, rng: random.Random, ctx: Ctx, inp: WtfInput) -> None:
        self.rng, self.ctx = rng, ctx
        self.t0 = inp.t
        self.s_now = inp.s        # position du dernier pas, mise à jour par `WtfMode`
        self.left_s = self.duration_s
        self.done = False
        self.points = 0
        self.outcome = "done"     # ligne du journal : success, fail, escaped, caught...

    def step(self, inp: WtfInput) -> None:
        self.left_s -= inp.dt
        if self.left_s <= 1e-9:
            self.left_s = 0.0
            self.timeout()

    def timeout(self) -> None:
        """Durée écoulée : issue et points de l'événement."""
        self.finish()

    def finish(self, outcome: str | None = None, points: int = 0) -> None:
        if self.done:
            return
        self.done = True
        if outcome:
            self.outcome = outcome
        self.points += points

    def apply(self, eff: Effects) -> None:
        pass

    def press(self, event: str) -> bool:
        """Bouton du Click ou du clavier ; vrai si l'événement l'a pris."""
        return False

    def data(self) -> dict:
        return {}

    def frame(self) -> dict:
        return {"id": self.id, "left_s": round(self.left_s, 1), **self.data()}


# --- physique détraquée ----------------------------------------------------------------------

class Gravity(Event):
    """La Lune ou Jupiter pendant une minute ; sur la Lune, le vélo fait des bonds."""

    id = "gravity"
    duration_s = 60.0
    HOP_PERIOD_S = 2.0

    def __init__(self, rng, ctx, inp) -> None:
        super().__init__(rng, ctx, inp)
        self.planet = rng.choice(("moon", "jupiter"))
        self.k = MOON_G if self.planet == "moon" else JUPITER_G
        self.hop_m = 0.0

    def step(self, inp) -> None:
        super().step(inp)
        if self.planet == "moon":
            # Bond parabolique toutes les 2 s, plus haut quand on roule vite (borné à 3 m).
            phase = ((inp.t - self.t0) % self.HOP_PERIOD_S) / self.HOP_PERIOD_S
            top = min(0.05 * inp.v * inp.v / (9.81 * self.k), 3.0)
            self.hop_m = 4.0 * top * phase * (1.0 - phase)

    def timeout(self) -> None:
        self.finish("done", 50)

    def apply(self, eff) -> None:
        eff.grade_k *= self.k
        eff.crr_factor *= self.k

    def data(self) -> dict:
        return {"planet": self.planet, "hop_m": round(self.hop_m, 2)}


class UpsideDown(Event):
    id = "upside_down"
    duration_s = 45.0

    def timeout(self) -> None:
        self.finish("done", 50)

    def apply(self, eff) -> None:
        eff.grade_sign *= -1.0


class Collapse(Event):
    """La route s'effondre derrière toi à la vitesse que donneraient 60 % de la FTP."""

    id = "collapse"
    duration_s = 60.0
    START_GAP_M = 120.0
    POWER_FRAC = 0.60

    def __init__(self, rng, ctx, inp) -> None:
        super().__init__(rng, ctx, inp)
        self.front_s = inp.s - self.START_GAP_M
        self.front_v = 0.0
        self._next_speed_t = inp.t

    def step(self, inp) -> None:
        if inp.t >= self._next_speed_t:   # dichotomie une fois par seconde, pas à 50 Hz
            self._next_speed_t = inp.t + 1.0
            self.front_v = steady_speed(self.POWER_FRAC * self.ctx.ftp_w, inp.grade_pct, self.ctx.params)
        self.front_s += self.front_v * inp.dt
        if self.front_s >= inp.s:
            self.finish("fell", 0)
            return
        super().step(inp)

    def timeout(self) -> None:
        self.finish("escaped", 150)

    def data(self) -> dict:
        return {"gap_m": round(max(self.s_now - self.front_s, 0.0), 1)}


class Cheese(Event):
    """Meule de fromage lâchée en haut d'une descente : rester devant jusqu'à 250 m d'avance."""

    id = "cheese"
    duration_s = 75.0
    START_GAP_M, ESCAPE_GAP_M = 60.0, 250.0
    ACCEL = 0.5
    SQUASH_S = 3.0

    def __init__(self, rng, ctx, inp) -> None:
        super().__init__(rng, ctx, inp)
        self.cheese_s = inp.s - self.START_GAP_M
        self.cheese_v = 0.8 * inp.v
        self.v_max = max(1.5 * inp.v, 15.0)
        self.gap_m = self.START_GAP_M
        self.squash_left = 0.0

    def step(self, inp) -> None:
        if self.squash_left > 0.0:   # écrasé : 3 s de dessin animé, puis fin
            self.squash_left -= inp.dt
            if self.squash_left <= 0.0:
                self.finish("caught", 0)
            return
        self.cheese_v = min(self.cheese_v + self.ACCEL * inp.dt, self.v_max)
        self.cheese_s += self.cheese_v * inp.dt
        self.gap_m = inp.s - self.cheese_s
        if self.gap_m <= 0.0:
            self.squash_left = self.SQUASH_S
            self.gap_m = 0.0
            return
        if self.gap_m >= self.ESCAPE_GAP_M:
            self.finish("escaped", 150)
            return
        super().step(inp)

    def timeout(self) -> None:
        self.finish("rolled_away", 50)   # la meule part dans un champ

    def data(self) -> dict:
        return {"gap_m": round(self.gap_m, 1), "squashed": self.squash_left > 0.0}


class Storm(Event):
    """Tornade de vaches et vent de face : sous 50 % de la FTP, le vent te repousse (visuel)."""

    id = "storm"
    duration_s = 40.0
    WIND_MPS = 6.0
    FEEL_PCT = 1.5
    PUSH_MPS, RECOVER_MPS, PUSH_MAX_M = 1.5, 3.0, 30.0

    def __init__(self, rng, ctx, inp) -> None:
        super().__init__(rng, ctx, inp)
        self.pushback_m = 0.0

    def step(self, inp) -> None:
        if inp.power_w < 0.5 * self.ctx.ftp_w:
            self.pushback_m = min(self.pushback_m + self.PUSH_MPS * inp.dt, self.PUSH_MAX_M)
        else:
            self.pushback_m = max(self.pushback_m - self.RECOVER_MPS * inp.dt, 0.0)
        super().step(inp)

    def timeout(self) -> None:
        held = self.pushback_m < 1.0
        self.finish("held" if held else "blown", 100 if held else 20)

    def apply(self, eff) -> None:
        eff.wind_add_mps += self.WIND_MPS
        eff.feel_offset_pct += self.FEEL_PCT

    def data(self) -> dict:
        cows = min(int((self.duration_s - self.left_s) * 2), 40)   # la tornade se remplit de vaches
        return {"pushback_m": round(self.pushback_m, 1), "cows": cows}


# --- règles à la WarioWare -------------------------------------------------------------------

CHALLENGES = ("cadence", "sprint", "cap", "steady", "spin")


class Micro(Event):
    """Trois micro-défis de 30 s à la suite, seuils indexés sur la FTP."""

    id = "micro"
    ROUND_S = 30.0
    ROUNDS = 3
    duration_s = ROUND_S * ROUNDS

    def __init__(self, rng, ctx, inp) -> None:
        super().__init__(rng, ctx, inp)
        self.queue = rng.sample(CHALLENGES, self.ROUNDS)
        self.results: list[bool] = []
        self._start_round()

    def _start_round(self) -> None:
        self.kind = self.queue[len(self.results)]
        self.round_left = self.ROUND_S
        self.acc = 0.0          # temps réussi cumulé
        self.over = 0.0         # temps au-dessus du plafond
        self.ref_w: float | None = None
        self._ref_sum = self._ref_t = 0.0
        ftp = self.ctx.ftp_w
        self.target = {
            "cadence": float(self.rng.choice((80, 85, 90, 95, 100))),
            "sprint": round(1.5 * ftp / 5) * 5.0,
            "cap": round(0.6 * ftp / 5) * 5.0,
            "steady": 0.0,
            "spin": 110.0,
        }[self.kind]

    def _round_success(self) -> bool | None:
        """Vrai ou faux si le défi est déjà tranché, None s'il faut attendre la fin."""
        if self.kind == "sprint" and self.acc >= 5.0:
            return True
        if self.kind == "spin" and self.acc >= 10.0:
            return True
        if self.kind == "cap" and self.over > 3.0:
            return False
        return None

    def _end_success(self) -> bool:
        if self.kind == "cadence":
            return self.acc >= 0.6 * self.ROUND_S
        if self.kind == "cap":
            return self.over <= 3.0
        if self.kind == "steady":
            return self.acc >= 0.7 * (self.ROUND_S - 5.0)
        return False   # sprint et spin non atteints

    def step(self, inp) -> None:
        dt = inp.dt
        k = self.kind
        if k == "cadence" and abs(inp.cadence_rpm - self.target) <= 3.0:
            self.acc += dt
        elif k == "sprint" and inp.power_w >= self.target:
            self.acc += dt
        elif k == "cap" and inp.power_w > self.target:
            self.over += dt
        elif k == "spin" and inp.cadence_rpm >= self.target:
            self.acc += dt
        elif k == "steady":
            if self.ROUND_S - self.round_left < 5.0:   # 5 s pour fixer la référence
                self._ref_sum += inp.power_w * dt
                self._ref_t += dt
            else:
                if self.ref_w is None:
                    self.ref_w = self._ref_sum / self._ref_t if self._ref_t else inp.power_w
                    self.target = round(self.ref_w)
                if self.ref_w and abs(inp.power_w - self.ref_w) <= 0.10 * self.ref_w:
                    self.acc += dt
        self.round_left -= dt
        self.left_s = max(self.left_s - dt, 0.0)
        verdict = self._round_success()
        if verdict is None and self.round_left <= 1e-9:
            verdict = self._end_success()
        if verdict is not None:
            self.results.append(verdict)
            self.left_s = self.ROUND_S * (self.ROUNDS - len(self.results))
            if len(self.results) == self.ROUNDS:
                won = sum(self.results)
                self.finish("success" if won == self.ROUNDS else f"{won}/{self.ROUNDS}", 100 * won)
            else:
                self._start_round()

    def data(self) -> dict:
        return {"kind": self.kind, "target": self.target, "round": len(self.results) + 1,
                "round_left_s": round(max(self.round_left, 0.0), 1), "results": list(self.results),
                "progress": round(self._progress(), 2)}

    def _progress(self) -> float:
        need = {"cadence": 0.6 * self.ROUND_S, "sprint": 5.0, "spin": 10.0, "steady": 0.7 * (self.ROUND_S - 5.0)}
        if self.kind == "cap":
            return max(0.0, 1.0 - self.over / 3.0)
        return min(self.acc / need[self.kind], 1.0)


class Eggs(Event):
    """Six œufs à livrer à 3 km : un écart de puissance de plus de 35 % de la FTP d'une seconde
    à l'autre en casse un (une casse toutes les 2 s au plus, rien pendant une coupure)."""

    id = "eggs"
    duration_s = 480.0
    DISTANCE_M = 3000.0
    EGGS = 6
    JERK_FRAC = 0.35
    COOLDOWN_S = 2.0

    def __init__(self, rng, ctx, inp) -> None:
        super().__init__(rng, ctx, inp)
        self.s0 = inp.s
        self.eggs = self.EGGS
        self._bucket = self._bucket_t = 0.0
        self._prev_avg: float | None = None
        self._cool = 0.0
        self._bucket_ok = True
        self.broke_at: float | None = None

    def step(self, inp) -> None:
        self._cool = max(self._cool - inp.dt, 0.0)
        self._bucket += inp.power_w * inp.dt
        self._bucket_t += inp.dt
        self._bucket_ok = self._bucket_ok and inp.measures_ok
        if self._bucket_t >= 1.0:
            avg = self._bucket / self._bucket_t
            if not self._bucket_ok:
                self._prev_avg = None        # coupure du trainer : on repart de zéro
            else:
                if self._prev_avg is not None and self._cool == 0.0 \
                        and abs(avg - self._prev_avg) > self.JERK_FRAC * self.ctx.ftp_w:
                    self.eggs -= 1
                    self._cool = self.COOLDOWN_S
                    self.broke_at = inp.t
                self._prev_avg = avg
            self._bucket = self._bucket_t = 0.0
            self._bucket_ok = True
        if self.eggs <= 0:
            self.finish("omelette", 0)
            return
        if inp.s - self.s0 >= self.DISTANCE_M:
            self.finish("delivered", 50 * self.eggs)
            return
        super().step(inp)

    def timeout(self) -> None:
        self.finish("late", 10 * self.eggs)

    def data(self) -> dict:
        return {"eggs": self.eggs, "left_m": round(max(self.DISTANCE_M - (self.s_now - self.s0), 0.0))}


# --- décor et caméra -------------------------------------------------------------------------

class Tiny(Event):
    id = "tiny"
    duration_s = 60.0
    SCALE = 0.025

    def timeout(self) -> None:
        self.finish("done", 30)

    def data(self) -> dict:
        return {"scale": self.SCALE, "set": "kitchen"}


CAMERAS = ("pigeon", "snail", "wheel")


class Camera(Event):
    id = "camera"
    duration_s = 30.0

    def __init__(self, rng, ctx, inp) -> None:
        super().__init__(rng, ctx, inp)
        self.view = rng.choice(CAMERAS)

    def timeout(self) -> None:
        self.finish("done", 20)

    def data(self) -> dict:
        return {"view": self.view}


def sinus(t: float, period_s: float) -> float:
    return math.sin(2.0 * math.pi * t / period_s)
