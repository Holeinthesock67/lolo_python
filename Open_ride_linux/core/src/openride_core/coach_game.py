"""Séance de jeu calibrée au besoin (série CO, lot CO9) : course contre les bots ou Dernier survivant,
avec les bots, le parcours et la durée choisis pour travailler le besoin du jour (plan
`docs/5.0/PLAN_SERIE_CO.md` §4 ter).

Formats essayés dans l'ordre de la table `[[game.formats]]` de `data/coach.toml` (mode, bots et leur
niveau en % de la FTP, tactique des bots Y10, contraintes du parcours, cycliste virtuel). Pour chaque
format, les parcours prêts du catalogue (fiches O15) qui respectent ses contraintes sont simulés en
temps accéléré avec le cycliste virtuel aux valeurs du joueur (stratégie `pente` de `sim_rider.py` :
`rider_pct` % de la FTP sur le plat, qui suit la pente ; `climb_pct` dans les montées quand le format
le fixe ; sprints de `sprint_s` s à `sprint_pct` % à chaque arche du Dernier survivant), tronçon de
100 m par tronçon à la vitesse d'équilibre du barème des fiches (`route_stats.steady_speed`). Le
format est proposé si le temps prédit dans les zones du besoin atteint `min_ratio_pct` % de celui de
l'entraînement équivalent (l'entraînement conseillé, lot CO2, sinon `reference_pct` % de la durée) ;
sinon le format suivant, sinon rien (entraînement ERG seul).

Le calcul reste sous la seconde : la vraie séance (`tools/bots_race.py`, 50 Hz avec physique, abri et
tactique) se garde pour la recette sur le PC (lot CO7). La difficulté de la pente n'est pas touchée :
elle reste au joueur.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .route_stats import steady_speed

CHUNK_M = 100.0
CLIMB_GRADE_PCT = 2.0      # au-dessus : montée pour `climb_pct` (même seuil que les relais de Y10)


@dataclass(frozen=True)
class Candidate:
    """Parcours prêt du catalogue avec son profil en tronçons de 100 m (longueur, pente %)."""
    id: str
    name: str
    loop: bool
    chunks: tuple[tuple[float, float], ...]
    stats: dict[str, Any]


def need_zones(need: str, table: dict[str, Any]) -> list[str]:
    return list(table["game"]["recovery_zones"]) if need == "recovery" else list(table["needs"][need])


def chunks_of(route: Any) -> tuple[tuple[float, float], ...]:
    """Tronçons de 100 m (longueur, pente moyenne %) d'une couche route (`route.Route`)."""
    n, ds, length = int(route.n), float(route.ds_m), float(route.length_m)
    s = [i * ds for i in range(n - 1)] + [length]
    alt = [float(a) for a in route.alt_m]
    out, i = [], 0
    while i < len(s) - 1:
        j = i + 1
        while j < len(s) - 1 and s[j] - s[i] < CHUNK_M:
            j += 1
        dist = s[j] - s[i]
        if dist > 0:
            out.append((dist, (alt[j] - alt[i]) / dist * 100.0))
        i = j
    return tuple(out)


def rider_power(fmt: dict[str, Any], grade_pct: float, ftp_w: float) -> float:
    """Puissance du cycliste virtuel (stratégie `pente` de `sim_rider.SimRider`, sans bruit)."""
    if fmt.get("climb_pct") and grade_pct >= CLIMB_GRADE_PCT:
        return ftp_w * float(fmt["climb_pct"]) / 100.0
    return ftp_w * float(fmt["rider_pct"]) / 100.0 * min(max(1.0 + 0.06 * grade_pct, 0.4), 1.5)


def simulate(fmt: dict[str, Any], chunks: tuple[tuple[float, float], ...], ftp_w: float, duration_s: float,
             loop: bool) -> dict[str, Any]:
    """Séance simulée : tours du parcours (une boucle se répète, un aller s'arrête à l'arrivée) jusqu'à
    `duration_s` ; secondes par zone, distance, tours. Arche du Dernier survivant tous les `spacing_km`."""
    from .tools.session_summary import ZONES, zone_of

    names = [z[0] for z in ZONES]
    zone_s = dict.fromkeys(names, 0.0)
    t = dist = 0.0
    laps = 0
    sprint_every = float(fmt.get("spacing_km") or 0.0) * 1000.0
    next_sprint = sprint_every if sprint_every else None
    sprint_w = ftp_w * float(fmt.get("sprint_pct") or 0.0) / 100.0
    sprint_s = float(fmt.get("sprint_s") or 0.0)
    while t < duration_s and chunks:
        for length, grade in chunks:
            p = rider_power(fmt, grade, ftp_w)
            dt = length / steady_speed(p, grade)
            if next_sprint is not None and dist + length >= next_sprint and sprint_s > 0:
                zone_s[names[zone_of(sprint_w, ftp_w)]] += sprint_s
                dt = max(dt - sprint_s, 0.0)
                t += sprint_s
                next_sprint += sprint_every
            zone_s[names[zone_of(p, ftp_w)]] += dt
            t += dt
            dist += length
            if t >= duration_s:
                break
        laps += 1
        if not loop:
            break
    return {"zone_s": zone_s, "duration_s": t, "distance_m": dist, "laps": laps}


