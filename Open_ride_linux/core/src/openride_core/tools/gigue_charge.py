"""Gigue de la boucle du core sous charge (lot X17, critère de la série W : p99 < 5 ms).

    python -m openride_core.tools.gigue_charge [--duree 120] [--charge compilation|cpu|aucune] [--strict]

Lance une séance simulée sans engine (`openride-core run --trainer sim --input none --autostart`, HOME
temporaire, parcours de démonstration) pendant qu'une charge tourne :
- `compilation` (défaut) : `openride-compiler build` d'une trace fabriquée de 40 km, sans réseau
  (couches route, terrain et segments ; MNT vide, altitude 0), relancée en boucle ;
- `cpu` : un processus de calcul par cœur ;
- `aucune` : la mesure de référence.

La séance écrit une ligne `Gigue` par minute et une pour la séance entière (module `jitter`) ; l'outil
la relit avec `log_report --gigue` et rend le verdict. Au cloud, le verdict est une information (code 0) ;
`--strict` (sur le PC) rend le code 1 si le p99 de la physique dépasse 5 ms. Sorties : `core.log`,
`gigue.txt` et `gigue.json` dans `~/OpenRide/gigue/<date>_<heure>/`.
"""

from __future__ import annotations

import argparse
import json
import math
import multiprocessing
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

from .log_report import format_jitter, jitter_report

DEFAULT_OUT = Path.home() / "OpenRide" / "gigue"
CHARGES = ("compilation", "cpu", "aucune")
TRACK_KM = 40.0


def write_track(path: Path, km: float = TRACK_KM) -> Path:
    """Trace GPX fabriquée : une boucle ondulée de `km` kilomètres autour du parcours de démonstration."""
    n = int(km * 1000 / 10)
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        r = km * 1000 / (2 * math.pi) + 150 * math.sin(7 * a)
        lat = 45.09 + r * math.cos(a) / 111_320
        lon = 6.06 + r * math.sin(a) / (111_320 * math.cos(math.radians(45.09)))
        pts.append(f'<trkpt lat="{lat:.6f}" lon="{lon:.6f}"><ele>{250 + 40 * math.sin(5 * a):.1f}</ele></trkpt>')
    path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="gigue_charge" '
                    'xmlns="http://www.topografix.com/GPX/1/1"><trk><name>charge</name><trkseg>'
                    + "".join(pts) + "</trkseg></trk></gpx>\n", encoding="utf-8")
    return path


def _spin(stop_at: float) -> None:
    x = 0.0
    while time.time() < stop_at:
        for i in range(10_000):
            x += math.sqrt(i)


def start_load(kind: str, tmp: Path, env: dict[str, str], duration: float) -> list[subprocess.Popen]:
    """Processus de charge, arrêtés par l'appelant (ou seuls à la fin de `duration` pour `cpu`)."""
    if kind == "aucune":
        return []
    if kind == "cpu":
        stop_at = time.time() + duration
        code = f"from openride_core.tools.gigue_charge import _spin\n_spin({stop_at})"
        return [subprocess.Popen([sys.executable, "-c", code], env=env, start_new_session=True)
                for _ in range(multiprocessing.cpu_count())]
    gpx = write_track(tmp / "charge.gpx")
    # Sans réseau : une liste de tuiles du MNT qui ne couvre pas la trace (la mer, altitude 0) suffit à
    # faire tout le travail du compilateur, terrain compris.
    dem = tmp / "dem" / "copernicus_glo30"
    dem.mkdir(parents=True)
    (dem / "tileList.txt").write_text("Copernicus_DSM_COG_10_N10_00_E010_00_DEM\n", encoding="utf-8")
    loop = (f"while true; do {sys.executable} -m openride_compiler build {gpx} --out {tmp / 'charge_out'} "
            f"--layers route,terrain,segments --offline --force >/dev/null 2>&1 && echo >> {tmp / 'builds.txt'}; done")
    return [subprocess.Popen(["bash", "-c", loop], env={**env, "OPENRIDE_DEM_CACHE": str(tmp / "dem")},
                             start_new_session=True)]


def stop_load(procs: list[subprocess.Popen]) -> None:
    for p in procs:
        if p.poll() is None:
            try:
                os.killpg(p.pid, signal.SIGTERM)   # la boucle de compilation et le build en cours
            except OSError:
                pass
    for p in procs:
        try:
            p.wait(10)
        except subprocess.TimeoutExpired:
            p.kill()


def run(duration: float, charge: str, out: Path) -> dict:
    repo = Path(__file__).resolve().parents[4]
    tmp = Path(tempfile.mkdtemp(prefix="openride-gigue-"))
    home = tmp / "home"
    routes = home / ".local" / "share" / "openride" / "routes"
    routes.mkdir(parents=True)
    paths = [str(repo / "core" / "src"), str(repo / "compiler" / "src")]
    env = {**os.environ, "HOME": str(home), "PYTHONUNBUFFERED": "1",
           "PYTHONPATH": os.pathsep.join(paths + ([os.environ["PYTHONPATH"]] if os.environ.get("PYTHONPATH") else []))}
    for k in ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
        env.pop(k, None)
    subprocess.run([sys.executable, "-m", "openride_core.tools.fake_world", "--demo", "--terrain", "--out",
                    str(routes)], check=True, env=env, stdout=subprocess.DEVNULL)
    log_path = out / "core.log"
    load = start_load(charge, tmp, env, duration + 5)
    try:
        with log_path.open("wb") as fh:
            core = subprocess.Popen([sys.executable, "-m", "openride_core", "run", "--trainer", "sim", "--input",
                                     "none", "--autostart", "--route", "demo", "--sim-scenario", "nominal"],
                                    env=env, stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
            time.sleep(duration)
            core.send_signal(signal.SIGTERM)
            try:
                core.wait(30)
            except subprocess.TimeoutExpired:
                core.kill()
                core.wait()
    finally:
        stop_load(load)
        builds = (tmp / "builds.txt").read_text().count("\n") if (tmp / "builds.txt").is_file() else 0
        shutil.rmtree(tmp, ignore_errors=True)
    rep = jitter_report(log_path.read_text(encoding="utf-8", errors="replace").splitlines())
    rep["charge"], rep["duree_s"], rep["compilations"] = charge, duration, builds
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gigue de la boucle du core sous charge (lot X17).")
    ap.add_argument("--duree", type=float, default=120.0, help="durée de la séance en secondes (défaut 120)")
    ap.add_argument("--charge", choices=CHARGES, default="compilation", help="charge pendant la séance")
    ap.add_argument("--strict", action="store_true", help="code 1 si le p99 de la physique dépasse 5 ms (PC)")
    ap.add_argument("--out", type=Path, help=f"dossier de sortie (défaut : {DEFAULT_OUT}/<date>)")
    args = ap.parse_args(argv)
    out = args.out or DEFAULT_OUT / datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    print(f"== séance simulée de {args.duree:.0f} s, charge : {args.charge} ==", flush=True)
    rep = run(args.duree, args.charge, out)
    text = format_jitter(rep) + (f"\nCompilations terminées pendant la séance : {rep['compilations']}"
                                 if args.charge == "compilation" else "")
    (out / "gigue.txt").write_text(text + "\n", encoding="utf-8")
    (out / "gigue.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(text)
    print(f"Résultats : {out}" + ("" if args.strict else " (verdict informatif ; --strict sur le PC)"))
    if rep["p99_ms"] is None:
        return 1
    return 1 if args.strict and not rep["ok"] else 0


if __name__ == "__main__":
    sys.exit(main())
