"""Enchaînement de parcours en session libre (série PE, lot PE1, module pur).

Demande du propriétaire du 22 novembre 2026 : à l'arrivée d'un parcours en ligne en session libre, enchaîner
sur un autre parcours sans s'arrêter ni repasser par l'accueil, avec un seul enregistrement pour toute la
séance (cadrage `plans/CADRAGE_ENCHAINEMENT_PARCOURS_2026-11-22.md`).

Ce module ne fait aucune entrée-sortie. Il dit :
- si la séance peut enchaîner (`refusal`, raison écrite sinon) ;
- quels parcours proposer ensuite (`candidates`), le premier pas encore roulé dans la séance en tête ;
- où en est l'enchaînement (`ChainSession` : phases « choix » puis « en route », parcours roulés) ;
- la ligne de journal de chaque nouveau parcours (`kind` = `chain`, `event` = `route_start`), qui devient un
  tour du FIT (`fit_export.LAP_LINES`).

Rien ne se décide sans le joueur (réponse du 22/11) : pas de choix ni de fin automatique ; tant qu'il ne
choisit pas, il roule au calme (demi-tour de l'arrivée, fin de séance commune RT2).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .mode_routes import is_free

JOURNAL_KIND = "chain"
EVENT_ROUTE_START = "route_start"

PHASE_CHOOSE = "choose"   # liste « Parcours suivant » à l'écran
PHASE_WARP = "warp"       # hyperespace : nouveau monde en préparation
PHASES = (PHASE_CHOOSE, PHASE_WARP)

# Raisons écrites d'un refus (mots simples : quoi et pourquoi). Le joueur ne les voit que s'il demande
# d'enchaîner quand ce n'est pas possible ; le bouton n'est pas proposé dans ces cas.
REFUSALS: dict[str, str] = {
    "not_free": "Enchaîner un parcours n'existe qu'en session libre.",
    "workout": "Entraînement en cours : il continue sur ce parcours jusqu'à la fin.",
    "open_world": "Le monde ouvert a sa propre route : pas d'enchaînement.",
    "loop": "Ce parcours est une boucle : il ne finit pas, rien à enchaîner.",
    "no_route": "Aucun autre parcours prêt à rouler.",
    "busy": "Le parcours suivant est déjà en préparation.",
}


@dataclass(frozen=True)
class ChainContext:
    """Ce que la séance sait au moment de l'arrivée (lu par `session.py`, aucun objet de la séance ici)."""
    start_mode: str              # `start.mode` : « ride » = session libre
    rogue: bool = False          # run Cyber-Rogue
    open_world: bool = False
    league: bool = False         # manche de ligue (Course de la ligue d'hiver)
    workout_running: bool = False   # entraînement ERG ou test de FTP pas fini (`workout_done` absent)
    route_is_loop: bool = False
    enabled: bool = True         # réglage « Proposer d'enchaîner à l'arrivée »


def refusal(ctx: ChainContext) -> str | None:
    """Code du refus (clé de `REFUSALS`), ou None si la séance peut enchaîner à son arrivée."""
    if not ctx.enabled or ctx.start_mode != "ride" or ctx.rogue or ctx.league:
        return "not_free"
    if ctx.open_world:
        return "open_world"
    if ctx.workout_running:
        return "workout"
    if ctx.route_is_loop:
        return "loop"
    return None


@dataclass(frozen=True)
class Candidate:
    """Parcours proposé ensuite (une ligne de la liste « Parcours suivant »)."""
    id: str
    name: str
    length_m: float | None
    ascent_m: float | None
    loop: bool
    ridden: bool                 # déjà roulé dans cette séance

    def to_dict(self) -> dict:
        out: dict[str, Any] = {"id": self.id, "name": self.name}
        if self.length_m is not None:
            out["length_m"] = round(self.length_m)
        if self.ascent_m is not None:
            out["ascent_m"] = round(self.ascent_m)
        if self.loop:
            out["loop"] = True
        if self.ridden:
            out["ridden"] = True
        return out


def _ascent(stats: Any) -> float | None:
    if not isinstance(stats, dict):
        return None
    for key in ("gain_m", "ascent_m"):   # fiche calculée (route_stats, lot O15)
        v = stats.get(key)
        if isinstance(v, (int, float)):
            return float(v)
    return None


def candidates(entries: Iterable[Any], current_id: str | None, ridden: Iterable[str]) -> list[Candidate]:
    """Parcours proposés après `current_id` : prêts, libres (pas réservés à un mode, lots GP13 et GPL1 : liste générale « Parcours »), autres que celui
    qu'on vient de finir. Ceux pas encore roulés dans la séance d'abord, puis l'ordre du catalogue.

    `entries` : `catalog.RouteEntry` (ou tout objet aux mêmes attributs : id, name, status, length_m,
    route_type, stats, library)."""
    done = set(ridden)
    fresh: list[Candidate] = []
    again: list[Candidate] = []
    for e in entries:
        if getattr(e, "status", None) != "ready" or e.id == current_id:
            continue
        if not is_free(getattr(e, "library", None) or {}, getattr(e, "route_type", None)):
            continue
        c = Candidate(id=str(e.id), name=str(getattr(e, "name", "") or e.id),
                      length_m=getattr(e, "length_m", None), ascent_m=_ascent(getattr(e, "stats", None)),
                      loop=getattr(e, "route_type", None) == "loop", ridden=e.id in done)
        (again if c.ridden else fresh).append(c)
    return fresh + again


