"""Mode « Grand Prix des objets » : règles de la course avec objets (lot GP1, module pur).

La séance (lot GP2) appelle le mode à chaque pas, après la physique de tous les coureurs :

    vitesses = mode.step(GpInput(t, dt, {id: RiderIn(s, v, v_eq, lane_m, grade_pct), ...}, paused))
    physics.v = vitesses[id]                          # vitesse virtuelle seulement
    physics.p = replace(base, wind_mps=vent + mode.wind_mps(id))   # vent contraire sans ressenti
    mode.use(id) ; mode.set_lane(id, voie | None)     # Z court ; A court, flèches, A long

Le mode ne calcule **aucune pente** : la pente envoyée au trainer ne dépend pas des objets (plan
`docs/4.0/PLAN_SERIE_GP.md` §7) ; la puissance mesurée n'y entre pas. Seuls l'abri et le vent,
calculés ailleurs avec leurs rampes et leur borne, se ressentent.

Règles communes : 2 s sans nouveau coup après un coup reçu ; parade automatique de la musette
guidée par un bidon ou une musette en réserve ; un seul nuage d'orage en vol ; rien pendant une
pause ou une coupure du trainer (`paused`), ni pendant 3 s après la reprise.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Iterable, Mapping, NamedTuple

from ..physics import PhysicsParams, resistive_force
from ..route_objects import RouteObjects, Runner
from .brain import BotBrain
from .boxes import BOX_EVERY_KM, LANES, ROULETTE_S, BoxRows, row_positions
from .draw import DrawContext, draw
from .effects import CHAOS, DURATIONS, IMPULSES, Active, EffectSpec, apply_speed, gain_s, is_immune, wind_of
from .items import DEFAULT_TABLE, ITEM_IDS, SHIELDS, GrandPrixError, ItemSpec, ItemTable

ME = "me"
LANE_EDGES_M = (1.07, 1.83)          # voies des objets sur la chaussée de droite (draft.LANE_MIN_M à LANE_MAX_M)
LANE_CENTRES_M = (0.68, 1.45, 2.22)  # gauche, centre, droite : cibles du placement forcé (GP2)
LANE_CHANGE_S = 0.6
MANUAL_HOLD_S = 20.0                 # placement automatique repris après 20 s sans objet en vue
VIEW_AHEAD_M, VIEW_BEHIND_M = 150.0, 100.0
HIT_GRACE_S = 2.0
RESUME_GRACE_S = 3.0
CHARGE_GAP_S = 1.0                   # une charge par seconde au plus
DROP_BEHIND_M, LAUNCH_AHEAD_M = 2.0, 2.0
FRAME_BEHIND_M, FRAME_AHEAD_M, FRAME_OBJECTS = 100.0, 400.0, 12
RESULT_REPEAT = 3
V_FLOOR = 1.0                        # m/s : vitesse plancher des écarts en temps
LOSS_DT_S = 0.1                      # pas de l'estimation du temps perdu (`loss_s`)


def lane_index(lane_m: float | None) -> int:
    """Voie (0 gauche, 1 centre, 2 droite) d'un écart à l'axe `lane_m` (AS2) ; centre sans écart."""
    if lane_m is None:
        return 1
    return sum(1 for edge in LANE_EDGES_M if lane_m >= edge)


class RiderIn(NamedTuple):
    s: float                         # abscisse de course (cumulée sur un circuit)
    v: float                         # vitesse virtuelle après la physique du pas
    v_eq: float                      # vitesse d'équilibre à la puissance et la pente du moment
    lane_m: float | None = None      # écart à l'axe du placement automatique (AS2)
    grade_pct: float = 0.0           # pente du parcours (estimation du temps perdu seulement)


class GpInput(NamedTuple):
    t: float
    dt: float
    riders: Mapping[str, RiderIn]
    paused: bool = False


@dataclass
class Racer:
    id: str
    s: float = 0.0
    s0: float = 0.0
    v: float = 0.0
    v_eq: float = 0.0
    grade_pct: float = 0.0
    lane: int = 1
    lane_to: int | None = None
    lane_at: float = 0.0
    auto: bool = True
    manual_t: float = 0.0
    held: str | None = None
    charges: int = 0
    roll: str | None = None
    roll_until: float = 0.0
    last_use: float = -1e9
    fx: list[Active] = field(default_factory=list)
    impulses: list[EffectSpec] = field(default_factory=list)
    hit_until: float = -1e9
    finished: int | None = None      # rang d'arrivée
    launched: dict[str, int] = field(default_factory=dict)
    received: dict[str, int] = field(default_factory=dict)
    dodged: int = 0
    gained_s: dict[str, float] = field(default_factory=dict)
    lost_s: dict[str, float] = field(default_factory=dict)


@dataclass
class _Burst:
    item: str
    by: str
    target: str
    at: float


@dataclass
class _Pending:
    msg: dict
    at: float
    left: int


@lru_cache(maxsize=512)
def _gain(effects: tuple[EffectSpec, ...], v_eq: float, grade: float, key: tuple) -> float:
    if v_eq <= V_FLOOR:
        return 0.0
    params = PhysicsParams(*key)
    power = max(resistive_force(v_eq, grade, 0.0, params) * v_eq / params.efficiency, 0.0)
    return gain_s(effects, power, grade, params, dt=LOSS_DT_S)


def estimate_s(effects: Iterable[EffectSpec], v_eq: float, grade_pct: float, params: PhysicsParams) -> float:
    """Temps gagné (positif) ou perdu par un effet, à la vitesse et la pente du moment (arrondis)."""
    key = (params.mass_kg, params.cda_m2, params.crr, params.efficiency, params.wind_mps)
    return _gain(tuple(effects), round(v_eq * 2.0) / 2.0, float(round(grade_pct)), key)


class GrandPrixMode:
    def __init__(self, riders: Iterable[str], length_m: float, *, lap_m: float | None = None,
                 table: ItemTable = DEFAULT_TABLE, chaos: str = "normal", box_every_km: float = 1.5,
                 enabled: Iterable[str] | None = None, seed: int | None = None,
                 params: PhysicsParams | None = None, origin_m: float = 0.0,
                 bots: Iterable[str] | None = None, levels: Mapping[str, float] | None = None) -> None:
        if chaos not in CHAOS:
            raise GrandPrixError(f"chaos : {chaos!r} refusé ({', '.join(CHAOS)})")
        if box_every_km not in BOX_EVERY_KM:
            raise GrandPrixError(f"écart des boîtes : {box_every_km!r} refusé")
        chosen = set(table.enabled if enabled is None else enabled)
        self.enabled = tuple(i for i in ITEM_IDS if i in chosen)
        unknown = chosen - set(ITEM_IDS)
        if unknown:
            raise GrandPrixError(f"objets inconnus : {', '.join(sorted(unknown))}")
        self.chaos = chaos
        k = CHAOS[chaos]
        self.table = table.scaled(k)
        self.length_m = float(length_m)
        self.lap_m = lap_m
        self.origin_m = float(origin_m)   # abscisse du départ : la course va de origin_m à origin_m + length_m
        # fréquence des objets × chaos : rangées plus serrées en « fou », plus espacées en « doux »
        self.boxes = BoxRows([self.origin_m + x for x in row_positions(self.length_m, box_every_km * 1000.0 / k, lap_m)])
        self.objects = RouteObjects()
        self.params = params or PhysicsParams()
        self.rng = random.Random(seed)
        self.racers: dict[str, Racer] = {rid: Racer(rid) for rid in riders}
        if ME not in self.racers:
            raise GrandPrixError("le cycliste (« me ») doit être en course")
        # Coureurs menés par le core (lot GP3 ; tous sauf le cycliste par défaut, le cycliste virtuel du banc
        # GP5 compris) : niveau en % de la FTP (esquive ± 10 points), 100 sans niveau connu
        levels = levels or {}
        driven = [rid for rid in self.racers if rid != ME] if bots is None else list(bots)
        if not set(driven) <= set(self.racers):
            raise GrandPrixError("bots : coureurs inconnus")
        self.brain = BotBrain({rid: float(levels.get(rid, 100.0)) for rid in driven}, chaos, seed)
        self.clock = 0.0
        self.t = 0.0
        self.grace_until = 0.0
        self.was_paused = False
        self.bursts: list[_Burst] = []
        self.arrivals = 0
        self.journal: list[dict] = []
        self._pending: list[_Pending] = []

    # --- course ---------------------------------------------------------------------------------

    def start(self, t: float, riders: Mapping[str, RiderIn]) -> None:
        self.t = t
        for rid, r in riders.items():
            racer = self.racers[rid]
            racer.s = racer.s0 = r.s
            racer.v, racer.v_eq = r.v, r.v_eq
            racer.lane = lane_index(r.lane_m)

    @property
    def finished(self) -> bool:
        return all(r.finished is not None for r in self.racers.values())

    def order(self) -> list[Racer]:
        """Coureurs dans l'ordre de la course : arrivés par rang d'arrivée, puis par abscisse."""
        return sorted(self.racers.values(),
                      key=lambda r: (r.finished is None, r.finished or 0, -r.s, r.id))

    def place(self, rid: str) -> int:
        return 1 + [r.id for r in self.order()].index(rid)

    def gap_s(self, rid: str) -> float:
        lead = self.order()[0]
        r = self.racers[rid]
        if r is lead:
            return 0.0
        return max(lead.s - r.s, 0.0) / max(r.v, V_FLOOR)

    def _racing(self) -> list[Racer]:
        return [r for r in self.racers.values() if r.finished is None]

    def _ahead_of(self, r: Racer) -> list[Racer]:
        return sorted((o for o in self._racing() if o.s > r.s and o is not r), key=lambda o: o.s)

    def _leader(self, but: Racer | None = None) -> Racer | None:
        rest = [o for o in self._racing() if o is not but]
        return max(rest, key=lambda o: (o.s, o.id)) if rest else None

    def step(self, inp: GpInput) -> dict[str, float]:
        """Avance d'un pas ; renvoie la vitesse virtuelle de chaque coureur après les objets."""
        self.t = inp.t
        if inp.paused:
            self.was_paused = True
            return {rid: r.v for rid, r in inp.riders.items()}
        if self.was_paused:
            self.was_paused = False
            self.grace_until = self.clock + RESUME_GRACE_S
        self.clock += inp.dt
        now = self.clock
        for rid, ri in inp.riders.items():
            r = self.racers[rid]
            r.s0, r.s, r.v, r.v_eq, r.grade_pct = r.s, ri.s, ri.v, ri.v_eq, ri.grade_pct
            if r.auto and r.lane_to is None:
                r.lane = lane_index(ri.lane_m)
        for r in self.racers.values():
            self._step_lane(r, now)
            if r.roll is not None and now >= r.roll_until:
                spec = self.table.items[r.roll]
                r.held, r.charges, r.roll = r.roll, spec.charges, None
            if r.finished is None and r.s >= self.origin_m + self.length_m:
                self.arrivals += 1
                r.finished = self.arrivals
                self._log("finish", r.id, place=r.finished)
        for r in self._racing():
            for row in self.boxes.crossed(r.s0, r.s):
                if self.boxes.take(row, r.lane, now) and r.held is None and r.roll is None:
                    self._roll(r, now)
        self.brain.step(self, now)
        self._step_objects(inp.dt)
        self._step_bursts(now)
        self._step_touch(now)
        out: dict[str, float] = {}
        for r in self.racers.values():
            r.fx = [a for a in r.fx if a.until_t > now]
            r.v = apply_speed(r.v, r.v_eq, r.impulses, r.fx)
            r.impulses.clear()
            out[r.id] = r.v
        return out

    def wind_mps(self, rid: str) -> float:
        """Vent de face virtuel en plus du vent réel (m/s), pour la physique seulement."""
        return wind_of(self.racers[rid].fx)

    # --- voies ----------------------------------------------------------------------------------

    def lane_target(self, rid: str) -> int | None:
        """Voie forcée vers laquelle va le coureur (None : placement automatique), pour l'écart à l'axe."""
        r = self.racers[rid]
        if r.auto:
            return None
        return r.lane if r.lane_to is None else r.lane_to

    def set_lane(self, rid: str, lane: int | None) -> bool:
        """Voie forcée (0, 1, 2) en 0,6 s ; None : retour au placement automatique."""
        r = self.racers[rid]
        if lane is None:
            r.auto, r.lane_to = True, None
            return True
        if isinstance(lane, bool) or lane not in range(LANES):
            return False
        r.auto, r.manual_t = False, self.clock
        if lane != r.lane:
            r.lane_to, r.lane_at = lane, self.clock + LANE_CHANGE_S
        else:
            r.lane_to = None
        return True

    def lane_choice_shown(self, rid: str) -> bool:
        """Le choix de voie a un sens : objet ou boîte à moins de 150 m devant, ou projectile derrière."""
        r = self.racers[rid]
        if self.boxes.ahead(r.s, VIEW_AHEAD_M):
            return True
        for o in self.objects.near(r.s, VIEW_BEHIND_M, VIEW_AHEAD_M):
            if o.s >= r.s or o.v > r.v:
                return True
        return False

    def _step_lane(self, r: Racer, now: float) -> None:
        if r.lane_to is not None and now >= r.lane_at:
            r.lane, r.lane_to = r.lane_to, None
        if not r.auto and r.lane_to is None and now - r.manual_t >= MANUAL_HOLD_S:
            if self.lane_choice_shown(r.id):
                r.manual_t = now
            else:
                r.auto = True

    # --- objets ---------------------------------------------------------------------------------

    def _roll(self, r: Racer, now: float) -> None:
        ctx = DrawContext(self.place(r.id), self.gap_s(r.id), len(self._ahead_of(r)), self._storm_flying())
        item = draw(ctx, self.table.weights, self.enabled, self.rng)
        if item is not None:
            r.roll, r.roll_until = item, now + ROULETTE_S
            self._log("box", r.id, item=item, place=ctx.place, gap_s=round(ctx.gap_s, 1))

    def _storm_flying(self) -> bool:
        return any(self.table.items.get(o.kind, None) is not None and self.table.items[o.kind].warn_s > 0.0
                   for o in self.objects) or bool(self.bursts)

    def use(self, rid: str) -> bool:
        """Z court : utilise l'objet en réserve. Faux s'il n'y en a pas ou s'il est trop tôt."""
        r = self.racers[rid]
        now = self.clock
        if r.held is None or r.finished is not None or now - r.last_use < CHARGE_GAP_S:
            return False
        item = r.held
        spec = self.table.items[item]
        if not self._fire(r, spec, now):
            return False
        r.last_use = now
        r.charges -= 1
        if r.charges <= 0:
            r.held, r.charges = None, 0
        r.launched[item] = r.launched.get(item, 0) + 1
        self._log("use", rid, item=item)
        if spec.steal_m:
            self._steal(r, spec.steal_m)
        return True

    def _fire(self, r: Racer, spec: ItemSpec, now: float) -> bool:
        if spec.target == "self":
            self._give(r, spec.self_fx, spec.id, r.id, now)
            if spec.self_fx:   # impulsion comme plancher de vitesse (super-forme, voiture d'équipe, lot GP5)
                self._credit(r, spec.id, spec.self_fx)
            return True
        if spec.form == "dropped":
            return self.objects.add(spec.id, r.s - DROP_BEHIND_M, r.lane, now, spec.ttl_s, owner=r.id,
                                    evictable=True) is not None
        if spec.form == "projectile":
            target = None
            if spec.target == "leader":
                lead = self._leader(but=r)
                if lead is None or lead.s <= r.s:
                    return False
                target = lead.id
            elif spec.lock_m:
                ahead = [o for o in self._ahead_of(r) if o.s - r.s <= spec.lock_m]
                target = ahead[0].id if ahead else None
            lane = None if spec.target == "leader" else r.lane
            return self.objects.add(spec.id, r.s + LAUNCH_AHEAD_M, lane, now, spec.ttl_s,
                                    v=r.v + spec.speed_rel_mps, range_m=spec.range_m, owner=r.id,
                                    target=target) is not None
        if spec.target == "near":
            for o in list(self.objects):
                if abs(o.s - r.s) <= spec.clear_m and o.target in (None, r.id):
                    self.objects.remove(o)
            gone = [b for b in self.bursts if b.target == r.id]
            for b in gone:
                self.bursts.remove(b)
                r.dodged += 1
            for o in self._racing():
                if o is not r and abs(o.s - r.s) <= spec.radius_m:
                    self._hit(o, spec, spec.hit_fx, r.id, now)
            return True
        if spec.target == "ahead":
            for o in self._ahead_of(r):
                self._hit(o, spec, spec.hit_fx, r.id, now)
            return True
        return False

    def _steal(self, r: Racer, within_m: float) -> None:
        for o in self._ahead_of(r):
            if o.s - r.s > within_m:
                break
            if o.held is not None and r.held is None:
                r.held, r.charges, o.held, o.charges = o.held, o.charges, None, 0
                self._log("steal", r.id, item=r.held, target=o.id)
                break

    def _give(self, r: Racer, fx: Iterable[EffectSpec], item: str, by: str, now: float) -> None:
        for e in fx:
            if e.effect in IMPULSES:
                r.impulses.append(e)
            elif e.effect in DURATIONS:
                r.fx.append(Active(e, now + e.duration_s, item, by))

    def _hit(self, target: Racer, spec: ItemSpec, fx: tuple[EffectSpec, ...], by: str, now: float) -> bool:
        """Coup reçu ; faux s'il est arrêté (invincible, parade, coup récent, reprise après pause)."""
        if not fx or target.finished is not None:
            return False
        knock = any(e.effect in ("slip", "cap") for e in fx)
        if is_immune(target.fx) or now < self.grace_until or (knock and now < target.hit_until):
            target.dodged += 1
            return False
        if knock:
            target.hit_until = now + HIT_GRACE_S
        self._give(target, fx, spec.id, by, now)
        loss = max(-estimate_s(fx, target.v_eq, target.grade_pct, self.params), 0.0)   # perte, positive
        target.received[spec.id] = target.received.get(spec.id, 0) + 1
        target.lost_s[spec.id] = round(target.lost_s.get(spec.id, 0.0) + loss, 2)
        msg = {"type": "gp_hit", "v": 1, "item": spec.id, "by": by, "target": target.id,
               "loss_s": round(loss, 1)}
        self._pending.append(_Pending(msg, self.t, RESULT_REPEAT))
        self._log("hit", target.id, item=spec.id, by=by, loss_s=round(loss, 1))
        return True

    def _credit(self, r: Racer, item: str, fx: tuple[EffectSpec, ...]) -> None:
        gain = estimate_s(fx, r.v_eq, r.grade_pct, self.params)
        r.gained_s[item] = round(r.gained_s.get(item, 0.0) + gain, 2)

    def _step_objects(self, dt: float) -> None:
        now = self.clock
        for o in self.objects:
            spec = self.table.items[o.kind]
            if spec.target == "leader":
                lead = self._leader(but=self.racers.get(o.owner))
                o.target = lead.id if lead else None
        runners = [Runner(r.id, r.s0, r.s, r.lane) for r in self._racing()]
        for c in self.objects.step(now, dt, runners):
            spec = self.table.items[c.obj.kind]
            target = self.racers[c.runner]
            if spec.warn_s > 0.0:
                self.bursts.append(_Burst(spec.id, c.obj.owner or "", target.id, now + spec.warn_s))
                self._log("warn", target.id, item=spec.id, by=c.obj.owner)
                continue
            if spec.lock_m and target.held in SHIELDS and not is_immune(target.fx):
                target.charges -= 1
                if target.charges <= 0:
                    target.held, target.charges = None, 0
                target.dodged += 1
                self._log("parry", target.id, item=spec.id, by=c.obj.owner)
                continue
            self._hit(target, spec, spec.hit_fx, c.obj.owner or "", now)

    def _step_bursts(self, now: float) -> None:
        for b in [b for b in self.bursts if now >= b.at]:
            self.bursts.remove(b)
            spec = self.table.items[b.item]
            target = self.racers[b.target]
            self._hit(target, spec, spec.hit_fx, b.by, now)
            for o in self._racing():
                if o is not target and abs(o.s - target.s) <= spec.splash_m:
                    self._hit(o, spec, spec.splash_fx, b.by, now)

    def _step_touch(self, now: float) -> None:
        """Coureurs frôlés par un coureur sous un effet qui touche (super-forme : même voie, 1,5 m)."""
        for r in self._racing():
            for a in r.fx:
                spec = self.table.items.get(a.item)
                if spec is None or spec.form != "duration" or not spec.radius_m or a.by != r.id:
                    continue
                for o in self._racing():
                    if o is not r and o.lane == r.lane and abs(o.s - r.s) <= spec.radius_m:
                        self._hit(o, spec, spec.hit_fx, r.id, now)
                break

    # --- sorties --------------------------------------------------------------------------------

    def frame(self, rid: str = ME) -> dict:
        """`state.gp` vu par un coureur (le cycliste par défaut)."""
        r = self.racers[rid]
        now = self.clock
        objs = self.objects.near(r.s, FRAME_BEHIND_M, FRAME_AHEAD_M, FRAME_OBJECTS)
        warn = None
        threats = [(o.s, o.kind) for o in self.objects if o.target == rid and o.owner != rid]
        threats += [(r.s, b.item) for b in self.bursts if b.target == rid]
        if threats:
            s, kind = min(threats, key=lambda x: abs(x[0] - r.s))
            warn = [self.table.items[kind].shot_kind, round(abs(r.s - s), 1)]
        out = {
            "place": self.place(rid), "of": len(self.racers), "gap_s": round(self.gap_s(rid), 1),
            "held": r.held, "n": r.charges, "roll_s": round(max(r.roll_until - now, 0.0), 1) if r.roll else 0.0,
            "lane": r.lane if r.lane_to is None else r.lane_to, "auto": r.auto,
            "fx": self._fx_items(r, now),
            "warn": warn,
            "obj": [[o.id, self.table.items[o.kind].shot_kind, round(o.s, 1), o.lane if o.lane is not None else -1]
                    for o in objs],
            "boxes": [round(x) for x in self.boxes.ahead(r.s, FRAME_AHEAD_M)][:2],   # rangées fixes : au mètre
            "pick": self.lane_choice_shown(rid),   # lot GP2 : A court change de voie (sinon vue suivante)
        }
        if self.lap_m:
            lap = min(int(max(r.s - self.origin_m, 0.0) // self.lap_m) + 1, max(int(round(self.length_m / self.lap_m)), 1))
            out["lap"] = [lap, max(int(round(self.length_m / self.lap_m)), 1)]
        return out

    def bot_frame(self, rid: str) -> dict:
        """Champs ajoutés à un élément de `bots` : objet en réserve et effets en cours."""
        r = self.racers[rid]
        return {"item": r.held, "fx": [k for k, _ in self._fx_items(r, self.clock)]}

    @staticmethod
    def _fx_items(r: Racer, now: float) -> list[list]:
        """Effets en cours regroupés par objet : [[objet, reste en s], ...] (l'icône du HUD est celle de l'objet)."""
        left: dict[str, float] = {}
        for a in r.fx:
            if a.until_t > now:
                left[a.item] = max(left.get(a.item, 0.0), a.until_t - now)
        return [[k, round(v, 1)] for k, v in sorted(left.items())]

    def due_results(self, t: float) -> list[dict]:
        """Messages `gp_hit` à envoyer maintenant (3 fois, à une seconde d'intervalle)."""
        out: list[dict] = []
        for p in self._pending:
            if t >= p.at:
                out.append(p.msg)
                p.left -= 1
                p.at = t + 1.0
        self._pending = [p for p in self._pending if p.left > 0]
        return out

    def _log(self, event: str, rider: str, **kw) -> None:
        self.journal.append({"kind": "gp", "t": round(self.t, 2), "event": event, "rider": rider, **kw})

    def take_journal(self) -> list[dict]:
        lines, self.journal = self.journal, []
        return lines

    def summary(self, rid: str = ME) -> dict:
        """`summary.gp` : place, format, objets lancés, reçus, esquivés, temps gagné et perdu par objet."""
        r = self.racers[rid]
        out = {"place": self.place(rid), "of": len(self.racers), "launched": dict(sorted(r.launched.items())),
               "received": dict(sorted(r.received.items())), "dodged": r.dodged,
               "gained_s": dict(sorted(r.gained_s.items())), "lost_s": dict(sorted(r.lost_s.items()))}
        if self.lap_m:
            out["laps"] = max(int(round(self.length_m / self.lap_m)), 1)
        else:
            out["distance_km"] = round(self.length_m / 1000.0, 1)
        return out
