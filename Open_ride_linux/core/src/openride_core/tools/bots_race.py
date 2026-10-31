"""Course des bots en temps accéléré (lot X27) : calibrage et stratégies des bots à profil, sans vélo.

    python -m openride_core.tools.bots_race --route demo|plat|col|FICHIER.world --rider-pct 85 \\
        --bots climber,rouleur,sprinter,diesel [--ftp 250] [--niveau 85] [--json]

La vraie séance (`CoreSession`, avec son calibrage des bots du lot T13, ses segments et ses maillots)
tourne au pas fixe de 20 ms sans trainer ni engine : le cycliste roule à `--rider-pct` % de sa FTP
(`MockDriver`, puissance constante), les bots à profil sont calibrés au niveau `--niveau` (% de la FTP,
par défaut celui du cycliste : ils doivent alors finir avec lui). Les bots qui finissent après le cycliste
continuent avec la même physique jusqu'à l'arrivée.

Tableau par bot : temps d'arrivée, écart avec le cycliste, W′ le plus bas, maillots ; trame `state` la plus
grande. Échec (code 1) si un bot calibré au niveau du cycliste finit à plus de 2 % de lui, ou si une trame
`state` dépasse la limite du contrat (4 096 octets) ; code 2 pour un profil, un parcours ou un appel
invalide. Parcours `plat` (20 km à 0 %) et `col` (2 km de plat puis 8 km à 7 %) : écrits à la volée.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from unittest import mock
from pathlib import Path
from typing import Any

from .. import fit_export
from ..bots import PROFILES, ProfileBot, profile_bot_names
from ..config import Config
from ..demo_world import write_world
from ..input_providers import NullProvider
from ..ipc_budget import STATE_LIMIT_1_3, size
from ..mock_driver import MockDriver
from ..session import CoreSession

DT = 0.02
FRAME_EVERY = 2                # trame `state` toutes les 40 ms (25 Hz, DT_STATE de la séance)
GAP_LIMIT_PCT = 2.0
MAX_RIDE_S = 6 * 3600.0
SYNTHETIC = {
    "plat": (20000.0, lambda s: 0.0),
    "col": (10000.0, lambda s: 0.0 if s < 2000.0 else 7.0),
}


class RaceError(Exception):
    """Appel invalide : profil ou parcours inconnu."""


def prepare_route(route: str, routes_root: Path) -> str:
    """Identifiant du parcours dans `routes_root` (écrit pour `plat`, `col` et un dossier .world)."""
    if route == "demo":
        return "demo"
    if route in SYNTHETIC:
        length, grade = SYNTHETIC[route]
        write_world(routes_root, route, length, created="2026-10-28T00:00:00+01:00", grade=grade)
        return route
    src = Path(route).expanduser()
    if not (src / "manifest.json").is_file():
        raise RaceError(f"parcours introuvable : {route} (demo, plat, col ou dossier .world)")
    import shutil
    shutil.copytree(src, routes_root / src.name, dirs_exist_ok=True)
    return src.stem


def race(route: str, rider_pct: float, profiles: list[str], ftp_w: float = 250.0,
         level_pct: float | None = None, dt: float = DT) -> dict[str, Any]:
    unknown = [p for p in profiles if p not in PROFILES]
    if unknown:
        raise RaceError(f"profil(s) de bot inconnu(s) : {', '.join(unknown)} ({', '.join(PROFILES)})")
    level = float(level_pct if level_pct is not None else rider_pct)
    t_wall = time.perf_counter()
    # Tout ce que la séance écrit (journal, FIT de fin de parcours, records, progression) reste dans un
    # dossier temporaire : la course ne touche pas à l'historique du cycliste.
    with tempfile.TemporaryDirectory(prefix="openride-bots-race-") as tmp_s, \
            mock.patch.object(fit_export, "ACTIVITIES_DIR", Path(tmp_s) / "Activities"):
        tmp = Path(tmp_s)
        routes = tmp / "routes"
        routes.mkdir()
        route_id = prepare_route(route, routes)
        cfg = Config()
        cfg.depart.mode = "immediat"   # banc sans engine ni cycliste : départ à la commande start (lot O36)
        cfg.rider.ftp_w = ftp_w
        cfg.bots.level_pct = round(level)
        cfg.powerups.mode = "off"            # course sans bonus : seuls la physique et les stratégies jouent
        names = profile_bot_names(profiles)
        bots = [ProfileBot(p, bot_id=f"b{i + 1}", name=n, bike_mass_kg=cfg.bike.mass_kg)
                for i, (p, n) in enumerate(zip(profiles, names))]
        for b in bots:
            b.level_pct = level
        s = CoreSession(cfg, driver=MockDriver(base_power_w=ftp_w * rider_pct / 100.0, ramp_amplitude_w=0.0),
                        inputs=[NullProvider()], journal_dir=tmp / "journal", routes_root=routes,
                        workouts_dir=tmp / "workouts", bots=bots, records_path=tmp / "records.json",
                        powerups_path=tmp / "powerups.toml", profile_path=tmp / "profile.json")
        results: list[dict] = []
        s.server.send_raw = lambda m, max_size=None: results.append(m) if m.get("type") == "segment_result" else None
        s.server.send_input_event = lambda ev: None
        s._on_command("select_route", {"route_id": route_id}, 1)
        if s.route is None:
            raise RaceError(f"parcours {route} refusé par la séance")
        s._on_command("start", {}, 2)
        length = s.route.length_m
        finish: dict[str, float] = {}
        wmin = {b.id: 100.0 for b in bots}
        jerseys: Any = None
        biggest = 0
        t = 0.0
        step = 0
        while t < MAX_RIDE_S and (len(finish) < len(bots) + 1):
            if "rider" not in finish:
                s._step(dt, time.monotonic())
                if s.physics.s >= length - 1e-6 or s.state.session_state == "FINISHED":
                    finish["rider"] = t + dt
                if step % FRAME_EVERY == 0 and s.state.session_state == "RUNNING":
                    s.state.bots = [b.to_dict() for b in s.bots]
                    s._fill_race_frame()
                    frame = s.state.to_dict()
                    biggest = max(biggest, size(frame))
                    jerseys = frame.get("jerseys") or jerseys
            else:   # le cycliste a fini : les bots restants continuent avec la même physique
                for b in bots:
                    if b.id not in finish:
                        b.step(dt, s.route)
            t += dt
            step += 1
            for b in bots:
                wmin[b.id] = min(wmin[b.id], b.wbal_pct)
                if b.id not in finish and b.s >= length - 1e-6:
                    finish[b.id] = t
        s._finish(save=False)
    rider_t = finish.get("rider")
    rows = []
    for b in bots:
        bt = finish.get(b.id)
        gap = (bt - rider_t) / rider_t * 100.0 if bt is not None and rider_t else None
        rows.append({"id": b.id, "profile": b.profile, "name": b.name, "scale": round(b.scale, 3),
                     "finish_s": None if bt is None else round(bt, 1), "gap_pct": None if gap is None else round(gap, 2),
                     "wbal_min_pct": round(wmin[b.id], 1),
                     "jerseys": sorted(k for k, v in (jerseys or {}).items() if v == b.id)})
    checks = []
    if abs(level - rider_pct) < 1e-9:
        for r in rows:
            ok = r["gap_pct"] is not None and abs(r["gap_pct"]) <= GAP_LIMIT_PCT
            checks.append((ok, f"{r['name']} au niveau du cycliste : écart {r['gap_pct']} % (au plus {GAP_LIMIT_PCT:g} %)"))
    checks.append((biggest <= STATE_LIMIT_1_3, f"trame state la plus grande : {biggest} octets (limite {STATE_LIMIT_1_3})"))
    return {"route": route, "length_m": round(length, 1), "rider_pct": rider_pct, "level_pct": level, "ftp_w": ftp_w,
            "rider_finish_s": None if rider_t is None else round(rider_t, 1), "bots": rows,
            "rider_jerseys": sorted(k for k, v in (jerseys or {}).items() if v == "me"),
            "segment_results": len(results), "state_max_bytes": biggest,
            "checks": [{"ok": ok, "text": txt} for ok, txt in checks],
            "wall_s": round(time.perf_counter() - t_wall, 2)}


def format_text(out: dict[str, Any]) -> str:
    lines = [f"Course des bots sur {out['route']} ({out['length_m'] / 1000:.1f} km) : cycliste à {out['rider_pct']:g} % "
             f"de {out['ftp_w']:g} W, bots au niveau {out['level_pct']:g} %",
             f"Cycliste : arrivée en {out['rider_finish_s']} s ; {out['segment_results']} résultat(s) de segment ; "
             f"maillots {', '.join(out['rider_jerseys']) or '—'}",
             "", f"  {'bot':<12} {'profil':<9} {'échelle':>7} {'arrivée':>9} {'écart':>8} {'W′ min':>7}  maillots"]
    for r in out["bots"]:
        gap = "—" if r["gap_pct"] is None else f"{r['gap_pct']:+.2f} %"
        fin = "—" if r["finish_s"] is None else f"{r['finish_s']:.0f} s"
        lines.append(f"  {r['name']:<12} {r['profile']:<9} {r['scale']:>7.2f} {fin:>9} {gap:>8} {r['wbal_min_pct']:>6.0f} %"
                     f"  {', '.join(r['jerseys']) or '—'}")
    lines.append("")
    lines += [f"[{'OK' if c['ok'] else 'ÉCHEC'}] {c['text']}" for c in out["checks"]]
    lines.append(f"Calcul en {out['wall_s']:.1f} s")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Course des bots en temps accéléré (lot X27).")
    ap.add_argument("--route", default="demo", help="demo, plat, col ou dossier .world")
    ap.add_argument("--rider-pct", type=float, default=85.0, help="puissance du cycliste en %% de sa FTP")
    ap.add_argument("--bots", default="climber,rouleur,sprinter,diesel", help="profils séparés par des virgules")
    ap.add_argument("--ftp", type=float, default=250.0)
    ap.add_argument("--niveau", type=float, help="niveau des bots en %% de la FTP (défaut : celui du cycliste)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    profiles = [p.strip() for p in args.bots.split(",") if p.strip()]
    if not profiles:
        print("aucun bot demandé", file=sys.stderr)
        return 2
    try:
        out = race(args.route, args.rider_pct, profiles, args.ftp, args.niveau)
    except RaceError as exc:
        print(f"ÉCHEC : {exc}", file=sys.stderr)
        return 2
    print(json.dumps(out, ensure_ascii=False, indent=2) if args.json else format_text(out), end="" if not args.json else "\n")
    return 0 if all(c["ok"] for c in out["checks"]) else 1


if __name__ == "__main__":
    sys.exit(main())
