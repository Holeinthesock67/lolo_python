"""Chef d'orchestre du mode WTF (lot WTF1, module pur).

`WtfMode` tire un événement au hasard parmi les règles actives toutes les 45 à 90 s (un seul à la
fois), lance le fromage en haut des descentes, fait vivre les règles permanentes et combine les
effets. La séance (lot WTF2) l'appelle à chaque pas en `RUNNING` :

    mode.step(WtfInput(...))
    eff = mode.effects()
    grade_physique = mode.grade(pente_du_parcours, eff)        # aussi pour la pente anticipée
    cible_trainer = mode.clamp_feel(braquet(mode.grade(pente_anticipée, eff)) + mode.feel_offset(eff))
    physics.p = mode.physics_params(base, eff) ; physics.step(mode.power(puissance_mesurée, eff), ...)

Garde-fous (la résistance réelle reste sûre) : supplément ressenti borné à ± 3 points, pente
envoyée bornée de − 6 % à + 10 % avant la limitation de variation habituelle du core, puissance
mesurée jamais modifiée (journal, FIT, bilan). Le mode est SIM seulement, comme la Course
tactique : en ERG le trainer impose la puissance et aucune règle n'aurait de sens.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field, replace

from ..physics import PhysicsParams
from .chef import Chef
from .events import (Camera, Cheese, Collapse, Ctx, Effects, Eggs, Event, Gravity, Micro, Storm, Tiny,
                     UpsideDown, WtfInput)
from .rules import DEFAULT_TABLE, WtfTable

FEEL_MIN_PCT, FEEL_MAX_PCT = -6.0, 10.0
FEEL_OFFSET_MAX_PCT = 3.0
CHEESE_GRADE_PCT, CHEESE_HOLD_S = -3.0, 3.0

EVENT_CLASSES: dict[str, type[Event]] = {
    "gravity": Gravity, "upside_down": UpsideDown, "collapse": Collapse, "cheese": Cheese,
    "micro": Micro, "eggs": Eggs, "tiny": Tiny, "storm": Storm, "camera": Camera, "chef": Chef,
}
# Le fromage ne se tire pas : il part tout seul en haut d'une descente.
DRAWN = tuple(k for k in EVENT_CLASSES if k != "cheese")

# Katamari : (objet, taille minimale pour le ramasser, gain de taille)
KATAMARI = (("apple", 1.0, 0.02), ("sign", 1.1, 0.05), ("cow", 1.4, 0.10), ("car", 2.0, 0.15),
            ("house", 3.0, 0.30), ("church", 4.5, 0.50))
KATA_SIZE_MAX = 6.0
KATA_KG_PER_SIZE, KATA_KG_MAX = 10.0, 50.0
KATA_FEEL_PER_SIZE, KATA_FEEL_MAX = 0.4, 2.0
KATA_AHEAD_M = 300.0
KATA_GAP_M = (40.0, 120.0)

SKINS = ("grandma", "tractor", "bathtub", "whale")
ATTACK_EVERY_S = (150.0, 240.0)
ATTACK_S, ATTACK_FACTOR = 20.0, 1.3
WHALE_DRAFT_K, DRAFT_CAP = 1.5, 0.55         # plafond d'abri de la série AS (AS4)

CLOCK_START_H = 10.0
FISH_ON_RPM, FISH_OFF_RPM = 100.0, 95.0


@dataclass
class WtfMode:
    table: WtfTable = DEFAULT_TABLE
    ftp_w: float = 250.0
    params: PhysicsParams = field(default_factory=PhysicsParams)
    seed: int | None = None
    erg: bool = False

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)
        self.ctx = Ctx(self.ftp_w, self.params)
        self.event: Event | None = None
        self.next_event_t = self.table.first_s
        self.points = 0
        self.played: list[dict] = []
        self.journal: list[dict] = []
        self.vexed = False
        self._desc_t = 0.0
        # Katamari
        self.kata_size = 1.0
        self.kata_count = 0
        self.kata_bonks = 0
        self.kata_last: str | None = None
        self._kata_objs: list[tuple[float, str]] = []
        self._kata_next_s: float | None = None
        # Peloton
        self.skins: dict[str, str] = {}
        self.attack_bot: str | None = None
        self._attack_left = 0.0
        self._next_attack_t = self.rng.uniform(*ATTACK_EVERY_S)
        # Cadence qui pilote le monde
        self.clock_h = CLOCK_START_H
        self.fish = False

    # --- pas de séance -------------------------------------------------------------------

    def step(self, inp: WtfInput) -> None:
        on = self.table.on
        if on("katamari"):
            self._step_katamari(inp.s)
        if on("peloton"):
            self._step_peloton(inp)
        if on("clock"):
            self.clock_h = (self.clock_h + inp.dt * inp.cadence_rpm / 30.0 / 60.0) % 24.0
            self.fish = inp.cadence_rpm >= (FISH_OFF_RPM if self.fish else FISH_ON_RPM)
        self._desc_t = self._desc_t + inp.dt if inp.grade_pct <= CHEESE_GRADE_PCT else 0.0

        ev = self.event
        if ev is not None:
            ev.s_now = inp.s
            ev.step(inp)
            if ev.done:
                self._close(ev, inp.t)
            return
        if on("cheese") and self._desc_t >= CHEESE_HOLD_S:
            self._open("cheese", inp)
            return
        if inp.t >= self.next_event_t:
            pool = [k for k in DRAWN if on(k)]
            if pool:
                self._open(self.rng.choice(pool), inp)
            else:
                self.next_event_t = math.inf

    def _open(self, kind: str, inp: WtfInput) -> None:
        cls = EVENT_CLASSES[kind]
        if cls is Chef:
            self.event = Chef(self.rng, self.ctx, inp, vexed=self.vexed)
            self.vexed = False
        else:
            self.event = cls(self.rng, self.ctx, inp)

    def _close(self, ev: Event, t: float) -> None:
        self.points += ev.points
        line = {"type": "wtf", "t": round(t, 2), "event": ev.id, "outcome": ev.outcome, "points": ev.points}
        if isinstance(ev, Chef):
            line["dish"] = ev.dish
            self.vexed = ev.refused
        elif isinstance(ev, Gravity):
            line["planet"] = ev.planet
        self.journal.append(line)
        self.played.append(line)
        self.event = None
        self._desc_t = 0.0   # pas deux fromages dans la même descente
        self.next_event_t = t + self.rng.uniform(self.table.gap_min_s, self.table.gap_max_s)

    def press(self, event: str) -> bool:
        """Bouton relayé par la séance ; vrai si le mode l'a pris (Z court refuse le plat du chef)."""
        return self.event.press(event) if self.event is not None else False

    def take_journal(self) -> list[dict]:
        out, self.journal = self.journal, []
        return out

    # --- Katamari ------------------------------------------------------------------------

    def _step_katamari(self, s: float) -> None:
        if self._kata_next_s is None:
            self._kata_next_s = s + self.rng.uniform(*KATA_GAP_M)
        while self._kata_next_s < s + KATA_AHEAD_M:
            reach = [k for k, need, _ in KATAMARI if need <= self.kata_size * 1.6]
            self._kata_objs.append((self._kata_next_s, self.rng.choice(reach)))
            self._kata_next_s += self.rng.uniform(*KATA_GAP_M)
        while self._kata_objs and self._kata_objs[0][0] <= s:
            _, kind = self._kata_objs.pop(0)
            need, gain = next((n, g) for k, n, g in KATAMARI if k == kind)
            if self.kata_size >= need:
                self.kata_size = min(self.kata_size + gain, KATA_SIZE_MAX)
                self.kata_count += 1
                self.kata_last = kind
            else:
                self.kata_bonks += 1   # trop gros pour toi : « boing »

    # --- peloton délirant ----------------------------------------------------------------

    def bot_skin(self, bot_id: str) -> str:
        """Costume d'un bot, donné à sa première apparition ; une seule baleine."""
        skin = self.skins.get(bot_id)
        if skin is None:
            skin = SKINS[len(self.skins) % len(SKINS)]
            if skin == "whale" and "whale" in self.skins.values():
                skin = "grandma"
            self.skins[bot_id] = skin
        return skin

    def _step_peloton(self, inp: WtfInput) -> None:
        if self._attack_left > 0.0:
            self._attack_left -= inp.dt
            if self._attack_left <= 0.0:
                self.attack_bot = None
        elif inp.t >= self._next_attack_t:
            grannies = sorted(b for b, sk in self.skins.items() if sk == "grandma")
            self._next_attack_t = inp.t + self.rng.uniform(*ATTACK_EVERY_S)
            if grannies:
                self.attack_bot = self.rng.choice(grannies)
                self._attack_left = ATTACK_S

    def bot_power_factor(self, bot_id: str) -> float:
        """Mamie à l'attaque : × 1,3 pendant 20 s."""
        return ATTACK_FACTOR if bot_id == self.attack_bot and self.table.on("peloton") else 1.0

    def draft(self, bot_id: str | None, alpha: float) -> float:
        """Abri derrière la baleine volante : × 1,5, sous le plafond de 55 % de la série AS."""
        if bot_id is not None and self.table.on("peloton") and self.skins.get(bot_id) == "whale":
            return min(alpha * WHALE_DRAFT_K, DRAFT_CAP)
        return alpha

    # --- effets --------------------------------------------------------------------------

    def effects(self) -> Effects:
        eff = Effects()
        if self.erg:
            return eff
        if self.event is not None:
            self.event.apply(eff)
        if self.table.on("katamari") and self.kata_size > 1.0:
            grow = self.kata_size - 1.0
            eff.mass_add_kg += min(grow * KATA_KG_PER_SIZE, KATA_KG_MAX)
            eff.feel_offset_pct += min(grow * KATA_FEEL_PER_SIZE, KATA_FEEL_MAX)
        return eff

    @staticmethod
    def grade(route_grade_pct: float, eff: Effects) -> float:
        """Pente transformée (physique virtuelle et base de la pente envoyée)."""
        return eff.grade_sign * route_grade_pct * eff.grade_k + eff.grade_add_pct

    @staticmethod
    def feel_offset(eff: Effects) -> float:
        return max(-FEEL_OFFSET_MAX_PCT, min(FEEL_OFFSET_MAX_PCT, eff.feel_offset_pct))

    @staticmethod
    def clamp_feel(target_pct: float) -> float:
        return max(FEEL_MIN_PCT, min(FEEL_MAX_PCT, target_pct))

    @staticmethod
    def physics_params(base: PhysicsParams, eff: Effects) -> PhysicsParams:
        if eff.crr_factor == 1.0 and eff.mass_add_kg == 0.0 and eff.wind_add_mps == 0.0:
            return base
        return replace(base, crr=base.crr * eff.crr_factor, mass_kg=base.mass_kg + eff.mass_add_kg,
                       wind_mps=base.wind_mps + eff.wind_add_mps)

    @staticmethod
    def power(measured_w: float, eff: Effects) -> float:
        """Puissance prise en compte par la physique (jamais écrite au journal ni au FIT)."""
        return measured_w * eff.power_factor

    def set_erg(self, on: bool) -> None:
        self.erg = bool(on)

    # --- trame et bilan ------------------------------------------------------------------

    def frame(self, t: float, s: float) -> dict:
        """Forme proposée pour le champ `wtf` de la trame `state` (lot WTF2)."""
        on = self.table.on
        out: dict = {"points": self.points,
                     "event": self.event.frame() if self.event is not None else None}
        if self.event is None and math.isfinite(self.next_event_t):
            out["next_s"] = round(max(self.next_event_t - t, 0.0))
        if on("katamari"):
            out["kata"] = {"size": round(self.kata_size, 2), "count": self.kata_count, "last": self.kata_last,
                           "next": [[round(o - s, 1), k] for o, k in self._kata_objs[:3]]}
        if on("peloton"):
            out["skins"] = dict(self.skins)
            out["attack"] = self.attack_bot
        if on("clock"):
            out["clock_h"] = round(self.clock_h, 2)
            out["fish"] = self.fish
        return out

    def summary(self) -> dict:
        """Bilan de fin de séance : points, événements joués, Katamari."""
        counts: dict[str, int] = {}
        for line in self.played:
            counts[line["event"]] = counts.get(line["event"], 0) + 1
        return {"points": self.points, "events": counts, "kata_size": round(self.kata_size, 2),
                "kata_count": self.kata_count}
