"""Catalogue des treize objets du Grand Prix (lot GP1, plan `docs/4.0/PLAN_SERIE_GP.md` §3).

Chaque objet est décrit par des données : une **cible** (soi, devant, premier, coureurs proches),
une **forme** (immédiat, durée, objet posé, projectile), les effets sur soi (`self_fx`), les effets
sur le coureur touché (`hit_fx`) et quelques portées. Le mode (`mode.py`) ne connaît que ces
champs : aucun objet n'a de branche de code à lui.

Les valeurs se modifient dans `~/OpenRide/grandprix.toml` (facultatif), bornées paramètre par
paramètre ; une valeur hors bornes ou une clé inconnue refusent tout le fichier :

    [gel]
    kick = 1.3              # facteur d'un effet, par son nom
    [storm]
    cap = 0.5
    duration_s = 1.5        # durée de tous les effets à durée de l'objet
    splash_m = 10
    [weights.lead]          # poids du tirage en tête (lead, lt5, 5to15, gt15)
    bottle = 30
    [items]                 # objets joués (true) ou coupés (false), écrit par le menu (lot GP2)
    storm = false
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Mapping

from ..config import OPENRIDE_HOME
from .effects import DURATIONS, EFFECTS, EffectSpec

GRANDPRIX_FILE = OPENRIDE_HOME / "grandprix.toml"

TARGETS = ("self", "ahead", "leader", "near", "behind")
FORMS = ("instant", "duration", "dropped", "projectile")

ITEM_IDS = ("gel", "gel_x3", "bottle", "bottle_x3", "musette", "musette_x3", "homing", "storm",
            "star", "bell", "headwind", "team_car", "stealth")
LABELS = {
    "gel": "Coup de fouet", "gel_x3": "Trois coups de fouet", "bottle": "Bidon glissant",
    "bottle_x3": "Trois bidons", "musette": "Musette lancée", "musette_x3": "Trois musettes",
    "homing": "Musette guidée", "storm": "Nuage d'orage", "star": "Super-forme", "bell": "Sonnette",
    "headwind": "Vent contraire", "team_car": "Voiture d'équipe", "stealth": "Furtif",
}
# Familles des maquettes GP6 (validées le 7 novembre 2026) : une couleur et une forme de pastille chacune
FAMILIES = {
    "gel": "self", "gel_x3": "self", "star": "self", "team_car": "self", "stealth": "self",
    "musette": "attack", "musette_x3": "attack", "homing": "attack",
    "bottle": "trap", "bottle_x3": "trap",
    "storm": "leader", "headwind": "leader",
    "bell": "guard",
}
SHIELDS = ("bottle", "bottle_x3", "musette", "musette_x3")   # en réserve, parent la musette guidée

# Tranches du tirage selon le retard sur le premier (plan §4.2)
BRACKETS = ("lead", "lt5", "5to15", "gt15")
BRACKET_LIMITS_S = (5.0, 15.0)

# Poids en % (jeu « normal ») ; les lignes doubles du plan (« Bidon, trois bidons ») sont partagées
# trois quarts pour l'objet simple, un quart pour l'objet triple.
DEFAULT_WEIGHTS: dict[str, dict[str, float]] = {
    "lead": {"bottle": 30, "bottle_x3": 10, "musette": 15, "musette_x3": 5, "bell": 25,
             "gel": 11.25, "gel_x3": 3.75},
    "lt5": {"bottle": 15, "bottle_x3": 5, "musette": 18.75, "musette_x3": 6.25, "homing": 20, "bell": 5,
            "gel": 15, "gel_x3": 5, "headwind": 5, "star": 5},
    "5to15": {"bottle": 3.75, "bottle_x3": 1.25, "musette": 15, "musette_x3": 5, "homing": 20,
              "gel": 18.75, "gel_x3": 6.25, "headwind": 10, "storm": 10, "star": 10},
    "gt15": {"musette": 7.5, "musette_x3": 2.5, "homing": 10, "gel": 15, "gel_x3": 5, "headwind": 10,
             "storm": 10, "star": 15, "team_car": 20, "stealth": 5},
}

# Bornes des paramètres réglables (fichier de valeurs)
FACTOR_BOUNDS = {"kick": (1.0, 2.0), "slip": (0.2, 1.0), "speed_floor": (1.0, 2.0), "cap": (0.2, 1.0),
                 "wind": (0.0, 15.0)}
PARAM_BOUNDS = {"duration_s": (0.5, 30.0), "ttl_s": (5.0, 300.0), "range_m": (50.0, 1000.0),
                "speed_rel_mps": (5.0, 40.0), "lock_m": (20.0, 500.0), "radius_m": (0.5, 30.0),
                "clear_m": (1.0, 50.0), "splash_m": (0.0, 30.0), "steal_m": (10.0, 200.0),
                "warn_s": (0.0, 5.0)}
WEIGHT_MAX = 100.0


class GrandPrixError(ValueError):
    """Fichier de valeurs ou réglage refusé."""


@dataclass(frozen=True)
class ItemSpec:
    id: str
    target: str
    form: str
    self_fx: tuple[EffectSpec, ...] = ()
    hit_fx: tuple[EffectSpec, ...] = ()
    charges: int = 1
    speed_rel_mps: float = 0.0        # projectile : vitesse en plus de celle du lanceur
    range_m: float | None = None      # projectile : portée
    ttl_s: float = 30.0               # objet posé ou projectile : durée de vie
    lock_m: float = 0.0               # cible devant à moins de `lock_m` (musette guidée)
    radius_m: float = 0.0             # coureurs touchés autour (super-forme : même voie ; sonnette)
    clear_m: float = 0.0              # objets détruits autour (sonnette)
    splash_m: float = 0.0             # coureurs proches de la cible touchés aussi (nuage d'orage)
    steal_m: float = 0.0              # vole l'objet du coureur devant à moins de `steal_m` (Furtif)
    warn_s: float = 0.0               # délai entre l'arrivée sur la cible et le coup (nuage d'orage)
    splash_fx: tuple[EffectSpec, ...] = ()   # effets sur les coureurs à moins de `splash_m` de la cible
    shot: str = ""                    # objet posé ou lancé tel que l'engine le dessine (vide : `id`)
    escort: str = ""                  # véhicule d'AS6 (sorte de `traffic.KINDS`) devant le lanceur pendant ses
    #                                   effets à durée : la séance le dessine et en donne l'abri (voiture d'équipe, GP4)

    def __post_init__(self) -> None:
        if self.target not in TARGETS or self.form not in FORMS:
            raise ValueError(f"{self.id} : cible {self.target!r} ou forme {self.form!r} inconnue")

    @property
    def shot_kind(self) -> str:
        return self.shot or self.id

    @property
    def label(self) -> str:
        return LABELS[self.id]

    def scaled(self, chaos: float) -> "ItemSpec":
        return replace(self, self_fx=tuple(e.scaled(chaos) for e in self.self_fx),
                       hit_fx=tuple(e.scaled(chaos) for e in self.hit_fx),
                       splash_fx=tuple(e.scaled(chaos) for e in self.splash_fx))


SLIP = (EffectSpec("slip", 0.7),)
_GEL = dict(target="self", form="instant", self_fx=(EffectSpec("kick", 1.3),))
_BOTTLE = dict(target="behind", form="dropped", hit_fx=SLIP, ttl_s=90.0)
_MUSETTE = dict(target="ahead", form="projectile", hit_fx=SLIP, speed_rel_mps=15.0, range_m=400.0, ttl_s=60.0)

DEFAULT_ITEMS: dict[str, ItemSpec] = {s.id: s for s in (
    ItemSpec("gel", **_GEL),
    ItemSpec("gel_x3", charges=3, **_GEL),
    ItemSpec("bottle", **_BOTTLE),
    ItemSpec("bottle_x3", charges=3, shot="bottle", **_BOTTLE),
    ItemSpec("musette", **_MUSETTE),
    ItemSpec("musette_x3", charges=3, shot="musette", **_MUSETTE),
    ItemSpec("homing", target="ahead", form="projectile", hit_fx=SLIP, speed_rel_mps=15.0, range_m=600.0,
             ttl_s=40.0, lock_m=200.0),
    ItemSpec("storm", target="leader", form="projectile", hit_fx=(EffectSpec("cap", 0.5, 1.5),),
             speed_rel_mps=30.0, ttl_s=120.0, splash_m=10.0, splash_fx=SLIP, warn_s=1.0),
    ItemSpec("star", target="self", form="duration", hit_fx=SLIP, radius_m=1.5,
             self_fx=(EffectSpec("immune", 1.0, 8.0), EffectSpec("speed_floor", 1.2, 8.0))),
    ItemSpec("bell", target="near", form="instant", hit_fx=SLIP, radius_m=5.0, clear_m=15.0),
    ItemSpec("headwind", target="ahead", form="duration", hit_fx=(EffectSpec("wind", 5.0, 6.0),)),
    ItemSpec("team_car", target="self", form="duration",
             self_fx=(EffectSpec("immune", 1.0, 6.0), EffectSpec("speed_floor", 1.5, 6.0),
                      EffectSpec("cap", 1.5, 6.0)), escort="car_a"),
    ItemSpec("stealth", target="self", form="duration", self_fx=(EffectSpec("breakaway", 1.0, 10.0),),
             steal_m=50.0),
)}


@dataclass(frozen=True)
class ItemTable:
    items: Mapping[str, ItemSpec] = field(default_factory=lambda: dict(DEFAULT_ITEMS))
    weights: Mapping[str, Mapping[str, float]] = field(default_factory=lambda: {
        b: dict(w) for b, w in DEFAULT_WEIGHTS.items()})
    enabled: frozenset[str] = frozenset(ITEM_IDS)   # section [items] : objets joués (lot GP2)

    def scaled(self, chaos: float) -> "ItemTable":
        return replace(self, items={k: v.scaled(chaos) for k, v in self.items.items()})


DEFAULT_TABLE = ItemTable()


def _num(where: str, value, lo: float, hi: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not lo <= value <= hi:
        raise GrandPrixError(f"{where} : {value!r} refusé ({lo:g} à {hi:g})")
    return float(value)


def _item_from(spec: ItemSpec, data: Mapping) -> ItemSpec:
    if not isinstance(data, Mapping):
        raise GrandPrixError(f"[{spec.id}] : table attendue")
    fx_self, fx_hit, fx_splash, changes = list(spec.self_fx), list(spec.hit_fx), list(spec.splash_fx), {}
    for key, value in data.items():
        where = f"{spec.id}.{key}"
        if key in EFFECTS:
            if key not in FACTOR_BOUNDS:
                raise GrandPrixError(f"{where} : effet sans facteur réglable")
            found = False
            for fx in (fx_self, fx_hit, fx_splash):
                for i, e in enumerate(fx):
                    if e.effect == key:
                        fx[i] = replace(e, factor=_num(where, value, *FACTOR_BOUNDS[key]))
                        found = True
            if not found:
                raise GrandPrixError(f"{where} : effet absent de cet objet")
        elif key == "duration_s":
            d = _num(where, value, *PARAM_BOUNDS[key])
            fx_self = [replace(e, duration_s=d) if e.effect in DURATIONS else e for e in fx_self]
            fx_hit = [replace(e, duration_s=d) if e.effect in DURATIONS else e for e in fx_hit]
        elif key in PARAM_BOUNDS:
            current = getattr(spec, key)
            if not current:
                raise GrandPrixError(f"{where} : paramètre sans objet pour {spec.id}")
            changes[key] = _num(where, value, *PARAM_BOUNDS[key])
        else:
            raise GrandPrixError(f"{where} : clé inconnue")
    return replace(spec, self_fx=tuple(fx_self), hit_fx=tuple(fx_hit), splash_fx=tuple(fx_splash), **changes)


def table_from(data: Mapping) -> ItemTable:
    items = dict(DEFAULT_ITEMS)
    weights = {b: dict(w) for b, w in DEFAULT_WEIGHTS.items()}
    enabled = set(ITEM_IDS)
    for key, value in data.items():
        if key == "items":
            if not isinstance(value, Mapping):
                raise GrandPrixError("[items] : table attendue")
            for item, on in value.items():
                if item not in items:
                    raise GrandPrixError(f"items.{item} : objet inconnu")
                if not isinstance(on, bool):
                    raise GrandPrixError(f"items.{item} : true ou false attendu")
                (enabled.add if on else enabled.discard)(item)
        elif key in items:
            items[key] = _item_from(items[key], value)
        elif key == "weights":
            if not isinstance(value, Mapping):
                raise GrandPrixError("[weights] : table attendue")
            for bracket, row in value.items():
                if bracket not in BRACKETS or not isinstance(row, Mapping):
                    raise GrandPrixError(f"weights.{bracket} : tranche inconnue ({', '.join(BRACKETS)})")
                for item, w in row.items():
                    if item not in items:
                        raise GrandPrixError(f"weights.{bracket}.{item} : objet inconnu")
                    weights[bracket][item] = _num(f"weights.{bracket}.{item}", w, 0.0, WEIGHT_MAX)
        else:
            raise GrandPrixError(f"[{key}] : objet inconnu ({', '.join(ITEM_IDS)})")
    return ItemTable(items, weights, frozenset(enabled))


def load_table(path: Path | None = None) -> ItemTable:
    """Table des objets : celle par défaut, modifiée par `~/OpenRide/grandprix.toml` s'il existe."""
    path = path or GRANDPRIX_FILE
    if not path.exists():
        return DEFAULT_TABLE
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise GrandPrixError(f"{path} illisible : {exc}") from exc
    return table_from(data)


def options_list(table: ItemTable) -> list[dict]:
    """Objets pour l'écran « Objets » du menu (message `mode_options`, lot GP2) : un élément par objet."""
    return [{"id": i, "label": LABELS[i], "family": FAMILIES[i], "on": i in table.enabled} for i in ITEM_IDS]


def with_item(table: ItemTable, item: str, on: bool) -> ItemTable:
    """Table avec un objet joué ou coupé ; un objet inconnu est refusé."""
    if item not in ITEM_IDS:
        raise GrandPrixError(f"objet inconnu : {item!r} ({', '.join(ITEM_IDS)})")
    enabled = set(table.enabled)
    (enabled.add if on else enabled.discard)(item)
    return replace(table, enabled=frozenset(enabled))
