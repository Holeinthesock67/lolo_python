#!/usr/bin/env python3
"""Recette U18, partie PC sans vélo (étape 7bt) : biomes du premier jalon en low, medium et high.

Usage :
    recette_u18.py lancer [--out DOSSIER] [--qualites low,medium,high] [--vitesse 60] [--size 1680x1011]
                          [--trace DOSSIER.world | --sans-trace] [--culling on|off] [--godot CHEMIN]
    recette_u18.py analyser DOSSIER
    recette_u18.py gravel [JOURNAL.jsonl] [--out DOSSIER]

`lancer` enchaîne, sans rien écrire dans le vrai dossier personnel (sim_bench.py a son HOME temporaire) :

1. `openride-core demo-biomes --out DOSSIER/routes --json` : les parcours de démonstration du lot U19 et
   les parts de leurs biomes (`routes/parts.json`) ;
2. pour chaque qualité : `sim_bench.py --native --probe` sur le tour des six biomes du premier jalon
   (`demo-biomes-tour`, 12 km tenus à `--vitesse` km/h, une capture tous les 500 m : milieu de chaque biome
   et chaque frontière), puis 90 s sur la côte avec la mer (`demo-biomes-cote`) ;
3. pour chaque qualité, si une trace personnelle compilée est trouvée (ou donnée par `--trace`) : 90 s avec
   le biome forcé « mediterranean » puis « alpine » (étape 3 du cahier U18) ;
4. `analyser`.

`analyser` découpe la sonde du tour biome par biome (distance lue au journal de séance, parts du
générateur `make_biome_world.Plan`, frontières de 300 m mises à part) et écrit dans DOSSIER :
`resume.md` (tableaux par qualité et par biome, critères du cahier U18 §5 et budgets de
`perf_targets.json`), `resume.json`, et `planche/` (une capture par biome et par qualité, et les
frontières, avec `planche/index.html`) pour la validation des captures par le propriétaire.

`gravel` (étape vélo 7bu, cahier U18 §4.4) lit le journal d'une séance roulée avec l'option gravel (défaut :
le plus récent de `~/OpenRide/Activities/.journal/`), en SIM puis en ERG libre, et juge les critères U18 §5.4 :
supplément de pente moyen d'au moins 0,3 point en non revêtu et nul sur le bitume, jamais plus de 4 points
envoyés (vent compris), cible ERG inchangée et vitesse en non revêtu sous 97 % de celle du bitume, rapportée à
la vitesse d'équilibre du modèle physique du joueur (`config.toml` local, jamais recopié). Les 100 m qui suivent
un changement de surface ou de mode sont écartés. Il écrit `resume_gravel.md` et `resume_gravel.json`
(défaut `~/OpenRide/mesures/<date>/u18_7bu/`).

Confidentialité : la trace personnelle n'est jamais nommée dans `resume.md` ni `resume.json`
(« trace personnelle ») ; seuls des chiffres en sortent, à recopier dans la PR de recette.

Code de sortie : 0 si tous les critères jugés passent, 1 sinon, 2 si l'appel est impossible.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR))
import make_biome_world  # noqa: E402
import perf_probe  # noqa: E402

QUALITIES = ("low", "medium", "high")
TOUR_WORLD = "demo-biomes-tour"
COAST_WORLD = "demo-biomes-cote"
FORCED = ("mediterranean", "alpine")
SHORT_S = 90.0
EVERY_M = 500.0
PURE_SHARE = 0.9             # une seconde compte pour un biome si sa part y dépasse 90 %
TEXTURE_LIMIT_MB = 1024.0    # U18 §5.2 : textures du décor sous 1 Go en high
U18_FPS_MIN, U18_P99_MAX = 55.0, 25.0   # U18 §5.1, en low, sur chaque biome
PERSONAL = "trace personnelle"


def default_out() -> Path:
    return Path.home() / "OpenRide" / "mesures" / time.strftime("%Y-%m-%d") / "u18_7bt"


def find_personal_trace() -> Path | None:
    """Plus gros parcours compilé du propriétaire (hors démonstrations, essais et monde ouvert)."""
    found: list[tuple[int, Path]] = []
    for base in (Path.home() / "OpenRide" / "Routes", Path.home() / ".local" / "share" / "openride" / "routes"):
        if not base.is_dir():
            continue
        for w in base.glob("*.world"):
            name = w.name.lower()
            if name.startswith(("demo", "essai", "_", ".")) or not (w / "manifest.json").is_file():
                continue
            size = sum(f.stat().st_size for f in w.rglob("*") if f.is_file())
            found.append((size, w))
    return max(found)[1] if found else None


def run(cmd: list[str], log: Path) -> int:
    print("$ " + " ".join(cmd), flush=True)
    with log.open("w", encoding="utf-8") as fh:
        return subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT).returncode


def bench(args: argparse.Namespace, out: Path, world: Path, quality: str, duration: float,
          extra: list[str]) -> int:
    out.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(TESTS_DIR / "sim_bench.py"), "--native", "--probe", "--muet",
           "--quality", quality, "--size", args.size, "--world", str(world),
           "--duration", f"{duration:.0f}", "--culling", args.culling, "--out", str(out)] + extra
    if args.godot:
        cmd += ["--godot", str(args.godot)]
    return run(cmd, out / "sim_bench.txt")


def cmd_lancer(args: argparse.Namespace) -> int:
    out: Path = args.out
    routes = out / "routes"
    routes.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "OPENRIDE_ENGINE": str(TESTS_DIR.parent)}
    p = subprocess.run([sys.executable, "-m", "openride_core", "demo-biomes", "--out", str(routes), "--json"],
                       capture_output=True, text=True, env=env)
    if p.returncode != 0:
        print(f"demo-biomes impossible (code {p.returncode}) : {p.stderr.strip()[-400:]}", file=sys.stderr)
        return 2
    (routes / "parts.json").write_text(p.stdout, encoding="utf-8")
    tour, coast = routes / f"{TOUR_WORLD}.world", routes / f"{COAST_WORLD}.world"
    if not tour.is_dir() or not coast.is_dir():
        print(f"parcours de démonstration absents dans {routes}", file=sys.stderr)
        return 2
    trace = None if args.sans_trace else (args.trace or find_personal_trace())
    (out / "trace.txt").write_text("absente\n" if trace is None else "trouvée\n", encoding="utf-8")
    print("Trace personnelle : " + ("absente, étape 3 sautée" if trace is None else "trouvée"))
    length = route_length(out) or make_biome_world.Plan(make_biome_world.TOUR, False, False).length_m
    tour_s = length / (args.vitesse / 3.6) + 45.0     # départ au pédalage et chargement compris
    t0 = time.time()
    for q in args.qualites:
        speed = ["--speed-kmh", f"{args.vitesse:g}"]
        bench(args, out / q / "tour", tour, q, tour_s, speed + ["--every-m", f"{EVERY_M:g}"])
        bench(args, out / q / "cote", coast, q, SHORT_S, speed + ["--every", "30"])
        if trace is not None:
            for b in FORCED:
                bench(args, out / q / f"perso_{b}", trace, q, SHORT_S, ["--biome", b, "--every", "30"])
        print(f"Qualité {q} finie ({(time.time() - t0) / 60:.0f} min)", flush=True)
    return analyse(out)


# --- analyse ----------------------------------------------------------------------------------------------

def run_dir(path: Path) -> Path | None:
    """Dossier du scénario écrit par sim_bench (`<out>/demo/`)."""
    hits = sorted(path.glob("*/moteur.csv"))
    return hits[0].parent if hits else None


def journal_distance(path: Path) -> list[tuple[float, float]]:
    """(heure unix, distance m) des lignes `record` du journal de séance."""
    out = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("kind") == "record" and isinstance(d.get("ts"), (int, float)):
                out.append((float(d["ts"]), float(d.get("distance") or 0.0)))
    return out


def distance_at(track: list[tuple[float, float]], t: float) -> float | None:
    if not track or t < track[0][0] - 2.0 or t > track[-1][0] + 2.0:
        return None
    lo, hi = 0, len(track) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if track[mid][0] <= t:
            lo = mid
        else:
            hi = mid
    (t0, d0), (t1, d1) = track[lo], track[hi]
    return d0 if t1 <= t0 else d0 + (d1 - d0) * min(max((t - t0) / (t1 - t0), 0.0), 1.0)


def probe_rows(sdir: Path) -> list[dict[str, Any]]:
    """Lignes de la sonde (engine + nvidia-smi recalés par sim_bench), sinon celles de l'engine seul."""
    merged = sdir / "sonde" / "sonde.csv"
    return perf_probe.read_engine_csv(merged if merged.is_file() else sdir / "moteur.csv")


