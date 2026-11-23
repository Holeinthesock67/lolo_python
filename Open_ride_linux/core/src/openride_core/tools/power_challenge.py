"""Défi « bats ton record » de « Ma puissance » (série PP, lot PP7, première partie).

    python -m openride_core.tools.power_challenge [--json]

Un seul défi à la fois, tiré de la courbe du profil (lot PP1) et de « Se connaître » (lot PP5), au menu
seulement (rien pendant la séance, plan PP §8.5) :

- **durée** : le point faible du profil s'il existe, sinon la durée du record vieillissant, sinon 5 min ;
- **cible** : le record des 6 mois sur cette durée plus 1 W, écrite en watts (« 5 min au-dessus de 310 W ») ;
- **parcours proposé** : pour 1 min et plus, le parcours prêt dont la montée principale dure, à la puissance
  visée, au moins la durée du défi et le moins longtemps au-delà (vitesse d'équilibre de `route_stats`) ;
  les parcours propres à un mode (vélodrome, Grand Prix) sont écartés ; en dessous d'une minute, n'importe
  quel sprint suffit et aucun parcours n'est imposé.

Sans record sur la durée retenue, pas de défi : l'écran propose déjà de combler le trou.

Clés (objet `challenge` du message `power_curve`, révision 1.29) : s, target_w, record_w, why
(`weak`, `aging` ou `default`), route_id, route_name, climb_s.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Iterable

from .. import mode_routes
from ..route_stats import steady_speed

DEFAULT_S = 300
SPRINT_MAX_S = 60
MAX_FACTOR = 2.5     # montée retenue : au plus 2,5 fois la durée du défi


def pick_duration(profile: dict[str, Any] | None) -> tuple[int, str]:
    profile = profile or {}
    if profile.get("weak"):
        return int(profile["weak"]), "weak"
    aging = profile.get("aging")
    if isinstance(aging, dict) and aging.get("s"):
        return int(aging["s"]), "aging"
    return DEFAULT_S, "default"


def climb_time_s(stats: dict[str, Any] | None, power_w: float) -> float | None:
    main = (stats or {}).get("main_climb") if isinstance(stats, dict) else None
    if not isinstance(main, dict) or not main.get("length_m"):
        return None
    return float(main["length_m"]) / steady_speed(power_w, float(main.get("avg_grade_pct") or 0.0))


def pick_route(routes: Iterable[Any], seconds: int, power_w: float) -> tuple[Any, float] | None:
    """Parcours prêt dont la montée principale tient au moins `seconds` à `power_w`, au plus près."""
    best = None
    for r in routes:
        if getattr(r, "status", "") != "ready" or mode_routes.mode_of(getattr(r, "library", None)):
            continue
        t = climb_time_s(getattr(r, "stats", None), power_w)
        if t is None or t < seconds or t > seconds * MAX_FACTOR:
            continue
        if best is None or t < best[1] or (t == best[1] and r.id < best[0].id):
            best = (r, t)
    return best


def challenge(profile: dict[str, Any] | None, m6_points: list[dict], routes: Iterable[Any]) -> dict[str, Any] | None:
    """Défi du moment depuis le profil PP5 et la fenêtre 6 mois de `power_curve.window_curve`."""
    seconds, why = pick_duration(profile)
    rec = next((p for p in m6_points if p.get("seconds") == seconds), None)
    if rec is None or rec.get("watts") is None:
        return None
    target = int(rec["watts"]) + 1
    out = {"s": seconds, "target_w": target, "record_w": int(rec["watts"]), "why": why,
           "route_id": None, "route_name": None, "climb_s": None}
    if seconds >= SPRINT_MAX_S:
        found = pick_route(routes, seconds, target)
        if found is not None:
            r, t = found
            out.update(route_id=r.id, route_name=r.name, climb_s=int(round(t)))
    return out


def main(argv: list[str] | None = None) -> int:
    from .. import profiles
    from ..catalog import list_routes
    from . import power_curve as pc, power_profile

    ap = argparse.ArgumentParser(prog="python -m openride_core.tools.power_challenge",
                                 description="Défi « bats ton record » du profil en cours.")
    ap.add_argument("--json", action="store_true", help="sortie JSON")
    a = ap.parse_args(argv)
    try:
        import time
        ctx = profiles.current()
        now = time.time()
        kept = pc.kept_sessions(pc.session_entries(ctx.activities_dir, ctx.mmp_cache), ctx.counted_sources,
                                getattr(ctx, "stats_since", None))   # remise à zéro (lot RZ1)
        m6 = pc.window_curve(kept, pc.WINDOWS["months6"], now)
        w6 = pc.window_curve(kept, pc.WINDOWS["weeks6"], now)
        r = challenge(power_profile.profile_from_windows(m6, w6, now), m6["points"], list_routes())
    except Exception as exc:
        print(f"Défi impossible : {exc}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    elif r is None:
        print("Pas de défi : aucun record sur la durée retenue.")
    else:
        where = f" sur {r['route_name']} (montée d'environ {r['climb_s'] // 60} min)" if r["route_id"] else ""
        print(f"Défi : {pc.duration_label(r['s'])} au-dessus de {r['record_w']} W{where}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