def route_fits(fmt: dict[str, Any], stats: dict[str, Any], ftp_w: float) -> bool:
    """Contraintes du format sur la fiche du parcours : pente maximale, durée de la montée principale."""
    if fmt.get("max_grade_pct") is not None and float(stats.get("max_grade_pct", 0.0)) > float(fmt["max_grade_pct"]):
        return False
    climb = stats.get("main_climb")
    climb_s = 0.0
    if climb:
        grade = float(climb["avg_grade_pct"])
        climb_s = float(climb["length_m"]) / steady_speed(rider_power(fmt, grade, ftp_w), grade)
    if fmt.get("min_climb_s") is not None and climb_s < float(fmt["min_climb_s"]):
        return False
    return not (fmt.get("max_climb_s") is not None and climb_s > float(fmt["max_climb_s"]))


def choose(need: str, duration_s: float, reference_need_s: float | None, candidates: list[Candidate],
           ftp_w: float, table: dict[str, Any]) -> dict[str, Any] | None:
    """Séance de jeu du besoin (objet `route` du message `coach`), ou None : aucun format ne tient
    `min_ratio_pct` % du temps de l'entraînement équivalent sur un parcours du catalogue."""
    game = table["game"]
    zones = need_zones(need, table)
    reference = reference_need_s if reference_need_s else duration_s * float(game["reference_pct"][need]) / 100.0
    for fmt in (f for f in game["formats"] if f["need"] == need):
        best: tuple[float, Candidate, dict[str, Any]] | None = None
        for c in candidates:
            if not route_fits(fmt, c.stats, ftp_w):
                continue
            if fmt["mode"] == "survivor" and not c.loop \
                    and sum(x for x, _ in c.chunks) < float(fmt["opponents"]) * float(fmt["spacing_km"]) * 1000.0:
                continue
            sim = simulate(fmt, c.chunks, ftp_w, duration_s, c.loop)
            if sim["duration_s"] < float(game["min_duration_pct"]) / 100.0 * duration_s:
                continue
            in_need = sum(sim["zone_s"][z] for z in zones)
            if best is None or in_need > best[0]:
                best = (in_need, c, sim)
        if best is None:
            continue
        in_need, c, sim = best
        ratio = 100.0 * in_need / reference if reference > 0 else 0.0
        if ratio < float(game["min_ratio_pct"]):
            continue
        return {"mode": fmt["mode"], "label": fmt["label"], "route_id": c.id, "route_name": c.name,
                "laps": sim["laps"], "duration_s": int(round(sim["duration_s"])),
                "bots": {"count": int(fmt.get("bots", 0)), "level_pct": int(fmt.get("level_pct", 0)),
                         "tactics": fmt.get("tactics", "none")},
                "survivor": ({"opponents": int(fmt["opponents"]), "spacing_km": int(fmt["spacing_km"])}
                             if fmt["mode"] == "survivor" else None),
                "predicted_need_s": int(round(in_need)), "reference_need_s": int(round(reference)),
                "ratio_pct": round(ratio)}
    return None


def load_candidates(routes_root: Path | None = None, gpx_dir: Path | None = None) -> list[Candidate]:
    """Parcours prêts du catalogue, avec leur fiche et leur profil (les illisibles sont omis)."""
    from .catalog import list_routes
    from .config import GPX_DIR, ROUTES_DIR
    from .route import WorldError, load_world

    root = Path(routes_root) if routes_root is not None else ROUTES_DIR
    out = []
    for e in list_routes(routes_root=root, gpx_dir=Path(gpx_dir) if gpx_dir is not None else GPX_DIR):
        if e.status != "ready" or not e.stats:
            continue
        try:
            world = load_world(root / f"{e.id}.world")
        except (WorldError, OSError, ValueError):
            continue
        out.append(Candidate(e.id, e.name, world.route.type == "loop", chunks_of(world.route), dict(e.stats)))
    return out
