#!/usr/bin/env python3
"""Sonde de performance du moteur, côté système (lot X13).

L'engine lancé avec `--perf-probe=FICHIER.csv` écrit chaque seconde ses mesures (temps d'image p50 et
p99, temps CPU et GPU de la vue, appels de dessin, objets, primitives, mémoire vidéo, tuiles et arbres :
`engine/scripts/perf_probe.gd`). Cet outil relève en même temps, chaque seconde :
- nvidia-smi s'il est là : charge du GPU, mémoire vidéo utilisée, température, fréquence ;
- le CPU (en % d'un cœur) et la mémoire résidente de chaque processus suivi (core, Godot), lus dans /proc.
Il recale les deux séries sur l'heure, puis écrit `sonde.csv`, `sonde.txt` (médianes, p99, maxima et
dérive entre la première et la dernière minute) et `rapport.html` (courbes).

Usage, avec le vrai jeu :

    OPENRIDE_PERF_PROBE=~/OpenRide/sonde/moteur.csv openride        # terminal 1 (ou openride-dev.sh)
    engine/tests/perf_probe.py watch                                  # terminal 2

`watch` attend le fichier de l'engine, mesure jusqu'à ce que l'engine n'écrive plus depuis 10 s (jeu
fermé), `--duration` ou Ctrl+C, puis écrit le rapport dans `~/OpenRide/sonde/<date>_<heure>/`.
`report DOSSIER` refait le rapport d'un dossier déjà mesuré. Le banc simulé l'utilise aussi :
`sim_bench.py --probe` (rapport dans le dossier du scénario).
`chauffe DOSSIER [--tranche-min 10]` donne, par tranche, les médianes du temps GPU de la vue, de la charge, de
la température et de la fréquence du GPU : un temps GPU qui monte avec la fréquence qui baisse est une
chauffe de la carte (endurance 7bi : `chauffe <scénario>/sonde`).
Budgets du préréglage (lot X14) : `sonde.txt` juge images/s, p99, GPU de la vue et GPU saturé face à
`perf_targets.json`, pour le préréglage noté par l'engine ; avec `--budgets`, un budget dépassé donne le
code de sortie 1 (`report --xvfb` : rendu logiciel, budgets en INFO).

Saccades et démarrage (lot X15) : l'engine écrit aussi, à côté de son fichier, `saccades.csv` (chaque
image de plus de 33 ms avec sa cause : tuile de terrain, tronçon OSM, arbres, capture, ou « inconnue »),
`taches.csv` (durée des tâches de fond) et `demarrage.txt` (première image jouable). Le rapport y ajoute
les 20 pires saccades, le compte par cause, les durées des tâches de fond et le temps de démarrage.
Bibliothèque standard seulement.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import shutil
import statistics
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

DEFAULT_ENGINE_CSV = Path.home() / "OpenRide" / "sonde" / "moteur.csv"
DEFAULT_OUT = Path.home() / "OpenRide" / "sonde"
# Processus suivis : nom de colonne → mots cherchés dans la ligne de commande.
PROCESSES = {"core": ("openride_core", "openride-core"), "godot": ("Godot", "godot")}
NVIDIA_QUERY = "utilization.gpu,memory.used,memory.total,temperature.gpu,clocks.gr"
NVIDIA_COLUMNS = ("gpu_util_pct", "gpu_mem_mb", "gpu_mem_total_mb", "gpu_temp_c", "gpu_clock_mhz")
IDLE_STOP_S = 10.0
# Colonnes résumées dans sonde.txt : (colonne, libellé, unité).
SUMMARY = (
    ("fps", "images/s", ""), ("frame_p50_ms", "temps d'image p50", "ms"),
    ("frame_p99_ms", "temps d'image p99", "ms"), ("frame_max_ms", "pire image", "ms"),
    ("cpu_ms", "CPU de la vue", "ms"), ("gpu_ms", "GPU de la vue", "ms"),
    ("draw_calls", "appels de dessin", ""), ("objects", "objets dessinés", ""),
    ("primitives", "primitives dessinées", ""), ("vram_mb", "mémoire vidéo (Godot)", "Mo"),
    ("static_mb", "mémoire statique (Godot)", "Mo"), ("nodes", "nœuds", ""),
    ("near_tiles", "tuiles proches", ""), ("far_tiles", "tuiles lointaines", ""),
    ("osm_chunks", "tronçons OSM", ""), ("trees", "arbres", ""),
    ("culled_near", "tuiles proches écartées (S1)", ""),
    ("gpu_util_pct", "charge du GPU", "%"), ("gpu_mem_mb", "mémoire vidéo (nvidia-smi)", "Mo"),
    ("gpu_temp_c", "température du GPU", "°C"), ("core_cpu_pct", "CPU du core", "%"),
    ("godot_cpu_pct", "CPU de Godot", "%"), ("core_rss_mb", "mémoire du core", "Mo"),
    ("godot_rss_mb", "mémoire de Godot", "Mo"),
)
# Dérive mesurée entre la première et la dernière minute (fuites, échauffement).
DRIFT = ("vram_mb", "static_mb", "nodes", "gpu_mem_mb", "godot_rss_mb", "core_rss_mb", "frame_p99_ms", "gpu_temp_c")
CHARTS = (
    ("Temps d'image (ms)", (("frame_p50_ms", "p50", "#2980b9"), ("frame_p99_ms", "p99", "#c0392b"))),
    ("Temps de la vue (ms)", (("cpu_ms", "CPU", "#8e44ad"), ("gpu_ms", "GPU", "#16a085"))),
    ("Appels de dessin et objets", (("draw_calls", "appels", "#d35400"), ("objects", "objets", "#7f8c8d"))),
    ("Primitives dessinées", (("primitives", "primitives", "#2c3e50"),)),
    ("Mémoire vidéo (Mo)", (("vram_mb", "Godot", "#27ae60"), ("gpu_mem_mb", "nvidia-smi", "#c0392b"))),
    ("Décor chargé", (("near_tiles", "tuiles proches", "#2980b9"), ("far_tiles", "lointaines", "#7f8c8d"),
                      ("osm_chunks", "tronçons OSM", "#d35400"), ("culled_near", "écartées (S1)", "#c0392b"))),
    ("Arbres", (("trees", "arbres", "#27ae60"),)),
    ("CPU des processus (% d'un cœur)", (("godot_cpu_pct", "Godot", "#2980b9"), ("core_cpu_pct", "core", "#d35400"))),
    ("GPU (nvidia-smi)", (("gpu_util_pct", "charge %", "#c0392b"), ("gpu_temp_c", "température °C", "#8e44ad"))),
)


# --- lecture -------------------------------------------------------------------------------

def _num(text: str) -> float | str:
    try:
        return float(text)
    except ValueError:
        return text


def read_engine_csv(path: Path) -> list[dict[str, Any]]:
    """Lignes du fichier de l'engine (séparateur « ; »), nombres convertis ; ligne incomplète ignorée."""
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh, delimiter=";"))
    if not rows:
        return []
    head = rows[0]
    return [{k: _num(v) for k, v in zip(head, r)} for r in rows[1:] if len(r) == len(head)]


