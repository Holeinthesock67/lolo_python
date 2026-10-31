"""Banc des séances enchaînées sans quitter le jeu (endurance 7bi) : temps de pas et mémoire du core, sans vélo.

    python -m openride_core.tools.seances_enchainees [--seances 6] [--minutes 2] [--bots 2] [--sans-memoire] [--json]

La vraie séance (`CoreSession`, trainer simulé à puissance variable, bots à puissance constante) roule au pas
fixe de 20 ms en temps accéléré, sans trainer ni engine : `--seances` séances de `--minutes` min, chacune
ouverte comme la relance de l'endurance (`select_route` puis `start`) et fermée par `end_session` avec
enregistrement (journal, FIT, records, XP dans un dossier temporaire).

Relevés par séance : temps de pas moyen et p99 (temps réel du calcul), taille de la fenêtre de la puissance
3 s, mémoire Python gardée en fin de séance par le code d'OpenRide (tracemalloc, allocations dont la pile passe
par `openride_core` ; ni celles d'autres fils du même processus, ni les lignes du journal que garderait un
gestionnaire, la capture des logs de pytest par exemple, ne comptent ;
environ 8 fois plus lent ; `--sans-memoire` pour ne mesurer que le temps).

Échec (code 1) si : le pas moyen de la dernière séance dépasse 1,5 fois celui de la première (plus 0,05 ms
de marge de mesure), si la fenêtre de la puissance 3 s dépasse 3 s de relevés, ou si la mémoire gardée d'une
séance à l'autre dépasse `PER_SESSION_KB` Ko par séance (ce que garde normalement une séance de plus :
bilan de progression, records) plus `MAX_GROWTH_MB_PER_H` Mo par heure roulée (seuil de l'endurance : 20 Mo/h).
"""

from __future__ import annotations

import argparse
import gc
import json
import logging
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path
from typing import Any
from unittest import mock

from .. import fit_export
from ..bots import ConstantPowerBot
from ..config import Config
from ..demo_world import write_world
from ..input_providers import NullProvider
from ..mock_driver import MockDriver
from ..session import CoreSession

DT = 0.02
ROUTE_M = 60000.0              # jamais fini pendant une séance : la séance se ferme par end_session
STEP_RATIO_MAX = 1.5
STEP_MARGIN_MS = 0.05
WINDOW_MAX = int(3.0 / DT) + 10
MAX_GROWTH_MB_PER_H = 2.0
PER_SESSION_KB = 50.0
T0_WALL = 1_790_000_000.0
TRACE_FRAMES = 16
OWN_CODE = tracemalloc.Filter(True, str(Path(__file__).resolve().parents[1] / "*"), all_frames=True)
# Lignes du journal : gardées par un gestionnaire qui les accumule (capture des logs de pytest), pas par le core.
LOG_RECORDS = tracemalloc.Filter(False, logging.__file__.rsplit("/", 1)[0] + "/*", all_frames=True)


def own_memory_mb() -> float:
    """Mémoire Python allouée par le code d'OpenRide et encore vivante, en Mo."""
    gc.collect()
    snap = tracemalloc.take_snapshot().filter_traces([OWN_CODE, LOG_RECORDS])
    return sum(st.size for st in snap.statistics("filename")) / 1e6


def run(sessions: int = 6, minutes: float = 2.0, n_bots: int = 2, memory: bool = True) -> dict[str, Any]:
    t_wall = time.perf_counter()
    wall = [T0_WALL]
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="openride-seances-") as tmp_s, \
            mock.patch.object(fit_export, "ACTIVITIES_DIR", Path(tmp_s) / "Activities"), \
            mock.patch.object(time, "time", lambda: wall[0]):
        tmp = Path(tmp_s)
        routes = tmp / "routes"
        routes.mkdir()
        write_world(routes, "boucle", ROUTE_M, created="2026-10-31T00:00:00+01:00")
        cfg = Config()
        cfg.powerups.mode = "off"
        bots = [ConstantPowerBot(200.0 + 20.0 * i, bot_id=f"bot{i + 1}") for i in range(n_bots)]
        s = CoreSession(cfg, driver=MockDriver(base_power_w=210.0, ramp_amplitude_w=45.0, ramp_period_s=120.0),
                        inputs=[NullProvider()], journal_dir=tmp / "journal", routes_root=routes,
                        workouts_dir=tmp / "workouts", bots=bots, records_path=tmp / "records.json",
                        powerups_path=tmp / "powerups.toml", profile_path=tmp / "profile.json")
        s.server.send_raw = lambda m, max_size=None: None
        s.server.send_input_event = lambda ev: None
        if memory:
            tracemalloc.start(TRACE_FRAMES)
        steps = int(round(minutes * 60.0 / DT))
        cmd_id = t_sim = 0
        try:
            for k in range(sessions):
                cmd_id += 1
                s._on_command("select_route", {"route_id": "boucle"}, cmd_id)
                cmd_id += 1
                s._on_command("start", {}, cmd_id)
                step_ms: list[float] = []
                for _ in range(steps):
                    t_sim += 1
                    wall[0] = T0_WALL + t_sim * DT
                    t0 = time.perf_counter()
                    s._step(DT, t_sim * DT)
                    step_ms.append((time.perf_counter() - t0) * 1000.0)
                window = len(s._power_window)
                cmd_id += 1
                s._on_command("end_session", {"save": True}, cmd_id)
                step_ms.sort()
                row = {"seance": k + 1, "pas_moyen_ms": round(sum(step_ms) / len(step_ms), 4),
                       "pas_p99_ms": round(step_ms[min(int(0.99 * len(step_ms)), len(step_ms) - 1)], 4),
                       "fenetre_3s": window, "etat": s.state.session_state}
                if memory:
                    row["memoire_mo"] = round(own_memory_mb(), 3)
                rows.append(row)
        finally:
            if memory:
                tracemalloc.stop()
    return {"seances": sessions, "minutes": minutes, "bots": n_bots, "rows": rows,
            "checks": checks(rows, minutes), "wall_s": round(time.perf_counter() - t_wall, 1)}