@dataclass
class Leg:
    """Un parcours roulé dans la séance (un tour du FIT)."""
    route_id: str
    start_ts: float
    start_distance_m: float


@dataclass
class ChainSession:
    """Suivi de l'enchaînement pendant une séance libre. La séance reste `RUNNING` dans toutes les phases."""
    legs: list[Leg] = field(default_factory=list)
    phase: str | None = None
    offer: list[Candidate] = field(default_factory=list)
    target: str | None = None    # parcours choisi, en préparation (phase « en route »)

    @classmethod
    def begin(cls, route_id: str, ts: float) -> "ChainSession":
        return cls(legs=[Leg(route_id, ts, 0.0)])

    @property
    def current(self) -> str | None:
        return self.legs[-1].route_id if self.legs else None

    @property
    def ridden(self) -> list[str]:
        return [leg.route_id for leg in self.legs]

    def open_choice(self, entries: Iterable[Any]) -> str | None:
        """« Enchaîner un autre parcours » appuyé : liste « Parcours suivant ». Code du refus ou None."""
        if self.phase == PHASE_WARP:
            return "busy"
        offer = candidates(entries, self.current, self.ridden)
        if not offer:
            return "no_route"
        self.offer = offer
        self.phase = PHASE_CHOOSE
        return None

    def cancel(self) -> None:
        """Choix abandonné (retour à l'écran d'arrivée) : on continue de rouler au calme."""
        if self.phase == PHASE_CHOOSE:
            self.phase = None
            self.offer = []

    def choose(self, route_id: str) -> str | None:
        """Parcours choisi dans la liste : début de l'hyperespace. Code du refus ou None."""
        if self.phase == PHASE_WARP:
            return "busy"
        if self.phase != PHASE_CHOOSE or route_id not in {c.id for c in self.offer}:
            return "no_route"
        self.target = route_id
        self.phase = PHASE_WARP
        return None

    def fail(self) -> None:
        """Le parcours choisi n'a pas pu être lu : retour à la liste, sans lui."""
        if self.phase == PHASE_WARP:
            self.offer = [c for c in self.offer if c.id != self.target]
            self.target = None
            self.phase = PHASE_CHOOSE if self.offer else None

    def arrive(self, ts: float, distance_m: float) -> dict:
        """Nouveau monde prêt (`scene_ready` du parcours choisi) : nouveau parcours de la séance. Renvoie la
        ligne de journal à écrire (tour du FIT)."""
        assert self.phase == PHASE_WARP and self.target is not None
        leg = Leg(self.target, ts, distance_m)
        self.legs.append(leg)
        self.phase, self.target, self.offer = None, None, []
        return journal_line(leg, len(self.legs))

    def to_state(self, can_chain: bool) -> dict | None:
        """Objet `chain` de la trame `state` ; None si rien à montrer (séance qui ne peut pas enchaîner)."""
        if not can_chain and self.phase is None:
            return None
        out: dict[str, Any] = {"leg": len(self.legs), "can_chain": bool(can_chain)}
        if self.phase is not None:
            out["phase"] = self.phase
        if self.phase == PHASE_CHOOSE:
            out["offer"] = [c.to_dict() for c in self.offer]
        if self.phase == PHASE_WARP and self.target is not None:
            name = next((c.name for c in self.offer if c.id == self.target), self.target)
            out["target"] = {"id": self.target, "name": name}
        return out


def journal_line(leg: Leg, index: int) -> dict:
    """Ligne `chain` du journal : début du parcours n° `index` de la séance (tour du FIT)."""
    return {"kind": JOURNAL_KIND, "event": EVENT_ROUTE_START, "ts": round(leg.start_ts, 3),
            "route_id": leg.route_id, "leg": index, "distance": round(leg.start_distance_m, 2)}


def legs_of(lines: Iterable[dict], first_route_id: str | None) -> list[tuple[str, float]]:
    """Parcours roulés d'un journal relu (reprise, records) : [(route_id, ts de début)], le premier étant celui
    de l'en-tête (ts 0 : depuis le début de la séance)."""
    out: list[tuple[str, float]] = [(first_route_id, 0.0)] if first_route_id else []
    for ln in lines:
        if ln.get("kind") == JOURNAL_KIND and ln.get("event") == EVENT_ROUTE_START and ln.get("route_id"):
            out.append((str(ln["route_id"]), float(ln.get("ts", 0.0))))
    return out


def route_at(legs: list[tuple[str, float]], ts: float) -> str | None:
    """Parcours roulé à l'instant `ts` d'après `legs_of` (records de segments rangés sous le bon parcours)."""
    current = None
    for route_id, start in legs:
        if ts >= start:
            current = route_id
        else:
            break
    return current