def parse_nvidia(text: str) -> dict[str, float] | None:
    """Première ligne de `nvidia-smi --query-gpu=… --format=csv,noheader,nounits`."""
    line = text.strip().splitlines()[0] if text.strip() else ""
    parts = [p.strip() for p in line.split(",")]
    if len(parts) != len(NVIDIA_COLUMNS):
        return None
    out: dict[str, float] = {}
    for k, v in zip(NVIDIA_COLUMNS, parts):
        try:
            out[k] = float(v)
        except ValueError:
            pass   # « [N/A] » sur certaines cartes
    return out


def nvidia_sample() -> dict[str, float] | None:
    if shutil.which("nvidia-smi") is None:
        return None
    try:
        res = subprocess.run(["nvidia-smi", f"--query-gpu={NVIDIA_QUERY}", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return parse_nvidia(res.stdout) if res.returncode == 0 else None


def find_pids(patterns: tuple[str, ...], proc: Path = Path("/proc")) -> list[int]:
    """Processus dont un des trois premiers mots de la ligne de commande contient un des mots cherchés
    (le programme, ou `python -m openride_core` ; pas xvfb-run qui lance Godot, ni cet outil)."""
    me = os.getpid()
    out = []
    for d in proc.iterdir() if proc.is_dir() else []:
        if not d.name.isdigit() or int(d.name) == me:
            continue
        try:
            argv = (d / "cmdline").read_bytes().decode("utf-8", "replace").split("\0")
        except OSError:
            continue
        head = " ".join(argv[:3])
        if "perf_probe" not in head and any(p in head for p in patterns):
            out.append(int(d.name))
    return sorted(out)


def proc_times(pid: int, proc: Path = Path("/proc")) -> tuple[float, float] | None:
    """(temps CPU utilisateur + système en s, mémoire résidente en Mo) d'un processus."""
    try:
        stat = (proc / str(pid) / "stat").read_text()
        statm = (proc / str(pid) / "statm").read_text().split()
    except OSError:
        return None
    fields = stat.rsplit(")", 1)[1].split()   # le nom entre parenthèses peut contenir des espaces
    ticks = os.sysconf("SC_CLK_TCK")
    cpu_s = (int(fields[11]) + int(fields[12])) / ticks
    rss_mb = int(statm[1]) * os.sysconf("SC_PAGE_SIZE") / 1048576.0
    return cpu_s, rss_mb


class SystemSampler:
    """Relève nvidia-smi et le CPU des processus suivis chaque seconde, dans un fil à part."""

    def __init__(self, period_s: float = 1.0, processes: dict[str, tuple[str, ...]] | None = None) -> None:
        self.period_s = period_s
        self.processes = PROCESSES if processes is None else processes
        self.rows: list[dict[str, Any]] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last: dict[str, tuple[float, float]] = {}   # nom → (heure, temps CPU cumulé)

    def sample(self) -> dict[str, Any]:
        now = time.time()
        row: dict[str, Any] = {"unix_s": now}
        row.update(nvidia_sample() or {})
        for name, patterns in self.processes.items():
            cpu_total = rss_total = 0.0
            found = False
            for pid in find_pids(patterns):
                t = proc_times(pid)
                if t is not None:
                    found = True
                    cpu_total += t[0]
                    rss_total += t[1]
            if not found:
                self._last.pop(name, None)
                continue
            row[f"{name}_rss_mb"] = rss_total
            prev = self._last.get(name)
            if prev is not None and now > prev[0]:
                row[f"{name}_cpu_pct"] = max(0.0, (cpu_total - prev[1]) / (now - prev[0]) * 100.0)
            self._last[name] = (now, cpu_total)
        self.rows.append(row)
        return row

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.sample()
            self._stop.wait(self.period_s)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="perf_probe", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=10)


# --- analyse -------------------------------------------------------------------------------

def merge(engine: list[dict[str, Any]], system: list[dict[str, Any]], tolerance_s: float = 1.5) -> list[dict[str, Any]]:
    """Ajoute à chaque ligne de l'engine le relevé système le plus proche dans le temps (± tolérance).
    Sans ligne de l'engine, renvoie les relevés système seuls (t_s compté depuis le premier)."""
    if not engine:
        t0 = system[0]["unix_s"] if system else 0.0
        return [{"t_s": r["unix_s"] - t0, **r} for r in system]
    out = []
    j = 0
    for e in engine:
        row = dict(e)
        t = e.get("unix_s")
        if isinstance(t, float) and system:
            while j + 1 < len(system) and abs(system[j + 1]["unix_s"] - t) <= abs(system[j]["unix_s"] - t):
                j += 1
            if abs(system[j]["unix_s"] - t) <= tolerance_s:
                row.update({k: v for k, v in system[j].items() if k != "unix_s"})
        out.append(row)
    return out


def columns_of(rows: list[dict[str, Any]]) -> list[str]:
    cols: list[str] = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    return cols


def values(rows: list[dict[str, Any]], key: str) -> list[float]:
    return [float(r[key]) for r in rows if isinstance(r.get(key), (int, float))]


def percentile(vals: list[float], q: float) -> float:
    s = sorted(vals)
    return s[min(int(len(s) * q), len(s) - 1)]


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Médiane, p99 et maximum de chaque mesure ; dérive (dernière minute − première minute)."""
    out: dict[str, Any] = {"rows": len(rows), "duration_s": 0.0, "stats": {}, "drift": {}}
    ts = values(rows, "t_s")
    if ts:
        out["duration_s"] = max(ts) - min(ts)
    for key, _label, _unit in SUMMARY:
        v = values(rows, key)
        if v:
            out["stats"][key] = {"p50": statistics.median(v), "p99": percentile(v, 0.99), "max": max(v)}
    # Images d'une capture d'écran de test (lot X35) : déjà hors p99 et pire image côté engine, comptées à part.
    cap = values(rows, "capture")
    if cap and sum(cap) > 0:
        out["captures"] = {"frames": int(sum(cap)), "max_ms": max(values(rows, "capture_max_ms"), default=0.0)}
    if ts and out["duration_s"] >= 120.0:
        t_first, t_last = min(ts) + 60.0, max(ts) - 60.0
        for key in DRIFT:
            first = [float(r[key]) for r in rows if isinstance(r.get(key), (int, float)) and r["t_s"] <= t_first]
            last = [float(r[key]) for r in rows if isinstance(r.get(key), (int, float)) and r["t_s"] >= t_last]
            if first and last:
                out["drift"][key] = statistics.median(last) - statistics.median(first)
    return out


def summary_text(summary: dict[str, Any], title: str) -> str:
    lines = [title, f"{summary['rows']} relevés sur {summary['duration_s'] / 60:.1f} min", ""]
    labels = {k: (lab, unit) for k, lab, unit in SUMMARY}
    lines.append(f"  {'mesure':<28} {'médiane':>10} {'p99':>10} {'max':>10}")
    for key, st in summary["stats"].items():
        lab, unit = labels[key]
        name = f"{lab} ({unit})" if unit else lab
        lines.append(f"  {name:<28} {st['p50']:>10.1f} {st['p99']:>10.1f} {st['max']:>10.1f}")
    if summary.get("captures"):
        c = summary["captures"]
        lines += ["", f"Images des captures d'écran mises à part : {c['frames']} (pire {c['max_ms']:.0f} ms), "
                  "hors temps d'image p99, pire image et saccades."]
    if summary["drift"]:
        lines += ["", "Dérive (médiane de la dernière minute − première minute) :"]
        for key, d in summary["drift"].items():
            lab, unit = labels.get(key, (key, ""))
            lines.append(f"  {lab} : {d:+.1f} {unit}".rstrip())
    elif summary["duration_s"] < 120.0:
        lines += ["", "Dérive non calculée : moins de 2 min de mesures."]
    return "\n".join(lines) + "\n"


# --- endurance (lot X16) -------------------------------------------------------------------

# Seuils de l'essai d'endurance (recette 1.0, lignes 17 et 18 : 30 images/s en low, 1 h sans plantage
# ni saccade). Pentes en Mo par heure, mesurées après la mise en route.
ENDURANCE_LIMITS = {
    "warmup_s": 300.0,           # chargement du parcours et premières tuiles : hors calcul des pentes
    "min_fps_p50": 30.0,         # médiane des images/s (fenêtre réelle seulement)
    "max_fps_drop_pct": 10.0,    # images/s des 10 dernières minutes contre les 10 premières
    "stutter_ms": 100.0,         # une seconde dont la pire image dépasse ce temps est une saccade
    "max_stutters_per_h": 6.0,
    "min_slope_span_s": 1200.0,  # pente jugée sur 20 min au moins, sinon indicative
    "slopes_mb_per_h": {"godot_rss_mb": 100.0, "core_rss_mb": 20.0, "vram_mb": 50.0, "gpu_mem_mb": 100.0,
                        "static_mb": 50.0},
}


def slope_per_hour(rows: list[dict[str, Any]], key: str, after_s: float = 0.0) -> float | None:
    """Pente (unité par heure) de la droite des moindres carrés de `key` en fonction de t_s, calculée sur
    la médiane de chaque minute (un pic d'une seconde, un processus fils par exemple, ne pèse pas)."""
    raw = [(float(r["t_s"]), float(r[key])) for r in rows
           if isinstance(r.get(key), (int, float)) and isinstance(r.get("t_s"), (int, float)) and r["t_s"] >= after_s]
    if len(raw) < 10:
        return None
    minutes: dict[int, list[tuple[float, float]]] = {}
    for t, v in raw:
        minutes.setdefault(int(t // 60), []).append((t, v))
    pts = [(statistics.median(t for t, _ in m), statistics.median(v for _, v in m)) for m in minutes.values()]
    if len(pts) < 2:
        pts = raw
    mt = statistics.fmean(t for t, _ in pts)
    mv = statistics.fmean(v for _, v in pts)
    den = sum((t - mt) ** 2 for t, _ in pts)
    if den <= 0:
        return None
    return sum((t - mt) * (v - mv) for t, v in pts) / den * 3600.0


def endurance_checks(rows: list[dict[str, Any]], real_window: bool,
                     limits: dict[str, Any] | None = None) -> list[tuple[bool | None, str, str]]:
    """Vérifications de l'essai d'endurance : (réussi, libellé, mesure) ; réussi vaut None pour une mesure
    donnée à titre indicatif (images/s sous Xvfb, rendu logiciel)."""
    lim = {**ENDURANCE_LIMITS, **(limits or {})}
    out: list[tuple[bool | None, str, str]] = []
    ts = values(rows, "t_s")
    if not ts:
        return [(False, "endurance : mesures de l'engine", "aucune ligne de la sonde")]
    warm = min(ts) + lim["warmup_s"]
    steady = [r for r in rows if isinstance(r.get("t_s"), (int, float)) and r["t_s"] >= warm]
    fps = values(steady, "fps")
    if fps:
        p50 = statistics.median(fps)
        ok = p50 >= lim["min_fps_p50"] if real_window else None
        out.append((ok, "endurance : images/s", f"médiane {p50:.1f}, 1er centile {percentile(fps, 0.01):.1f}"
                    f" (seuil {lim['min_fps_p50']:.0f}{'' if real_window else ', non appliqué sous Xvfb'})"))
        first = values([r for r in steady if r["t_s"] < warm + 600.0], "fps")
        last = values([r for r in steady if r["t_s"] > max(ts) - 600.0], "fps")
        if first and last and max(ts) - warm >= 1800.0:
            drop = (1.0 - statistics.median(last) / statistics.median(first)) * 100.0 if statistics.median(first) else 0.0
            out.append((drop <= lim["max_fps_drop_pct"] if real_window else None, "endurance : images/s dans la durée",
                        f"{statistics.median(first):.1f} au début, {statistics.median(last):.1f} à la fin ({drop:+.0f} %)"))
    worst = values(steady, "frame_max_ms")
    if worst:
        stutters = sum(w > lim["stutter_ms"] for w in worst)
        hours = max((max(ts) - warm) / 3600.0, 1e-6)
        rate = stutters / hours
        shots = sum(w > lim["stutter_ms"] for w in values(steady, "capture_max_ms"))
        out.append((rate <= lim["max_stutters_per_h"] if real_window else None, "endurance : saccades",
                    f"{stutters} seconde(s) avec une image de plus de {lim['stutter_ms']:.0f} ms, {rate:.1f} par heure"
                    f" (seuil {lim['max_stutters_per_h']:.0f})"
                    + (f" ; {shots} autre(s) due(s) aux captures d'écran, non comptée(s)" if shots else "")))
    long_enough = max(ts) - warm >= lim["min_slope_span_s"]
    labels = {k: lab for k, lab, _ in SUMMARY}
    for key, max_slope in lim["slopes_mb_per_h"].items():
        slope = slope_per_hour(rows, key, warm)
        if slope is None:
            continue
        note = "" if long_enough else f", indicatif : moins de {lim['min_slope_span_s'] / 60:.0f} min mesurées"
        out.append((slope <= max_slope if long_enough else None, f"endurance : croissance de la {labels.get(key, key)}",
                    f"{slope:+.1f} Mo/h (seuil {max_slope:.0f}{note})"))
    return out


# --- chauffe du GPU dans la durée (enquête 7bi) ------------------------------------------------

HEAT_COLUMNS = (("gpu_ms", "GPU ms"), ("gpu_util_pct", "charge %"), ("gpu_temp_c", "temp °C"),
                ("gpu_clock_mhz", "fréq. MHz"), ("fps", "i/s"), ("core_cpu_pct", "CPU core %"))


def heat_windows(rows: list[dict[str, Any]], window_s: float = 600.0,
                 warmup_s: float = 60.0) -> list[dict[str, Any]]:
    """Médianes par tranche de `window_s` (temps GPU de la vue, charge, température, fréquence, images/s,
    CPU du core) et part des secondes à plus de 95 % de charge : un temps GPU qui monte quand la fréquence
    baisse est une chauffe de la carte, pas une scène plus lourde."""
    ts = values(rows, "t_s")
    if not ts:
        return []
    start = min(ts) + warmup_s
    groups: dict[int, list[dict[str, Any]]] = {}
    for r in rows:
        t = r.get("t_s")
        if isinstance(t, (int, float)) and t >= start:
            groups.setdefault(int((t - start) // window_s), []).append(r)
    out = []
    for k in sorted(groups):
        g = groups[k]
        w: dict[str, Any] = {"debut_min": round((start - min(ts) + k * window_s) / 60.0, 1), "secondes": len(g)}
        for key, _ in HEAT_COLUMNS:
            v = values(g, key)
            w[key] = round(statistics.median(v), 2) if v else None
        util = values(g, "gpu_util_pct")
        w["busy95_pct"] = round(100.0 * sum(u > 95.0 for u in util) / len(util), 1) if util else None
        out.append(w)
    return out


def heat_text(windows: list[dict[str, Any]]) -> str:
    """Tableau des tranches et lecture : écart du temps GPU et de la fréquence entre la première et la dernière."""
    if not windows:
        return "Aucune mesure après la mise en route.\n"
    head = f"{'début':>7}  " + "  ".join(f"{lab:>10}" for _, lab in HEAT_COLUMNS) + f"  {'>95 %':>6}"
    lines = [head]
    for w in windows:
        cells = "  ".join(f"{w[k]:>10.2f}" if w[k] is not None else f"{'-':>10}" for k, _ in HEAT_COLUMNS)
        busy = f"{w['busy95_pct']:>5.1f}%" if w["busy95_pct"] is not None else f"{'-':>6}"
        lines.append(f"{w['debut_min']:>5.0f} m  {cells}  {busy}")
    a, b = windows[0], windows[-1]
    if len(windows) > 1 and a["gpu_ms"] and b["gpu_ms"]:
        d_gpu = (b["gpu_ms"] / a["gpu_ms"] - 1.0) * 100.0
        msg = f"GPU {a['gpu_ms']:.2f} → {b['gpu_ms']:.2f} ms ({d_gpu:+.0f} %)"
        if a["gpu_clock_mhz"] and b["gpu_clock_mhz"]:
            d_clk = (b["gpu_clock_mhz"] / a["gpu_clock_mhz"] - 1.0) * 100.0
            msg += f", fréquence {a['gpu_clock_mhz']:.0f} → {b['gpu_clock_mhz']:.0f} MHz ({d_clk:+.0f} %)"
            if a["gpu_temp_c"] and b["gpu_temp_c"]:
                msg += f", température {a['gpu_temp_c']:.0f} → {b['gpu_temp_c']:.0f} °C"
            if d_gpu > 3.0 and d_clk < -3.0:
                msg += " : la carte ralentit en chauffant (temps GPU qui monte avec la fréquence qui baisse)"
            elif d_gpu > 3.0:
                msg += " : fréquence stable, le temps GPU monte pour une autre raison (scène, pilote)"
        lines += ["", msg]
    return "\n".join(lines) + "\n"


# --- budgets par préréglage (lot X14) ---------------------------------------------------------

TARGETS_FILE = Path(__file__).resolve().parent / "perf_targets.json"


def load_targets(path: Path = TARGETS_FILE) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def budget_checks(rows: list[dict[str, Any]], targets: dict[str, Any] | None = None,
                  real_window: bool = True) -> list[tuple[bool | None, str, str]]:
    """Vérifications des budgets du préréglage noté par l'engine dans la sonde (pas celui de la ligne de
    commande : lot X32) : (réussi, libellé, mesure). Réussi vaut None sous Xvfb (rendu logiciel, à titre
    indicatif) et pour une mesure absente (pas de nvidia-smi)."""
    t = targets or load_targets()
    presets = presets_of(rows)
    if len(presets) != 1:
        return [(False, "budgets du préréglage", "aucun préréglage noté dans la sonde" if not presets
                 else f"plusieurs préréglages dans la mesure ({', puis '.join(presets)}) : budgets non jugés")]
    preset = presets[0]
    budget = t["presets"].get(preset)
    if budget is None:
        return [(False, "budgets du préréglage", f"pas de budget pour {preset} dans perf_targets.json")]
    ts = values(rows, "t_s")
    warm = (min(ts) if ts else 0.0) + float(t.get("warmup_s", 0))
    steady = [r for r in rows if isinstance(r.get("t_s"), (int, float)) and r["t_s"] >= warm]
    note = "" if real_window else ", indicatif sous Xvfb"
    out: list[tuple[bool | None, str, str]] = []

    def judge(label: str, vals: list[float], ok_of: Callable[[float], bool], text: Callable[[float], str]) -> None:
        if not vals:
            out.append((None, label, "pas de mesure"))
            return
        v = statistics.median(vals)
        out.append((ok_of(v) if real_window else None, label, text(v) + note))

    fmin, pmax, gmax = budget["fps_median_min"], budget["p99_ms_max"], budget["gpu_ms_median_max"]
    judge(f"budget {preset} : images/s", values(steady, "fps"), lambda v: v >= fmin,
          lambda v: f"médiane {v:.1f} (au moins {fmin})")
    judge(f"budget {preset} : temps d'image p99", values(steady, "frame_p99_ms"), lambda v: v < pmax,
          lambda v: f"{v:.1f} ms (médiane des p99 de chaque seconde, sous {pmax} ms)")
    judge(f"budget {preset} : GPU de la vue", values(steady, "gpu_ms"), lambda v: v <= gmax,
          lambda v: f"médiane {v:.2f} ms (au plus {gmax} ms)")
    util = values(steady, "gpu_util_pct")
    busy_max, busy = budget["gpu_busy95_pct_max"], float(t.get("busy_pct", 95))
    if util:
        share = 100.0 * sum(u > busy for u in util) / len(util)
        out.append(((share <= busy_max) if real_window else None, f"budget {preset} : GPU saturé",
                    f"{share:.1f} % des secondes au-dessus de {busy:.0f} % de charge (au plus {busy_max} %){note}"))
    else:
        out.append((None, f"budget {preset} : GPU saturé", "pas de mesure (nvidia-smi absent)"))
    return out


def budget_text(checks: list[tuple[bool | None, str, str]]) -> str:
    return "\n".join(f"  [{'INFO' if ok is None else 'OK' if ok else 'ÉCHEC'}] {label} : {msg}"
                     for ok, label, msg in checks)


def presets_of(rows: list[dict[str, Any]]) -> list[str]:
    """Préréglages appliqués, dans l'ordre (l'engine note la qualité réellement appliquée, lot X32)."""
    out: list[str] = []
    for r in rows:
        p = str(r.get("preset") or "")
        if p and (not out or out[-1] != p):
            out.append(p)
    return out


def quality_check(summary: dict[str, Any], wanted: str) -> tuple[bool, str]:
    """Garde-fou du lot X32 : toutes les secondes mesurées l'ont été dans le préréglage voulu."""
    seen = summary.get("presets") or []
    if not seen:
        return False, "aucun préréglage noté dans la sonde"
    if any(p != wanted for p in seen):
        return False, f"qualité voulue {wanted}, mesurée en {', puis '.join(seen)}"
    return True, f"{wanted} sur toute la mesure"


# --- saccades et démarrage (lot X15) -----------------------------------------------------

STALL_TOP = 20
STARTUP_PREFIX = "Démarrage : première image jouable à "


def read_stalls(engine_dir: Path) -> dict[str, Any] | None:
    """Fichiers X15 de l'engine dans `engine_dir` : saccades, tâches de fond et démarrage (ms, ou None).
    None si l'engine n'en a écrit aucun (engine plus ancien)."""
    sac, tasks = engine_dir / "saccades.csv", engine_dir / "taches.csv"
    start = engine_dir / "demarrage.txt"
    if not (sac.is_file() or tasks.is_file() or start.is_file()):
        return None
    startup = None
    if start.is_file():
        text = start.read_text(encoding="utf-8").strip()
        if text.startswith(STARTUP_PREFIX):
            try:
                startup = float(text[len(STARTUP_PREFIX):].split()[0])
            except (ValueError, IndexError):
                pass
    return {"saccades": read_engine_csv(sac), "tasks": read_engine_csv(tasks), "startup_ms": startup}


def stall_summary(stalls: dict[str, Any]) -> dict[str, Any]:
    """Compte des saccades par cause (nombre, pire), les STALL_TOP pires, durées des tâches par type."""
    sac = [r for r in stalls["saccades"] if isinstance(r.get("frame_ms"), float)]
    causes: dict[str, dict[str, float]] = {}
    for r in sac:
        c = causes.setdefault(str(r.get("cause") or "inconnue"), {"count": 0, "worst_ms": 0.0, "total_ms": 0.0})
        c["count"] += 1
        c["worst_ms"] = max(c["worst_ms"], r["frame_ms"])
        c["total_ms"] += r["frame_ms"]
    tasks: dict[str, dict[str, float]] = {}
    for kind in sorted({str(r.get("kind")) for r in stalls["tasks"]}):
        v = [float(r["ms"]) for r in stalls["tasks"] if str(r.get("kind")) == kind and isinstance(r.get("ms"), float)]
        if v:
            tasks[kind] = {"count": len(v), "p50": statistics.median(v), "p99": percentile(v, 0.99), "max": max(v)}
    return {"count": len(sac), "causes": dict(sorted(causes.items(), key=lambda kv: -kv[1]["count"])),
            "top": sorted(sac, key=lambda r: -r["frame_ms"])[:STALL_TOP], "tasks": tasks,
            "startup_ms": stalls["startup_ms"]}


def stall_text(st: dict[str, Any]) -> str:
    lines = ["Démarrage : " + (f"première image jouable à {st['startup_ms'] / 1000:.1f} s"
                               if st["startup_ms"] is not None else "pas de première image jouable notée"),
             "", f"Saccades (images de plus de 33 ms) : {st['count']}"]
    for cause, c in st["causes"].items():
        lines.append(f"  {cause:<10} {c['count']:>5} image(s), pire {c['worst_ms']:.0f} ms, total {c['total_ms'] / 1000:.1f} s")
    if st["top"]:
        lines += ["", f"Les {len(st['top'])} pires saccades :", f"  {'t (s)':>8} {'ms':>7} {'distance':>9}  cause : étapes"]
        for r in st["top"]:
            dist = r.get("distance_m")
            lines.append(f"  {r.get('t_s', 0.0):>8.1f} {r['frame_ms']:>7.1f} "
                         f"{(f'{dist:.0f} m') if isinstance(dist, float) else '':>9}  {r.get('cause', '')} : {r.get('steps', '')}")
    if st["tasks"]:
        lines += ["", "Tâches de fond (ms) :", f"  {'type':<10} {'nombre':>7} {'médiane':>8} {'p99':>8} {'max':>8}"]
        for kind, t in st["tasks"].items():
            lines.append(f"  {kind:<10} {t['count']:>7} {t['p50']:>8.1f} {t['p99']:>8.1f} {t['max']:>8.1f}")
    return "\n".join(lines) + "\n"


# --- écriture ------------------------------------------------------------------------------

def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    cols = columns_of(rows)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(cols)
        for r in rows:
            w.writerow([f"{r[c]:.2f}" if isinstance(r.get(c), float) else r.get(c, "") for c in cols])


def svg_chart(rows: list[dict[str, Any]], title: str, series: tuple[tuple[str, str, str], ...],
              width: int = 900, height: int = 150) -> str:
    present = [(k, lab, col) for k, lab, col in series if values(rows, k)]
    if not present:
        return ""
    ts = values(rows, "t_s")
    tmin, tmax = (min(ts), max(ts)) if ts else (0.0, 1.0)
    span = max(tmax - tmin, 1.0)
    hi = max(max(values(rows, k)) for k, _, _ in present) or 1.0
    left, top, bottom = 50, 22, 18

    def pt(t: float, v: float) -> str:
        return f"{left + (t - tmin) / span * (width - left - 10):.1f},{top + (1 - v / hi) * (height - top - bottom):.1f}"

    parts = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img" aria-label="{html.escape(title)}">',
             f'<text x="2" y="14" class="lbl">{html.escape(title)}</text>',
             f'<text x="2" y="{top + 4}" class="lbl">{hi:.0f}</text>',
             f'<text x="2" y="{height - bottom}" class="lbl">0</text>',
             f'<text x="{width - 60}" y="{height - 4}" class="lbl">{span / 60:.1f} min</text>']
    x = 260
    for k, lab, col in present:
        line = " ".join(pt(float(r["t_s"]), float(r[k])) for r in rows
                        if isinstance(r.get(k), (int, float)) and isinstance(r.get("t_s"), (int, float)))
        parts.append(f'<polyline points="{line}" fill="none" stroke="{col}" stroke-width="1.4"/>')
        parts.append(f'<text x="{x}" y="14" class="lbl" fill="{col}">■ {html.escape(lab)}</text>')
        x += 14 + 8 * len(lab)
    parts.append("</svg>")
    return "".join(parts)


def write_report(rows: list[dict[str, Any]], out: Path, title: str = "Sonde de performance du moteur",
                 real_window: bool = True, engine_dir: Path | None = None) -> dict[str, Any]:
    """Écrit sonde.csv, sonde.txt et rapport.html dans `out` ; renvoie le résumé. Avec `engine_dir` (dossier
    du fichier de l'engine), y ajoute les saccades, les tâches de fond et le démarrage (lot X15), recopiés
    dans `out`."""
    out.mkdir(parents=True, exist_ok=True)
    write_csv(rows, out / "sonde.csv")
    summary = summarize(rows)
    text = summary_text(summary, title)
    summary["budgets"] = budget_checks(rows, real_window=real_window) if values(rows, "fps") else []
    if summary["budgets"]:
        text += "\nBudgets du préréglage (engine/tests/perf_targets.json, lot X14) :\n" + budget_text(summary["budgets"]) + "\n"
    stalls = read_stalls(engine_dir) if engine_dir is not None else None
    if stalls is not None:
        summary["stalls"] = stall_summary(stalls)
        text += "\n" + stall_text(summary["stalls"])
        for name in ("saccades.csv", "taches.csv", "demarrage.txt"):
            if (engine_dir / name).is_file() and (engine_dir / name).resolve() != (out / name).resolve():
                shutil.copyfile(engine_dir / name, out / name)
    (out / "sonde.txt").write_text(text, encoding="utf-8")
    charts = "\n".join(c for c in (svg_chart(rows, t, s) for t, s in CHARTS) if c)
    summary["presets"] = presets_of(rows)
    summary["preset"] = summary["presets"][-1] if summary["presets"] else ""
    preset = ", puis ".join(summary["presets"])
    (out / "rapport.html").write_text(f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>body{{font-family:sans-serif;margin:16px;max-width:960px}} pre{{background:#f4f4f4;padding:8px;overflow-x:auto}}
.chart{{width:100%;height:auto;border-bottom:1px solid #ddd;margin:6px 0}} .lbl{{font-size:11px;fill:#555}}</style></head>
<body><h1>{html.escape(title)}</h1>
<p>Préréglage {html.escape(str(preset) or "?")}. Une mesure par seconde : moyenne des images de la seconde
pour les temps de la vue, dernière image pour les compteurs du rendu.</p>
<pre>{html.escape(text)}</pre>
{charts}
</body></html>
""", encoding="utf-8")
    return summary


# --- commandes -----------------------------------------------------------------------------

def watch(engine_csv: Path, out: Path, duration_s: float | None, wait_s: float = 120.0, budgets: bool = False,
          idle_stop_s: float = IDLE_STOP_S, period_s: float = 1.0, quality: str | None = None) -> int:
    print(f"Sonde : attente du fichier de l'engine {engine_csv} …", flush=True)
    t0 = time.monotonic()
    while not engine_csv.is_file() and time.monotonic() - t0 < wait_s:
        time.sleep(0.5)
    if not engine_csv.is_file():
        print(f"Pas de fichier en {wait_s:.0f} s : l'engine est-il lancé avec --perf-probe ou OPENRIDE_PERF_PROBE ?")
        return 1
    sampler = SystemSampler(period_s)
    sampler.start()
    print("Sonde : mesure en cours (Ctrl+C pour arrêter).", flush=True)
    start = time.monotonic()
    last_size, last_change = -1, time.monotonic()
    try:
        while True:
            time.sleep(1.0)
            size = engine_csv.stat().st_size if engine_csv.is_file() else 0
            if size != last_size:
                last_size, last_change = size, time.monotonic()
            if time.monotonic() - last_change > idle_stop_s:
                print("Sonde : l'engine n'écrit plus, fin de la mesure.")
                break
            if duration_s is not None and time.monotonic() - start >= duration_s:
                break
    except KeyboardInterrupt:
        print()
    sampler.stop()
    rows = merge(read_engine_csv(engine_csv), sampler.rows)
    summary = write_report(rows, out, engine_dir=engine_csv.parent)
    print((out / "sonde.txt").read_text(encoding="utf-8"), end="")
    print(f"Rapport : {out / 'rapport.html'}")
    return max(_quality_verdict(summary, quality), _budget_verdict(summary, budgets))


def _budget_verdict(summary: dict[str, Any], strict: bool) -> int:
    """Code 1 si un budget est dépassé et que `--budgets` est demandé."""
    return 1 if strict and any(ok is False for ok, _, _ in summary.get("budgets", [])) else 0


def _quality_verdict(summary: dict[str, Any], quality: str | None) -> int:
    if not quality:
        return 0
    ok, msg = quality_check(summary, quality)
    print(f"[{'OK' if ok else 'ÉCHEC'}] qualité réellement appliquée : {msg}")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Sonde de performance du moteur (lot X13).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("watch", help="mesurer pendant que l'engine tourne")
    w.add_argument("--engine-csv", type=Path, default=Path(os.environ.get("OPENRIDE_PERF_PROBE", DEFAULT_ENGINE_CSV)),
                   help=f"fichier écrit par l'engine (défaut : OPENRIDE_PERF_PROBE ou {DEFAULT_ENGINE_CSV})")
    w.add_argument("--out", type=Path, help=f"dossier du rapport (défaut : {DEFAULT_OUT}/<date>)")
    w.add_argument("--duration", type=float, help="durée maximale en secondes")
    w.add_argument("--quality", help="préréglage voulu : échec si une seconde a été mesurée dans un autre (lot X32)")
    w.add_argument("--budgets", action="store_true", help="code 1 si un budget de perf_targets.json est dépassé (lot X14)")
    r = sub.add_parser("report", help="refaire le rapport d'un dossier (sonde.csv) ou d'un fichier de l'engine")
    r.add_argument("source", type=Path)
    r.add_argument("--out", type=Path)
    r.add_argument("--quality", help="préréglage voulu : échec si une seconde a été mesurée dans un autre (lot X32)")
    r.add_argument("--budgets", action="store_true", help="code 1 si un budget de perf_targets.json est dépassé (lot X14)")
    r.add_argument("--xvfb", action="store_true", help="mesure sous Xvfb : budgets en INFO")
    c = sub.add_parser("chauffe", help="temps GPU, charge, température et fréquence par tranche (dossier ou sonde.csv)")
    c.add_argument("source", type=Path)
    c.add_argument("--tranche-min", type=float, default=10.0, help="durée d'une tranche en minutes (défaut 10)")
    args = ap.parse_args(argv)
    if args.cmd == "watch":
        out = args.out or DEFAULT_OUT / datetime.now().strftime("%Y-%m-%d_%H%M%S")
        return watch(args.engine_csv.expanduser(), out, args.duration, quality=args.quality, budgets=args.budgets)
    src = args.source / "sonde.csv" if args.source.is_dir() else args.source
    rows = read_engine_csv(src)
    if not rows:
        print(f"Aucune mesure dans {src}")
        return 1
    if args.cmd == "chauffe":
        print(heat_text(heat_windows(rows, args.tranche_min * 60.0)), end="")
        return 0
    out = args.out or (args.source if args.source.is_dir() else args.source.parent)
    summary = write_report(rows, out, real_window=not args.xvfb, engine_dir=src.parent)
    print((out / "sonde.txt").read_text(encoding="utf-8"), end="")
    return max(_quality_verdict(summary, args.quality), _budget_verdict(summary, args.budgets))


if __name__ == "__main__":
    sys.exit(main())
