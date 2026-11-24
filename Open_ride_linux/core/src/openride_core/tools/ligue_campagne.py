"""Banc des saisons simulées de la ligue d'hiver (série CH, lot CH2) : le cycliste gagne-t-il environ 10 % des manches ?

    python -m openride_core.tools.ligue_campagne [--saisons 100] [--forces 1200,1500,1900] [--presence 0.8]
        [--rodage 3] [--graine 1] [--ftp 250] [--json]

Le calibrage ne se juge pas sur un essai vélo (une manche par semaine). Ce banc joue des saisons entières au modèle
de la cote Elo (#941, banc `elo_campagne`) : à chaque manche, cotes des rivaux tirées de la cote du cycliste
(`league.round_ratings`), arrivée tirée au sort (Plackett-Luce, échelle Elo) avec la vraie force du cycliste
(`--forces`, en points Elo : 1 900 = nettement plus fort que la cote de départ), cote mise à jour
(`league.rider_update`). Les manches non courues (`--presence`) sont simulées pour les rivaux. Rien n'est écrit.

Contrôles (code 1 si l'un échoue, code 2 pour un appel invalide), après `--rodage` saisons :
- part de victoires du cycliste entre 6 et 14 % pour chaque force, toutes manches confondues ;
- entre 4 et 18 % pour chaque type de manche (terrain), forces confondues ;
- la cote suit la force (écart moyen sous 120 points) ;
- le cycliste n'est pas toujours dernier ni toujours sur le podium : place moyenne entre 3 et 9.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from datetime import date, timedelta
from typing import Any

from .. import bot_effort, bot_elo, league

MON = date(2026, 11, 23)
WIN_BOUNDS = (0.06, 0.14)
TERRAIN_BOUNDS = (0.04, 0.18)
RATING_TOL = 120.0
PLACE_BOUNDS = (3.0, 9.0)


def campaign(force: float, seasons: int, presence: float = 0.8, burn_in: int = 3, seed: int = 1) -> dict[str, Any]:
    """Saisons enchaînées pour un cycliste de vraie force `force` (points Elo) ; rend les relevés après rodage."""
    rng = random.Random(seed * 104729 + int(force))
    book = bot_elo.EloBook()
    season = None
    races = wins = 0
    places: list[int] = []
    ratings: list[float] = []
    by_terrain: dict[str, list[int]] = {}
    day = MON
    for n in range(seasons):
        season = league.new_season(day, seed=rng.randrange(1 << 30), previous=season)
        for i, rnd in enumerate(league.ROUNDS):
            today = season.start + timedelta(weeks=i, days=3)
            if rng.random() < presence:
                cotes = league.round_ratings(season, rnd, book.rating, book.offsets)
                strengths = dict(cotes)
                strengths[league.ME] = force
                order = league.plackett_luce(strengths, random.Random(rng.randrange(1 << 30)))
                result = {k: p for p, k in enumerate(order, 1)}
                season.record(i, result, today)
                league.rider_update(book, result, cotes)
                if n >= burn_in:
                    races += 1
                    wins += result[league.ME] == 1
                    places.append(result[league.ME])
                    ratings.append(book.rating)
                    by_terrain.setdefault(rnd.terrain, []).append(int(result[league.ME] == 1))
        day = season.start + timedelta(weeks=league.WEEKS)
        season.advance(day)
    return {"force": force, "races": races, "win_rate": wins / races if races else 0.0,
            "mean_place": statistics.fmean(places) if places else 0.0,
            "mean_rating": statistics.fmean(ratings) if ratings else book.rating,
            "by_terrain": {k: (sum(v), len(v)) for k, v in by_terrain.items()}}


def check(results: list[dict[str, Any]]) -> list[str]:
    errors = []
    terrain: dict[str, list[int]] = {}
    for r in results:
        if not WIN_BOUNDS[0] <= r["win_rate"] <= WIN_BOUNDS[1]:
            errors.append(f"force {r['force']:.0f} : {r['win_rate']:.1%} de victoires (attendu {WIN_BOUNDS[0]:.0%}"
                          f" à {WIN_BOUNDS[1]:.0%})")
        if abs(r["mean_rating"] - r["force"]) > RATING_TOL:
            errors.append(f"force {r['force']:.0f} : cote moyenne {r['mean_rating']:.0f}, loin de la force")
        if not PLACE_BOUNDS[0] <= r["mean_place"] <= PLACE_BOUNDS[1]:
            errors.append(f"force {r['force']:.0f} : place moyenne {r['mean_place']:.1f}")
        for k, (w, n) in r["by_terrain"].items():
            t = terrain.setdefault(k, [0, 0])
            t[0] += w
            t[1] += n
    for k, (w, n) in terrain.items():
        if n and not TERRAIN_BOUNDS[0] <= w / n <= TERRAIN_BOUNDS[1]:
            errors.append(f"manches « {k} » : {w / n:.1%} de victoires sur {n}")
    return errors


def watts_line(ftp_w: float) -> str:
    """Repère en watts : niveau des rivaux le plus faible et le plus fort d'une manche type à la cote de départ,
    appliqué à FTP × objectif Tempo (les bots suivent la FTP du cycliste, `bot_effort` ; la durée de la course
    module encore ce chiffre en séance)."""
    season = league.new_season(MON, seed=1)
    f = league.level_factors(league.round_ratings(season, league.ROUNDS[0], bot_elo.START))
    base = ftp_w * bot_effort.OBJECTIVES["tempo"] / 100.0
    lo, hi = min(f.values()), max(f.values())
    return f"rivaux au Tempo, FTP {ftp_w:.0f} W : ≈ {base * lo:.0f} à {base * hi:.0f} W (× {lo:.3f} à × {hi:.3f})"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ligue_campagne", description=__doc__.splitlines()[0])
    ap.add_argument("--saisons", type=int, default=100)
    ap.add_argument("--forces", default="1200,1500,1900")
    ap.add_argument("--presence", type=float, default=0.8)
    ap.add_argument("--rodage", type=int, default=3)
    ap.add_argument("--graine", type=int, default=1)
    ap.add_argument("--ftp", type=float, default=250.0)
    ap.add_argument("--json", action="store_true")
    try:
        args = ap.parse_args(argv)
        forces = [float(x) for x in args.forces.split(",") if x.strip()]
    except (SystemExit, ValueError):
        return 2
    if args.saisons <= args.rodage or not forces or not 0.0 < args.presence <= 1.0:
        print("appel invalide : --saisons doit dépasser --rodage, --presence dans ]0, 1]", file=sys.stderr)
        return 2
    results = [campaign(f, args.saisons, args.presence, args.rodage, args.graine) for f in forces]
    errors = check(results)
    if args.json:
        print(json.dumps({"results": results, "errors": errors}, ensure_ascii=False, indent=1))
    else:
        for r in results:
            terr = ", ".join(f"{k} {w}/{n}" for k, (w, n) in sorted(r["by_terrain"].items()))
            print(f"force {r['force']:.0f} : {r['races']} manches, {r['win_rate']:.1%} de victoires, place moyenne "
                  f"{r['mean_place']:.1f}, cote {r['mean_rating']:.0f} ({terr})")
        print(watts_line(args.ftp))
        print("OK" if not errors else "ÉCHEC :\n- " + "\n- ".join(errors))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
