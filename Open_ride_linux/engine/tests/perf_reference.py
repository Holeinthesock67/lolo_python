#!/usr/bin/env python3
"""Référence de performance du moteur (lot X14).

    engine/tests/perf_reference.py run [--duree 300] [--qualite low,medium,high] [--mondes village,demo] [--native]
    engine/tests/perf_reference.py compare DOSSIER        # un passage déjà fait, face à la référence
    engine/tests/perf_reference.py update DOSSIER         # ce passage devient la référence

`run` lance `sim_bench.py --probe` (scénario `nominal`) sur des parcours fixes, pour chaque préréglage, puis
résume chaque mesure après la chauffe (médianes : images/s, p99, GPU de la vue, appels de dessin, triangles)
dans `<dossier>/resultat.json`, et la compare à `~/OpenRide/perf/reference.json` : alerte au-delà de
−5 % d'images/s ou de +1 ms de p99. Sans référence, le passage est seulement écrit (`update` pour l'adopter).
Les mondes : `village` (village simulé, montée et descente), `demo` (circuit d'essai), `osm` ; un parcours par
biome de démonstration (U19) s'ajoutera quand il existera.

Sous Xvfb (sans `--native`), le rendu est logiciel : écarts en INFO, code 0. Sur l'écran réel, une alerte
donne le code 1. Dossier : `~/OpenRide/perf/<date>_<heure>/` (`--out`). Bibliothèque standard seulement.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR))
import compare_bench  # noqa: E402
import perf_probe  # noqa: E402

PERF_DIR = Path.home() / "OpenRide" / "perf"
REFERENCE = PERF_DIR / "reference.json"
FPS_DROP_PCT = 5.0     # alerte : images/s en baisse de plus de 5 %
P99_RISE_MS = 1.0      # alerte : p99 en hausse de plus de 1 ms
DEFAULT_WORLDS = ("village", "demo")
DEFAULT_QUALITIES = ("low", "medium", "high")


def bench_command(godot: str, world: str, quality: str, duration: float, out: Path, native: bool) -> list[str]:
    cmd = [sys.executable, str(TESTS_DIR / "sim_bench.py"), "--godot", godot, "--scenario", "nominal",
           "--world", world, "--quality", quality, "--duration", f"{duration:g}", "--probe", "--muet",
           "--out", str(out)]
    return cmd + (["--native"] if native else [])


def summarize_run(folder: Path, warmup_s: float) -> dict[str, Any]:
    """Résumé d'une mesure du banc : médianes après la chauffe et préréglage appliqué."""
    side = compare_bench.load_side(folder, warmup_s)
    metrics = next(iter(side.entries.values()), {})
    preset = next(iter(side.presets.values()), "")
    return {"metrics": metrics, "preset": preset}


def alerts(result: dict[str, Any], reference: dict[str, Any]) -> list[str]:
    """Écarts au-delà des seuils, mesure par mesure (monde/préréglage présents des deux côtés)."""
    out: list[str] = []
    for key, run in result["runs"].items():
        ref = reference.get("runs", {}).get(key)
        if ref is None:
            continue
        m, r = run["metrics"], ref["metrics"]
        if "fps" in m and r.get("fps"):
            drop = (r["fps"] - m["fps"]) / r["fps"] * 100.0
            if drop > FPS_DROP_PCT:
                out.append(f"{key} : images/s {r['fps']:.1f} → {m['fps']:.1f} (−{drop:.1f} %, seuil {FPS_DROP_PCT:g} %)")
        if "p99_ms" in m and "p99_ms" in r and m["p99_ms"] - r["p99_ms"] > P99_RISE_MS:
            out.append(f"{key} : p99 {r['p99_ms']:.1f} → {m['p99_ms']:.1f} ms (+{m['p99_ms'] - r['p99_ms']:.1f} ms, "
                       f"seuil +{P99_RISE_MS:g} ms)")
        if run.get("preset") and ref.get("preset") and run["preset"] != ref["preset"]:
            out.append(f"{key} : préréglage appliqué {run['preset']} contre {ref['preset']} dans la référence")
    return out