def stats(rows: list[dict[str, Any]], budget: dict[str, Any]) -> dict[str, Any]:
    def med(key: str) -> float | None:
        v = perf_probe.values(rows, key)
        return round(statistics.median(v), 2) if v else None

    def top(key: str) -> float | None:
        v = perf_probe.values(rows, key)
        return round(max(v), 1) if v else None

    util = perf_probe.values(rows, "gpu_util_pct")
    busy = round(100.0 * sum(u > 95.0 for u in util) / len(util), 1) if util else None
    s = {"secondes": len(rows), "fps": med("fps"), "p99_ms": med("frame_p99_ms"), "gpu_ms": med("gpu_ms"),
         "gpu_sature_pct": busy, "vram_godot_max_mb": top("vram_mb"), "textures_max_mb": top("texture_mb"),
         "vram_nvidia_max_mb": top("gpu_mem_mb")}
    ok = []
    if s["fps"] is not None:
        ok.append(s["fps"] >= budget["fps_median_min"])
    if s["p99_ms"] is not None:
        ok.append(s["p99_ms"] < budget["p99_ms_max"])
    if s["gpu_ms"] is not None:
        ok.append(s["gpu_ms"] <= budget["gpu_ms_median_max"])
    s["budgets_ok"] = all(ok) if ok else None
    return s


