"""Objets sur la route : objets posés et projectiles, repérés par leur abscisse `s` et leur voie (lot GP1).

Module générique et pur (aucune entrée-sortie) : le mode « Grand Prix des objets » y pose ses bidons
et lance ses musettes ; un autre mode pourra le reprendre (le Mode WTF garde ses règles). Un objet a
une abscisse `s`, une voie (entier, `None` : toutes les voies), une vitesse `v` (0 pour un objet
posé), une durée de vie et une portée. À chaque pas, `RouteObjects.step` avance les projectiles,
retire les objets échus et renvoie les contacts : un coureur et un objet sur la même voie qui se sont
croisés pendant le pas (ou qui sont à moins de `CONTACT_M` l'un de l'autre).

Au plus `MAX_OBJECTS` objets à la fois : au-delà, le plus vieil objet « évinçable » disparaît
(les bidons posés), sinon l'ajout est refusé. Plan : `docs/4.0/PLAN_SERIE_GP.md` §5 et §8.3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, NamedTuple

MAX_OBJECTS = 32
ID_MAX = 99              # identifiants repris de 1 à 99 (jamais celui d'un objet encore sur la route) : trame courte
CONTACT_M = 1.0          # écart en s sous lequel un coureur et un objet de la même voie se touchent


@dataclass
class RouteObject:
    id: int
    kind: str
    s: float
    lane: int | None
    born_t: float
    ttl_s: float
    v: float = 0.0                      # m/s le long de la route (0 : objet posé)
    range_m: float | None = None        # distance parcourue au-delà de laquelle l'objet disparaît
    owner: str | None = None
    target: str | None = None           # coureur suivi (projectile guidé) : la voie suit la sienne
    evictable: bool = False             # peut disparaître quand la réserve de `MAX_OBJECTS` est pleine
    travelled_m: float = 0.0
    prev_s: float = field(default=0.0, repr=False)

    def __post_init__(self) -> None:
        self.prev_s = self.s


class Runner(NamedTuple):
    """Un coureur vu par les objets : abscisse avant et après le pas, voie."""

    id: str
    s0: float
    s1: float
    lane: int


class Contact(NamedTuple):
    obj: RouteObject
    runner: str


@dataclass
class RouteObjects:
    max_objects: int = MAX_OBJECTS
    contact_m: float = CONTACT_M

    def __post_init__(self) -> None:
        self.objects: list[RouteObject] = []
        self._next_id = 1

    def __len__(self) -> int:
        return len(self.objects)

    def __iter__(self):
        return iter(self.objects)

    def add(self, kind: str, s: float, lane: int | None, t: float, ttl_s: float, *, v: float = 0.0,
            range_m: float | None = None, owner: str | None = None, target: str | None = None,
            evictable: bool = False) -> RouteObject | None:
        """Ajoute un objet ; None si la réserve est pleine sans objet évinçable."""
        if len(self.objects) >= self.max_objects:
            old = [o for o in self.objects if o.evictable]
            if not old:
                return None
            self.objects.remove(min(old, key=lambda o: (o.born_t, o.id)))
        live = {o.id for o in self.objects}
        while self._next_id in live:
            self._next_id = self._next_id % ID_MAX + 1
        obj = RouteObject(self._next_id, kind, s, lane, t, ttl_s, v, range_m, owner, target, evictable)
        self._next_id = self._next_id % ID_MAX + 1
        self.objects.append(obj)
        return obj

    def remove(self, obj: RouteObject) -> None:
        if obj in self.objects:
            self.objects.remove(obj)

    def step(self, t: float, dt: float, runners: Iterable[Runner],
             speeds: Mapping[str, float] | None = None) -> list[Contact]:
        """Avance les projectiles de `dt`, retire les objets échus et renvoie les contacts du pas.

        `speeds` : vitesse de chaque coureur, pour un projectile guidé qui ne dépasse pas sa cible de
        plus de sa vitesse propre. Un objet touche au plus un coureur (le premier rencontré) et
        disparaît ; il ne touche jamais son lanceur pendant sa première seconde."""
        runners = list(runners)
        by_id = {r.id: r for r in runners}
        for o in self.objects:
            o.prev_s = o.s
            if o.v:
                o.s += o.v * dt
                o.travelled_m += abs(o.v) * dt
            if o.target is not None and o.target in by_id:
                o.lane = by_id[o.target].lane
        self.objects = [o for o in self.objects
                        if t - o.born_t < o.ttl_s and (o.range_m is None or o.travelled_m <= o.range_m)]
        contacts: list[Contact] = []
        for o in sorted(self.objects, key=lambda o: (o.born_t, o.id)):
            hit = self._first_contact(o, runners, t)
            if hit is not None:
                contacts.append(Contact(o, hit))
        for c in contacts:
            self.remove(c.obj)
        return contacts

    def _first_contact(self, o: RouteObject, runners: list[Runner], t: float) -> str | None:
        best: tuple[float, str] | None = None
        for r in runners:
            if o.lane is not None and r.lane != o.lane:
                continue
            if o.target is not None and r.id != o.target:
                continue
            if r.id == o.owner and t - o.born_t < 1.0:
                continue
            d0, d1 = r.s0 - o.prev_s, r.s1 - o.s
            crossed = (d0 < 0.0 <= d1) or (d0 > 0.0 >= d1)
            if crossed or abs(d1) <= self.contact_m:
                # le premier rencontré : le plus proche de la position de départ de l'objet, dans son sens
                key = abs(r.s0 - o.prev_s)
                if best is None or (key, r.id) < best:
                    best = (key, r.id)
        return best[1] if best else None

    def near(self, s: float, behind_m: float, ahead_m: float, limit: int | None = None) -> list[RouteObject]:
        """Objets entre `s − behind_m` et `s + ahead_m`, du plus proche au plus loin."""
        out = [o for o in self.objects if -behind_m <= o.s - s <= ahead_m]
        out.sort(key=lambda o: (abs(o.s - s), o.id))
        return out[:limit] if limit is not None else out
