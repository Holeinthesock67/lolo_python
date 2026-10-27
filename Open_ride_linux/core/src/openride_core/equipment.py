"""Équipement de la série V (lot V3) : catalogue, effets bornés, conseil et temps gagné.

Le catalogue est la liste `[[items]]` de `data/progression.toml` (chargée par
`progression.load_table`). Cadre et roues changent la masse et le CdA, donc la vitesse
virtuelle seulement : la résistance au trainer ne dépend pas de l'équipement (branchement dans
la séance : lot V11). Les autres emplacements sont de l'apparence.

Bornes du plan V §2.2, cadre et roues ensemble : la masse ne baisse jamais de plus de 3 % de la
masse totale de départ, le CdA de plus de 6 %. Les hausses ne sont pas bornées. Les bonus de la
série T se composent ensuite par multiplication (lot T6).
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass, replace
from typing import Any, Iterable

from .physics import DT_DEFAULT, PhysicsParams, RiderPhysics
from .progression import Table

SLOTS = ("frame", "wheels", "helmet", "kit", "socks", "glasses")
PHYSICAL_SLOTS = ("frame", "wheels")
TERRAINS = ("flat", "rolling", "climb", "all")
TERRAIN_NAMES = {"flat": "plat", "rolling": "vallonné", "climb": "col", "all": "tout terrain"}
SLOT_NAMES = {"frame": "Cadre", "wheels": "Roues", "helmet": "Casque", "kit": "Tenue",
              "socks": "Chaussettes", "glasses": "Lunettes"}

MAX_MASS_DROP = 0.03      # fraction de la masse totale
MAX_CDA_DROP = 0.06       # fraction du CdA
ITEM_MASS_RANGE = (-2.0, 1.0)     # kg, par pièce
ITEM_CDA_RANGE = (-5.0, 0.0)      # %, par pièce
FLAT_MAX_M_PER_KM = 5.0
CLIMB_MIN_M_PER_KM = 15.0

_ITEM_KEYS = {"id": str, "slot": str, "name": str, "level": int, "price": int,
              "mass_delta_kg": float, "cda_delta_pct": float, "terrain": str, "look": str,
              "default": bool, "buyable": bool}


class CatalogueError(Exception):
    """Catalogue invalide (le message nomme la pièce fautive)."""


@dataclass(frozen=True)
class Item:
    id: str
    slot: str
    name: str
    level: int = 1
    price: int = 0
    mass_delta_kg: float = 0.0
    cda_delta_pct: float = 0.0
    terrain: str = "all"
    look: str = ""
    default: bool = False
    buyable: bool = True     # faux : offerte par un défi seulement

    @property
    def physical(self) -> bool:
        return self.slot in PHYSICAL_SLOTS


@dataclass
class Catalogue:
    items: dict[str, Item]

    def __getitem__(self, item_id: str) -> Item:
        return self.items[item_id]

    def __contains__(self, item_id: object) -> bool:
        return item_id in self.items

    def by_slot(self, slot: str) -> list[Item]:
        return sorted((i for i in self.items.values() if i.slot == slot), key=lambda i: (i.level, i.price, i.id))

    def defaults(self) -> dict[str, str]:
        return {i.slot: i.id for i in self.items.values() if i.default}


def _typed(value: Any, expected: type, where: str) -> Any:
    if expected is bool:
        if not isinstance(value, bool):
            raise CatalogueError(f"{where} : booléen attendu")
        return value
    if expected in (int, float):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise CatalogueError(f"{where} : nombre attendu")
        if expected is int and int(value) != value:
            raise CatalogueError(f"{where} : entier attendu")
        return expected(value)
    if not isinstance(value, expected) or not value:
        raise CatalogueError(f"{where} : texte non vide attendu")
    return value


def load_catalogue(table: Table) -> Catalogue:
    """Catalogue vérifié depuis les tables chargées ; lève `CatalogueError`."""
    raw = table.data.get("items", [])
    if not isinstance(raw, list) or not raw:
        raise CatalogueError("[[items]] : liste de pièces absente")
    items: dict[str, Item] = {}
    for n, entry in enumerate(raw, start=1):
        label = entry.get("id", f"n° {n}") if isinstance(entry, dict) else f"n° {n}"
        where = f"pièce « {label} »"
        if not isinstance(entry, dict):
            raise CatalogueError(f"{where} : table attendue")
        for key in entry:
            if key not in _ITEM_KEYS:
                raise CatalogueError(f"{where}, {key} : clé inconnue")
        for key in ("id", "slot", "name"):
            if key not in entry:
                raise CatalogueError(f"{where}, {key} : clé manquante")
        values = {k: _typed(v, _ITEM_KEYS[k], f"{where}, {k}") for k, v in entry.items()}
        item = Item(**values)
        if item.id in items:
            raise CatalogueError(f"{where} : identifiant en double")
        if item.slot not in SLOTS:
            raise CatalogueError(f"{where}, slot : « {item.slot} » inconnu (attendu : {', '.join(SLOTS)})")
        if item.terrain not in TERRAINS:
            raise CatalogueError(f"{where}, terrain : « {item.terrain} » inconnu")
        if item.level < 1 or item.price < 0:
            raise CatalogueError(f"{where} : niveau d'au moins 1 et prix positif attendus")
        if not item.physical and (item.mass_delta_kg or item.cda_delta_pct):
            raise CatalogueError(f"{where} : une pièce d'apparence n'a pas d'effet")
        lo, hi = ITEM_MASS_RANGE
        if not lo <= item.mass_delta_kg <= hi:
            raise CatalogueError(f"{where}, mass_delta_kg : hors de {lo:g} à {hi:g} kg")
        lo, hi = ITEM_CDA_RANGE
        if not lo <= item.cda_delta_pct <= hi:
            raise CatalogueError(f"{where}, cda_delta_pct : hors de {lo:g} à {hi:g} %")
        items[item.id] = item
    cat = Catalogue(items)
    for slot in SLOTS:
        defaults = [i.id for i in cat.by_slot(slot) if i.default]
        if len(defaults) != 1:
            raise CatalogueError(f"emplacement {slot} : une pièce par défaut attendue, {len(defaults)} trouvée(s)")
        if cat[defaults[0]].mass_delta_kg or cat[defaults[0]].cda_delta_pct:
            raise CatalogueError(f"pièce « {defaults[0]} » : la pièce par défaut n'a pas d'effet")
    for ch in table.challenges:
        if ch.reward and ch.reward not in cat:
            raise CatalogueError(f"défi « {ch.id} » : récompense « {ch.reward} » absente du catalogue")
    return cat


# --- effets ---------------------------------------------------------------------------------

def physical_deltas(loadout: dict[str, str], catalogue: Catalogue) -> tuple[float, float]:
    """Somme brute (non bornée) des deltas de masse (kg) et de CdA (%) du cadre et des roues."""
    mass = cda = 0.0
    for slot in PHYSICAL_SLOTS:
        item = catalogue.items.get(loadout.get(slot, ""))
        if item is not None:
            mass += item.mass_delta_kg
            cda += item.cda_delta_pct
    return mass, cda


def apply_equipment(base: PhysicsParams, loadout: dict[str, str], catalogue: Catalogue) -> PhysicsParams:
    """`PhysicsParams` avec l'équipement, dans les bornes du plan ; `crr` et rendement inchangés."""
    mass_delta, cda_pct = physical_deltas(loadout, catalogue)
    mass_delta = max(mass_delta, -MAX_MASS_DROP * base.mass_kg)
    cda_factor = max(1.0 + cda_pct / 100.0, 1.0 - MAX_CDA_DROP)
    return replace(base, mass_kg=base.mass_kg + mass_delta, cda_m2=base.cda_m2 * cda_factor)