def ground_textures_mb(sdir: Path) -> float | None:
    """Plus forte « textures du sol N Mo » des lignes [perf-rendu] du journal de l'engine (lot U17)."""
    log = sdir / "engine.log"
    if not log.is_file():
        return None
    vals = [float(m.group(1)) for m in re.finditer(r"\[perf-rendu\].*textures du sol ([0-9.]+) Mo",
                                                   log.read_text(encoding="utf-8", errors="replace"))]
    return max(vals) if vals else None


def route_length(out: Path) -> float | None:
    """Longueur du tour compilé (`routes/parts.json`), un peu plus longue que celle du plan du générateur."""
    try:
        for info in json.loads((out / "routes" / "parts.json").read_text(encoding="utf-8")):
            if info.get("route") == TOUR_WORLD:
                return float(info["length_m"])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def split_tour(rows: list[dict[str, Any]], track: list[tuple[float, float]], warm_s: float,
               length_m: float | None = None,
               biomes: tuple[str, ...] = make_biome_world.TOUR) -> dict[str, list[dict[str, Any]]]:
    """Secondes de la sonde rangées par biome ; la distance du journal est ramenée à l'abscisse du plan.

    `biomes` : blocs du parcours généré (le tour par défaut ; un tronçon pour cout_rendu.py --troncon)."""
    plan = make_biome_world.Plan(tuple(biomes), False, False)
    scale = plan.length_m / length_m if length_m else 1.0
    t_min = min(perf_probe.values(rows, "t_s"), default=0.0) + warm_s
    groups: dict[str, list[dict[str, Any]]] = {b: [] for b in biomes}
    groups["frontières"] = []
    for r in rows:
        if not isinstance(r.get("unix_s"), (int, float)) or r.get("t_s", 0) < t_min:
            continue
        d = distance_at(track, float(r["unix_s"]))
        if d is None:
            continue
        d *= scale
        if d <= 0.0 or d >= plan.length_m:
            continue
        w = plan.weights(d)
        main = max(w, key=w.get)
        groups[main if w[main] >= PURE_SHARE else "frontières"].append(r)
    return groups


