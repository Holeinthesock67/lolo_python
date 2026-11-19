"""Registre unique de la chaussée (lot AS11, série AS) : une règle commune à tous les usagers de la route.

Module pur, sans entrée-sortie. À chaque pas, après que chacun a avancé selon son intention (placement des coureurs
d'AS2 à PL1, tactique des bots, Grand Prix, circulation d'AS6, cyclistes du décor d'AS7 à AS10), la séance inscrit
tous les usagers proches dans le même registre, dans le même repère (celui du sens de marche, N23 : u = L − s à
rebours) et dans les deux voies : cycliste, voitures d'équipe, bots, véhicules, cyclistes du décor (un groupe est un
seul usager : la boîte de ses membres) et objets posés sur la chaussée.

Une seule règle : **personne ne chevauche personne**, gabarits de la table `GABARITS` plus une marge (`MARGIN_LEN_M`,
`MARGIN_WIDTH_M`) qui couvre l'extrapolation de l'engine entre deux listes. Les usagers sont placés un à un par ordre
de priorité (`RANK`, le plus prioritaire d'abord) ; un usager qui chevauche un usager déjà placé prend la plus petite
place libre voisine (en arrière ou en avant dans son couloir, ou à côté, entre les bords permis), au coût
`|Δs| + LATERAL_COST × |Δécart|`. Un usager dont la position n'est pas libre (`move_s` faux : le cycliste, un bot que
sa physique fait avancer) ne bouge qu'en travers ; le cycliste ne bouge jamais. Un usager reculé derrière un autre de
son sens prend au plus sa vitesse. Chaque correction est rendue à la séance (`Correction`), qui l'écrit dans le
modèle de l'usager et la compte au journal : elle doit rester rare, la règle d'intention de chacun étant censée
l'éviter ; ce compte dit au banc laquelle a manqué, sans contact à l'écran.

Objets posés (boîtes et objets du Grand Prix) : obstacles fixes pour la circulation et les cyclistes du décor ; les
coureurs les traversent (c'est le jeu).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace

from . import draft as draft_mod
from . import traffic as traffic_mod

BIKE_HALF_LEN_M = 0.5 * draft_mod.BIKE_LENGTH_M          # 0,85 m : `living_decor.CONTACT_BIKE_HALF_M`
BIKE_HALF_WIDTH_M = 0.5 * draft_mod.RIDER_WIDTH_M        # 0,3 m : `traffic_model.RIDER_HALF_WIDTH_M`
OBJECT_HALF_M = 0.4                                      # boîte ou objet posé du Grand Prix
MARGIN_LEN_M = 0.4      # en long : extrapolation de l'engine entre deux listes et arrondi des listes au décimètre (lot AS11)
RACER_MARGIN_M = 0.0     # entre deux coureurs (roue dans la roue, en diagonale) : le contact seulement, leur placement fait le reste
MARGIN_WIDTH_M = 0.05   # en travers
LATERAL_COST = 3.0      # un décalage en travers se voit plus qu'un recul de même longueur
SEARCH_STEPS = 24       # places essayées au plus pour un usager coincé
ROAD_HALF_M = 3.0       # demi-chaussée de 6 m (`draft.LANE_MAX_M` + `LANE_EDGE_M`)

# Gabarits : (demi-longueur, demi-largeur) de chaque sorte d'usager, une seule table pour tout le core
GABARITS: dict[str, tuple[float, float]] = {"bike": (BIKE_HALF_LEN_M, BIKE_HALF_WIDTH_M),
                                            "object": (OBJECT_HALF_M, OBJECT_HALF_M)}
GABARITS.update({k: (0.5 * float(v["length"]), float(v["half_width"])) for k, v in traffic_mod.KINDS.items()})

# Priorités : le plus petit est placé d'abord et ne cède jamais à un plus grand
RANK = {"object": 0, "rider": 1, "escort": 2, "bot": 3, "vehicle": 4, "cyclist": 5}
RACERS = ("rider", "escort", "bot")


@dataclass
class Body:
    """Un usager de la chaussée : centre `s` (repère du sens de marche), écart à l'axe `lat` (positif à droite),
    vitesse `v` (m/s, positive dans son sens `dir`), demi-longueur et demi-largeur ; `role` : sa priorité (`RANK`).
    `lat_min`, `lat_max` : écarts permis à son centre (chaussée) ; `move_s` faux : il ne recule ni n'avance."""

    id: str
    role: str
    s: float
    lat: float
    v: float = 0.0
    dir: int = 1
    half_len: float = BIKE_HALF_LEN_M
    half_width: float = BIKE_HALF_WIDTH_M
    lat_min: float = -3.0
    lat_max: float = 3.0
    move_s: bool = True
    name: str = ""
    group: str = ""          # usagers d'un même bloc (coureur et sa voiture d'équipe) : ils ne se touchent pas
    push: bool = True        # peut être avancé (faux pour un coureur : retenu derrière seulement, jamais avancé)

    @property
    def rank(self) -> int:
        return RANK[self.role]


@dataclass
class Correction:
    """Place corrigée d'un usager : écarts en long et en travers, nouvelle vitesse, usager qu'il touchait."""

    id: str
    role: str
    ds: float
    dlat: float
    v: float
    against: str
    against_role: str
    resolved: bool = True


@dataclass
class Report:
    corrections: list[Correction] = field(default_factory=list)
    unresolved: int = 0


def gabarit(kind: str) -> tuple[float, float]:
    return GABARITS.get(kind, GABARITS["bike"])


def _solid(a: Body, b: Body) -> bool:
    """Les coureurs traversent les objets posés (boîtes du Grand Prix) ; tous les autres usagers se touchent, sauf
    deux usagers d'un même bloc (`group`)."""
    if a.group and a.group == b.group:
        return False
    if "object" in (a.role, b.role):
        other = b if a.role == "object" else a
        return other.role not in RACERS and other.role != "object"
    return True