# --- conseil par terrain -----------------------------------------------------------------

def route_terrain(length_m: float, climb_m: float) -> str:
    """`flat` sous 5 m de D+ par km, `climb` au-delà de 15 m/km, `rolling` entre les deux."""
    if length_m <= 0:
        return "flat"
    per_km = climb_m / (length_m / 1000.0)
    if per_km < FLAT_MAX_M_PER_KM:
        return "flat"
    if per_km > CLIMB_MIN_M_PER_KM:
        return "climb"
    return "rolling"


def advice(terrain: str, catalogue: Catalogue) -> dict[str, Item]:
    """Cadre et roues conseillés : même terrain (le plus haut niveau), sinon la pièce `all`."""
    out: dict[str, Item] = {}
    for slot in PHYSICAL_SLOTS:
        matching = [i for i in catalogue.by_slot(slot) if i.terrain == terrain]
        out[slot] = matching[-1] if matching else next(i for i in catalogue.by_slot(slot) if i.default)
    return out


def fiche(item: Item) -> str:
    """Fiche d'une pièce : « Grimpeur — −1,5 kg, CdA = — Conseillé : col »."""
    if not item.physical:
        return f"{item.name} — apparence"
    mass = "masse =" if not item.mass_delta_kg else f"{_signed(item.mass_delta_kg)} kg"
    cda = "CdA =" if not item.cda_delta_pct else f"CdA {_signed(item.cda_delta_pct)} %"
    return f"{item.name} — {mass}, {cda} — Conseillé : {TERRAIN_NAMES[item.terrain]}"