def pick_captures(sdir: Path, quality: str, dest: Path) -> list[dict[str, str]]:
    """Captures `dNNNNN` du tour : milieu de chaque biome (2 km × k + 1 km) et frontières (2 km × k)."""
    picked = []
    block = make_biome_world.BLOCK_M
    for png in sorted(sdir.glob("*_d[0-9][0-9][0-9][0-9][0-9].png")):
        s_m = float(png.stem.rsplit("_d", 1)[1])
        k, rest = divmod(s_m, block)
        tour = make_biome_world.TOUR
        if abs(rest - block / 2) < 1.0 and int(k) < len(tour):
            label = tour[int(k)]
        elif rest < 1.0 and 0 < int(k) < len(tour):
            label = f"{tour[int(k) - 1]}__{tour[int(k)]}"
        else:
            continue
        name = f"{label}_{quality}.png"
        shutil.copy(png, dest / name)
        picked.append({"label": label, "quality": quality, "file": name})
    return picked


def analyse(out: Path) -> int:
    targets = perf_probe.load_targets()
    warm = float(targets.get("warmup_s", 20))
    length = route_length(out)
    result: dict[str, Any] = {"tour": {}, "cote": {}, "perso": {}, "textures_sol_mb": {}, "criteres": []}
    planche = out / "planche"
    planche.mkdir(parents=True, exist_ok=True)
    shots: list[dict[str, str]] = []
    for q in QUALITIES:
        budget = targets["presets"][q]
        tdir = run_dir(out / q / "tour")
        if tdir is None:
            continue
        groups = split_tour(probe_rows(tdir), journal_distance(tdir / "seance.jsonl"), warm, length)
        result["tour"][q] = {b: stats(rows, budget) for b, rows in groups.items()}
        result["textures_sol_mb"][q] = ground_textures_mb(tdir)
        shots += pick_captures(tdir, q, planche)
        cdir = run_dir(out / q / "cote")
        if cdir is not None:
            rows = [r for r in probe_rows(cdir) if r.get("t_s", 0) >= warm]
            result["cote"][q] = stats(rows, budget)
            for png in sorted(cdir.glob("*_t*.png"))[-1:]:
                shutil.copy(png, planche / f"cote_mer_{q}.png")
                shots.append({"label": "cote_mer", "quality": q, "file": f"cote_mer_{q}.png"})
        for b in FORCED:
            pdir = run_dir(out / q / f"perso_{b}")
            if pdir is None:
                continue
            rows = [r for r in probe_rows(pdir) if r.get("t_s", 0) >= warm]
            result["perso"].setdefault(q, {})[b] = stats(rows, budget)
            for png in sorted(pdir.glob("*_t*.png"))[-1:]:
                shutil.copy(png, planche / f"perso_{b}_{q}.png")
                shots.append({"label": f"perso_{b}", "quality": q, "file": f"perso_{b}_{q}.png"})

    crit = result["criteres"]

    def add(ok: bool | None, label: str, detail: str) -> None:
        crit.append({"ok": ok, "critere": label, "mesure": detail})

    low = result["tour"].get("low", {})
    for b in make_biome_world.TOUR:
        s = low.get(b)
        if not s or s["fps"] is None:
            add(None, f"U18 §5.1 low {b}", "pas de mesure")
            continue
        add(s["fps"] >= U18_FPS_MIN and (s["p99_ms"] or 99.0) < U18_P99_MAX, f"U18 §5.1 low {b}",
            f"{s['fps']} i/s, p99 {s['p99_ms']} ms ({s['secondes']} s)")
    high = result["tour"].get("high", {})
    tex = [v for v in [result["textures_sol_mb"].get("high")] + [s.get("textures_max_mb") for s in high.values()]
           if isinstance(v, (int, float))]
    add(max(tex) < TEXTURE_LIMIT_MB if tex else None, "U18 §5.2 textures du décor en high < 1 Go",
        f"{max(tex):.0f} Mo" if tex else "pas de mesure")
    for q in QUALITIES:
        for b, s in result["tour"].get(q, {}).items():
            if b != "frontières" and s["budgets_ok"] is not None:
                add(s["budgets_ok"], f"budgets {q} {b}", f"{s['fps']} i/s, p99 {s['p99_ms']}, GPU {s['gpu_ms']} ms")
    add(None, "U18 §5.3 aucune frontière droite entre biomes", "à juger sur planche/ (propriétaire)")

    (out / "resume.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(out, result)
    write_planche(planche, shots)
    failed = sum(1 for c in crit if c["ok"] is False)
    print(f"Résumé : {out / 'resume.md'} ; planche : {planche / 'index.html'}")
    print("RÉSULTAT : " + ("recette U18 (PC) OK" if not failed else f"ÉCHEC ({failed} critère(s))"))
    return 0 if not failed else 1


def fmt(v: Any) -> str:
    return "—" if v is None else (f"{v:g}" if isinstance(v, (int, float)) else str(v))


def write_markdown(out: Path, result: dict[str, Any]) -> None:
    head = "| Biome | s | i/s | p99 ms | GPU ms | GPU saturé % | VRAM Godot Mo | textures Mo | VRAM nvidia Mo |"
    sep = "| --- " * 9 + "|"
    keys = ("secondes", "fps", "p99_ms", "gpu_ms", "gpu_sature_pct", "vram_godot_max_mb", "textures_max_mb",
            "vram_nvidia_max_mb")
    lines = ["# Recette U18, partie PC (7bt)", ""]
    for q in QUALITIES:
        if q not in result["tour"]:
            continue
        lines += [f"## {q}", "", f"Textures du sol (ligne [perf-rendu]) : {fmt(result['textures_sol_mb'].get(q))} Mo",
                  "", head, sep]
        rows = dict(result["tour"][q])
        if q in result["cote"]:
            rows["côte avec la mer (90 s)"] = result["cote"][q]
        for b, s in result["perso"].get(q, {}).items():
            rows[f"{PERSONAL}, {b} forcé"] = s
        for b, s in rows.items():
            lines.append(f"| {b} | " + " | ".join(fmt(s.get(k)) for k in keys) + " |")
        lines.append("")
    lines += ["## Critères", ""]
    for c in result["criteres"]:
        mark = {True: "OK", False: "ÉCHEC", None: "À VOIR"}[c["ok"]]
        lines.append(f"- [{mark}] {c['critere']} : {c['mesure']}")
    (out / "resume.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_planche(planche: Path, shots: list[dict[str, str]]) -> None:
    labels = list(dict.fromkeys(s["label"] for s in shots))
    by = {(s["label"], s["quality"]): s["file"] for s in shots}
    rows = []
    for lab in labels:
        cells = "".join(f'<td><img src="{by[(lab, q)]}" width="420"></td>' if (lab, q) in by else "<td>—</td>"
                        for q in QUALITIES)
        rows.append(f"<tr><th>{lab}</th>{cells}</tr>")
    (planche / "index.html").write_text(
        "<!doctype html><meta charset=utf-8><title>Recette U18 : planche</title>"
        "<table><tr><th></th>" + "".join(f"<th>{q}</th>" for q in QUALITIES) + "</tr>" + "".join(rows)
        + "</table>\n", encoding="utf-8")


# --- étape vélo gravel (7bu) ------------------------------------------------------------------------------

GRAVEL_STEADY_M = 100.0       # mètres écartés après chaque changement de surface (fondu de 20 m et élan)
GRAVEL_SIM_MIN_PCT = 0.3      # U18 §5.4 « nettement plus forte » : au moins 0,3 point en moyenne en non revêtu
GRAVEL_PAVED_MAX_PCT = 0.05   # sur le bitume, aucun supplément du gravel
GRAVEL_OFFSET_MAX_PCT = 4.0   # U18 §5.4 : jamais plus de 4 points de supplément, vent compris
GRAVEL_ERG_DW_MAX = 5.0       # U18 §5.4 : puissance ERG inchangée (écart des moyennes, W)
GRAVEL_ERG_SLOWER = 0.97      # vitesse en non revêtu au plus 97 % de celle du bitume (même puissance, même pente)
GRAVEL_MIN_RECORDS = 50       # une partie (SIM ou ERG, revêtu ou non) compte à partir de 50 mesures (≈ 50 s)


def read_journal(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    header: dict[str, Any] = {}
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("kind") == "header" and not header:
                header = row
            elif row.get("kind") == "record":
                records.append(row)
    return header, records


def steady_records(records: list[dict[str, Any]], steady_m: float = GRAVEL_STEADY_M) -> list[dict[str, Any]]:
    """Mesures roulées (au-dessus de 1 m/s) à plus de `steady_m` du dernier changement de surface ou de mode."""
    out: list[dict[str, Any]] = []
    key, since = None, 0.0
    for r in records:
        if r.get("surface") is None:
            key = None
            continue
        k = (r["surface"] != "paved", r.get("mode", "SIM"))
        d = float(r.get("distance") or 0.0)
        if k != key:
            key, since = k, d
        if d - since >= steady_m and float(r.get("speed") or 0.0) > 1.0:
            out.append(r)
    return out


def _f2(v: Any) -> str:
    return "—" if v is None else (f"{round(v, 2):g}" if isinstance(v, float) else str(v))


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def gravel_stats(records: list[dict[str, Any]], params: Any = None, steady_speed: Any = None,
                 max_offset_pct: float = GRAVEL_OFFSET_MAX_PCT) -> dict[str, Any]:
    """Chiffres de la séance gravel : supplément de pente en SIM, puissance et vitesse en ERG, par surface.

    `params` (PhysicsParams du joueur) et `steady_speed` (physics.steady_speed) : vitesse attendue sur le bitume
    à la même puissance et sur la même pente ; sans eux, la partie vitesse de l'ERG n'est pas jugée."""
    rows = steady_records(records)
    res: dict[str, Any] = {"records": len(records), "steady": len(rows)}
    total = [float(r.get("wind_grade_pct") or 0.0) + float(r.get("gravel_grade_pct") or 0.0)
             for r in records if r.get("mode", "SIM") == "SIM" and r.get("surface") is not None]
    res["offset_raw_max"] = max(total) if total else None
    res["offset_sent_max"] = max(min(t, max_offset_pct) for t in total) if total else None
    for mode in ("SIM", "ERG"):
        for unpaved in (False, True):
            part = [r for r in rows if r.get("mode", "SIM") == mode and (r["surface"] != "paved") == unpaved]
            name = f"{mode.lower()}_{'non_revetu' if unpaved else 'bitume'}"
            dist = [float(r.get("distance") or 0.0) for r in part]
            stat: dict[str, Any] = {
                "n": len(part),
                "m": round(sum(b - a for a, b in zip(dist, dist[1:]) if 0.0 < b - a < 20.0)),
                "gravel_pct": _mean([float(r.get("gravel_grade_pct") or 0.0) for r in part]),
                "power_w": _mean([float(r["power"]) for r in part if r.get("power") is not None]),
                "target_w": _mean([float(r["target_w"]) for r in part if r.get("target_w") is not None]),
                "speed_kmh": _mean([float(r.get("speed") or 0.0) * 3.6 for r in part]),
            }
            if params is not None and steady_speed is not None:
                ratios = []
                for r in part:
                    p = r.get("power")
                    if p is None or float(p) <= 0.0:
                        continue
                    params.wind_mps = float(r.get("head_mps") or 0.0)
                    v0 = steady_speed(float(p), float(r.get("grade") or 0.0), params, float(r.get("alt") or 0.0))
                    if v0 > 0.5:
                        ratios.append(float(r.get("speed") or 0.0) / v0)
                params.wind_mps = 0.0
                stat["speed_ratio"] = _mean(ratios)
            res[name] = stat
    return res


def gravel_checks(res: dict[str, Any]) -> list[dict[str, Any]]:
    """Critères U18 §5.4 jugés sur les chiffres de `gravel_stats` (None : partie non roulée)."""
    checks: list[dict[str, Any]] = []

    def add(ok: bool | None, label: str, detail: str) -> None:
        checks.append({"ok": ok, "critere": label, "detail": detail})

    sp, su = res["sim_bitume"], res["sim_non_revetu"]
    ep, eu = res["erg_bitume"], res["erg_non_revetu"]
    sim_ok = sp["n"] >= GRAVEL_MIN_RECORDS and su["n"] >= GRAVEL_MIN_RECORDS
    erg_ok = ep["n"] >= GRAVEL_MIN_RECORDS and eu["n"] >= GRAVEL_MIN_RECORDS
    add((su["gravel_pct"] or 0.0) >= GRAVEL_SIM_MIN_PCT and (sp["gravel_pct"] or 0.0) <= GRAVEL_PAVED_MAX_PCT
        if sim_ok else None,
        "§5.4 SIM : résistance plus forte en non revêtu",
        f"supplément moyen {_f2(su['gravel_pct'])} point(s) en non revêtu (≥ {GRAVEL_SIM_MIN_PCT}), "
        f"{_f2(sp['gravel_pct'])} sur le bitume (≤ {GRAVEL_PAVED_MAX_PCT})")
    add(res["offset_sent_max"] <= GRAVEL_OFFSET_MAX_PCT + 1e-6 if res["offset_sent_max"] is not None else None,
        "§5.4 SIM : jamais plus de 4 points en supplément (vent compris)",
        f"supplément envoyé au plus {_f2(res['offset_sent_max'])} point(s) "
        f"(avant la borne : {_f2(res['offset_raw_max'])})")
    if erg_ok and ep["target_w"] is not None and eu["target_w"] is not None:
        dw = abs(eu["target_w"] - ep["target_w"])
        add(dw <= GRAVEL_ERG_DW_MAX, "§5.4 ERG : puissance inchangée",
            f"cible moyenne {_f2(ep['target_w'])} W sur le bitume, {_f2(eu['target_w'])} W en non revêtu "
            f"(écart ≤ {GRAVEL_ERG_DW_MAX:g} W)")
    else:
        add(None, "§5.4 ERG : puissance inchangée", "partie ERG trop courte sur l'une des surfaces")
    rp, ru = ep.get("speed_ratio"), eu.get("speed_ratio")
    if erg_ok and rp and ru:
        add(ru / rp <= GRAVEL_ERG_SLOWER, "§5.4 ERG : vitesse plus faible en non revêtu",
            f"vitesse / vitesse du bitume attendue : {rp:.3f} sur le bitume, {ru:.3f} en non revêtu "
            f"(rapport {ru / rp:.3f} ≤ {GRAVEL_ERG_SLOWER})")
    else:
        add(None, "§5.4 ERG : vitesse plus faible en non revêtu",
            "partie ERG trop courte sur l'une des surfaces, ou modèle physique indisponible")
    return checks


def _player_physics() -> tuple[Any, Any, float]:
    """Modèle physique du joueur (config.toml local, jamais recopié) ; (None, None, 4) sans openride_core."""
    try:
        from openride_core import config as core_config
        from openride_core.physics import PhysicsParams, steady_speed
    except ImportError:
        return None, None, GRAVEL_OFFSET_MAX_PCT
    cfg = core_config.load()
    return PhysicsParams.from_config(cfg), steady_speed, float(cfg.wind.max_grade_offset_pct)


def write_gravel_markdown(path: Path, res: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    lines = ["# Recette U18, étape vélo gravel (7bu)", "",
             (f"Parcours : {res.get('route') or 'inconnu'} ; {res['records']} mesures, {res['steady']} "
              f"retenues (à plus de {GRAVEL_STEADY_M:g} m d'un changement de surface ou de mode)."), "",
             ("| Partie | Mesures | Mètres | Supplément gravel (pts) | Puissance (W) | Cible ERG (W) | km/h "
              "| Vitesse / attendue bitume |"),
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for name, label in (("sim_bitume", "SIM bitume"), ("sim_non_revetu", "SIM non revêtu"),
                        ("erg_bitume", "ERG bitume"), ("erg_non_revetu", "ERG non revêtu")):
        s = res[name]
        lines.append(f"| {label} | {s['n']} | {s['m']} | {_f2(s['gravel_pct'])} | {_f2(s['power_w'])} | "
                     f"{_f2(s['target_w'])} | {_f2(s['speed_kmh'])} | {_f2(s.get('speed_ratio'))} |")
    lines += ["", "| Critère | Résultat | Détail |", "| --- | --- | --- |"]
    for c in checks:
        mark = "OK" if c["ok"] else ("NON" if c["ok"] is False else "non jugé")
        lines.append(f"| {c['critere']} | {mark} | {c['detail']} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def cmd_gravel(args: argparse.Namespace) -> int:
    journal: Path | None = args.journal
    if journal is None:
        base = Path.home() / "OpenRide" / "Activities" / ".journal"
        found = sorted(base.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime) if base.is_dir() else []
        journal = found[-1] if found else None
    if journal is None or not journal.is_file():
        print("journal de séance introuvable (donner son chemin)", file=sys.stderr)
        return 2
    header, records = read_journal(journal)
    if not any(r.get("surface") is not None for r in records):
        print("gravel coupé dans ce journal (aucune colonne surface)", file=sys.stderr)
        return 2
    route = str(header.get("route_id") or "")
    params, steady, bound = _player_physics()
    res = gravel_stats(records, params, steady, bound)
    res["route"] = route if route.startswith("demo") else ("trace personnelle" if route else None)
    checks = gravel_checks(res)
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "resume_gravel.json").write_text(json.dumps({**res, "criteres": checks}, indent=1, ensure_ascii=False),
                                            encoding="utf-8")
    write_gravel_markdown(out / "resume_gravel.md", res, checks)
    print((out / "resume_gravel.md").read_text(encoding="utf-8"))
    judged = [c["ok"] for c in checks if c["ok"] is not None]
    return 0 if judged and all(judged) else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    la = sub.add_parser("lancer", help="parcours U19, bancs low/medium/high et analyse")
    la.add_argument("--out", type=Path, default=default_out())
    la.add_argument("--qualites", default=",".join(QUALITIES))
    la.add_argument("--vitesse", type=float, default=60.0, help="vitesse tenue sur le tour (km/h, défaut 60)")
    la.add_argument("--size", default="1680x1011", help="fenêtre (défaut 1680x1011, comme les bancs 7v)")
    la.add_argument("--trace", type=Path, help="parcours personnel compilé (défaut : le plus gros trouvé)")
    la.add_argument("--culling", default="off", choices=("on", "off"),
                    help="tri de ce que la caméra ne voit pas (lot S1, sim_bench --culling ; défaut off comme le jeu)")
    la.add_argument("--sans-trace", action="store_true", help="sauter l'étape 3 (biomes forcés sur la trace)")
    la.add_argument("--godot", type=Path, default=Path(os.environ["GODOT"]) if os.environ.get("GODOT") else None)
    an = sub.add_parser("analyser", help="refaire résumé et planche d'un dossier déjà mesuré")
    an.add_argument("dossier", type=Path)
    gr = sub.add_parser("gravel", help="étape vélo gravel (7bu) : critères U18 §5.4 lus au journal de séance")
    gr.add_argument("journal", type=Path, nargs="?", help="journal .jsonl (défaut : le plus récent)")
    gr.add_argument("--out", type=Path, default=default_out().with_name("u18_7bu"))
    args = ap.parse_args(argv)
    if args.cmd == "gravel":
        return cmd_gravel(args)
    if args.cmd == "analyser":
        return analyse(args.dossier) if args.dossier.is_dir() else 2
    args.qualites = [q for q in args.qualites.split(",") if q]
    bad = [q for q in args.qualites if q not in QUALITIES]
    if bad:
        print(f"qualité inconnue : {', '.join(bad)}", file=sys.stderr)
        return 2
    return cmd_lancer(args)


if __name__ == "__main__":
    sys.exit(main())
