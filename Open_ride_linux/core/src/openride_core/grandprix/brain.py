"""Bots du Grand Prix des objets : usage des objets, garde et esquive (lot GP3, module pur).

Règles du plan `docs/4.0/PLAN_SERIE_GP.md` §6, lues sur la fiche de chaque objet (cible et forme) plutôt
que sur son nom, pour qu'un objet ajouté à la table suive la règle de sa famille :

- objet pour soi (coup de fouet, super-forme, voiture d'équipe, furtif) et nuage d'orage : tout de suite,
  après un délai tiré entre 0,5 et 3 s (graine de la séance) ; le nuage seulement s'il y a un premier devant ;
- bidon (posé derrière) : un coureur à moins de 30 m derrière ;
- musette (lancée devant) : une cible sur la voie du bot à moins de 150 m ; musette guidée : une cible à
  moins de sa portée de verrouillage (200 m), toutes voies ;
- sonnette (autour de soi) : un projectile à moins de 30 m derrière qui arrive, ou le nuage qui vise le bot,
  vu depuis un temps de réaction humain tiré entre 0,6 et 1,5 s (lot GPO1) ;
- vent contraire (devant, durée) : au moins deux coureurs devant ;
- garde : le bot en tête garde son bidon ou sa musette comme bouclier tant qu'aucune boîte n'approche ;
- voie des boîtes (lot GPO1) : à moins de 150 m d'une rangée, le bot prend la voie de la famille qui
  lui sert, « attaquer » (droite) dans les 5 s du premier ou en tête, « s'aider » (gauche) plus loin, ou
  reste au centre une fois sur trois (graine de la séance) ; une décision par rangée, jamais sur un objet ;
- esquive : un objet sur sa voie à moins de 40 m devant, une décision par objet, réussie avec une
  probabilité de 30, 50 ou 75 % selon le chaos, plus ou moins 10 points selon le niveau du bot.

Le cerveau ne touche qu'aux objets et aux voies : jamais à la puissance d'un bot (pas d'élastique,
§6). Le rattrapage ne passe que par le tirage selon le retard (§4.2).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Mapping

from .boxes import LANES
from .items import BOX_LANES, BRACKET_LIMITS_S, SHIELDS, ItemSpec

if TYPE_CHECKING:
    from .mode import GrandPrixMode, Racer

DELAY_S = (0.5, 3.0)                 # délai avant d'utiliser un objet tout juste reçu
DROP_BEHIND_TRIGGER_M = 30.0         # bidon : coureur à moins de 30 m derrière
LAUNCH_LANE_M = 150.0                # musette : cible sur la voie à moins de 150 m
BELL_TRIGGER_M = 30.0                # sonnette : projectile à moins de 30 m derrière
HEADWIND_MIN_AHEAD = 2               # vent contraire : au moins deux coureurs devant
GUARD_BOX_M = 150.0                  # garde levée quand une rangée de boîtes approche (vue du choix de voie)
DODGE_LOOK_M = 40.0
BOX_LANE_M = 150.0                   # voie de la famille choisie à moins de 150 m d'une rangée de boîtes
BOX_CENTRE_P = 1.0 / 3.0             # une fois sur trois : centre (tout le tirage)
DODGE_BASE = {"soft": 0.18, "normal": 0.30, "wild": 0.45}   # lot GPO1 : 0,30 / 0,50 / 0,75 avant (essai du 22/11)
REACT_S = (0.6, 1.5)                 # sonnette : temps de réaction humain à une menace (0,02 s avant, essai du 22/11)
DODGE_LEVEL_PTS = 10.0               # ± 10 points entre 50 et 150 % de la FTP
LEVEL_MIN, LEVEL_MID, LEVEL_MAX = 50.0, 100.0, 150.0


def dodge_chance(chaos: str, level_pct: float) -> float:
    """Probabilité d'esquive d'un bot : celle du chaos, ± 10 points de 50 à 150 % de la FTP."""
    level = min(max(level_pct, LEVEL_MIN), LEVEL_MAX)
    pts = DODGE_LEVEL_PTS * (level - LEVEL_MID) / (LEVEL_MAX - LEVEL_MID)
    return min(max(DODGE_BASE[chaos] + pts / 100.0, 0.0), 1.0)


@dataclass
class _Mind:
    ready_at: float | None = None    # objet en réserve utilisable à partir de cet instant
    seen: set[tuple[int, float]] = field(default_factory=set)   # objets déjà jugés (id, naissance)
    box_row: float | None = None     # rangée de boîtes pour laquelle la voie est déjà choisie
    react_at: float | None = None    # menace vue : sonnette possible à partir de cet instant


@dataclass
class DodgeStats:
    tries: int = 0                   # objets jugés sur la voie à moins de 40 m
    done: int = 0                    # esquives décidées


class BotBrain:
    """Décisions des bots, appelées par `GrandPrixMode.step` avant le pas des objets."""

    def __init__(self, bots: Mapping[str, float], chaos: str, seed: int | None = None) -> None:
        self.chance = {rid: dodge_chance(chaos, level) for rid, level in bots.items()}
        self.minds = {rid: _Mind() for rid in bots}
        self.rng = random.Random(None if seed is None else f"{seed}:bots")
        self.stats = DodgeStats()

    def step(self, mode: GrandPrixMode, now: float) -> None:
        for rid, mind in self.minds.items():
            r = mode.racers[rid]
            if r.finished is not None:
                continue
            self._box_lane(mode, r, mind)
            self._dodge(mode, r, mind, now)
            if r.held is None:
                mind.ready_at = None
                continue
            if mind.ready_at is None:
                mind.ready_at = now + self.rng.uniform(*DELAY_S)
            spec = mode.table.items[r.held]
            if spec.target == "near":   # sonnette : pas avant un temps de réaction humain après la menace vue
                if not threatened(mode, r):
                    mind.react_at = None
                    continue
                if mind.react_at is None:
                    mind.react_at = now + self.rng.uniform(*REACT_S)
                if now < mind.react_at:
                    continue
            if now >= mind.ready_at and wants(mode, r, spec):
                mode.use(rid)
                mind.react_at = None

    def _box_lane(self, mode: GrandPrixMode, r: Racer, mind: _Mind) -> None:
        """Voie de la famille d'objets qui sert au bot, avant chaque rangée (sans réserve ni roulette)."""
        if r.held is not None or r.roll is not None:
            return
        rows = mode.boxes.ahead(r.s, BOX_LANE_M)
        if not rows or rows[0] == mind.box_row:
            return
        mind.box_row = rows[0]
        if self.rng.random() < BOX_CENTRE_P:
            want = BOX_LANES.index("any")
        else:
            near_lead = mode.place(r.id) <= 1 or mode.gap_s(r.id) < BRACKET_LIMITS_S[0]
            want = BOX_LANES.index("attack" if near_lead else "help")
        lane = r.lane if r.lane_to is None else r.lane_to
        blocked = {o.lane for o in mode.objects.near(r.s, 0.0, DODGE_LOOK_M) if o.s > r.s and o.owner != r.id}
        if want != lane and want not in blocked:
            mode.set_lane(r.id, want)

    def _dodge(self, mode: GrandPrixMode, r: Racer, mind: _Mind, now: float) -> None:
        lane = r.lane if r.lane_to is None else r.lane_to
        mind.seen = {k for k in mind.seen if any((o.id, o.born_t) == k for o in mode.objects)}
        for o in mode.objects.near(r.s, 0.0, DODGE_LOOK_M):
            key = (o.id, o.born_t)
            if o.s <= r.s or o.lane != lane or o.owner == r.id or key in mind.seen:
                continue
            mind.seen.add(key)
            self.stats.tries += 1
            if self.rng.random() >= self.chance[r.id]:
                continue
            free = free_lanes(mode, r, lane)
            if free:
                self.stats.done += 1
                mode.set_lane(r.id, min(free, key=lambda x: (abs(x - lane), x)))
                mode._log("dodge", r.id, item=o.kind)
            return