def report(result: dict[str, Any], reference_path: Path) -> int:
    native = bool(result.get("native"))
    for key, run in result["runs"].items():
        m = run["metrics"]
        print(f"  {key:<16} {run.get('preset') or '?':<7} " + ", ".join(
            f"{compare_bench.METRICS[k][0]} {v:.2f}" for k, v in m.items() if k in compare_bench.METRICS))
    if not reference_path.is_file():
        print(f"Pas de référence ({reference_path}) : « perf_reference.py update DOSSIER » pour adopter ce passage.")
        return 0
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    if bool(reference.get("native")) != native:
        print(f"[INFO] référence mesurée {'sur écran réel' if reference.get('native') else 'sous Xvfb'}, passage "
              f"{'sur écran réel' if native else 'sous Xvfb'} : comparaison indicative")
    found = alerts(result, reference)
    tag = "ÉCHEC" if native and bool(reference.get("native")) else "INFO"
    for a in found:
        print(f"[{tag}] {a}")
    if not found:
        print(f"[OK] dans la référence du {reference.get('date', '?')} (images/s −{FPS_DROP_PCT:g} %, p99 +{P99_RISE_MS:g} ms)")
    return 1 if found and tag == "ÉCHEC" else 0


def cmd_run(args: argparse.Namespace) -> int:
    out = args.out or PERF_DIR / time.strftime("%Y-%m-%d_%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    warmup = float(perf_probe.load_targets().get("warmup_s", 0))
    result: dict[str, Any] = {"date": time.strftime("%Y-%m-%d %H:%M"), "native": args.native,
                              "duration_s": args.duree, "runs": {}}
    failed = []
    for world in args.mondes:
        for quality in args.qualite:
            key = f"{world}/{quality}"
            folder = out / f"{world}_{quality}"
            print(f"== {key} ({args.duree:g} s) …", flush=True)
            cmd = bench_command(args.godot, world, quality, args.duree, folder, args.native)
            rc = subprocess.run(cmd, cwd=TESTS_DIR, check=False,
                                stdout=open(out / f"{world}_{quality}.log", "w", encoding="utf-8"),
                                stderr=subprocess.STDOUT).returncode
            try:
                result["runs"][key] = {**summarize_run(folder, warmup), "bench_rc": rc}
            except SystemExit as exc:
                failed.append(f"{key} : {exc}")
                continue
            if rc != 0:
                failed.append(f"{key} : banc en échec (code {rc}, {folder / 'nominal' / 'rapport.html'})")
    (out / "resultat.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    for f in failed:
        print(f"[ÉCHEC] {f}")
    code = report(result, args.reference)
    print(f"Passage : {out / 'resultat.json'}")
    return 1 if failed else code


def _load_result(folder: Path) -> dict[str, Any]:
    path = folder / "resultat.json" if folder.is_dir() else folder
    if not path.is_file():
        raise SystemExit(f"pas de resultat.json dans {folder}")
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Référence de performance du moteur (lot X14).")
    ap.add_argument("--reference", type=Path, default=REFERENCE, help=f"fichier de référence (défaut {REFERENCE})")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="mesurer et comparer à la référence")
    r.add_argument("--godot", default=os.environ.get("GODOT", str(Path.home() / "Applications/godot/Godot_v4.3-stable_linux.x86_64")))
    r.add_argument("--duree", type=float, default=300.0, help="durée de chaque mesure en s (défaut 300)")
    r.add_argument("--qualite", type=lambda s: [q for q in s.split(",") if q], default=list(DEFAULT_QUALITIES))
    r.add_argument("--mondes", type=lambda s: [w for w in s.split(",") if w], default=list(DEFAULT_WORLDS))
    r.add_argument("--native", action="store_true", help="écran réel (sinon Xvfb, mesures en INFO)")
    r.add_argument("--out", type=Path)
    c = sub.add_parser("compare", help="comparer un passage à la référence")
    c.add_argument("dossier", type=Path)
    u = sub.add_parser("update", help="adopter un passage comme référence")
    u.add_argument("dossier", type=Path)
    args = ap.parse_args(argv)
    if args.cmd == "run":
        return cmd_run(args)
    try:
        result = _load_result(args.dossier)
    except SystemExit as exc:
        print(f"ÉCHEC : {exc}", file=sys.stderr)
        return 2
    if args.cmd == "compare":
        return report(result, args.reference)
    args.reference.parent.mkdir(parents=True, exist_ok=True)
    if args.reference.is_file():
        shutil.copy2(args.reference, args.reference.with_name(f"reference-{time.strftime('%Y%m%d-%H%M%S')}.json"))
    args.reference.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Référence mise à jour : {args.reference} (passage du {result.get('date', '?')})")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(TESTS_DIR.parents[1] / "scripts"))
    from isolation_tests import verrou_suite   # une seule suite de tests ou banc à la fois

    with verrou_suite("perf_reference"):
        code = main()
    sys.exit(code)