def checks(rows: list[dict[str, Any]], minutes: float) -> list[dict[str, Any]]:
    out: list[tuple[bool, str]] = []
    first, last = rows[0], rows[-1]
    limit = first["pas_moyen_ms"] * STEP_RATIO_MAX + STEP_MARGIN_MS
    out.append((last["pas_moyen_ms"] <= limit,
                f"pas moyen stable : {first['pas_moyen_ms']:.3f} ms à la 1re séance, {last['pas_moyen_ms']:.3f} ms "
                f"à la {last['seance']}e (au plus {limit:.3f})"))
    worst = max(r["fenetre_3s"] for r in rows)
    out.append((worst <= WINDOW_MAX, f"fenêtre de la puissance 3 s : {worst} relevés au plus (au plus {WINDOW_MAX})"))
    out.append((all(r["etat"] == "FINISHED" for r in rows), "chaque séance se ferme en FINISHED"))
    if "memoire_mo" in first and len(rows) > 1:
        n = len(rows) - 1
        kept_kb = (last["memoire_mo"] - first["memoire_mo"]) * 1000.0 / n
        limit_kb = PER_SESSION_KB + MAX_GROWTH_MB_PER_H * 1000.0 * minutes / 60.0
        out.append((kept_kb <= limit_kb,
                    f"mémoire gardée d'une séance à l'autre : {kept_kb:+.1f} Ko par séance de {minutes:g} min, "
                    f"soit {kept_kb * 60.0 / minutes / 1000.0:+.2f} Mo par heure roulée (au plus {limit_kb:.0f} Ko : "
                    f"{PER_SESSION_KB:g} Ko par séance et {MAX_GROWTH_MB_PER_H:g} Mo/h)"))
    return [{"ok": ok, "text": txt} for ok, txt in out]


def format_text(out: dict[str, Any]) -> str:
    mem = "memoire_mo" in out["rows"][0]
    lines = [f"{out['seances']} séances de {out['minutes']:g} min enchaînées, {out['bots']} bot(s), "
             f"temps accéléré ({out['wall_s']:.0f} s de calcul)", "",
             f"  {'séance':>6}  {'pas moyen':>10}  {'pas p99':>9}  {'fenêtre 3 s':>11}" + (f"  {'mémoire':>9}" if mem else "")]
    for r in out["rows"]:
        lines.append(f"  {r['seance']:>6}  {r['pas_moyen_ms']:>7.3f} ms  {r['pas_p99_ms']:>6.3f} ms  {r['fenetre_3s']:>11}"
                     + (f"  {r['memoire_mo']:>6.2f} Mo" if mem else ""))
    lines.append("")
    lines += [f"[{'OK' if c['ok'] else 'ÉCHEC'}] {c['text']}" for c in out["checks"]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Banc des séances enchaînées du core (endurance 7bi).")
    ap.add_argument("--seances", type=int, default=6, help="nombre de séances enchaînées (au moins 2)")
    ap.add_argument("--minutes", type=float, default=2.0, help="durée de chaque séance (min)")
    ap.add_argument("--bots", type=int, default=2, help="bots à puissance constante (0 à 4)")
    ap.add_argument("--sans-memoire", action="store_true", help="sans tracemalloc : plus rapide, temps de pas seul")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.seances < 2 or args.minutes <= 0 or not 0 <= args.bots <= 4:
        print("au moins 2 séances, une durée positive et 0 à 4 bots", file=sys.stderr)
        return 2
    out = run(args.seances, args.minutes, args.bots, memory=not args.sans_memoire)
    print(json.dumps(out, ensure_ascii=False, indent=2) if args.json else format_text(out), end="" if not args.json else "\n")
    return 0 if all(c["ok"] for c in out["checks"]) else 1


if __name__ == "__main__":
    sys.exit(main())