def free_lanes(mode: GrandPrixMode, r: Racer, lane: int) -> list[int]:
    """Voies voisines sans objet devant à moins de 40 m."""
    blocked = {o.lane for o in mode.objects.near(r.s, 0.0, DODGE_LOOK_M) if o.s > r.s and o.owner != r.id}
    return [x for x in (lane - 1, lane + 1) if 0 <= x < LANES and x not in blocked]


def leads(mode: GrandPrixMode, r: Racer) -> bool:
    return not mode._ahead_of(r)


def wants(mode: GrandPrixMode, r: Racer, spec: ItemSpec) -> bool:
    """L'objet en réserve sert maintenant (règles du plan §6, garde comprise)."""
    if spec.id in SHIELDS and leads(mode, r) and not mode.boxes.ahead(r.s, GUARD_BOX_M):
        return False
    ahead = mode._ahead_of(r)
    if spec.target == "self":
        return True
    if spec.target == "leader":
        lead = mode._leader(but=r)
        return lead is not None and lead.s > r.s
    if spec.form == "dropped":
        return any(0.0 < r.s - o.s <= DROP_BEHIND_TRIGGER_M for o in mode._racing() if o is not r)
    if spec.target == "ahead" and spec.form == "projectile":
        if spec.lock_m:
            return any(o.s - r.s <= spec.lock_m for o in ahead)
        return any(o.s - r.s <= LAUNCH_LANE_M and o.lane == r.lane for o in ahead)
    if spec.target == "ahead":
        return len(ahead) >= HEADWIND_MIN_AHEAD
    if spec.target == "near":
        return threatened(mode, r)
    return False


def threatened(mode: GrandPrixMode, r: Racer) -> bool:
    """Projectile à moins de 30 m derrière qui arrive sur le bot, ou nuage d'orage qui le vise."""
    if any(b.target == r.id for b in mode.bursts):
        return True
    for o in mode.objects:
        if o.owner == r.id:
            continue
        if o.target == r.id and mode.table.items[o.kind].warn_s > 0.0:
            return True
        coming = o.v > r.v and 0.0 <= r.s - o.s <= BELL_TRIGGER_M
        if coming and (o.target == r.id or o.lane is None or o.lane == r.lane):
            return True
    return False
