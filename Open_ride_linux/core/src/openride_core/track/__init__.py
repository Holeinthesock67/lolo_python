"""Épreuves de piste du vélodrome (série VD, lot VD6) : une règle, un fichier.

`EVENTS` donne, pour chaque épreuve, sa classe, ses réglages (valeurs permises, défaut) et son
plateau (adversaires) ; `make` construit une épreuve depuis ces réglages. Plan : `docs/4.0/PLAN_SERIE_VD.md`
§5 ; cahier : `docs/lots/LOT_VD6_epreuves.md`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..bot_tactics import LEVELS as TACTIC_LEVELS
from .base import LAP_M, ME, Entrant, TrackError, TrackEvent
from .elimination import Elimination
from .free import Free
from .hour import Hour
from .keirin import Keirin
from .madison import Madison
from .omnium import Omnium
from .points import Points
from .pursuit import Pursuit
from .scratch import Scratch
from .team_pursuit import TeamPursuit
from .team_sprint import TeamSprint
from .tempo import Tempo
from .time_trial import TimeTrial


@dataclass(frozen=True)
class Option:
    """Réglage d'une épreuve : identifiant, valeurs permises, défaut."""
    id: str
    values: tuple
    default: Any


@dataclass(frozen=True)
class EventSpec:
    id: str
    cls: type
    opponents: tuple[int, ...]           # nombre d'adversaires permis (bots ou équipes de bots)
    team_size: int = 1                   # coureurs par équipe (1 : épreuve individuelle)
    options: tuple[Option, ...] = ()
    fixed: dict = field(default_factory=dict)
    erg: bool = False                    # la séance libre seule accepte l'ERG (plan §5)


_MASS = tuple(range(3, 12))
EVENTS: dict[str, EventSpec] = {s.id: s for s in (
    EventSpec("free", Free, tuple(range(0, 12)), erg=True),
    EventSpec("pursuit", Pursuit, (0, 1), options=(Option("distance_m", (3000, 4000), 4000),)),
    EventSpec("kilo", TimeTrial, (0,), fixed={"variant": "kilo"}),
    EventSpec("500", TimeTrial, (0,), fixed={"variant": "500"}),
    EventSpec("flying_200", TimeTrial, (0,), fixed={"variant": "flying_200"}),
    EventSpec("hour", Hour, (0,)),
    EventSpec("scratch", Scratch, _MASS, options=(Option("laps", (10, 15, 20, 30, 40, 60), 20),)),
    EventSpec("points", Points, _MASS, options=(Option("laps", (20, 30, 40, 60), 40),)),
    EventSpec("tempo", Tempo, _MASS, options=(Option("laps", (10, 20, 30), 10),)),
    EventSpec("elimination", Elimination, _MASS),
    EventSpec("keirin", Keirin, (3, 4, 5, 6), options=(Option("laps", (6, 8), 8),)),
    EventSpec("omnium", Omnium, _MASS),
    EventSpec("team_sprint", TeamSprint, (0, 1), team_size=3, options=(Option("place", (1, 2, 3), 1),)),
    EventSpec("team_pursuit", TeamPursuit, (0, 1), team_size=4, options=(Option("relay_laps", (0.5, 1.0), 0.5),)),
    EventSpec("madison", Madison, (3, 4, 5), team_size=2, options=(Option("laps", (20, 30, 40), 30),)),
)}


def options(event_id: str) -> list[dict]:
    """Réglages d'une épreuve, pour `list_mode_options` : adversaires d'abord, puis ceux de l'épreuve."""
    spec = EVENTS.get(event_id)
    if spec is None:
        raise TrackError(f"épreuve inconnue : {event_id!r}")
    opp = spec.opponents
    out = [{"id": "opponents", "values": list(opp), "default": opp[len(opp) // 2] if len(opp) > 2 else opp[-1]}]
    out += [{"id": o.id, "values": list(o.values), "default": o.default} for o in spec.options]
    if has_bots(event_id):   # lot VD7 : « Tactique des bots : aucune, simple, complète », complète par défaut
        out.append({"id": "bot_tactics", "values": list(TACTIC_LEVELS), "default": "full"})
    return out


def has_bots(event_id: str) -> bool:
    """Vrai si l'épreuve peut avoir des bots (adversaires ou coéquipiers)."""
    spec = EVENTS[event_id]
    return max(spec.opponents) > 0 or spec.team_size > 1


def check(event_id: str, settings: dict) -> dict:
    """Réglages complétés par les défauts ; TrackError sur une épreuve ou une valeur refusée."""
    out = {}
    for o in options(event_id):
        v = settings.get(o["id"], o["default"])
        if isinstance(v, bool) or v not in o["values"]:
            raise TrackError(f"{event_id} : {o['id']} = {v!r} refusé ({', '.join(map(str, o['values']))})")
        out[o["id"]] = v
    unknown = set(settings) - set(out)
    if unknown:
        raise TrackError(f"{event_id} : réglage inconnu {', '.join(sorted(unknown))}")
    return out


def field_size(event_id: str, settings: dict) -> int:
    """Bots à engager à côté du cycliste : coéquipiers compris."""
    spec = EVENTS[event_id]
    opp = int(settings["opponents"])
    return (spec.team_size - 1) + opp * spec.team_size


def make(event_id: str, entrants: list[Entrant], settings: dict, **kw) -> TrackEvent:
    """Épreuve prête à partir. Épreuves par équipes : l'équipe du cycliste est « home », ses coéquipiers
    sont les premiers bots ; `place` (vitesse par équipes) range le cycliste à sa place dans l'équipe."""
    spec = EVENTS.get(event_id)
    if spec is None:
        raise TrackError(f"épreuve inconnue : {event_id!r}")
    s = check(event_id, settings)
    if len(entrants) != 1 + field_size(event_id, s):
        raise TrackError(f"{event_id} : {len(entrants)} engagés pour {field_size(event_id, s)} bots attendus")
    args = {k: v for k, v in s.items() if k not in ("opponents", "place", "bot_tactics")}
    if "distance_m" in args:
        args["distance_m"] = float(args["distance_m"])
    if spec.team_size > 1:
        entrants = teams(entrants, spec.team_size, int(s.get("place", 1)))
    return spec.cls(entrants, **spec.fixed, **args, **kw)


def teams(entrants: list[Entrant], size: int, place: int = 1) -> list[Entrant]:
    """Équipes de `size` dans l'ordre des engagés : le cycliste et ses `size − 1` premiers bots forment
    « home », les suivants « t2 », « t3 »… ; le cycliste se range à `place` dans son équipe."""
    me = [e for e in entrants if e.id == ME]
    bots = [e for e in entrants if e.id != ME]
    home = bots[:size - 1]
    home.insert(min(max(place, 1), size) - 1, me[0])
    out = [Entrant(e.id, e.name, "home", e.level) for e in home]
    rest = bots[size - 1:]
    for i in range(0, len(rest), size):
        out += [Entrant(e.id, e.name, f"t{i // size + 2}", e.level) for e in rest[i:i + size]]
    return out


__all__ = ["EVENTS", "TACTIC_LEVELS", "has_bots", "LAP_M", "ME", "Entrant", "EventSpec", "Option", "TrackError", "TrackEvent",
           "check", "field_size", "make", "options", "teams"]