def _racers(a: Body, b: Body) -> bool:
    return a.role in RACERS and b.role in RACERS


def margin_len(a: Body, b: Body) -> float:
    """Marge en long : aucune entre deux coureurs ni entre un coureur et un véhicule (le placement des coureurs les
    tient roue dans la roue, ou à l'abri derrière le véhicule, lot AS6), sinon `MARGIN_LEN_M`."""
    if _racers(a, b) or (a.role in RACERS and b.role == "vehicle") or (b.role in RACERS and a.role == "vehicle"):
        return RACER_MARGIN_M
    return MARGIN_LEN_M


def margin_width(a: Body, b: Body) -> float:
    return RACER_MARGIN_M if _racers(a, b) else MARGIN_WIDTH_M


def overlaps(a: Body, b: Body, margin: bool = True) -> bool:
    """Vrai si les gabarits de `a` et `b` se chevauchent (marges comprises si `margin`)."""
    ml = margin_len(a, b) if margin else 0.0
    mw = margin_width(a, b) if margin else 0.0
    return abs(a.s - b.s) < a.half_len + b.half_len + ml and abs(a.lat - b.lat) < a.half_width + b.half_width + mw


def contacts(bodies: Sequence[Body]) -> list[tuple[Body, Body]]:
    """Paires qui se touchent, sans marge : le critère de `living_decor._count_contacts` de l'engine."""
    out = []
    for i, a in enumerate(bodies):
        for b in bodies[i + 1:]:
            if _solid(a, b) and overlaps(a, b, margin=False):
                out.append((a, b))
    return out


def _candidates(body: Body, hits: Sequence[Body]) -> list[tuple[float, float]]:
    """Places voisines à essayer : juste derrière ou devant chaque usager touché, ou à côté de lui."""
    out: list[tuple[float, float]] = []
    eps = 1e-3
    for h in hits:
        reach = body.half_len + h.half_len + margin_len(body, h) + eps
        side = body.half_width + h.half_width + margin_width(body, h) + eps
        if body.move_s:
            out.append((h.s - body.dir * reach, body.lat))
            if body.push:
                out.append((h.s + body.dir * reach, body.lat))
        for lat in (h.lat - side, h.lat + side):
            if body.lat_min <= lat <= body.lat_max:
                out.append((body.s, lat))
    return out


def _place(body: Body, placed: list[Body]) -> tuple[float, float] | None:
    """Plus petite place libre voisine de `body` parmi `placed` ; None si aucune (usager laissé où il est)."""
    hits = [p for p in placed if _solid(body, p) and overlaps(body, p)]
    if not hits:
        return body.s, body.lat
    seen: set[tuple[float, float]] = set()
    frontier = _candidates(body, hits)
    best: tuple[float, float, float] | None = None
    for _ in range(SEARCH_STEPS):
        nxt: list[tuple[float, float]] = []
        for s, lat in frontier:
            key = (round(s, 3), round(lat, 3))
            if key in seen:
                continue
            seen.add(key)
            cost = abs(s - body.s) + LATERAL_COST * abs(lat - body.lat)
            if best is not None and cost >= best[0]:
                continue
            probe = replace(body, s=s, lat=lat)
            more = [p for p in placed if _solid(body, p) and overlaps(probe, p)]
            if not more:
                best = (cost, s, lat)
            else:
                nxt += _candidates(probe, more)
        if not nxt:
            break
        frontier = nxt
    return None if best is None else (best[1], best[2])


def resolve(bodies: Sequence[Body]) -> Report:
    """Place chaque usager, du plus prioritaire au moins prioritaire (à priorité égale, du plus avancé dans son sens
    au plus en retrait) ; corrige en place `s`, `lat` et `v` de ceux qui chevauchaient un usager déjà placé."""
    order = sorted(bodies, key=lambda b: (b.rank, -b.dir * b.s))
    placed: list[Body] = []
    rep = Report()
    for b in order:
        hits = [p for p in placed if _solid(b, p) and overlaps(b, p)]
        if hits and b.role != "rider":
            spot = _place(b, placed)
            first = hits[0]
            if spot is None:
                rep.unresolved += 1
                rep.corrections.append(Correction(b.id, b.role, 0.0, 0.0, b.v, first.id, first.role, False))
            else:
                ds, dlat = spot[0] - b.s, spot[1] - b.lat
                b.s, b.lat = spot
                # reculé derrière un usager de son sens : pas plus vite que lui
                ahead = [p for p in hits if p.dir == b.dir and b.dir * (p.s - b.s) > 0.0
                         and abs(p.lat - b.lat) < p.half_width + b.half_width + margin_width(p, b)]
                if ahead:
                    b.v = min([b.v] + [max(0.0, p.v) for p in ahead])
                # poussé devant un usager plus rapide de son sens (le cycliste, qu'on ne freine jamais) : à sa vitesse,
                # pour que l'affichage, qui l'extrapole entre deux listes, ne le voie pas reculer sur lui
                behind = [p for p in hits if p.dir == b.dir and b.dir * (b.s - p.s) > 0.0
                          and abs(p.lat - b.lat) < p.half_width + b.half_width + margin_width(p, b)]
                if behind and not ahead:
                    b.v = max([b.v] + [max(0.0, p.v) for p in behind])
                rep.corrections.append(Correction(b.id, b.role, ds, dlat, b.v, first.id, first.role))
        placed.append(b)
    return rep


__all__ = ["Body", "Correction", "Report", "GABARITS", "RANK", "gabarit", "overlaps", "contacts", "resolve"]