def _signed(x: float) -> str:
    """« −1,5 », « +0,5 » : signe typographique et virgule décimale."""
    return ("−" if x < 0 else "+") + f"{abs(x):.1f}".replace(".", ",")


# --- temps gagné par l'équipement -------------------------------------------------------

class _Profile:
    """Pente et altitude du journal en fonction de la distance (paliers entre deux relevés)."""

    def __init__(self, records: list[dict]) -> None:
        pts = sorted((float(r["distance"]), float(r.get("grade") or 0.0), float(r.get("alt") or 0.0))
                     for r in records if r.get("distance") is not None)
        self.s = [p[0] for p in pts]
        self.grade = [p[1] for p in pts]
        self.alt = [p[2] for p in pts]

    def at(self, s: float) -> tuple[float, float]:
        i = max(bisect.bisect_right(self.s, s) - 1, 0)
        return self.grade[i], self.alt[i]


def _simulate(params: PhysicsParams, powers: list[float], profile: _Profile, v0: float,
              dt: float) -> list[tuple[float, float]]:
    """Trajectoire (temps, distance) en rejouant la puissance seconde par seconde."""
    rider = RiderPhysics(params, s=profile.s[0], v=v0)
    steps = max(int(round(1.0 / dt)), 1)
    out = [(0.0, rider.s)]
    t = 0.0
    for p in powers:
        for _ in range(steps):
            grade, alt = profile.at(rider.s)
            rider.step(p, grade, alt, dt=1.0 / steps)
        t += 1.0
        out.append((t, rider.s))
    return out


def _time_at(traj: list[tuple[float, float]], s: float) -> float | None:
    """Temps de passage à la distance `s`, interpolé ; None si elle n'est jamais atteinte."""
    for (t0, s0), (t1, s1) in zip(traj, traj[1:]):
        if s1 >= s:
            if s1 == s0:
                return t1
            return t0 + (t1 - t0) * (s - s0) / (s1 - s0)
    return None


def equipment_time_gain(records: Iterable[dict], equipped: PhysicsParams, base: PhysicsParams,
                        s_start: float | None = None, s_end: float | None = None,
                        dt: float = DT_DEFAULT) -> float | None:
    """Temps gagné (négatif) ou perdu par l'équipement : même puissance mesurée, même profil.

    Sur toute la séance, la distance comparée est la plus courte des deux simulations ; sur un
    segment `[s_start, s_end]`, le temps entre les deux bornes. None sans puissance ni distance,
    ou si une borne n'est pas atteinte.
    """
    recs = [r for r in records if r.get("kind", "record") == "record"]
    if not recs or all(r.get("power") is None for r in recs):
        return None
    profile = _Profile(recs)
    if not profile.s or profile.s[-1] <= profile.s[0]:
        return None
    if equipped == base:
        return 0.0
    powers = [float(r.get("power") or 0.0) for r in sorted(recs, key=lambda r: float(r.get("t") or 0.0))]
    v0 = float(recs[0].get("speed") or 0.0)
    a = _simulate(equipped, powers, profile, v0, dt)
    b = _simulate(base, powers, profile, v0, dt)
    start = profile.s[0] if s_start is None else s_start
    end = min(a[-1][1], b[-1][1]) if s_end is None else s_end
    if end <= start:
        return None
    times = [_time_at(tr, end) for tr in (a, b)] + [_time_at(tr, start) for tr in (a, b)]
    if any(x is None for x in times):
        return None
    return (times[0] - times[2]) - (times[1] - times[3])


def gain_text(item_name: str, slot: str, seconds: float, where: str = "sur la séance") -> str:
    """« Cadre Grimpeur : −14 s dans la montée » (signe moins si l'équipement fait gagner)."""
    sign = "−" if seconds < 0 else "+"
    return f"{SLOT_NAMES.get(slot, slot)} {item_name} : {sign}{abs(seconds):.0f} s {where}"
